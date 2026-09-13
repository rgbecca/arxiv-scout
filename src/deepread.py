"""
deepread.py — 对 star.py 标记过的论文，批量调用 paperwise (`rh read`) 生成精读报告。

前提：本地已 clone + `pip install -e .` 装好 paperwise（独立仓库），
并设置环境变量指向该仓库：
    export PAPERWISE_REPO_DIR="/Users/xxx/Documents/paperwise"

用法（在 src/ 目录下运行）：
    python deepread.py              # 处理所有已 star 但还没精读的论文
    python deepread.py 2506.00001   # 只处理指定的论文（不要求已 star）
"""

import os
import subprocess
import sys
from pathlib import Path

from config_loader import load_config
from store import init_db, get_paper, get_starred_unread, mark_deep_read


def _resolve_paperwise_repo() -> Path:
    repo_dir = os.environ.get("PAPERWISE_REPO_DIR")
    if not repo_dir:
        print("[错误] 请先设置环境变量 PAPERWISE_REPO_DIR，指向 paperwise 仓库所在目录，例如：")
        print('       export PAPERWISE_REPO_DIR="/Users/xxx/Documents/paperwise"')
        sys.exit(1)
    path = Path(repo_dir).expanduser().resolve()
    if not path.exists():
        print(f"[错误] PAPERWISE_REPO_DIR 指向的目录不存在: {path}")
        sys.exit(1)
    return path


def _resolve_rh_bin(repo_dir: Path) -> str:
    # paperwise 装在自己的 venv 里，优先用它自己的 rh；找不到就假设 rh 在 PATH 上
    venv_rh = repo_dir / ".venv" / "bin" / "rh"
    return str(venv_rh) if venv_rh.exists() else "rh"


def deep_read_one(rh_bin: str, repo_dir: Path, arxiv_id: str) -> bool:
    # --pdf 不会补取日期、分类和摘要，因此始终通过 ID 获取完整元数据。
    cmd = [rh_bin, "read", "--arxiv", arxiv_id]
    print("      按 arXiv ID 获取元数据，由 paperwise 管理 PDF 缓存")
    result = subprocess.run(cmd, cwd=repo_dir)
    return result.returncode == 0


def main():
    config = load_config()
    db_path = Path(__file__).parent.parent / config["storage"]["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    repo_dir = _resolve_paperwise_repo()
    rh_bin = _resolve_rh_bin(repo_dir)

    args = sys.argv[1:]
    arxiv_ids = args if args else get_starred_unread(db_path)

    if not arxiv_ids:
        print("没有待精读的论文（都已处理，或还没有 star 任何论文）。")
        return

    print(f"待精读 {len(arxiv_ids)} 篇：{', '.join(arxiv_ids)}")

    for arxiv_id in arxiv_ids:
        paper = get_paper(db_path, arxiv_id)
        title = paper["title"] if paper else arxiv_id
        print(f"\n[精读] {title} ({arxiv_id})")

        ok = deep_read_one(rh_bin, repo_dir, arxiv_id)
        if ok:
            mark_deep_read(db_path, arxiv_id)
            print(f"      完成，报告在 {repo_dir}/outputs/ 下按 arxiv_id+标题 命名的目录里")
        else:
            print(f"      [错误] {arxiv_id} 精读失败，跳过")


if __name__ == "__main__":
    main()
