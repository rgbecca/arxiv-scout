"""
star.py — 收藏待精读论文；可通过 --download 额外下载本地 PDF。

用法（在 src/ 目录下运行）：
    # 直接指定 arXiv ID（可传多个）
    python star.py 2506.00001 2506.00123

    # 不传参数则进入交互模式：列出近期已推送、还没 star 的论文，输入序号选择
    python star.py

    python star.py --download 2506.00001
"""

import argparse
import re
import unicodedata
from pathlib import Path

import httpx

from config_loader import load_config
from store import init_db, get_paper, get_recent_unstarred, mark_starred

ARXIV_ID_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def slugify(title: str, max_len: int = 60) -> str:
    """精简标题为文件名片段：与 paperwise 风格保持一致（保留大小写，下划线分隔）"""
    text = unicodedata.normalize("NFKD", title)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.ASCII).strip()
    text = re.sub(r"[\s-]+", "_", text)
    return text[:max_len].strip("_") or "untitled"


def download_pdf(arxiv_id: str, title: str, papers_dir: Path) -> Path:
    papers_dir.mkdir(parents=True, exist_ok=True)
    # 文件名规则对齐 paperwise：Arxiv ID 的 "." 换成 "_" + 精简标题
    dest = papers_dir / f"{arxiv_id.replace('.', '_')}_{slugify(title)}.pdf"

    if dest.exists():
        print(f"      [跳过] {dest.name} 已存在")
        return dest

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(f"https://arxiv.org/pdf/{arxiv_id}.pdf")
        resp.raise_for_status()
        dest.write_bytes(resp.content)

    print(f"      [下载完成] {dest.name}")
    return dest


def interactive_select(db_path: Path) -> list[str]:
    """列出近期未 star 的论文，让用户输入序号选择"""
    candidates = get_recent_unstarred(db_path)
    if not candidates:
        print("没有待选的论文（都已 star，或还没有推送记录）。")
        return []

    print("\n近期已推送、尚未 star 的论文：\n")
    for i, p in enumerate(candidates, 1):
        print(f"  [{i:2d}] ({p['score']}/10) {p['title']}  · {p['arxiv_id']}")

    raw = input("\n输入要 star 的序号（空格分隔，直接回车取消）：").strip()
    if not raw:
        return []

    ids = []
    for tok in raw.split():
        if tok.isdigit() and 1 <= int(tok) <= len(candidates):
            ids.append(candidates[int(tok) - 1]["arxiv_id"])
        else:
            print(f"      [忽略] 无效序号: {tok}")
    return ids


def main():
    parser = argparse.ArgumentParser(description="收藏待精读论文，默认不下载 PDF")
    parser.add_argument("arxiv_ids", nargs="*", help="arXiv ID；留空则交互选择")
    parser.add_argument("--download", action="store_true", help="同时下载 PDF 作为本地备份")
    args = parser.parse_args()

    config = load_config()
    db_path = Path(__file__).parent.parent / config["storage"]["db_path"]
    papers_dir = Path(__file__).parent.parent / config.get("paperwise", {}).get("papers_dir", "papers")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    if args.arxiv_ids:
        arxiv_ids = []
        for a in args.arxiv_ids:
            cleaned = re.sub(r"v\d+$", "", a.strip())
            if not ARXIV_ID_RE.match(a.strip()):
                print(f"[警告] 「{a}」看起来不是合法的 arXiv ID，已跳过")
                continue
            arxiv_ids.append(cleaned)
    else:
        arxiv_ids = interactive_select(db_path)

    if not arxiv_ids:
        print("没有要 star 的论文。")
        return

    for arxiv_id in dict.fromkeys(arxiv_ids):
        paper = get_paper(db_path, arxiv_id)
        if paper is None:
            print(f"[跳过] {arxiv_id} 不在数据库中（还没被推送过）")
            continue

        mark_starred(db_path, arxiv_id)
        print(f"[⭐] {paper['title']} ({arxiv_id})")
        if args.download:
            try:
                download_pdf(arxiv_id, paper["title"], papers_dir)
            except Exception as e:
                print(f"      [错误] PDF 下载失败，收藏已保留: {e}")

    print("\n收藏处理完成，可运行 deepread.py 精读待处理论文。")


if __name__ == "__main__":
    main()
