# Experiment Analysis / 实验分析

**Run / 实验：** Winner-XFG perturbation report: run_20260731_014428_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：30（Samples）。
- 尝试生成的变体：2700；有效评分对比：2700；不可应用或不完整：0。
- 观测到的成功攻击：310。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%])。
- 在预算 3 下，观测到的最高ASR为：XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%])。
- 在预算 5 下，观测到的最高ASR为：XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- targeted subgraph injection 的预算响应呈保持不变模式（B1=6.7% -> B3=6.7% -> B5=6.7%）。
- XFG edge attack 的预算响应呈非单调模式（B1=10.0% -> B3=23.3% -> B5=13.3%）。
- XFG feature mask 的预算响应呈非递减模式（B1=10.0% -> B3=13.3% -> B5=13.3%）。
- targeted subgraph injection（预算 1） 的平均预测概率向上变化最大（+0.0057）；XFG edge attack（预算 3） 的平均预测概率向下变化最大（-0.0542）。
- targeted subgraph injection（预算 5） 的平均绝对节点变化最大（15.00）；targeted subgraph injection（预算 5） 的平均绝对边变化最大（20.00）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 30 (Samples).
- Attempted variants: 2700; scored comparisons: 2700; not applicable or incomplete: 0.
- Observed successful attacks: 310.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%]).
- At budget 3, the highest observed ASR is: XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%]).
- At budget 5, the highest observed ASR is: XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- targeted subgraph injection has an observed constant budget response (B1=6.7% -> B3=6.7% -> B5=6.7%).
- XFG edge attack has an observed non-monotonic budget response (B1=10.0% -> B3=23.3% -> B5=13.3%).
- XFG feature mask has an observed non-decreasing budget response (B1=10.0% -> B3=13.3% -> B5=13.3%).
- targeted subgraph injection at budget 1 has the largest upward mean probability shift (+0.0057); XFG edge attack at budget 3 has the largest downward shift (-0.0542).
- targeted subgraph injection at budget 5 has the largest mean absolute node change (15.00); targeted subgraph injection at budget 5 has the largest mean absolute edge change (20.00).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| targeted subgraph injection | 1 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | +0.0057 | 0.1206 [0.0970, 0.1442] | 3.00 | 4.00 |
| XFG edge attack | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0413 | 0.0995 [0.0775, 0.1216] | 0.00 | 1.00 |
| XFG feature mask | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0104 | 0.1167 [0.0892, 0.1441] | 0.00 | 0.00 |
| targeted subgraph injection | 3 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0203 | 0.1138 [0.0875, 0.1401] | 9.00 | 12.00 |
| XFG edge attack | 3 | 300/300 | 100.0% | 70 | 23.3% | [23.3%, 23.3%] | -0.0542 | 0.1691 [0.1377, 0.2006] | 0.00 | 3.00 |
| XFG feature mask | 3 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0392 | 0.1206 [0.0936, 0.1476] | 0.00 | 0.00 |
| targeted subgraph injection | 5 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0206 | 0.1381 [0.1108, 0.1653] | 15.00 | 20.00 |
| XFG edge attack | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0241 | 0.1710 [0.1390, 0.2030] | 0.00 | 5.00 |
| XFG feature mask | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0373 | 0.1260 [0.0999, 0.1522] | 0.00 | 0.00 |
