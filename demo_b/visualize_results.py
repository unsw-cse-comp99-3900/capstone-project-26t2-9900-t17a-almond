"""Create a self-contained, filterable report from an archived Demo B run.

The report deliberately consumes the compact CSV artifacts committed with each
run.  It therefore works on any machine without Docker, Joern, pandas, or a
running DeepWuKong container.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(row: dict[str, str], name: str) -> float:
    return float(row[name])


def action_metrics(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["action"]].append(row)
    return [
        {
            "action": action,
            "variants": len(group),
            "mean_delta": sum(number(row, "delta_prob") for row in group) / len(group),
            "mean_nodes": sum(number(row, "delta_nodes") for row in group) / len(group),
            "mean_edges": sum(number(row, "delta_edges") for row in group) / len(group),
        }
        for action, group in sorted(grouped.items())
    ]


def svg_action_chart(metrics: list[dict[str, object]]) -> str:
    width, height, left, bottom = 720, 250, 70, 45
    values = [abs(float(metric["mean_delta"])) for metric in metrics]
    maximum = max(values, default=1.0) or 1.0
    bar_width = 120
    bars = []
    for index, metric in enumerate(metrics):
        value = abs(float(metric["mean_delta"]))
        bar_height = value / maximum * 155
        x = left + index * 200
        y = height - bottom - bar_height
        action = html.escape(str(metric["action"]))
        bars.append(
            f'<g data-action-chart="{action}"><rect x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" '
            f'fill="#5b8ff9"/><text x="{x + bar_width / 2}" y="{height - 22}" text-anchor="middle" '
            f'font-size="12">{action}</text><text x="{x + bar_width / 2}" '
            f'y="{y - 7:.1f}" text-anchor="middle" font-size="12">{value:.4f}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Mean absolute probability change by action">'
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-15}" y2="{height-bottom}" stroke="#6b7280"/>'
        f'<text x="8" y="20" font-size="13">Mean |probability change|</text>{"".join(bars)}</svg>'
    )


def render_report(rows: list[dict[str, str]], output: Path, title: str) -> None:
    successful = [row for row in rows if row.get("status") == "success"]
    metrics = action_metrics(successful)
    actions = sorted({row["action"] for row in successful})
    max_change = max(successful, key=lambda row: abs(number(row, "delta_prob")))
    flips = sum(row["flipped"].lower() == "true" for row in successful)
    baseline_count = len({row["sample"] for row in successful})
    table_rows = "".join(
        "<tr data-action=\"{action}\"><td>{sample}</td><td>{function}</td><td>{action}</td>"
        "<td>{base:.6f}</td><td>{variant:.6f}</td><td class=\"delta\">{delta:+.6f}</td>"
        "<td>{nodes:+.0f}</td><td>{edges:+.0f}</td><td>{flipped}</td></tr>".format(
            action=html.escape(row["action"]),
            sample=html.escape(row["sample"]),
            function=html.escape(row["function"]),
            base=number(row, "base_prob"), variant=number(row, "variant_prob"),
            delta=number(row, "delta_prob"), nodes=number(row, "delta_nodes"),
            edges=number(row, "delta_edges"), flipped="yes" if row["flipped"].lower() == "true" else "no",
        )
        for row in successful
    )
    metric_rows = "".join(
        "<tr><td>{action}</td><td>{variants}</td><td>{delta:+.6f}</td><td>{nodes:.1f}</td><td>{edges:.1f}</td></tr>".format(
            action=html.escape(str(metric["action"])), variants=metric["variants"],
            delta=float(metric["mean_delta"]), nodes=float(metric["mean_nodes"]), edges=float(metric["mean_edges"]),
        ) for metric in metrics
    )
    controls = " ".join(
        f'<label><input type="checkbox" value="{html.escape(action)}" checked> {html.escape(action)}</label>'
        for action in actions
    )
    action_options = "".join(
        f'<option value="{html.escape(action)}">{html.escape(action)}</option>' for action in actions
    )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:#f5f7fb;color:#172033}}main{{max-width:1120px;margin:auto;padding:32px}}
h1{{margin-bottom:4px}}.sub{{color:#5d687c}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}.card{{background:white;border-radius:12px;padding:18px;min-width:170px;box-shadow:0 2px 10px #17203312}}.value{{font-size:28px;font-weight:700;color:#2457c5}}section{{background:white;border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 2px 10px #17203312}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f1f5ff}}.delta{{font-variant-numeric:tabular-nums}}label{{display:inline-block;margin:4px 14px 8px 0}}.note{{padding:12px;background:#fff8e5;border-left:4px solid #e6aa13}}
</style></head><body><main>
<h1>{html.escape(title)}</h1><p class="sub">Archived DeepWuKong robustness run — source-level perturbations regenerated through Joern/PDG/XFG inference.</p>
<div class="cards"><div class="card"><div class="value">{baseline_count}</div>baseline samples</div><div class="card"><div class="value">{len(successful)}</div>successful variants</div><div class="card"><div class="value">{flips}</div>prediction flips</div><div class="card"><div class="value">{abs(number(max_change, 'delta_prob')):.4f}</div>largest probability shift</div></div>
<section><h2>What changed most?</h2><p class="note"><strong>{html.escape(max_change['sample'])}</strong> with <strong>{html.escape(max_change['action'])}</strong> changed from {number(max_change, 'base_prob'):.6f} to {number(max_change, 'variant_prob'):.6f} ({number(max_change, 'delta_prob'):+.6f}) without a label flip.</p>{svg_action_chart(metrics)}</section>
<section><h2>Action-level comparison</h2><table><thead><tr><th>Action</th><th>Variants</th><th>Mean probability delta</th><th>Mean Δ nodes</th><th>Mean Δ edges</th></tr></thead><tbody>{metric_rows}</tbody></table></section>
<section><h2>Variant explorer</h2><p>Use one method for a focused walkthrough, or select several methods for comparison. New actions found in the CSV appear automatically.</p><div id="filters"><label for="primary-action">Focused action</label><select id="primary-action"><option value="__all__">All actions</option>{action_options}<option value="__custom__">Custom selection</option></select><p id="selection-summary"></p><div id="action-checks">{controls}</div></div><table><thead><tr><th>Sample</th><th>Function</th><th>Action</th><th>Baseline</th><th>Variant</th><th>Δ probability</th><th>Δ nodes</th><th>Δ edges</th><th>Flipped</th></tr></thead><tbody>{table_rows}</tbody></table></section>
</main><script>const boxes=[...document.querySelectorAll('#action-checks input')];const primary=document.getElementById('primary-action');const summary=document.getElementById('selection-summary');function selected(){{return new Set(boxes.filter(box=>box.checked).map(box=>box.value));}}function filter(){{const chosen=selected();document.querySelectorAll('tbody tr[data-action]').forEach(row=>row.hidden=!chosen.has(row.dataset.action));document.querySelectorAll('[data-action-chart]').forEach(mark=>mark.hidden=!chosen.has(mark.dataset.actionChart));summary.textContent=`Showing ${{chosen.size}} of ${{boxes.length}} perturbation methods.`;}}primary.addEventListener('change',()=>{{if(primary.value==='__all__')boxes.forEach(box=>box.checked=true);else if(primary.value!=='__custom__')boxes.forEach(box=>box.checked=box.value===primary.value);filter();}});boxes.forEach(box=>box.addEventListener('change',()=>{{const chosen=selected();primary.value=chosen.size===boxes.length?'__all__':chosen.size===1?[...chosen][0]:'__custom__';filter();}}));filter();</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an offline DeepWuKong perturbation dashboard.")
    parser.add_argument("--run-dir", type=Path, default=Path("outputs/run_20260710_code_devign_round1"))
    parser.add_argument("--output", type=Path, default=None, help="Defaults to <run-dir>/dashboard.html")
    args = parser.parse_args()
    comparison = args.run_dir / "prediction_comparison.csv"
    if not comparison.is_file():
        parser.error(f"missing comparison table: {comparison}")
    output = args.output or args.run_dir / "dashboard.html"
    render_report(read_rows(comparison), output, f"DeepWuKong perturbation report: {args.run_dir.name}")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
