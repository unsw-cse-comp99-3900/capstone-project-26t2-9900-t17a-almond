# Experiment Analysis / 实验分析

**Run / 实验：** DeepWuKong perturbation report: graph_random<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：60（Samples）。
- 尝试生成的变体：360；有效评分对比：360；不可应用或不完整：0。
- 观测到的预测翻转：3。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在固定设置下，观测到的最高预测翻转率为：node delete: 3.3% (2/60, 95% CI [0.9%, 11.4%])。
- node delete 的平均绝对概率变化最大（0.0755，n=60）。
- node attribute modify 的平均预测概率向上变化最大（+0.0423）；edge add 的平均预测概率向下变化最大（-0.0424）。
- node add 的平均绝对节点变化最大（1.00）；node delete 的平均绝对边变化最大（2.07）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 60 (Samples).
- Attempted variants: 360; scored comparisons: 360; not applicable or incomplete: 0.
- Observed prediction flips: 3.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At the fixed setting, the highest observed prediction flip rate is: node delete: 3.3% (2/60, 95% CI [0.9%, 11.4%]).
- node delete has the largest mean absolute probability change (0.0755, n=60).
- node attribute modify has the largest upward mean probability shift (+0.0423); edge add has the largest downward shift (-0.0424).
- node add has the largest mean absolute node change (1.00); node delete has the largest mean absolute edge change (2.07).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| edge add | fixed setting | 60/60 | 100.0% | 0 | 0.0% | [0.0%, 6.0%] | -0.0424 | 0.0561 [0.0210, 0.0913] | 0.00 | 1.00 |
| edge delete | fixed setting | 60/60 | 100.0% | 0 | 0.0% | [0.0%, 6.0%] | +0.0260 | 0.0278 [0.0080, 0.0475] | 0.00 | 1.00 |
| edge reconnect | fixed setting | 60/60 | 100.0% | 0 | 0.0% | [0.0%, 6.0%] | +0.0309 | 0.0315 [0.0104, 0.0526] | 0.00 | 0.00 |
| node add | fixed setting | 60/60 | 100.0% | 0 | 0.0% | [0.0%, 6.0%] | -0.0239 | 0.0240 [0.0034, 0.0445] | 1.00 | 1.00 |
| node attribute modify | fixed setting | 60/60 | 100.0% | 1 | 1.7% | [0.3%, 8.9%] | +0.0423 | 0.0423 [0.0130, 0.0716] | 0.00 | 0.00 |
| node delete | fixed setting | 60/60 | 100.0% | 2 | 3.3% | [0.9%, 11.4%] | -0.0405 | 0.0755 [0.0268, 0.1241] | 1.00 | 2.07 |
