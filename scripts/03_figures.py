"""03_figures.py - 由 output/tables 中的汇总表生成 6 张图（PNG）

用法:  python -I -X utf8 scripts/03_figures.py
图只读取汇总 CSV（不直接读原始数据），图中所有数字（含标题、脚注）都从汇总表取值，保证“图 = 表”，
数据更新后重跑不会出现过期数字。

配色：ADS = 蓝 #2a78d6，ADAS = 橙 #eb6834（dataviz 校验脚本：CVD ΔE 24.7、正常视觉 ΔE 33.6，通过）。
图 3 右图两条线同属 ADAS，用橙色同色系两档 + 不同标记 + 图例区分（避免同图出现第 3/4 种色相）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # 仅加入本项目 scripts 目录
from config import DATA_UPDATED, FIG_DIR, TABLE_DIR  # noqa: E402
import pipeline as P  # noqa: E402

# ---------------------------------------------------------------- 样式
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, BAND, BAND2 = "#e1e0d9", "#c3c2b7", "#ebeae5", "#f4f3f0"
C = {"ADS": "#2a78d6", "ADAS": "#eb6834"}
ADAS_DARK = "#a8461c"  # 橙色同色系深一档（仅用于图 3 右图的第二条线）
SUSPECT = ", ".join(P.TIME_BASE_SUSPECT.get("ADAS", []))
SOURCE = (f"数据：NHTSA Standing General Order 2021-01 第三修订版事故报告（{DATA_UPDATED} 发布，含 2026-09-15 前收到的报告）。"
          "计数未按车辆数/里程等暴露量归一化，不能据此比较安全性。")

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans SC", "DejaVu Sans"],
    "font.family": "sans-serif",
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": INK2,
    "axes.grid": False,
    "font.size": 9,
})


def read(name: str) -> pd.DataFrame:
    # 只把空字符串当缺失：pandas 默认会把字符串 "None"（Driver / Operator Type 的合法取值）读成 NaN
    return pd.read_csv(TABLE_DIR / name, encoding="utf-8-sig", keep_default_na=False, na_values=[""])


KM = read("key_metrics.csv").set_index(["dataset", "metric_id"])
COMP = read("data_completeness.csv").set_index(["dataset", "field"])


def km(ds: str, mid: str, col: str = "value"):
    v = KM.loc[(ds, mid), col]
    try:
        f = float(v)
        return int(f) if col in ("numerator", "denominator") else f
    except (TypeError, ValueError):
        return v


def comp(ds: str, field: str) -> float:
    return float(COMP.loc[(ds, field), "pct_not_known"])


def style_axis(ax, grid_axis="x"):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    if grid_axis == "x":
        ax.spines["left"].set_visible(False)
        ax.xaxis.grid(True, color=GRID, linewidth=0.6)
        ax.tick_params(axis="y", length=0)
    else:
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.tick_params(axis="x", length=0)
    ax.set_axisbelow(True)


def header(fig, title: str, subtitle: str = ""):
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.012, 0.925, subtitle, ha="left", va="top", fontsize=9, color=INK2)


def footer(fig, extra: str = ""):
    txt = (extra + "\n" if extra else "") + SOURCE
    fig.text(0.012, 0.012, txt, ha="left", va="bottom", fontsize=7.3, color=MUTED, linespacing=1.5)


def legend(ax, loc="upper right"):
    leg = ax.legend(loc=loc, frameon=False, fontsize=8.5, handlelength=1.2)
    for t in leg.get_texts():
        t.set_color(INK2)


def pct_axis(axis):
    axis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))


def grouped_barh(ax, labels, ads_vals, adas_vals, ads_txt=None, adas_txt=None, xmax=None, bar_h=0.34, tick_max=None):
    """水平分组条形：每类上为 ADS、下为 ADAS；数值标在条形末端（文字用墨色，不用系列色）。"""
    y = np.arange(len(labels))[::-1].astype(float)
    gap = 0.03  # 两条之间留出表面色缝隙
    ya, yb = y + bar_h / 2 + gap / 2, y - bar_h / 2 - gap / 2
    ax.barh(ya, ads_vals, height=bar_h, color=C["ADS"], label="ADS")
    ax.barh(yb, adas_vals, height=bar_h, color=C["ADAS"], label="ADAS")
    xmax = xmax or float(np.nanmax(np.r_[ads_vals, adas_vals])) * 1.32
    ax.set_xlim(0, xmax)
    for yy, vals, txts in [(ya, ads_vals, ads_txt), (yb, adas_vals, adas_txt)]:
        for yv, v, t in zip(yy, vals, txts or [None] * len(labels)):
            if not np.isnan(v):
                ax.text(v + xmax * 0.012, yv, t or f"{v:.1f}%", va="center", fontsize=7.6, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.5, color=INK)
    if tick_max is not None:  # 比例轴不显示超过 100% 的刻度
        ax.set_xticks(np.arange(0, tick_max + 1, 20))
    pct_axis(ax.xaxis)
    style_axis(ax, "x")


def dist_values(dist: pd.DataFrame, field: str, cats: list[str], col: str = "pct_of_known"):
    out = {}
    for ds in ["ADS", "ADAS"]:
        sub = dist[(dist["field"] == field) & (dist["dataset"] == ds)].set_index("category")
        out[ds] = np.array([float(sub[col].get(c, 0.0)) if c in sub.index else 0.0 for c in cats])
        out[ds + "_n"] = np.array([int(sub["n"].get(c, 0)) if c in sub.index else 0 for c in cats])
        out[ds + "_known"] = int(sub["n_known"].iloc[0]) if len(sub) else 0
    return out


def save(fig, name: str):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / name, dpi=200)
    plt.close(fig)
    print("saved", FIG_DIR / name)


# ---------------------------------------------------------------- 图 1：月度趋势
def fig1_monthly():
    m = read("monthly_incidents.csv")
    months = m["incident_month"].unique().tolist()
    top = int(np.ceil(m["n_incidents"].max() * 1.1 / 100.0) * 100)
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 5.6), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.82, bottom=0.17, hspace=0.32)
    first, last = months[0], months[-1]
    header(fig, "按事故发生月份统计的报告事故数（ADS 与 ADAS 分开）",
           f"{first} 与 {last} 为部分月份（浅色）：第三修订版 2025-06-16 生效；数据只含 2026-09-15 前收到的报告")
    x = np.arange(len(months))
    for ax, ds in zip(axes, ["ADS", "ADAS"]):
        sub = m[m["dataset"] == ds].set_index("incident_month").loc[months]
        vals = sub["n_incidents"].to_numpy()
        partial = sub["partial_month"].astype(str).str.lower().eq("true").to_numpy()
        colors = [C[ds] if not p else "none" for p in partial]
        ax.bar(x, vals, width=0.62, color=colors)
        ax.bar(x[partial], vals[partial], width=0.62, color=C[ds], alpha=0.32)
        off = top * 0.02
        for i in np.where(partial)[0]:
            ax.text(x[i], vals[i] + off, f"{vals[i]}\n(部分)", ha="center", va="bottom", fontsize=7.2, color=MUTED)
        full = np.where(~partial)[0]
        for i in {full[np.argmax(vals[full])], full[np.argmin(vals[full])]}:
            ax.text(x[i], vals[i] + off, f"{vals[i]}", ha="center", va="bottom", fontsize=7.6, color=INK2)
        ax.set_title(f"{ds}（分析总体 {int(vals.sum()):,} 起）", loc="left", fontsize=9.5, color=INK, pad=4)
        style_axis(ax, "y")
        ax.set_ylim(0, top)
    labels = []
    for i, mo in enumerate(months):
        y, mm = mo.split("-")
        labels.append(f"{int(mm)}\n{y}" if (i == 0 or mm == "01") else f"{int(mm)}")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=8)
    axes[1].set_xlabel("事故月份（Incident Date，仅精确到月）", fontsize=8.5)
    footer(fig, "数量变化可能来自车队规模/运营城市扩张、上报主体增减或上报实践变化，不代表安全水平变化。")
    save(fig, "fig1_monthly_incidents.png")


# ---------------------------------------------------------------- 图 2：ODD 相关条件
def fig2_conditions():
    cond = read("conditions.csv").set_index(["dataset", "condition"])
    rows = [
        ("降雨（Weather - Rain）", "Weather - Rain"),
        ("湿滑路面（Roadway-Wet Surface Condition）", "Roadway-Wet Surface Condition"),
        ("降雨或湿滑（二者任一）", "Rain 或 Wet Surface（rain_or_wet）"),
        ("深夜 22:00-04:59（当地时间）†", "深夜 22:00-04:59（当地时间，基本全年天黑）"),
        ("夜间宽口径 20:00-05:59（当地时间）†", "夜间宽口径 20:00-05:59（当地时间）"),
    ]
    labels, vals, txt = [], {"ADS": [], "ADAS": []}, {"ADS": [], "ADAS": []}
    for lab, key in rows:
        labels.append(lab)
        for ds in ["ADS", "ADAS"]:
            r = cond.loc[(ds, key)]
            vals[ds].append(float(r["pct_of_known"]))
            txt[ds].append(f"{r['pct_of_known']:.1f}%  ({int(r['n']):,}/{int(r['n_known']):,})")
    labels.append("Highway / Freeway（Roadway Type）")
    for ds in ["ADS", "ADAS"]:
        vals[ds].append(km(ds, "K21"))
        txt[ds].append(f"{km(ds, 'K21'):.1f}%  ({km(ds, 'K21', 'numerator'):,}/{km(ds, 'K21', 'denominator'):,})")
    n_time = int(cond.loc[("ADAS", rows[3][1]), "n_known"])
    fig, ax = plt.subplots(figsize=(9.6, 5.4))
    fig.subplots_adjust(left=0.33, right=0.97, top=0.83, bottom=0.2)
    header(fig, "ODD 相关环境条件：在报告事故中所占比例（占该字段已知的事故）",
           f"括号内为 事故数/已知事故数；ADAS 天气未知 {comp('ADAS', 'Weather（无实质选项）'):.1f}%、"
           f"路面描述未知 {comp('ADAS', 'Roadway 描述（无实质选项）'):.1f}%，若把未知视为“无”，比例会更低")
    xmax = max(80.0, max(max(vals["ADS"]), max(vals["ADAS"])) * 1.38)
    grouped_barh(ax, labels, np.array(vals["ADS"]), np.array(vals["ADAS"]), txt["ADS"], txt["ADAS"], xmax=xmax)
    legend(ax, "upper right")
    footer(fig, f"† ADAS 时段只统计 {SUSPECT} 以外的报告（{n_time:,} 起时间已知）：{SUSPECT} 报告的 Incident Time 疑似非当地时间（见图 3）。"
                "时段只是光照的代理指标——第三修订版表单已无 Lighting 字段。")
    save(fig, "fig2_odd_conditions.png")


# ---------------------------------------------------------------- 图 3：时段 + 时间基准检验
def fig3_time():
    hp = read("hourly_profiles.csv")
    tb = read("time_base_check_by_tz.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.9))
    fig.subplots_adjust(left=0.06, right=0.985, top=0.8, bottom=0.25, wspace=0.18)
    header(fig, "事故发生时段（光照的代理指标）与 Incident Time 时间基准检验",
           "左：按当地时间小时的分布；右：ADAS 最大上报主体在东部（ET）与太平洋（PT）时区州的小时分布")
    ymax = float(np.ceil(hp["pct"].max() * 1.35))

    for a, b in [(21.5, 23.5), (-0.5, 4.5)]:
        ax1.axvspan(a, b, color=BAND, lw=0)
    for a, b in [(19.5, 21.5), (4.5, 5.5)]:
        ax1.axvspan(a, b, color=BAND2, lw=0)
    for prof, ds, lab in [("ADS（全部）", "ADS", "ADS"),
                          ("ADAS（剔除时间基准存疑主体）", "ADAS", f"ADAS（{SUSPECT} 以外，样本小）")]:
        s = hp[hp["profile"] == prof].sort_values("hour")
        ax1.plot(s["hour"], s["pct"], color=C[ds], lw=2, marker="o", ms=3.2,
                 label=f"{lab}  n={int(s['n_known_hour'].iloc[0]):,}")
    ax1.text(1.5, ymax * 0.94, "深夜 22-05 时", fontsize=7.4, color=MUTED, ha="center")
    ax1.set_xlabel("当地时间（时）", fontsize=8.5)
    ax1.set_title("占时间已知事故的比例", loc="left", fontsize=9, color=INK2)
    legend(ax1, "upper center")

    tt = tb[(tb["dataset"] == "ADAS") & (tb["reporter_group"] == SUSPECT)].set_index("time_zone")
    for prof, col, mk, tz in [("ADAS 时间基准存疑主体 - ET 州", C["ADAS"], "o", "ET"),
                              ("ADAS 时间基准存疑主体 - PT 州", ADAS_DARK, "s", "PT")]:
        s = hp[hp["profile"] == prof].sort_values("hour")
        ax2.plot(s["hour"], s["pct"], color=col, lw=2, marker=mk, ms=3.4,
                 label=f"{SUSPECT} ADAS 报告 · {tz} 州  n={int(s['n_known_hour'].iloc[0]):,}")
    for tz, col, ytxt in [("ET", C["ADAS"], ymax * 0.36), ("PT", ADAS_DARK, ymax * 0.48)]:
        w = tt.loc[tz, "trough_3h_window"]
        a = int(w[:2])
        ax2.axvspan(a - 0.5, a + 2.5, color=col, alpha=0.10, lw=0)
        ax2.text(a + 1, ytxt, f"{tz} 州低谷\n{w} 时", ha="center", va="bottom", fontsize=7.6, color=INK2, linespacing=1.25)
    sh = (int(tt.loc["PT", "trough_3h_window"][:2]) - int(tt.loc["ET", "trough_3h_window"][:2])) % 24
    ax2.set_xlabel("Incident Time 字段记录的钟点（时）", fontsize=8.5)
    ax2.set_title(f"低谷相差 {sh} 小时（ET 与 PT 时差为 3 小时）", loc="left", fontsize=9, color=INK2)
    legend(ax2, "upper left")
    for ax in (ax1, ax2):
        ax.set_xlim(-0.5, 23.5)
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)])
        ax.set_ylim(0, ymax)
        pct_axis(ax.yaxis)
        style_axis(ax, "y")
    ads_tr = sorted(set(tb[(tb["dataset"] == "ADS")]["trough_3h_window"]))
    footer(fig, f"若记录的是当地时间，各时区的低谷应在同一钟点（ADS 叙述核验 {km('ADS', 'K18', 'numerator'):,}/{km('ADS', 'K18', 'denominator'):,} 份时间一致，"
                f"ADS 各时区低谷为 {'/'.join(ads_tr)} 时）；该主体的低谷随时区平移，\n与 UTC 记录一致，"
                f"因此其报告（占 ADAS {km('ADAS', 'K19n'):.1f}%）不纳入时段统计。这是数据质量判断，不涉及安全比较。")
    save(fig, "fig3_time_of_day_and_timebase.png")


# ---------------------------------------------------------------- 图 4：道路类型 + 车速
def fig4_roadway_speed():
    dist = read("distributions.csv")
    spd_sum = read("speed_summary.csv").set_index("dataset")
    road = ["Street", "Intersection", "Highway / Freeway", "Parking lot / garage", "Rural road", "Other (traffic circle / unpaved)"]
    road_lab = ["Street（城市道路）", "Intersection（路口）", "Highway / Freeway（高速/快速路）",
                "Parking Lot / Garage（停车场）", "Rural Road（乡村道路）", "Traffic Circle / Unpaved"]
    rv = dist_values(dist, "roadway_group", road)
    spd = P.SPEED_LABELS
    spd_lab = ["0", "1-10\n(2-16)", "11-25\n(18-40)", "26-45\n(42-72)", "46-65\n(74-105)", ">65\n(>105)"]
    sv = dist_values(dist, "speed_band", spd)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.6, 4.9), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=0.2, right=0.985, top=0.8, bottom=0.22, wspace=0.28)
    header(fig, "道路类型与主车（SV）碰撞前车速：ADS 以城市低速为主，ADAS 以高速公路、较高车速为主",
           f"均为占已知的比例；已知数 Roadway Type：ADS {rv['ADS_known']:,} / ADAS {rv['ADAS_known']:,}；"
           f"车速：ADS {sv['ADS_known']:,} / ADAS {sv['ADAS_known']:,}")
    grouped_barh(ax1, road_lab, rv["ADS"], rv["ADAS"], xmax=max(80.0, float(np.max(np.r_[rv["ADS"], rv["ADAS"]])) * 1.25))
    ax1.set_title("Roadway Type", loc="left", fontsize=9, color=INK2)
    legend(ax1, "lower right")

    x = np.arange(len(spd))
    w, gap = 0.36, 0.03
    top = float(np.ceil(np.max(np.r_[sv["ADS"], sv["ADAS"]]) * 1.15 / 10) * 10)
    for off, ds in [(-(w / 2 + gap / 2), "ADS"), (w / 2 + gap / 2, "ADAS")]:
        ax2.bar(x + off, sv[ds], width=w, color=C[ds], label=ds)
        for xi, v in zip(x + off, sv[ds]):
            ax2.text(xi, v + top * 0.015, f"{v:.1f}", ha="center", va="bottom", fontsize=7.2, color=INK2)
    ax2.set_xticks(x)
    ax2.set_xticklabels(spd_lab, fontsize=8)
    ax2.set_ylim(0, top)
    pct_axis(ax2.yaxis)
    ax2.set_xlabel("SV Precrash Speed (MPH)（括号内为 km/h）", fontsize=8.5)
    ax2.set_title("SV Precrash Speed 分档", loc="left", fontsize=9, color=INK2)
    style_axis(ax2, "y")
    legend(ax2, "upper right")
    footer(fig, f"ADAS 中 Roadway Type 未知 {km('ADAS', 'K23'):.1f}%、车速未知 {spd_sum.loc['ADAS', 'pct_unknown']:.1f}%；"
                f"ADS 分别为 {km('ADS', 'K23'):.1f}%、{spd_sum.loc['ADS', 'pct_unknown']:.1f}%。"
                "道路构成可能同时反映各系统的设计运行范围（如仅限高速公路使用的系统）与上报门槛。")
    save(fig, "fig4_roadway_speed.png")


# ---------------------------------------------------------------- 图 5：碰撞构型
def fig5_configuration():
    dist = read("distributions.csv")
    mv = ["Stationary", "Proceeding straight", "Turning", "Lane change / merge / pass", "Lane / road departure",
          "Backing / parking", "Other"]
    mv_lab = ["Stopped / Parked（静止）", "Proceeding Straight（直行）", "Turning（转弯）",
              "Lane Change/Merge/Pass（变道等）", "Lane / Road Departure（偏离）", "Backing / Parking（倒车泊车）", "Other（其他）"]
    m = dist_values(dist, "sv_move_group", mv)
    cw = P.CRASH_WITH_ORDER
    cw_lab = ["轻型车辆（Car / SUV / Pickup / Van）", "重卡 / 客车（Heavy Truck / Bus）", "摩托车（Motorcycle）",
              "行人 / 骑行者等（Non-Motorist）", "固定物（Pole / Tree / Other Fixed Object）", "其他（Animal / Other 等）"]
    c = dist_values(dist, "crash_with_group", cw)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 5.0))
    fig.subplots_adjust(left=0.195, right=0.985, top=0.8, bottom=0.2, wspace=0.66)
    header(fig, "碰撞构型：主车碰撞前运动（SV Pre-Crash Movement）与碰撞对象（Crash With）",
           f"均为占已知的比例；已知数 SV 运动：ADS {m['ADS_known']:,} / ADAS {m['ADAS_known']:,}；"
           f"碰撞对象：ADS {c['ADS_known']:,} / ADAS {c['ADAS_known']:,}")
    grouped_barh(ax1, mv_lab, m["ADS"], m["ADAS"], xmax=max(60.0, float(np.max(np.r_[m["ADS"], m["ADAS"]])) * 1.3))
    ax1.set_title("SV Pre-Crash Movement（分组）", loc="left", fontsize=9, color=INK2)
    legend(ax1, "lower right")
    grouped_barh(ax2, cw_lab, c["ADS"], c["ADAS"], xmax=max(80.0, float(np.max(np.r_[c["ADS"], c["ADAS"]])) * 1.3))
    ax2.set_title("Crash With（分组）", loc="left", fontsize=9, color=INK2)
    legend(ax2, "lower right")
    footer(fig, f"ADAS 中 SV 运动未知 {km('ADAS', 'K35'):.1f}%、碰撞对象未知 {km('ADAS', 'K44'):.1f}%。运动状态只描述碰撞前动作，不代表责任归属。"
                f"ADS 静止事故中 {km('ADS', 'K32'):.1f}% 主车后部有接触（{km('ADS', 'K32', 'numerator'):,}/{km('ADS', 'K32', 'denominator'):,}）。")
    save(fig, "fig5_crash_configuration.png")


# ---------------------------------------------------------------- 图 6：伤害程度 + 数据完整度
def fig6_severity_completeness():
    dist = read("distributions.csv")
    sev = P.SEVERITY_ORDER
    sev_lab = ["Fatality（死亡）", "Serious（重伤）", "Moderate（中度）", "Minor（轻微）", "无人受伤 / 仅财损", "Unknown（未知）"]
    s = dist_values(dist, "severity_group", sev, col="pct_of_all")
    s_txt = {ds: [f"{p:.1f}%  ({n:,})" for p, n in zip(s[ds], s[ds + "_n"])] for ds in ["ADS", "ADAS"]}
    fields = ["Roadway Type", "Weather（无实质选项）", "Roadway 描述（无实质选项）", "Crash With", "SV Pre-Crash Movement",
              "SV Precrash Speed (MPH)", "Highest Injury Severity Alleged", "Was Any Vehicle Towed?", "Within ODD?", "Narrative"]
    flab = ["Roadway Type", "Weather（无实质选项）", "Roadway 描述（无实质选项）", "Crash With", "SV Pre-Crash Movement",
            "SV Precrash Speed", "Highest Injury Severity", "Was Any Vehicle Towed?", "Within ODD?（含 CBI 脱敏）", "Narrative（含 CBI 脱敏）"]
    cv = {ds: np.array([comp(ds, f) for f in fields]) for ds in ["ADS", "ADAS"]}
    rt = dist[(dist["field"] == "Report Type") & (dist["dataset"] == "ADAS")].set_index("category")
    five_day = float(rt.loc["5-Day", "pct_of_all"]) if "5-Day" in rt.index else float("nan")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 5.2))
    fig.subplots_adjust(left=0.13, right=0.985, top=0.8, bottom=0.2, wspace=0.55)
    header(fig, "伤害程度（Highest Injury Severity Alleged）与数据完整度",
           "左：占全部事故（含 Unknown）；右：各字段 Unknown / 未报告 / 脱敏的比例。ADAS 的上报门槛本身偏向严重事故（气囊展开、送医、死亡、撞击弱势道路使用者）")
    grouped_barh(ax1, sev_lab, s["ADS"], s["ADAS"], s_txt["ADS"], s_txt["ADAS"], xmax=125, tick_max=100)
    ax1.set_title("伤害程度分组（占全部）", loc="left", fontsize=9, color=INK2)
    legend(ax1, "upper right")
    grouped_barh(ax2, flab, cv["ADS"], cv["ADAS"], xmax=118, tick_max=100)
    ax2.set_title("未知 / 脱敏比例", loc="left", fontsize=9, color=INK2)
    legend(ax2, "upper right")
    footer(fig, "两类报告门槛不同（ADS 含一定财损事故；ADAS 仅限死亡/送医/气囊展开/撞击弱势道路使用者），伤害构成不可直接比较。"
                f"NHTSA 说明：遥测可让上报主体很快获知气囊展开，\n但未必掌握路面、伤情等细节；本数据 ADAS 最新版本中 {five_day:.1f}% 为 5-Day 报告。")
    save(fig, "fig6_severity_completeness.png")


def main():
    fig1_monthly()
    fig2_conditions()
    fig3_time()
    fig4_roadway_speed()
    fig5_configuration()
    fig6_severity_completeness()


if __name__ == "__main__":
    main()
