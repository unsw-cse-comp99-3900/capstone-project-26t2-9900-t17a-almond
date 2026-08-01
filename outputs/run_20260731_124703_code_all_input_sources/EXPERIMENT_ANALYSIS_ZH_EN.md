# Experiment Analysis / 实验分析

**Run / 实验：** DeepWuKong perturbation report: run_20260731_124703_code_all_input_sources<br>
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

## Chart-by-chart Conclusions / 各图表推论

以下推论由当前run的数据自动生成，并与Dashboard中的控制变量图一一对应；它们保留描述性边界，不替代显著性检验。
The conclusions below are generated from this run and correspond to the controlled-variable charts in the dashboard; they remain descriptive and do not replace significance tests.

| 图表 / Chart | 中文推论 | English inference |
|---|---|---|
| 有效性 / Effectiveness | 在固定设置的方法比较中，sink bound guard 的观测预测翻转率最高，为36.4%（4/11）。这是本次run的描述性最高值；跨Budget的最高值不能被解释为只由方法差异造成，也不等于已证明总体显著更优。 | In the fixed-setting method comparison, sink bound guard has the highest observed prediction flip rate: 36.4% (4/11). This is the descriptive maximum in this run; a maximum across budgets cannot be attributed to method alone and does not prove population-level superiority. |
| 效应幅度 / Effect magnitude | range clamp 的平均绝对概率变化最大，为0.2319。这表示模型分数平均被推动得最远，但不说明推动方向，也不保证最终分类翻转。 | range clamp has the largest mean absolute probability change, 0.2319. This means it moves model scores farthest on average, but says neither the direction nor that the final class flips. |
| 效应方向 / Effect direction | sink bound guard 的平均向上变化最大（+0.0339）；range clamp 的平均向下变化最大（-0.2310）。方向表示漏洞预测概率相对基线升降，不直接等同于攻击是否成功。 | sink bound guard has the largest upward mean shift (+0.0339); range clamp has the largest downward mean shift (-0.2310). Direction describes movement in predicted vulnerability probability relative to baseline and is not itself attack success. |
| 样本级分布 / Sample-level distribution | range clamp 的中位数离零最远（-0.3317）；range clamp 的箱体IQR最宽（0.4702）。中位数描述典型样本的方向和幅度，IQR表示中间50%样本的反应一致性；须线极值不能单独证明稳定攻击效果。 | range clamp has the median farthest from zero (-0.3317); range clamp has the widest box IQR (0.4702). The median describes the direction and magnitude of a typical sample, while IQR describes consistency in the middle 50%. Whisker extremes alone do not establish a stable attack effect. |
| 适用性 / Applicability | wide char sink guard 的覆盖率最低，为1.7%（1/60）。覆盖率低意味着效果估计只来自较小的可成功运行子集。 | wide char sink guard has the lowest coverage, 1.7% (1/60). Low coverage means the effect estimate comes from a smaller successfully executed subset. |
| 结构变化 / Realised structural change | pattern dead code 的平均绝对节点变化最大（54.02）；pattern dead code 的平均绝对边变化最大（99.20）。它们说明扰动实际改了多少结构，不等于模型受影响程度。 | pattern dead code has the largest mean absolute node change (54.02); pattern dead code has the largest mean absolute edge change (99.20). These values quantify realised structural change, not how strongly the model was affected. |


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
