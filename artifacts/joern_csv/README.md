# artifacts/joern_csv

## 文件夹用途

这个文件夹用于放 Joern 从原始源码或扰动源码生成的 CSV 图产物。

## 需要放什么

- `nodes.csv`
- `edges.csv`
- Joern 解析元数据，例如运行时间、选中的 CSV 路径、节点数、边数和源码 hash。

## 在项目中的作用

如果后续把 Joern 从 DeepWuKong 中拆出来，这里就是最关键的中间层。DeepWuKong 可以从这里的 Joern CSV 继续构建 PDG/XFG，而不是每次内部重新运行 Joern。

## DeepWuKong 至少需要什么

DeepWuKong 至少需要：

- `nodes.csv`
- `edges.csv`
- 与 CSV 匹配的原始或扰动源码文件
- 与 DeepWuKong 前处理一致的 sensitive API 配置

## 不应该放什么

- XFG 模型输入 tensor。
- 最终预测结果。
- 源码扰动模块。
