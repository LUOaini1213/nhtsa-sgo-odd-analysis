"""00_inspect_raw.py - 原始数据结构探查（只读）

用法（必须用 -I 隔离模式）:
    python -I scripts/00_inspect_raw.py

输出:
    output/tables/raw_schema_profile.csv  每列: 非空数 / 唯一值数 / 脱敏(redaction)单元格数 / Top 值
    终端打印: 版本结构、Same Incident ID、日期范围、关键分类字段取值等检查结果

数据视为不可信数据：全部按字符串读取，不 eval、不执行任何内容。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # 仅加入本项目 scripts 目录
from config import RAW_FILES, TABLE_DIR  # noqa: E402
from io_utils import read_raw  # noqa: E402

REDACTION_PATTERN = r"\[REDACTED|MAY CONTAIN|\[XXX\]"

KEY_CATEGORICALS = [
    "Report Type",
    "Report Version",
    "Automation System Engaged?",
    "Engagement Status",
    "Driver / Operator Type",
    "Roadway Type",
    "Crash With",
    "Highest Injury Severity Alleged",
    "SV Pre-Crash Movement",
    "CP Pre-Crash Movement",
    "Any Air Bags Deployed?",
    "Was Any Vehicle Towed?",
    "Within ODD?",
    "Within ODD? - CBI",
    "Incident Date - Unknown",
    "Incident Time - Unknown",
    "SV Pre-crash Speed - Unknown",
]


def profile(df: pd.DataFrame, label: str) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col].astype(str).str.strip()
        nonblank = s[s != ""]
        vc = nonblank.value_counts().head(8)
        top = " | ".join(f"{str(k)[:40]}={v}" for k, v in vc.items())
        rows.append(
            {
                "dataset": label,
                "column": col,
                "n_rows": len(s),
                "non_blank": int(len(nonblank)),
                "n_unique": int(nonblank.nunique()),
                "n_redacted": int(s.str.contains(REDACTION_PATTERN, regex=True).sum()),
                "top_values": top,
            }
        )
    return pd.DataFrame(rows)


def section(title: str) -> None:
    print("\n" + "=" * 8 + " " + title + " " + "=" * 8)


def inspect(df: pd.DataFrame, label: str) -> None:
    section(f"{label}: rows={len(df)} cols={df.shape[1]} encoding={df.attrs.get('encoding')}")
    ver = pd.to_numeric(df["Report Version"], errors="coerce")
    print("Report Version non-numeric:", int(ver.isna().sum()))
    g = df.assign(_v=ver).groupby("Report ID")["_v"]
    n_ids = df["Report ID"].nunique()
    print("unique Report ID:", n_ids)
    print("versions per Report ID:", g.size().value_counts().sort_index().to_dict())
    gaps = (g.max() != g.size()).sum()
    print("Report IDs where max(version) != n_rows (missing/duplicate versions):", int(gaps))
    dup_rows = df.duplicated(subset=["Report ID", "Report Version"]).sum()
    print("duplicate (Report ID, Report Version) rows:", int(dup_rows))
    print("exact duplicate rows:", int(df.duplicated().sum()))

    # 最新版本
    latest = df.assign(_v=ver).sort_values("_v").groupby("Report ID").tail(1)
    print("latest-version rows:", len(latest))

    # 同一 Report ID 不同版本间 Same Incident ID 是否变化
    sid_var = df.groupby("Report ID")["Same Incident ID"].nunique()
    print("Report IDs whose Same Incident ID changes across versions:", int((sid_var > 1).sum()))
    # 同一 Same Incident ID 下的 Report ID 数（最新版本）
    blank_sid = (latest["Same Incident ID"].str.strip() == "").sum()
    print("latest rows with blank Same Incident ID:", int(blank_sid))
    rid_per_sid = latest.groupby("Same Incident ID")["Report ID"].nunique()
    print("Report IDs per Same Incident ID (latest):", rid_per_sid.value_counts().sort_index().to_dict())
    multi = rid_per_sid[rid_per_sid > 1].index
    if len(multi):
        m = latest[latest["Same Incident ID"].isin(multi)]
        same_entity = m.groupby("Same Incident ID")["Reporting Entity"].nunique()
        print("  multi-report incidents: n=", len(multi), " of which single entity:", int((same_entity == 1).sum()))

    # 日期
    for c in ["Incident Date", "Report Submission Date", "Report Month", "Report Year", "Incident Time (24:00)"]:
        s = latest[c].str.strip()
        print(f"{c}: blank={int((s == '').sum())} redacted={int(s.str.contains(REDACTION_PATTERN).sum())} "
              f"sample={s[s != ''].head(5).tolist()}")
    # 数据字典写 [MMM-YY]，但文件实际为 MMM-YYYY（如 AUG-2026）
    inc = pd.to_datetime(latest["Incident Date"].str.strip().str.title(), format="%b-%Y", errors="coerce")
    print("Incident Date parsed min/max:", inc.min(), inc.max(), " unparsable:", int(inc.isna().sum()))
    print("Incident month counts:", inc.dt.to_period("M").value_counts().sort_index().to_dict())
    sub = pd.to_datetime(latest["Report Submission Date"].str.strip().str.title(), format="%b-%Y", errors="coerce")
    print("Report Submission Date parsed min/max:", sub.min(), sub.max(), " unparsable:", int(sub.isna().sum()))

    # 关键分类字段（最新版本）
    for c in KEY_CATEGORICALS:
        if c in latest.columns:
            print(f"-- {c}:", latest[c].str.strip().replace("", "<blank>").value_counts().to_dict())

    # 车速
    spd_raw = latest["SV Precrash Speed (MPH)"].str.strip()
    spd = pd.to_numeric(spd_raw, errors="coerce")
    print("SV speed: blank=", int((spd_raw == "").sum()), " non-numeric non-blank=",
          int(((spd_raw != "") & spd.isna()).sum()),
          " numeric describe=", spd.describe().round(1).to_dict())
    print("SV speed non-numeric values:", spd_raw[(spd_raw != "") & spd.isna()].value_counts().head(10).to_dict())

    # 多选 flag 列
    flag_cols = [c for c in latest.columns if c.startswith(("Roadway-", "Weather - "))]
    for c in flag_cols:
        vals = latest[c].str.strip().replace("", "<blank>").value_counts().to_dict()
        print(f"   flag {c}: {vals}")
    rw = [c for c in flag_cols if c.startswith("Roadway-")]
    wx = [c for c in flag_cols if c.startswith("Weather - ")]
    print("rows with no Roadway-* flag:", int((latest[rw].apply(lambda s: s.str.strip()).eq("").all(axis=1)).sum()))
    print("rows with no Weather flag:", int((latest[wx].apply(lambda s: s.str.strip()).eq("").all(axis=1)).sum()))

    # 上报主体 / 品牌 / 州
    print("Reporting Entity (latest):", latest["Reporting Entity"].value_counts().head(15).to_dict())
    print("Make (latest):", latest["Make"].value_counts().head(15).to_dict())
    print("State (latest):", latest["State"].str.strip().replace("", "<blank>").value_counts().head(15).to_dict())
    print("City blank/redacted:", int((latest["City"].str.strip() == "").sum()),
          int(latest["City"].str.contains(REDACTION_PATTERN).sum()))


def main() -> None:
    pd.set_option("display.width", 220)
    frames = {}
    out = []
    for label, path in RAW_FILES.items():
        df = read_raw(path)
        frames[label] = df
        inspect(df, label)
        out.append(profile(df, label))

    section("Cross-file checks")
    a, b = frames["ADS"], frames["ADAS"]
    rid_overlap = set(a["Report ID"]) & set(b["Report ID"])
    print("Report IDs present in both files:", len(rid_overlap), sorted(rid_overlap)[:10])
    sa = set(a["Same Incident ID"].str.strip()) - {""}
    sb = set(b["Same Incident ID"].str.strip()) - {""}
    print("Same Incident IDs present in both files:", len(sa & sb))
    print("columns identical:", list(a.columns) == list(b.columns))

    prof = pd.concat(out, ignore_index=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    prof.to_csv(TABLE_DIR / "raw_schema_profile.csv", index=False, encoding="utf-8-sig")
    print("\nwritten: output/tables/raw_schema_profile.csv")


if __name__ == "__main__":
    main()
