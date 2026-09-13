"""
SQLite 存储层：论文元数据持久化 + 去重。
数据库文件跟 repo 一起提交（通过 GitHub Actions 自动 commit），
这样你本地也能 pull 下来查历史记录。
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def init_db(db_path: Path):
    """初始化数据库表"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            arxiv_id       TEXT PRIMARY KEY,
            title          TEXT NOT NULL,
            authors        TEXT,
            abstract       TEXT,
            categories     TEXT,
            published      TEXT,
            url            TEXT,
            score          INTEGER,
            summary_zh     TEXT,
            pushed_at      TEXT,
            starred        INTEGER DEFAULT 0,
            confirmed_venue TEXT,
            deep_read_at   TEXT
        )
    """)
    # 兼容旧数据库：老库没有这些列，补上即可，已存在则忽略
    for column, coltype in [("confirmed_venue", "TEXT"), ("deep_read_at", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {column} {coltype}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()


def is_paper_seen(db_path: Path, arxiv_id: str) -> bool:
    """检查论文是否已在数据库中"""
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT 1 FROM papers WHERE arxiv_id = ?", (arxiv_id,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def get_paper(db_path: Path, arxiv_id: str) -> dict | None:
    """按 arxiv_id 查询单篇论文，返回 dict 或 None"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_recent_unstarred(db_path: Path, limit: int = 30) -> list[dict]:
    """列出近期已推送、尚未 star 的论文，按推送时间倒序"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT arxiv_id, title, score, pushed_at FROM papers
        WHERE starred = 0 AND pushed_at IS NOT NULL
        ORDER BY pushed_at DESC, score DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_starred(db_path: Path, arxiv_id: str) -> bool:
    """标记某篇论文为 starred，返回是否命中"""
    conn = sqlite3.connect(db_path)
    cur = conn.execute("UPDATE papers SET starred = 1 WHERE arxiv_id = ?", (arxiv_id,))
    conn.commit()
    hit = cur.rowcount > 0
    conn.close()
    return hit


def get_starred_unread(db_path: Path) -> list[str]:
    """列出已 star 但还没精读过的论文 arxiv_id"""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT arxiv_id FROM papers WHERE starred = 1 AND deep_read_at IS NULL"
    )
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids


def mark_deep_read(db_path: Path, arxiv_id: str) -> bool:
    """标记某篇论文已经跑过 paperwise 精读，返回是否命中"""
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "UPDATE papers SET deep_read_at = ? WHERE arxiv_id = ?", (now, arxiv_id)
    )
    conn.commit()
    hit = cur.rowcount > 0
    conn.close()
    return hit


def store_papers(db_path: Path, papers: list[dict]):
    """将论文写入数据库"""
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()

    for p in papers:
        conn.execute(
            """
            INSERT OR REPLACE INTO papers
            (arxiv_id, title, authors, abstract, categories, published, url, score, summary_zh, pushed_at, confirmed_venue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["arxiv_id"],
                p["title"],
                json.dumps(p.get("authors", []), ensure_ascii=False),
                p.get("abstract", ""),
                json.dumps(p.get("categories", []), ensure_ascii=False),
                p.get("published", ""),
                p.get("url", ""),
                p.get("score", 0),
                p.get("summary_zh", ""),
                now,
                p.get("confirmed_venue"),
            ),
        )

    conn.commit()
    conn.close()
    print(f"      已存储 {len(papers)} 篇论文")
