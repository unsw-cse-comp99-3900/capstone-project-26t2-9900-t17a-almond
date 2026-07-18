# run_20260717_code_devign_round1

This directory is a reformatted code-level perturbation run generated from `C:\Users\weijt\Desktop\UNSW\COMP9900\project\capstone-project-26t2-9900-t17a-almond\outputs\generated\full_budget_search_20260717`.

It mirrors the file layout used by `outputs/run_20260717_graph_cwe119_round1`, but the actions are source-code perturbation strategies rather than direct graph mutations.

## Contents

- `baseline_predictions.csv`: one baseline DeepWuKong prediction per sample.
- `baseline_summary.csv`: compact baseline table.
- `perturbation_results.csv`: one row per sample/action/count perturbation attempt.
- `prediction_comparison.csv`: baseline vs perturbed prediction comparison.
- `action_summary.csv`: flip and probability-delta summary by action.
- `action_metrics.csv`: aggregate action metrics.
- `summary.json`: compact experiment summary.
- `details.json`: source paths, run directories, perturbation notes, and flip details.
- `runs/baseline/*.json`: flattened baseline `predictions.json` files.
- `runs/perturbed/*.json`: flattened perturbed `predictions.json` files.

## Result

- Dataset: `devign`
- Samples: 10
- Perturbation attempts: 284
- Successful runs: 259
- Label flips: 2
