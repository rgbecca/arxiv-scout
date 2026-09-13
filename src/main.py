"""
arxiv-daily: 每日论文推送系统
1. 从 arXiv 拉取昨天的新论文
2. 用关键词预筛选
3. 用 DeepSeek 评分 + 生成一句话中文摘要
4. 取 top_k 篇存入 SQLite
5. 发送邮件推送
"""

import asyncio
import sys
from pathlib import Path

from fetch import fetch_papers
from score import score_papers
from store import init_db, store_papers, is_paper_seen
from email_push import send_digest
from config_loader import load_config


async def main():
    config = load_config()
    print(f"[arxiv-daily] 研究方向: {config['discovery']['description'][:80]}...")

    # 1. 拉取论文
    print("[1/4] 从 arXiv 拉取新论文...")
    raw_papers = await fetch_papers(config["discovery"])
    print(f"      拉取到 {len(raw_papers)} 篇原始论文")

    if not raw_papers:
        print("      今日无新论文（周末/节假日），跳过。")
        return

    # 2. 初始化数据库 & 去重
    db_path = Path(__file__).parent.parent / config["storage"]["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    unseen = [p for p in raw_papers if not is_paper_seen(db_path, p["arxiv_id"])]
    print(f"      去重后 {len(unseen)} 篇新论文")

    if not unseen:
        print("      所有论文已推送过，跳过。")
        return

    # 3. LLM 评分
    print("[2/4] DeepSeek 评分中...")
    scored = await score_papers(unseen, config)
    min_score = config["discovery"].get("min_score", 5)
    qualified = [p for p in scored if p["score"] >= min_score]
    qualified.sort(key=lambda x: x["score"], reverse=True)
    top_k = config["discovery"].get("top_k", 10)
    selected = qualified[:top_k]
    print(f"      评分完成，{len(qualified)} 篇达标，推送 {len(selected)} 篇")

    if not selected:
        print("      无达标论文，跳过推送。")
        return

    # 4. 存储
    print("[3/4] 存入数据库...")
    store_papers(db_path, selected)

    # 5. 推送
    print("[4/4] 发送邮件...")
    send_digest(selected, config)
    print("[完成] 推送成功！")


if __name__ == "__main__":
    asyncio.run(main())
