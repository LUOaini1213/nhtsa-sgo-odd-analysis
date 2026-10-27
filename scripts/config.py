"""config.py - 路径与常量（所有脚本共用）

原始数据路径可用环境变量 NHTSA_SGO_DIR 覆盖；默认指向仓库内的 data/raw/（NHTSA 官方 CSV 的原样副本）。
原始文件只读，本项目从不在下载目录中写入或执行任何东西。
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = Path(
    os.environ.get(
        "NHTSA_SGO_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "raw"),
    )
)
RAW_FILES = {
    "ADS": RAW_DIR / "SGO-2021-01_Incident_Reports_ADS.csv",
    "ADAS": RAW_DIR / "SGO-2021-01_Incident_Reports_ADAS.csv",
}
OUTPUT_DIR = PROJECT_DIR / "output"
TABLE_DIR = OUTPUT_DIR / "tables"
FIG_DIR = OUTPUT_DIR / "figures"
CLEAN_DIR = OUTPUT_DIR / "clean"

# 数据版本说明（NHTSA 页面显示的数据更新日期，由用户下载时记录）
DATA_UPDATED = "2026-10-15"
