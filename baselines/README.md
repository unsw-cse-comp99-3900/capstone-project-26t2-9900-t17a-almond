# baselines

## 文件夹用途

这个文件夹用于放 Demo B 会调用的漏洞检测 baseline。每个检测器应该有自己独立的子目录，并提供稳定的命令行或 Python 调用接口。

## 需要放什么

- 每个检测器一个子目录，例如 `deepwukong/`。
- baseline 自己的配置、脚本、模型说明和接口文档。
- 每个 baseline 都应有 README，说明输入格式、输出格式、运行依赖和限制。

## 在项目中的作用

这个目录把模型实现和 Demo B 主流程分开。主流程应该通过稳定 wrapper 调用 baseline，而不是直接依赖散落在各处的内部文件。

## 不应该放什么

- 扰动代码。
- 整体实验报告。
- Demo B 主流程代码。
- 临时运行结果，除非是 baseline 自己的 smoke test。
