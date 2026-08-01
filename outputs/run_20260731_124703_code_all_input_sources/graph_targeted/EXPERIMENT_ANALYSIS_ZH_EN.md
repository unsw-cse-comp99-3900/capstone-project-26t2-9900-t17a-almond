# Experiment Analysis / 实验分析

**Run / 实验：** Winner-XFG perturbation report: run_20260731_124703_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：30（Samples）。
- 尝试生成的变体：9000；有效评分对比：9000；不可应用或不完整：0。
- 观测到的成功攻击：1070。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%])。
- 在预算 3 下，观测到的最高ASR为：XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%])。
- 在预算 5 下，观测到的最高ASR为：XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 7 下，观测到的最高ASR为：XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]); XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 9 下，观测到的最高ASR为：XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 11 下，观测到的最高ASR为：XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 13 下，观测到的最高ASR为：XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 15 下，观测到的最高ASR为：XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 20 下，观测到的最高ASR为：XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 25 下，观测到的最高ASR为：XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- targeted subgraph injection 的预算响应呈非递减模式（B1=6.7% -> B3=6.7% -> B5=6.7% -> B7=6.7% -> B9=6.7% -> B11=6.7% -> B13=6.7% -> B15=6.7% -> B20=13.3% -> B25=13.3%）。
- XFG edge attack 的预算响应呈非单调模式（B1=10.0% -> B3=23.3% -> B5=13.3% -> B7=16.7% -> B9=16.7% -> B11=13.3% -> B13=10.0% -> B15=10.0% -> B20=10.0% -> B25=10.0%）。
- XFG feature mask 的预算响应呈非单调模式（B1=10.0% -> B3=13.3% -> B5=16.7% -> B7=16.7% -> B9=13.3% -> B11=13.3% -> B13=13.3% -> B15=13.3% -> B20=16.7% -> B25=16.7%）。
- targeted subgraph injection（预算 1） 的平均预测概率向上变化最大（+0.0059）；XFG edge attack（预算 25） 的平均预测概率向下变化最大（-0.0940）。
- targeted subgraph injection（预算 25） 的平均绝对节点变化最大（75.00）；targeted subgraph injection（预算 25） 的平均绝对边变化最大（100.00）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 30 (Samples).
- Attempted variants: 9000; scored comparisons: 9000; not applicable or incomplete: 0.
- Observed successful attacks: 1070.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%]).
- At budget 3, the highest observed ASR is: XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%]).
- At budget 5, the highest observed ASR is: XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 7, the highest observed ASR is: XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]); XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 9, the highest observed ASR is: XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 11, the highest observed ASR is: XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 13, the highest observed ASR is: XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 15, the highest observed ASR is: XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 20, the highest observed ASR is: XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 25, the highest observed ASR is: XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- targeted subgraph injection has an observed non-decreasing budget response (B1=6.7% -> B3=6.7% -> B5=6.7% -> B7=6.7% -> B9=6.7% -> B11=6.7% -> B13=6.7% -> B15=6.7% -> B20=13.3% -> B25=13.3%).
- XFG edge attack has an observed non-monotonic budget response (B1=10.0% -> B3=23.3% -> B5=13.3% -> B7=16.7% -> B9=16.7% -> B11=13.3% -> B13=10.0% -> B15=10.0% -> B20=10.0% -> B25=10.0%).
- XFG feature mask has an observed non-monotonic budget response (B1=10.0% -> B3=13.3% -> B5=16.7% -> B7=16.7% -> B9=13.3% -> B11=13.3% -> B13=13.3% -> B15=13.3% -> B20=16.7% -> B25=16.7%).
- targeted subgraph injection at budget 1 has the largest upward mean probability shift (+0.0059); XFG edge attack at budget 25 has the largest downward shift (-0.0940).
- targeted subgraph injection at budget 25 has the largest mean absolute node change (75.00); targeted subgraph injection at budget 25 has the largest mean absolute edge change (100.00).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| targeted subgraph injection | 1 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | +0.0059 | 0.1208 [0.0972, 0.1444] | 3.00 | 4.00 |
| XFG edge attack | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0413 | 0.0995 [0.0775, 0.1216] | 0.00 | 1.00 |
| XFG feature mask | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0104 | 0.1166 [0.0892, 0.1441] | 0.00 | 0.00 |
| targeted subgraph injection | 3 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0177 | 0.1164 [0.0900, 0.1429] | 9.00 | 12.00 |
| XFG edge attack | 3 | 300/300 | 100.0% | 70 | 23.3% | [23.3%, 23.3%] | -0.0542 | 0.1692 [0.1378, 0.2006] | 0.00 | 3.00 |
| XFG feature mask | 3 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0398 | 0.1200 [0.0929, 0.1470] | 0.00 | 0.00 |
| targeted subgraph injection | 5 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0224 | 0.1362 [0.1092, 0.1633] | 15.00 | 20.00 |
| XFG edge attack | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0241 | 0.1710 [0.1391, 0.2030] | 0.00 | 5.00 |
| XFG feature mask | 5 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0239 | 0.1395 [0.1115, 0.1675] | 0.00 | 0.00 |
| targeted subgraph injection | 7 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0248 | 0.1484 [0.1210, 0.1758] | 21.00 | 28.00 |
| XFG edge attack | 7 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0374 | 0.1720 [0.1381, 0.2059] | 0.00 | 6.93 |
| XFG feature mask | 7 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0157 | 0.1477 [0.1178, 0.1775] | 0.00 | 0.00 |
| targeted subgraph injection | 9 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0248 | 0.1562 [0.1286, 0.1837] | 27.00 | 36.00 |
| XFG edge attack | 9 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0526 | 0.1913 [0.1574, 0.2252] | 0.00 | 8.80 |
| XFG feature mask | 9 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1146, 0.1722] | 0.00 | 0.00 |
| targeted subgraph injection | 11 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0292 | 0.1548 [0.1268, 0.1829] | 33.00 | 44.00 |
| XFG edge attack | 11 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0727 | 0.1859 [0.1531, 0.2187] | 0.00 | 10.63 |
| XFG feature mask | 11 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1147, 0.1722] | 0.00 | 0.00 |
| targeted subgraph injection | 13 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0278 | 0.1559 [0.1274, 0.1843] | 39.00 | 52.00 |
| XFG edge attack | 13 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0760 | 0.1828 [0.1525, 0.2131] | 0.00 | 12.43 |
| XFG feature mask | 13 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1146, 0.1722] | 0.00 | 0.00 |
| targeted subgraph injection | 15 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0271 | 0.1585 [0.1296, 0.1874] | 45.00 | 60.00 |
| XFG edge attack | 15 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0654 | 0.1706 [0.1412, 0.1999] | 0.00 | 14.23 |
| XFG feature mask | 15 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0201 | 0.1433 [0.1145, 0.1721] | 0.00 | 0.00 |
| targeted subgraph injection | 20 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0261 | 0.1641 [0.1343, 0.1938] | 60.00 | 80.00 |
| XFG edge attack | 20 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0902 | 0.1638 [0.1362, 0.1913] | 0.00 | 18.33 |
| XFG feature mask | 20 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0191 | 0.1443 [0.1154, 0.1733] | 0.00 | 0.00 |
| targeted subgraph injection | 25 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0259 | 0.1697 [0.1394, 0.1999] | 75.00 | 100.00 |
| XFG edge attack | 25 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0940 | 0.1606 [0.1334, 0.1878] | 0.00 | 22.33 |
| XFG feature mask | 25 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0191 | 0.1443 [0.1154, 0.1733] | 0.00 | 0.00 |
