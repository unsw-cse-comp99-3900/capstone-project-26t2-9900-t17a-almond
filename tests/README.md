# tests

## 文件夹用途

这个文件夹用于放 Demo B pipeline 和各个 adapter 的测试。

## 需要放什么

- 命令行入口 smoke test。
- 路径处理、扰动输出格式、报告生成、前后对比逻辑的单元测试。
- 可以提交的小型 fixture 文件。

## 在项目中的作用

测试用于保护项目从 Demo A 风格结构迁移到 Demo B 风格结构时，核心功能不被破坏。

## 不应该放什么

- 大型数据集。
- 完整实验输出。
- 默认运行的长时间 GPU 测试。

## 推荐测试层级

- 快速 host-only 测试。
- 可选 Docker/DeepWuKong smoke test。
- 标记为 slow 的完整推理测试。
