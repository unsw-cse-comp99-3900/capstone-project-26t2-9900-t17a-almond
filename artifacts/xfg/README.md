# artifacts/xfg

## 文件夹用途

这个文件夹用于放由 Joern CSV 和 DeepWuKong 前处理生成的 XFG 产物。

## 需要放什么

- 序列化后的 XFG slice 元数据。
- key line map。
- XFG 类别信息，例如 call、array、pointer、arithmetic。
- 可选的每个 XFG 的预测详情。

## 在项目中的作用

XFG 比原始 Joern CSV 更接近 DeepWuKong 的真实模型输入。保存 XFG 有助于分析扰动为什么改变了预测结果。

## 不应该放什么

- 原始 Joern CSV。
- 大模型 checkpoint。
- 最终给用户看的报告。

## 注意事项

如果这些产物要用于推理，其格式必须和 DeepWuKong 的前处理逻辑完全一致，否则模型结果不可比。
