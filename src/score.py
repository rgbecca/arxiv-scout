"""
用 DeepSeek 对论文做相关性评分 + 生成一句话中文摘要。
为节省 token：
  - 关键词匹配的论文优先送 LLM 评分
  - 每次送一批（10篇）的标题+摘要，让 LLM 批量打分
"""

import json
import os
import asyncio

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def _build_system_prompt(description: str) -> str:
    return f"""你是一个学术论文筛选助手。用户的研究方向如下：

{description}

你的任务：
1. 阅读每篇论文的标题和摘要
2. 给出 1-10 的相关性评分（10=完美匹配研究方向，1=完全无关）
3. 用中文写一句话摘要（不超过40字，说清楚这篇论文做了什么）

如果论文标注了 Confirmed venue（已确认被顶会/顶刊接收或发表），这是论文质量的
强信号，在相关性相近时可以适当加分；但评分核心依据仍是与研究方向的相关性，
不要因为顶会接收就给明显不相关的论文打高分。

严格按以下 JSON 格式返回，不要输出任何其他内容：
[
  {{"id": "论文arxiv_id", "score": 8, "summary_zh": "一句话中文摘要"}},
  ...
]"""


def _build_user_prompt(papers: list[dict]) -> str:
    lines = []
    for p in papers:
        venue_line = f"\nConfirmed venue: {p['confirmed_venue']}" if p.get("confirmed_venue") else ""
        lines.append(
            f"---\nID: {p['arxiv_id']}\n"
            f"Title: {p['title']}\n"
            f"Abstract: {p['abstract'][:500]}"
            f"{venue_line}\n"
        )
    return "\n".join(lines)


async def _call_deepseek(system: str, user: str, config: dict) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")

    model = config["llm"].get("model", "deepseek-v4-0324")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


async def score_papers(papers: list[dict], config: dict) -> list[dict]:
    """
    对论文批量评分。关键词匹配的优先，分批送 LLM（每批10篇）。
    返回带 score 和 summary_zh 字段的论文列表。
    """
    description = config["discovery"]["description"]
    system_prompt = _build_system_prompt(description)

    # 关键词匹配的排前面
    papers_sorted = sorted(papers, key=lambda p: not p.get("keyword_match", False))

    # 限制总量：最多评分 100 篇（控制成本）
    to_score = papers_sorted[:100]

    # 分批，每批 10 篇
    batch_size = 10
    batches = [
        to_score[i : i + batch_size] for i in range(0, len(to_score), batch_size)
    ]

    all_scored = []

    for i, batch in enumerate(batches):
        print(f"      评分批次 {i+1}/{len(batches)} ({len(batch)} 篇)...")
        user_prompt = _build_user_prompt(batch)

        try:
            raw = await _call_deepseek(system_prompt, user_prompt, config)
            # 解析 JSON — 处理 LLM 可能返回的各种格式
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

            parsed = json.loads(raw)
            # 有时 LLM 返回 {"results": [...]} 而不是直接的列表
            if isinstance(parsed, dict):
                parsed = parsed.get("results", parsed.get("papers", list(parsed.values())[0]))

            # 合并评分到论文数据
            score_map = {item["id"]: item for item in parsed}
            for paper in batch:
                if paper["arxiv_id"] in score_map:
                    s = score_map[paper["arxiv_id"]]
                    paper["score"] = int(s.get("score", 1))
                    paper["summary_zh"] = s.get("summary_zh", "（摘要生成失败）")
                else:
                    paper["score"] = 0
                    paper["summary_zh"] = "（未评分）"
                all_scored.append(paper)

        except Exception as e:
            print(f"      [警告] 批次 {i+1} 评分失败: {e}")
            # 失败的批次给默认分
            for paper in batch:
                paper["score"] = 0
                paper["summary_zh"] = "（评分失败）"
                all_scored.append(paper)

        # arXiv API 和 DeepSeek 都有速率限制，稍等一下
        if i < len(batches) - 1:
            await asyncio.sleep(1)

    return all_scored
