"""run_all.py - 按顺序运行全部脚本（每步都以 `python -I -X utf8` 独立进程运行，工作目录为项目根目录）

用法（在仓库根目录）:
    python -I -B -X utf8 scripts/run_all.py

-I：隔离模式，不把脚本目录/当前目录加入 sys.path，也忽略 PYTHON* 环境变量（数据目录中的任何文件都不会被当作代码导入）。
-X utf8：标准输出使用 UTF-8（-I 会忽略 PYTHONIOENCODING）。
-B：不写 __pycache__，保持项目目录整洁。
原始数据目录可用环境变量 NHTSA_SGO_DIR 覆盖（见 config.py）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["00_inspect_raw.py", "01_clean.py", "02_analyze.py", "03_figures.py"]

for step in STEPS:
    print(f"\n>>> {step}", flush=True)
    r = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", str(HERE / step)], cwd=str(HERE.parent))
    if r.returncode != 0:
        sys.exit(f"{step} 失败（exit {r.returncode}）")
print("\n全部完成：output/tables、output/clean、output/figures 已更新")
