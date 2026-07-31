# 随机图扰动修复与评价说明

本文档面向需要运行 Full Test、检查实验结果或解读 Dashboard 的组员，
总结本轮随机图扰动修复、局部重跑流程和新增统计口径。

## 1. 背景

组员最近一次 60 样本 Full Test 使用了以下图实验配置：

- 图扰动预算：`1 / 3 / 5`
- 随机种子：`7, 17, 29, 42, 61, 73, 89, 101, 137, 2026`
- Random graph：6 个基础图 action
- Winner-XFG targeted graph：3 个定向 macro action

根据组员提供的运行总结，而非本机重新验证：

| 阶段 | 结果 |
|---|---|
| Baseline | 60/60 成功 |
| Code perturbation | 请求 780 个变体，349 个完成评分，6 次预测翻转 |
| Winner-XFG | 2700/2700 完成评分，310 次攻击成功，ASR 11.48% |
| Random graph | 请求 10800 个配置，10333 个完成评分 |
| Random graph 错误 | 467 个，均为 `IndexError: index 0 is out of bounds...` |

这 467 个错误主要集中在 `node_delete`、`edge_delete` 的 B3/B5，以及少量
`edge_reconnect`。错误发生在图删除后进入模型推理的边界情形，并不表示
整个 Full Test、Joern 或 DeepWuKong 模型崩溃。

## 2. 根因

Random graph runner 的流程是：

```text
PDG action
-> build_XFG
-> XFG 转 tensor
-> batch
-> DeepWuKong inference
```

删除节点或边后，`build_XFG` 仍可能返回候选 XFG，但其中某些 XFG 转换后的
节点特征 tensor 或边 tensor 为空。旧逻辑只检查是否返回了 XFG 对象，没有
在 batch 前排除空 tensor，因此模型内部索引第一个节点或边时触发
`IndexError`。

本轮修复引入以下判定：

```text
node feature tensor 非空
AND edge tensor 非空
=> scoreable XFG
```

空 XFG 会在 batch 前被过滤。如果一个扰动变体最终没有任何可评分 XFG，
它会被记录为：

```text
prediction_status = no_xfg
status = no_xfg
predicted_label = empty
probability = empty
```

`no_xfg` 是“预处理后没有可供模型判断的 XFG”，不是模型预测为 0，也不是
一次攻击成功或预测翻转。

## 3. 本轮四项修改

### 3.1 修复空 XFG 推理错误

Random graph 和 Winner-XFG predictor 现在都会：

1. 构建 XFG。
2. 将每个 XFG 转为模型 tensor。
3. 排除空节点特征或空边 tensor。
4. 只对剩余 XFG 执行 batch inference。
5. 若全部为空，保留该变体并标记为 `no_xfg`。

新增或强化的结果字段包括：

| 字段 | 含义 |
|---|---|
| `prediction_status` | `ok`、`no_xfg` 或其他执行状态 |
| `skipped_empty_xfg` | 当前变体中被排除的空 XFG 数量 |
| `perturbations_scored` | 实际完成模型评分的变体数 |
| `perturbations_unscored_no_xfg` | 因无可评分 XFG 而未评分的变体数 |
| `perturbation_errors` | 真正的执行错误数 |

因此，新的 runner 不会再用 `predicted_label=0` 掩盖空图，也不会把
`no_xfg` 纳入 flip rate 或 ASR 的分母。

### 3.2 支持只重跑 Random graph

新增脚本：

```text
scripts/rerun_random_graph.py
```

它复用现有 Full Test 已保存的：

- `graph_inputs/sources/`
- `graph_inputs/csv/`
- `graph_inputs/metadata.csv`
- 根目录 code/baseline 结果
- `graph_targeted/` 结果

因此不需要再次运行：

- baseline；
- 代码级扰动；
- Joern 图生成；
- Winner-XFG targeted graph。

在最近一次耗时分布中，代码阶段约 30 分钟，而 Random graph 约 9 分钟。
局部重跑可以避免重复最慢且已经成功的阶段。

### 3.3 自动替换结果并刷新 Dashboard

局部重跑采用候选目录和备份目录，避免失败结果直接覆盖原结果：

```text
graph_random_rerun_<timestamp>       # 新结果的临时候选目录
graph_random_before_rerun_<timestamp> # 原结果的备份目录
graph_random/                         # 验证成功后启用的新结果
```

处理顺序如下：

1. 在候选目录执行完整 Random graph。
2. runner 非零退出时保留原 `graph_random/`，不替换。
3. runner 成功后把原目录改名为备份目录。
4. 将候选目录改名为新的 `graph_random/`。
5. 重新生成当前 Full Test 的 Dashboard 和统计 CSV。
6. 在根 `summary.json` 的 `partial_reruns` 中记录局部重跑历史。

### 3.4 增加独立样本、seed 和共同队列统计

10 个 seed 会为同一个源代码样本产生重复观测。不能把这些观测全部当成
相互独立的 600 个样本。因此 Dashboard 现在同时提供以下四类口径。

#### A. Variant-level ASR

```text
ASR = 攻击成功且已评分的变体数 / baseline 正确且已评分的变体数
```

这个指标回答：“一次具体 action + budget + seed 配置成功的概率是多少？”

#### B. Sample-level statistics

将同一源样本的重复 seed 合并，每个源样本只计一次。主要字段包括：

- eligible/scored samples；
- 至少一个 seed 成功的样本数和比例；
- 所有已评分 seed 均成功的样本数；
- 每个样本 seed 成功率的平均值；
- 每个样本平均完成评分的变体数。

这个指标回答：“有多少独立源样本能够被该方法攻击成功？”

#### C. Seed-level stability

分别计算每个 seed 的：

- 覆盖率；
- eligible scored variants；
- attack success；
- ASR；
- 平均绝对概率变化。

Dashboard 还展示 seed ASR 的均值、标准差和范围：

```text
mean ± SD [min, max]
```

这个指标回答：“结果是否依赖某一个特别幸运或特别不利的 seed？”

#### D. Paired common-cohort comparison

Random graph 与 Winner-XFG 只在双方都成功评分的共同键上比较：

```text
(sample, budget, seed)
```

输出包括：

- common keys；
- common samples；
- 两个方法各自的 scored action variants；
- common cohort 上的 variant ASR；
- 每个共同键是否至少有一个 action 成功。

该统计减少了不同覆盖率造成的偏差。需要注意：Random graph 有 6 个 action，
Winner-XFG 有 3 个 action，因此“任一 action 成功率”是描述性比较，不等同于
严格控制 action 数量后的因果比较。

## 4. 如何局部重跑

### 4.1 前置条件

运行前确认：

1. 已同步包含本轮修复的代码。
2. Docker Desktop 正常运行。
3. DeepWuKong 镜像和 checkpoint 可用。
4. 目标目录是 `outputs/` 的直接子目录。
5. 目标 Full Test 中保留了 `graph_inputs/`、`graph_targeted/` 和根
   `prediction_comparison.csv`。

### 4.2 Docker 命令

在仓库根目录运行：

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond `
  rerun-random-graph --run-dir outputs/<full-test-run-name>
```

例如：

```powershell
docker compose -f scripts/docker/compose.yaml run --rm almond `
  rerun-random-graph --run-dir outputs/run_20260730_013637_code_all_input_sources
```

不要把绝对 Windows 路径传给 `--run-dir`。该参数应使用仓库内
`outputs/<run-name>` 的相对路径。

默认配置固定为：

```text
budgets = 1, 3, 5
seeds = 7, 17, 29, 42, 61, 73, 89, 101, 137, 2026
```

## 5. 重跑后的文件

目标 Full Test 目录中应重点检查：

```text
<run>/
  graph_random/
    prediction_comparison.csv
    action_summary.csv
    summary.json
  graph_random_before_rerun_<timestamp>/
  graph_logs/
    random_graph_rerun_<timestamp>.log
  graph_comparison/
    prediction_comparison.csv
    dashboard.html
    sample_level_summary.csv
    seed_level_summary.csv
    paired_common_summary.csv
  dashboard.html
  summary.json
```

具体 Dashboard 目录可能随已有 Full Test 布局略有差异，但以下三个统计文件
由新版报告生成器负责输出：

| 文件 | 用途 |
|---|---|
| `sample_level_summary.csv` | 去除重复 seed 后的独立样本统计 |
| `seed_level_summary.csv` | 每个 seed 的覆盖率、ASR 和概率变化 |
| `paired_common_summary.csv` | Random 与 Winner-XFG 在共同可评分键上的比较 |

## 6. 验收清单

局部重跑完成后建议依次检查：

1. 命令退出码为 0。
2. 日志末尾出现 Random graph 和 Dashboard 完成信息。
3. 新 `graph_random/summary.json` 中：
   - `perturbation_errors = 0`；
   - `perturbations_scored` 大于 0；
   - 允许 `perturbations_unscored_no_xfg` 大于 0。
4. CSV 中不再出现 `IndexError: index 0 is out of bounds...`。
5. `prediction_status=no_xfg` 的行没有伪造概率或预测标签。
6. 根 `summary.json` 包含新的 `partial_reruns` 记录。
7. `graph_targeted/`、代码结果和 baseline 结果仍保留原内容。
8. Dashboard 能打开，并显示 sample、seed 和 paired common-cohort 表格。
9. `graph_random_before_rerun_<timestamp>/` 保留旧结果，便于回溯。

## 7. 如何解读新结果

### 7.1 不要继续使用旧的 467 个失败作为模型预测

旧错误是推理输入边界问题。重跑后它们会分成两类：

- 仍有有效 XFG：正常评分；
- 没有有效 XFG：记录为 `no_xfg`，只影响 coverage。

### 7.2 Winner-XFG 与 Random graph 的强弱结论

旧汇总中 Winner-XFG ASR 为 11.48%，Random graph ASR 为 2.44%，说明定向
扰动可能更有效。但正式报告应优先引用 `paired_common_summary.csv`，因为旧
数字的可评分样本集合和 action 数量并不完全一致。

推荐报告顺序：

1. 分别报告两种方法的 coverage。
2. 报告各自 variant-level ASR。
3. 报告独立 sample-level success。
4. 报告 10 个 seed 的均值、标准差和范围。
5. 最后引用 common cohort 上的配对比较。

### 7.3 Budget 不要求单调

B5 的攻击成功率低于 B3 不一定是 bug。更大的 budget 会增加修改数量，但
不会保证模型输出持续向攻击目标移动。图扰动可能：

- 删除原本有利于攻击的结构；
- 创建新的替代路径；
- 使 XFG 切片改变；
- 让不同修改的效果互相抵消。

因此应把 B1/B3/B5 当作实验自变量比较，而不是预设“budget 越大 ASR 必须
越高”。

### 7.4 Code perturbation 需要同时报告覆盖率

代码阶段请求 780 个变体，但只有 349 个完成评分。正式报告不能只写
“6 次翻转”，还应同时写：

```text
有效覆盖率 = 349 / 780 = 44.7%
```

源码结构不适用导致的 action skip、编译/Joern 问题和真正模型推理失败应
分别统计，避免把未生成的变体当作攻击失败。

## 8. 本轮涉及的主要文件

| 文件 | 作用 |
|---|---|
| `experiment_design.py` | 定义可评分 XFG tensor 检查 |
| `run_random_graph_experiment.py` | Random graph 的 `no_xfg` 处理与统计 |
| `run_xfg_targeted_experiment.py` | Winner-XFG 使用相同的输入防护 |
| `scripts/rerun_random_graph.py` | 对已有 Full Test 只重跑 Random graph |
| `scripts/docker/docker_entrypoint.py` | 注册 `rerun-random-graph` Docker 命令 |
| `visualize_results.py` | 新增 sample、seed 和 paired common-cohort 统计 |
| `tests/test_random_graph_rerun.py` | 局部重跑和 summary 更新测试 |
| `tests/test_visualize_results.py` | 新统计口径和输出文件测试 |

## 9. 当前限制

- 本轮代码尚未在组员的最新 60 样本输出上实际执行；上述修复需要通过一次
  Random graph 局部重跑验证。
- `no_xfg` 表示该图无法按当前 DeepWuKong XFG 输入规范评分，不表示源码
  有漏洞或无漏洞。
- paired common-cohort 控制了样本、budget、seed 和可评分性，但尚未控制
  两类方法的 action 数量差异。
- 旧 `graph_random_before_rerun_*` 目录不会自动删除。确认新结果无误后再由
  团队决定是否归档或清理。

