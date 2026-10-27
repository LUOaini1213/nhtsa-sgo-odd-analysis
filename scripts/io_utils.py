"""io_utils.py - 安全读取原始 CSV

- 全部列按字符串 (dtype=str) 读取，避免类型推断把编号/邮编/日期误转换；
- 不把任何字符串当作 NA（keep_default_na=False），空字符串之后由清洗规则统一处理，
  这样 "N/A"、"NA" 之类的原始取值不会被 pandas 静默吞掉；
- 编码先试 utf-8-sig，失败再退回 cp1252（NHTSA 文件历史上出现过 Windows 编码字符）。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_raw(path: Path) -> pd.DataFrame:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "cp1252"):
        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                na_values=[],
                encoding=enc,
                low_memory=False,
            )
            df.attrs["encoding"] = enc
            # 列名去首尾空白（不改变大小写与内容）
            df.columns = [c.strip() for c in df.columns]
            return df
        except UnicodeDecodeError as err:  # 退回下一种编码
            last_err = err
    raise RuntimeError(f"无法解码 {path}: {last_err}")


BOOL_COLS = [
    "weather_known", "surface_known", "rain", "adverse_weather", "wet_surface", "rain_or_wet",
    "rain_or_wet_known", "sv_rear_contact", "sv_front_contact", "engaged", "airbag_sv",
]
NUM_COLS = [
    "speed_mph", "hour", "night_20_06", "night_22_05", "info_missing", "n_reports_linked",
    "n_versions_in_file", "min_version_in_file",
]


def read_clean(path: Path) -> pd.DataFrame:
    """读取 01_clean.py 的输出，并恢复布尔/数值列类型。"""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    for c in BOOL_COLS:
        if c in df.columns:
            df[c] = df[c].map({"True": True, "False": False}).astype(bool)
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")  # 空字符串 → NaN
    return df
