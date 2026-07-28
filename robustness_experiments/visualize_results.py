"""Create a self-contained, filterable report from an archived Demo B run."""

from __future__ import annotations

import argparse
import csv
import html
import os
import re
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
    """Give every method-and-strength combination one stable display label."""
    method, strength = perturbation_configuration(row)
    return f"{method} | {strength}" if strength else method


def perturbation_configuration(row: dict[str, str]) -> tuple[str, str]:
    """Normalize graph budgets and code ``__cN`` suffixes into one configuration."""
    if row["budget"]:
        return row["action"], f"budget {row['budget']}"
    match = re.fullmatch(r"(.+)__c(\d+)", row["action"])
    if match:
        return match.group(1), f"count {match.group(2)}"
    return row["action"], ""


def explicit_attack_success(rows: list[dict[str, str]]) -> bool:
    """Whether this CSV defines a targeted-attack success outcome."""
    return any("attack_success" in row for row in rows)


def success_term(rows: list[dict[str, str]]) -> str:
    return "Attack Success Rate (ASR)" if explicit_attack_success(rows) else "Prediction Flip Rate"


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
        '<div class="chart-scroll sensitivity-chart">'
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Mean absolute probability change by action">'
        f'<text x="0" y="22" font-size="15">Top {len(shown)} configurations by mean absolute probability change</text>{"".join(bars)}</svg></div>'
    )


def attack_succeeded(row: dict[str, str]) -> bool:
    """Use the explicit targeted-attack outcome when available, otherwise a label flip."""
    value = row.get("attack_success", "")
    return value.lower() == "true" if value else row["flipped"].lower() == "true"


def success_metrics(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[selection_key(row)].append(row)
    return [
        {
            "selection": selection,
            "total": len(group),
            "successes": sum(attack_succeeded(row) for row in group),
        }
        for selection, group in grouped.items()
    ]


def robustness_summary(rows: list[dict[str, str]]) -> dict[str, tuple[int, int] | None]:
    """Summarise outcome success overall, per sample, and per known true class."""
    successes = sum(attack_succeeded(row) for row in rows)
    sample_outcomes: dict[str, bool] = defaultdict(bool)
    for row in rows:
        sample_outcomes[row["sample"]] = sample_outcomes[row["sample"]] or attack_succeeded(row)
    summary: dict[str, tuple[int, int] | None] = {
        "overall": (successes, len(rows)),
        "samples": (sum(sample_outcomes.values()), len(sample_outcomes)),
        "vulnerable": None,
        "non_vulnerable": None,
    }
    labelled = [row for row in rows if row.get("true_label", "") != ""]
    if labelled:
        vulnerable = [row for row in labelled if row["true_label"].strip().lower() in {"1", "true", "vulnerable"}]
        non_vulnerable = [row for row in labelled if row not in vulnerable]
        summary["vulnerable"] = (sum(attack_succeeded(row) for row in vulnerable), len(vulnerable))
        summary["non_vulnerable"] = (sum(attack_succeeded(row) for row in non_vulnerable), len(non_vulnerable))
    return summary


def success_card(label: str, value: tuple[int, int]) -> str:
    successful, total = value
    rate = successful / total if total else 0.0
    return f'<div class="card"><div class="value">{rate:.1%}</div>{html.escape(label)}<small>{successful}/{total}</small></div>'


def svg_success_rate_chart(rows: list[dict[str, str]]) -> str:
    """Compare each perturbation configuration by its outcome-changing rate."""
    shown = sorted(
        success_metrics(rows),
        key=lambda metric: (int(metric["successes"]) / int(metric["total"]), int(metric["successes"])),
        reverse=True,
    )
    width, label_width, bar_width = 960, 280, 500
    row_height, top, bottom = 48, 50, 32
    bars = []
    for index, metric in enumerate(shown):
        total, successes = int(metric["total"]), int(metric["successes"])
        rate = successes / total if total else 0.0
        y = top + index * row_height
        label = html.escape(str(metric["selection"]))
        bars.append(
            f'<g><text x="{label_width - 12}" y="{y + 22}" text-anchor="end" font-size="14">{label}</text>'
            f'<rect x="{label_width}" y="{y + 5}" width="{bar_width}" height="25" fill="#e5e7eb"/>'
            f'<rect x="{label_width}" y="{y + 5}" width="{bar_width * rate:.1f}" height="25" fill="#16a34a"/>'
            f'<text x="{label_width + bar_width + 12}" y="{y + 23}" font-size="14">{successes}/{total} ({rate:.0%})</text></g>'
        )
    height = top + len(shown) * row_height + bottom
    return (
        '<div class="chart-scroll success-chart">'
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{success_term(rows)} by configuration">'
        f'<text x="0" y="22" font-size="15">{success_term(rows)} by configuration</text>{"".join(bars)}</svg></div>'
    )


def strength_sort_key(strength: str) -> tuple[int, str]:
    match = re.search(r"(\d+)$", strength)
    return (int(match.group(1)) if match else -1, strength)


def method_intensity_heatmap(rows: list[dict[str, str]]) -> str:
    """Render success rates by method and strength without mixing methods."""
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        method, strength = perturbation_configuration(row)
        if strength:
            grouped[(method, strength)].append(row)
    if not grouped:
        return '<p class="sub">No budget or count values were recorded for this run.</p>'
    methods = sorted({method for method, _ in grouped})
    strengths = sorted({strength for _, strength in grouped}, key=strength_sort_key)
    header = "".join(f"<th>{html.escape(strength)}</th>" for strength in strengths)
    body: list[str] = []
    for method in methods:
        cells = []
        for strength in strengths:
            group = grouped.get((method, strength), [])
            if not group:
                cells.append('<td class="heatmap-empty">—</td>')
                continue
            successes = sum(attack_succeeded(row) for row in group)
            rate = successes / len(group)
            cells.append(
                f'<td class="heatmap-cell" style="--rate:{rate:.3f}" aria-label="{html.escape(method)} {html.escape(strength)}: {successes} of {len(group)}">'
                f'<strong>{rate:.0%}</strong><span>{successes}/{len(group)}</span></td>'
            )
        body.append(f'<tr><th>{html.escape(method)}</th>{"".join(cells)}</tr>')
    return (
        '<div class="heatmap-wrap"><h3>Method–intensity heatmap</h3>'
        f'<p class="sub">Each cell is {success_term(rows)} for one method and one strength. It shows whether stronger perturbations are consistently more effective.</p>'
        f'<div class="data-scroll"><table class="heatmap"><thead><tr><th>Method</th>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div></div>'
    )


def success_matrix(rows: list[dict[str, str]]) -> str:
    """Show which samples are compromised by which of the strongest configurations."""
    all_metrics = sorted(
        success_metrics(rows),
        key=lambda metric: (int(metric["successes"]), str(metric["selection"])),
        reverse=True,
    )
    metrics = all_metrics[:12] if len(all_metrics) > 12 else all_metrics
    selections = [str(metric["selection"]) for metric in metrics]
    samples = sorted({row["sample"] for row in rows})
    lookup = {(row["sample"], selection_key(row)): attack_succeeded(row) for row in rows}
    header = "".join(f'<th>{html.escape(selection)}</th>' for selection in selections)
    body = "".join(
        '<tr><th>{sample}</th>{cells}</tr>'.format(
            sample=html.escape(sample),
            cells="".join(
                '<td class="success" aria-label="attack succeeded">✓</td>' if lookup.get((sample, selection))
                else '<td class="failure" aria-label="attack did not succeed">–</td>'
                for selection in selections
            ),
        ) for sample in samples
    )
    scope_note = "All configurations are shown." if len(metrics) == len(all_metrics) else "Top 12 configurations by success count are shown."
    return (
        '<div class="matrix-wrap"><h3>Sample robustness matrix</h3><p class="sub">'
        f'Each row is one sample. A check mark means {success_term(rows)} succeeded. {scope_note}</p>'
        f'<div class="data-scroll"><table class="matrix"><thead><tr><th>Sample</th>{header}</tr></thead><tbody>{body}</tbody></table></div></div>'
    )


def available_runs() -> list[Path]:
    """Return every archived run that has a comparison table."""
    return sorted(
        candidate for candidate in Path("outputs").glob("run_*")
        if (candidate / "prediction_comparison.csv").is_file()
    )


def input_sample_count(run: Path, scored: list[dict[str, str]]) -> tuple[str, int]:
    """Prefer the immutable full-test input manifest over scored-variant coverage."""
    manifest = run / "input_manifest.csv"
    if manifest.is_file():
        with manifest.open(encoding="utf-8-sig", newline="") as handle:
            return "Input samples", sum(1 for _ in csv.DictReader(handle))
    return "Samples", len({row["sample"] for row in scored})


def render_index(runs: list[Path], output: Path) -> None:
    """Create a compact landing page for navigating all archived experiments."""
    cards: list[str] = []
    for run in runs:
        rows = read_rows(run / "prediction_comparison.csv")
        scored = [row for row in rows if is_scored(row)]
        selections = {selection_key(row) for row in scored}
        sample_label, sample_count = input_sample_count(run, scored)
        kind = "Code-level" if "_code_" in run.name else "Graph-level"
        if (run / "graph_random" / "prediction_comparison.csv").is_file() or (run / "graph_targeted" / "prediction_comparison.csv").is_file():
            kind = "Full test (code + graph)"
        cards.append(
            '<a class="run-card" href="{href}"><span class="kind">{kind}</span><h2>{name}</h2>'
            '<dl><div><dt>{sample_label}</dt><dd>{samples}</dd></div><div><dt>Scored variants</dt><dd>{variants}</dd></div>'
            '<div><dt>Configurations</dt><dd>{selections}</dd></div><div><dt>Prediction flips</dt><dd>{flips}</dd></div></dl></a>'.format(
                href=html.escape(f"{run.name}/dashboard.html"), kind=kind, name=html.escape(run.name),
                sample_label=html.escape(sample_label), samples=sample_count, variants=len(scored), selections=len(selections),
                flips=sum(row["flipped"].lower() == "true" for row in scored),
            )
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DeepWuKong experiment index</title><style>
body{{font-family:Inter,Segoe UI,Arial,sans-serif;font-size:clamp(16px,1vw,22px);margin:0;background:#f5f7fb;color:#172033}}main{{width:100%;box-sizing:border-box;padding:clamp(16px,2.2vw,32px)}}.sub{{color:#5d687c}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:26px}}.run-card{{display:block;color:inherit;text-decoration:none;background:white;border-radius:12px;padding:20px;box-shadow:0 2px 10px #17203312}}.run-card:hover{{box-shadow:0 6px 18px #17203322}}.run-card h2{{font-size:1.15em;margin:10px 0 18px;overflow-wrap:anywhere}}.kind{{color:#2457c5;font-weight:600}}dl{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:0}}dt{{font-size:.8em;color:#5d687c}}dd{{font-size:1.5em;font-weight:700;margin:3px 0 0}}
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
    scored_sample_count, unscored = len({row["sample"] for row in scored}), len(rows) - len(scored)
    input_label, input_count = input_sample_count(output.parent, scored)
    input_card = ""
    if input_label == "Input samples":
        input_card = f'<div class="card"><div class="value">{input_count}</div>input samples</div>'
    summary = robustness_summary(scored)
    success_cards = success_card(f"overall {success_term(scored)}", summary["overall"])
    success_cards += success_card("samples compromised at least once", summary["samples"])
    if summary["vulnerable"] is not None:
        success_cards += success_card("vulnerable-row success rate", summary["vulnerable"])
        success_cards += success_card("non-vulnerable-row success rate", summary["non_vulnerable"])
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
body{{font-family:Inter,Segoe UI,Arial,sans-serif;font-size:clamp(16px,1vw,22px);margin:0;background:#f5f7fb;color:#172033}}main{{width:100%;box-sizing:border-box;padding:clamp(16px,2.2vw,32px)}}h1{{font-size:1.7em;margin-bottom:4px}}h2{{font-size:1.35em}}h3{{font-size:1.1em;margin-bottom:.2em}}.sub{{color:#5d687c}}.run-switcher{{margin:16px 0}}.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}}.card{{background:white;border-radius:12px;padding:18px;min-width:170px;box-shadow:0 2px 10px #17203312}}.card small{{display:block;color:#5d687c;margin-top:4px}}.value{{font-size:2em;font-weight:700;color:#2457c5}}section{{background:white;border-radius:12px;padding:22px;margin:18px 0;box-shadow:0 2px 10px #17203312}}table{{width:100%;border-collapse:collapse;font-size:clamp(13px,.85vw,18px)}}th,td{{padding:.55em .5em;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#f1f5ff}}.delta{{font-variant-numeric:tabular-nums}}label{{display:inline-block;margin:4px 14px 8px 0}}select,input{{font:inherit}}.note{{padding:.7em;background:#fff8e5;border-left:4px solid #e6aa13}}.method-picker{{margin-top:14px;border:1px solid #cbd5e1;border-radius:8px;background:#f8faff}}.method-picker summary{{cursor:pointer;padding:.75em 1em;font-weight:600;font-size:1.05em}}.picker-actions{{padding:.5em 1em;border-top:1px solid #dbe4f2}}.picker-actions label{{font-weight:600;margin:0}}#action-checks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:4px 14px;max-height:420px;overflow-y:auto;padding:2px 16px 16px}}#action-checks label{{margin:0;padding:6px 2px;overflow-wrap:anywhere}}.evaluation svg{{display:block;max-width:none;height:auto;margin:0}}.chart-scroll,.data-scroll,.table-scroll{{overflow:auto;scrollbar-width:auto;scrollbar-color:#496b9e #e3eaf6}}.chart-scroll{{max-height:min(620px,65vh);margin:16px 0}}.chart-scroll svg{{width:100%;min-width:860px}}.data-scroll{{max-height:min(520px,55vh)}}.chart-scroll::-webkit-scrollbar,.data-scroll::-webkit-scrollbar,.table-scroll::-webkit-scrollbar{{width:16px;height:16px}}.chart-scroll::-webkit-scrollbar-track,.data-scroll::-webkit-scrollbar-track,.table-scroll::-webkit-scrollbar-track{{background:#e3eaf6}}.chart-scroll::-webkit-scrollbar-thumb,.data-scroll::-webkit-scrollbar-thumb,.table-scroll::-webkit-scrollbar-thumb{{background:#496b9e;border:3px solid #e3eaf6;border-radius:10px}}.heatmap{{min-width:600px}}.heatmap th{{overflow-wrap:anywhere}}.heatmap-cell{{text-align:center;background:rgba(22,163,74,var(--rate));min-width:88px}}.heatmap-cell strong,.heatmap-cell span{{display:block}}.heatmap-cell span{{font-size:.82em}}.heatmap-empty{{text-align:center;color:#6b7280;background:#f3f4f6}}.matrix{{font-size:12px;min-width:900px}}.matrix th{{max-width:130px;overflow-wrap:anywhere}}.matrix td{{text-align:center;font-weight:700}}.matrix .success{{background:#dcfce7;color:#166534}}.matrix .failure{{background:#f3f4f6;color:#6b7280}}.data-scroll thead th,.table-scroll thead th{{position:sticky;top:0;z-index:1}}.table-scroll{{max-height:min(680px,70vh);min-height:360px;overflow-y:scroll}}.summary-table-scroll{{max-height:min(620px,65vh)}}.variant-table{{table-layout:fixed;font-size:clamp(12px,.78vw,17px)}}.variant-table th,.variant-table td{{padding:.55em .45em;overflow-wrap:anywhere;vertical-align:top}}.variant-table th:nth-child(n+4),.variant-table td:nth-child(n+4){{text-align:center;white-space:nowrap}}
</style></head><body><main>
<h1>{html.escape(title)}</h1><p class="sub">Archived DeepWuKong robustness run - code- or graph-level perturbations compared with the same baseline prediction.</p>{run_selector}
<div class="cards">{input_card}<div class="card"><div class="value">{scored_sample_count}</div>samples with scored variants</div><div class="card"><div class="value">{len(scored)}</div>scored variants</div><div class="card"><div class="value">{flips}</div>prediction flips</div><div class="card"><div class="value">{unscored}</div>unscored / incomplete</div></div>
<section class="evaluation"><h2>Robustness evaluation</h2><p class="sub">{success_term(scored)} is the primary result. Targeted graph CSVs use their recorded attack success; code-level CSVs use a prediction-label flip. These measures are related but not identical.</p><div class="cards">{success_cards}</div>{svg_success_rate_chart(scored)}{method_intensity_heatmap(scored)}</section>
<section class="evaluation">{success_matrix(scored)}</section>
<section><h2>Sensitivity diagnostic</h2><p class="note"><strong>{html.escape(max_change['sample'])}</strong> with <strong>{html.escape(max_change['action'])}</strong> changed from {number(max_change, 'base_prob'):.6f} to {number(max_change, 'variant_prob'):.6f} ({number(max_change, 'delta_prob'):+.6f}) {max_change_note} This chart explains confidence movement; it is not the robustness success measure.</p>{svg_action_chart(metrics)}</section>
<section><h2>Action-level comparison</h2><div class="data-scroll summary-table-scroll"><table><thead><tr><th>{metric_name}</th><th>Scored variants</th><th>Mean probability delta</th><th>Mean delta nodes</th><th>Mean delta edges</th></tr></thead><tbody>{metric_rows}</tbody></table></div></section>
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
