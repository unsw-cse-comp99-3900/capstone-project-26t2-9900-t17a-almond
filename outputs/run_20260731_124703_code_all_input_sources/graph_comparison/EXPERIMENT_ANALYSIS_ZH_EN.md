# Experiment Analysis / 实验分析

**Run / 实验：** Random graph vs Winner-XFG: run_20260731_124703_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：58（Samples）。
- 尝试生成的变体：43800；有效评分对比：40404；不可应用或不完整：3396。
- 观测到的成功攻击：1859。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); Winner-XFG - XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%])。
- 在预算 3 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%])。
- 在预算 5 下，观测到的最高ASR为：Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 7 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]); Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 9 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 11 下，观测到的最高ASR为：Winner-XFG - XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 13 下，观测到的最高ASR为：Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 15 下，观测到的最高ASR为：Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%])。
- 在预算 20 下，观测到的最高ASR为：Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- 在预算 25 下，观测到的最高ASR为：Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%])。
- Random graph - edge add 的预算响应呈非单调模式（B1=2.0% -> B3=4.0% -> B5=3.0% -> B7=4.0% -> B9=3.3% -> B11=3.7% -> B13=4.0% -> B15=4.7% -> B20=4.3% -> B25=4.0%）。
- Random graph - edge delete 的预算响应呈非单调模式（B1=0.7% -> B3=2.9% -> B5=5.5% -> B7=7.2% -> B9=4.1% -> B11=3.7% -> B13=3.6% -> B15=4.5% -> B20=6.0% -> B25=3.8%）。
- Random graph - edge reconnect 的预算响应呈非单调模式（B1=1.3% -> B3=2.3% -> B5=2.3% -> B7=2.4% -> B9=3.3% -> B11=2.7% -> B13=3.3% -> B15=3.0% -> B20=4.3% -> B25=3.4%）。
- Random graph - node add 的预算响应呈非递减模式（B1=0.0% -> B3=0.7% -> B5=1.3% -> B7=2.3% -> B9=3.7% -> B11=3.7% -> B13=4.3% -> B15=5.3% -> B20=5.7% -> B25=6.7%）。
- Random graph - node attribute modify 的预算响应呈非单调模式（B1=1.3% -> B3=3.3% -> B5=5.3% -> B7=6.7% -> B9=7.3% -> B11=7.0% -> B13=7.7% -> B15=9.3% -> B20=12.3% -> B25=13.3%）。
- Random graph - node delete 的预算响应呈非单调模式（B1=1.3% -> B3=3.4% -> B5=6.4% -> B7=7.5% -> B9=9.3% -> B11=8.1% -> B13=11.4% -> B15=11.5% -> B20=12.6% -> B25=15.5%）。
- Winner-XFG - targeted subgraph injection 的预算响应呈非递减模式（B1=6.7% -> B3=6.7% -> B5=6.7% -> B7=6.7% -> B9=6.7% -> B11=6.7% -> B13=6.7% -> B15=6.7% -> B20=13.3% -> B25=13.3%）。
- Winner-XFG - XFG edge attack 的预算响应呈非单调模式（B1=10.0% -> B3=23.3% -> B5=13.3% -> B7=16.7% -> B9=16.7% -> B11=13.3% -> B13=10.0% -> B15=10.0% -> B20=10.0% -> B25=10.0%）。
- Winner-XFG - XFG feature mask 的预算响应呈非单调模式（B1=10.0% -> B3=13.3% -> B5=16.7% -> B7=16.7% -> B9=13.3% -> B11=13.3% -> B13=13.3% -> B15=13.3% -> B20=16.7% -> B25=16.7%）。
- 覆盖率提示：Random graph - edge delete 的有效评分样本少于尝试样本的一半，其估计值对完整输入集的代表性较弱。
- Random graph - edge delete（预算 25） 的平均预测概率向上变化最大（+0.0639）；Random graph - edge add（预算 25） 的平均预测概率向下变化最大（-0.1060）。
- Winner-XFG - targeted subgraph injection（预算 25） 的平均绝对节点变化最大（75.00）；Winner-XFG - targeted subgraph injection（预算 25） 的平均绝对边变化最大（100.00）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 58 (Samples).
- Attempted variants: 43800; scored comparisons: 40404; not applicable or incomplete: 3396.
- Observed successful attacks: 1859.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: Winner-XFG - XFG edge attack: 10.0% (30/300, 95% CI [10.0%, 10.0%]); Winner-XFG - XFG feature mask: 10.0% (30/300, 95% CI [10.0%, 10.0%]).
- At budget 3, the highest observed ASR is: Winner-XFG - XFG edge attack: 23.3% (70/300, 95% CI [23.3%, 23.3%]).
- At budget 5, the highest observed ASR is: Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 7, the highest observed ASR is: Winner-XFG - XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]); Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 9, the highest observed ASR is: Winner-XFG - XFG edge attack: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 11, the highest observed ASR is: Winner-XFG - XFG edge attack: 13.3% (40/300, 95% CI [13.3%, 13.3%]); Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 13, the highest observed ASR is: Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 15, the highest observed ASR is: Winner-XFG - XFG feature mask: 13.3% (40/300, 95% CI [13.3%, 13.3%]).
- At budget 20, the highest observed ASR is: Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- At budget 25, the highest observed ASR is: Winner-XFG - XFG feature mask: 16.7% (50/300, 95% CI [16.7%, 16.7%]).
- Random graph - edge add has an observed non-monotonic budget response (B1=2.0% -> B3=4.0% -> B5=3.0% -> B7=4.0% -> B9=3.3% -> B11=3.7% -> B13=4.0% -> B15=4.7% -> B20=4.3% -> B25=4.0%).
- Random graph - edge delete has an observed non-monotonic budget response (B1=0.7% -> B3=2.9% -> B5=5.5% -> B7=7.2% -> B9=4.1% -> B11=3.7% -> B13=3.6% -> B15=4.5% -> B20=6.0% -> B25=3.8%).
- Random graph - edge reconnect has an observed non-monotonic budget response (B1=1.3% -> B3=2.3% -> B5=2.3% -> B7=2.4% -> B9=3.3% -> B11=2.7% -> B13=3.3% -> B15=3.0% -> B20=4.3% -> B25=3.4%).
- Random graph - node add has an observed non-decreasing budget response (B1=0.0% -> B3=0.7% -> B5=1.3% -> B7=2.3% -> B9=3.7% -> B11=3.7% -> B13=4.3% -> B15=5.3% -> B20=5.7% -> B25=6.7%).
- Random graph - node attribute modify has an observed non-monotonic budget response (B1=1.3% -> B3=3.3% -> B5=5.3% -> B7=6.7% -> B9=7.3% -> B11=7.0% -> B13=7.7% -> B15=9.3% -> B20=12.3% -> B25=13.3%).
- Random graph - node delete has an observed non-monotonic budget response (B1=1.3% -> B3=3.4% -> B5=6.4% -> B7=7.5% -> B9=9.3% -> B11=8.1% -> B13=11.4% -> B15=11.5% -> B20=12.6% -> B25=15.5%).
- Winner-XFG - targeted subgraph injection has an observed non-decreasing budget response (B1=6.7% -> B3=6.7% -> B5=6.7% -> B7=6.7% -> B9=6.7% -> B11=6.7% -> B13=6.7% -> B15=6.7% -> B20=13.3% -> B25=13.3%).
- Winner-XFG - XFG edge attack has an observed non-monotonic budget response (B1=10.0% -> B3=23.3% -> B5=13.3% -> B7=16.7% -> B9=16.7% -> B11=13.3% -> B13=10.0% -> B15=10.0% -> B20=10.0% -> B25=10.0%).
- Winner-XFG - XFG feature mask has an observed non-monotonic budget response (B1=10.0% -> B3=13.3% -> B5=16.7% -> B7=16.7% -> B9=13.3% -> B11=13.3% -> B13=13.3% -> B15=13.3% -> B20=16.7% -> B25=16.7%).
- Coverage warning: Random graph - edge delete were scored on fewer than half of attempted cases; their estimates are less representative of the full input set.
- Random graph - edge delete at budget 25 has the largest upward mean probability shift (+0.0639); Random graph - edge add at budget 25 has the largest downward shift (-0.1060).
- Winner-XFG - targeted subgraph injection at budget 25 has the largest mean absolute node change (75.00); Winner-XFG - targeted subgraph injection at budget 25 has the largest mean absolute edge change (100.00).

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
| Winner-XFG - targeted subgraph injection | 1 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | +0.0059 | 0.1208 [0.0972, 0.1444] | 3.00 | 4.00 |
| Winner-XFG - XFG edge attack | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0413 | 0.0995 [0.0775, 0.1216] | 0.00 | 1.00 |
| Winner-XFG - XFG feature mask | 1 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0104 | 0.1166 [0.0892, 0.1441] | 0.00 | 0.00 |
| Random graph - edge add | 3 | 580/580 | 100.0% | 12 | 4.0% | [2.7%, 5.3%] | -0.0181 | 0.0700 [0.0579, 0.0820] | 0.00 | 3.00 |
| Random graph - edge delete | 3 | 540/580 | 93.1% | 8 | 2.9% | [1.1%, 4.7%] | -0.0212 | 0.0707 [0.0569, 0.0845] | 0.00 | 3.00 |
| Random graph - edge reconnect | 3 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0374 | 0.0694 [0.0568, 0.0821] | 0.00 | 0.00 |
| Random graph - node add | 3 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 2.0%] | +0.0060 | 0.0279 [0.0208, 0.0350] | 3.00 | 3.00 |
| Random graph - node attribute modify | 3 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0188 | 0.0912 [0.0763, 0.1061] | 0.00 | 0.00 |
| Random graph - node delete | 3 | 442/580 | 76.2% | 8 | 3.4% | [1.0%, 5.8%] | +0.0080 | 0.0668 [0.0486, 0.0851] | 2.98 | 9.27 |
| Winner-XFG - targeted subgraph injection | 3 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0177 | 0.1164 [0.0900, 0.1429] | 9.00 | 12.00 |
| Winner-XFG - XFG edge attack | 3 | 300/300 | 100.0% | 70 | 23.3% | [23.3%, 23.3%] | -0.0542 | 0.1692 [0.1378, 0.2006] | 0.00 | 3.00 |
| Winner-XFG - XFG feature mask | 3 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0398 | 0.1200 [0.0929, 0.1470] | 0.00 | 0.00 |
| Random graph - edge add | 5 | 580/580 | 100.0% | 9 | 3.0% | [0.9%, 5.1%] | -0.0402 | 0.0799 [0.0658, 0.0939] | 0.00 | 5.00 |
| Random graph - edge delete | 5 | 444/580 | 76.6% | 13 | 5.5% | [3.7%, 7.2%] | -0.0084 | 0.0657 [0.0485, 0.0828] | 0.00 | 5.00 |
| Random graph - edge reconnect | 5 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0582 | 0.0825 [0.0687, 0.0964] | 0.00 | 0.00 |
| Random graph - node add | 5 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0039 | 0.0531 [0.0434, 0.0629] | 5.00 | 5.00 |
| Random graph - node attribute modify | 5 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0371 | 0.1091 [0.0928, 0.1254] | 0.00 | 0.00 |
| Random graph - node delete | 5 | 431/580 | 74.3% | 15 | 6.4% | [3.6%, 9.3%] | +0.0153 | 0.0865 [0.0667, 0.1064] | 4.84 | 14.90 |
| Winner-XFG - targeted subgraph injection | 5 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0224 | 0.1362 [0.1092, 0.1633] | 15.00 | 20.00 |
| Winner-XFG - XFG edge attack | 5 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0241 | 0.1710 [0.1391, 0.2030] | 0.00 | 5.00 |
| Winner-XFG - XFG feature mask | 5 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0239 | 0.1395 [0.1115, 0.1675] | 0.00 | 0.00 |
| Random graph - edge add | 7 | 580/580 | 100.0% | 12 | 4.0% | [2.1%, 5.9%] | -0.0550 | 0.0988 [0.0835, 0.1141] | 0.00 | 7.00 |
| Random graph - edge delete | 7 | 418/580 | 72.1% | 16 | 7.2% | [5.2%, 9.1%] | +0.0055 | 0.0778 [0.0579, 0.0976] | 0.00 | 7.00 |
| Random graph - edge reconnect | 7 | 573/580 | 98.8% | 7 | 2.4% | [1.0%, 3.8%] | -0.0539 | 0.0922 [0.0776, 0.1067] | 0.00 | 0.00 |
| Random graph - node add | 7 | 580/580 | 100.0% | 7 | 2.3% | [0.6%, 4.0%] | -0.0025 | 0.0668 [0.0548, 0.0789] | 7.00 | 7.00 |
| Random graph - node attribute modify | 7 | 580/580 | 100.0% | 20 | 6.7% | [5.3%, 8.0%] | -0.0341 | 0.1300 [0.1119, 0.1482] | 0.00 | 0.00 |
| Random graph - node delete | 7 | 413/580 | 71.2% | 17 | 7.5% | [6.1%, 8.8%] | +0.0110 | 0.0989 [0.0778, 0.1199] | 6.25 | 19.97 |
| Winner-XFG - targeted subgraph injection | 7 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0248 | 0.1484 [0.1210, 0.1758] | 21.00 | 28.00 |
| Winner-XFG - XFG edge attack | 7 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0374 | 0.1720 [0.1381, 0.2059] | 0.00 | 6.93 |
| Winner-XFG - XFG feature mask | 7 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0157 | 0.1477 [0.1178, 0.1775] | 0.00 | 0.00 |
| Random graph - edge add | 9 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0663 | 0.1040 [0.0882, 0.1199] | 0.00 | 9.00 |
| Random graph - edge delete | 9 | 384/580 | 66.2% | 8 | 4.1% | [1.2%, 6.9%] | +0.0250 | 0.0871 [0.0661, 0.1081] | 0.00 | 9.00 |
| Random graph - edge reconnect | 9 | 580/580 | 100.0% | 10 | 3.3% | [1.6%, 5.0%] | -0.0522 | 0.1011 [0.0853, 0.1168] | 0.00 | 0.00 |
| Random graph - node add | 9 | 580/580 | 100.0% | 11 | 3.7% | [1.6%, 5.7%] | -0.0004 | 0.0825 [0.0688, 0.0962] | 9.00 | 9.00 |
| Random graph - node attribute modify | 9 | 580/580 | 100.0% | 22 | 7.3% | [5.0%, 9.7%] | -0.0326 | 0.1402 [0.1215, 0.1589] | 0.00 | 0.00 |
| Random graph - node delete | 9 | 406/580 | 70.0% | 21 | 9.3% | [7.7%, 10.9%] | +0.0289 | 0.1079 [0.0873, 0.1284] | 7.40 | 24.08 |
| Winner-XFG - targeted subgraph injection | 9 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0248 | 0.1562 [0.1286, 0.1837] | 27.00 | 36.00 |
| Winner-XFG - XFG edge attack | 9 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0526 | 0.1913 [0.1574, 0.2252] | 0.00 | 8.80 |
| Winner-XFG - XFG feature mask | 9 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1146, 0.1722] | 0.00 | 0.00 |
| Random graph - edge add | 11 | 580/580 | 100.0% | 11 | 3.7% | [2.1%, 5.2%] | -0.0783 | 0.1117 [0.0954, 0.1280] | 0.00 | 10.98 |
| Random graph - edge delete | 11 | 373/580 | 64.3% | 7 | 3.7% | [1.0%, 6.5%] | +0.0238 | 0.1066 [0.0827, 0.1306] | 0.00 | 11.00 |
| Random graph - edge reconnect | 11 | 578/580 | 99.7% | 8 | 2.7% | [1.4%, 4.0%] | -0.0499 | 0.0961 [0.0806, 0.1115] | 0.00 | 0.00 |
| Random graph - node add | 11 | 580/580 | 100.0% | 11 | 3.7% | [1.6%, 5.7%] | -0.0012 | 0.0872 [0.0727, 0.1017] | 11.00 | 11.00 |
| Random graph - node attribute modify | 11 | 580/580 | 100.0% | 21 | 7.0% | [4.9%, 9.1%] | -0.0293 | 0.1530 [0.1335, 0.1726] | 0.00 | 0.00 |
| Random graph - node delete | 11 | 402/580 | 69.3% | 18 | 8.1% | [6.3%, 9.9%] | +0.0342 | 0.1152 [0.0946, 0.1359] | 8.39 | 27.71 |
| Winner-XFG - targeted subgraph injection | 11 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0292 | 0.1548 [0.1268, 0.1829] | 33.00 | 44.00 |
| Winner-XFG - XFG edge attack | 11 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0727 | 0.1859 [0.1531, 0.2187] | 0.00 | 10.63 |
| Winner-XFG - XFG feature mask | 11 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1147, 0.1722] | 0.00 | 0.00 |
| Random graph - edge add | 13 | 580/580 | 100.0% | 12 | 4.0% | [2.4%, 5.6%] | -0.0842 | 0.1218 [0.1045, 0.1390] | 0.00 | 12.95 |
| Random graph - edge delete | 13 | 345/580 | 59.5% | 6 | 3.6% | [1.0%, 6.3%] | +0.0191 | 0.1223 [0.0960, 0.1486] | 0.00 | 13.00 |
| Random graph - edge reconnect | 13 | 578/580 | 99.7% | 10 | 3.3% | [1.7%, 5.0%] | -0.0629 | 0.1047 [0.0887, 0.1207] | 0.00 | 0.00 |
| Random graph - node add | 13 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0063 | 0.0890 [0.0742, 0.1038] | 13.00 | 13.00 |
| Random graph - node attribute modify | 13 | 580/580 | 100.0% | 23 | 7.7% | [5.1%, 10.3%] | -0.0339 | 0.1524 [0.1322, 0.1725] | 0.00 | 0.00 |
| Random graph - node delete | 13 | 399/580 | 68.8% | 25 | 11.4% | [9.9%, 13.0%] | +0.0419 | 0.1290 [0.1065, 0.1515] | 9.32 | 31.08 |
| Winner-XFG - targeted subgraph injection | 13 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0278 | 0.1559 [0.1274, 0.1843] | 39.00 | 52.00 |
| Winner-XFG - XFG edge attack | 13 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0760 | 0.1828 [0.1525, 0.2131] | 0.00 | 12.43 |
| Winner-XFG - XFG feature mask | 13 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0200 | 0.1434 [0.1146, 0.1722] | 0.00 | 0.00 |
| Random graph - edge add | 15 | 580/580 | 100.0% | 14 | 4.7% | [2.7%, 6.7%] | -0.0895 | 0.1303 [0.1126, 0.1481] | 0.00 | 14.88 |
| Random graph - edge delete | 15 | 324/580 | 55.9% | 7 | 4.5% | [1.9%, 7.2%] | +0.0169 | 0.1396 [0.1110, 0.1682] | 0.00 | 15.00 |
| Random graph - edge reconnect | 15 | 571/580 | 98.4% | 9 | 3.0% | [1.5%, 4.5%] | -0.0533 | 0.0874 [0.0720, 0.1028] | 0.00 | 0.00 |
| Random graph - node add | 15 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0070 | 0.0948 [0.0793, 0.1103] | 15.00 | 15.00 |
| Random graph - node attribute modify | 15 | 580/580 | 100.0% | 28 | 9.3% | [6.6%, 12.1%] | -0.0273 | 0.1508 [0.1310, 0.1706] | 0.00 | 0.00 |
| Random graph - node delete | 15 | 398/580 | 68.6% | 25 | 11.5% | [9.9%, 13.1%] | +0.0390 | 0.1276 [0.1056, 0.1497] | 10.20 | 34.17 |
| Winner-XFG - targeted subgraph injection | 15 | 300/300 | 100.0% | 20 | 6.7% | [6.7%, 6.7%] | -0.0271 | 0.1585 [0.1296, 0.1874] | 45.00 | 60.00 |
| Winner-XFG - XFG edge attack | 15 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0654 | 0.1706 [0.1412, 0.1999] | 0.00 | 14.23 |
| Winner-XFG - XFG feature mask | 15 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0201 | 0.1433 [0.1145, 0.1721] | 0.00 | 0.00 |
| Random graph - edge add | 20 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0996 | 0.1429 [0.1247, 0.1611] | 0.00 | 19.22 |
| Random graph - edge delete | 20 | 310/580 | 53.4% | 9 | 6.0% | [2.4%, 9.6%] | +0.0475 | 0.1473 [0.1184, 0.1762] | 0.00 | 20.00 |
| Random graph - edge reconnect | 20 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0651 | 0.1041 [0.0876, 0.1206] | 0.00 | 0.00 |
| Random graph - node add | 20 | 580/580 | 100.0% | 17 | 5.7% | [4.0%, 7.4%] | -0.0135 | 0.1052 [0.0890, 0.1214] | 20.00 | 20.00 |
| Random graph - node attribute modify | 20 | 580/580 | 100.0% | 37 | 12.3% | [9.9%, 14.7%] | -0.0171 | 0.1736 [0.1525, 0.1947] | 0.00 | 0.00 |
| Random graph - node delete | 20 | 387/580 | 66.7% | 26 | 12.6% | [10.9%, 14.2%] | +0.0434 | 0.1369 [0.1140, 0.1598] | 11.91 | 39.64 |
| Winner-XFG - targeted subgraph injection | 20 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0261 | 0.1641 [0.1343, 0.1938] | 60.00 | 80.00 |
| Winner-XFG - XFG edge attack | 20 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0902 | 0.1638 [0.1362, 0.1913] | 0.00 | 18.33 |
| Winner-XFG - XFG feature mask | 20 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0191 | 0.1443 [0.1154, 0.1733] | 0.00 | 0.00 |
| Random graph - edge add | 25 | 580/580 | 100.0% | 12 | 4.0% | [2.4%, 5.6%] | -0.1060 | 0.1495 [0.1308, 0.1681] | 0.00 | 23.43 |
| Random graph - edge delete | 25 | 276/580 | 47.6% | 5 | 3.8% | [0.0%, 8.5%] | +0.0639 | 0.1217 [0.0934, 0.1501] | 0.00 | 25.00 |
| Random graph - edge reconnect | 25 | 576/580 | 99.3% | 10 | 3.4% | [1.4%, 5.4%] | -0.0762 | 0.1118 [0.0952, 0.1283] | 0.00 | 0.00 |
| Random graph - node add | 25 | 580/580 | 100.0% | 20 | 6.7% | [5.3%, 8.0%] | -0.0098 | 0.1161 [0.0993, 0.1330] | 25.00 | 25.00 |
| Random graph - node attribute modify | 25 | 580/580 | 100.0% | 40 | 13.3% | [10.8%, 15.9%] | -0.0104 | 0.1724 [0.1514, 0.1934] | 0.00 | 0.00 |
| Random graph - node delete | 25 | 380/580 | 65.5% | 31 | 15.5% | [14.5%, 16.5%] | +0.0436 | 0.1456 [0.1222, 0.1690] | 13.16 | 43.37 |
| Winner-XFG - targeted subgraph injection | 25 | 300/300 | 100.0% | 40 | 13.3% | [13.3%, 13.3%] | -0.0259 | 0.1697 [0.1394, 0.1999] | 75.00 | 100.00 |
| Winner-XFG - XFG edge attack | 25 | 300/300 | 100.0% | 30 | 10.0% | [10.0%, 10.0%] | -0.0940 | 0.1606 [0.1334, 0.1878] | 0.00 | 22.33 |
| Winner-XFG - XFG feature mask | 25 | 300/300 | 100.0% | 50 | 16.7% | [16.7%, 16.7%] | -0.0191 | 0.1443 [0.1154, 0.1733] | 0.00 | 0.00 |
