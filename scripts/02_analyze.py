"""02_analyze.py - 描述性统计（ADS 与 ADAS 分开），只做计数与占比，不做率与因果推断

用法:  python -I -X utf8 scripts/02_analyze.py
输入:  output/clean/*_incidents.csv（分析总体）、*_reports_latest.csv（敏感性分析）
       原始 CSV 仅用于读取叙述全文（积水/打滑关键词复核、叙述时间核对）
输出（output/tables/）:
  monthly_incidents.csv           按 Incident Date 月份的事故数（含部分月份标记）
  distributions.csv               各字段分布长表：n、占全部 %、占已知 %
  conditions.csv                  天气/路面多选项 + 复合条件 + 夜间时段代理
  hourly_profiles.csv             按小时分布（ADS；ADAS 剔除时间基准存疑主体；时区检验用分组）
  time_base_check_by_tz.csv       按时区比较 3 小时“低谷/高峰”时段（检验 Incident Time 是否为当地时间）
  time_base_check_narratives.csv  叙述中写明的时间与 Incident Time 字段是否一致
  speed_summary.csv               SV Precrash Speed 汇总统计
  crash_configuration.csv         SV 运动分组 × CP 运动分组 交叉表
  data_completeness.csv           各字段 Unknown / 未报告 / 脱敏比例
  reporting_entities_context.csv  上报主体构成（仅作背景，不是安全排名）
  narrative_water_mentions.csv    叙述中积水/打滑关键词命中 + 人工复核
  sensitivity_checks.csv          关键比例在不同口径下的稳健性
  key_metrics.csv                 README / report 引用的全部数字
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # 仅加入本项目 scripts 目录
from config import CLEAN_DIR, RAW_FILES, TABLE_DIR  # noqa: E402
from io_utils import read_clean, read_raw  # noqa: E402
import pipeline as P  # noqa: E402

DATASETS = ["ADS", "ADAS"]
NK = P.NOT_KNOWN

TIME_BASE_SUSPECT = P.TIME_BASE_SUSPECT  # 规则 R8b，定义与依据见 pipeline.py

# 人工复核（2026-10-27，针对 2026-10-15 发布版逐条阅读叙述全文后填写）。只描述叙述写明的事实，不判断责任与原因。
MANUAL_WATER_REVIEW = {
    "30270-11571": ("SV entered standing water", "SV 驶入积水后车辆受损、被拖离；无其他交通参与者"),
    "30270-11996": ("SV entered standing water", "SV 直行通过路口时驶入积水，车辆受损、被拖离；无其他交通参与者"),
    "30270-15993": ("SV entered standing water", "SV 驶入积水，底盘接触积水，车辆受损、被拖离；无其他交通参与者"),
    "30270-16298": ("SV entered standing water", "SV 变道时驶入积水并减速停在车道内，随后被后方乘用车追尾"),
    "31101-14899": ("Other vehicle hydroplaned", "SV 红灯停车，后方乘用车在湿滑路面打滑（hydroplaned）后追尾"),
    "540-15575": ("SV hydroplaned / lost control", "驾驶员称车辆打滑失控；叙述称 Super Cruise 在碰撞前 8 秒转为 Disabled/Not Ready（原因：手握方向盘）"),
    "540-15297": ("SV hydroplaned / lost control", "车辆打滑后与相邻车道皮卡及护栏碰撞；叙述称 Super Cruise 在碰撞前 5.8 秒因 degraded condition 转为 Disabled/Not Ready"),
    "753-15556": ("SV hydroplaned / lost control", "客户称大雨中打滑撞护栏；车辆数据称碰撞前约 6 秒 LFA 因无法识别车道线而退出，驾驶员持续踩加速踏板"),
    "502-14852": ("SV hydroplaned / lost control", "驾驶员称 BlueCruise 开启时转向“卡住”后打滑撞中央隔离带；厂商称调查仍在进行"),
    "1306-14367": ("SV hydroplaned / lost control", "警方报告：降雨、路面湿滑有积水；叙述称车辆开始摇摆时 LTA 关闭，记录车速 77.6 mph"),
}
# 叙述中明确写明“L2 系统在碰撞前退出/关闭”的报告（ADAS）
L2_DISENGAGED_BEFORE_CRASH = {"540-15575", "540-15297", "753-15556", "1306-14367"}


def pct(n: float, d: float) -> float:
    return round(100.0 * float(n) / float(d), 1) if d else np.nan


def distribution(d: pd.DataFrame, field: str, ds: str, order: list[str] | None = None) -> list[dict]:
    vc = d[field].value_counts()
    n_all = len(d)
    n_known = int((~d[field].isin(NK)).sum())
    cats = list(order or [])
    cats += [c for c in vc.index if c not in cats and c not in NK]
    cats += [c for c in ["Unknown", "Not reported", "Redacted"] if c in vc.index]
    rows = []
    for cat in cats:
        n = int(vc.get(cat, 0))
        rows.append({
            "dataset": ds, "field": field, "category": cat, "n": n,
            "pct_of_all": pct(n, n_all),
            "pct_of_known": None if cat in NK else pct(n, n_known),
            "n_all": n_all, "n_known": n_known,
        })
    return rows


def known_share(d: pd.DataFrame, field: str, cats: list[str]) -> tuple[int, int, float]:
    num = int(d[field].isin(cats).sum())
    den = int((~d[field].isin(NK)).sum())
    return num, den, pct(num, den)


def metric_set(d: pd.DataFrame) -> dict[str, float]:
    return {
        "降雨或湿滑（占已知%）": pct(d["rain_or_wet"].sum(), d["rain_or_wet_known"].sum()),
        "Highway / Freeway（占已知%）": known_share(d, "roadway_group", ["Highway / Freeway"])[2],
        "SV 静止 Stopped/Parked（占已知%）": known_share(d, "sv_move_group", ["Stationary"])[2],
        "SV Lane / Road Departure（占已知%）": known_share(d, "sv_move_group", ["Lane / road departure"])[2],
        "碰撞对象为固定物（占已知%）": known_share(d, "crash_with_group", ["Fixed object"])[2],
        "碰撞对象为轻型车辆（占已知%）": known_share(d, "crash_with_group", ["Light vehicle"])[2],
    }


def time_ok(d: pd.DataFrame, ds: str) -> pd.DataFrame:
    """时段统计使用的子集：剔除时间基准存疑主体。"""
    return d[~d["Reporting Entity"].isin(TIME_BASE_SUSPECT.get(ds, []))]


def main() -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    A = {ds: read_clean(CLEAN_DIR / f"{ds.lower()}_incidents.csv") for ds in DATASETS}
    L = {ds: read_clean(CLEAN_DIR / f"{ds.lower()}_reports_latest.csv") for ds in DATASETS}
    RAWL = {ds: P.latest_versions(P.strip_all(read_raw(RAW_FILES[ds]))).set_index("Report ID") for ds in DATASETS}
    clog = pd.read_csv(TABLE_DIR / "cleaning_log.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    for ds in DATASETS:
        for d in (A[ds], L[ds]):
            d["state_std"] = d["State"].where(d["State"].ne(""), "Not reported")
            d["tz"] = d["State"].map(P.STATE_TZ).fillna("")

    # ------------------------------------------------------------ 1. 月度事故数
    months = [str(p) for p in pd.period_range(P.WINDOW_START, P.WINDOW_END, freq="M")]
    rows = []
    for ds in DATASETS:
        d = A[ds]
        for m in months:
            sub = d[d["incident_month"] == m]
            rows.append({
                "dataset": ds, "incident_month": m, "n_incidents": len(sub),
                "n_latest_5day": int(sub["Report Type"].eq("5-Day").sum()),
                "n_latest_monthly": int(sub["Report Type"].eq("Monthly").sum()),
                "n_latest_update": int(sub["Report Type"].eq("Update").sum()),
                "partial_month": m in P.PARTIAL_MONTHS, "note": P.PARTIAL_MONTHS.get(m, ""),
            })
    monthly = pd.DataFrame(rows)
    monthly.to_csv(TABLE_DIR / "monthly_incidents.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 2. 字段分布
    fields = [
        ("roadway_group", P.ROADWAY_ORDER), ("roadway_type", None),
        ("crash_with_group", P.CRASH_WITH_ORDER), ("crash_with", None),
        ("severity_group", P.SEVERITY_ORDER[:-1]), ("severity", None),
        ("sv_move_group", P.MOVE_ORDER[:6] + ["Other"]), ("sv_move", None),
        ("cp_move_group", P.MOVE_ORDER), ("cp_move", None),
        ("speed_band", P.SPEED_LABELS),
        ("engagement", None), ("operator_type", None), ("within_odd", None),
        ("airbag", None), ("towed", None), ("Report Type", None), ("state_std", None),
    ]
    rows = []
    for ds in DATASETS:
        for f, order in fields:
            rows += distribution(A[ds], f, ds, order)
    pd.DataFrame(rows).to_csv(TABLE_DIR / "distributions.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 3. 时间基准检验
    rows = []
    shifts = {}
    for ds in DATASETS:
        d = A[ds]
        top = d["Reporting Entity"].value_counts().index[0]
        d["_grp"] = np.where(d["Reporting Entity"] == top, top, "其他主体")
        for (g, tz), sub in d[d["tz"].ne("")].groupby(["_grp", "tz"]):
            if len(sub) < 40:  # 样本太少时低谷位置不稳定
                continue
            tr, pk, n = P.trough_peak_3h(sub["hour"])
            rows.append({"dataset": ds, "reporter_group": g, "time_zone": tz, "n_known_hour": n,
                         "trough_3h_window": tr, "peak_3h_window": pk})
        tb = pd.DataFrame([r for r in rows if r["dataset"] == ds and r["reporter_group"] == top])
        tz_start = {r["time_zone"]: int(r["trough_3h_window"][:2]) for _, r in tb.iterrows()}
        if "ET" in tz_start and "PT" in tz_start:
            shifts[(ds, top)] = (tz_start["PT"] - tz_start["ET"]) % 24
    tbz = pd.DataFrame(rows)
    tbz.to_csv(TABLE_DIR / "time_base_check_by_tz.csv", index=False, encoding="utf-8-sig")
    for (ds, ent), sh in shifts.items():
        flag = ent in TIME_BASE_SUSPECT.get(ds, [])
        print(f"[时间基准] {ds} {ent}: PT 低谷起点 - ET 低谷起点 = {sh} 小时（当地时间应≈0，UTC 应≈3）；列入存疑={flag}")
        if (sh >= 2) != flag:
            print("  [警告] 检验结果与 TIME_BASE_SUSPECT 设置不一致，请复核")

    rows = []
    for ds in DATASETS:
        nar = RAWL[ds]["Narrative"]
        d = A[ds]
        off = pd.Series([P.narrative_time_offset_h(nar.get(r, ""), t) for r, t in zip(d["Report ID"], d["Incident Time (24:00)"])],
                        index=d.index)
        d["_time_verified"] = off.abs().lt(0.05).fillna(False).astype(bool)  # 叙述时间与字段完全一致
        tmp = d.assign(_off=off).dropna(subset=["_off"])
        for ent, sub in tmp.groupby("Reporting Entity"):
            o = sub["_off"].abs()
            rows.append({"dataset": ds, "Reporting Entity": ent, "n_narratives_with_ampm_time": len(sub),
                         "n_exact_match": int((o < 0.05).sum()), "n_12h_offset (AM/PM 混淆)": int(((o - 12).abs() < 0.05).sum()),
                         "n_other_offset": int(((o >= 0.05) & ((o - 12).abs() >= 0.05)).sum())})
    tbn = pd.DataFrame(rows).sort_values(["dataset", "n_narratives_with_ampm_time"], ascending=[True, False])
    tbn.to_csv(TABLE_DIR / "time_base_check_narratives.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 4. 按小时分布
    rows = []
    ads_t, adas_t = time_ok(A["ADS"], "ADS"), time_ok(A["ADAS"], "ADAS")
    suspect = A["ADAS"][A["ADAS"]["Reporting Entity"].isin(TIME_BASE_SUSPECT["ADAS"])]
    profiles = [
        ("ADS（全部）", ads_t),
        ("ADAS（剔除时间基准存疑主体）", adas_t),
        ("ADAS 时间基准存疑主体 - ET 州", suspect[suspect["tz"] == "ET"]),
        ("ADAS 时间基准存疑主体 - PT 州", suspect[suspect["tz"] == "PT"]),
        ("ADS - ET 州", A["ADS"][A["ADS"]["tz"] == "ET"]),
        ("ADS - PT 州", A["ADS"][A["ADS"]["tz"] == "PT"]),
    ]
    for name, d in profiles:
        h = d["hour"].dropna().astype(int)
        cnt = np.bincount(h, minlength=24)
        for hr in range(24):
            rows.append({"profile": name, "hour": hr, "n": int(cnt[hr]), "n_known_hour": int(len(h)),
                         "pct": pct(cnt[hr], len(h))})
    pd.DataFrame(rows).to_csv(TABLE_DIR / "hourly_profiles.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 5. 天气 / 路面 / 时间条件
    rows = []
    for ds in DATASETS:
        d = A[ds]
        n_all = len(d)
        wx = [c for c in d.columns if c.startswith("Weather - ")]
        rw = [c for c in d.columns if c.startswith("Roadway-")]
        for c in wx:
            n = int(d[c].eq("Y").sum())
            den = None if c == P.WEATHER_UNK else int(d["weather_known"].sum())
            rows.append({"dataset": ds, "group": "Weather（多选）", "condition": c, "n": n, "n_all": n_all,
                         "pct_of_all": pct(n, n_all), "n_known": den, "pct_of_known": pct(n, den) if den else None, "note": ""})
        for c in rw:
            n = int(d[c].eq("Y").sum())
            den = None if c == P.ROADWAY_UNK else int(d["surface_known"].sum())
            rows.append({"dataset": ds, "group": "Roadway 描述（多选）", "condition": c, "n": n, "n_all": n_all,
                         "pct_of_all": pct(n, n_all), "n_known": den, "pct_of_known": pct(n, den) if den else None, "note": ""})
        comps = [
            ("复合", "Rain 或 Wet Surface（rain_or_wet）", d["rain_or_wet"].sum(), d["rain_or_wet_known"].sum(), n_all, ""),
            ("复合", "任一不良天气（Rain/Snow/Fog/Severe Wind/Dust/Hurricane）", d["adverse_weather"].sum(), d["weather_known"].sum(), n_all, ""),
        ]
        dt = time_ok(d, ds)
        note = "" if len(dt) == n_all else f"已剔除时间基准存疑主体（{', '.join(TIME_BASE_SUSPECT[ds])}）"
        comps += [
            ("时间代理", "深夜 22:00-04:59（当地时间，基本全年天黑）", dt["night_22_05"].eq(1).sum(), dt["hour"].notna().sum(), len(dt), note),
            ("时间代理", "夜间宽口径 20:00-05:59（当地时间）", dt["night_20_06"].eq(1).sum(), dt["hour"].notna().sum(), len(dt), note),
        ]
        for g, name, n, den, base, nt in comps:
            rows.append({"dataset": ds, "group": g, "condition": name, "n": int(n), "n_all": int(base),
                         "pct_of_all": pct(n, base), "n_known": int(den), "pct_of_known": pct(n, den), "note": nt})
    cond = pd.DataFrame(rows)
    cond.to_csv(TABLE_DIR / "conditions.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 6. 车速
    rows = []
    for ds in DATASETS:
        s = A[ds]["speed_mph"].dropna()
        rows.append({
            "dataset": ds, "n_all": len(A[ds]), "n_known": len(s), "pct_unknown": pct(len(A[ds]) - len(s), len(A[ds])),
            "median_mph": float(s.median()), "p25_mph": float(s.quantile(0.25)), "p75_mph": float(s.quantile(0.75)),
            "mean_mph": round(float(s.mean()), 1), "max_mph": float(s.max()),
            "pct_0mph": pct((s == 0).sum(), len(s)), "pct_le10mph": pct((s <= 10).sum(), len(s)),
            "pct_ge46mph": pct((s >= 46).sum(), len(s)), "pct_gt65mph": pct((s > 65).sum(), len(s)),
        })
    speed = pd.DataFrame(rows)
    speed.to_csv(TABLE_DIR / "speed_summary.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 7. 碰撞构型（SV × CP）
    rows = []
    for ds in DATASETS:
        d = A[ds]
        ct = d.groupby(["sv_move_group", "cp_move_group"]).size().reset_index(name="n")
        ct.insert(0, "dataset", ds)
        ct["pct_of_all"] = (100 * ct["n"] / len(d)).round(1)
        rows.append(ct.sort_values("n", ascending=False))
    pd.concat(rows).to_csv(TABLE_DIR / "crash_configuration.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 8. 数据完整度
    rows = []
    for ds in DATASETS:
        d = A[ds]
        checks = [
            ("Roadway Type", d["roadway_type"].isin(NK), d["roadway_type"].eq("Redacted")),
            ("Weather（无实质选项）", ~d["weather_known"], None),
            ("Roadway 描述（无实质选项）", ~d["surface_known"], None),
            ("Crash With", d["crash_with"].isin(NK), d["crash_with"].eq("Redacted")),
            ("SV Pre-Crash Movement", d["sv_move"].isin(NK), d["sv_move"].eq("Redacted")),
            ("CP Pre-Crash Movement", d["cp_move"].isin(NK), d["cp_move"].eq("Redacted")),
            ("SV Precrash Speed (MPH)", d["speed_mph"].isna(), None),
            ("Highest Injury Severity Alleged", d["severity"].isin(NK), d["severity"].eq("Redacted")),
            ("Was Any Vehicle Towed?", d["towed"].isin(NK), d["towed"].eq("Redacted")),
            ("Within ODD?", d["within_odd"].isin(NK), d["within_odd"].eq("Redacted")),
            ("Narrative", d["narrative_status"].ne("readable"), d["narrative_status"].eq("redacted (CBI)")),
        ]
        for name, miss, red in checks:
            n_red = int(red.sum()) if red is not None else 0
            n_miss = int(miss.sum())
            rows.append({"dataset": ds, "field": name, "n_not_known": n_miss, "n_redacted": n_red,
                         "n_unknown_or_not_reported": n_miss - n_red, "n_all": len(d), "pct_not_known": pct(n_miss, len(d))})
    pd.DataFrame(rows).to_csv(TABLE_DIR / "data_completeness.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 9. 上报主体（仅背景）
    rows = []
    for ds in DATASETS:
        vc = A[ds]["Reporting Entity"].value_counts()
        for ent, n in vc.head(8).items():
            rows.append({"dataset": ds, "Reporting Entity": ent, "n_incidents": int(n), "pct_of_incidents": pct(n, len(A[ds]))})
        rest = vc.iloc[8:]
        rows.append({"dataset": ds, "Reporting Entity": f"其他 {len(rest)} 家", "n_incidents": int(rest.sum()),
                     "pct_of_incidents": pct(rest.sum(), len(A[ds]))})
    ents = pd.DataFrame(rows)
    ents["caveat"] = "报告数取决于车队规模、里程、遥测能力与上报口径，未按暴露量归一化，不能用于安全排名"
    ents.to_csv(TABLE_DIR / "reporting_entities_context.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 10. 叙述：积水 / 打滑
    rows = []
    for ds in DATASETS:
        nar = RAWL[ds]["Narrative"]
        in_pop = set(A[ds]["Report ID"])
        for _, r in L[ds][L[ds]["water_keywords"].ne("")].iterrows():
            text = nar.get(r["Report ID"], "")
            m = P.WATER_RE.search(text)
            excerpt = " ".join(text[max(0, m.start() - 150): m.end() + 150].split()) if m else ""  # 合并换行/多余空白
            cat, note = MANUAL_WATER_REVIEW.get(r["Report ID"], ("未复核", ""))
            rows.append({
                "dataset": ds, "Report ID": r["Report ID"], "Reporting Entity": r["Reporting Entity"],
                "incident_month": r["incident_month"], "Incident Time (24:00)": r["Incident Time (24:00)"],
                "City": r["City"], "State": r["State"], "Roadway Type": r["Roadway Type"],
                "Weather - Rain": r["Weather - Rain"], "Roadway-Wet Surface Condition": r["Roadway-Wet Surface Condition"],
                "Crash With": r["Crash With"], "SV Pre-Crash Movement": r["SV Pre-Crash Movement"],
                "SV Precrash Speed (MPH)": r["SV Precrash Speed (MPH)"], "Within ODD?": r["Within ODD?"],
                "Engagement Status": r["Engagement Status"], "keywords": r["water_keywords"],
                "in_analysis_population": r["Report ID"] in in_pop,
                "manual_category": cat, "manual_note_cn": note,
                "l2_disengaged_before_crash_per_narrative": r["Report ID"] in L2_DISENGAGED_BEFORE_CRASH,
                "excerpt": excerpt,
            })
    water = pd.DataFrame(rows)
    water.to_csv(TABLE_DIR / "narrative_water_mentions.csv", index=False, encoding="utf-8-sig")
    if len(water) and (water["manual_category"] == "未复核").any():
        print("[警告] 有新的关键词命中尚未人工复核：", water.loc[water["manual_category"] == "未复核", "Report ID"].tolist())

    # ------------------------------------------------------------ 11. 敏感性分析
    rows = []
    for ds in DATASETS:
        top_ent = A[ds]["Reporting Entity"].value_counts().idxmax()
        scen = [
            ("S0", "主口径：分析总体（R1-R4）", A[ds]),
            ("S1", "全部最新版本报告（不做 R3 合并、不做 R4 窗口）", L[ds]),
            ("S2", "主口径，剔除 Engagement Status = Verified Not Engaged", A[ds][A[ds]["engagement"] != "Verified Not Engaged"]),
            ("S3", f"主口径，剔除报告量最大的主体（{top_ent}）——构成敏感性，不是安全比较", A[ds][A[ds]["Reporting Entity"] != top_ent]),
        ]
        for sid, desc, d in scen:
            for k, v in metric_set(d).items():
                rows.append({"dataset": ds, "scenario": sid, "scenario_desc": desc, "n": len(d), "metric": k, "value": v})
    sens = pd.DataFrame(rows)
    sens.to_csv(TABLE_DIR / "sensitivity_checks.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------------------ 12. 关键指标
    K = []

    def km(mid, ds, name, num, den=None, unit="%", definition="", text=None):
        val = pct(num, den) if unit == "%" else (text if text is not None else num)
        if isinstance(num, (float, np.floating)) and float(num).is_integer():
            num = int(num)
        K.append({"metric_id": mid, "dataset": ds, "metric": name, "value": val,
                  "numerator": None if num is None else (int(num) if isinstance(num, (np.integer,)) else num),
                  "denominator": None if den is None else int(den), "unit": unit, "definition": definition})

    for ds in DATASETS:
        d, lt = A[ds], L[ds]
        g = clog[clog["dataset"] == ds].set_index("step")
        n = len(d)
        km("K01", ds, "原始行数（含所有版本）", int(g.loc["R0", "rows_before"]), unit="行")
        km("K02", ds, "Report ID 数（最新版本报告）", len(lt), unit="份")
        km("K03", ds, "Same Incident ID 合并后事故数", int(g.loc["R3", "rows_after"]), unit="起")
        km("K04", ds, "分析总体（Incident Date 2025-06 至 2026-09）", n, unit="起")
        km("K10", ds, "Weather - Rain：占全部", d["rain"].sum(), n)
        km("K11", ds, "Weather - Rain：占天气已知", d["rain"].sum(), d["weather_known"].sum(),
           definition="分母：至少勾选一个非 Unk 的天气选项")
        km("K12", ds, "Roadway-Wet Surface Condition：占全部", d["wet_surface"].sum(), n)
        km("K13", ds, "Roadway-Wet Surface Condition：占路面已知", d["wet_surface"].sum(), d["surface_known"].sum(),
           definition="分母：至少勾选一个非 Unknown 的路面描述选项")
        km("K14", ds, "降雨或湿滑：占全部", d["rain_or_wet"].sum(), n)
        km("K15", ds, "降雨或湿滑：占已知", d["rain_or_wet"].sum(), d["rain_or_wet_known"].sum(),
           definition="分母：天气或路面至少一项已知")
        dt = time_ok(d, ds)
        sfx = "" if len(dt) == n else "（剔除时间基准存疑主体）"
        km("K16", ds, f"深夜 22:00-04:59：占时间已知{sfx}", dt["night_22_05"].eq(1).sum(), dt["hour"].notna().sum(),
           definition="当地时间代理指标，不等于光照条件（第三修订版表单无 Lighting 字段）")
        km("K17", ds, f"夜间宽口径 20:00-05:59：占时间已知{sfx}", dt["night_20_06"].eq(1).sum(), dt["hour"].notna().sum())
        nb = tbn[tbn["dataset"] == ds]
        km("K18", ds, "叙述写明的时间与 Incident Time 完全一致（可比较的叙述中）",
           int(nb["n_exact_match"].sum()), int(nb["n_narratives_with_ampm_time"].sum()))
        tv = d[d["_time_verified"]]
        if len(tv) >= 100:  # 稳健性：只用“叙述时间与字段一致”的报告计算时段占比
            km("K16v", ds, "深夜 22:00-04:59：仅限叙述时间与字段一致的报告", tv["night_22_05"].eq(1).sum(), len(tv))
            km("K17v", ds, "夜间宽口径 20:00-05:59：仅限叙述时间与字段一致的报告", tv["night_20_06"].eq(1).sum(), len(tv))
        if ds in TIME_BASE_SUSPECT:
            for ent in TIME_BASE_SUSPECT[ds]:
                sub = tbz[(tbz["dataset"] == ds) & (tbz["reporter_group"] == ent)]
                txt = "; ".join(f"{r.time_zone} 低谷 {r.trough_3h_window} 时" for r in sub.itertuples())
                km("K19", ds, f"时间基准存疑主体（{ent}）各时区 3 小时低谷", None, unit="文本", text=txt,
                   definition="当地时间记录时低谷应在各时区同一钟点；随时区平移约 1 小时/时区，与 UTC 记录一致")
                km("K19n", ds, "时间基准存疑主体的报告占比", int(d["Reporting Entity"].eq(ent).sum()), n)
        km("K1W", ds, "天气已知的事故占比", d["weather_known"].sum(), n)
        num, den, _ = known_share(d, "roadway_group", ["Street", "Intersection"])
        km("K20", ds, "Roadway Type = Street 或 Intersection：占已知", num, den)
        num, den, _ = known_share(d, "roadway_group", ["Highway / Freeway"])
        km("K21", ds, "Roadway Type = Highway / Freeway：占已知", num, den)
        num, den, _ = known_share(d, "roadway_group", ["Parking lot / garage"])
        km("K22", ds, "Roadway Type = Parking Lot/Garage：占已知", num, den)
        km("K23", ds, "Roadway Type = Unknown：占全部", d["roadway_type"].isin(NK).sum(), n)
        num, den, _ = known_share(d, "sv_move_group", ["Stationary"])
        km("K30", ds, "SV Pre-Crash Movement = Stopped/Parked：占已知", num, den)
        km("K31", ds, "SV Pre-Crash Movement = Stopped/Parked：占全部", num, n)
        st = d[d["sv_move_group"] == "Stationary"]
        km("K32", ds, "SV 静止事故中 SV 后部（Rear/Rear Left/Rear Right）有接触", st["sv_rear_contact"].sum(), len(st))
        km("K37", ds, "SV 静止且 SV 后部有接触：占全部", st["sv_rear_contact"].sum(), n)
        num, den, _ = known_share(d, "sv_move_group", ["Proceeding straight"])
        km("K33", ds, "SV Pre-Crash Movement = Proceeding Straight：占已知", num, den)
        num, den, _ = known_share(d, "sv_move_group", ["Lane / road departure"])
        km("K34", ds, "SV Pre-Crash Movement = Lane / Road Departure：占已知", num, den)
        km("K35", ds, "SV Pre-Crash Movement = Unknown：占全部", d["sv_move"].isin(NK).sum(), n)
        for j, grp in enumerate(["Proceeding straight", "Backing / parking", "Lane change / merge / pass"]):
            km(f"K36{j}", ds, f"SV 静止事故中 CP 运动分组 = {grp}", st["cp_move_group"].eq(grp).sum(), len(st))
        dep = d[d["sv_move_group"] == "Lane / road departure"]
        km("K38", ds, "SV Lane / Road Departure 事故中 Crash With = 固定物", dep["crash_with_group"].eq("Fixed object").sum(), len(dep))
        num, den, _ = known_share(d, "crash_with_group", ["Light vehicle"])
        km("K40", ds, "Crash With = 轻型车辆（Passenger Car/SUV/Pickup/Van）：占已知", num, den)
        num, den, _ = known_share(d, "crash_with_group", ["Heavy truck / bus"])
        km("K41", ds, "Crash With = Heavy Truck/Bus：占已知", num, den)
        num, den, _ = known_share(d, "crash_with_group", ["Fixed object"])
        km("K42", ds, "Crash With = 固定物（Pole/Tree、Other Fixed Object）：占已知", num, den)
        num, den, _ = known_share(d, "crash_with_group", ["VRU (non-motorist)"])
        km("K43", ds, "Crash With = Non-Motorist（行人/骑行者/滑板等）：占已知", num, den)
        km("K44", ds, "Crash With = Unknown：占全部", d["crash_with"].isin(NK).sum(), n)
        s = d["speed_mph"].dropna()
        km("K50", ds, "SV Precrash Speed 已知数", len(s), unit="起")
        km("K51", ds, "SV Precrash Speed 中位数（已知）", float(s.median()), unit="mph")
        km("K52", ds, "SV Precrash Speed 第 75 百分位（已知）", float(s.quantile(0.75)), unit="mph")
        km("K53", ds, "SV Precrash Speed = 0 mph：占已知", (s == 0).sum(), len(s))
        km("K54", ds, "SV Precrash Speed ≥ 46 mph：占已知", (s >= 46).sum(), len(s))
        km("K55", ds, "SV Precrash Speed ≤ 10 mph：占已知", (s <= 10).sum(), len(s))
        km("K60", ds, "Highest Injury Severity Alleged = Fatality", int(d["severity_group"].eq("Fatality").sum()), unit="起")
        km("K61", ds, "Highest Injury Severity Alleged = Serious（含/不含住院）", int(d["severity_group"].eq("Serious").sum()), unit="起")
        km("K62", ds, "伤害程度 Unknown：占全部", d["severity_group"].isin(NK).sum(), n)
        num, den, _ = known_share(d, "severity_group", ["No injury reported"])
        km("K63", ds, "无人受伤（No Injured Reported / Property Damage）：占已知", num, den)
        km("K64", ds, "主车气囊展开（Any Air Bags Deployed? = Yes Subject Vehicle…）：占全部", d["airbag_sv"].sum(), n)
        num, den, _ = known_share(d, "within_odd", ["Yes"])
        km("K70", ds, "Within ODD? = Yes：占未脱敏且已知", num, den)
        km("K71", ds, "Within ODD? 脱敏（CBI）：占全部", d["within_odd"].eq("Redacted").sum(), n)
        km("K72", ds, "Engagement Status = Verified Engaged：占全部", d["engagement"].eq("Verified Engaged").sum(), n)
        km("K73", ds, "Engagement Status = Verified Not Engaged", int(d["engagement"].eq("Verified Not Engaged").sum()), unit="起")
        op = "None" if ds == "ADS" else "Consumer"
        km("K74", ds, f"Driver / Operator Type = {op}：占全部", d["operator_type"].eq(op).sum(), n)
        vc = d["Reporting Entity"].value_counts()
        km("K80", ds, "报告量最大的上报主体占比（仅背景）", int(vc.iloc[0]), n, definition=f"主体：{vc.index[0]}")
        km("K81", ds, "上报主体数", int(vc.size), unit="家")
        sv = d["state_std"].value_counts()
        top3 = sv[sv.index != "Not reported"].head(3)
        km("K82", ds, "事故数前三的州合计占比", int(top3.sum()), n, definition="州：" + "/".join(top3.index))
        km("K90", ds, "叙述可读（未整段脱敏）：占全部", d["narrative_status"].eq("readable").sum(), n)
        w = water[(water["dataset"] == ds) & water["in_analysis_population"]] if len(water) else water
        km("K91", ds, "可读叙述中积水/打滑关键词命中（人工复核后）", len(w), unit="份")
        if ds == "ADS":
            km("K92", ds, "叙述写明 SV 驶入积水", int(w["manual_category"].eq("SV entered standing water").sum()), unit="份")
        else:
            km("K92", ds, "叙述写明主车打滑/失控", int(w["manual_category"].eq("SV hydroplaned / lost control").sum()), unit="份")
            km("K93", ds, "其中叙述写明 L2 在碰撞前退出/关闭", int(w["l2_disengaged_before_crash_per_narrative"].sum()), unit="份")
        full = monthly[(monthly["dataset"] == ds) & ~monthly["partial_month"]]
        km("K95", ds, "完整月份（2025-07 至 2026-08）月事故数范围", None, unit="起/月",
           text=f"{full['n_incidents'].min()}–{full['n_incidents'].max()}")
        first3, last3 = full.head(3), full.tail(3)
        a3, b3 = first3["n_incidents"].mean(), last3["n_incidents"].mean()
        km("K96", ds, f"最早 3 个完整月（{first3['incident_month'].iloc[0]}~{first3['incident_month'].iloc[-1]}）月均事故数",
           round(float(a3), 1), unit="起/月")
        km("K97", ds, f"最近 3 个完整月（{last3['incident_month'].iloc[0]}~{last3['incident_month'].iloc[-1]}）月均事故数",
           round(float(b3), 1), unit="起/月")
        km("K98", ds, "K97 / K96（倍数，仅描述报告数量变化，不代表风险变化）", round(float(b3 / a3), 2), unit="倍")
    keym = pd.DataFrame(K)
    fmt = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else (  # noqa: E731
        str(int(v)) if isinstance(v, (int, float, np.integer, np.floating)) and float(v).is_integer() else str(v))
    for col in ["numerator", "denominator"]:
        keym[col] = keym[col].map(fmt)
    keym.to_csv(TABLE_DIR / "key_metrics.csv", index=False, encoding="utf-8-sig")

    with pd.option_context("display.width", 250, "display.max_rows", 500, "display.max_colwidth", 80):
        print(keym[["metric_id", "dataset", "metric", "value", "numerator", "denominator", "unit"]].to_string(index=False))
        print(sens.pivot_table(index=["dataset", "metric"], columns="scenario", values="value").to_string())
        print(tbz.to_string(index=False))
        print(tbn.to_string(index=False))
    print("tables written to", TABLE_DIR)


if __name__ == "__main__":
    main()
