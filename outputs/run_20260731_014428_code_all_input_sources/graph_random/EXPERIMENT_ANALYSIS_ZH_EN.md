# Experiment Analysis / 实验分析

**Run / 实验：** Random graph perturbation report: run_20260731_014428_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：58（Samples）。
- 尝试生成的变体：10440；有效评分对比：9973；不可应用或不完整：467。
- 观测到的成功攻击：131。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：edge add: 2.0% (6/300, 95% CI [0.6%, 3.4%])。
- 在预算 3 下，观测到的最高ASR为：edge add: 4.0% (12/300, 95% CI [2.7%, 5.3%])。
- 在预算 5 下，观测到的最高ASR为：node delete: 6.4% (15/232, 95% CI [3.6%, 9.3%])。
- edge add 的预算响应呈非单调模式（B1=2.0% -> B3=4.0% -> B5=3.0%）。
- edge delete 的预算响应呈非递减模式（B1=0.7% -> B3=2.9% -> B5=5.5%）。
- edge reconnect 的预算响应呈非单调模式（B1=1.3% -> B3=2.3% -> B5=2.3%）。
- node add 的预算响应呈非递减模式（B1=0.0% -> B3=0.7% -> B5=1.3%）。
- node attribute modify 的预算响应呈非递减模式（B1=1.3% -> B3=3.3% -> B5=5.3%）。
- node delete 的预算响应呈非递减模式（B1=1.3% -> B3=3.4% -> B5=6.4%）。
- node delete（预算 5） 的平均预测概率向上变化最大（+0.0153）；edge reconnect（预算 5） 的平均预测概率向下变化最大（-0.0588）。
- node add（预算 5） 的平均绝对节点变化最大（5.00）；node delete（预算 5） 的平均绝对边变化最大（14.90）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 58 (Samples).
- Attempted variants: 10440; scored comparisons: 9973; not applicable or incomplete: 467.
- Observed successful attacks: 131.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: edge add: 2.0% (6/300, 95% CI [0.6%, 3.4%]).
- At budget 3, the highest observed ASR is: edge add: 4.0% (12/300, 95% CI [2.7%, 5.3%]).
- At budget 5, the highest observed ASR is: node delete: 6.4% (15/232, 95% CI [3.6%, 9.3%]).
- edge add has an observed non-monotonic budget response (B1=2.0% -> B3=4.0% -> B5=3.0%).
- edge delete has an observed non-decreasing budget response (B1=0.7% -> B3=2.9% -> B5=5.5%).
- edge reconnect has an observed non-monotonic budget response (B1=1.3% -> B3=2.3% -> B5=2.3%).
- node add has an observed non-decreasing budget response (B1=0.0% -> B3=0.7% -> B5=1.3%).
- node attribute modify has an observed non-decreasing budget response (B1=1.3% -> B3=3.3% -> B5=5.3%).
- node delete has an observed non-decreasing budget response (B1=1.3% -> B3=3.4% -> B5=6.4%).
- node delete at budget 5 has the largest upward mean probability shift (+0.0153); edge reconnect at budget 5 has the largest downward shift (-0.0588).
- node add at budget 5 has the largest mean absolute node change (5.00); node delete at budget 5 has the largest mean absolute edge change (14.90).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| edge add | 1 | 580/580 | 100.0% | 6 | 2.0% | [0.6%, 3.4%] | -0.0140 | 0.0401 [0.0313, 0.0488] | 0.00 | 1.00 |
| edge delete | 1 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 1.5%] | +0.0121 | 0.0258 [0.0190, 0.0327] | 0.00 | 1.00 |
| edge reconnect | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0178 | 0.0589 [0.0469, 0.0708] | 0.00 | 0.00 |
| node add | 1 | 580/580 | 100.0% | 0 | 0.0% | [0.0%, 0.0%] | -0.0017 | 0.0052 [0.0021, 0.0082] | 1.00 | 1.00 |
| node attribute modify | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0087 | 0.0380 [0.0285, 0.0475] | 0.00 | 0.00 |
| node delete | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0115 | 0.0482 [0.0366, 0.0598] | 1.00 | 2.78 |
| edge add | 3 | 580/580 | 100.0% | 12 | 4.0% | [2.7%, 5.3%] | -0.0181 | 0.0700 [0.0579, 0.0820] | 0.00 | 3.00 |
| edge delete | 3 | 540/580 | 93.1% | 8 | 2.9% | [1.1%, 4.7%] | -0.0212 | 0.0707 [0.0569, 0.0845] | 0.00 | 3.00 |
| edge reconnect | 3 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0374 | 0.0694 [0.0567, 0.0821] | 0.00 | 0.00 |
| node add | 3 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 2.0%] | +0.0060 | 0.0279 [0.0208, 0.0350] | 3.00 | 3.00 |
| node attribute modify | 3 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0188 | 0.0912 [0.0763, 0.1061] | 0.00 | 0.00 |
| node delete | 3 | 442/580 | 76.2% | 8 | 3.4% | [1.0%, 5.8%] | +0.0080 | 0.0668 [0.0486, 0.0851] | 2.98 | 9.27 |
| edge add | 5 | 580/580 | 100.0% | 9 | 3.0% | [0.9%, 5.1%] | -0.0402 | 0.0799 [0.0658, 0.0939] | 0.00 | 5.00 |
| edge delete | 5 | 444/580 | 76.6% | 13 | 5.5% | [3.7%, 7.2%] | -0.0084 | 0.0657 [0.0485, 0.0828] | 0.00 | 5.00 |
| edge reconnect | 5 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0588 | 0.0819 [0.0681, 0.0957] | 0.00 | 0.00 |
| node add | 5 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0039 | 0.0531 [0.0434, 0.0629] | 5.00 | 5.00 |
| node attribute modify | 5 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0371 | 0.1091 [0.0928, 0.1254] | 0.00 | 0.00 |
| node delete | 5 | 431/580 | 74.3% | 15 | 6.4% | [3.6%, 9.3%] | +0.0153 | 0.0865 [0.0667, 0.1064] | 4.84 | 14.90 |
