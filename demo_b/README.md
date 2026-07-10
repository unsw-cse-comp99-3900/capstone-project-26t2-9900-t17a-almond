# demo_b

## 文件夹用途

这个文件夹用于放 Demo B 的主流程集成代码。它负责把输入函数、扰动模块、Joern 图生成、DeepWuKong 推理、最小翻转搜索、报告生成和可视化串起来。

## 需要放什么

- `pipeline.py`：总流程控制器。
- `baseline.py`：DeepWuKong 检测器调用封装。
- `perturbations.py`：源码扰动接口。
- `graphs.py`：Joern 图产物和图分析接口。
- `flip_search.py`：最小扰动翻转搜索逻辑。
- `reporting.py`：CSV 和 Markdown 报告生成。
- `visualization.py`：HTML 或图可视化生成。
- `utils.py`：路径、JSON、CSV 等通用工具函数。

## 在项目中的作用

`demo_b` 应该是整个实验流程的唯一主控层。其他目录可以提供模型、旧模块、输入数据或中间产物，但完整控制流程应该放在这里。

## 不应该放什么

- 原始大数据集。
- 模型 checkpoint。
- 大量生成结果。
- 旧实验文件夹的完整复制。
- Docker 构建产物。
