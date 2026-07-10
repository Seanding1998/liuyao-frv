# Changelog

## v1.5.9 (2026-07-10)

### 重构 — 拆分 `LUNAR_TABLE` 到独立 `lunar_data.py`

**动机**：v1.5.8 把 62 行农历查找表 `LUNAR_TABLE_2025_2086` 直接内嵌在 `paipan.py` 里，视觉上占屏让主脚本显得臃肿。用户提议"用立春+闰月等关键信息算法推算以减小体积"。

**调研结论**：算法路径不可行。
- 实测 2026-2086 全部 2196 天，用"正月初一锚点 + 平均朔望月 29.5306 天"推算，**错误率 77.5%**（1701/2196 天偏移）
- 根因：农历从清代《时宪历》起改为**定朔**（每月初一是实际新月日），朔望月长度在 29.18-29.93 天之间不规则波动，**无代数公式可算**
- 表本身其实很小：62 年 × 6 字节 = **372 字节 ≈ 0.36 KB**，已是最紧凑精确表示（位编码 1 bit/月）

**重构方案**：保持精确性，仅做代码组织优化。
- 新增 `scripts/lunar_data.py`：独立存放 `LUNAR_TABLE_2025_2086` + 详细数据结构/来源说明
- `paipan.py` 顶部改为 `from lunar_data import LUNAR_TABLE_2025_2086`
- 内部引用点（`_solar_to_lunar_pure()` 等共 5 处）零改动
- 文件头注释解释了"为什么不能用算法推算"（含 77.5% 错误率实验数据），防止未来又有人尝试

**验证**
- sxtwl 分支：`2026-07-10 13:54 → '丙午年五月廿六'` ✅
- pure 分支（`_SXTWL_AVAILABLE=False`）：同上 ✅
- 跨年：`2026-01-15 → '乙巳年十一月廿七'` ✅
- 闰月：`2028-07-05 → '戊申年闰五月十三'` ✅
- 端到端 `python paipan.py --subject ... --seed 42`：JSON `lunar` 字段正确写入 ✅

**零行为变更**：纯重构，外部 API、JSON schema、解卦流程均无变化。

## v1.5.8 (2026-07-10)

### 修复 — `lunar` 字段双轨自动输出（消除 AI 手算农历）

**问题**：`paipan.py` 已用 sxtwl 算四柱，但 **只输出公历 + 四柱，不输出农历日期**。HTML 报告 `meta.lunar` 是必填字段，迫使 AI 在生成报告时手算农历——既易错（实测解卦"找女友"时把五月廿六算成五月廿五，差 1 天）又浪费 token。

**修复 1 — `paipan.py` 双轨输出 `lunar` 字段**
- sxtwl 分支：直接调 `day_obj.getLunarYear/Month/Day()` + `isLunarLeap()`，零手算
- 纯 Python 分支：新增 `LUNAR_TABLE_2025_2086` 查找表（由 sxtwl 一次性预生成的 61 年数据，紧凑位编码：每月天数 1 位）+ `_solar_to_lunar_pure()` 查表函数
- 农历年干支：`_lunar_year_gz()` 优先查 `YEAR_GZ_LICHUN`，超出表用 60 甲子周期推算（支持 2026 年初跨年场景 → 乙巳年）
- `calc_ganzhi()` 两个分支 + `build_paipan_data()` 最终 result 均暴露 `lunar` 字段
- 覆盖 2025 是为了让 2026-01-xx ~ 2026-02-16（正月初一前）的占卜日期能正确归到农历乙巳年年末

**修复 2 — 纯 Python 回退月空计算既有 bug**（顺手）
- `calc_ganzhi_pure()` 第 373 行原有 `TIANGAN_INDEX[month_gan]`，但 `month_gan` 变量从未定义（只有 `month_gan_idx`）→ pure 模式必崩
- 因实际用户基本都装了 sxtwl，此 bug 从未暴露；本次加 lunar 字段触发测试才发现
- 修复：新增 `month_gan = TIANGAN[month_gan_idx]` 变量赋值

**验证**（9 个测试用例 × 双轨 = 18 次对比）
- 主流程：2026-07-10 → 丙午年五月廿六 ✅
- 正月初一：2026-02-17 → 丙午年正月初一 ✅
- 跨年（立春前）：2026-02-16 → 乙巳年腊月廿九 ✅
- 立春日：2026-02-04 → 乙巳年腊月十七 ✅
- 闰五月：2028-07-01 → 戊申年闰五月初九 ✅
- 闰十一月：2033-12-22 → 癸丑年闰十一月初一 ✅
- 中段：2050-06-15 → 庚午年四月廿六 ✅
- 表末：2086-02-14 / 2086-12-31 ✅
- sxtwl 与 pure 两后端输出完全一致

**文档**
- `SKILL.md` 第零步强制输出新增「农历日期」项，明确标注「**直接读 JSON `lunar` 字段，禁止手算**」
- `SKILL.md` 检查点关键字段列表新增 `lunar`
- `SKILL.md` frontmatter version `1.5.7` → `1.5.8`

## v1.5.7 (2026-07-09)

### 改进 — 排盘正确性、可复现性、流程重构

**修复 1 — 六兽代码注释与实际逻辑矛盾**（`paipan.py` 第 829-831 行）
- 旧注释「自上而下排列：上爻(i=5)→初爻(i=0)」与代码 `(start + i) % 6` 实际的「自下而上」赋值方向矛盾，按注释"修正"会把六兽全排反
- 新注释明确写出日干→起始六兽映射 + 自下而上排列规则

**新增 — 摇卦 seed 可复现性**
- `paipan.py` 新增 `--seed N` 参数：指定后随机序列固定，同 seed 两次运行产出完全相同的 ygua
- JSON 顶层新增 `seed: int|null` 字段，便于事后复核"那天那个卦怎么排出来的"
- 占卜传统讲究"初筮告，再三渎"——seed 不改初筮随机性，但使卦象可追溯

**新增 — 特殊格局自动检测收敛到 `paipan.py`**
- 新增 `detect_patterns()` 函数 + 地支关系常量（六合/六冲/三会局对）
- JSON 新增 `patterns` 字段：`sanhui_ju` / `dizhi_liuhe` / `dizhi_liuchong` / `fuyin_positions` / `fanyin_positions` / `dufa` / `dujing` / `ben_liuchong_gua` / `ben_liuhe_gua` / `dong_count`
- SKILL.md 第三步从「AI 手动识别格局」改为「直接读 JSON patterns 字段」——单一权威，杜绝两套逻辑打架
- SKILL.md 全局铁律新增第 13 条「格局检测单一权威」

**新增 — `generate_report.py --validate` 子命令**
- 校验逻辑从 SKILL.md 的 inline Python heredoc 收敛到 `generate_report.py --validate`
- 检查 `meta`/`yao`/`steps` 顶层域 + `step1`~`step8` 齐全 + `step5` 四个六兽字段 + 每爻 `ben_yin_yang`
- SKILL.md 第九步用 `python generate_report.py -i xxx.json --validate` 替代 heredoc——跨平台引号转义风险消除，schema 演进只需改一处

**改进 — 第零步交互轮次合并**
- 旧流程：问事 → 确认意图 → 检测 sxtwl → 问 A/B 选择 → 执行（3-4 轮 round-trip）
- 新流程：问事 → 同时呈现「意图确认 + sxtwl A/B 选择」→ 执行（2 轮）
- sxtwl 未安装时 ⚠️ **显眼标注**「B 纯 Python 回退仅支持 2026-2086 年」
- 纯 Python 年份越界的报错信息补充「请安装 sxtwl」提示

**改进 — 版本号与文档一致性**
- SKILL.md frontmatter `version: "1.5.0"` → `"1.5.7"`（修复 1.5.1-1.5.6 对外不可见的 bug）
- 流程标题「解卦流程（九步法）」→「解卦流程（十步法：第零步排盘 + 第一至九步解卦）」
- README 版本节更新
- CHANGELOG v1.5.3/4/5 重排为严格倒序

**改进 — 桌面路径回退不污染主目录**
- 旧回退：Linux 无 Desktop 时 → `~/`（卦例目录散落 home 根）
- 新回退：→ `~/.liuyao/cases/`（自动创建，隔离存放）

**改进 — 第八步内联 16 条原则速查表**
- 核心契约从 `references/jie-gua-xiang-jie.md` 第一节内联到 SKILL.md 第八步
- 校验时无需额外加载即可对照，减少 Agent 凭记忆偷懒的可能

### 变更文件
- `scripts/paipan.py`：六兽注释修正；新增 `DIZHI_LIUHE_PAIRS` / `DIZHI_LIUCHONG_PAIRS` / `DIZHI_SANHUI_GROUPS` 常量；新增 `detect_patterns()` 函数；`build_paipan_data` 签名加 `seed` 参数；JSON 输出加 `patterns` 和 `seed` 字段；CLI 新增 `--seed` 参数；年份越界报错信息增强
- `scripts/generate_report.py`：新增 `validate_json()` 函数 + `--validate` 子命令；CLI 版本号 v1.4 → v1.5
- `SKILL.md`：frontmatter 版本号更新；角色定义与流程标题统一为十步法；全局铁律新增第 13 条；第零步交互合并 + sxtwl 警示 + seed 文档 + patterns 输出要求；第三步改为读 JSON patterns；强制触发条件表更新；第八步内联 16 条原则速查表；第九步用 `--validate` 替代 heredoc；桌面路径回退改为 `~/.liuyao/cases/`
- `README.md`：版本节更新为 v1.5.7

---

## v1.5.6 (2026-07-08)

### 改进 — 第零步文件管理重构 + 跨平台兼容

**问题**：排盘脚本 `paipan_result.json` 输出到用户主目录或当前工作目录，与桌面卦例目录分离。过程文件散落各处，缺乏统一管理。

**改进方案**：
- **全局铁律新增第12条**「文件统一存放」：所有过程文件必须统一存入桌面卦例目录，目录第零步创建、排盘后重命名
- **第零步流程重构**：意图确认后立即创建 `~/Desktop/YY.MM.DD-事件简称/` 临时目录 → 排盘 `-o` 输出到该目录 → 读取卦名后重命名为 `YY.MM.DD-本卦名-事件简称/`
- **第一步简化**：去掉「创建输出目录」块（已前移至第零步），改为确认目录存在
- **跨平台兼容**：桌面路径适配 Windows/macOS/Linux（含中文 locale 回退），重命名命令分平台说明（`mv` / `move`）
- **示例更新**：所有目录名示例统一使用「工作」场景

### 变更文件
- `SKILL.md`：全局铁律第12条、第零步步骤5-7重写、第一步简化、跨平台路径标注
- `.gitignore`：新增 `paipan_result.json` 忽略规则

---

## v1.5.5 (2026-07-01)

### 修复 — 第五步取象遗漏八卦/地支类象文件

**问题**：SKILL.md 将 bagua-leixiang.md（八卦万物类象）和 shier-dizhi-leixiang.md（十二地支类象）列在「按需加载」中。对于「失物」「寻人」「天气」等需要精确定位物品/人物类别的 intent，Agent 进入第五步取象时未加载这两个文件，凭记忆取象导致偏差。例如寻物卦中，离卦「中虚」（空腔容器）、辰土「盆坛」（罐形器皿）、午火「食物」三条类象均在文件中明列，但因未加载而遗漏，最终将空饮料罐误判为手机。

**修复方案**：
- SKILL.md 第五步强制加载规则新增：若 intent 为「失物」「寻人」「天气」等需精确定位物品/人物的类别 → 必须额外加载 references/bagua-leixiang.md 和 references/shier-dizhi-leixiang.md 全文，不得凭记忆取象
- 强制触发条件表新增一行：进入第五步且 intent 为失物/寻人/天气 → bagua-leixiang.md + shier-dizhi-leixiang.md（全文）

### 变更文件
- SKILL.md：第五步强制加载规则（第 350 行）+ 强制触发条件表（第 527 行）

---

## v1.5.4 (2026-07-01)

### 修复 — `ben_yin_yang` 字段缺失导致卦象面板显示错误

**问题**：HTML 报告中标题/信息条显示正确的卦名，但卦象面板（六爻符号 + 八卦符号）显示的是另一个卦。例如标题写「水山蹇」但面板画出「泽风大过」。

**根因**：`paipan.py` 输出的 JSON 中每爻缺少 `ben_yin_yang`（本卦阴阳属性）字段，`generate_report.py` 被迫从 `ygua`（原始六爻编码）推算。当 AI 在解卦流程中手工修改 JSON 数据时若忘记同步 `ygua`，推算结果就与 `ben_gua` 不一致，导致卦象面板分裂。

**修复方案**：
- `scripts/paipan.py`：`lines.append` 新增 `ben_yin_yang` 字段，基于 `gua[i]`（与 `guastr`/`ben_gua` 严格绑定）
- `scripts/generate_report.py`：扁平 JSON 适配器优先使用 paipan 直出的 `ben_yin_yang`，缺失时回退 `ygua` 推算（兼容旧 JSON）
- `scripts/generate_report.py`：`build_gua_panels` 新增 `ben_gua_name` 参数，面板卦名使用 JSON meta 的 `ben_gua`，与标题/信息条完全一致

### 修复 — 变卦非动爻缺少纳甲信息

**问题**：六爻详表中「变卦」列对非动爻显示的是本卦的六亲和地支（fallback），而非变卦自身的纳甲。例如风雷益→天地否，非动爻在变卦列应显示「子孙巳」，却错误显示本卦的「兄弟寅」。

**根因**：`paipan.py` 中 `bian_yao` 仅在 `is_dong` 为 `True` 时计算，非动爻的 `bian_yao` 为 `None`，导致 `generate_report.py` 用本卦数据作为 fallback。

**修复方案**：
- `scripts/paipan.py`：将条件从 `if is_dong and bian_gua_arr is not None` 改为 `if bian_gua_arr is not None`，只要存在变卦就为所有爻计算变卦纳甲（地支取自变卦结构，六亲按本卦宫五行重算）

### 变更文件
- `scripts/paipan.py`：新增 `ben_yin_yang` 字段（第 840 行）；bian_yao 计算扩展至全部爻（第 798 行）
- `scripts/generate_report.py`：扁平适配优先取直出字段（第 789-797 行）；面板卦名参数化（第 155、184、708 行）

---

## v1.5.3 (2026-06-25)

### 修复 — 终端编码导致排盘 JSON 乱码

**问题**：Windows PowerShell 中 `python paipan.py` 的 stdout 经过 Python（默认 GBK）→ PowerShell（UTF-8）双重编码转换后，中文全部变为乱码。此前 Agent 的做法是重新运行脚本（以 UTF-8 环境变量），但**重新运行会重新随机摇卦**，导致初筮之卦丢失——这是方法论错误。

**根因**：非终端问题，而是 Python 在 Windows 上未设 `PYTHONIOENCODING` 时默认走系统 locale（中文 GBK），与 PowerShell 的 UTF-8 编码打架。

**修复方案**（换终端不如绕过管道）：
- `scripts/paipan.py` 新增 `-o / --output` 参数：直接将 JSON 写入 UTF-8 文件，完全绕过 stdout 管道
- 文件模式下 stderr 输出简短确认信息，stdout 无中文
- SKILL.md 第零步第 5-6 条更新：**强制使用 `-o paipan_result.json` 文件模式**，然后用 `read_file` 工具读取（不经过 shell 管道）
- 新增 ⛔ 硬性规定：禁止依赖 stdout 传递中文 JSON

### 变更文件
- `scripts/paipan.py`：新增 `-o/--output` 参数（第 904 行、第 937-940 行、第 970-975 行）
- `SKILL.md`：第零步第 5-6 条重写，强制输出路径描述更新

---

## v1.5 (2026-06-08)

### 新增
- **自动排盘功能**：新增 `scripts/paipan.py` 自包含排盘脚本，合并 LiuYao 项目 `data.py` + `divination.py` 全部逻辑
- **第零步·自动排盘**：Skill 现在主动提问→分析意图/用神→三币摇卦→sxtwl 四柱计算→定卦→产出结构化 JSON，全程无需外部排盘系统
- **intent→用神速查表**：11 类意图（求财/官运/学业/感情/健康/孕产/出行/失物/词讼/天气/通用）的主用神与辅助用神一目了然
- **排盘脚本 CLI**：支持 `--subject`/`--intent`/`--yao`（手动六爻）/日期参数，三币随机或手动指定均可

### 变更
- 角色定义从「只解卦」升级为「排盘+解卦」
- 全局铁律新增第 0 条「排盘优先」
- 流程从九步扩展为十步（第零步+九步解卦）
- 输入格式说明更新：明确 JSON 结构由第零步产出
- README 新增「方式一：自动排盘」推荐用法

### 脚本细节
- `scripts/paipan.py`：826 行，零外部依赖（除可选 sxtwl），内嵌 64 卦 + 64 藏爻全部数据
- 三币摇卦概率：老阴(4)=1/8, 少阳(1)=3/8, 少阴(2)=3/8, 老阳(3)=1/8
- 输出 JSON 字段完整匹配 SKILL.md 输入格式：`date`/`ganzhi`/`month_branch`/`ri_chen`/`kong_wang`/`question`/`intent`/`ben_gua`/`bian_gua`/`lines[*]`（含 `fu_shen`/`bian_yao`/`liu_shou`），并带 `backend` 标记计算来源

### v1.5 后续补丁（同日）

**双轨干支计算**：
- sxtwl 改为可选依赖：已安装→`getYearGZ(False)` 立春分界；未安装→纯 Python 回退
- 纯 Python 路径：五虎遁（年干→月干）+ 五鼠遁（日干→时干）+ 日干支推算（2026-04-20 甲子基准）+ 旬空计算
- `YEAR_GZ_LICHUN` 嵌入 2026-2086 年干支 + 立春日期（用 `getJieQiByYear` 精确到日，立春分界）
- `_get_month_zhi()` 12 节气显式逐月判断，±1 天精度
- 年柱推算修复：`getYearGZ(True)`（春节）→ `getYearGZ(False)`（立春），与六爻传统一致

**第零步交互优化**：
- 意图确认后新增 sxtwl 检测步骤：已安装→直接排盘；未安装→询问用户选 A(安装) 或 B(纯 Python 回退)
- JSON 输出新增 `backend` 字段（`sxtwl` | `pure`），解卦时可据此判断时间精度

**子智能体验证**：
- 确认子智能体（DeepSeek Flash）不适用于本 skill：无 shell 执行能力、无法支撑解卦推理、压缩 reference 会丢失质量
- 结论：排盘+解卦全部由 V4 Pro 父进程单线程完成，不做子智能体分解

**旬空公式修复**：
- 原 LiuYao 项目 `divination.py` 旬空公式 bug：`cha += 10`（天干周期）→ 修正为 `cha += 12`（地支周期）
- 影响范围：所有 `日支序 - 日干序 < 0` 的日柱（癸日、壬日等），旬空全错
- 修复后与野鹤六爻排盘系统对照验证通过（癸丑日旬空寅卯）

**变卦六亲修复**：
- 从「变卦自身宫五行定六亲」改为「**本卦宫五行定变卦六亲**」（传统本卦宫法）
- 新增 `_GONG_WUXING`（八宫→五行）、`_liuqin_by_gong()` 函数
- 对照验证：兑宫归妹→变水解，初爻官鬼巳火 ×→ 妻财寅木（兑宫金克寅木=妻财，与野鹤六爻一致）

**神煞系统**：
- 新增 22 个神煞计算（`compute_shensha()`），按野鹤六爻 13 神煞标准对照验证
- 日干神煞（8个）：天乙贵人、禄神、羊刃、文昌、金舆、太极贵人、学堂、词馆
- 日支三合神煞（8个）：桃花、驿马、华盖、劫煞、灾煞、将星、亡神、谋星
- 月支神煞（4个）：天德、月德、天医（月支退一位）、天喜（按季节）
- 其他（2个）：天厨（日干）、干禄/日禄（别名）
- 贵人 bug 修复：庚日原误为丑未 → 修正为午寅（"庚辛逢马虎"）
- JSON 输出新增顶层 `shensha` 字段 + 每爻 `shensha` 数组（该爻地支命中的神煞名列表）

### v1.5 后续补丁 — HTML 报告 v1.4（同日）

**六爻盘面三栏+错综卦**：
- `generate_report.py` 升级至 v1.4（18.1 KB），内嵌 48 行八卦数据库 + 64 卦名字典
- **三栏盘面**：本卦 / 变卦 / 互卦 并排展示，各含卦名 + 六爻阴阳卦符（▅▅▅▅▅ / ▅▅  ▅▅）+ Unicode 八卦符号，无需纳甲信息
- **错卦/综卦按钮切换**：默认隐藏，点击按钮展开，面板仅展示卦名 + 卦符，无六兽干支
- 错卦 = 阴阳全反（兑为泽 → 艮为山），综卦 = 上下颠倒（兑为泽 → 巽为风）
- **变卦完整显示**：脚本自动推算变卦完整六爻（非动爻保持本卦阴阳，动爻翻转），非动爻补全 `bian_yin_yang` 字段
- CSS 新增：`.gua-panels` / `.gua-panel` / `.gua-toggle-bar` / `.gua-toggle-btn` 组件，`.fu-yang`（赤）/ `.fu-yin`（青）卦符染色，打印模式自动展开错/综面板

**维护**：
- `html-report-guide.md` 标注脚本版本 v1.4

### v1.5 后续补丁 — JSON 数据录入防错（2026-06-09）

**Bug 修复 — 静卦 JSON 数据两个易错点**：
- **`yao[].ben_yin_yang` 缺失 → 卦象面板全错**：脚本 `ben_lines_from_yao()` 以 `y.get("ben_yin_yang") == "阳"` 判读每爻阴阳。AI 构建 JSON 时漏填此字段，`get()` 返回 `None` ≠ `"阳"`，六爻全判为阴爻 → 卦名误算为「坤为地」、卦符全部虚线。水火既济（阳-阴-阳-阴-阳-阴）的实际卦象被覆盖。
- **`bian_gua: null` → 渲染为 `"None"`**：静卦场景下变卦名没有实际值。Python `dict.get("bian_gua", "—")` 在 key **存在但值为 None** 时不走默认值路径，直接返回 `None`，被 `format()` 转为字符串 `"None"` 显示在标题和信息条中。静卦应传 `"静卦"` 字符串或不传此 key。

**规则澄清**：
- `ben_yin_yang` 是 `yao` 数组的**事实必填字段**（schema 标注为可选但脚本现实依赖），无论静卦动卦都必须为每爻填写 `"阳"` / `"阴"`
- 静卦 JSON 的 `bian_gua` 应设为 `"静卦"` 而非 `null`，确保 HTML 标题和信息条正确渲染
- 动卦正常传变卦名字符串（如 `"山风蛊"`），不存在此问题

### v1.5 后续补丁 — 脚本增强四合一（2026-06-09）

**A. 特殊格局自动检测**：
- `generate_report.py` 新增 `detect_patterns()` 函数，自动检测三会局（含严格成局/虚势/之势三级判定）、六合、六冲、本卦六冲卦、伏吟、反吟
- HTML 报告新增「特殊格局」板块，不同格局以不同色标渲染

**D. 神煞展示**：
- `generate_report.py` 新增 `build_shensha_section()` 函数，渲染顶层全局神煞 + 每爻神煞
- HTML 报告新增「神煞」板块，paipan.py 输出的 22 个神煞全部可视化

**E. 排盘增强**：
- paipan.py 新增 `--manual` 标志（配合 `--yao` 使用，JSON 中标记 mode: manual）
- paipan.py 新增 `--from-json` 参数（从已有排盘 JSON 导入，跳过摇卦直接标准化输出）
- generate_report.py 新增扁平格式自动适配器（paipan.py 直出的 lines 数组 → 自动包装为 meta/yao/steps）

**B. 解卦流程强化**：
- SKILL.md 全局铁律新增第 11 条「格局不遗漏」
- 第三步输出模板扩展：特殊格局从一行扩展为六项逐条检测（三会局/六合/六冲/本卦六冲卦/伏吟反吟/独发独静）
- 静卦也必须逐项检测，禁止空白或敷衍

---

## v1.4 (2026-06-01)

### 流程改进
- **每步落地到本地 md**：全局执行铁律新增第7条，每步「📤 强制输出」同步写入 `{卦例目录}/步骤N-名称.md`
- **第一步自动创建卦例目录**：桌面路径 `~/Desktop/YY.MM.DD-本卦之变卦-事件/`，后续所有产物（md、JSON、HTML）均归入此目录
- **第九步从本地 md 读取**：构建 JSON 前先遍历 `{卦例目录}/` 下的步骤文件，以本地文件为唯一数据源，不再依赖对话记忆
- **第九步新增 schema 校验**：JSON 写入后、脚本调用前，强制运行 `assert` 检查 `meta`/`yao`/`steps` 三大域及 `step5` 的子字段完整性
- **第三步新增「伏神旁注」子步骤**：用神明现但其爻下 `fu_shen` 非空时，执行一句话级别的伏神旁注，第七步综合断语必须引用

### 算法深化
- **日辰合绊三层解读**：新增 `dong-bian-fa-ze.md` 第六节，定下「现象→时效→寓意」三层递进框架
- **三会局认定严格化**：`di-zhi-relations.md` 第三节重写，三方须均在动爻/变爻中方为严格成局；否则降级为「三会之势」
- **伏神旁注规则表**：新增 `dong-bian-fa-ze.md` 第十节

### 维护
- `dong-bian-fa-ze.md` 全部标题重编号（五→六→…→十）
- `jie-gua-xiang-jie.md` 两处交叉引用更新（第八节→第九节）

---

## v1.3 (2026-05-21)

### 算法修正
- **日月等权**：月建分值从 ±2 改为 ±1，与日辰权重相等（`jie-gua-xiang-jie.md` 第二节）
- 月破/日破统一为 ±2（结构破损，重于普通克 ±1），月日破对等
- **合的保护**：新增规则——月建与用神有六合/半合/三合关系时，克的负面被保护抵消（死 → 0）
- 综合判定四档条件重写为总分制
- 明确「六爻测的是当下的能量状态」，月日同为此时此地的气，不分轻重；应期层面仍保持月管周期、日管急事的区分

### 新增
- 六爻盘面**卦符列**：本卦/变卦阴阳爻可视化（▅▅▅▅▅ / ▅▅  ▅▅），动爻展示本→变
- **特殊标签徽章**：旬空[空]、月破[破]、暗动[暗]、入墓[墓] 在爻表中直观标记
- **生克链条可视化**：chain-box 块，关键箭头和回头克关系染色高亮
- **趋势推演 + 行动建议**双栏布局：将综合断语拆分为客观趋势（绿）和可执行建议（橙）
- 综合断语中做了白话翻译，术语替换为生活语言

### 变更
- `generate_report.py` 完整重写（12.2 KB → 18.5 KB），新增 5 个 CSS 组件
- `html-report-guide.md` JSON schema 扩展：yao 新增 `ben_yin_yang`/`bian_yin_yang`/`special_tags`/`fu_shen`；step7 新增 `trend`/`action_advice`
- 容器最大宽度从 780px → 820px 适配卦符列

---

## v1.2 (2026-05-21)

### 变更
- 第九步 HTML 报告改为 **Python 脚本生成**（`scripts/generate_report.py`），AI 只整理 JSON 数据，不在对话中输出完整 HTML，大幅节省 tokens
- `references/html-report-guide.md`：新增 JSON 数据 schema（第二节），原有 HTML 模板降级为回退方案（第三节）
- SKILL.md 第九步：操作流程从「手动拼 HTML」改为「整理 JSON → 写文件 → 调用脚本」

### 新增
- `scripts/generate_report.py`：零依赖独立脚本，内嵌 HTML 模板 + CSS，读取 JSON 输出报告

### 不影响
- 前八步规则不动，JSON schema 字段完全对应前八步输出

---

## v1.1 (2026-05-21)

### 新增
- 第九步「生成 HTML 报告」：校验通过后自动生成可交付的网页版卦象报告
- `references/html-report-guide.md`：HTML 报告生成规范（结构模板、CSS 样式、验证规则）
- `README.md`：面向用户的 skill 说明文档

### 变更
- 流程从八步法升级为九步法
- SKILL.md 全局铁律、流程概览表、强制触发条件表、按需加载表同步更新
- 输出风格新增"HTML 报告排版美观、可直接交付问卦人"

### 不影响
- 前八步（取用神→校验）的所有规则、门禁、强制输出格式、检查点原封不动
- 全部 reference 文件的加载逻辑未变

---

## v1.0 (2026-05)

### 首次发布
- 八步法解卦流程：审题取用神、判定用神旺衰、追踪动变路径、伏神分析、世应关系、六兽取象、应期推断、综合断语输出
- 第八步断后校验：步骤完整性 + 交叉验证 + 16 条原则映射
- 14 个 reference 文件覆盖解卦全知识域
- 12 类 intent 支持
- 半文半白输出风格
