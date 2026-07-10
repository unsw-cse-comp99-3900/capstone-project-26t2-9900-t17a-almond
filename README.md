# Demo B 结构草案

这个文件夹是 Demo B 的推荐项目结构草案。当前只用于规划目录职责，不放正式代码、模型、数据或实验结果。

## 目标流程

```text
input_sources/
  -> demo_b 扰动与实验流程
  -> artifacts/perturbed_sources
  -> artifacts/joern_csv
  -> artifacts/xfg
  -> baselines/deepwukong 推理
  -> outputs 输出报告和对比结果
```

## 推荐目录结构

```text
Demo B Structure Draft/
  README.md
  demo_b/
  baselines/
    deepwukong/
  input_sources/
  artifacts/
    perturbed_sources/
    joern_csv/
    xfg/
    graphs/
  outputs/
  tests/
  legacy/
    minimal_flip_search/
    perturbation/
    visualization/
```

## 根目录未来应放的文件

后续正式项目根目录可以放：

- `run_demo_b.py`：Demo B 总入口命令。
- `README.md`：项目总说明和运行方式。
- `requirements.txt`：宿主机 Python 依赖。
- Docker 相关文件：等整体流程稳定后再加入。

## 当前状态

当前只放 Markdown 说明文档。目录职责确认之前，不应在这里放代码、模型 checkpoint、测试源码、生成图或实验输出。
