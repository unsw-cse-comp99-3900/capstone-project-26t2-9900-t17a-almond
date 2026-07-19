"""Create a self-contained, filterable report from an archived Demo B run."""

from __future__ import annotations

import argparse
import csv
import html
import os
from collections import defaultdict
from pathlib import Path

NUMERIC_FIELDS = ("base_prob", "variant_prob", "delta_prob", "delta_nodes", "delta_edges")


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read either the code-level or graph-level comparison CSV schema."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no comparison rows")
    if {"sample", "action"} - set(rows[0]):
        raise ValueError(f"{path} must contain sample and action columns")
    return [normalise_row(row) for row in rows]


def normalise_row(row: dict[str, str]) -> dict[str, str]:
    """Map archived code- and graph-level variants to one display schema."""
    result = dict(row)
    result["delta_prob"] = row.get("delta_prob") or row.get("delta_probability") or ""
    result["function"] = row.get("function") or "unknown"
    result["status"] = row.get("status") or "unknown"
    result["flipped"] = row.get("flipped") or "False"
    result["budget"] = row.get("budget") or ""
    for field in NUMERIC_FIELDS:
        result.setdefault(field, "")
    return result


def number(row: dict[str, str], name: str) -> float:
    return float(row[name])


def is_scored(row: dict[str, str]) -> bool:
    """A successful generation is not necessarily a scored model prediction."""
    if row["status"].lower() != "success":
        return False
    try:
        for field in NUMERIC_FIELDS:
            number(row, field)
    except (KeyError, ValueError):
        return False
    return True


def selection_key(row: dict[str, str]) -> str:
    """Keep attack budgets distinct when a run evaluates multiple budgets."""
    return f"{row['action']} | budget {row['budget']}" if row["budget"] else row["action"]


def action_metrics(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[selection_key(row)].append(row)
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


def chart_label(selection: str) -> list[str]:
    """Make long method-and-budget names readable in the SVG chart."""
    method, separator, budget = selection.partition(" | budget ")
    friendly_method = method.replace("winner_xfg_", "XFG ").replace("_", " ")
    words = friendly_method.split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if current and len(proposed) > 20:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    if separator:
        lines.append(f"budget {budget}")
    return lines


def svg_action_chart(metrics: list[dict[str, object]]) -> str:
    shown = sorted(metrics, key=lambda metric: abs(float(metric["mean_delta"])), reverse=True)[:12]
    width, label_width, bar_width = 960, 260, 510
    row_height, top, bottom = 52, 50, 36
    height = top + len(shown) * row_height + bottom
    maximum = max((abs(float(metric["mean_delta"])) for metric in shown), default=1.0) or 1.0
    bars = []
    for index, metric in enumerate(shown):
        value = abs(float(metric["mean_delta"]))
        bar_length = value / maximum * bar_width
        y = top + index * row_height
        action = html.escape(str(metric["action"]))
        label_lines = "".join(
            f'<tspan x="{label_width - 12}" dy="{14 if line_index else 0}">{html.escape(line)}</tspan>'
            for line_index, line in enumerate(chart_label(str(metric["action"])))
        )
        bars.append(
            f'<g data-action-chart="{action}"><text x="{label_width - 12}" y="{y + 18}" text-anchor="end" font-size="14">{label_lines}</text>'
            f'<rect x="{label_width}" y="{y + 6}" width="{bar_length:.1f}" height="26" fill="#5b8ff9"/>'
            f'<text x="{label_width + bar_length + 10:.1f}" y="{y + 24}" font-size="14">{value:.4f}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Mean absolute probability change by action">'
        f'<text x="0" y="22" font-size="15">Top {len(shown)} configurations by mean absolute probability change</text>{"".join(bars)}</svg>'
    )


def available_runs() -> list[Path]:
    """Return every archived run that has a comparison table."""
    return sorted(
        candidate for candidate in Path("outputs").glob("run_*")
        if (candidate / "prediction_comparison.csv").is_file()
    )


def render_index(runs: list[Path], output: Path) -> None:
    """Create a compact landing page for navigating all archived experiments."""
    cards: list[str] = []
    for run in runs:
        rows = read_rows(run / "prediction_comparison.csv")
        scored = [row for row in rows if is_scored(row)]
        selections = {selection_key(row) for row in scored}
        kind = "Code-level" if "_code_" in run.name else "Graph-level"
        cards.append(
            '<a class="run-card" href="{href}"><span class="kind">{kind}</span><h2>{name}</h2>'
            '<dl><div><dt>Samples</dt><dd>{samples}</dd></div><div><dt>Scored variants</dt><dd>{variants}</dd></div>'
            '<div><dt>Configurations</dt><dd>{selections}</dd></div><div><dt>Prediction flips</dt><dd>{flips}</dd></div></dl></a>'.format(
                href=html.escape(f"{run.name}/dashboard.html"), kind=kind, name=html.escape(run.name),
                samples=len({row["sample"] for row in scored}), variants=len(scored), selections=len(selections),
                flips=sum(row["flipped"].lower() == "true" for row in scored),
            )
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DeepWuKong experiment index</title><style>
body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:#f5f7fb;color:#172033}}main{{max-width:1120px;margin:auto;padding:32px}}.sub{{color:#5d687c}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:26px}}.run-card{{display:block;color:inherit;text-decoration:none;background:white;border-radius:12px;padding:20px;box-shadow:0 2px 10px #17203312}}.run-card:hover{{box-shadow:0 6px 18px #17203322}}.run-card h2{{font-size:18px;margin:10px 0 18px;overflow-wrap:anywhere}}.kind{{color:#2457c5;font-weight:600}}dl{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0}}dt{{font-size:13px;color:#5d687c}}dd{{font-size:24px;font-weight:700;margin:3px 0 0}}
</style></head><body><main><h1>DeepWuKong experiment index</h1><p class="sub">Choose an archived code-level or graph-level perturbation run to view its full comparison dashboard.</p><div class="grid">{"".join(cards)}</div></main></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def render_report(
    rows: list[dict[str, str]],
    output: Path,
    title: str,
    run_options: list[tuple[str, str]] | None = None,
    current_run: str | None = None,
) -> None:
    scored = [row for row in rows if is_scored(row)]
    if not scored:
        raise ValueError("the comparison CSV has no successful rows with complete numeric prediction data")
    metrics = action_metrics(scored)
    selections = sorted({selection_key(row) for row in scored})
    has_budgets = any(row["budget"] for row in scored)
    selection_name = "attack configurations" if has_budgets else "perturbation methods"
    metric_name = "Configuration" if has_budgets else "Action"
    max_change = max(scored, key=lambda row: abs(number(row, "delta_prob")))
    flips = sum(row["flipped"].lower() == "true" for row in scored)
    baseline_count, unscored = len({row["sample"] for row in scored}), len(rows) - len(scored)
    max_change_note = "and flipped the final label." if max_change["flipped"].lower() == "true" else "without a label flip."
    table_rows = "".join(
        "<tr data-selection=\"{selection}\"><td>{sample}</td><td>{function}</td><td>{action}</td><td>{budget}</td>"
        "<td>{base:.6f}</td><td>{variant:.6f}</td><td class=\"delta\">{delta:+.6f}</td>"
        "<td>{nodes:+.0f}</td><td>{edges:+.0f}</td><td>{flipped}</td></tr>".format(
            selection=html.escape(selection_key(row)), action=html.escape(row["action"]), sample=html.escape(row["sample"]),
            function=html.escape(row["function"]), budget=html.escape(row["budget"] or "N/A"),
            base=number(row, "base_prob"), variant=number(row, "variant_prob"),
            delta=number(row, "delta_prob"), nodes=number(row, "delta_nodes"), edges=number(row, "delta_edges"),
            flipped="yes" if row["flipped"].lower() == "true" else "no",
        ) for row in scored
    )
    metric_rows = "".join(
        "<tr><td>{action}</td><td>{variants}</td><td>{delta:+.6f}</td><td>{nodes:.1f}</td><td>{edges:.1f}</td></tr>".format(
            action=html.escape(str(metric["action"])), variants=metric["variants"],
            delta=float(metric["mean_delta"]), nodes=float(metric["mean_nodes"]), edges=float(metric["mean_edges"]),
        ) for metric in metrics
    )
    controls = " ".join(f'<label><input type="checkbox" value="{html.escape(selection)}" checked> {html.escape(selection)}</label>' for selection in selections)
    run_selector = ""
    if run_options:
        run_selector_options = "".join(
            f'<option value="{html.escape(destination)}"{" selected" if name == current_run else ""}>{html.escape(name)}</option>'
            for name, destination in run_options
        )
        run_selector = (
            '<div class="run-switcher"><label for="run-selector">Experiment run</label>'
            f'<select id="run-selector">{run_selector_options}</select> <a href="../index.html">All runs</a></div>'
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><style>
body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:#f5f7fb;color:#172033}}main{{max-width:1120px;margin:auto;padding:32px}}h1{{margin-bottom:4px}}.sub{{color:#5d687c}}.run-switcher{{margin:16px 0}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}.card{{background:white;border-radius:12px;padding:18px;min-width:170px;box-shadow:0 2px 10px #17203312}}.value{{font-size:28px;font-weight:700;color:#2457c5}}section{{background:white;border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 2px 10px #17203312}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f1f5ff}}.delta{{font-variant-numeric:tabular-nums}}label{{display:inline-block;margin:4px 14px 8px 0}}.note{{padding:12px;background:#fff8e5;border-left:4px solid #e6aa13}}.method-picker{{margin-top:14px;border:1px solid #cbd5e1;border-radius:8px;background:#f8faff}}.method-picker summary{{cursor:pointer;padding:14px 16px;font-weight:600;font-size:16px}}.picker-actions{{padding:8px 16px;border-top:1px solid #dbe4f2}}.picker-actions label{{font-weight:600;margin:0}}#action-checks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:4px 14px;max-height:420px;overflow-y:auto;padding:2px 16px 16px}}#action-checks label{{margin:0;padding:6px 2px;overflow-wrap:anywhere}}.table-scroll{{max-height:680px;overflow-y:scroll;scrollbar-width:auto;scrollbar-color:#496b9e #e3eaf6}}.table-scroll::-webkit-scrollbar{{width:16px}}.table-scroll::-webkit-scrollbar-track{{background:#e3eaf6}}.table-scroll::-webkit-scrollbar-thumb{{background:#496b9e;border:3px solid #e3eaf6;border-radius:10px}}.table-scroll thead th{{position:sticky;top:0;z-index:1}}.variant-table{{table-layout:fixed;font-size:13px}}.variant-table th,.variant-table td{{padding:8px 7px;overflow-wrap:anywhere;vertical-align:top}}.variant-table th:nth-child(n+4),.variant-table td:nth-child(n+4){{text-align:center;white-space:nowrap}}
</style></head><body><main>
<h1>{html.escape(title)}</h1><p class="sub">Archived DeepWuKong robustness run - code- or graph-level perturbations compared with the same baseline prediction.</p>{run_selector}
<div class="cards"><div class="card"><div class="value">{baseline_count}</div>baseline samples</div><div class="card"><div class="value">{len(scored)}</div>scored variants</div><div class="card"><div class="value">{flips}</div>prediction flips</div><div class="card"><div class="value">{unscored}</div>unscored / incomplete</div></div>
<section><h2>What changed most?</h2><p class="note"><strong>{html.escape(max_change['sample'])}</strong> with <strong>{html.escape(max_change['action'])}</strong> changed from {number(max_change, 'base_prob'):.6f} to {number(max_change, 'variant_prob'):.6f} ({number(max_change, 'delta_prob'):+.6f}) {max_change_note}</p>{svg_action_chart(metrics)}</section>
<section><h2>Action-level comparison</h2><table><thead><tr><th>{metric_name}</th><th>Scored variants</th><th>Mean probability delta</th><th>Mean delta nodes</th><th>Mean delta edges</th></tr></thead><tbody>{metric_rows}</tbody></table></section>
<section><h2>Variant explorer</h2><p>Select one or more {selection_name} for comparison. New actions and budgets found in the CSV appear automatically.</p><div id="filters"><p id="selection-summary"></p><details class="method-picker"><summary>Choose {selection_name} (checkboxes)</summary><div class="picker-actions"><label><input id="select-all" type="checkbox" checked> All</label></div><div id="action-checks">{controls}</div></details></div><div class="table-scroll"><table class="variant-table"><colgroup><col style="width:10%"><col style="width:20%"><col style="width:18%"><col style="width:5%"><col style="width:8%"><col style="width:8%"><col style="width:9%"><col style="width:7%"><col style="width:7%"><col style="width:8%"></colgroup><thead><tr><th>Sample</th><th>Function</th><th>Action</th><th>Budget</th><th>Baseline</th><th>Variant</th><th>Delta probability</th><th>Delta nodes</th><th>Delta edges</th><th>Flipped</th></tr></thead><tbody>{table_rows}</tbody></table></div></section>
</main><script>const boxes=[...document.querySelectorAll('#action-checks input')];const allBox=document.getElementById('select-all');const summary=document.getElementById('selection-summary');const runSelector=document.getElementById('run-selector');function selected(){{return new Set(boxes.filter(box=>box.checked).map(box=>box.value));}}function filter(){{const chosen=selected();allBox.checked=chosen.size===boxes.length;allBox.indeterminate=chosen.size>0&&chosen.size<boxes.length;document.querySelectorAll('tbody tr[data-selection]').forEach(row=>row.hidden=!chosen.has(row.dataset.selection));document.querySelectorAll('[data-action-chart]').forEach(mark=>mark.hidden=!chosen.has(mark.dataset.actionChart));summary.textContent=`Showing ${{chosen.size}} of ${{boxes.length}} {selection_name}.`;}}allBox.addEventListener('change',()=>{{boxes.forEach(box=>box.checked=allBox.checked);filter();}});boxes.forEach(box=>box.addEventListener('change',filter));if(runSelector)runSelector.addEventListener('change',()=>{{window.location.href=runSelector.value;}});filter();</script></body></html>"""
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
    runs = available_runs()
    run_options = [
        (candidate.name, Path(os.path.relpath(candidate / "dashboard.html", output.parent)).as_posix())
        for candidate in runs
    ]
    render_report(
        read_rows(comparison), output, f"DeepWuKong perturbation report: {args.run_dir.name}",
        run_options, args.run_dir.name,
    )
    render_index(runs, Path("outputs") / "index.html")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
