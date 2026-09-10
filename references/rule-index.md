# 规则编号注册表

本文件是维护索引，不替代任何执行规则。`SKILL.md` 仍是十步流程、铁律、准入、强制输出和加载规则的源点；`references/jie-gua-xiang-jie.md` 仍是 16 条核心原则与解卦细则的源点。

## 编号约定

- `TL-*`：全局执行铁律，定义源为 `SKILL.md`。
- `PR-*`：16 条核心原则，定义源为 `references/jie-gua-xiang-jie.md`。
- 修改规则时先改定义源，再同步本索引、README 维护说明、CHANGELOG 当前维护重点，以及相关脚本测试或校验。

## 铁律索引

| ID | 名称 | 类型 | 定义源 | 相关文件 | 防错目的 | 维护备注 |
|----|------|------|--------|----------|----------|----------|
| TL-01 | 排盘优先 | 运行协议 | `SKILL.md` 全局执行铁律 | `scripts/paipan.py` | 防止未生成结构化卦象就凭题意直接断卦 | 不得跳过第零步；已有 JSON 时也要确认字段完整 |
| TL-02 | 顺序不可逆 | 运行协议 | `SKILL.md` 全局执行铁律 | `references/jie-gua-xiang-jie.md` | 防止先下结论再倒填步骤 | 十步法顺序是交付骨架，不改成自由分析 |
| TL-03 | 输出不可省 | 运行协议 | `SKILL.md` 全局执行铁律 | `references/html-report-guide.md` | 防止用“已分析”替代可审查步骤内容 | 第九步依赖各步骤正文组装报告 |
| TL-04 | 门禁不可破 | 运行协议 | `SKILL.md` 全局执行铁律 | `references/jie-gua-xiang-jie.md` | 防止准入条件未满足时继续推进 | 修改步骤准入时同步检查点和审查 prompt |
| TL-05 | 引用不可跳 | 数据权威 | `SKILL.md` 全局执行铁律 | `references/*` | 防止 Agent 凭记忆替代本仓库 reference | 新增 reference 后要补加载规则和自检清单要求 |
| TL-06 | 审查不可代 | 审查协议 | `SKILL.md` 全局执行铁律、第八步 | `references/jie-gua-xiang-jie.md` 第八节 | 防止主流程既当执行者又当裁判，自查放水或掩盖漏判 | 保持独立审查智能体；当前机制为单轮审查制 |
| TL-07 | 渐进加载 | 数据权威 | `SKILL.md` 全局执行铁律 | `SKILL.md` 参考资料加载规则 | 防止一次性泛读或该读时未读，导致上下文和判断错位 | 文末加载规则是源点，步骤内为执行复述 |
| TL-08 | 落地不可略 | 运行协议 | `SKILL.md` 全局执行铁律 | `references/html-report-guide.md`、`scripts/generate_report.py` | 防止对话记忆丢失、步骤被压缩、HTML 空报告 | 第九步必须从步骤 md 文件读取并组装 `md_full` |
| TL-09 | 爻位用汉字 | 表达规范 | `SKILL.md` 全局执行铁律 | `scripts/generate_report.py` | 防止报告里“1爻/2爻”破坏术语统一 | JSON `pos` 与代码可用数字，用户文本必须用汉字 |
| TL-10 | 旺衰内量化外自然 | 判断完整性 | `SKILL.md` 全局执行铁律 | `references/wuxing-shengke.md` | 防止最终报告出现内部打分记号，削弱可读性 | 内部可量化，交付文本必须转自然语言 |
| TL-11 | 格局不遗漏 | 判断完整性 | `SKILL.md` 全局执行铁律、第三步、第七步 | `references/di-zhi-relations.md`、`references/te-shu-ge-ju.md`、`scripts/generate_report.py` | 防止特殊格局只列不析、浅套话或漏入综合断语 | 修改格局模板时同步第三步、第七步、第八步和 validate |
| TL-12 | 文件统一存放 | 运行协议 | `SKILL.md` 全局执行铁律、第零步 | `references/html-report-guide.md` | 防止过程文件散落，审查智能体和第九步找不到证据 | 路径策略变更要保持桌面优先与无桌面回退 |
| TL-13 | 格局检测单一权威 | 数据权威 | `SKILL.md` 全局执行铁律、第三步 | `scripts/paipan.py`、`scripts/test_gua_patterns.py` | 防止手动误判六冲、六合、游魂、归魂等格局 | `patterns` 字段是权威；新增格局必须补测试 |
| TL-14 | 路由表优先 | 数据权威 | `SKILL.md` 全局执行铁律、第零步附 | `references/yingqi-faze.md`、`references/bagua-leixiang.md`、`references/shier-dizhi-leixiang.md`、`references/liuqin-liushen-leixiang.md`、各类象 reference | 防止场景类知识到第七步才补读，前面判断已走偏 | 跨 intent 取并集；加载条件源点仍在文末表；不得指向本分支不存在的类象库 |
| TL-15 | 每步自检门禁 | 数据权威 | `SKILL.md` 全局执行铁律、各步输出块 | `references/*`、第八步审查 D 项 | 防止纸面合规、reference 假读、只列文件名不摘关键句 | 清单必须含关键句摘录，未摘录等同步骤无效 |
| TL-16 | 流程抗疲劳 | 运行协议 | `SKILL.md` 全局执行铁律 | `SKILL.md` 第零步附路由表 | 防止同会话第二卦以后因熟悉感跳过预读和门禁 | 不设强校验，但不得删除醒脑约束 |
| TL-17 | 立币作废 | 运行协议 | `SKILL.md` 全局执行铁律、第零步 | `scripts/paipan.py`、`scripts/test_gua_patterns.py` | 防止忽略退出码 3、把作废卦当正常卦解，或当场重摇抹掉立币征兆 | 每枚硬币落地同源同抽定正/反/立；概率口径、退出码 3、作废话术变更需同步脚本、测试与第零步 |

## 核心原则索引

| ID | 名称 | 类型 | 定义源 | 相关步骤 | 防错目的 | 维护备注 |
|----|------|------|--------|----------|----------|----------|
| PR-01 | 用神为纲 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第一步、第八步 | 防止脱离所问之事泛断 | intent 映射变更要同步第一步 |
| PR-02 | 旺衰为本 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第二步、第八步 | 防止只看动爻、不先定用神气势 | 旺衰体系变更要同步第二步 |
| PR-03 | 动爻是故事的导演 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第三步 | 防止有动不看、静卦乱加动变 | 动变规则变更要同步 `dong-bian-fa-ze.md` |
| PR-04 | 日月如天 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第二步、第六步 | 防止忽略月建日辰的高权重 | 日辰暗动/月破规则不可混同月建 |
| PR-05 | 卦不妄成 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第一步、第五步 | 防止把动爻、旬空、月破当无意义噪声 | 取象和旺衰都要保留证据链 |
| PR-06 | 实事求是 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第七步、第九步 | 防止一味讨好或恐吓式断语 | 凶中指救，吉中防暗 |
| PR-07 | 不知为不知 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第七步、第八步 | 防止罕见格局编造规则 | 罕见项可说明不确定，不得硬编 |
| PR-08 | 伏神必查 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第3.5步 | 防止用神不现时直接断无 | 与 `fushi-riyue-guashen.md` 保持同步 |
| PR-09 | 冲合分虚实 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第三步、第四步、第六步 | 防止把冲、合、暗动、日破混断 | 与 `di-zhi-relations.md`、`dong-bian-fa-ze.md` 同步 |
| PR-10 | 三合为大 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第三步、第七步 | 防止成局力量被单爻生克淹没 | 三合/三会状态机变更必须补测试 |
| PR-11 | 刑害为隐 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第四步 | 防止漏掉暗礁与纠葛层 | 刑害不单独决吉凶，需并入人我关系 |
| PR-12 | 贪忘有先后 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第三步 | 防止多关系并存时优先级错乱 | 优先级为合 > 冲 > 刑 > 害 > 生 > 克 |
| PR-13 | 动则不空 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第二步、第三步 | 防止发动旬空爻被直接判无力 | 与空亡旺衰规则同步 |
| PR-14 | 动不为破 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第二步、第三步 | 防止发动月破爻被直接判废 | 破中能动，不等同完全无用 |
| PR-15 | 旺不为空 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第二步、第六步 | 防止旺相旬空被当真空 | 出空、填实、临值应期要同步 |
| PR-16 | 化出定结局 | 解卦原则 | `references/jie-gua-xiang-jie.md` | 第三步、第七步 | 防止只看本爻不看变爻收场 | 动变方向必须显式验算 |
