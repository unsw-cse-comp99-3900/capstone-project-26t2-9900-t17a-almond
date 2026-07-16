# Demo B

This is the active integration area for the perturbation experiment.

## Current Files

| File | Purpose |
|---|---|
| `perturbations.py` | CLI and implementations for the active perturbation actions. |
| `run_budget_search.py` | Minimal flip search over sample, action, and count budgets. |
| `PERTURBATIONS.md` | Action semantics, safety constraints, examples, and planned work. |
| `__init__.py` | Python package marker. |

Generate all applicable variants from the repository root:

```powershell
python demo_b\perturbations.py
```

Generate the recommended single-action budget sweep:

```powershell
python demo_b\perturbations.py --counts 1 2 3 5
```

Run the minimal flip search:

```powershell
python demo_b\run_budget_search.py --counts 1 2 3 5
```

Implemented actions, ordered by the recommended search priority:

- `pattern_dead_code`
- `data_flow_alias`
- `xfg_targeted_dead_code`
- `dead_statement`
- `control_wrapper`
- `temp_variable_split`

## Strategy

The current perturbation search is ordered from targeted, XFG-sensitive edits to
broader budget repetition:

```text
pattern_dead_code near sensitive API
> data-flow alias/temp split near sink
> XFG-targeted no-op/dead statement
> ordinary count repetition
```

### English

DeepWuKong predicts from regenerated Joern graphs, PDGs, and XFG slices rather
than from raw source text. A source edit is therefore most useful when it lands
near code that is likely to be included in the highest-scoring XFG slice. The
actions are designed with that in mind:

- `pattern_dead_code` inserts unreachable pointer/array/length-shaped code near
  sensitive APIs or structural lines. It is tested first because it introduces a
  vulnerability-like graph/token pattern while keeping runtime semantics
  unchanged.
- `data_flow_alias` inserts alias-preserving data-flow no-ops near sink or call
  arguments. If no suitable call argument exists, it falls back to the existing
  temporary-variable split.
- `xfg_targeted_dead_code` inserts simpler unreachable no-op blocks near
  sensitive APIs, pointer operations, array indexing, or arithmetic lines.
- Ordinary count repetition then increases the perturbation budget, always
  regenerating each count from the original source for reproducibility.

### 中文

DeepWuKong 不是直接根据原始源码文本预测，而是重新生成 Joern graph、PDG 和
XFG slice 后再做预测。因此，扰动如果想影响结果，最好落在可能进入最高分 XFG
slice 的敏感区域附近。当前 action 按这个思路排序：

- `pattern_dead_code` 会在敏感 API 或结构性语句附近插入不可达的
  pointer/array/length 形状代码。它优先级最高，因为这种结构更像漏洞上下文，
  但运行语义仍然不变。
- `data_flow_alias` 会在 sink 或函数调用参数附近插入保持别名/数据流的 no-op；
  如果找不到合适调用参数，则回退到原来的 temporary-variable split。
- `xfg_targeted_dead_code` 会在敏感 API、指针操作、数组访问或算术语句附近插入
  更简单的不可达 no-op/dead statement。
- 最后再做普通 count 重复。每个 count 都从原始源码重新生成，保证实验可复现。

## Testing Method

### English

First verify that the perturbation code is syntactically valid and that the unit
tests still pass:

```powershell
python -m py_compile demo_b\perturbations.py demo_b\run_budget_search.py tests\test_perturbations.py
python -m unittest tests.test_perturbations
```

Generate variants without running DeepWuKong:

```powershell
python demo_b\perturbations.py --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

Run minimal flip search on the near-threshold sample first:

```powershell
python demo_b\run_budget_search.py --input input_sources\09_codexglue_devign_25916.c --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

Then run the same search across all current samples:

```powershell
python demo_b\run_budget_search.py --input input_sources --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

Check `budget_search.csv`. A successful flip is recorded when `flipped` is
`True`. Useful secondary columns are `base_probability`, `variant_probability`,
and `delta_probability`.

### 中文

先确认扰动代码语法正确，并且单元测试通过：

```powershell
python -m py_compile demo_b\perturbations.py demo_b\run_budget_search.py tests\test_perturbations.py
python -m unittest tests.test_perturbations
```

只生成扰动源码，不运行 DeepWuKong：

```powershell
python demo_b\perturbations.py --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

先对接近阈值的样本做 minimal flip search：

```powershell
python demo_b\run_budget_search.py --input input_sources\09_codexglue_devign_25916.c --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

然后再扩展到全部样本：

```powershell
python demo_b\run_budget_search.py --input input_sources --actions pattern_dead_code data_flow_alias xfg_targeted_dead_code --counts 1 2 3 5
```

结果看 `budget_search.csv`。如果 `flipped` 为 `True`，说明该样本在该 action 和
count 下成功反转。辅助观察列包括 `base_probability`、`variant_probability`
和 `delta_probability`。

## Still Planned

The integrated pipeline controller, baseline adapter, report generator, and
visualization module are still planned. Add those modules here when they become
active code rather than placing prototypes in `legacy/`.
