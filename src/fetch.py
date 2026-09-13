"""
从 arXiv API 拉取昨日新论文，按关键词预筛选。
arXiv API 文档: https://info.arxiv.org/help/api/index.html
"""

import asyncio
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

# arXiv Atom feed namespace
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"

# 顶会/顶刊名称（用于从 comment 字段里识别是否已确认接收）
_VENUE_NAMES = [
    "CVPR", "ICCV", "ECCV", "NeurIPS", "NIPS", "ICML", "ICLR", "AAAI", "IJCAI",
    "ACL", "EMNLP", "NAACL", "CoRL", "ICRA", "IROS", "RSS", "SIGGRAPH", "KDD",
    "WWW", "UAI", "COLM", "TPAMI", "IJCV", "JMLR",
]
_VENUE_RE = re.compile(
    r"\b(" + "|".join(_VENUE_NAMES) + r")\b['’]?\s*(\d{2,4})?", re.IGNORECASE
)
_ACCEPT_RE = re.compile(
    r"\b(accept(ed)?|to appear|camera[- ]ready|in proceedings|proceedings of|published (in|at))\b",
    re.IGNORECASE,
)


def extract_confirmed_venue(comment: str | None, journal_ref: str | None) -> str | None:
    """
    从 arXiv 的 comment / journal_ref 字段里启发式识别"已确认接收"的顶会/顶刊。
    journal_ref 有值代表已经正式发表，直接采用；否则在 comment 里找
    "accepted/to appear..." 这类措辞 + 会议名，避免把"投稿中"误判为"已接收"。
    这只能覆盖作者自己更新过备注的论文，不是全量判断。
    """
    if journal_ref:
        return journal_ref.strip()[:80]
    if not comment or not _ACCEPT_RE.search(comment):
        return None
    m = _VENUE_RE.search(comment)
    if not m:
        return None
    venue, year = m.group(1).upper(), m.group(2)
    return f"{venue} {year}" if year else venue


async def fetch_papers(discovery_config: dict) -> list[dict]:
    """
    拉取 arXiv 指定分类的近期论文，用关键词预筛。
    返回 [{arxiv_id, title, authors, abstract, categories, published, url}, ...]
    """
    categories = discovery_config["arxiv_categories"]
    keywords = [kw.lower() for kw in discovery_config.get("keywords", [])]

    # 构建查询：多个分类用 OR 连接
    cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)

    # arXiv API 每次最多返回一定数量，我们取最近的论文
    # submittedDate 范围：过去 3 天（arXiv 周末不更新，所以多取几天保险）
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=3)).strftime("%Y%m%d")
    date_to = now.strftime("%Y%m%d")

    # 用 search_query + sortBy=submittedDate 获取最新论文
    base_url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"({cat_query})",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": 300,  # 拉够多的，后面筛
    }
    url = f"{base_url}?{urllib.parse.urlencode(params, safe='+:()/')}"

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entries = root.findall(f"{ATOM}entry")

    papers = []
    for entry in entries:
        arxiv_id = entry.find(f"{ATOM}id").text.strip().split("/abs/")[-1]
        # 去掉版本号 (v1, v2, ...)
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)

        title = entry.find(f"{ATOM}title").text.strip().replace("\n", " ")
        title = re.sub(r"\s+", " ", title)

        abstract = entry.find(f"{ATOM}summary").text.strip().replace("\n", " ")
        abstract = re.sub(r"\s+", " ", abstract)

        authors = [
            a.find(f"{ATOM}name").text.strip()
            for a in entry.findall(f"{ATOM}author")
        ]

        published = entry.find(f"{ATOM}published").text.strip()

        # 论文分类
        cats = [
            c.get("term")
            for c in entry.findall(f"{ATOM}category")
        ]

        # PDF 链接
        pdf_url = f"https://arxiv.org/abs/{arxiv_id}"

        comment_el = entry.find(f"{ARXIV}comment")
        comment = comment_el.text.strip() if comment_el is not None and comment_el.text else None
        journal_ref_el = entry.find(f"{ARXIV}journal_ref")
        journal_ref = journal_ref_el.text.strip() if journal_ref_el is not None and journal_ref_el.text else None
        confirmed_venue = extract_confirmed_venue(comment, journal_ref)

        paper = {
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": cats,
            "published": published,
            "url": pdf_url,
            "confirmed_venue": confirmed_venue,
        }

        # 关键词预筛：标题或摘要包含任一关键词
        if keywords:
            text = (title + " " + abstract).lower()
            if any(kw in text for kw in keywords):
                paper["keyword_match"] = True
                papers.append(paper)
            else:
                # 不匹配关键词的也保留，但标记为 False
                # LLM 评分阶段可能仍然判定相关
                paper["keyword_match"] = False
                papers.append(paper)

    return papers
