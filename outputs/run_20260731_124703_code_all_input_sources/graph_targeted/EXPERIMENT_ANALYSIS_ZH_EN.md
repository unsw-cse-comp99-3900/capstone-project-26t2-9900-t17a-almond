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

## Chart-by-chart Conclusions / 各图表推论

以下推论由当前run的数据自动生成，并与Dashboard中的控制变量图一一对应；它们保留描述性边界，不替代显著性检验。
The conclusions below are generated from this run and correspond to the controlled-variable charts in the dashboard; they remain descriptive and do not replace significance tests.

| 图表 / Chart | 中文推论 | English inference |
|---|---|---|
| 有效性 / Effectiveness | 在所有已观测的方法–Budget组合中，XFG edge attack（Budget 3） 的观测攻击成功率最高，为23.3%（70/300）。这是本次run的描述性最高值；跨Budget的最高值不能被解释为只由方法差异造成，也不等于已证明总体显著更优。 | Across all observed method–budget combinations, XFG edge attack at budget 3 has the highest observed attack success rate: 23.3% (70/300). This is the descriptive maximum in this run; a maximum across budgets cannot be attributed to method alone and does not prove population-level superiority. |
| Budget响应 / Budget response | targeted subgraph injection 从Budget 1到25的端点变化幅度最大：6.7% → 13.3%，即上升6.7%。端点差异概括总体变化，但不能替代对中间Budget是否单调的逐点检查。 | targeted subgraph injection has the largest endpoint change from budget 1 to 25: 6.7% → 13.3%, an absolute increase of 6.7%. The endpoint contrast summarizes the overall shift but does not replace checking whether intermediate budgets are monotonic. |
| 效应幅度 / Effect magnitude | XFG edge attack（Budget 9） 的平均绝对概率变化最大，为0.1913。这表示模型分数平均被推动得最远，但不说明推动方向，也不保证最终分类翻转。 | XFG edge attack at budget 9 has the largest mean absolute probability change, 0.1913. This means it moves model scores farthest on average, but says neither the direction nor that the final class flips. |
| 效应方向 / Effect direction | targeted subgraph injection（Budget 1） 的平均向上变化最大（+0.0059）；XFG edge attack（Budget 25） 的平均向下变化最大（-0.0940）。方向表示漏洞预测概率相对基线升降，不直接等同于攻击是否成功。 | targeted subgraph injection at budget 1 has the largest upward mean shift (+0.0059); XFG edge attack at budget 25 has the largest downward mean shift (-0.0940). Direction describes movement in predicted vulnerability probability relative to baseline and is not itself attack success. |
| 样本级分布 / Sample-level distribution | 所有方法–Budget箱体的中位数在四位小数精度下都接近零，未显示典型样本稳定地向某一方向移动；XFG edge attack（Budget 13） 的箱体IQR最宽（0.1930）。中位数描述典型样本的方向和幅度，IQR表示中间50%样本的反应一致性；须线极值不能单独证明稳定攻击效果。 | All method–budget boxplot medians are near zero at four-decimal precision, so the typical sample does not show a stable directional shift; XFG edge attack at budget 13 has the widest box IQR (0.1930). The median describes the direction and magnitude of a typical sample, while IQR describes consistency in the middle 50%. Whisker extremes alone do not establish a stable attack effect. |
| 适用性 / Applicability | targeted subgraph injection（Budget 1） 的覆盖率最低，为100.0%（300/300）。覆盖率低意味着效果估计只来自较小的可成功运行子集。 | targeted subgraph injection at budget 1 has the lowest coverage, 100.0% (300/300). Low coverage means the effect estimate comes from a smaller successfully executed subset. |
| 结构变化 / Realised structural change | targeted subgraph injection（Budget 25） 的平均绝对节点变化最大（75.00）；targeted subgraph injection（Budget 25） 的平均绝对边变化最大（100.00）。它们说明扰动实际改了多少结构，不等于模型受影响程度。 | targeted subgraph injection at budget 25 has the largest mean absolute node change (75.00); targeted subgraph injection at budget 25 has the largest mean absolute edge change (100.00). These values quantify realised structural change, not how strongly the model was affected. |


## Chart Reading Guide / 图表理解对照表

| 中文术语 | English term | 中文理解 | English interpretation |
|---|---|---|---|
| 点估计 | Point estimate | 根据本次有效数据算出的单个比率或均值。它是当前最佳估计，但不是没有误差的真实值。 | The single rate or mean calculated from scored data. It is the best estimate from this run, not an error-free population truth. |
| 竖向柱状图 | Vertical bar chart | 每根柱代表一种方法，柱高表示观测比率或均值。只有在Budget、样本和模型等条件相同时才适合直接比较。 | Each bar represents one method and its height is the observed rate or mean. Heights are directly comparable only when budget, samples, model, and other controlled conditions are the same. |
| 95%置信区间 | 95% confidence interval | 如果反复进行许多次可比实验并每次按同样方式构造区间，大约95%的区间会覆盖总体真实比率或均值。它不是“95%的样本位于区间中”，也不是“真实值有95%概率在当前区间内”。 | If many comparable experiments were repeated and intervals were constructed the same way, about 95% of those intervals would contain the underlying population rate or mean. It is not the range containing 95% of samples, nor a statement that the fixed true value has a 95% probability of lying in this particular interval. |
| 误差线/端帽线 | Error bar / capped interval | 为提高可读性，当前Dashboard不再把95%置信区间画成柱子或圆点旁的误差线；精确上下界仍保留在“Statistical evidence”统计证据表中。 | For readability, the current dashboard does not draw 95% confidence intervals as error bars beside bars or points; the exact bounds remain in the Statistical evidence table. |
| 有效样本数n | Effective count (n) | `n`是计算点估计时真正使用的有效评分次数。n小通常使区间更宽；多Seed重复不能自动当成更多独立源代码。 | `n` is the number of scoreable observations used for the estimate. Small n usually produces wider intervals; repeated seeds must not automatically be treated as additional independent source programs. |
| 攻击成功率 | Attack Success Rate (ASR) | 在基线预测正确且攻击合格的结果中，扰动实现攻击目标的比例。 | Among baseline-correct, attack-eligible results, the proportion for which the perturbation achieved the attack objective. |
| 预测翻转率 | Prediction Flip Rate | 扰动前后最终分类标签发生变化的比例。翻转可能朝任意方向，因此不一定全部等于攻击成功。 | The proportion whose final class label changed after perturbation. A flip may occur in either direction and is not always equivalent to a successful attack. |
| 效应幅度 | Effect magnitude | 概率变化的绝对值，回答“模型被推动了多远”，不考虑方向，也不要求最终标签翻转。 | The absolute probability change. It answers how far the model moved, regardless of direction or whether the final label flipped. |
| 效应方向 | Effect direction | 带符号的平均概率变化。负值表示模型预测漏洞的概率下降，正值表示上升。 | The signed mean probability change. Negative values lower predicted vulnerability probability; positive values raise it. |
| 零参考线 | Zero reference line | 表示平均没有变化。柱或点位于零线上方或下方，分别代表正向或负向变化。 | Represents no average change. Marks above or below it indicate positive or negative movement. |
| Budget响应折线 | Budget-response line | 固定同一种方法，只改变Budget。连接线用于观察趋势，不表示两个Budget之间所有中间值都被测量。 | Holds the method fixed and changes only budget. The connecting line shows the observed trend and does not imply that every intermediate budget was measured. |
| 箱体Q1–Q3 | Box, Q1 to Q3 | 箱体覆盖中间50%的样本变化，从第25百分位数到第75百分位数。箱体越大，说明样本反应差异越大。 | The box covers the middle 50% of sample changes, from the 25th to the 75th percentile. A larger box indicates greater variation across samples. |
| 中位数 | Median | 箱体内部的粗线；一半样本小于它，另一半大于它，比均值更不容易被极端值拉动。 | The thick line inside the box. Half the observations are below it and half above it; it is less sensitive to extreme values than the mean. |
| 须线 | Whiskers | 当前Dashboard中的须线连接实际观测到的最小值和最大值，不是95%置信区间。 | In this dashboard the whiskers span the observed minimum and maximum; they are not 95% confidence intervals. |
| 覆盖率 | Coverage / applicability | 成功产生完整、可评分结果的尝试比例。高ASR但覆盖率很低的方法可能只对少量特殊样本有效。 | The proportion of attempts producing a complete, scoreable comparison. A method with high ASR but low coverage may work only on a small special subset. |
| 配对共同队列 | Paired common cohort | 只比较Random与Winner-XFG双方都能评分的相同样本、Budget和Seed，减少输入组成不同造成的不公平。 | Compares only sample, budget, and seed keys scoreable by both Random and Winner-XFG, reducing unfairness caused by different input composition. |


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
