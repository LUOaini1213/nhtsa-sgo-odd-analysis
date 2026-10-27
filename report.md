# NHTSA 自动驾驶 / L2 辅助驾驶事故报告分析：ODD 条件与国际化启示（完整报告）

- 作者：罗文杰（Luo Wenjie）｜完成日期：2026-10-27
- 数据：NHTSA Standing General Order (SGO) 2021-01 第三修订版事故报告。CSV 由 static.nhtsa.gov 下载，2026-10-15 发布，包含 2025-06-16 至 2026-09-15 收到的报告。
- 代码与输出：`scripts/`（可一键复现）、`output/tables/`（汇总表）、`output/figures/`（6 张图）。正文中的数字都可以在 `output/tables/key_metrics.csv` 里按编号（K..）查到，或在对应的汇总表中找到。

> **阅读须知**：本报告只做描述性统计。SGO 数据没有按车辆数、行驶里程等暴露量归一化，各公司的上报门槛和数据获取能力也不同，报告内容还可能未经核实。因此，本报告**不计算事故率，不比较任何公司或系统的安全性，也不做因果推断**。文中“占比”的意思都是“在被上报的事故中所占的比例”。

## 目录
1. 背景与问题
2. 数据来源、范围与字段
3. NHTSA 官方对数据的提示（重点）
4. 数据清洗规则（R0–R13）
5. 数据质量发现
6. 描述性分析（ADS 与 ADAS 分开）
7. 洞察：观察 → 解读 → 局限
8. 局限性汇总
9. 可复现性
附录 A：输出文件；附录 B：数据字典与实际文件的差异

---

## 1. 背景与问题

我在 NUS 的研究关注自动驾驶车辆在积水/洪水条件下的运行设计域（ODD）边界。车企把智能驾驶/智能网联功能带到海外市场时，需要面对海外市场的 ODD 定义、L2 功能的人机交互，以及不同气候和交通环境下的部署问题。本项目借助美国唯一公开的、强制上报的自动驾驶与 L2 事故数据库（NHTSA SGO），回答三个描述性问题：

1. 被上报的 ADS 事故和 L2 ADAS 事故，分别发生在什么道路、天气、路面和时段？
2. 两类事故的碰撞构型有什么不同？构型包括主车与碰撞伙伴的碰撞前运动、碰撞对象、主车车速。
3. 这些描述对 ODD 定义、L2 的 HMI/驾驶员监控，以及在马来西亚这类多雨市场的部署有什么启示？在数据能支持的范围内回答，并说明数据不能回答什么。

## 2. 数据来源、范围与字段

### 2.1 文件与版本
| 文件 | 行数（含所有版本） | Report ID 数 | 字段数 |
|---|---|---|---|
| `SGO-2021-01_Incident_Reports_ADS.csv` | 1,595 | 1,551 | 116 |
| `SGO-2021-01_Incident_Reports_ADAS.csv` | 2,574 | 2,427 | 116 |

- 按 NHTSA 网页说明，这两份 CSV 收录的是 **2025-06-16 至 2026-09-15** 的报告，使用第三修订版字段；第三修订版于 2025-04-24 发布，2025-06-16 生效。2025-06-16 之前的数据在 NHTSA 的归档区，使用旧版字段，本项目未下载。
- 数据字典（2026-10-15 版）的变更记录写明，本次发布包含 2026-09-15 前收到的报告。2025-11-17 起数据开始包含 City 和 State。
- 文件按最新版本的 `Automation System Engaged?`（ADS / ADAS）划分；未报告自动化类型的报告放在 OTHER 文件中。按任务要求本项目没有下载 OTHER 文件；NHTSA 自己的仪表板同样不纳入 Unknown 类型的报告。

### 2.2 第三修订版的上报门槛（据 NHTSA SGO 网页）
- **ADS**：碰撞前 30 秒内任何时刻 ADS 处于使用状态，且事故造成以下任一后果，就必须上报：一定程度的财产损失、死亡、撞击弱势道路使用者、气囊展开、车辆被拖走、有人被送往医院治疗。
- **L2 ADAS**：碰撞前 30 秒内任何时刻 L2 处于使用状态，且事故涉及撞击弱势道路使用者，或造成死亡、气囊展开、有人被送医，才需要上报。**仅有财产损失或仅有拖车的 L2 事故不在上报范围内。**
- 第三修订版的其他变化：最严重的事故 5 天内上报，较轻事故按月上报（ADS 新增了财损门槛）；原则上不再要求多个主体重复上报同一事故，除非各自掌握不同信息；不再要求定期更新，只有获得新信息时才提交更新。

**直接后果**：ADAS 报告从门槛上就偏向严重事故（本数据中 96.5% 主车气囊展开，K64），ADS 报告则包含大量轻微财损事故。两者的伤害构成**不可比较**。

### 2.3 使用到的字段（字段名保留英文）
| 字段 | 含义（据 NHTSA 数据字典） | 本项目用法 |
|---|---|---|
| `Report ID` / `Report Version` | NHTSA 生成的报告号；同一报告每次更新，版本号顺序递增 | R1 取最新版本 |
| `Report Type` | 5-Day / Monthly / Update | 描述、解释月度数据 |
| `Report Submission Date` | 门户记录的提交月份（MON-YYYY） | R3 择优时的次级排序 |
| `Same Incident ID` | NHTSA 根据报告信息生成的“同一事故”标识 | R3 合并同一事故 |
| `Reporting Entity` | 上报主体 | 仅作背景 |
| `Automation System Engaged?` | ADS / ADAS / Unknown, see Narrative | R2 校验 |
| `Engagement Status` | 碰撞前 30 秒到碰撞结束期间，自动化系统的最高接合状态（Verified/Alleged Engaged、Verified Not Engaged、Unknown） | 描述、敏感性分析 S2 |
| `Driver / Operator Type` | Consumer、In-Vehicle / Remote (Commercial/Test)、None 等 | 描述 |
| `Incident Date` / `Incident Time (24:00)` | 事故年月（只精确到月）/ 事故当地时间 | 月度统计、时段代理指标 |
| `City` / `State` | 城市与州；经纬度、地址、邮编已全部脱敏 | 背景、时区检验 |
| `Roadway Type` | 单选：Highway / Freeway、Street、Intersection、Parking Lot、Traffic Circle、Rural Road、Parking Garage、Unpaved Road、Unknown | 道路类型 |
| `Roadway-*`（8 项） | 多选：Wet Surface Condition、Degraded Surface、Missing/Degraded Marking、Work Zone、Traffic Incident、No Unusual Conditions、Other、Unknown | 路面状况 |
| `Weather - *`（11 项） | 多选：Clear、Cloudy、Partly Cloudy、Rain、Snow、Fog/Smoke/Haze、Severe Wind、Dust Storm、Severe Hurricane、Structure-Indoor、Unk - See Narrative | 天气 |
| `Crash With` | 碰撞对象（17 类） | 碰撞对象 |
| `Highest Injury Severity Alleged` | 已确认或被声称的最高伤害程度 | 伤害程度 |
| `SV Pre-Crash Movement` / `CP Pre-Crash Movement` | 主车（SV）/ 碰撞伙伴（CP）碰撞前的运动；未报告碰撞伙伴时 CP 为空 | 碰撞构型 |
| `SV Precrash Speed (MPH)` + `SV Pre-crash Speed - Unknown` | 主车碰撞前车速 | 车速分档 |
| `SV Contact Area - *` | 主车接触部位（多选） | 判断“静止时后部被接触” |
| `Any Air Bags Deployed?` / `Was Any Vehicle Towed?` | 气囊展开 / 车辆拖离 | 描述 |
| `Within ODD?` | 碰撞前 30 秒到结束期间是否处于 ODD 内；可按 CBI 理由脱敏 | 描述 |
| `Narrative` | 上报主体撰写的经过叙述；可部分或整段按 CBI 脱敏，`[XXX]` 表示 PII | 积水/打滑关键词；核对时间 |

**当前文件中没有的字段**：NHTSA 的归档数据字典（2021–2025）中有 `Lighting`（Daylight、Dawn/Dusk、Dark - Lighted、Dark - Not Lighted 等）、`Posted Speed Limit (MPH)` 和单选的 `Roadway Surface`。第三修订版字段中，**没有 `Lighting` 和 `Posted Speed Limit`**，路面状况改为多选的 `Roadway-*`。因此本项目：
- **光照**：用事故时段作为代理指标（规则 R8），并明确标注这不等于光照条件。
- **限速**：无法分析。如需分析，需另行获取归档数据（按任务要求未下载）。

## 3. NHTSA 官方对数据的提示（重点）

以下六条是 NHTSA 在 SGO 网页的 Data 部分和数据字典第 1 节中列出的注意事项，用中文概括：

1. **Reporting Requirements Are Different for ADS and Level 2 ADAS**：两类系统的上报门槛不同（见 2.2）。ADS 门槛更严格，覆盖面更宽。
2. **Access to Crash Data May Affect Crash Reporting**：各公司的数据记录和遥测能力差异很大。L2 车辆多为私人所有，厂商可能只在车主联系时才知道发生了事故，也可能永远不知道。NHTSA 明确表示，不应认为这些数据在统计上代表所有事故；遥测能力强的厂商，可能仅仅因为知道得更多而报告得更多。
3. **Incident Report Data May Be Incomplete or Unverified**：上报主体必须在规定时间内提交报告，无论自己是否核实或认同其中信息。初次报告可能不完整；获得新信息后需要更新，但上报主体没有主动调查的义务。
4. **Redacted Confidential Business Information and Personally Identifiable Information**：上报主体可以对三个字段申请 CBI 保密：自动化功能版本、是否处于 ODD 内、叙述。PII 一律删除。VIN 只保留前 11 位，日期只保留年和月。
5. **The Same Crash May Have Multiple Reports**：同一事故可能有初报和多次更新；第三修订版虽然力求避免重复，但不同主体掌握不同信息时，仍可能各自上报。`Same Incident ID` 用来识别同一事故，但 NHTSA 也提示：VIN 等信息缺失或错误时，这个 ID 可能缺失、不准确，或在不同版本间变化。
6. **Summary Incident Report Data Are Not Normalized**：上报主体不提交车辆数和行驶里程，所以报告数**没有按任何暴露量调整**，包括 ODD 和行驶里程。报告数多的公司，可能只是车更多、跑得更远。

NHTSA 的 FAQ 还专门提醒：在不同主体之间比较事故数据时要谨慎，车辆数、里程、数据获取能力、运营地点等因素都会影响比较的有效性。另外，NHTSA 网页说明：旧版 SGO 下，曾有上报主体把 L2 误标为 ADS（或反过来），NHTSA 正与上报主体一起纠正。

**本项目据此遵守的原则**：
- ADS 与 ADAS 始终分开统计。
- 不计算任何“率”，不比较公司或系统的安全性，上报主体只作为背景信息列出。
- 所有占比同时给出“占全部”和“占已知”两种口径，并注明分母。
- 解读中不使用因果表述。

## 4. 数据清洗规则（R0–R13）

| 规则 | 内容 | ADS 行数 | ADAS 行数 |
|---|---|---|---|
| R0 | 所有列按字符串读取，不自动把任何字符串当作缺失（避免 `None`、`N/A` 等被误读），所有单元格去掉首尾空白 | 1,595 | 2,574 |
| R1 | 同一 `Report ID` 只保留最大的 `Report Version`（与 NHTSA 仪表板“多版本取最新”的做法一致） | 1,551 | 2,427 |
| R2 | 校验最新版本的 `Automation System Engaged?` 与文件类型一致（结果 100% 一致，未剔除任何报告）。有 4 行早期版本的类型与文件类型不同（ADS 文件 1 行、ADAS 文件 3 行），已被 R1 覆盖 | 1,551 | 2,427 |
| R3 | 同一文件内，`Same Incident ID` 相同的多份报告合并为一起事故，保留信息最完整的一份：先比关键字段 Unknown/空白最少，再比提交月份最新，最后按 Report ID 排序以保证可复现。`Same Incident ID` 为空的报告单独成为一起事故。**不跨文件合并**（理由见 5.2） | 1,550 | 2,418 |
| R4 | 统计窗口：`Incident Date` 在 2025-06 至 2026-09（第三修订版报告期）。剔除更早的事故（ADS 1 起，ADAS 58 起，多为旧版 SGO 下首报、此后才提交更新的报告，或迟报的旧事故）和日期未知的事故（ADAS 1 起）。2025-06 与 2026-09 标记为部分月份 | **1,549** | **2,359** |
| R5 | 单选字段统一：`Unknown`、`Unknown, see Narrative`、`Unknown - see Narrative` 合并为 Unknown；空白记为 Not reported；含脱敏标记的记为 Redacted；其余保留 NHTSA 原始英文取值 | | |
| R5b | `CP Pre-Crash Movement` 为空，表示“未报告碰撞伙伴”（数据字典定义），记为 “No crash partner (fixed object)”。已核对：这些空值与 `Crash With` 为固定物完全对应，不一致数为 0 | | |
| R6 | 多选字段 `Weather - *` / `Roadway-*`：Y 表示选中。“天气已知”指至少勾选了一个非 `Unk - See Narrative` 的选项；“路面已知”指至少勾选了一个非 `Roadway-Unknown` 的选项；“降雨或湿滑” = `Weather - Rain` 或 `Roadway-Wet Surface Condition` | | |
| R7 | `SV Precrash Speed (MPH)` 转为数值；空白或 Unknown 标记为 Y 的记为未知。分档：0 / 1–10 / 11–25 / 26–45 / 46–65 / >65 mph | | |
| R8 | `Incident Time (24:00)` 解析出小时（支持 H:MM 和 HH:MM）。时段代理指标：深夜 22:00–04:59（在美国本土几乎所有地点全年都处于日落后、日出前，仅少数高纬度东部地点夏至前后 4 点多已日出）；宽口径 20:00–05:59（夏季 20 时前后和 5 时以后可能仍有天光） | | |
| R8b | 时间基准存疑的上报主体（ADAS 中的 Tesla, Inc.）**不参与时段统计**，其他字段照常使用（依据见 5.3） | | |
| R9 | 伤害程度归为 6 组：Fatality / Serious / Moderate / Minor（各自含“W/”和“W/O Hospitalization”）/ 无人受伤（`No Injured Reported` 和 `Property Damage. No Injured Reported`）/ Unknown | | |
| R10 | 碰撞对象分组：轻型车辆（Passenger Car、SUV、Pickup Truck、Van）/ 重卡与客车 / 摩托车 / 弱势道路使用者（Non-Motorist: *）/ 固定物（Pole / Tree、Other Fixed Object）/ 其他（First Responder Vehicle、Animal、Other） | | |
| R11 | 运动分组：静止（Stopped、Parked）/ 直行 / 转弯 / 变道·汇入·超车·进入车流·越入对向 / 偏离车道或道路 / 倒车·泊车 / 非机动者运动 / 其他 | | |
| R12 | 叙述可读性：整段等于 CBI 脱敏标记的记为不可读；部分 `[XXX]` 脱敏仍视为可读 | | |
| R13 | 积水/打滑关键词（带词边界的正则表达式）：flood*、standing water、water on the road*、pooled water、ponding、puddle(s)、submerged、high water、deep water、hydroplan*、aquaplan*。每条命中都由人工阅读全文复核，复核结论写入 `narrative_water_mentions.csv`。开发中曾发现 `ponding` 会误命中 corresponding 和 responding，因此加了词边界 | | |

每一步的行数见 `output/tables/cleaning_log.csv`，被合并的多报告事故见 `multi_report_incidents.csv`，数据质量检查见 `data_quality_checks.csv`。

## 5. 数据质量发现

### 5.1 多版本与跨期版本
- ADS：1,551 个 Report ID 中有 36 个存在多个版本，版本号连续、无缺号。
- ADAS：2,427 个 Report ID 中有 37 个在本文件中缺少早期版本（文件里最早的版本 > 1）。这 37 份报告的事故都发生在 2025-06 之前，首版是按旧版 SGO 提交的、存放在归档区；本文件只收录了 2025-06-16 之后提交的更新版本。它们全部被 R4 剔除。

### 5.2 `Same Incident ID` 的异常
- ADS 有 1 起事故、2 份报告，来自两个主体（运营方与车辆厂商），合并为 1 起。
- ADAS 有 7 起事故、共 16 份报告：5 起由同一主体重复提交（同车、同时刻），1 起由两个主体分别上报（售后 L2 供应商和车辆厂商），还有 1 起是同一主体的两份报告，同车、同月、同城市，但 `Incident Time` 不同（04:30 和 17:19）。最后这起可能并不是同一事故。本项目仍按 NHTSA 的 ID 合并，并在此说明，影响 1 起。
- **跨文件 ID 重合**：有 1 个 `Same Incident ID` 同时出现在 ADS 和 ADAS 文件中，但两份报告的地点（加州旧金山 vs 新泽西州 Edison）和时间（16:05 vs 23:27）都不同，显然不是同一起事故。这说明该 ID 只适合在文件内部使用，所以 R3 不跨文件合并。
- 同一 Report ID 在不同版本间 `Same Incident ID` 发生变化的：ADS 2 个，ADAS 7 个。均以最新版本为准，这与 NHTSA 的提示一致。

### 5.3 `Incident Time` 的时间基准（本项目的一项独立发现）
数据字典规定，`Incident Time (24:00)` 记录的是事故**当地时间**。检验方法如下：如果记录的确是当地时间，那么不同时区的小时分布，低谷都应出现在同一个钟点（凌晨车流最少时）；如果记录的是 UTC，低谷会随时区按 1 小时/时区平移。

| 分组 | ET | CT | MT | AZ（MST） | PT |
|---|---|---|---|---|---|
| ADS Waymo LLC（3 小时滑动窗口的最低点） | 03–05 时 | 03–05 时 | — | 03–05 时 | 03–05 时 |
| ADS 其他主体 | — | 04–06 时 | — | — | 04–06 时 |
| **ADAS Tesla, Inc.** | **07–09 时** | **08–10 时** | 07–09 时（n=58） | **10–12 时** | **10–12 时** |

（只统计基本处于单一时区的州，各组 n ≥ 40；完整表格见 `time_base_check_by_tz.csv`）

- ADS 的叙述文本常写明当地时间（如 “10:48 PM MT”）。在能比对的 1,391 份叙述中，1,370 份（98.5%）与 `Incident Time` 完全一致（K18），可以确认 ADS 记录的是当地时间。
- ADAS 中 Tesla, Inc. 的报告占 90.0%（K19n），叙述基本都被整段脱敏，无法逐条核对。但它的低谷在 ET、CT、PT 和 AZ 分别为 07–09、08–10、10–12、10–12 时，正好等于“当地 03–05 时”换算成 UTC 的结果（按夏令时换算：EDT=UTC−4、CDT=UTC−5、PDT=UTC−7；亚利桑那全年 MST=UTC−7）。只有 MT 组（n=58）不符合。这与 UTC 记录一致。
- **处理**：这部分报告不参与时段统计（R8b），ADAS 的时段结果只基于其他主体的 231 起事故（时间已知），样本较小。这是数据质量判断，不涉及任何安全比较；结论是“疑似”，可向 NHTSA 反馈核实。

### 5.4 未知与脱敏
| 字段 | ADS 未知/脱敏 | ADAS 未知/脱敏 |
|---|---|---|
| Roadway Type | 0.1% | 38.0% |
| Weather（无实质选项） | 0.0% | 36.5% |
| Roadway 描述（无实质选项） | 0.0% | 52.1% |
| Crash With | 0.0% | 52.7% |
| SV Pre-Crash Movement | 0.1% | 52.9% |
| CP Pre-Crash Movement | 0.3% | 57.1% |
| SV Precrash Speed | 0.0% | 11.7% |
| Highest Injury Severity Alleged | 1.6% | 91.2% |
| Was Any Vehicle Towed? | 0.0% | 92.2% |
| Within ODD?（其中 CBI 脱敏） | 0.9%（0.9%） | 93.5%（91.5%） |
| Narrative（不可读，含整段 CBI 脱敏） | 0.1% | 90.9% |
| Latitude / Longitude | 100% 脱敏 | 100% 脱敏或为空 |

（`data_completeness.csv`、`data_quality_checks.csv`）ADAS 最新版本中有 94.5% 是 5-Day 报告。NHTSA 解释过，遥测能让上报主体很快知道气囊展开了，但未必掌握路面、伤情等细节。

其他小问题（按原值保留，不做修改）：
- ADS 有 9 份报告的 `SV Pre-Crash Movement` 为 Stopped/Parked，但车速 > 0。
- ADAS 有 10 份报告车速 > 100 mph。
- 部分叙述中有编码乱码字符（来源文件本身如此）。

## 6. 描述性分析（ADS 与 ADAS 分开）

分析总体：ADS 1,549 起，ADAS 2,359 起。下文“占已知”的分母是该字段已知的事故数。

### 6.1 按月份的事故数（图 1，`monthly_incidents.csv`）
| 月份 | 25-06* | 07 | 08 | 09 | 10 | 11 | 12 | 26-01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADS | 59 | 66 | 61 | 67 | 97 | 112 | 109 | 118 | 92 | 145 | 141 | 118 | 129 | 120 | 103 | 12 |
| ADAS | 89 | 93 | 82 | 105 | 133 | 117 | 130 | 120 | 127 | 155 | 181 | 221 | 227 | 264 | 232 | 83 |

\* 部分月份。2026-09 的 ADS 只有 12 起，因为 ADS 月报要到次月 15 日才提交，本数据截止于 9 月 15 日。

- 完整月份的月事故数：ADS 61–145 起，ADAS 82–264 起（K95）。
- 最近 3 个完整月（2026-06 至 08）的月均事故数，ADS 是最早 3 个完整月（2025-07 至 09）的 1.81 倍（117.3 vs 64.7），ADAS 是 2.58 倍（241.0 vs 93.3）（K96–K98）。
- **不能解读为安全水平变化**：车队规模、运营城市、上报主体以及上报实践的变化，都会改变报告数量，而本数据没有暴露量信息。

### 6.2 道路类型（图 4 左，`distributions.csv` 中的 roadway_group）
| Roadway Type | ADS（占已知，n=1,548） | ADAS（占已知，n=1,463） |
|---|---|---|
| Street | 69.6% | 17.0% |
| Intersection | 19.8% | 17.1% |
| Highway / Freeway | 2.1% | 59.6% |
| Parking Lot / Garage | 8.2% | 2.3% |
| Rural Road | 0.0% | 3.8% |
| Traffic Circle / Unpaved | 0.3% | 0.3% |
| Unknown（占全部） | 0.1% | 38.0% |

### 6.3 天气与路面（图 2，`conditions.csv`）
| 条件 | ADS 占全部（= 占已知） | ADAS 占全部 | ADAS 占已知 |
|---|---|---|---|
| Weather - Clear | 73.3% | 34.8% | 54.8% |
| Weather - Cloudy / Partly Cloudy | 14.1% / 9.1% | 23.6% / 2.7% | 37.2% / 4.3% |
| **Weather - Rain** | **3.9%（61）** | 7.9%（186） | **12.4%（186/1,497）** |
| Snow / Fog-Smoke-Haze | 0 / 0.1% | 0.2% / 0.3% | 0.3% / 0.5% |
| Roadway-No Unusual Conditions | 92.8% | 34.7% | 72.5% |
| **Roadway-Wet Surface Condition** | **2.3%（36）** | 8.6%（204） | **18.1%（204/1,129）** |
| Roadway-Work Zone | 1.7% | 0.9% | 1.9% |
| Roadway-Degraded Surface / Missing-Degraded Marking | 1.0% / 0.1% | 0 / <0.1% | 0 / 0.1% |
| **降雨或湿滑（二者任一）** | **4.4%（68）** | 9.2%（218） | **14.3%（218/1,520）** |

ADS 报告的天气和路面信息全部已知。ADAS 的天气有 36.5% 没有实质选项，路面有 52.1%。“占全部”的比例相当于下界：假设未知的都不是雨天或湿滑。

### 6.4 时段（光照的代理指标）（图 3，`hourly_profiles.csv`、`conditions.csv`）
| 指标 | ADS（n=1,549，当地时间已核验） | ADAS（Tesla, Inc. 以外，n=231） |
|---|---|---|
| 深夜 22:00–04:59 | 23.1%（358） | 17.3%（40） |
| 宽口径 20:00–05:59 | 32.9%（509） | 27.7%（64） |

- ADS 的小时分布：15 时最高（6.7%），03–05 时最低。只用叙述时间与字段完全一致的 1,370 份 ADS 报告计算，深夜占 23.7%，宽口径占 33.8%（K16v/K17v），与主口径基本一致。
- 时段只能近似光照条件，不知道当时是否有路灯。时段占比主要反映各时段的运营量，不能说明夜间风险更高或更低。

### 6.5 碰撞对象（图 5 右，`distributions.csv` 中的 crash_with）
| Crash With（原始取值，占已知） | ADS（n=1,549） | ADAS（n=1,116） |
|---|---|---|
| Passenger Car / SUV / Pickup Truck / Van | 31.5 / 23.7 / 11.0 / 3.2% | 21.2 / 16.1 / 6.5 / 1.0% |
| Heavy Truck / Bus | 9.5 / 3.6% | 3.1 / 0.3% |
| Other Fixed Object / Pole / Tree | 5.4 / 0.7% | 31.9 / 5.5% |
| Motorcycle | 1.0% | 0.7% |
| Non-Motorist（Cyclist / Pedestrian / Scooter 等） | 1.7%（26 起） | 1.1%（12 起） |
| Animal / First Responder Vehicle | 0.8 / 0.6% | 2.4 / 0.4% |
| Other, see Narrative | 7.3% | 9.7% |
| Unknown（占全部） | 0% | 52.7% |

分组口径（K40–K43）：轻型车辆 ADS 69.4% / ADAS 44.9%；重卡与客车 13.0% / 3.4%；固定物 6.1% / 37.4%。

### 6.6 碰撞前运动与碰撞构型（图 5 左，`crash_configuration.csv`）
| SV Pre-Crash Movement（分组，占已知） | ADS（n=1,548） | ADAS（n=1,111） |
|---|---|---|
| 静止（Stopped / Parked） | 50.3% | 2.0% |
| 直行（Proceeding Straight） | 35.0% | 46.3% |
| 转弯（Left / Right / U-Turn） | 7.2% | 11.7% |
| 变道 / 汇入 / 超车等 | 4.2% | 1.3% |
| 偏离车道/道路（Lane / Road Departure） | 0.6% | 35.7% |
| 倒车 / 泊车 | 2.0% | 0.5% |
| 其他 | 0.7% | 2.6% |
| Unknown（占全部） | 0.1% | 52.9% |

| CP Pre-Crash Movement（分组，占已知） | ADS（n=1,545） | ADAS（n=1,012） |
|---|---|---|
| 直行 | 33.7% | 26.3% |
| 变道 / 汇入 / 超车等（ADS 中 `Passing` 有 181 起） | 23.0% | 4.9% |
| 倒车 / 泊车 | 11.6% | 0.0% |
| 转弯 | 10.0% | 7.6% |
| 静止 | 3.8% | 7.2% |
| 未报告碰撞伙伴（固定物） | 6.1% | 41.2% |
| 其他 / 偏离 / 非机动者 | 10.2 / 0.8 / 0.7% | 5.1 / 5.7 / 1.9% |
| Unknown（占全部） | 0.3% | 57.1% |

- **ADS 的典型构型**：主车静止、碰撞伙伴直行（占全部 ADS 事故的 21.1%）；主车静止、伙伴变道/汇入/超车（12.8%）；主车静止、伙伴倒车/泊车（9.2%）。主车静止的 778 起中，67.4% 主车后部（Rear / Rear Left / Rear Right）有接触（K32），这类“静止 + 后部接触”占全部 ADS 事故的 33.8%（K37）。
- **ADAS 的典型构型**：除去运动状态完全未知的组合（52.1%），最多的是“主车偏离车道/道路、无碰撞伙伴”（12.5%）。在 397 起偏离事故中，74.3% 撞上固定物（K38）。
- 运动字段只描述碰撞前的动作，**不代表责任归属**。

### 6.7 主车碰撞前车速（图 4 右，`speed_summary.csv`）
| 指标 | ADS（n=1,549） | ADAS（n=2,083，未知 11.7%） |
|---|---|---|
| 中位数 / P25 / P75 | 0 / 0 / 9 mph | 38 / 22 / 60 mph |
| 0 mph | 50.9% | 2.0% |
| ≤10 mph | 77.3% | 8.7% |
| ≥46 mph（约 74 km/h） | 1.2% | 39.5% |
| >65 mph（约 105 km/h） | 0% | 18.8% |

### 6.8 伤害程度（图 6 左）
| Highest Injury Severity（分组） | ADS（占全部） | ADAS（占全部） |
|---|---|---|
| Fatality | 2 起（0.1%） | 25 起（1.1%） |
| Serious | 4（0.3%） | 20（0.8%） |
| Moderate | 13（0.8%） | 15（0.6%） |
| Minor | 138（8.9%） | 67（2.8%） |
| 无人受伤 / 仅财损 | 1,367（88.3%） | 80（3.4%） |
| Unknown | 25（1.6%） | 2,152（91.2%） |

两类报告的门槛不同，ADAS 的伤害信息又绝大多数未知，所以**这张表不能用来比较 ADS 与 ADAS 的伤害风险**。死亡事故数同样只是报告数，不能换算成死亡率。

### 6.9 接合状态、操作者与 ODD
- `Engagement Status` = Verified Engaged：ADS 96.9%，ADAS 97.8%（K72）。Verified Not Engaged：ADS 44 起，ADAS 7 起。剔除它们后，主要比例的变化不超过 1.1 个百分点（6.12）。
- `Driver / Operator Type`：ADS 中 None（车内外都无人负责驾驶任务）占 83.3%，车内有商业/测试人员的占 15.2%；ADAS 中 Consumer 占 98.1%（K74）。
- `Within ODD?`：ADS 未脱敏的 1,535 起中，1,533 起填 Yes（99.9%，K70），另有 No、Exiting ODD 各 1 起。ADAS 有 91.5% 以 CBI 理由脱敏，已知的 153 起中 Yes 占 97.4%。该字段由上报主体自报。

### 6.10 上报主体与地区（仅作背景，不是安全排名，`reporting_entities_context.csv`）
- ADS：共 19 家主体。Waymo LLC 占 82.8%，Avride 5.2%，Zoox 5.0%，Tesla 2.3%，May Mobility 1.3%，其余 14 家合计 3.4%。按州：CA 52.2%，TX 20.8%，AZ 13.4%，三州合计 86.3%（K82）；GA 5.2%，NV 3.2%，FL 3.0%。
- ADAS：共 21 家主体。Tesla, Inc. 占 90.0%，General Motors 4.8%，Ford 1.2%，其余均 < 1%。按州（占全部）：CA 27.8%，TX 12.6%，FL 8.5%，三州合计 48.9%。
- 报告数取决于车队规模、行驶里程、遥测能力和上报口径，这些数字**不代表任何公司的安全水平**。

### 6.11 叙述文本：积水与打滑个案（`narrative_water_mentions.csv`）
可读叙述：ADS 1,548 份（99.9%），ADAS 214 份（9.1%）。人工复核后的命中如下：

| 数据集 | Report ID | 年月 / 时间 | 地点 | 复核结论（只转述叙述内容，未经核实） |
|---|---|---|---|---|
| ADS | 30270-11571 | 2025-08 / 22:48 | Phoenix, AZ | 主车驶入积水后受损、被拖离，无其他交通参与者 |
| ADS | 30270-11996 | 2025-10 / 00:37 | Austin, TX | 直行通过路口时驶入积水，受损、被拖离，无其他交通参与者 |
| ADS | 30270-15993 | 2026-07 / 13:25 | Atlanta, GA | 驶入积水，底盘接触积水，受损、被拖离，无其他交通参与者 |
| ADS | 30270-16298 | 2026-08 / 23:40 | Tempe, AZ | 变道时驶入积水，减速停在车道内，随后被后方乘用车追尾 |
| ADS | 31101-14899 | 2026-04 / 08:01 | Austin, TX | 主车红灯停车，后车在湿滑路面打滑后追尾 |
| ADAS | 540-15575 | 2026-06 / 19:58 | Hancock, MD | 驾驶员称车辆打滑失控；系统数据称 Super Cruise 在碰撞前 8 秒转为 Disabled/Not Ready |
| ADAS | 540-15297 | 2026-05 / 14:39 | Forsyth, GA | 打滑后撞相邻车道皮卡和护栏；Super Cruise 在碰撞前 5.8 秒因 degraded condition 退出 |
| ADAS | 753-15556 | 2026-06 / 04:45 | Greensboro, GA | 大雨中打滑撞护栏；车辆数据称 LFA 在碰撞前约 6 秒因无法识别车道线而退出，驾驶员持续踩加速踏板 |
| ADAS | 502-14852 | 2026-04 / 15:18 | Temple, TX | 驾驶员称 BlueCruise 开启时转向“卡住”后打滑；厂商称调查仍在进行 |
| ADAS | 1306-14367 | 2026-03 / 17:00 | LA（州） | 警方报告：降雨、路面湿滑有积水；车辆开始摇摆时 LTA 关闭，记录车速 77.6 mph |

- ADS 中写明“主车驶入积水”的有 4 份（K92），都来自同一运营商、三个城市；4 份的 `Within ODD?` 都为 Yes；3 份的时间在 22:00–01:00 之间。
- ADAS 中 5 份写明主车打滑或失控（K92），其中 4 份写明 L2 在碰撞前退出或关闭（K93）。
- 这些是**个案**：关键词检索可能漏掉其他表述；ADAS 90.9% 的叙述不可读；叙述由上报主体撰写，NHTSA 未核实。它们只能证明“这类场景存在”，不能估计发生频率。

### 6.12 稳健性检查（`sensitivity_checks.csv`）
| 指标（占已知 %） | S0 主口径 | S1 全部最新报告 | S2 剔除 Verified Not Engaged | S3 剔除报告量最大的主体 |
|---|---|---|---|---|
| ADS 降雨或湿滑 | 4.4 | 4.4 | 4.5 | 5.6 |
| ADS Highway / Freeway | 2.1 | 2.1 | 1.9 | 5.2 |
| ADS SV 静止 | 50.3 | 50.2 | 51.4 | 27.1 |
| ADS 碰撞对象为固定物 | 6.1 | 6.1 | 5.6 | 13.1 |
| ADAS 降雨或湿滑 | 14.3 | 14.1 | 14.4 | 9.2 |
| ADAS Highway / Freeway | 59.6 | 59.4 | 59.5 | 83.3 |
| ADAS Lane / Road Departure | 35.7 | 34.7 | 35.8 | 19.5 |
| ADAS 碰撞对象为固定物 | 37.4 | 36.9 | 37.3 | 34.6 |

n：ADS 为 1,549 / 1,551 / 1,505 / 267；ADAS 为 2,359 / 2,427 / 2,352 / 237。

- 清洗口径（S1）和是否包含 Verified Not Engaged（S2）对结论几乎没有影响，差异不超过 1.1 个百分点。
- 剔除报告量最大的主体（S3）后，构成明显变化：ADS 的“主车静止”从 50.3% 降到 27.1%；ADAS 的 Highway 从 59.6% 升到 83.3%，偏离车道从 35.7% 降到 19.5%。这说明**汇总分布在很大程度上反映了一两家主体的车队与运营特征**。S3 是构成敏感性检查，不是安全比较。剔除 Tesla 后 ADAS 的 Highway 占比更高，这与部分 L2 系统只在高速公路上设计使用的情况一致，但本数据无法验证各系统的 ODD。

## 7. 洞察：观察 → 解读 → 局限

### 洞察 1：报告中的雨天和湿滑比例不高，主要反映暴露与运营地域，不能外推到多雨市场
- **观察**：降雨或湿滑在 ADS 中占 4.4%（68/1,549，K14）；在 ADAS 中占已知的 14.3%（218/1,520，K15），占全部 9.2%。ADS 事故 86.3% 来自 CA/TX/AZ（K82）。作为光照代理，ADS 有 23.1% 发生在深夜时段，32.9% 发生在宽口径夜间时段。
- **解读**：没有分母（雨天行驶里程）就无法判断雨天风险高低。ADS 的雨天占比低，更可能说明 Robotaxi 主要在少雨的阳光带城市运行，也可能有运营策略的原因，但本数据无法验证。马来西亚属于热带气候，全年多雨，午后强降雨和城市内涝都很常见，在美国事故数据中几乎没有对应样本。
- **对 ODD 与部署的启示**：
  1. 进入多雨市场时，ODD 应把降雨强度、路面积水和能见度写成明确的参数和阈值，不能只写“恶劣天气除外”。
  2. 验证数据需要在当地采集，美国的事故构成不能直接沿用。
  3. 马来西亚靠左行驶，摩托车多，场景库中的转向类场景需要镜像处理，摩托车交互场景需要加权（美国 ADS 数据中摩托车只占 1.0%）。
- **局限**：天气由上报主体填写；ADAS 有三成以上未知；所有占比都不是率。

### 洞察 2：积水是真实存在的 ODD 边缘场景，而现有上报表单无法系统记录它
- **观察**：4 份 ADS 叙述写明主车驶入积水（K92）。其中 3 份没有其他交通参与者，车辆受损被拖离；1 份停在积水中被追尾。4 份都填 `Within ODD?` = Yes，3 份发生在夜间（22:48、23:40、00:37）。5 份可读的 ADAS 叙述写明主车打滑，其中 4 份称 L2 在碰撞前退出或关闭（K93），3 份给出了时间：5.8–8 秒前。
- **解读**：即使在少雨城市，积水也会造成车辆受损和拖车事故，而上报主体仍认为当时处于 ODD 内。这说明“ODD 内”的判断可能没有覆盖水深这一维度，至少在上报口径上如此。SGO 表单没有积水或水深字段，这类事件只能靠阅读叙述发现。
- **对 ODD 与部署的启示**：
  1. ADS 的 ODD 规格中，应定义可通行水深上限、积水检测（感知或地图/气象信息）以及应对策略（绕行、降速、靠边停车等最小风险策略）。
  2. L2 的情况是：系统在湿滑路面上退出时，往往距碰撞只剩几秒，接管条件最差。应考虑在雨天提前提示、主动降速，并在系统退出前确认驾驶员已经准备好接管（需要 DMS）。
  3. 车端数据记录应包含“是否遇到积水”。
  这与我在 NUS 研究的“积水条件下的 ODD 边界”直接对应。
- **局限**：只有 9 份个案，而且是关键词检索加单人复核的结果，可能有遗漏；叙述未经核实；不能据此估计频率，也不能判断原因。

### 洞察 3：ADS（Robotaxi）报告事故以城市低速交互为主
- **观察**：Street 与 Intersection 占 89.4%（K20）。主车静止占 50.3%（K30），车速中位数 0 mph，≤10 mph 占 77.3%。主车静止且后部有接触的占全部 ADS 事故的 33.8%（K37）。主车静止时，碰撞伙伴的运动以直行（42.0%）、变道/汇入/超车（25.4%）、倒车/泊车（18.3%）为主。碰撞对象中轻型车辆占 69.4%，弱势道路使用者占 1.7%。
- **解读**：被上报的 Robotaxi 事故，主要是在混合交通中与人类驾驶车辆发生的低速接触。ODD 的挑战不只是环境条件，还包括交互行为，例如停车位置和时机、上下客、周边车辆倒车或加塞。这里只描述动作，不判断责任。
- **启示**：ODD 和测试场景应把交通交互（场景中其他交通参与者的行为分布）作为显式维度。在海外市场，需要按当地的驾驶习惯（摩托车穿行、靠左行驶）重建交互场景。
- **局限**：ADS 有 82.8% 来自单一运营商，S3 显示剔除该主体后，“主车静止”占比降到 27.1%；ADS 的上报门槛包含轻微财损事故。

### 洞察 4：被上报的 L2 事故以中高速、偏离车道的单车事故最为突出，指向驾驶员监控与 ODD 边界管理
- **观察**：在已知值中，Highway/Freeway 占 59.6%（K21），`Lane / Road Departure` 占 35.7%（K34），偏离事故中 74.3% 撞上固定物（K38），碰撞对象为固定物的占 37.4%（K42）。车速中位数 38 mph，≥46 mph 占 39.5%（K54）。96.5% 主车气囊展开，98.1% 为私人用户（Consumer）。
- **解读**：L2 的上报门槛只纳入较严重的事故，在这些事故中，中高速下偏离车道撞上固定物的单车事故很突出。数据不能说明偏离是系统控制还是驾驶员操作造成的。但 6.11 的个案显示，有的事故中系统在碰撞前数秒退出，或驾驶员在超控系统。这类场景与驾驶员是否保持专注、接管提示是否及时、系统能否识别 ODD 边界（车道线丢失、弯道、雨天）密切相关。
- **启示**：
  1. 面向海外的 L2 应配备摄像头式 DMS，检测视线和注意力，并设置逐级升级的提醒。
  2. 在雨天、车道线质量差等 ODD 边界条件下，提前降级或请求接管，而不是在临界时刻才退出。
  3. 记录接管时序数据，用于事后分析。
  国际法规趋势也在加强对 L2 驾驶员注意力监测的要求（例如 UN R171 DCAS，具体条款以法规原文为准）。
- **局限**：ADAS 有 90.0% 来自单一主体。S3 显示剔除后，偏离车道的占比降到 19.5%，Highway 升到 83.3%，说明构成高度依赖主体。运动和碰撞对象有一半以上未知；上报门槛本身就偏向高速、严重的事故。

### 洞察 5：数据可得性本身就是结论之一，ODD 证据链需要车企自己的数据记录
- **观察**：ADAS 的伤害程度 91.2% 未知（K62），碰撞对象 52.7% 未知，`Within ODD?` 91.5% 被脱敏，叙述 90.9% 不可读。占 ADAS 90.0% 的主体，其 `Incident Time` 疑似为 UTC（5.3）。第三修订版表单没有 Lighting 和 Posted Speed Limit，经纬度全部脱敏。相比之下，ADS 报告几乎没有未知，时间也已用叙述核验（98.5%）。
- **解读**：仅靠外部事故报告，难以重建 ODD 相关的条件（光照、限速、积水深度、接管时序）。时间基准不一致这种看似技术性的细节，会直接让“夜间占比”这类结论失效。
- **启示**：在出海项目中，事件数据记录应包含：天气和降雨强度、路面积水、光照、限速、系统状态和接管时序、DMS 状态，并统一采用 UTC 加时区的时间戳。这样才能满足各国的事故上报和监管问询要求，也能支持 ODD 迭代。
- **局限**：未知比例高可能与上报方式有关（以遥测触发的 5-Day 报告为主）；这是对数据的描述，不代表各主体的数据能力。

## 8. 局限性汇总
1. **没有暴露量**：没有车辆数、里程、运营时段和地域的分母，所以不能计算任何率，不能比较 ADS 与 ADAS 或公司之间的安全性，也不能判断某种条件“更危险”。
2. **上报门槛不同**：ADAS 只纳入死亡、送医、气囊展开、撞击弱势道路使用者四类事故；ADS 包含财损和拖车事故。两类报告的构成差异中，有一部分是门槛造成的。
3. **主体集中**：ADS 有 82.8% 来自单一运营商，ADAS 有 90.0% 来自单一厂商。汇总分布主要反映少数主体的车队和上报实践（6.12）。
4. **报告未经核实且不完整**：ADAS 大量字段未知或被脱敏；叙述由上报主体撰写。
5. **时间窗口短**：约 15.5 个月，首尾月份不完整；仅限美国，以 CA/TX/AZ 为主。
6. **字段变化**：第三修订版没有 Lighting 和限速字段，时段只能作为光照的代理；未与归档数据（旧字段）合并。
7. **时间基准**：ADAS 最大主体的时间疑似为 UTC，因此 ADAS 的时段分析只基于 231 起事故。
8. **同一事故识别**：完全依赖 NHTSA 的 `Same Incident ID`，已知存在跨文件 ID 重合，也有 1 起疑似误合并（影响 1 起）。
9. **未使用 OTHER 文件**：类型未知的报告未纳入，这与 NHTSA 仪表板一致。
10. **人工复核**：积水/打滑叙述由一人复核，可能漏检或误判。

## 9. 可复现性
- 运行命令：在仓库根目录执行 `python -I -B -X utf8 scripts/run_all.py`
- 环境：Python 3.13.14，pandas 3.0.5，matplotlib 3.11.0（Windows，中文字体微软雅黑）。
- 原始数据（`data/raw/`，NHTSA 官方 CSV 原样副本）只读，路径可通过环境变量 `NHTSA_SGO_DIR` 修改。不访问网络，不执行数据中的任何内容。`-I` 隔离模式保证不会从数据目录导入代码。
- 数据源更新后重跑：清洗、统计和作图会自动更新，图中的数字全部取自汇总表。但有两处人工判断需要重新核对：`02_analyze.py` 中的积水叙述人工复核表（出现新命中时会打印“未复核”警告），以及 `pipeline.py` 中的 `TIME_BASE_SUSPECT`（检验结果与设置不一致时会打印警告）。

## 附录 A：输出文件（`output/`）
| 文件 | 内容 |
|---|---|
| `tables/raw_schema_profile.csv` | 原始 116 个字段的非空数、唯一值数、脱敏数、Top 值 |
| `tables/cleaning_log.csv` | R0–R4 每步行数 |
| `tables/data_quality_checks.csv` | 数据质量检查（版本、ID、脱敏、一致性等） |
| `tables/multi_report_incidents.csv` | 被合并的同一事故多报告明细 |
| `tables/monthly_incidents.csv` | 月度事故数（含部分月份标记） |
| `tables/distributions.csv` | 各字段分布（n、占全部 %、占已知 %） |
| `tables/conditions.csv` | 天气和路面多选项、复合条件、时段代理 |
| `tables/hourly_profiles.csv` | 按小时分布（含时区检验分组） |
| `tables/time_base_check_by_tz.csv` / `time_base_check_narratives.csv` | 时间基准检验 |
| `tables/speed_summary.csv` | 车速统计 |
| `tables/crash_configuration.csv` | SV × CP 运动交叉表 |
| `tables/data_completeness.csv` | 未知/脱敏比例 |
| `tables/reporting_entities_context.csv` | 上报主体构成（仅背景） |
| `tables/narrative_water_mentions.csv` | 积水/打滑叙述命中与人工复核 |
| `tables/sensitivity_checks.csv` | 稳健性检查 |
| `tables/key_metrics.csv` | 文档引用的全部数字（编号、分子、分母、定义） |
| `clean/*_reports_latest.csv`、`clean/*_incidents.csv` | 清洗后的数据（不含叙述全文和已脱敏的位置字段） |
| `figures/fig1–fig6*.png` | 6 张图 |

## 附录 B：数据字典与实际文件的差异（处理时需要注意）
- `Incident Date`：字典写 `[MMM-YY]`，实际文件为 `MMM-YYYY`（如 `AUG-2026`）。
- `Highest Injury Severity Alleged`：字典取值如 “Minor Without Hospitalization”“Property Damage, No Injury”，文件实际为 “Minor W/O Hospitalization”“Property Damage. No Injured Reported”“No Injured Reported”。
- `Engagement Status`：字典为 “Unknown, see Narrative”，文件为 “Unknown - see Narrative”。
- `Report Month` / `Report Year`：只在 Monthly 报告中填写，5-Day 和 Update 报告为空。
- `Narrative - CBI?` 等标记字段中存在只含空格的值，R0 统一去除了首尾空白。
- `Incident Time` 有 `H:MM` 和 `HH:MM` 两种格式；ADAS 最大主体的时间疑似 UTC（5.3）。
