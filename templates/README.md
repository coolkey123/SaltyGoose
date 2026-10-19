# templates/ — 产物模板与命名规范

> **本目录是什么**：七阶段产物（00-08 编号链）的空白模板 + 确认门记录模板。每个模板是该阶段产物的唯一格式正本——写产物时按模板落盘，禁自创格式。
> **产物链是唯一可靠的外置记忆**：每个文件是下一阶段的输入，也是断点续写的唯一依据。

## 模板清单

| 模板 | 产物名 | 阶段 |
|---|---|---|
| `00-topic-evaluation.md` | 00-选题评估.md | stage1-topic |
| `01-synopsis.md` | 01-梗概.md | stage2-synopsis |
| `02-outline.md` | 02-细纲.md（单文件两篇） | stage3-outline |
| `03-manuscript.md` | 03-正文.md | stage4-draft |
| `04-annotated.md` | 04-润色标注稿.md | stage5-polish |
| `04-clean.md` | 04-正文净稿.md | stage5-polish |
| `05-first-review.md` | 05-初审报告.md | stage6-review（初审 6a） |
| `05-final-review.md` | 05-终审报告.md | stage6-review（终审 6b） |
| `06-submission.md` | 06-投稿包/（两件） | stage7-delivery |
| `machine-check-package.md` | 项目-{书名}/机检提交/（四件） | stage6/stage7 |
| `07-review.md` | 07-复盘.md | stage7-delivery |
| `08-fingerprint.md` | 08-结构指纹.md | stage1 登记 / 交付复盘更新 |
| `gate-record.md` | 确认门记录（四道门通用） | 全阶段 |

## 产物链命名规范

1. **编号唯一**：00-选题评估 / 01-梗概 / 02-细纲 / 03-正文 / 04-润色标注稿 + 04-正文净稿 / **05-初审报告 + 05-终审报告（05 双报告，初审 6a 与终审 6b 各出一份）** / 06-投稿包 / 07-复盘 / 08-结构指纹——项目目录与脚本 glob 只认这套命名。
2. **`02-细纲.md` 单文件两篇**：上篇施工版（节拍表/伏笔规划表）+ 下篇投前方案（人设卡/伏笔地图）同文件双视图，**禁拆回两个文件**。
3. **旧产物名全库禁残留**：命名以本文件与 `../SKILL.md` 产物链为准；`../scripts/check-consistency.py` 已对旧名断言锁定，发现旧名引用一律按现行命名改正。

## 使用规则

- 全部落盘 `项目-{书名}/` 目录（**目录隔离**：该目录建在技能文件夹之外——技能文件夹只含技能文件与测试夹具，写作产物禁入技能文件夹）；
- 字段空缺填"待核"或"⚠️ 无来源"，禁留空格、禁猜测代填（编造防线）；
- 每个模板末尾附"门禁自检"行——落盘即对照，缺一即门不过；
- 模板内容与该阶段 `../references/stageN-*/` 四文件冲突时，以 references 为准并回改模板（references 是规则，templates 是空壳）。
