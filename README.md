# 六爻解卦分析 Skill

> 专业六爻纳甲筮法排盘 + 解卦工具。自动摇卦排盘 → 十步法逐层分析 → 可交付的 HTML 卦象报告。
>
> 开源免费版 v1.5.10 · MIT License

## 快速开始

### 安装

将此 Skill 安装到你的 Claude Code 环境中：

```bash
# 克隆仓库
git clone https://github.com/Seanding1998/liuyao.git ~/.codex/skills/liuyao-divination
```

### 依赖

- Python 3.8+
- 推荐安装 `sxtwl` 以获得精确节气计算（支持全年份）：

```bash
pip install sxtwl
```

> 未安装 `sxtwl` 时，脚本自动回退到纯 Python 四柱计算（仅支持 2026-2086 年，节气边界 ±1 天）。

### 使用

直接告诉 Agent 你想占卜的事，Skill 自动完成全流程：

```
用户: 我手机找不到了，帮我看看在哪
Agent: 分析你的问题，意图类别「失物」，主用神「妻财」。确认无误请回复「是」。
用户: 是
Agent: [三币摇卦 → 排盘 → 十步解卦 → HTML 报告]
```

## 输出内容

严格按十步流程依次输出，每一步有强制输出格式：

| 步骤 | 名称 | 说明 |
| --- | --- | --- |
| 0 | 自动排盘 | 提问→意图分析→三币摇卦→四柱排盘→JSON 卦象 |
| 1 | 审题取用神 | 确定分析核心（官鬼/妻财/父母…） |
| 2 | 判定用神旺衰 | 月建、日辰生克综合判定 |
| 3 | 追踪动变路径 | 动爻来龙去脉，特殊格局检测 |
| 3.5 | 伏神分析 | 用神不现时的飞伏生克（条件触发） |
| 4 | 分析世应关系 | 人我格局 |
| 5 | 六兽取象 | 神煞修饰 |
| 6 | 应期推断 | 时间窗口推算 |
| 7 | 综合断语 | 定性总结 + 建议 |
| 8 | 断后校验 | 交叉验证 + 16条原则逐条检查 |
| 9 | 生成 HTML 报告 | 可交付的网页版卦象报告 |

HTML 报告使用内联 CSS，无需外部依赖，可直接在浏览器打开、打印或分享。

## 项目结构

```
├── SKILL.md               # Claude Code Skill 定义（十步解卦流程）
├── README.md              # 本文件
├── CHANGELOG.md           # 版本历史
├── LICENSE                # MIT
├── scripts/
│   ├── paipan.py          # 三币摇卦 + sxtwl 四柱 + 排盘
│   ├── generate_report.py # HTML 报告生成器
│   └── lunar_data.py      # 农历数据查找表 (2026-2086)
└── references/
    ├── jie-gua-xiang-jie.md   # 解卦执行手册（核心）
    ├── html-report-guide.md   # HTML 报告生成指南
    ├── dong-bian-fa-ze.md     # 动变法则
    ├── di-zhi-relations.md    # 地支关系（合冲刑害）
    ├── bagua-leixiang.md      # 八卦万物类象
    ├── shier-dizhi-leixiang.md # 十二地支类象
    ├── 64-gua.md              # 六十四卦八宫归属
    ├── wuxing-shengke.md      # 五行生克
    ├── te-shu-ge-ju.md        # 特殊格局
    ├── fushi-riyue-guashen.md # 伏神日月卦身
    └── yingqi-faze.md         # 应期法则
```

## 特色

- **自动排盘**：三币摇卦法，sxtwl 双轨四柱，定卦/世应/六神/六亲/伏神全自动
- **严谨不敷衍**：每一步有门禁、有强制输出、有检查点，不跳步、不合并
- **可追溯**：每条结论可回溯到具体分析步骤
- **断后校验**：第八步自动交叉验证，旺衰/动变/世应/应期逐条比对
- **可交付**：HTML 报告排版美观，适合正式场景交付

## 限制

- **非迷信工具**：六爻是一种传统决策辅助工具，不替代理性判断
- **免费版场景**：当前版本主要支持「寻物」等少数意图场景，完整 intent 路由在付费版中提供

## 许可

MIT License — 详见 [LICENSE](./LICENSE)
