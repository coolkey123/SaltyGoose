# 测试 Prompt 索引（唯一正本见 `../test-prompts.json`）

> **本文件是过渡层，不存正文。** 2026-10-18起，原先分居两处的测试集已合并为 `../test-prompts.json` 一份 5 条——
> 历史上 `tests/test-prompts.json` 与根目录 `test-prompts.json` 内容不同、互不引用、无归属说明，属重复登记（普查缺陷 D7）。
>
> **为什么不直接删**：`tests/` 是回归目录，`run-tests.py` 与本目录其他夹具同处一处，保留本索引可让「回归同目录」的直觉不失联。
>
> | 事项 | 口径 |
> |---|---|
> | 测试集正本 | `../test-prompts.json`（5 条：happy path×2 / 编造防线 / 范围边界 / 会话续写） |
> | 本文件角色 | 指路索引，**不复制条目** |
> | 新增用例 | 只加进 `../test-prompts.json`，不在此处另立 |
> | 与脚本的关系 | 两者都不被 `run-tests.py` 消费——本文件集供 darwin 式 paired 实测（维度 8）使用 |

## 为什么测试集不放在 tests/

`run-tests.py` 跑的是**脚本回归**（9 个脚本的退出码与判据是否仍然正确），输入是 `tests/fixtures/` 的固定夹具。
`test-prompts.json` 跑的是**技能行为实测**（带着 SKILL.md 执行用户请求，看是否按流水线走、是否守住编造防线），
输入是自然语言 prompt + 期望行为描述，需要子 agent 盲测。两者验证对象不同，混放在 `tests/` 会让人误以为
「跑 run-tests.py 就等于测过技能行为了」——而这恰恰是 darwin 反复强调的 dry_run 陷阱。
