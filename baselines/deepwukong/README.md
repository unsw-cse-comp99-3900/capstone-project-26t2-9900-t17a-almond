# DeepWuKong baseline

此目录提供 Demo B 使用的 DeepWuKong CWE-119 漏洞检测 baseline。它只包含模型推理所需的配置、入口脚本、checkpoint 和最小兼容代码；数据集、扰动源码、全局实验报告与历史运行结果不放在这里。

## 目录结构

```text
baselines/deepwukong/
├── configs/       # 模型路径与运行配置
├── models/        # DeepWuKong checkpoint
├── scripts/       # 单文件、目录和 Devign 批量推理入口
├── src/           # Demo B 兼容模式使用的最小 Python 模块
├── MODEL_CARD.md  # 模型身份、输入输出语义和限制
└── requirements.txt
```

## 输入与输出

主要入口接收单个 C/C++ 源文件或包含源码的目录：

```powershell
python .\scripts\run_demo_pipeline.py `
  --input <source-file-or-directory> `
  --output <output-directory> `
  --config .\configs\demo_config.json `
  --no-timestamp-output
```

单文件运行会生成：

- `predictions.json`：完整预测与 XFG 级细节。
- `predictions.csv`：扁平预测记录。
- `run_metadata.json`：Joern、图规模、耗时和警告信息。
- `demo_report.md`：便于阅读的单文件报告。

目录批量运行会额外生成 `summary.json`、`summary.csv`、`summary_report.md` 和逐文件的 `runs/` 子目录。

稳定输出字段包括 `predicted_label`、`vulnerability_probability`、`confidence`、`num_nodes`、`num_edges` 和 `joern_status`。Demo B 应通过这些字段调用 baseline，不应依赖内部临时文件。

## 推理流程

完整推理保持与 DeepWuKong 训练时一致的输入路径：

```text
C/C++ source -> Joern CSV -> PDG -> XFG -> tokenized graph -> DeepWuKong model
```

一个源码文件可能生成多个 XFG。文件级漏洞概率取所有 XFG 漏洞概率的最大值，并使用 `0.5` 作为默认分类阈值。如果 Joern 没有生成敏感 XFG，结果为 `non_vulnerable`、概率为 `0.0`，同时在元数据中记录警告。

## 运行依赖

宿主机入口只使用 Python 标准库，但完整推理需要：

- Docker Desktop 正常运行，并且 `docker` 位于 `PATH`。
- 本机已有 `deepwukong-rtx5060-cu128:experimental` Docker 镜像。
- GPU 模式下 Docker 能访问 NVIDIA GPU。
- `models/deepwukong/deepwukong_cwe119_best.ckpt` 存在。

从本目录运行一个源码文件：

```powershell
python .\scripts\run_demo_pipeline.py `
  --input ..\..\input_sources\sample.c `
  --output ..\..\outputs\deepwukong\sample `
  --no-timestamp-output
```

也可以使用 PowerShell 包装脚本：

```powershell
.\scripts\run_demo.ps1 -InputPath ..\..\input_sources -Output ..\..\outputs\deepwukong
```

## Joern/XFG 入口

当前源码入口会在 Docker 内调用 Joern，并由 `scripts/infer_single_source.py` 完成 Joern CSV、PDG、XFG 和模型预测。`scripts/evaluate_devign_projects_container.py` 包含从批量 Joern 产物构建预测的实现，可作为后续拆分稳定 `infer_from_joern_csv` 接口的基础。

## 限制

- 当前 checkpoint 面向 CWE-119，不代表对所有漏洞类型都具有同等效果。
- 输出是源码/函数级判断，不提供精确漏洞行定位。
- 完整推理依赖本地 Docker 镜像；只有仓库内容时不能自动重建该镜像。
- `src/models/lexical.py` 只用于 Demo B 兼容路径，不是正式 DeepWuKong 图模型。
- 本目录不保存 Demo B 全局报告、扰动源码批次、通用扰动模块或历史 Devign 输出。
