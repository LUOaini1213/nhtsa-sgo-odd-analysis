"""README.md / report.md 中的数字必须能追溯到 output/tables/。

三层检查：
1. 文档里引用的每个 K 编号都存在于 key_metrics.csv；
2. 自动检查：紧挨在「（…Kxx…）」前面的数字，必须等于该 K 编号某个数据集的 value / numerator / denominator
   （文本型 value 如 "82–264" 则取其中的数字）；
3. README 首屏与主要发现表中、K 编号不紧挨数字的说法逐条钉住（下方 PINNED / PINNED_S3）：
   文档必须原样包含这句话，且句中的数字等于表中的值。
"""
from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "output" / "tables"
DOCS = ["README.md", "report.md"]

KID = r"K\d+[a-zA-Z]?"
NUM = r"\d[\d,]*(?:\.\d+)?"


def _read_csv(name: str) -> list[dict[str, str]]:
    with open(TABLES / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


KEY = _read_csv("key_metrics.csv")
SENS = _read_csv("sensitivity_checks.csv")


def _doc(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _dec(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def km(kid: str, dataset: str) -> str:
    rows = [r for r in KEY if r["metric_id"] == kid and r["dataset"] == dataset]
    assert len(rows) == 1, f"key_metrics.csv 中 {dataset}/{kid} 应恰好一行，实际 {len(rows)}"
    return rows[0]["value"]


def sens(dataset: str, scenario: str, metric: str) -> str:
    rows = [r for r in SENS if r["dataset"] == dataset and r["scenario"] == scenario and r["metric"] == metric]
    assert len(rows) == 1, f"sensitivity_checks.csv 中 {dataset}/{scenario}/{metric} 应恰好一行"
    return rows[0]["value"]


def _allowed_numbers(kid: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for r in KEY:
        if r["metric_id"] != kid:
            continue
        for field in ("value", "numerator", "denominator"):
            for tok in re.findall(NUM, r[field]):
                out.add(_dec(tok))
    return out


@pytest.mark.parametrize("doc", DOCS)
def test_every_cited_kid_exists(doc):
    known = {r["metric_id"] for r in KEY}
    cited = set(re.findall(rf"\b{KID}\b", _doc(doc)))
    assert cited, f"{doc} 中没有找到 K 编号"
    missing = sorted(cited - known)
    assert not missing, f"{doc} 引用了 key_metrics.csv 中不存在的编号：{missing}"


@pytest.mark.parametrize("doc", DOCS)
def test_number_right_before_kid_matches(doc):
    text = _doc(doc)
    pat = re.compile(rf"({NUM})\s*(?:%|mph|份|起)?（((?:[^（）]*?/)?[^（）]*?\b{KID}\b[^（）]*)）")
    checked = 0
    bad = []
    for m in pat.finditer(text):
        number = _dec(m.group(1))
        inside = m.group(2)
        kids = re.findall(rf"\b{KID}\b", inside)
        allowed: set[Decimal] = set()
        for k in kids:
            allowed |= _allowed_numbers(k)
        # 括号里形如 68/1,549 的分子/分母也必须来自同一编号
        for frac in re.findall(rf"({NUM})/({NUM})", inside):
            for part in frac:
                if _dec(part) not in allowed:
                    bad.append(f"{m.group(0)}：分数 {part} 不在 {kids} 的取值中")
        if number not in allowed:
            bad.append(f"{m.group(0)}：{number} 不在 {kids} 的取值 {sorted(allowed)} 中")
        checked += 1
    assert checked >= 10, f"{doc} 只匹配到 {checked} 处「数字（K..）」，正则可能失效"
    assert not bad, "\n".join(bad)


# (文档, 必须原样出现的句子片段, 片段中的数字应等于的值)
PINNED = [
    ("README.md", "如果按全部事故算是 9.2%", lambda: km("K14", "ADAS")),
    ("README.md", "ADS 有 86.3% 的事故发生在 CA/TX/AZ 三州（K82）", lambda: km("K82", "ADS")),
    ("README.md", "4 份 ADS 报告的叙述写明车辆驶入积水（K92）", lambda: km("K92", "ADS")),
    ("README.md", "另有 5 份可读的 ADAS 叙述写明车辆打滑", lambda: km("K92", "ADAS")),
    ("README.md", "其中 4 份称 L2 在碰撞前已退出或关闭（K93）", lambda: km("K93", "ADAS")),
    ("README.md", "主车车速中位数为 0 mph", lambda: km("K51", "ADS")),
    ("README.md", "主车车速中位数为 38 mph", lambda: km("K51", "ADAS")),
    ("README.md", "其中 74.3% 撞上固定物（K38）", lambda: km("K38", "ADAS")),
    ("README.md", "有 96.5% 的事故主车气囊展开（K64）", lambda: km("K64", "ADAS")),
    ("README.md", "ADAS 的伤害程度有 91.2% 未知（K62）", lambda: km("K62", "ADAS")),
    ("README.md", "碰撞对象有 52.7% 未知（K44）", lambda: km("K44", "ADAS")),
    ("README.md", "`Within ODD?` 有 91.5% 被脱敏（K71）", lambda: km("K71", "ADAS")),
    ("README.md", "ADS 报告中 Waymo 占 82.8%", lambda: km("K80", "ADS")),
    ("README.md", "ADAS 报告中 Tesla 占 90.0%（K80）", lambda: km("K80", "ADAS")),
    ("README.md", "subject vehicle stopped in 50.3% of known cases, K30", lambda: km("K30", "ADS")),
    ("README.md", "mostly highway (59.6% of known, K21)", lambda: km("K21", "ADAS")),
    ("README.md", "lane/road departure at 35.7% (K34)", lambda: km("K34", "ADAS")),
    ("README.md", "the reporter behind 90.0% of ADAS reports", lambda: km("K19n", "ADAS")),
    # 叙述不可读比例 = 100 - K90
    ("README.md", "叙述有 90.9% 不可读", lambda: str(Decimal(100) - _dec(km("K90", "ADAS")))),
    # 分析口径表
    ("README.md", "| ADS | 1,595 | 1,551 | 1,550 | **1,549** |",
     lambda: [km(k, "ADS") for k in ("K01", "K02", "K03", "K04")]),
    ("README.md", "| ADAS | 2,574 | 2,427 | 2,418 | **2,359** |",
     lambda: [km(k, "ADAS") for k in ("K01", "K02", "K03", "K04")]),
]

S3_ADS = ("ADS", "S3", "SV 静止 Stopped/Parked（占已知%）")
S3_HWY = ("ADAS", "S3", "Highway / Freeway（占已知%）")
S3_DEP = ("ADAS", "S3", "SV Lane / Road Departure（占已知%）")
PINNED_S3 = [
    ("README.md", "主车静止的占比降到 27.1%（`sensitivity_checks.csv`，S3）", S3_ADS),
    ("README.md", "Highway/Freeway 升到 83.3%", S3_HWY),
    ("README.md", "偏离车道降到 19.5%（`sensitivity_checks.csv`，S3）", S3_DEP),
    ("README.md", "excluding it moves 50.3% to 27.1% (ADS)", S3_ADS),
    ("README.md", "and 59.6% to 83.3% (ADAS;", S3_HWY),
    ("report.md", "ADS 的“主车静止”从 50.3% 降到 27.1%", S3_ADS),
    ("report.md", "ADAS 的 Highway 从 59.6% 升到 83.3%", S3_HWY),
    ("report.md", "偏离车道从 35.7% 降到 19.5%", S3_DEP),
]


def _numbers_in(snippet: str) -> list[Decimal]:
    # 去掉 K 编号、S 编号和州名等非数值记号后取数字
    cleaned = re.sub(rf"\b(?:{KID}|S\d)\b", " ", snippet)
    return [_dec(t) for t in re.findall(NUM, cleaned)]


@pytest.mark.parametrize("doc,snippet,expected", PINNED, ids=[p[1][:30] for p in PINNED])
def test_pinned_key_metric_claims(doc, snippet, expected):
    assert snippet in _doc(doc), f"{doc} 中找不到：{snippet}"
    exp = expected()
    exp_list = [_dec(e) for e in (exp if isinstance(exp, list) else [exp])]
    got = _numbers_in(snippet)
    for e in exp_list:
        assert e in got, f"{snippet!r}：期望表中的值 {e}，句中数字为 {got}"


@pytest.mark.parametrize("doc,snippet,key", PINNED_S3, ids=[p[1][:30] for p in PINNED_S3])
def test_pinned_sensitivity_claims(doc, snippet, key):
    assert snippet in _doc(doc), f"{doc} 中找不到：{snippet}"
    want = _dec(sens(*key))
    assert want in _numbers_in(snippet), f"{snippet!r} 应包含 sensitivity_checks.csv 的 {want}"
    base = _dec(sens(key[0], "S0", key[2]))
    nums = _numbers_in(snippet)
    if len(nums) >= 2:  # 「从 A 降到 B」形式：A 必须等于主口径 S0
        assert base in nums, f"{snippet!r} 中的主口径数字应为 S0 的 {base}"
