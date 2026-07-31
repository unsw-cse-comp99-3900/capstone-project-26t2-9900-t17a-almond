# Experiment Analysis / 实验分析

**Run / 实验：** DeepWuKong perturbation report: run_20260731_014428_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：60（Input samples）。
- 尝试生成的变体：780；有效评分对比：349；不可应用或不完整：431。
- 观测到的预测翻转：6。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在固定设置下，观测到的最高预测翻转率为：sink bound guard: 36.4% (4/11, 95% CI [15.2%, 64.6%])。
- range clamp 的平均绝对概率变化最大（0.2319，n=11）。
- 覆盖率提示：array index bound guard, range clamp, safe source substitution, sink bound guard, temp variable split, wide char sink guard 的有效评分样本少于尝试样本的一半，其估计值对完整输入集的代表性较弱。
- sink bound guard 的平均预测概率向上变化最大（+0.0339）；range clamp 的平均预测概率向下变化最大（-0.2310）。
- pattern dead code 的平均绝对节点变化最大（54.02）；pattern dead code 的平均绝对边变化最大（99.20）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 60 (Input samples).
- Attempted variants: 780; scored comparisons: 349; not applicable or incomplete: 431.
- Observed prediction flips: 6.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At the fixed setting, the highest observed prediction flip rate is: sink bound guard: 36.4% (4/11, 95% CI [15.2%, 64.6%]).
- range clamp has the largest mean absolute probability change (0.2319, n=11).
- Coverage warning: array index bound guard, range clamp, safe source substitution, sink bound guard, temp variable split, wide char sink guard were scored on fewer than half of attempted cases; their estimates are less representative of the full input set.
- sink bound guard has the largest upward mean probability shift (+0.0339); range clamp has the largest downward shift (-0.2310).
- pattern dead code has the largest mean absolute node change (54.02); pattern dead code has the largest mean absolute edge change (99.20).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| array index bound guard | fixed setting | 13/60 | 21.7% | 0 | 0.0% | [0.0%, 22.8%] | -0.0130 | 0.0134 [0.0000, 0.0387] | 25.85 | 40.31 |
| control wrapper | fixed setting | 56/60 | 93.3% | 0 | 0.0% | [0.0%, 6.4%] | -0.0051 | 0.0197 [0.0078, 0.0317] | 4.39 | 14.38 |
| data flow alias | fixed setting | 56/60 | 93.3% | 0 | 0.0% | [0.0%, 6.4%] | +0.0033 | 0.0093 [0.0001, 0.0184] | 19.32 | 43.73 |
| dead statement | fixed setting | 56/60 | 93.3% | 1 | 1.8% | [0.3%, 9.4%] | -0.0121 | 0.0212 [0.0000, 0.0483] | 12.00 | 27.00 |
| integer overflow guard | fixed setting | 0/60 | N/A | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| pattern dead code | fixed setting | 56/60 | 93.3% | 0 | 0.0% | [0.0%, 6.4%] | -0.0051 | 0.0129 [0.0000, 0.0258] | 54.02 | 99.20 |
| postcondition validation | fixed setting | 0/60 | N/A | 0 | N/A | N/A | N/A | N/A | N/A | N/A |
| range clamp | fixed setting | 11/60 | 18.3% | 0 | 0.0% | [0.0%, 25.9%] | -0.2310 | 0.2319 [0.0981, 0.3657] | 30.00 | 69.64 |
| safe source substitution | fixed setting | 7/60 | 11.7% | 0 | 0.0% | [0.0%, 35.4%] | -0.0323 | 0.0323 [0.0000, 0.0786] | 8.71 | 16.14 |
| sink bound guard | fixed setting | 11/60 | 18.3% | 4 | 36.4% | [15.2%, 64.6%] | +0.0339 | 0.0822 [0.0387, 0.1257] | 16.18 | 30.64 |
| temp variable split | fixed setting | 26/60 | 43.3% | 0 | 0.0% | [0.0%, 12.9%] | +0.0004 | 0.0015 [0.0000, 0.0035] | 8.00 | 17.85 |
| wide char sink guard | fixed setting | 1/60 | 1.7% | 0 | 0.0% | [0.0%, 79.3%] | -0.0010 | 0.0010 [0.0010, 0.0010] | 18.00 | 34.00 |
| xfg targeted dead code | fixed setting | 56/60 | 93.3% | 1 | 1.8% | [0.3%, 9.4%] | -0.0184 | 0.0192 [0.0000, 0.0460] | 15.71 | 35.36 |
