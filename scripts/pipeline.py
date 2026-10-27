"""pipeline.py - 清洗规则与派生字段（01_clean.py / 02_analyze.py 共用）

每条规则在 report.md 第 4 节有对应编号（R1-R13）。函数只做确定性的转换，
不读取网络、不执行数据中的任何内容。
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 常量
WINDOW_START = pd.Period("2025-06", freq="M")
WINDOW_END = pd.Period("2026-09", freq="M")
PARTIAL_MONTHS = {
    "2025-06": "第三修订版 SGO 于 2025-06-16 生效，当月只部分覆盖",
    "2026-09": "仅含 2026-09-15 前收到的报告；ADS 月报（次月 15 日前提交）尚未到期",
}

CBI_FULL = "[REDACTED, MAY CONTAIN CONFIDENTIAL BUSINESS INFORMATION]"
REDACTION_RE = re.compile(r"\[REDACTED|MAY CONTAIN|\[XXX\]")
UNKNOWN_TOKENS = {"unknown", "unknown, see narrative", "unknown - see narrative", "unk"}
NOT_KNOWN = {"Unknown", "Not reported", "Redacted"}

WEATHER_UNK = "Weather - Unk - See Narrative"
ROADWAY_UNK = "Roadway-Unknown"
ADVERSE_WEATHER = [
    "Weather - Rain",
    "Weather - Snow",
    "Weather - Fog/Smoke/Haze",
    "Weather - Severe Wind",
    "Weather - Dust Storm",
    "Weather - Severe Hurricane",
]
SV_REAR = ["SV Contact Area - Rear", "SV Contact Area - Rear Left", "SV Contact Area - Rear Right"]
SV_FRONT = ["SV Contact Area - Front", "SV Contact Area - Front Left", "SV Contact Area - Front Right"]

# 叙述文本中的“积水/打滑”关键词（带词边界，避免 corresponding/responding 误命中 ponding）
WATER_RE = re.compile(
    r"\bflood\w*|standing water|water on the road\w*|pooled water|\bponding\b|\bpuddles?\b|"
    r"\bsubmerged\b|high water|deep water|hydroplan\w*|aquaplan\w*",
    flags=re.IGNORECASE,
)

# 去重时用于衡量“信息完整度”的关键字段
INFO_FIELDS = [
    "roadway_type",
    "crash_with",
    "severity",
    "sv_move",
    "cp_move",
]

# ---------------------------------------------------------------- 分组映射
SEVERITY_GROUP = {
    "Fatality": "Fatality",
    "Serious W/ Hospitalization": "Serious",
    "Serious W/O Hospitalization": "Serious",
    "Serious With Hospitalization": "Serious",
    "Serious Without Hospitalization": "Serious",
    "Moderate W/ Hospitalization": "Moderate",
    "Moderate W/O Hospitalization": "Moderate",
    "Moderate With Hospitalization": "Moderate",
    "Moderate Without Hospitalization": "Moderate",
    "Minor W/ Hospitalization": "Minor",
    "Minor W/O Hospitalization": "Minor",
    "Minor With Hospitalization": "Minor",
    "Minor Without Hospitalization": "Minor",
    "No Injured Reported": "No injury reported",
    "No Injuries Reported": "No injury reported",
    "Property Damage. No Injured Reported": "No injury reported",
    "Property Damage, No Injury": "No injury reported",
}
SEVERITY_ORDER = ["Fatality", "Serious", "Moderate", "Minor", "No injury reported", "Unknown"]

CRASH_WITH_GROUP = {
    "Passenger Car": "Light vehicle",
    "SUV": "Light vehicle",
    "Pickup Truck": "Light vehicle",
    "Van": "Light vehicle",
    "Heavy Truck": "Heavy truck / bus",
    "Bus": "Heavy truck / bus",
    "Motorcycle": "Motorcycle",
    "Non-Motorist: Pedestrian": "VRU (non-motorist)",
    "Non-Motorist: Cyclist": "VRU (non-motorist)",
    "Non-Motorist: Scooter - Skateboard": "VRU (non-motorist)",
    "Non-Motorist: Other": "VRU (non-motorist)",
    "Non- Motorist: Other": "VRU (non-motorist)",
    "Pole / Tree": "Fixed object",
    "Other Fixed Object": "Fixed object",
    "First Responder Vehicle": "Other",
    "Animal": "Other",
    "Other, see Narrative": "Other",
}
CRASH_WITH_ORDER = [
    "Light vehicle",
    "Heavy truck / bus",
    "Motorcycle",
    "VRU (non-motorist)",
    "Fixed object",
    "Other",
]

MOVE_GROUP = {
    "Stopped": "Stationary",
    "Parked": "Stationary",
    "Proceeding Straight": "Proceeding straight",
    "Making Left Turn": "Turning",
    "Making Right Turn": "Turning",
    "Making U-Turn": "Turning",
    "Changing Lanes": "Lane change / merge / pass",
    "Merging": "Lane change / merge / pass",
    "Passing": "Lane change / merge / pass",
    "Entering Traffic": "Lane change / merge / pass",
    "Crossing into Opposing Lane": "Lane change / merge / pass",
    "Lane / Road Departure": "Lane / road departure",
    "Backing": "Backing / parking",
    "Parking Maneuver": "Backing / parking",
    "Traveling Wrong Way": "Other",
    "Other, see Narrative": "Other",
    "NM Crossing Roadway": "Non-motorist movement",
    "NM Waiting to Cross Roadway": "Non-motorist movement",
    "NM Moving Alongside Roadway": "Non-motorist movement",
    "NM Moving on Sidewalk": "Non-motorist movement",
    "NM in Roadway - Other": "Non-motorist movement",
}
MOVE_ORDER = [
    "Stationary",
    "Proceeding straight",
    "Turning",
    "Lane change / merge / pass",
    "Lane / road departure",
    "Backing / parking",
    "Non-motorist movement",
    "No crash partner (fixed object)",
    "Other",
]

ROADWAY_GROUP = {
    "Street": "Street",
    "Intersection": "Intersection",
    "Highway / Freeway": "Highway / Freeway",
    "Parking Lot": "Parking lot / garage",
    "Parking Garage": "Parking lot / garage",
    "Rural Road": "Rural road",
    "Traffic Circle": "Other (traffic circle / unpaved)",
    "Unpaved Road": "Other (traffic circle / unpaved)",
}
ROADWAY_ORDER = [
    "Street",
    "Intersection",
    "Highway / Freeway",
    "Parking lot / garage",
    "Rural road",
    "Other (traffic circle / unpaved)",
]

SPEED_BINS = [-0.1, 0, 10, 25, 45, 65, np.inf]
SPEED_LABELS = ["0", "1-10", "11-25", "26-45", "46-65", ">65"]

TIME_BAND_LABELS = ["00:00-05:59", "06:00-09:59", "10:00-15:59", "16:00-19:59", "20:00-23:59"]

# 时间基准检验用：只取基本处于单一时区的州（跨时区的州如 TN/KY/NE/KS/ND/SD/ID/OR 不纳入）
STATE_TZ: dict[str, str] = {}
for _s in "CT DE DC FL GA IN ME MD MA MI NH NJ NY NC OH PA RI SC VT VA WV".split():
    STATE_TZ[_s] = "ET"
for _s in "AL AR IL IA LA MN MS MO OK TX WI".split():
    STATE_TZ[_s] = "CT"
for _s in "CO MT NM UT WY".split():
    STATE_TZ[_s] = "MT"
STATE_TZ["AZ"] = "AZ (MST, 无夏令时)"
for _s in "CA NV WA".split():
    STATE_TZ[_s] = "PT"

# R8b 时间基准存疑的上报主体：其小时分布的“低谷”随时区平移（ET 07-09 时 → CT 08-10 时 → PT 10-12 时），
# 与 UTC 记录一致，而数据字典规定 Incident Time 为当地时间。依据见 output/tables/time_base_check_by_tz.csv。
# 处理：这些主体的报告不参与“时段/夜间”统计（其他字段照常使用）。数据更新后需重新核对。
TIME_BASE_SUSPECT: dict[str, list[str]] = {"ADAS": ["Tesla, Inc."]}

# 叙述中“h:mm AM/PM”形式的时间，用于核对 Incident Time 是否为当地时间
NARRATIVE_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*([AaPp])\.?\s*[Mm]\.?")


def trough_peak_3h(hours: pd.Series) -> tuple[str, str, int]:
    """24 小时环形、3 小时滑动窗口内事故最少/最多的时段（用于判断时间基准）。"""
    h = hours.dropna().astype(int).to_numpy()
    cnt = np.bincount(h, minlength=24).astype(float)
    roll = np.array([cnt[[(i + k) % 24 for k in range(3)]].sum() for i in range(24)])
    tmin, tmax = int(roll.argmin()), int(roll.argmax())
    return f"{tmin:02d}-{(tmin + 2) % 24:02d}", f"{tmax:02d}-{(tmax + 2) % 24:02d}", int(len(h))


def narrative_time_offset_h(narrative: str, field_time: str) -> float:
    """叙述首个 AM/PM 时间与 Incident Time 字段之差（小时，归一到 [-12, 12)）；无法比较时返回 NaN。"""
    m = NARRATIVE_TIME_RE.search(narrative or "")
    f = re.fullmatch(r"(\d{1,2}):(\d{2})", (field_time or "").strip())
    if not (m and f):
        return np.nan
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    diff = (int(f.group(1)) * 60 + int(f.group(2)) - h * 60 - int(m.group(2))) / 60.0
    return (diff + 12) % 24 - 12


# ---------------------------------------------------------------- 工具函数
def strip_all(df: pd.DataFrame) -> pd.DataFrame:
    """R0：所有单元格去首尾空白（原始数据中存在 ' ' 这类只含空格的值）。"""
    return df.apply(lambda s: s.astype(str).str.strip())


def std_category(value: str, blank_label: str = "Not reported") -> str:
    """R5：统一单选字段的未知/空白/脱敏取值，其余保留 NHTSA 原始英文取值。"""
    v = (value or "").strip()
    if v == "":
        return blank_label
    if REDACTION_RE.search(v):
        return "Redacted"
    if v.lower() in UNKNOWN_TOKENS:
        return "Unknown"
    return v


def latest_versions(df: pd.DataFrame) -> pd.DataFrame:
    """R1：每个 Report ID 只保留 Report Version 最大的一行。"""
    ver = pd.to_numeric(df["Report Version"], errors="raise")
    idx = df.assign(_ver=ver).groupby("Report ID")["_ver"].idxmax()
    out = df.loc[idx.values].copy()
    out["n_versions_in_file"] = out["Report ID"].map(df["Report ID"].value_counts())
    out["min_version_in_file"] = out["Report ID"].map(df.assign(_ver=ver).groupby("Report ID")["_ver"].min())
    return out.reset_index(drop=True)


def parse_hour(t: str) -> float:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (t or "").strip())
    if not m:
        return np.nan
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return float(h)
    return np.nan


def time_band(h: float) -> str:
    if pd.isna(h):
        return "Unknown"
    h = int(h)
    if h < 6:
        return TIME_BAND_LABELS[0]
    if h < 10:
        return TIME_BAND_LABELS[1]
    if h < 16:
        return TIME_BAND_LABELS[2]
    if h < 20:
        return TIME_BAND_LABELS[3]
    return TIME_BAND_LABELS[4]


def map_group(series: pd.Series, mapping: dict[str, str], extra: dict[str, str] | None = None) -> pd.Series:
    """把标准化后的取值映射到分组；Unknown/Not reported/Redacted 原样保留。"""
    extra = extra or {}

    def f(v: str) -> str:
        if v in extra:
            return extra[v]
        if v in NOT_KNOWN:
            return v
        if v in mapping:
            return mapping[v]
        return f"UNMAPPED: {v}"

    return series.map(f)


# ---------------------------------------------------------------- 派生字段
def derive(df: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """R4-R13：在“最新版本报告”上生成分析字段（不删除任何行）。"""
    d = df.copy()
    d.insert(0, "dataset", dataset)

    # R4 日期：Incident Date 为 MMM-YYYY（字典写 MMM-YY，实际文件为 4 位年份）
    inc = pd.to_datetime(d["Incident Date"].str.title(), format="%b-%Y", errors="coerce")
    d["incident_month"] = inc.dt.strftime("%Y-%m").fillna("")
    sub = pd.to_datetime(d["Report Submission Date"].str.title(), format="%b-%Y", errors="coerce")
    d["submission_month"] = sub.dt.strftime("%Y-%m").fillna("")

    # R5 单选字段标准化
    d["roadway_type"] = d["Roadway Type"].map(std_category)
    d["crash_with"] = d["Crash With"].map(std_category)
    d["severity"] = d["Highest Injury Severity Alleged"].map(std_category)
    d["sv_move"] = d["SV Pre-Crash Movement"].map(std_category)
    # 字典：未报告碰撞伙伴时 CP Pre-Crash Movement 为空 → 不是“缺失”，而是“无碰撞伙伴”
    d["cp_move"] = d["CP Pre-Crash Movement"].map(lambda v: std_category(v, blank_label="No crash partner (fixed object)"))
    d["engagement"] = d["Engagement Status"].map(std_category)
    d["operator_type"] = d["Driver / Operator Type"].map(std_category)
    d["within_odd"] = d["Within ODD?"].map(std_category)
    d["airbag"] = d["Any Air Bags Deployed?"].map(std_category)
    d["towed"] = d["Was Any Vehicle Towed?"].map(std_category)

    # 分组
    d["roadway_group"] = map_group(d["roadway_type"], ROADWAY_GROUP)
    d["crash_with_group"] = map_group(d["crash_with"], CRASH_WITH_GROUP)
    d["severity_group"] = map_group(d["severity"], SEVERITY_GROUP)
    d["sv_move_group"] = map_group(d["sv_move"], MOVE_GROUP)
    d["cp_move_group"] = map_group(
        d["cp_move"], MOVE_GROUP, extra={"No crash partner (fixed object)": "No crash partner (fixed object)"}
    )

    # R6 多选 flag：'Y' = 选中
    wx_cols = [c for c in d.columns if c.startswith("Weather - ")]
    rw_cols = [c for c in d.columns if c.startswith("Roadway-")]
    is_y = lambda cols: d[cols].eq("Y")  # noqa: E731
    d["weather_known"] = is_y([c for c in wx_cols if c != WEATHER_UNK]).any(axis=1)
    d["surface_known"] = is_y([c for c in rw_cols if c != ROADWAY_UNK]).any(axis=1)
    d["rain"] = d["Weather - Rain"].eq("Y")
    d["adverse_weather"] = is_y(ADVERSE_WEATHER).any(axis=1)
    d["wet_surface"] = d["Roadway-Wet Surface Condition"].eq("Y")
    d["rain_or_wet"] = d["rain"] | d["wet_surface"]
    d["rain_or_wet_known"] = d["weather_known"] | d["surface_known"]

    # R7 车速
    spd_raw = d["SV Precrash Speed (MPH)"]
    spd = pd.to_numeric(spd_raw.where(spd_raw != ""), errors="coerce")
    spd = spd.where(d["SV Pre-crash Speed - Unknown"] != "Y")
    d["speed_mph"] = spd
    band = pd.Series(pd.cut(spd, bins=SPEED_BINS, labels=SPEED_LABELS), index=d.index)
    d["speed_band"] = band.cat.add_categories(["Unknown"]).fillna("Unknown").astype(object).astype(str)

    # R8 时间（当地时间）→ 小时 / 时段 / 夜间代理
    hour = d["Incident Time (24:00)"].map(parse_hour)
    hour = hour.where(d["Incident Time - Unknown"] != "Y")
    d["hour"] = hour
    d["time_band"] = hour.map(time_band)
    d["night_20_06"] = np.where(hour.isna(), np.nan, ((hour >= 20) | (hour < 6)).astype(float))
    d["night_22_05"] = np.where(hour.isna(), np.nan, ((hour >= 22) | (hour < 5)).astype(float))

    # 接触部位
    d["sv_rear_contact"] = is_y(SV_REAR).any(axis=1)
    d["sv_front_contact"] = is_y(SV_FRONT).any(axis=1)

    # 其他
    d["engaged"] = d["engagement"].isin(["Verified Engaged", "Alleged Engaged"])
    d["airbag_sv"] = d["airbag"].str.startswith("Yes Subject Vehicle")

    # R12 叙述文本可读性；R13 积水/打滑关键词
    nar = d["Narrative"]
    d["narrative_status"] = np.select(
        [nar.eq(""), nar.eq(CBI_FULL)], ["blank", "redacted (CBI)"], default="readable"
    )
    d["water_keywords"] = [
        "; ".join(sorted({m.group(0).lower() for m in WATER_RE.finditer(t)})) if s == "readable" else ""
        for t, s in zip(nar, d["narrative_status"])
    ]

    # 信息完整度（用于同一事故多报告时择优）
    d["info_missing"] = (
        d[INFO_FIELDS].isin(NOT_KNOWN).sum(axis=1)
        + (~d["weather_known"]).astype(int)
        + (~d["surface_known"]).astype(int)
        + d["speed_mph"].isna().astype(int)
        + d["hour"].isna().astype(int)
    )
    return d


def dedup_incidents(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """R3：同一文件内按 Same Incident ID 合并为“一起事故一行”。

    择优顺序：信息缺失字段最少 → Report Submission Date 最新 → Report ID 字典序最大（保证可复现）。
    Same Incident ID 为空时，以 Report ID 作为事故键（不与其他报告合并）。
    返回 (事故表, 被合并的多报告事故明细)。
    """
    d = d.copy()
    sid = d["Same Incident ID"]
    d["incident_key"] = np.where(sid.eq(""), "RID:" + d["Report ID"], sid)
    d = d.sort_values(
        ["incident_key", "info_missing", "submission_month", "Report ID"],
        ascending=[True, True, False, False],
    )
    grp = d.groupby("incident_key")
    d["n_reports_linked"] = grp["Report ID"].transform("size")
    d["linked_report_ids"] = grp["Report ID"].transform(lambda s: "; ".join(sorted(s)))
    multi = d[d["n_reports_linked"] > 1].copy()
    multi["kept"] = ~multi.duplicated("incident_key", keep="first")
    kept = d.drop_duplicates("incident_key", keep="first").copy()
    return kept.reset_index(drop=True), multi.reset_index(drop=True)


def in_window(d: pd.DataFrame) -> pd.Series:
    """R4：统计窗口 2025-06 至 2026-09（Incident Date 未知者不在窗口内）。

    incident_month 为 'YYYY-MM' 字符串，字典序比较即时间顺序比较。
    """
    m = d["incident_month"]
    return m.ne("") & (m >= str(WINDOW_START)) & (m <= str(WINDOW_END))


def unmapped_values(d: pd.DataFrame) -> dict[str, list[str]]:
    out = {}
    for c in ["roadway_group", "crash_with_group", "severity_group", "sv_move_group", "cp_move_group"]:
        bad = sorted({v for v in d[c].unique() if str(v).startswith("UNMAPPED")})
        if bad:
            out[c] = bad
    return out
