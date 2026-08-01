# Experiment Analysis / 实验分析

**Run / 实验：** Random graph perturbation report: run_20260731_124703_code_all_input_sources<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：58（Samples）。
- 尝试生成的变体：34800；有效评分对比：31404；不可应用或不完整：3396。
- 观测到的成功攻击：789。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

- 在预算 1 下，观测到的最高ASR为：edge add: 2.0% (6/300, 95% CI [0.6%, 3.4%])。
- 在预算 3 下，观测到的最高ASR为：edge add: 4.0% (12/300, 95% CI [2.7%, 5.3%])。
- 在预算 5 下，观测到的最高ASR为：node delete: 6.4% (15/232, 95% CI [3.6%, 9.3%])。
- 在预算 7 下，观测到的最高ASR为：node delete: 7.5% (17/228, 95% CI [6.1%, 8.8%])。
- 在预算 9 下，观测到的最高ASR为：node delete: 9.3% (21/226, 95% CI [7.7%, 10.9%])。
- 在预算 11 下，观测到的最高ASR为：node delete: 8.1% (18/222, 95% CI [6.3%, 9.9%])。
- 在预算 13 下，观测到的最高ASR为：node delete: 11.4% (25/219, 95% CI [9.9%, 13.0%])。
- 在预算 15 下，观测到的最高ASR为：node delete: 11.5% (25/218, 95% CI [9.9%, 13.1%])。
- 在预算 20 下，观测到的最高ASR为：node delete: 12.6% (26/207, 95% CI [10.9%, 14.2%])。
- 在预算 25 下，观测到的最高ASR为：node delete: 15.5% (31/200, 95% CI [14.5%, 16.5%])。
- edge add 的预算响应呈非单调模式（B1=2.0% -> B3=4.0% -> B5=3.0% -> B7=4.0% -> B9=3.3% -> B11=3.7% -> B13=4.0% -> B15=4.7% -> B20=4.3% -> B25=4.0%）。
- edge delete 的预算响应呈非单调模式（B1=0.7% -> B3=2.9% -> B5=5.5% -> B7=7.2% -> B9=4.1% -> B11=3.7% -> B13=3.6% -> B15=4.5% -> B20=6.0% -> B25=3.8%）。
- edge reconnect 的预算响应呈非单调模式（B1=1.3% -> B3=2.3% -> B5=2.3% -> B7=2.4% -> B9=3.3% -> B11=2.7% -> B13=3.3% -> B15=3.0% -> B20=4.3% -> B25=3.4%）。
- node add 的预算响应呈非递减模式（B1=0.0% -> B3=0.7% -> B5=1.3% -> B7=2.3% -> B9=3.7% -> B11=3.7% -> B13=4.3% -> B15=5.3% -> B20=5.7% -> B25=6.7%）。
- node attribute modify 的预算响应呈非单调模式（B1=1.3% -> B3=3.3% -> B5=5.3% -> B7=6.7% -> B9=7.3% -> B11=7.0% -> B13=7.7% -> B15=9.3% -> B20=12.3% -> B25=13.3%）。
- node delete 的预算响应呈非单调模式（B1=1.3% -> B3=3.4% -> B5=6.4% -> B7=7.5% -> B9=9.3% -> B11=8.1% -> B13=11.4% -> B15=11.5% -> B20=12.6% -> B25=15.5%）。
- 覆盖率提示：edge delete 的有效评分样本少于尝试样本的一半，其估计值对完整输入集的代表性较弱。
- edge delete（预算 25） 的平均预测概率向上变化最大（+0.0639）；edge add（预算 25） 的平均预测概率向下变化最大（-0.1060）。
- node add（预算 25） 的平均绝对节点变化最大（25.00）；node delete（预算 25） 的平均绝对边变化最大（43.37）。

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: 58 (Samples).
- Attempted variants: 34800; scored comparisons: 31404; not applicable or incomplete: 3396.
- Observed successful attacks: 789.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

- At budget 1, the highest observed ASR is: edge add: 2.0% (6/300, 95% CI [0.6%, 3.4%]).
- At budget 3, the highest observed ASR is: edge add: 4.0% (12/300, 95% CI [2.7%, 5.3%]).
- At budget 5, the highest observed ASR is: node delete: 6.4% (15/232, 95% CI [3.6%, 9.3%]).
- At budget 7, the highest observed ASR is: node delete: 7.5% (17/228, 95% CI [6.1%, 8.8%]).
- At budget 9, the highest observed ASR is: node delete: 9.3% (21/226, 95% CI [7.7%, 10.9%]).
- At budget 11, the highest observed ASR is: node delete: 8.1% (18/222, 95% CI [6.3%, 9.9%]).
- At budget 13, the highest observed ASR is: node delete: 11.4% (25/219, 95% CI [9.9%, 13.0%]).
- At budget 15, the highest observed ASR is: node delete: 11.5% (25/218, 95% CI [9.9%, 13.1%]).
- At budget 20, the highest observed ASR is: node delete: 12.6% (26/207, 95% CI [10.9%, 14.2%]).
- At budget 25, the highest observed ASR is: node delete: 15.5% (31/200, 95% CI [14.5%, 16.5%]).
- edge add has an observed non-monotonic budget response (B1=2.0% -> B3=4.0% -> B5=3.0% -> B7=4.0% -> B9=3.3% -> B11=3.7% -> B13=4.0% -> B15=4.7% -> B20=4.3% -> B25=4.0%).
- edge delete has an observed non-monotonic budget response (B1=0.7% -> B3=2.9% -> B5=5.5% -> B7=7.2% -> B9=4.1% -> B11=3.7% -> B13=3.6% -> B15=4.5% -> B20=6.0% -> B25=3.8%).
- edge reconnect has an observed non-monotonic budget response (B1=1.3% -> B3=2.3% -> B5=2.3% -> B7=2.4% -> B9=3.3% -> B11=2.7% -> B13=3.3% -> B15=3.0% -> B20=4.3% -> B25=3.4%).
- node add has an observed non-decreasing budget response (B1=0.0% -> B3=0.7% -> B5=1.3% -> B7=2.3% -> B9=3.7% -> B11=3.7% -> B13=4.3% -> B15=5.3% -> B20=5.7% -> B25=6.7%).
- node attribute modify has an observed non-monotonic budget response (B1=1.3% -> B3=3.3% -> B5=5.3% -> B7=6.7% -> B9=7.3% -> B11=7.0% -> B13=7.7% -> B15=9.3% -> B20=12.3% -> B25=13.3%).
- node delete has an observed non-monotonic budget response (B1=1.3% -> B3=3.4% -> B5=6.4% -> B7=7.5% -> B9=9.3% -> B11=8.1% -> B13=11.4% -> B15=11.5% -> B20=12.6% -> B25=15.5%).
- Coverage warning: edge delete were scored on fewer than half of attempted cases; their estimates are less representative of the full input set.
- edge delete at budget 25 has the largest upward mean probability shift (+0.0639); edge add at budget 25 has the largest downward shift (-0.1060).
- node add at budget 25 has the largest mean absolute node change (25.00); node delete at budget 25 has the largest mean absolute edge change (43.37).

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
| 有效性 / Effectiveness | 在所有已观测的方法–Budget组合中，node delete（Budget 25） 的观测攻击成功率最高，为15.5%（31/200）。这是本次run的描述性最高值；跨Budget的最高值不能被解释为只由方法差异造成，也不等于已证明总体显著更优。 | Across all observed method–budget combinations, node delete at budget 25 has the highest observed attack success rate: 15.5% (31/200). This is the descriptive maximum in this run; a maximum across budgets cannot be attributed to method alone and does not prove population-level superiority. |
| Budget响应 / Budget response | node delete 从Budget 1到25的端点变化幅度最大：1.3% → 15.5%，即上升14.2%。端点差异概括总体变化，但不能替代对中间Budget是否单调的逐点检查。 | node delete has the largest endpoint change from budget 1 to 25: 1.3% → 15.5%, an absolute increase of 14.2%. The endpoint contrast summarizes the overall shift but does not replace checking whether intermediate budgets are monotonic. |
| 效应幅度 / Effect magnitude | node attribute modify（Budget 20） 的平均绝对概率变化最大，为0.1736。这表示模型分数平均被推动得最远，但不说明推动方向，也不保证最终分类翻转。 | node attribute modify at budget 20 has the largest mean absolute probability change, 0.1736. This means it moves model scores farthest on average, but says neither the direction nor that the final class flips. |
| 效应方向 / Effect direction | edge delete（Budget 25） 的平均向上变化最大（+0.0639）；edge add（Budget 25） 的平均向下变化最大（-0.1060）。方向表示漏洞预测概率相对基线升降，不直接等同于攻击是否成功。 | edge delete at budget 25 has the largest upward mean shift (+0.0639); edge add at budget 25 has the largest downward mean shift (-0.1060). Direction describes movement in predicted vulnerability probability relative to baseline and is not itself attack success. |
| 样本级分布 / Sample-level distribution | 所有方法–Budget箱体的中位数在四位小数精度下都接近零，未显示典型样本稳定地向某一方向移动；edge add（Budget 20） 的箱体IQR最宽（0.1904）。中位数描述典型样本的方向和幅度，IQR表示中间50%样本的反应一致性；须线极值不能单独证明稳定攻击效果。 | All method–budget boxplot medians are near zero at four-decimal precision, so the typical sample does not show a stable directional shift; edge add at budget 20 has the widest box IQR (0.1904). The median describes the direction and magnitude of a typical sample, while IQR describes consistency in the middle 50%. Whisker extremes alone do not establish a stable attack effect. |
| 适用性 / Applicability | edge delete（Budget 25） 的覆盖率最低，为47.6%（276/580）。覆盖率低意味着效果估计只来自较小的可成功运行子集。 | edge delete at budget 25 has the lowest coverage, 47.6% (276/580). Low coverage means the effect estimate comes from a smaller successfully executed subset. |
| 结构变化 / Realised structural change | node add（Budget 25） 的平均绝对节点变化最大（25.00）；node delete（Budget 25） 的平均绝对边变化最大（43.37）。它们说明扰动实际改了多少结构，不等于模型受影响程度。 | node add at budget 25 has the largest mean absolute node change (25.00); node delete at budget 25 has the largest mean absolute edge change (43.37). These values quantify realised structural change, not how strongly the model was affected. |


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
| edge add | 1 | 580/580 | 100.0% | 6 | 2.0% | [0.6%, 3.4%] | -0.0140 | 0.0401 [0.0313, 0.0488] | 0.00 | 1.00 |
| edge delete | 1 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 1.5%] | +0.0121 | 0.0258 [0.0190, 0.0327] | 0.00 | 1.00 |
| edge reconnect | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0178 | 0.0589 [0.0469, 0.0708] | 0.00 | 0.00 |
| node add | 1 | 580/580 | 100.0% | 0 | 0.0% | [0.0%, 0.0%] | -0.0017 | 0.0052 [0.0021, 0.0082] | 1.00 | 1.00 |
| node attribute modify | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0087 | 0.0380 [0.0285, 0.0475] | 0.00 | 0.00 |
| node delete | 1 | 580/580 | 100.0% | 4 | 1.3% | [0.3%, 2.4%] | -0.0115 | 0.0482 [0.0366, 0.0598] | 1.00 | 2.78 |
| edge add | 3 | 580/580 | 100.0% | 12 | 4.0% | [2.7%, 5.3%] | -0.0181 | 0.0700 [0.0579, 0.0820] | 0.00 | 3.00 |
| edge delete | 3 | 540/580 | 93.1% | 8 | 2.9% | [1.1%, 4.7%] | -0.0212 | 0.0707 [0.0569, 0.0845] | 0.00 | 3.00 |
| edge reconnect | 3 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0374 | 0.0694 [0.0568, 0.0821] | 0.00 | 0.00 |
| node add | 3 | 580/580 | 100.0% | 2 | 0.7% | [0.0%, 2.0%] | +0.0060 | 0.0279 [0.0208, 0.0350] | 3.00 | 3.00 |
| node attribute modify | 3 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0188 | 0.0912 [0.0763, 0.1061] | 0.00 | 0.00 |
| node delete | 3 | 442/580 | 76.2% | 8 | 3.4% | [1.0%, 5.8%] | +0.0080 | 0.0668 [0.0486, 0.0851] | 2.98 | 9.27 |
| edge add | 5 | 580/580 | 100.0% | 9 | 3.0% | [0.9%, 5.1%] | -0.0402 | 0.0799 [0.0658, 0.0939] | 0.00 | 5.00 |
| edge delete | 5 | 444/580 | 76.6% | 13 | 5.5% | [3.7%, 7.2%] | -0.0084 | 0.0657 [0.0485, 0.0828] | 0.00 | 5.00 |
| edge reconnect | 5 | 578/580 | 99.7% | 7 | 2.3% | [0.9%, 3.7%] | -0.0582 | 0.0825 [0.0687, 0.0964] | 0.00 | 0.00 |
| node add | 5 | 580/580 | 100.0% | 4 | 1.3% | [0.0%, 2.8%] | -0.0039 | 0.0531 [0.0434, 0.0629] | 5.00 | 5.00 |
| node attribute modify | 5 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0371 | 0.1091 [0.0928, 0.1254] | 0.00 | 0.00 |
| node delete | 5 | 431/580 | 74.3% | 15 | 6.4% | [3.6%, 9.3%] | +0.0153 | 0.0865 [0.0667, 0.1064] | 4.84 | 14.90 |
| edge add | 7 | 580/580 | 100.0% | 12 | 4.0% | [2.1%, 5.9%] | -0.0550 | 0.0988 [0.0835, 0.1141] | 0.00 | 7.00 |
| edge delete | 7 | 418/580 | 72.1% | 16 | 7.2% | [5.2%, 9.1%] | +0.0055 | 0.0778 [0.0579, 0.0976] | 0.00 | 7.00 |
| edge reconnect | 7 | 573/580 | 98.8% | 7 | 2.4% | [1.0%, 3.8%] | -0.0539 | 0.0922 [0.0776, 0.1067] | 0.00 | 0.00 |
| node add | 7 | 580/580 | 100.0% | 7 | 2.3% | [0.6%, 4.0%] | -0.0025 | 0.0668 [0.0548, 0.0789] | 7.00 | 7.00 |
| node attribute modify | 7 | 580/580 | 100.0% | 20 | 6.7% | [5.3%, 8.0%] | -0.0341 | 0.1300 [0.1119, 0.1482] | 0.00 | 0.00 |
| node delete | 7 | 413/580 | 71.2% | 17 | 7.5% | [6.1%, 8.8%] | +0.0110 | 0.0989 [0.0778, 0.1199] | 6.25 | 19.97 |
| edge add | 9 | 580/580 | 100.0% | 10 | 3.3% | [1.4%, 5.3%] | -0.0663 | 0.1040 [0.0882, 0.1199] | 0.00 | 9.00 |
| edge delete | 9 | 384/580 | 66.2% | 8 | 4.1% | [1.2%, 6.9%] | +0.0250 | 0.0871 [0.0661, 0.1081] | 0.00 | 9.00 |
| edge reconnect | 9 | 580/580 | 100.0% | 10 | 3.3% | [1.6%, 5.0%] | -0.0522 | 0.1011 [0.0853, 0.1168] | 0.00 | 0.00 |
| node add | 9 | 580/580 | 100.0% | 11 | 3.7% | [1.6%, 5.7%] | -0.0004 | 0.0825 [0.0688, 0.0962] | 9.00 | 9.00 |
| node attribute modify | 9 | 580/580 | 100.0% | 22 | 7.3% | [5.0%, 9.7%] | -0.0326 | 0.1402 [0.1215, 0.1589] | 0.00 | 0.00 |
| node delete | 9 | 406/580 | 70.0% | 21 | 9.3% | [7.7%, 10.9%] | +0.0289 | 0.1079 [0.0873, 0.1284] | 7.40 | 24.08 |
| edge add | 11 | 580/580 | 100.0% | 11 | 3.7% | [2.1%, 5.2%] | -0.0783 | 0.1117 [0.0954, 0.1280] | 0.00 | 10.98 |
| edge delete | 11 | 373/580 | 64.3% | 7 | 3.7% | [1.0%, 6.5%] | +0.0238 | 0.1066 [0.0827, 0.1306] | 0.00 | 11.00 |
| edge reconnect | 11 | 578/580 | 99.7% | 8 | 2.7% | [1.4%, 4.0%] | -0.0499 | 0.0961 [0.0806, 0.1115] | 0.00 | 0.00 |
| node add | 11 | 580/580 | 100.0% | 11 | 3.7% | [1.6%, 5.7%] | -0.0012 | 0.0872 [0.0727, 0.1017] | 11.00 | 11.00 |
| node attribute modify | 11 | 580/580 | 100.0% | 21 | 7.0% | [4.9%, 9.1%] | -0.0293 | 0.1530 [0.1335, 0.1726] | 0.00 | 0.00 |
| node delete | 11 | 402/580 | 69.3% | 18 | 8.1% | [6.3%, 9.9%] | +0.0342 | 0.1152 [0.0946, 0.1359] | 8.39 | 27.71 |
| edge add | 13 | 580/580 | 100.0% | 12 | 4.0% | [2.4%, 5.6%] | -0.0842 | 0.1218 [0.1045, 0.1390] | 0.00 | 12.95 |
| edge delete | 13 | 345/580 | 59.5% | 6 | 3.6% | [1.0%, 6.3%] | +0.0191 | 0.1223 [0.0960, 0.1486] | 0.00 | 13.00 |
| edge reconnect | 13 | 578/580 | 99.7% | 10 | 3.3% | [1.7%, 5.0%] | -0.0629 | 0.1047 [0.0887, 0.1207] | 0.00 | 0.00 |
| node add | 13 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0063 | 0.0890 [0.0742, 0.1038] | 13.00 | 13.00 |
| node attribute modify | 13 | 580/580 | 100.0% | 23 | 7.7% | [5.1%, 10.3%] | -0.0339 | 0.1524 [0.1322, 0.1725] | 0.00 | 0.00 |
| node delete | 13 | 399/580 | 68.8% | 25 | 11.4% | [9.9%, 13.0%] | +0.0419 | 0.1290 [0.1065, 0.1515] | 9.32 | 31.08 |
| edge add | 15 | 580/580 | 100.0% | 14 | 4.7% | [2.7%, 6.7%] | -0.0895 | 0.1303 [0.1126, 0.1481] | 0.00 | 14.88 |
| edge delete | 15 | 324/580 | 55.9% | 7 | 4.5% | [1.9%, 7.2%] | +0.0169 | 0.1396 [0.1110, 0.1682] | 0.00 | 15.00 |
| edge reconnect | 15 | 571/580 | 98.4% | 9 | 3.0% | [1.5%, 4.5%] | -0.0533 | 0.0874 [0.0720, 0.1028] | 0.00 | 0.00 |
| node add | 15 | 580/580 | 100.0% | 16 | 5.3% | [3.6%, 7.1%] | -0.0070 | 0.0948 [0.0793, 0.1103] | 15.00 | 15.00 |
| node attribute modify | 15 | 580/580 | 100.0% | 28 | 9.3% | [6.6%, 12.1%] | -0.0273 | 0.1508 [0.1310, 0.1706] | 0.00 | 0.00 |
| node delete | 15 | 398/580 | 68.6% | 25 | 11.5% | [9.9%, 13.1%] | +0.0390 | 0.1276 [0.1056, 0.1497] | 10.20 | 34.17 |
| edge add | 20 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0996 | 0.1429 [0.1247, 0.1611] | 0.00 | 19.22 |
| edge delete | 20 | 310/580 | 53.4% | 9 | 6.0% | [2.4%, 9.6%] | +0.0475 | 0.1473 [0.1184, 0.1762] | 0.00 | 20.00 |
| edge reconnect | 20 | 580/580 | 100.0% | 13 | 4.3% | [2.4%, 6.3%] | -0.0651 | 0.1041 [0.0876, 0.1206] | 0.00 | 0.00 |
| node add | 20 | 580/580 | 100.0% | 17 | 5.7% | [4.0%, 7.4%] | -0.0135 | 0.1052 [0.0890, 0.1214] | 20.00 | 20.00 |
| node attribute modify | 20 | 580/580 | 100.0% | 37 | 12.3% | [9.9%, 14.7%] | -0.0171 | 0.1736 [0.1525, 0.1947] | 0.00 | 0.00 |
| node delete | 20 | 387/580 | 66.7% | 26 | 12.6% | [10.9%, 14.2%] | +0.0434 | 0.1369 [0.1140, 0.1598] | 11.91 | 39.64 |
| edge add | 25 | 580/580 | 100.0% | 12 | 4.0% | [2.4%, 5.6%] | -0.1060 | 0.1495 [0.1308, 0.1681] | 0.00 | 23.43 |
| edge delete | 25 | 276/580 | 47.6% | 5 | 3.8% | [0.0%, 8.5%] | +0.0639 | 0.1217 [0.0934, 0.1501] | 0.00 | 25.00 |
| edge reconnect | 25 | 576/580 | 99.3% | 10 | 3.4% | [1.4%, 5.4%] | -0.0762 | 0.1118 [0.0952, 0.1283] | 0.00 | 0.00 |
| node add | 25 | 580/580 | 100.0% | 20 | 6.7% | [5.3%, 8.0%] | -0.0098 | 0.1161 [0.0993, 0.1330] | 25.00 | 25.00 |
| node attribute modify | 25 | 580/580 | 100.0% | 40 | 13.3% | [10.8%, 15.9%] | -0.0104 | 0.1724 [0.1514, 0.1934] | 0.00 | 0.00 |
| node delete | 25 | 380/580 | 65.5% | 31 | 15.5% | [14.5%, 16.5%] | +0.0436 | 0.1456 [0.1222, 0.1690] | 13.16 | 43.37 |
