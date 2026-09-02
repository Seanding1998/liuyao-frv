# 🔮 六爻解卦分析 Skill

> **专业纳甲筮法排盘 · 自动解卦 · 可交付 HTML 卦象报告**
>
> 问事不求人。把问题丢给它 —— 自动摇卦、十步推演、逐层断语，一套可追溯、不敷衍的六爻解卦工作流。
>
> `frv v2.0.1` · 个人免费 · 商业授权

---

<div align="center">

**如果这个工具帮到了你，欢迎打赏一杯咖啡 ☕**

| 支付宝 | 微信支付 | Touch 'n Go |
| :---: | :---: | :---: |
| <img src="docs/alipay.jpg" width="204" alt="支付宝收款码"> | <img src="docs/wechat.jpg" width="204" alt="微信支付收款码"> | <img src="docs/touch-n-go.jpg" width="204" alt="Touch 'n Go 收款码"> |

</div>

---

## ✨ 它是什么

一个装进 **Agent** 的水晶球：把传统六爻纳甲筮法变成一套**可复现、可交付**的决策辅助流程。从「你随口问一个问题」到「一份排版精美的 HTML 卦象报告」，全程自动。

它和你平时看的那种「看完就忘」的彩票式解卦不一样：

- **强执行规则** — 每一步有门禁、有强制输出、有检查点，不跳步、不合并、不改轻。
- **可追溯** — 每一条结论都能回溯到具体的分析步骤，而不是「感觉如此」。
- **断后校验** — 自动交叉验证旺衰 / 动变 / 世应 / 应期，逐条比对原则。
- **能交付** — 产出内联 CSS 的 HTML 报告，直接用浏览器打开、打印或分享。

## 🚀 快速开始

### 安装

把 Skill 装进你的 Agent 环境：

```bash
git clone https://github.com/Seanding1998/liuyao-frv.git ~/.codex/skills/liuyao-divination
```

### 依赖

- **Python 3.8+**
- 推荐安装 `sxtwl` 以获得精确节气计算（支持全年份）：

```bash
pip install sxtwl
```

> 未安装 `sxtwl` 时，脚本自动回退到纯 Python 四柱计算（仅支持 2026–2086 年，节气边界 ±1 天）。

## 🎯 怎么用

### 方式一：自动摇卦（什么都不用准备）⭐

直接说话就行，Skill 自动激活：

> 「我戒指找不到了，能帮我看看在哪吗」

Agent 会确认意图，然后自动**三币摇卦 → 排四柱 → 十步解卦 → 生成 HTML 报告**。

### 方式二：手动传入卦象（一句话排盘）

你手里已经有卦了，不需要重新摇。把**卦名 + 动爻位置 + 日期**混在问题里一句话丢进去即可：

> 「火地晋，下个月工作升职调动有戏吗？动爻是三爻，2026年7月18日」

更复杂的也照样一句话：

> 「水山蹇变小过卦，问这次出差谈的合同能不能签下来，动爻二爻和五爻」

> 「雷水解，静卦无动爻，看看我身体恢复得怎么样」

> 「天地否，动爻初爻变四爻，帮我断一下这个官司前景」

不用填表、不用记命令行参数 —— 像聊天一样说出来就行。

## 📋 输出内容

严格按十步流程依次输出，每一步有强制输出格式：

| 步骤 | 名称 | 说明 |
| --- | --- | --- |
| 0 | 自动排盘 | 提问 → 意图分析 → 三币摇卦 → 四柱排盘 → JSON 卦象 |
| 1 | 审题取用神 | 确定分析核心（官鬼 / 妻财 / 父母…） |
| 2 | 判定用神旺衰 | 月建、日辰生克综合判定 |
| 3 | 追踪动变路径 | 动爻来龙去脉，特殊格局检测 |
| 3.5 | 伏神分析 | 用神不现时的飞伏生克（条件触发） |
| 4 | 分析世应关系 | 人我格局 |
| 5 | 六神兽取象 | 神煞修饰 |
| 6 | 应期推断 | 时间窗口推算 |
| 7 | 综合断语 | 定性总结 + 建议 |
| 8 | 断后校验 | 交叉验证 + 16 条原则逐条检查 |
| 9 | 生成 HTML 报告 | 可交付的网页版卦象报告 |

HTML 报告使用内联 CSS，无需外部依赖。报告内含 **「旺相休囚死」** 板块（v1.8.0）：按能量从高到低展示五行之气在当前月令下的流转（如申月 → 金旺 水相 土休 火囚 木死）。

## 🧩 项目结构

```
├── SKILL.md               # Claude Code Skill 定义（十步解卦流程）
├── README.md              # 本文件
├── CHANGELOG.md           # 版本历史
├── LICENSE                # 个人免费·商业授权
├── scripts/
│   ├── paipan.py          # 三币摇卦 + sxtwl 四柱 + 排盘
│   ├── generate_report.py # HTML 报告生成器
│   └── lunar_data.py      # 农历数据查找表（2026–2086）
└── references/
    ├── jie-gua-xiang-jie.md     # 解卦执行手册（核心）
    ├── liuqin-liushen-leixiang.md # 六亲六神兽精细类象
    ├── html-report-guide.md     # HTML 报告生成指南
    ├── dong-bian-fa-ze.md       # 动变法则
    ├── di-zhi-relations.md      # 地支关系（合冲刑害）
    ├── bagua-leixiang.md        # 八卦万物类象
    ├── shier-dizhi-leixiang.md  # 十二地支类象
    ├── 64-gua.md                # 六十四卦八宫归属
    ├── wuxing-shengke.md        # 五行生克
    ├── te-shu-ge-ju.md          # 特殊格局
    ├── fushi-riyue-guashen.md   # 伏神日月卦身
    └── yingqi-faze.md           # 应期法则
```

## 🎨 特色

- **自动排盘** — 三币摇卦法，sxtwl 双轨四柱，定卦 / 世应 / 六神兽 / 六亲 / 伏神全自动
- **严谨不敷衍** — 每一步有门禁、有强制输出、有检查点，不跳步、不合并
- **可追溯** — 每条结论可回溯到具体分析步骤
- **断后校验** — 第八步自动交叉验证，旺衰 / 动变 / 世应 / 应期逐条比对
- **可交付** — HTML 报告排版美观，适合正式场景交付
- **五行之气可视化** — 爻象详表下方「旺相休囚死」板块，一眼看清当月五行能量强弱流转

## ⚠️ 限制

- **非迷信工具**：六爻是一种传统决策辅助工具，不替代理性判断
- **与全功能版差异**：本分支聚焦核心解卦流程与通用场景断语；全功能版额外提供孕产、寻人、阳宅等更多意图场景、神煞联合取象、太岁三层旺衰与全量类象库 —— 详见 [全功能版介绍](https://github.com/Seanding1998/liuyao)

## 🛠 维护者速览

本 Skill 的核心设计是 **「强执行规则 + 强防错闭环」**。维护时不要把规则改轻、改少、改漏、改丢；新增说明、索引和校验可以提升可读性，但不能替代原有门禁。

| 修改目标 | 优先修改位置 | 必须同步检查 |
|----------|--------------|--------------|
| 流程门禁、强制输出、十步法 | `SKILL.md` | `references/rule-index.md`、第八步审查 prompt、第九步准入 |
| 解卦原则与每步细则 | `references/jie-gua-xiang-jie.md` | `SKILL.md` 对应步骤、审查映射表 |
| reference 加载路由 | `SKILL.md` 文末「参考资料加载规则」 | 步骤内执行复述、第零步路由表、第八步 D 项 |
| HTML schema 与报告展示 | `references/html-report-guide.md`、`scripts/generate_report.py` | `generate_report.py --validate`、README 当前版本说明 |
| 格局检测 | `scripts/paipan.py` | `scripts/test_gua_patterns.py`、铁律 11/13、相关 references |
| 应期分层校验 | `references/yingqi-faze.md`、`scripts/generate_report.py` | `SKILL.md` 第六步、HTML guide 的 `step6.layers` schema |
| 版本发布 | `SKILL.md` frontmatter | README、CHANGELOG、HTML guide、脚本 CLI、`scripts/check_release_consistency.py` |

规则编号检索见 [references/rule-index.md](./references/rule-index.md)。`TL-*` 表示 SKILL.md 铁律，`PR-*` 表示 `jie-gua-xiang-jie.md` 的 16 条核心原则。

### 发布前检查清单

在 Windows PowerShell 下运行中文输出相关命令时，先设置 UTF-8，避免 GBK 控制台把脚本误判为异常：

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts\test_gua_patterns.py
python scripts\paipan.py --help
python scripts\generate_report.py --help
python scripts\check_release_consistency.py
```

发布前至少确认：

- [ ] `SKILL.md metadata.version` 是唯一权威版本号。
- [ ] README 当前版本、CHANGELOG 顶部版本、HTML guide 脚本版本、`generate_report.py` 文件头和 CLI description 已同步。
- [ ] 修改格局检测后已运行 `scripts/test_gua_patterns.py`。
- [ ] 修改 HTML schema 后已运行 `generate_report.py --validate` 的正反例。
- [ ] 修改加载规则后已同步文末权威表、步骤内执行复述、第八步 D 项审查标准。
- [ ] 修改审查流程后已同步 `SKILL.md` 第八步、`jie-gua-xiang-jie.md` 第八节和 README 当前说明。

## 📅 当前版本

### v2.0.x（当前）

- **v2.0.1** — 维护界面与发布治理升级：保留全部硬规则强度，新增设计意图导读、铁律分组、关键铁律防错目的、规则编号索引、维护者速览、发布前检查清单和版本一致性检查脚本。

### frv v1.8.x（当前）

- **v1.8.4** — 结构化应期分层：第六步强制加载 `yingqi-faze.md`；新增 `step6.layers.main/auxiliary/risk`，HTML 与 `--validate` 均按三层结构检查。
- **v1.8.3** — 应期分层能力泛化：按本分支已支持 intent 检查主应期、辅助节点、风险窗口是否覆盖关键角色。
- **v1.8.2** — 特殊格局重点展示与应期排序修正：HTML 特殊格局与全文附录支持 `**重点**` 加粗渲染；应期规则新增主应期、辅助节点、风险窗口三层排序。
- **v1.8.1** — 特殊格局深断改造：六合、六冲、三合、三会、伏吟、反吟、六合卦、六冲卦、游魂、归魂统一十项深断模板；HTML 特殊格局板块优先展示第三步深断。
- **v1.8.0** — HTML 报告爻象详表下方新增「旺相休囚死」能量展示板块。

> 注：早期审查机制以历史 changelog 为准；当前执行机制以 `SKILL.md` 第八步为准。

## 📄 许可

个人免费 · 商业授权 — 详见 [LICENSE](./LICENSE)
