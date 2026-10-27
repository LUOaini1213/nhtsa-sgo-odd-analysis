"""01_clean.py - 按清洗规则 R0-R13 生成分析数据，并记录每一步的行数变化

用法:  python -I -X utf8 scripts/01_clean.py

输出:
  output/clean/{ads,adas}_reports_latest.csv   每个 Report ID 的最新版本 + 派生字段（不含叙述全文与已脱敏的位置字段）
  output/clean/{ads,adas}_incidents.csv        分析总体：同一事故合并后一行，Incident Date 在 2025-06 至 2026-09
  output/tables/cleaning_log.csv               每条规则前后行数
  output/tables/multi_report_incidents.csv     被合并的“同一事故多份报告”明细及保留哪一份
  output/tables/data_quality_checks.csv        数据质量检查结果
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # 仅加入本项目 scripts 目录
from config import CLEAN_DIR, RAW_FILES, TABLE_DIR  # noqa: E402
from io_utils import read_raw  # noqa: E402
import pipeline as P  # noqa: E402

DROP_FROM_CLEAN = ["Narrative", "Latitude", "Longitude", "Address", "Zip Code", "VIN", "Serial Number"]


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    log, dq, multis, latest_all = [], [], [], {}

    def add_log(ds, step, rule, before, after, note=""):
        log.append({"dataset": ds, "step": step, "rule": rule, "rows_before": before,
                    "rows_after": after, "removed_or_merged": before - after, "note": note})

    def add_dq(ds, check, n, denom, scope, handling):
        dq.append({"dataset": ds, "check": check, "n": int(n), "denominator": int(denom),
                   "pct": round(100 * n / denom, 1) if denom else None, "scope": scope, "handling": handling})

    for ds, path in RAW_FILES.items():
        raw = P.strip_all(read_raw(path))
        n_raw = len(raw)
        add_log(ds, "R0", "读取原始 CSV（全部按字符串，去首尾空白）", n_raw, n_raw,
                f"{raw['Report ID'].nunique()} 个 Report ID")

        # 早期版本自动化类型与文件类型不一致（会被 R1 的最新版本覆盖）
        add_dq(ds, "早期版本行的 Automation System Engaged? 与文件类型不同", (raw["Automation System Engaged?"] != ds).sum(),
               n_raw, "全部版本行", "R1 取最新版本后不再存在")

        latest = P.latest_versions(raw)
        add_log(ds, "R1", "每个 Report ID 只保留最大 Report Version（与 NHTSA 仪表板做法一致）", n_raw, len(latest))
        add_dq(ds, "文件中最早版本 > 1 的 Report ID（首版在 2025-06-16 前提交、位于归档数据）",
               (latest["min_version_in_file"] > 1).sum(), len(latest), "最新版本报告", "仍使用文件中的最新版本")
        sid_change = raw.groupby("Report ID")["Same Incident ID"].nunique()
        add_dq(ds, "同一 Report ID 不同版本间 Same Incident ID 发生变化", (sid_change > 1).sum(), len(latest),
               "最新版本报告", "以最新版本的 Same Incident ID 为准（NHTSA 提示该字段可能随版本变化）")

        n_before = len(latest)
        latest = latest[latest["Automation System Engaged?"] == ds].copy()
        add_log(ds, "R2", f"最新版本 Automation System Engaged? = {ds}", n_before, len(latest),
                "Unknown 类型的报告在 NHTSA 的 OTHER 文件中，本项目未下载、未使用")

        d = P.derive(latest, ds)
        bad = P.unmapped_values(d)
        if bad:
            raise SystemExit(f"[{ds}] 存在未映射取值，请更新 pipeline.py 映射表: {bad}")
        latest_all[ds] = d

        # ---- 数据质量检查（最新版本报告层面）
        add_dq(ds, "Same Incident ID 为空", d["Same Incident ID"].eq("").sum(), len(d), "最新版本报告",
               "以 Report ID 作为事故键，不与其他报告合并")
        add_dq(ds, "Latitude/Longitude 已脱敏或为空", (d["Latitude"].str.contains(P.REDACTION_RE) | d["Latitude"].eq("")).sum(),
               len(d), "最新版本报告", "无法做基于经纬度的光照/日照计算")
        add_dq(ds, "Narrative 整段以 CBI 理由脱敏", d["narrative_status"].eq("redacted (CBI)").sum(), len(d),
               "最新版本报告", "叙述关键词分析只覆盖可读叙述，并注明覆盖率")
        add_dq(ds, "Within ODD? 以 CBI 理由脱敏", d["within_odd"].eq("Redacted").sum(), len(d), "最新版本报告",
               "单列 Redacted 类别，不计入已知分母")
        stopped_moving = d["sv_move"].isin(["Stopped", "Parked"]) & (d["speed_mph"] > 0)
        add_dq(ds, "SV Pre-Crash Movement 为 Stopped/Parked 但 SV Precrash Speed > 0", stopped_moving.sum(), len(d),
               "最新版本报告", "按原值保留（上报主体口径差异），不修改")
        add_dq(ds, "SV Precrash Speed > 100 mph", (d["speed_mph"] > 100).sum(), len(d), "最新版本报告",
               "按原值保留，计入 >65 档")
        cp_blank_not_fixed = d["cp_move"].eq("No crash partner (fixed object)") & ~d["crash_with_group"].eq("Fixed object")
        add_dq(ds, "CP Pre-Crash Movement 为空但 Crash With 不是固定物（一致性检查）", cp_blank_not_fixed.sum(), len(d),
               "最新版本报告", "0 表示“空白=无碰撞伙伴”的解释与数据一致")
        rw_cols = [c for c in d.columns if c.startswith("Roadway-") and c != P.ROADWAY_UNK]
        add_dq(ds, "Roadway-Unknown 与其他路面选项同时勾选", (d[P.ROADWAY_UNK].eq("Y") & d[rw_cols].eq("Y").any(axis=1)).sum(),
               len(d), "最新版本报告", "视为路面已知（有实质选项）")
        wx_cols = [c for c in d.columns if c.startswith("Weather - ") and c != P.WEATHER_UNK]
        add_dq(ds, "Weather - Unk 与其他天气选项同时勾选", (d[P.WEATHER_UNK].eq("Y") & d[wx_cols].eq("Y").any(axis=1)).sum(),
               len(d), "最新版本报告", "视为天气已知（有实质选项）")

        # ---- R3 同一事故合并
        inc, multi = P.dedup_incidents(d)
        add_log(ds, "R3", "同一文件内 Same Incident ID 相同的报告合并为一起事故（保留信息最完整的一份）",
                len(d), len(inc), f"{multi['incident_key'].nunique()} 起事故有多份报告")
        if len(multi):
            tdiff = multi.groupby("incident_key")["Incident Time (24:00)"].nunique()
            add_dq(ds, "被合并事故中各报告 Incident Time 不一致", (tdiff > 1).sum(), multi["incident_key"].nunique(),
                   "多报告事故", "仍按 NHTSA 的 Same Incident ID 合并，在 report.md 中单独说明")
            multis.append(multi[["dataset", "incident_key", "Report ID", "Report Version", "Reporting Entity",
                                 "Report Type", "Report Submission Date", "Incident Date", "Incident Time (24:00)",
                                 "City", "State", "Same Vehicle ID", "info_missing", "kept"]])

        # ---- R4 统计窗口
        win = P.in_window(inc)
        n_unknown_date = inc["incident_month"].eq("").sum()
        n_before_window = (inc["incident_month"].ne("") & (inc["incident_month"] < str(P.WINDOW_START))).sum()
        n_after_window = (inc["incident_month"] > str(P.WINDOW_END)).sum()
        analysis = inc[win].copy()
        add_log(ds, "R4", f"Incident Date 在 {P.WINDOW_START} 至 {P.WINDOW_END}（第三修订版报告期）", len(inc), len(analysis),
                f"早于窗口 {n_before_window} 起；日期未知 {n_unknown_date} 起；晚于窗口 {n_after_window} 起")
        add_dq(ds, "Incident Date 早于 2025-06（最新版本报告）", (d["incident_month"].ne("") & (d["incident_month"] < "2025-06")).sum(),
               len(d), "最新版本报告", "R4 剔除（多为旧版 SGO 首报后的更新或迟报）")

        cols = [c for c in d.columns if c not in DROP_FROM_CLEAN]
        d[cols].to_csv(CLEAN_DIR / f"{ds.lower()}_reports_latest.csv", index=False, encoding="utf-8-sig")
        analysis[[c for c in analysis.columns if c not in DROP_FROM_CLEAN]].to_csv(
            CLEAN_DIR / f"{ds.lower()}_incidents.csv", index=False, encoding="utf-8-sig")
        print(f"[{ds}] raw={n_raw} latest={len(d)} incidents={len(inc)} analysis={len(analysis)}")

    # ---- 跨文件：同一 Same Incident ID 同时出现在 ADS 与 ADAS 文件
    a, b = latest_all["ADS"], latest_all["ADAS"]
    common = (set(a["Same Incident ID"]) & set(b["Same Incident ID"])) - {""}
    detail = []
    for sid in sorted(common):
        ra, rb = a[a["Same Incident ID"] == sid].iloc[0], b[b["Same Incident ID"] == sid].iloc[0]
        detail.append(f"{sid}: ADS {ra['Report ID']} {ra['City']},{ra['State']} {ra['Incident Time (24:00)']} vs "
                      f"ADAS {rb['Report ID']} {rb['City']},{rb['State']} {rb['Incident Time (24:00)']}")
    add_dq("ADS+ADAS", "同一 Same Incident ID 同时出现在 ADS 与 ADAS 文件", len(common), len(a) + len(b),
           "两文件最新版本报告", "地点与时间均不同，判断为 ID 重合而非同一事故；两文件分别分析、不跨文件合并。"
           + (" 明细: " + " | ".join(detail) if detail else ""))

    pd.DataFrame(log).to_csv(TABLE_DIR / "cleaning_log.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(dq).to_csv(TABLE_DIR / "data_quality_checks.csv", index=False, encoding="utf-8-sig")
    if multis:
        pd.concat(multis).to_csv(TABLE_DIR / "multi_report_incidents.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(log)[["dataset", "step", "rows_before", "rows_after", "note"]].to_string(index=False))


if __name__ == "__main__":
    main()
