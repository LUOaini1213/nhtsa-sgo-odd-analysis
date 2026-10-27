# NHTSA 自动驾驶 / L2 辅助驾驶事故报告分析：ODD 条件与国际化启示

> **English summary.** A descriptive analysis of NHTSA's Standing General Order (SGO 2021-01, third amendment) crash reports, keeping ADS (L3–L5, mostly robotaxis) and Level 2 ADAS reports apart. It profiles roadway, weather, surface, time of day, crash partner and pre-crash movement, and draws implications for ODD definition, L2 HMI / driver monitoring and deployment in rainy markets. Descriptive only: the data are not normalised by exposure, so they cannot rank the safety of companies or systems. The pipeline re-runs from the raw CSVs in `data/raw/` and reproduces every table byte for byte.

罗文杰（Luo Wenjie）｜2026-10｜个人项目，使用 AI 工具辅助完成。

数据：NHTSA Standing General Order (SGO) 2021-01 第三修订版事故报告。2026-10-15 发布，覆盖 2025-06-16 至 2026-09-15 收到的报告。

**做了什么**：用 NHTSA 公开的 SGO 事故报告，把 ADS（L3–L5，主要是 Robotaxi）和 L2 ADAS 两类报告分开，描述事故发生的道路、天气、路面、时段、碰撞对象和碰撞前动作。在此基础上，提炼对 ODD 定义、L2 人机交互（HMI）/驾驶员监控（DMS），以及在多雨市场（如马来西亚）部署的启示。**本项目只做描述性统计：这些数据没有按车辆数或里程等暴露量归一化，不能用来比较公司或系统谁更安全，也不做因果推断。**

## 必读：NHTSA 官方对数据的提示（详见 report.md 第 3 节）
1. ADS 与 L2 ADAS 的上报门槛不同。L2 只报四类事故：死亡、有人送医、气囊展开、撞击弱势道路使用者。ADS 还要报达到一定财损或有车辆被拖走的事故。
2. 各公司获取事故信息的能力差别很大（车辆遥测 vs 等车主投诉），因此数据不能当作全部事故的代表性样本。
3. 报告可能不完整，也可能未经核实。
4. 涉及商业机密（CBI）和个人信息（PII）的内容已经脱敏。
5. 同一起事故可能有多份报告。
6. 数据没有按任何暴露量（包括 ODD、行驶里程）归一化。

## 分析口径（规则 R0–R13 见 report.md 第 4 节）
| | 原始行（含所有版本） | 每个 Report ID 取最新版本 | 按 Same Incident ID 合并 | 事故月份 2025-06 至 2026-09（分析总体） |
|---|---|---|---|---|
| ADS | 1,595 | 1,551 | 1,550 | **1,549** |
| ADAS | 2,574 | 2,427 | 2,418 | **2,359** |

## 主要发现（括号内为 `output/tables/key_metrics.csv` 中的指标编号）
| # | 观察（数据本身） | 解读（推断，不是因果结论） |
|---|---|---|
| 1 | 降雨或湿滑路面：ADS 占 4.4%（68/1,549，K14）。ADAS 在天气或路面已知的事故中占 14.3%（218/1,520，K15）；如果按全部事故算是 9.2%。ADS 有 86.3% 的事故发生在 CA/TX/AZ 三州（K82）。 | 这个比例主要反映车队在哪里、在什么天气下运行（即暴露），不能说明雨天更危险或更安全。美国 Robotaxi 数据里雨天样本很少，结论不能直接搬到马来西亚这类多雨市场。 |
| 2 | 4 份 ADS 报告的叙述写明车辆驶入积水（K92）。其中 3 份没有其他交通参与者，车辆受损并被拖离；4 份的 `Within ODD?` 都填 Yes。另有 5 份可读的 ADAS 叙述写明车辆打滑，其中 4 份称 L2 在碰撞前已退出或关闭（K93），3 份给出了时间：碰撞前 5.8–8 秒。 | 积水/内涝是真实存在的 ODD 边缘场景，但 SGO 表单里没有积水或水深字段，只能从叙述文本中找到。ODD 需要明确规定水深阈值，以及积水的检测与应对方式；L2 需要更早提示驾驶员并主动降速。注意这些只是个案，不代表发生频率。 |
| 3 | ADS 事故中，Street 与 Intersection 合计占 89.4%（K20）。主车静止（Stopped/Parked）占 50.3%（K30）。主车车速中位数为 0 mph，≤10 mph 的占 77.3%（K51、K55）。主车静止且后部有碰撞接触的占全部 ADS 事故的 33.8%（524/1,549，K37）。 | Robotaxi 的报告事故以城市低速、与人类驾驶车辆交互为主。所以 ODD 不只是天气、道路等环境条件，还应包括交通交互场景，例如停车、上下客、周边车辆倒车等。（这里只描述车辆动作，不判断责任。） |
| 4 | ADAS 事故中，Highway/Freeway 占已知的 59.6%（K21）。主车车速中位数为 38 mph，≥46 mph 的占 39.5%（K51、K54）。`Lane / Road Departure`（偏离车道/道路）占已知的 35.7%（K34），其中 74.3% 撞上固定物（K38）。有 96.5% 的事故主车气囊展开（K64），这与 L2 的上报门槛有关。 | 被上报的 L2 事故中，中高速下偏离车道的单车事故是一个突出的类型。这与三件事有关：驾驶员监控（DMS）、接管提示，以及对 ODD 边界（车道线、弯道、雨天）的识别。但从数据无法判断偏离是系统还是驾驶员造成的。 |
| 5 | 数据缺口：ADAS 的伤害程度有 91.2% 未知（K62），碰撞对象有 52.7% 未知（K44），`Within ODD?` 有 91.5% 被脱敏（K71），叙述有 90.9% 不可读。ADAS 报告量最大的主体占 90.0%（K19n），它的 `Incident Time` 在不同时区的事故低谷时段相差 3 小时（东部 07–09 时，太平洋 10–12 时），疑似记录的是 UTC，而不是数据字典规定的当地时间（K19）。另外，新版表单没有 Lighting 和 Posted Speed Limit 字段。 | 如果想用事故数据支撑 ODD 结论，车企自己的数据记录就必须包含天气、路面、光照、限速和接管时序，并统一时间基准（UTC 加时区）。本项目发现的时间基准问题就是一个具体例子。 |

**上报主体只作背景说明，不是安全排名**：ADS 报告中 Waymo 占 82.8%，ADAS 报告中 Tesla 占 90.0%（K80）。因此“ADS 与 ADAS 的差别”在很大程度上是少数几家公司的车队规模、运营地域和上报习惯不同，再叠加两类报告不同的上报门槛。

## 图（`output/figures/`）
`fig1` 月度事故数｜`fig2` ODD 相关条件｜`fig3` 时段（光照代理指标）与时间基准检验｜`fig4` 道路类型与车速｜`fig5` 碰撞构型｜`fig6` 伤害程度与数据完整度

## 如何复现
在 Python 3.13 / pandas 3.0.5 / numpy 2.5.0 / matplotlib 3.11.0 上运行通过（`requirements.txt`）。图中的中文需要系统里有中文字体（Windows 默认的微软雅黑即可）；没有中文字体时图照样生成，只是中文显示为方框。

```bash
pip install -r requirements.txt
python -I -B -X utf8 scripts/run_all.py
```

- 默认读取仓库内的 `data/raw/`（NHTSA 官方 CSV 原样副本，只读）。换成别的版本时，设置环境变量 `NHTSA_SGO_DIR` 指向那个目录。
- 运行顺序：`00_inspect_raw` 结构探查 → `01_clean` 清洗 → `02_analyze` 统计 → `03_figures` 作图。图中的数字全部取自 `output/tables`。
- `-I`（隔离模式）保证不会从数据目录或当前目录导入任何代码；`-B` 不生成 `__pycache__`；`-X utf8` 保证中文输出不乱码。
- 从 `data/raw/` 重跑后，`output/tables/` 的 17 张表与仓库里的版本逐字节一致（2026-10-27 在 Windows 上验证）。

## 目录
```
README.md            本页
report.md            完整报告：字段、NHTSA 提示、清洗规则、全部描述统计、洞察、局限
data/raw/            NHTSA SGO 原始 CSV（ADS、ADAS 各一份），来源与校验值见 data/README.md
scripts/             config / io_utils / pipeline（清洗规则）/ 00–03 / run_all
output/tables/       汇总 CSV（key_metrics.csv 收录了文档中引用的全部数字）
output/figures/      6 张 PNG 图
output/clean/        清洗后的数据（运行时生成，不入库）
```

## 局限（详见 report.md 第 8 节）
- 没有暴露量数据，所以不能计算事故率，也不能比较安全性；所有占比都只是在“报告事故”这个范围内的构成。
- 观察期只有约 15.5 个月，首尾两个月（2025-06、2026-09）数据不完整。
- 第三修订版删除了 Lighting 和 Posted Speed Limit 字段。本项目只能用事故发生时段近似光照条件，无法分析限速。
- ADAS 的未知比例很高，因此同时给出“占全部”和“占已知”两种口径。叙述关键词的人工复核由一人完成，可能有遗漏。

## 许可
- 代码：MIT（见 `LICENSE`）。
- 数据：NHTSA 发布的 SGO 事故报告，属于美国联邦政府作品，详见 `data/README.md`。
