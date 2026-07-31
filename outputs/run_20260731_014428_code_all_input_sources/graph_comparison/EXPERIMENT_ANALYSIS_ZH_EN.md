# Experiment Analysis / 实验分析

**Run / 实验：** Random graph vs Winner-XFG: run_20260731_014428_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：58（Samples）。
- 尝试生成的变体：13140；有效评分对比：12673；不可应用或不完整：467。
- 观测到的成功攻击：441。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); Winner-XFG - XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%])。
- 在预算 3 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%])。
- 在预算 5 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- Random graph - edge add 的预算响应呈非单调模式（B1=2.0% -> B3=4.0% -> B5=3.0%）。
- Random graph - edge delete 的预算响应呈非递减模式（B1=0.7% -> B3=2.9% -> B5=5.5%）。
- Random graph - edge reconnect 的预算响应呈非单调模式（B1=1.3% -> B3=2.3% -> B5=2.3%）。
- Random graph - node add 的预算响应呈非递减模式（B1=0.0% -> B3=0.7% -> B5=1.3%）。
- Random graph - node attribute modify 的预算响应呈非递减模式（B1=1.3% -> B3=3.3% -> B5=5.3%）。
- Random graph - node delete 的预算响应呈非递减模式（B1=1.3% -> B3=3.4% -> B5=6.4%）。
- Winner-XFG - targeted subgraph injection 的预算响应呈保持不变模式（B1=6.7% -> B3=6.7% -> B5=6.7%）。
- Winner-XFG - XFG edge attack 的预算响应呈非单调模式（B1=10.0% -> B3=23.3% -> B5=13.3%）。
- Winner-XFG - XFG feature mask 的预算响应呈非递减模式（B1=10.0% -> B3=13.3% -> B5=13.3%）。
- Random graph - node delete（预算 5） 的平均预测概率向上变化最大（+0.0153）；Random graph - edge reconnect（预算 5） 的平均预测概率向下变化最大（-0.0588）。
- Winner-XFG - targeted subgraph injection（预算 5） 的平均绝对节点变化最大（15.00）；Winner-XFG - targeted subgraph injection（预算 5） 的平均绝对边变化最大（20.00）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 58 (Samples).
- Attempted variants: 13140; scored comparisons: 12673; not applicable or incomplete: 467.
- Observed successful attacks: 441.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: Winner-XFG - XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); Winner-XFG - XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%]).
- At budget 3, the highest observed ASR is: Winner-XFG - XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%]).
- At budget 5, the highest observed ASR is: Winner-XFG - XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- Random graph - edge add has an observed non-monotonic budget response (B1=2.0% -> B3=4.0% -> B5=3.0%).
- Random graph - edge delete has an observed non-decreasing budget response (B1=0.7% -> B3=2.9% -> B5=5.5%).
- Random graph - edge reconnect has an observed non-monotonic budget response (B1=1.3% -> B3=2.3% -> B5=2.3%).
- Random graph - node add has an observed non-decreasing budget response (B1=0.0% -> B3=0.7% -> B5=1.3%).
- Random graph - node attribute modify has an observed non-decreasing budget response (B1=1.3% -> B3=3.3% -> B5=5.3%).
- Random graph - node delete has an observed non-decreasing budget response (B1=1.3% -> B3=3.4% -> B5=6.4%).
- Winner-XFG - targeted subgraph injection has an observed constant budget response (B1=6.7% -> B3=6.7% -> B5=6.7%).
- Winner-XFG - XFG edge attack has an observed non-monotonic budget response (B1=10.0% -> B3=23.3% -> B5=13.3%).
- Winner-XFG - XFG feature mask has an observed non-decreasing budget response (B1=10.0% -> B3=13.3% -> B5=13.3%).
- Random graph - node delete at budget 5 has the largest upward mean probability shift (+0.0153); Random graph - edge reconnect at budget 5 has the largest downward shift (-0.0588).
- Winner-XFG - targeted subgraph injection at budget 5 has the largest mean absolute node change (15.00); Winner-XFG - targeted subgraph injection at budget 5 has the largest mean absolute edge change (20.00).

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \|Δ nodes\| / 平均节点变化 | Mean \|Δ edges\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Random graph - edge add | 1 | 580/580 | 100.0% | 6 | 2.0% | [0.6%, 3.4%] | -0.0140 | 0.0401 [0.0313, 0.0488] | 0.00 | 1.00 |
| Random graph - edge delete | 1 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 1.5%] | +0.0121 | 0.0258 [0.0190, 0.0327] | 0.00 | 1.00 |
| Random graph - edge reconnect | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0178 | 0.0589 [0.0469, 0.0708] | 0.00 | 0.00 |
| Random graph - node add | 1 | 580/580 | 100.0% | 0 | 0.0% | [0.0%, 0.0%] | -0.0017 | 0.0052 [0.0021, 0.0082] | 1.00 | 1.00 |
| Random graph - node attribute modify | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0087 | 0.0380 [0.0285, 0.0475] | 0.00 | 0.00 |
| Random graph - node delete | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0115 | 0.0482 [0.0366, 0.0598] | 1.00 | 2.78 |
| Winner-XFG - targeted subgraph injection | 1 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | +0.0057 | 0.1206 [0.0970, 0.1442] | 3.00 | 4.00 |
| Winner-XFG - XFG edge attack | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0413 | 0.0995 [0.0775, 0.1216] | 0.00 | 1.00 |
| Winner-XFG - XFG feature mask | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0104 | 0.1167 [0.0892, 0.1441] | 0.00 | 0.00 |
| Random graph - edge add | 3 | 580/580 | 100.0% | 12 | 4.0% | [2.7%, 5.3%] | -0.0181 | 0.0700 [0.0579, 0.0820] | 0.00 | 3.00 |
| Random graph - edge delete | 3 | 540/580 | 93.1% | 8 | 2.9% | [1.1%, 4.7%] | -0.0212 | 0.0707 [0.0569, 0.0845] | 0.00 | 3.00 |
| Random graph - edge reconnect | 3 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0374 | 0.0694 [0.0567, 0.0821] | 0.00 | 0.00 |
| Random graph - node add | 3 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 2.0%] | +0.0060 | 0.0279 [0.0208, 0.0350] | 3.00 | 3.00 |
| Random graph - node attribute modify | 3 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0188 | 0.0912 [0.0763, 0.1061] | 0.00 | 0.00 |
| Random graph - node delete | 3 | 442/580 | 76.2% | 8 | 3.4% | [1.0%, 5.8%] | +0.0080 | 0.0668 [0.0486, 0.0851] | 2.98 | 9.27 |
| Winner-XFG - targeted subgraph injection | 3 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0203 | 0.1138 [0.0875, 0.1401] | 9.00 | 12.00 |
| Winner-XFG - XFG edge attack | 3 | 300/300 | 100.0% | 70 | 23.3% | [23.3%, 23.3%] | -0.0542 | 0.1691 [0.1377, 0.2006] | 0.00 | 3.00 |
| Winner-XFG - XFG feature mask | 3 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0392 | 0.1206 [0.0936, 0.1476] | 0.00 | 0.00 |
| Random graph - edge add | 5 | 580/580 | 100.0% | 9 | 3.0% | [0.9%, 5.1%] | -0.0402 | 0.0799 [0.0658, 0.0939] | 0.00 | 5.00 |
| Random graph - edge delete | 5 | 444/580 | 76.6% | 13 | 5.5% | [3.7%, 7.2%] | -0.0084 | 0.0657 [0.0485, 0.0828] | 0.00 | 5.00 |
| Random graph - edge reconnect | 5 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0588 | 0.0819 [0.0681, 0.0957] | 0.00 | 0.00 |
| Random graph - node add | 5 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0039 | 0.0531 [0.0434, 0.0629] | 5.00 | 5.00 |
| Random graph - node attribute modify | 5 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0371 | 0.1091 [0.0928, 0.1254] | 0.00 | 0.00 |
| Random graph - node delete | 5 | 431/580 | 74.3% | 15 | 6.4% | [3.6%, 9.3%] | +0.0153 | 0.0865 [0.0667, 0.1064] | 4.84 | 14.90 |
| Winner-XFG - targeted subgraph injection | 5 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0206 | 0.1381 [0.1108, 0.1653] | 15.00 | 20.00 |
| Winner-XFG - XFG edge attack | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0241 | 0.1710 [0.1390, 0.2030] | 0.00 | 5.00 |
| Winner-XFG - XFG feature mask | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0373 | 0.1260 [0.0999, 0.1522] | 0.00 | 0.00 |
