# outputs

## 文件夹用途

这个文件夹用于放最终实验结果，也就是用户或评审需要直接查看的内容。

## 需要放什么

- `demo_report.md`
- `baseline_comparison.csv`
- `baseline_comparison.md`
- `predictions_original.csv`
- `predictions_perturbed.csv`
- `minimal_flip_results.csv`
- `robustness_summary.csv`
- `demo_visualization.html`

## 在项目中的作用

`outputs` 用来总结一次实验发生了什么：原始预测、扰动后预测、是否翻转、概率变化和模型鲁棒性结论。

## 不应该放什么

- Joern CSV 中间文件。
- 大量扰动源码。
- 模型 checkpoint。
- pipeline 源码。

## 运行组织方式

多次实验建议每次一个子目录：

```text
outputs/
  run_YYYYMMDD_HHMMSS/
```
