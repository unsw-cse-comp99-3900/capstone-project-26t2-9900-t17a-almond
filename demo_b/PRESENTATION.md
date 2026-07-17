# DeepWuKong 扰动实验展示说明

本说明用于演示已归档的 `run_20260710_code_devign_round1` 实验：对 C 源码施加保持语义的
扰动，重新经过 Joern、PDG、XFG 和 DeepWuKong 推理，并比较模型输出。

## 快速开始

从仓库根目录生成展示页面：

```powershell
python demo_b\visualize_results.py --run-dir outputs\run_20260710_code_devign_round1
```

然后在浏览器中打开：

```text
outputs/run_20260710_code_devign_round1/dashboard.html
```

该页面是离线 HTML，不需要启动 Docker、Joern 或 GPU。也可以打开
`demo_b/deepwukong_results_dashboard.ipynb`，在 Jupyter 中按单元格展示。

## 数据来源

展示程序读取以下主分支已提交的结果，而不自行编造模型结果：

| 文件 | 用途 |
|---|---|
| `outputs/run_20260710_code_devign_round1/prediction_comparison.csv` | 每个 baseline–扰动变体配对后的预测、概率和图结构变化。 |
| `outputs/run_20260710_code_devign_round1/action_summary.csv` | 各扰动动作的聚合指标。 |
| `outputs/run_20260710_code_devign_round1/baseline_summary.csv` | 10 个原始样本的 DeepWuKong 预测。 |
| `outputs/run_20260710_code_devign_round1/runs/` | 每次 baseline 与扰动推理的完整 JSON 记录。 |

## 推荐演示顺序

1. 说明端到端路径：`original source -> perturbation -> Joern -> PDG/XFG -> DeepWuKong prediction`。
2. 打开 dashboard 的四张摘要卡：10 个 baseline、23 个成功扰动、0 次标签翻转，以及最大概率变化。
3. 查看动作级图表，比较三种动作：`control_wrapper`、`dead_statement` 和 `temp_variable_split`。
4. 用页面中的复选框筛选动作，并在逐变体表中比较 `Δ probability`、`Δ nodes` 和 `Δ edges`。
5. 强调最大变化案例：`07_codexglue_devign_4012` 的 `dead_statement` 将概率从 `0.899059` 降至 `0.751189`，但仍高于 0.5 阈值，因此没有翻转标签。

## 当前结论与边界

- 所有 23 个归档变体成功完成 Joern 与 DeepWuKong 推理。
- 当前三种较保守的扰动均改变了图结构，但没有改变 DeepWuKong 的最终二分类标签。
- 这说明当前实验验证了扰动—重建图—推理—比较的完整流程；它不等价于“模型对所有攻击都鲁棒”。
- 更有价值的下一步是优先针对接近阈值的样本，或将扰动定位到最高分 XFG 附近。

## 更新到新实验

新实验完成后，只要在新的 `outputs/run_<YYYYMMDD>_<level>_<dataset>_round<N>/` 中写出同名的
`prediction_comparison.csv`，即可重新生成页面：

```powershell
python demo_b\visualize_results.py --run-dir outputs\run_<YYYYMMDD>_<level>_<dataset>_round<N>
```

页面会输出到该运行目录的 `dashboard.html`。
