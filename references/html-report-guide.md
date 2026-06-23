# HTML 报告生成指南

> 对应主 Skill 第九步：生成 HTML 可交付报告。第八步校验通过后执行。
> 
> **脚本版本**：v1.4 — 新增本卦/变卦/互卦三栏盘面 + 错卦/综卦切换按钮，48 行八卦数据库 + 64 卦名内嵌推算。

---

## 一、生成方式（脚本优先）

### 1.1 首选：Python 脚本生成（省 tokens）

第八步校验通过后，**不在对话中输出完整 HTML**。改为：

1. AI 将前八步输出整理为结构化 JSON（见第二节 schema）
2. JSON 写入临时文件 `liuyao-data.json`
3. 调用本地脚本：
   ```
   python <skill_dir>/scripts/generate_report.py --input liuyao-data.json --output liuyao-report.html
   ```
4. 脚本内嵌 HTML 模板 + CSS，自动渲染输出

### 1.2 回退：手动 HTML 生成

仅当本地 Python 不可用时，AI 按第三节的 CSS 模板手动拼接完整 HTML。此时会消耗较多 tokens，仅作紧急回退。

### 1.3 生成时机

- **第八步校验通过后**，立即执行第九步
- 若校验未通过，**禁止生成**，必须先修正

---

## 二、JSON 数据 Schema

> ⛔ 传给 Python 脚本的 JSON 必须包含以下三个顶层域。字段名固定，不得随意增删。

### 2.1 顶层结构

```json
{
  "meta": { ... },    // 卦象元数据
  "yao": [ ... ],     // 六爻数组（6→1 爻序无关，脚本自动排序）
  "steps": {          // 前八步分析输出
    "step1": { ... },
    "step2": { ... },
    "step3": { ... },
    "step4": { ... },
    "step5": { ... },
    "step6": { ... },
    "step7": { ... },
    "step8": { ... }
  }
}
```

### 2.2 `meta` 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | ✅ | 公历日期时间，如 "2026-05-21 13:54" |
| lunar | string | ✅ | 农历日期，如 "二〇二六年四月初五" |
| question | string | ✅ | 所问之事原文 |
| intent | string | ✅ | 意图类别 |
| ben_gua | string | ✅ | 本卦名，如 "巽为风" |
| bian_gua | string |   | 变卦名，如 "山风蛊" |
| yue_jian | string | ✅ | 月建地支，如 "巳" |
| ri_chen | string | ✅ | 日辰地支，如 "未" |
| kong_wang | string | ✅ | 旬空，如 "辰巳" |

### 2.3 `yao` 数组

每爻一个对象，字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pos | int | ✅ | 爻位 1-6 |
| liu_qin | string | ✅ | 六亲 |
| di_zhi | string | ✅ | 地支 |
| wu_xing | string | ✅ | 五行：金/木/水/火/土 |
| shi_ying | string\|null | | "世" / "应" / null |
| liu_shou | string | ✅ | 六兽 |
| dong | bool | ✅ | 是否发动 |
| bian_di_zhi | string\|null | | 变爻地支（无则 null） |
| bian_liu_qin | string\|null | | 变爻六亲（无则 null） |

| ben_yin_yang | string | | "阳" / "阴"，本卦该爻阴阳（显示卦符用，无则跳过） |
| bian_yin_yang | string\|null | | 变卦该爻阴阳（仅动爻，无则 null） |
| special_tags | string[] | | 特殊标记，如 ["旬空", "月破"]，无则 [] |
| fu_shen | object\|null | | 伏神 { liu_qin, di_zhi, wu_xing }，无则 null |

### 2.4 `steps` 各步字段

**step1**（审题取用神）：
| 字段 | 类型 | 说明 |
|------|------|------|
| intent | string | 意图类别 |
| zhu_yong_shen | string | 主用神六亲 |
| fu_zhu_yong_shen | string | 辅助用神 |
| appearance | string | "明现于X爻" / "不现于卦面" / "明现但旬空" |
| note | string\|null | 补充说明 |

**step2**（用神旺衰）：
| 字段 | 类型 | 说明 |
|------|------|------|
| yong_shen_location | string | "X爻 六亲 地支" |
| yue_jian | string | 月建关系 + 分值 |
| ri_chen | string | 日辰关系 + 分值 |
| special | string | 特殊状态 |
| verdict | string | 旺相有力/中和可用/休囚无力/空破无用 |

**step3**（动变路径）：
| 字段 | 类型 | 说明 |
|------|------|------|
| dong_count | int | 动爻数量，0=静卦 |
| dong_yao | array | 动爻列表（可为空） |
| dong_yao[].pos | int | 爻位 |
| dong_yao[].liu_qin | string | 六亲 |
| dong_yao[].di_zhi | string | 地支 |
| dong_yao[].bian_di_zhi | string | 变爻地支 |
| dong_yao[].bian_liu_qin | string | 变爻六亲 |
| dong_yao[].role | string | 原神/忌神/兄弟/泄气/财源 |
| dong_yao[].change_type | string | 回头克/回头生/化进/化退/化空/化破... |
| dong_yao[].effect | string | 对用神的影响描述 |
| chain | string | 关键生克链条 |
| pattern | string | 特殊格局 |

**step4**（世应关系）：
| 字段 | 类型 | 说明 |
|------|------|------|
| shi | string | "X爻 六亲 地支" |
| ying | string | "X爻 六亲 地支" |
| relation | string | "世X应" |
| yong_shi_ying | string | 用神与世应关系 |
| xing_hai | string | 刑害检测结果 |

**step5**（六兽取象）：
| 字段 | 类型 | 说明 |
|------|------|------|
| yong_shen_shou | string | 用神所临六兽 |
| yong_shen_shou_xiang | string | 吉凶象 + 含义 |
| dong_yao_shou | string | 动爻所临六兽 |
| dong_yao_shou_xiang | string | 吉凶象 + 含义 |

**step6**（应期推断）：
| 字段 | 类型 | 说明 |
|------|------|------|
| matched_rule | string | 命中法则 |
| window | string | 综合时间窗口 |
| unit | string | 日/月/年 |
| detail | string | 依据推算 |

**step7**（综合断语）：
| 字段 | 类型 | 说明 |
|------|------|------|
| qualitative | string | 一句话定性 |
| basis | string | 核心依据 |
| final_verdict | string | 综合断语全文 |
| trend | string | 趋势推演（客观描述未来走向，2-4句） |
| action_advice | string | 行动建议/避坑指南（面向用户的直接动作指令） |

**step8**（校验报告）：
| 字段 | 类型 | 说明 |
|------|------|------|
| integrity | string | 步骤完整性 |
| cross_check | string | 交叉验证结论 |
| principles | string | 16条原则检查 |
| final | string | 最终校验结论 |

---

## 三、回退方案：手动 HTML 模板

> ⛔ 仅当 Python 不可用时使用。结构必须遵循以下规范。**不得**增删板块，**不得**改变顺序。样式可微调但必须保持整体风格。

### 2.1 整体结构

```
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>六爻卦象报告 — [本卦名]变[变卦名]</title>
  <style>/* 内联 CSS，见第三节 */</style>
</head>
<body>
  <div class="container">
    <!-- 1. 标题区 -->
    <!-- 2. 卦象信息条 -->
    <!-- 3. 六爻盘面 -->
    <!-- 4. 定性总览 -->
    <!-- 5. 用神分析 -->
    <!-- 6. 动变解析 -->
    <!-- 7. 世应关系 -->
    <!-- 8. 六兽提点 -->
    <!-- 9. 应期推断 -->
    <!-- 10. 综合断语 -->
    <!-- 11. 校验印记 -->
  </div>
</body>
</html>
```

### 2.2 各板块内容规范

**板块 1 — 标题区**：
```html
<header class="report-header">
  <h1>六爻卦象报告</h1>
  <p class="subtitle">本卦《[本卦名]》　变卦《[变卦名]》</p>
  <p class="question">所问：[question]</p>
  <p class="date">占卦时间：[公历日期时间]　农历[农历日期]</p>
</header>
```

**板块 2 — 卦象信息条**：
```html
<div class="info-bar">
  <div class="info-item"><span class="label">本卦</span><span class="value">[本卦名]</span></div>
  <div class="info-item"><span class="label">变卦</span><span class="value">[变卦名]</span></div>
  <div class="info-item"><span class="label">月建</span><span class="value">[月建地支]</span></div>
  <div class="info-item"><span class="label">日辰</span><span class="value">[日辰地支]</span></div>
  <div class="info-item"><span class="label">旬空</span><span class="value">[旬空地支]</span></div>
</div>
```

**板块 3 — 六爻盘面**：

用表格展示六爻，从六爻（上）到初爻（下）排列。动爻用 `class="dong"` 标记，变爻显示在旁边。

```html
<h2>六爻盘面</h2>
<table class="yao-table">
  <thead>
    <tr><th>爻位</th><th>六亲</th><th>地支</th><th>五行</th><th>世应</th><th>六兽</th><th>动变</th></tr>
  </thead>
  <tbody>
    <!-- 六爻 → 初爻，从上到下 -->
    <tr class="[dong? 'dong' : '']">
      <td>[X爻]</td>
      <td>[六亲]</td>
      <td>[地支]</td>
      <td class="wx-[五行]">[五行]</td>
      <td>[世/应/—]</td>
      <td>[六兽]</td>
      <td>[发动显示：如 '○ → 父母子水' / 静爻显示 '—']</td>
    </tr>
    <!-- ... -->
  </tbody>
</table>
```

**板块 4 — 定性总览**：
```html
<h2>定性总览</h2>
<div class="verdict-box [吉/凶/平]">
  <p class="verdict">[第七步开头的一句话定性]</p>
  <p class="verdict-detail">[核心依据，1-2句]</p>
</div>
```

**板块 5 — 用神分析**：
```html
<h2>用神分析</h2>
<p><strong>主用神：</strong>[六亲][地支]，在[爻位]爻，五行属[五行]</p>
<p><strong>月建：</strong>[旺/相/死/休/囚]（[分值]）　<strong>日辰：</strong>[生/克/比和/冲]（[分值]）</p>
<p><strong>特殊状态：</strong>[旬空/月破/入墓/无]</p>
<p><strong>综合判定：</strong><span class="wangshuai-[旺相有力/中和可用/休囚无力/空破无用]">[旺衰结论]</span></p>
<p><strong>辅助用神：</strong>[六亲][地支]，[补充说明]</p>
```

**板块 6 — 动变解析**：
```html
<h2>动变解析</h2>
<!-- 静卦时显示"本卦为静卦，无动变" -->
<div class="dong-yao-card">
  <h3>[X爻] [六亲][地支] 发动</h3>
  <p><strong>化为：</strong>[六亲][地支]</p>
  <p><strong>角色：</strong>[原神/忌神/兄弟/泄气/财源]</p>
  <p><strong>变化性质：</strong>[回头生/回头克/化进/化退/化空/化破/化墓/化绝...]</p>
  <p><strong>影响：</strong>[对用神的影响，2-3句]</p>
</div>
<p><strong>关键生克链条：</strong>[链路]</p>
<p><strong>特殊格局：</strong>[六冲/六合/归魂/独发...]</p>
```

**板块 7 — 世应关系**：
```html
<h2>世应关系</h2>
<p><strong>世爻：</strong>[爻位] [六亲][地支]（[六兽]，旬空：[是/否]）</p>
<p><strong>应爻：</strong>[爻位] [六亲][地支]（[六兽]，旬空：[是/否]）</p>
<p><strong>关系：</strong>世[X]应 → [含义]</p>
<p><strong>用神与世应：</strong>[持世/临应/生世/克世...]</p>
```

**板块 8 — 六兽提点**：
```html
<h2>六兽提点</h2>
<ul>
  <li>用神临[六兽]：[吉象/凶象]，[含义]</li>
  <li>动爻临[六兽]：[吉象/凶象]，[含义]</li>
</ul>
<p class="note">六兽不单独断吉凶，仅供修饰参考。</p>
```

**板块 9 — 应期推断**：
```html
<h2>应期推断</h2>
<p><strong>匹配法则：</strong>[第X条法则]</p>
<p><strong>综合窗口：</strong>[时间窗口]</p>
<p><strong>依据：</strong>[法则 + 地支推算]</p>
```

**板块 10 — 综合断语**：
```html
<h2>综合断语</h2>
<div class="final-verdict">
  [第七步的综合断语全文，保留分段]
</div>
```

**板块 11 — 校验印记**：
```html
<footer class="report-footer">
  <p class="verify-stamp">✅ 八步校验通过</p>
  <p class="generate-time">报告生成时间：[当前时间]</p>
  <p class="disclaimer">此报告由 AI 六爻解卦 Skill 自动生成，供参考之用。六爻为传统决策辅助工具，不替代理性判断。</p>
</footer>
```

---

## 四、CSS 样式规范（回退方案用）

> ⛔ 以下 CSS 为**最低要求**。可在此基础上微调颜色、间距，但必须保持以下特征：
> - 中国传统风格色调（以赭石、墨色、宣纸色为主）
> - 响应式布局（max-width 780px 居中）
> - 打印友好（@media print）
> - 动爻行高亮

### 3.1 基准样式

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", "宋体", serif;
  background: #f5f0e8;
  color: #3a3226;
  line-height: 1.8;
}
.container {
  max-width: 780px;
  margin: 0 auto;
  padding: 40px 24px 60px;
}

/* 标题区 */
.report-header { text-align: center; padding: 32px 0 24px; border-bottom: 2px solid #8b7355; margin-bottom: 32px; }
.report-header h1 { font-size: 28px; color: #5c3d2e; letter-spacing: 4px; margin-bottom: 8px; }
.report-header .subtitle { font-size: 18px; color: #8b7355; }
.report-header .question { font-size: 15px; color: #6b5a4e; margin-top: 12px; }
.report-header .date { font-size: 13px; color: #9e8b7a; margin-top: 4px; }

/* 信息条 */
.info-bar { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 32px; }
.info-item { background: #fff; border: 1px solid #d4c5b2; border-radius: 6px; padding: 8px 16px; }
.info-item .label { font-size: 12px; color: #9e8b7a; display: block; }
.info-item .value { font-size: 16px; color: #5c3d2e; font-weight: bold; }

/* 爻表 */
.yao-table { width: 100%; border-collapse: collapse; margin-bottom: 32px; font-size: 15px; }
.yao-table th { background: #5c3d2e; color: #f5f0e8; padding: 10px 8px; }
.yao-table td { padding: 10px 8px; text-align: center; border-bottom: 1px solid #d4c5b2; }
.yao-table tr.dong { background: #fdf2e0; font-weight: bold; }
.yao-table tr.dong td:first-child::before { content: "⚡ "; }

/* 定性框 */
.verdict-box { padding: 20px; border-radius: 8px; margin-bottom: 32px; text-align: center; }
.verdict-box.吉 { background: #e8f5e9; border: 1px solid #81c784; }
.verdict-box.凶 { background: #fbe9e7; border: 1px solid #e57373; }
.verdict-box.平 { background: #fff8e1; border: 1px solid #ffb74d; }
.verdict { font-size: 20px; font-weight: bold; }

/* 通用标题 */
h2 { font-size: 20px; color: #5c3d2e; border-left: 4px solid #8b7355; padding-left: 12px; margin: 32px 0 16px; }
h3 { font-size: 16px; color: #6b5a4e; margin: 16px 0 8px; }

/* 动爻卡片 */
.dong-yao-card { background: #fdf2e0; border-left: 4px solid #c49a3c; padding: 16px; margin-bottom: 12px; border-radius: 0 6px 6px 0; }

/* 综合断语 */
.final-verdict { background: #fff; border: 1px solid #d4c5b2; border-radius: 8px; padding: 24px; font-size: 15px; line-height: 2; }

/* 页脚 */
.report-footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid #d4c5b2; text-align: center; font-size: 12px; color: #9e8b7a; }
.verify-stamp { font-size: 14px; color: #5c8a5c; margin-bottom: 8px; }
.disclaimer { margin-top: 12px; font-style: italic; }

/* 打印样式 */
@media print {
  body { background: #fff; }
  .container { max-width: 100%; padding: 20px; }
  .yao-table th { background: #5c3d2e !important; color: #fff !important; -webkit-print-color-adjust: exact; }
  .dong-yao-card { -webkit-print-color-adjust: exact; }
}
```

---

## 五、生成后验证

HTML 报告生成后，必须执行以下验证：

1. **结构完整性**：检查 11 个板块是否全部存在
2. **占位符检查**：确认所有 `[ ]` 已被替换为实际内容
3. **动爻标记**：确认动爻行有 `class="dong"`
4. **文件可读性**：确认 HTML 文件成功写入磁盘

### 📤 强制输出

```
【第九步·输出】
- HTML 报告已生成：[文件路径]
- 文件大小：[约X KB]
- 板块数量：11/11
- 动爻标记：[X] 处
- 校验状态：✅ 通过 / ⚠️ 警告
```
