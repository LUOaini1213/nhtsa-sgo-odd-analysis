"""check_tables.py - 逐字节比对 output/tables/ 与已提交（git HEAD）的版本

用法（在仓库根目录，先运行 run_all.py）:
    python -I -B -X utf8 scripts/run_all.py
    python -I -B -X utf8 scripts/check_tables.py

比对的是磁盘上的原始字节与 git 中存储的字节（不经过行尾转换），
所以 CRLF/LF 差异、BOM 差异、任何数值变化都会被报出来。
也会报出 output/tables/ 下多出或缺少的 CSV。
退出码：0 = 全部一致；1 = 有差异；2 = 无法运行（例如不在 git 仓库中）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = "output/tables"


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def main() -> int:
    try:
        tracked = [p for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", TABLES).decode("utf-8").splitlines()
                   if p.endswith(".csv")]
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"无法读取 git HEAD：{err}", file=sys.stderr)
        return 2
    if not tracked:
        print(f"git HEAD 中没有 {TABLES}/*.csv", file=sys.stderr)
        return 2

    problems: list[str] = []
    on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / TABLES).glob("*.csv")}
    for extra in sorted(on_disk - set(tracked)):
        problems.append(f"多出的表（未提交）：{extra}")
    for rel in tracked:
        path = ROOT / rel
        if not path.exists():
            problems.append(f"缺少：{rel}")
            continue
        got = path.read_bytes()
        want = git("cat-file", "blob", f"HEAD:{rel}")
        if got != want:
            hint = "（含 CRLF 行尾）" if b"\r\n" in got and b"\r\n" not in want else ""
            problems.append(f"不一致{hint}：{rel}（磁盘 {len(got)} 字节，HEAD {len(want)} 字节）")

    if problems:
        print("output/tables 与已提交版本不一致：")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"OK：{len(tracked)} 张表与 git HEAD 逐字节一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
