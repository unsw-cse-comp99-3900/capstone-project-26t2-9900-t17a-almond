# baselines/deepwukong

## 文件夹用途

这个文件夹用于放 Demo B 使用的 DeepWuKong 漏洞检测 baseline。

## 需要放什么

- `configs/`：DeepWuKong 运行配置。
- `scripts/`：推理入口脚本，例如源码到预测结果、Joern CSV 到预测结果。
- `models/`：DeepWuKong checkpoint 说明，必要时放 checkpoint 文件。
- `README.md`：如何单独运行这个 baseline。
- `MODEL_CARD.md`：模型身份、训练目标、输入输出语义和限制。

## 在项目中的作用

DeepWuKong 是 Demo B 当前要评估的漏洞检测器。它应该通过稳定接口接收源码文件或预生成的 Joern/XFG 产物，并输出 label、漏洞概率、confidence 和图统计信息。

## 重要说明

- 完整 DeepWuKong 推理仍然依赖 Joern 前处理。
- 如果后续把 Joern 拆出来，这里应该提供类似 `infer_from_joern_csv` 的入口。
- 模型输入路径必须和 DeepWuKong 训练时一致：Joern CSV -> PDG -> XFG -> tokenized graph -> model。

## 不应该放什么

- Demo B 全局报告。
- 扰动后的源码批次。
- 通用扰动模块。
- 旧 Devign 代码，除非明确作为 legacy 资料保留。
