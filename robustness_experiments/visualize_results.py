"""Create a self-contained, filterable report from an archived Demo B run."""

from __future__ import annotations

import argparse
import csv
import html
import math
import os
import re
import statistics
from collections import defaultdict
from pathlib import Path

NUMERIC_FIELDS = ("base_prob", "variant_prob", "delta_prob", "delta_nodes", "delta_edges")
ANALYSIS_FILENAME = "EXPERIMENT_ANALYSIS_ZH_EN.md"


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
    result["seed"] = row.get("seed") or ""
    result["baseline_eligible"] = row.get("baseline_eligible") or ""
    result["method_family"] = row.get("method_family") or ""
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
    return any(str(row.get("attack_success", "")).strip() for row in rows)


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


def attack_eligible(row: dict[str, str]) -> bool:
    """Limit ASR to samples whose baseline prediction was originally correct."""
    value = str(row.get("baseline_eligible", "")).strip().lower()
    if value:
        return value in {"1", "true", "yes"}
    return bool(str(row.get("attack_success", "")).strip())


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


def mean_confidence_interval(values: list[float]) -> tuple[float, float, float]:
    """Return a descriptive mean and normal-approximation 95% confidence interval."""
    if not values:
        return 0.0, 0.0, 0.0
    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, mean, mean
    margin = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return mean, mean - margin, mean + margin


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    """Return a 95% Wilson interval for a binary rate."""
    if total <= 0:
        return 0.0, 0.0
    z = 1.96
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def comparison_groups(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Aggregate one method at one strength without mixing independent variables."""
    all_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        method, strength = perturbation_configuration(row)
        all_groups[(method, strength or "fixed setting")].append(row)

    groups: list[dict[str, object]] = []
    for (method, strength), attempted_rows in sorted(
        all_groups.items(), key=lambda item: (item[0][0], strength_sort_key(item[0][1]))
    ):
        scored = [row for row in attempted_rows if is_scored(row)]
        outcome_rows = (
            [row for row in scored if attack_eligible(row)]
            if explicit_attack_success(attempted_rows)
            else scored
        )
        successes = sum(attack_succeeded(row) for row in outcome_rows)
        rate = successes / len(outcome_rows) if outcome_rows else 0.0
        rate_low, rate_high = wilson_interval(successes, len(outcome_rows))
        coverage_rate = len(scored) / len(attempted_rows) if attempted_rows else 0.0
        coverage_low, coverage_high = wilson_interval(len(scored), len(attempted_rows))
        deltas = [number(row, "delta_prob") for row in scored]
        absolute_deltas = [abs(value) for value in deltas]
        absolute_nodes = [abs(number(row, "delta_nodes")) for row in scored]
        absolute_edges = [abs(number(row, "delta_edges")) for row in scored]
        mean_delta, delta_low, delta_high = mean_confidence_interval(deltas)
        mean_abs, abs_low, abs_high = mean_confidence_interval(absolute_deltas)
        mean_nodes, nodes_low, nodes_high = mean_confidence_interval(absolute_nodes)
        mean_edges, edges_low, edges_high = mean_confidence_interval(absolute_edges)
        seeds = sorted({row["seed"] for row in attempted_rows if row.get("seed", "")})
        if len(seeds) > 1:
            seed_success_rates = []
            seed_coverage_rates = []
            for seed in seeds:
                seed_attempted = [row for row in attempted_rows if row["seed"] == seed]
                seed_scored = [row for row in seed_attempted if is_scored(row)]
                seed_outcomes = (
                    [row for row in seed_scored if attack_eligible(row)]
                    if explicit_attack_success(seed_attempted)
                    else seed_scored
                )
                if seed_outcomes:
                    seed_success_rates.append(
                        sum(attack_succeeded(row) for row in seed_outcomes) / len(seed_outcomes)
                    )
                seed_coverage_rates.append(
                    len(seed_scored) / len(seed_attempted) if seed_attempted else 0.0
                )
            if seed_success_rates:
                rate, rate_low, rate_high = mean_confidence_interval(seed_success_rates)
                rate_low, rate_high = max(0.0, rate_low), min(1.0, rate_high)
            coverage_rate, coverage_low, coverage_high = mean_confidence_interval(seed_coverage_rates)
            coverage_low, coverage_high = max(0.0, coverage_low), min(1.0, coverage_high)
        budget_match = re.search(r"(\d+)$", strength)
        groups.append({
            "method": method,
            "strength": strength,
            "budget": int(budget_match.group(1)) if budget_match else 1,
            "attempted": len(attempted_rows),
            "scored": len(scored),
            "outcome_scored": len(outcome_rows),
            "successes": successes,
            "seed_count": len(seeds) or 1,
            "success_rate": rate,
            "success_low": rate_low,
            "success_high": rate_high,
            "coverage_rate": coverage_rate,
            "coverage_low": coverage_low,
            "coverage_high": coverage_high,
            "mean_delta": mean_delta,
            "delta_low": delta_low,
            "delta_high": delta_high,
            "mean_abs_delta": mean_abs,
            "abs_low": max(0.0, abs_low),
            "abs_high": max(0.0, abs_high),
            "mean_abs_nodes": mean_nodes,
            "nodes_low": max(0.0, nodes_low),
            "nodes_high": max(0.0, nodes_high),
            "mean_abs_edges": mean_edges,
            "edges_low": max(0.0, edges_low),
            "edges_high": max(0.0, edges_high),
        })
    return groups


SERIES_COLOURS = ("#2563eb", "#dc2626", "#059669", "#7c3aed", "#d97706", "#0891b2")


def friendly_method(method: str) -> str:
    family, separator, action = method.partition("::")
    friendly_action = (action if separator else family).replace("winner_xfg_", "XFG ").replace("_", " ")
    if not separator:
        return friendly_action
    family_name = {
        "random_graph": "Random graph",
        "winner_xfg": "Winner-XFG",
    }.get(family, family.replace("_", " "))
    return f"{family_name} - {friendly_action}"


def group_setting_label(group: dict[str, object]) -> str:
    strength = str(group["strength"])
    return str(group["budget"]) if strength.startswith("budget ") else strength


METRIC_INTERVALS = {
    "success_rate": ("success_low", "success_high"),
    "coverage_rate": ("coverage_low", "coverage_high"),
    "mean_delta": ("delta_low", "delta_high"),
    "mean_abs_delta": ("abs_low", "abs_high"),
    "mean_abs_nodes": ("nodes_low", "nodes_high"),
    "mean_abs_edges": ("edges_low", "edges_high"),
}


def metric_interval(group: dict[str, object], metric: str) -> tuple[float, float]:
    low_key, high_key = METRIC_INTERVALS[metric]
    return float(group[low_key]), float(group[high_key])


def spread_label_positions(
    items: list[tuple[str, float]], minimum: float, maximum: float, gap: float = 17.0
) -> dict[str, float]:
    """Keep direct point labels readable when estimates are tied or close."""
    ordered = sorted(items, key=lambda item: item[1])
    placed: list[list[object]] = []
    for key, preferred in ordered:
        position = max(minimum, preferred)
        if placed:
            position = max(position, float(placed[-1][1]) + gap)
        placed.append([key, position])
    if placed and float(placed[-1][1]) > maximum:
        shift = float(placed[-1][1]) - maximum
        for item in placed:
            item[1] = float(item[1]) - shift
    if placed and float(placed[0][1]) < minimum:
        shift = minimum - float(placed[0][1])
        for item in placed:
            item[1] = float(item[1]) + shift
    return {str(key): float(position) for key, position in placed}


def svg_budget_lines(groups: list[dict[str, object]], metric: str, label: str, percent: bool = False) -> str:
    """Plot one response variable over budget, with one stable line per method."""
    budgets = sorted({int(group["budget"]) for group in groups})
    methods = sorted({str(group["method"]) for group in groups})
    lookup = {(str(group["method"]), int(group["budget"])): group for group in groups}
    width, height = 1080, 500
    left, right, top, bottom = 84, 260, 34, 72
    plot_width, plot_height = width - left - right, height - top - bottom
    _, upper_key = METRIC_INTERVALS[metric]
    maximum = max((float(group[upper_key]) for group in groups), default=1.0)
    if percent:
        y_max = min(1.0, max(0.1, math.ceil(maximum * 10) / 10))
    else:
        y_max = max(0.01, math.ceil(maximum * 20) / 20)

    def x_for(budget: int) -> float:
        return left + (budgets.index(budget) / max(1, len(budgets) - 1)) * plot_width

    def y_for(value: float) -> float:
        return top + plot_height - max(0.0, min(value, y_max)) / y_max * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = y_max * tick / 5
        y = y_for(value)
        text = f"{value:.0%}" if percent else f"{value:.3f}"
        marks.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>')
        marks.append(f'<text class="axis-label" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{text}</text>')
    for budget in budgets:
        x = x_for(budget)
        marks.append(f'<text class="axis-label" x="{x:.1f}" y="{top + plot_height + 30}" text-anchor="middle">{budget}</text>')

    label_positions: dict[tuple[str, int], float] = {}
    for budget in budgets:
        positions = spread_label_positions(
            [
                (method, y_for(float(lookup[(method, budget)][metric])))
                for method in methods if (method, budget) in lookup
            ],
            top + 10,
            top + plot_height - 10,
        )
        label_positions.update({(method, budget): position for method, position in positions.items()})

    legend: list[str] = []
    for index, method in enumerate(methods):
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        points = [lookup[(method, budget)] for budget in budgets if (method, budget) in lookup]
        path = " ".join(
            f'{"M" if point_index == 0 else "L"}{x_for(int(point["budget"])):.1f},{y_for(float(point[metric])):.1f}'
            for point_index, point in enumerate(points)
        )
        marks.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="3"/>')
        for point in points:
            x, value = x_for(int(point["budget"])), float(point[metric])
            low, high = metric_interval(point, metric)
            value_text = f"{value:.0%}" if percent else f"{value:.3f}"
            label_y = label_positions[(method, int(point["budget"]))] + 5
            marks.append(
                f'<line x1="{x:.1f}" y1="{y_for(low):.1f}" x2="{x:.1f}" y2="{y_for(high):.1f}" stroke="{colour}" stroke-width="1.5"/>'
                f'<line x1="{x - 5:.1f}" y1="{y_for(low):.1f}" x2="{x + 5:.1f}" y2="{y_for(low):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - 5:.1f}" y1="{y_for(high):.1f}" x2="{x + 5:.1f}" y2="{y_for(high):.1f}" stroke="{colour}"/>'
                f'<circle cx="{x:.1f}" cy="{y_for(value):.1f}" r="6" fill="{colour}" stroke="white" stroke-width="2"/>'
                f'<text class="point-label" x="{x + 8:.1f}" y="{label_y:.1f}">{value_text}</text>'
            )
        legend_y = top + index * 34 + 8
        legend.append(
            f'<line x1="{left + plot_width + 34}" y1="{legend_y}" x2="{left + plot_width + 62}" y2="{legend_y}" stroke="{colour}" stroke-width="3"/>'
            f'<circle cx="{left + plot_width + 48}" cy="{legend_y}" r="5" fill="{colour}"/>'
            f'<text class="legend-label" x="{left + plot_width + 74}" y="{legend_y + 5}">{html.escape(friendly_method(method))}</text>'
        )
    return (
        '<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 1080 500" role="img" '
        f'aria-label="{html.escape(label)} by budget with 95 percent confidence intervals">'
        f'<title>{html.escape(label)} by budget</title><desc>Each line is one method. Budget is the only changing variable along the x axis. Error bars are 95 percent confidence intervals.</desc>'
        f'{"".join(marks)}{"".join(legend)}'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 18}" text-anchor="middle">Budget</text>'
        f'<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
    )


def svg_fixed_comparison(groups: list[dict[str, object]], metric: str, label: str, percent: bool = False) -> str:
    """Compare methods at one fixed setting using point estimates and 95% intervals."""
    shown = sorted(groups, key=lambda group: float(group[metric]), reverse=True)
    width, left, right = 1080, 320, 150
    row_height, top, bottom = 48, 48, 64
    height = top + len(shown) * row_height + bottom
    _, upper_key = METRIC_INTERVALS[metric]
    maximum = max((float(group[upper_key]) for group in shown), default=1.0)
    x_max = 1.0 if percent else max(0.01, math.ceil(maximum * 20) / 20)
    plot_width = width - left - right

    def x_for(value: float) -> float:
        return left + max(0.0, min(value, x_max)) / x_max * plot_width

    marks: list[str] = []
    for tick in range(6):
        value = x_max * tick / 5
        x = x_for(value)
        tick_text = f"{value:.0%}" if percent else f"{value:.3f}"
        marks.append(f'<line class="grid" x1="{x:.1f}" y1="{top - 15}" x2="{x:.1f}" y2="{height - bottom}"/>')
        marks.append(f'<text class="axis-label" x="{x:.1f}" y="{height - 25}" text-anchor="middle">{tick_text}</text>')
    for index, group in enumerate(shown):
        y = top + index * row_height + 12
        value = float(group[metric])
        low, high = metric_interval(group, metric)
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        value_text = f"{value:.1%}" if percent else f"{value:.4f}"
        evidence_count = (
            int(group["outcome_scored"])
            if metric == "success_rate"
            else int(group["scored"])
        )
        marks.append(
            f'<text class="method-label" x="{left - 16}" y="{y + 5}" text-anchor="end">{html.escape(friendly_method(str(group["method"])))}</text>'
            f'<line x1="{x_for(low):.1f}" y1="{y}" x2="{x_for(high):.1f}" y2="{y}" stroke="{colour}" stroke-width="3"/>'
            f'<line x1="{x_for(low):.1f}" y1="{y - 6}" x2="{x_for(low):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<line x1="{x_for(high):.1f}" y1="{y - 6}" x2="{x_for(high):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<circle cx="{x_for(value):.1f}" cy="{y}" r="6" fill="{colour}" stroke="white" stroke-width="2"/>'
            f'<text class="point-label" x="{x_for(high) + 10:.1f}" y="{y + 5}">{value_text} (n={evidence_count})</text>'
        )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(label)} by method at a fixed setting with 95 percent confidence intervals">'
        f'<title>{html.escape(label)} at a fixed setting</title><desc>Methods are compared at the same configured perturbation setting. Points are estimates and horizontal bars are 95 percent confidence intervals.</desc>'
        f'{"".join(marks)}<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 4}" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
    )


def signed_domain(groups: list[dict[str, object]], metric: str) -> tuple[float, float]:
    """Create a zero-inclusive domain for directional effects."""
    lows, highs = zip(*(metric_interval(group, metric) for group in groups))
    minimum, maximum = min(0.0, min(lows)), max(0.0, max(highs))
    if minimum == maximum:
        return -0.05, 0.05
    padding = (maximum - minimum) * 0.08
    return minimum - padding, maximum + padding


def svg_budget_signed_lines(groups: list[dict[str, object]], metric: str, label: str) -> str:
    """Plot a signed response over budget while keeping every method fixed."""
    budgets = sorted({int(group["budget"]) for group in groups})
    methods = sorted({str(group["method"]) for group in groups})
    lookup = {(str(group["method"]), int(group["budget"])): group for group in groups}
    width, height = 1080, 500
    left, right, top, bottom = 84, 260, 34, 72
    plot_width, plot_height = width - left - right, height - top - bottom
    y_min, y_max = signed_domain(groups, metric)

    def x_for(budget: int) -> float:
        return left + (budgets.index(budget) / max(1, len(budgets) - 1)) * plot_width

    def y_for(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = y_min + (y_max - y_min) * tick / 5
        y = y_for(value)
        marks.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>')
        marks.append(f'<text class="axis-label" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{value:+.3f}</text>')
    marks.append(
        f'<line class="zero-line" x1="{left}" y1="{y_for(0):.1f}" x2="{left + plot_width}" y2="{y_for(0):.1f}"/>'
    )
    for budget in budgets:
        marks.append(
            f'<text class="axis-label" x="{x_for(budget):.1f}" y="{top + plot_height + 30}" text-anchor="middle">{budget}</text>'
        )
    label_positions: dict[tuple[str, int], float] = {}
    for budget in budgets:
        positions = spread_label_positions(
            [
                (method, y_for(float(lookup[(method, budget)][metric])))
                for method in methods if (method, budget) in lookup
            ],
            top + 10,
            top + plot_height - 10,
        )
        label_positions.update({(method, budget): position for method, position in positions.items()})
    legend: list[str] = []
    for index, method in enumerate(methods):
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        points = [lookup[(method, budget)] for budget in budgets if (method, budget) in lookup]
        path = " ".join(
            f'{"M" if point_index == 0 else "L"}{x_for(int(point["budget"])):.1f},{y_for(float(point[metric])):.1f}'
            for point_index, point in enumerate(points)
        )
        marks.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="3"/>')
        for point in points:
            x, value = x_for(int(point["budget"])), float(point[metric])
            low, high = metric_interval(point, metric)
            label_y = label_positions[(method, int(point["budget"]))] + 5
            marks.append(
                f'<line x1="{x:.1f}" y1="{y_for(low):.1f}" x2="{x:.1f}" y2="{y_for(high):.1f}" stroke="{colour}" stroke-width="1.5"/>'
                f'<line x1="{x - 5:.1f}" y1="{y_for(low):.1f}" x2="{x + 5:.1f}" y2="{y_for(low):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - 5:.1f}" y1="{y_for(high):.1f}" x2="{x + 5:.1f}" y2="{y_for(high):.1f}" stroke="{colour}"/>'
                f'<circle cx="{x:.1f}" cy="{y_for(value):.1f}" r="6" fill="{colour}" stroke="white" stroke-width="2"/>'
                f'<text class="point-label" x="{x + 8:.1f}" y="{label_y:.1f}">{value:+.3f}</text>'
            )
        legend_y = top + index * 34 + 8
        legend.append(
            f'<line x1="{left + plot_width + 34}" y1="{legend_y}" x2="{left + plot_width + 62}" y2="{legend_y}" stroke="{colour}" stroke-width="3"/>'
            f'<circle cx="{left + plot_width + 48}" cy="{legend_y}" r="5" fill="{colour}"/>'
            f'<text class="legend-label" x="{left + plot_width + 74}" y="{legend_y + 5}">{html.escape(friendly_method(method))}</text>'
        )
    return (
        '<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 1080 500" role="img" '
        f'aria-label="{html.escape(label)} by budget with 95 percent confidence intervals">'
        f'<title>{html.escape(label)} by budget</title><desc>Each line fixes the method and changes only budget. Values above zero increase the predicted vulnerability probability; values below zero decrease it.</desc>'
        f'{"".join(marks)}{"".join(legend)}'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 18}" text-anchor="middle">Budget</text>'
        f'<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
    )


def svg_fixed_signed_comparison(groups: list[dict[str, object]], metric: str, label: str) -> str:
    """Compare signed method effects at one fixed setting around a zero reference."""
    shown = sorted(groups, key=lambda group: float(group[metric]))
    width, left, right = 1080, 320, 150
    row_height, top, bottom = 48, 48, 64
    height = top + len(shown) * row_height + bottom
    x_min, x_max = signed_domain(shown, metric)
    plot_width = width - left - right

    def x_for(value: float) -> float:
        return left + (value - x_min) / (x_max - x_min) * plot_width

    marks: list[str] = []
    for tick in range(6):
        value = x_min + (x_max - x_min) * tick / 5
        x = x_for(value)
        marks.append(f'<line class="grid" x1="{x:.1f}" y1="{top - 15}" x2="{x:.1f}" y2="{height - bottom}"/>')
        marks.append(f'<text class="axis-label" x="{x:.1f}" y="{height - 25}" text-anchor="middle">{value:+.3f}</text>')
    marks.append(
        f'<line class="zero-line" x1="{x_for(0):.1f}" y1="{top - 15}" x2="{x_for(0):.1f}" y2="{height - bottom}"/>'
    )
    for index, group in enumerate(shown):
        y = top + index * row_height + 12
        value = float(group[metric])
        low, high = metric_interval(group, metric)
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        marks.append(
            f'<text class="method-label" x="{left - 16}" y="{y + 5}" text-anchor="end">{html.escape(friendly_method(str(group["method"])))}</text>'
            f'<line x1="{x_for(low):.1f}" y1="{y}" x2="{x_for(high):.1f}" y2="{y}" stroke="{colour}" stroke-width="3"/>'
            f'<line x1="{x_for(low):.1f}" y1="{y - 6}" x2="{x_for(low):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<line x1="{x_for(high):.1f}" y1="{y - 6}" x2="{x_for(high):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<circle cx="{x_for(value):.1f}" cy="{y}" r="6" fill="{colour}" stroke="white" stroke-width="2"/>'
            f'<text class="point-label" x="{x_for(high) + 10:.1f}" y="{y + 5}">{value:+.4f} (n={int(group["scored"])})</text>'
        )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(label)} by method at a fixed setting">'
        f'<title>{html.escape(label)} at a fixed setting</title><desc>Methods are compared at one fixed configured setting. The darker reference line is zero; estimates to either side show effect direction.</desc>'
        f'{"".join(marks)}<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 4}" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
    )


def percentile(values: list[float], proportion: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * proportion
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution_summary(values: list[float]) -> tuple[float, float, float, float, float]:
    return min(values), percentile(values, 0.25), percentile(values, 0.5), percentile(values, 0.75), max(values)


def svg_fixed_delta_boxplots(rows: list[dict[str, str]]) -> str:
    """Show sample-level signed probability changes by method at a fixed budget."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if is_scored(row):
            method, _ = perturbation_configuration(row)
            grouped[method].append(number(row, "delta_prob"))
    summaries = [(method, values, distribution_summary(values)) for method, values in grouped.items()]
    summaries.sort(key=lambda item: statistics.fmean(abs(value) for value in item[1]), reverse=True)
    all_values = [value for _, values, _ in summaries for value in values]
    minimum, maximum = min(0.0, min(all_values)), max(0.0, max(all_values))
    if minimum == maximum:
        minimum, maximum = -0.05, 0.05
    padding = (maximum - minimum) * 0.06
    minimum, maximum = minimum - padding, maximum + padding
    width, left, right = 1080, 320, 90
    row_height, top, bottom = 48, 45, 62
    height = top + len(summaries) * row_height + bottom
    plot_width = width - left - right

    def x_for(value: float) -> float:
        return left + (value - minimum) / (maximum - minimum) * plot_width

    marks: list[str] = []
    for tick in range(6):
        value = minimum + (maximum - minimum) * tick / 5
        x = x_for(value)
        marks.append(f'<line class="grid" x1="{x:.1f}" y1="{top - 15}" x2="{x:.1f}" y2="{height - bottom}"/>')
        marks.append(f'<text class="axis-label" x="{x:.1f}" y="{height - 24}" text-anchor="middle">{value:+.2f}</text>')
    marks.append(f'<line class="zero-line" x1="{x_for(0):.1f}" y1="{top - 15}" x2="{x_for(0):.1f}" y2="{height - bottom}"/>')
    for index, (method, values, (low, q1, median, q3, high)) in enumerate(summaries):
        y = top + index * row_height + 12
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        marks.append(
            f'<text class="method-label" x="{left - 16}" y="{y + 5}" text-anchor="end">{html.escape(friendly_method(method))}</text>'
            f'<line x1="{x_for(low):.1f}" y1="{y}" x2="{x_for(high):.1f}" y2="{y}" stroke="{colour}"/>'
            f'<line x1="{x_for(low):.1f}" y1="{y - 6}" x2="{x_for(low):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<line x1="{x_for(high):.1f}" y1="{y - 6}" x2="{x_for(high):.1f}" y2="{y + 6}" stroke="{colour}"/>'
            f'<rect x="{x_for(q1):.1f}" y="{y - 10}" width="{max(1.0, x_for(q3) - x_for(q1)):.1f}" height="20" fill="{colour}" fill-opacity="0.22" stroke="{colour}"/>'
            f'<line x1="{x_for(median):.1f}" y1="{y - 10}" x2="{x_for(median):.1f}" y2="{y + 10}" stroke="{colour}" stroke-width="3"/>'
            f'<text class="point-label" x="{x_for(high) + 8:.1f}" y="{y + 5}">n={len(values)}</text>'
        )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 {width} {height}" role="img" aria-label="Sample probability change distributions by method">'
        '<title>Sample-level probability change distributions</title><desc>Methods are compared at the same configured setting. Boxes span the interquartile range, the inner line is the median, and whiskers show the observed range.</desc>'
        f'{"".join(marks)}<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 4}" text-anchor="middle">Signed probability change</text></svg></div>'
    )


def svg_budget_delta_small_multiples(rows: list[dict[str, str]]) -> str:
    """Facet sample-level delta distributions by method with a shared scale."""
    grouped: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        if is_scored(row):
            method, strength = perturbation_configuration(row)
            match = re.search(r"(\d+)$", strength or "1")
            grouped[(method, int(match.group(1)) if match else 1)].append(number(row, "delta_prob"))
    methods = sorted({method for method, _ in grouped})
    budgets = sorted({budget for _, budget in grouped})
    all_values = [value for values in grouped.values() for value in values]
    minimum, maximum = min(0.0, min(all_values)), max(0.0, max(all_values))
    if minimum == maximum:
        minimum, maximum = -0.05, 0.05
    padding = (maximum - minimum) * 0.08
    minimum, maximum = minimum - padding, maximum + padding
    width, height = 1080, 430
    left, right, top, bottom, panel_gap = 72, 24, 52, 68, 32
    plot_height = height - top - bottom
    panel_width = (width - left - right - panel_gap * (len(methods) - 1)) / max(1, len(methods))

    def y_for(value: float) -> float:
        return top + (maximum - value) / (maximum - minimum) * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = minimum + (maximum - minimum) * tick / 5
        y = y_for(value)
        marks.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>')
        marks.append(f'<text class="axis-label" x="{left - 10}" y="{y + 5:.1f}" text-anchor="end">{value:+.2f}</text>')
    marks.append(f'<line class="zero-line" x1="{left}" y1="{y_for(0):.1f}" x2="{width - right}" y2="{y_for(0):.1f}"/>')
    for method_index, method in enumerate(methods):
        panel_left = left + method_index * (panel_width + panel_gap)
        marks.append(
            f'<text class="method-label" x="{panel_left + panel_width / 2:.1f}" y="22" text-anchor="middle">{html.escape(friendly_method(method))}</text>'
        )
        for budget_index, budget in enumerate(budgets):
            values = grouped.get((method, budget), [])
            if not values:
                continue
            low, q1, median, q3, high = distribution_summary(values)
            x = panel_left + (budget_index + 0.5) * panel_width / len(budgets)
            colour = SERIES_COLOURS[method_index % len(SERIES_COLOURS)]
            marks.append(
                f'<line x1="{x:.1f}" y1="{y_for(low):.1f}" x2="{x:.1f}" y2="{y_for(high):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - 6:.1f}" y1="{y_for(low):.1f}" x2="{x + 6:.1f}" y2="{y_for(low):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - 6:.1f}" y1="{y_for(high):.1f}" x2="{x + 6:.1f}" y2="{y_for(high):.1f}" stroke="{colour}"/>'
                f'<rect x="{x - 12:.1f}" y="{y_for(q3):.1f}" width="24" height="{max(1.0, y_for(q1) - y_for(q3)):.1f}" fill="{colour}" fill-opacity="0.22" stroke="{colour}"/>'
                f'<line x1="{x - 12:.1f}" y1="{y_for(median):.1f}" x2="{x + 12:.1f}" y2="{y_for(median):.1f}" stroke="{colour}" stroke-width="3"/>'
                f'<text class="axis-label" x="{x:.1f}" y="{height - 34}" text-anchor="middle">B{budget}</text>'
            )
    return (
        '<div class="chart-wrap"><svg class="comparison-chart" viewBox="0 0 1080 430" role="img" aria-label="Sample probability change distributions by budget, faceted by method">'
        '<title>Sample-level probability change distributions by budget</title><desc>Each panel fixes one method and changes only budget. Every panel shares the same probability-change scale.</desc>'
        f'{"".join(marks)}<text class="axis-title" transform="translate(18 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">Signed probability change</text></svg></div>'
    )


def horizontal_budget_comparisons(
    groups: list[dict[str, object]],
    metric: str,
    label: str,
    *,
    percent: bool = False,
) -> str:
    """Compare all methods side by side while holding one budget fixed."""
    panels = []
    for budget in sorted({int(group["budget"]) for group in groups}):
        peers = [group for group in groups if int(group["budget"]) == budget]
        panels.append(
            f'<div class="chart-block"><h3>Budget {budget}</h3>'
            f'{svg_fixed_comparison(peers, metric, f"{label} at budget {budget}", percent=percent)}</div>'
        )
    return "".join(panels)


def evidence_insights(groups: list[dict[str, object]], rows: list[dict[str, str]]) -> list[str]:
    """Produce conservative, reproducible observations from the displayed aggregates."""
    if not groups:
        return ["No scored comparisons are available."]
    insights: list[str] = []
    outcome_label = "ASR" if explicit_attack_success(rows) else "prediction flip rate"
    budgets = sorted({int(group["budget"]) for group in groups})
    if len(budgets) > 1:
        for budget in budgets:
            peers = [group for group in groups if int(group["budget"]) == budget]
            top_rate = max(float(group["success_rate"]) for group in peers)
            leaders = [group for group in peers if float(group["success_rate"]) == top_rate]
            leader_names = " and ".join(friendly_method(str(group["method"])) for group in leaders)
            leader_verb = "have" if len(leaders) > 1 else "has"
            top = leaders[0]
            insights.append(
                f'At budget {budget}, {leader_names} {leader_verb} the highest observed {outcome_label} '
                f'({float(top["success_rate"]):.1%}, {int(top["successes"])}/{int(top["outcome_scored"])} eligible scored cases).'
            )
        for method in sorted({str(group["method"]) for group in groups}):
            series = sorted((group for group in groups if group["method"] == method), key=lambda group: int(group["budget"]))
            rates = [float(group["success_rate"]) for group in series]
            if len(rates) >= 2:
                if len(set(rates)) == 1:
                    pattern = "constant"
                elif all(right >= left for left, right in zip(rates, rates[1:])):
                    pattern = "non-decreasing"
                elif all(right <= left for left, right in zip(rates, rates[1:])):
                    pattern = "non-increasing"
                else:
                    pattern = "non-monotonic"
                insights.append(
                    f'{friendly_method(method)} shows a {pattern} budget-response pattern '
                    f'({rates[0]:.1%} at budget {int(series[0]["budget"])} versus {rates[-1]:.1%} at budget {int(series[-1]["budget"])}).'
                )
    else:
        top_success = max(groups, key=lambda group: (float(group["success_rate"]), int(group["successes"])))
        top_effect = max(groups, key=lambda group: float(group["mean_abs_delta"]))
        if float(top_success["success_rate"]) == 0:
            insights.append(f'No scored method caused a {outcome_label} event at this fixed setting.')
        else:
            insights.append(
                f'{friendly_method(str(top_success["method"]))} has the highest observed {outcome_label} '
                f'({float(top_success["success_rate"]):.1%}, {int(top_success["successes"])}/{int(top_success["outcome_scored"])} eligible scored cases).'
            )
        insights.append(
            f'{friendly_method(str(top_effect["method"]))} produces the largest mean absolute probability change '
            f'({float(top_effect["mean_abs_delta"]):.4f}, n={int(top_effect["scored"])}).'
        )
        low_coverage = [group for group in groups if int(group["scored"]) < int(group["attempted"]) / 2]
        if low_coverage:
            names = ", ".join(friendly_method(str(group["method"])) for group in low_coverage[:4])
            insights.append(f'{names} apply to fewer than half of attempted samples; compare their effect sizes with that limited coverage in mind.')
    upward = max(groups, key=lambda group: float(group["mean_delta"]))
    downward = min(groups, key=lambda group: float(group["mean_delta"]))
    upward_name = friendly_method(str(upward["method"])) + (f' at budget {upward["budget"]}' if len(budgets) > 1 else "")
    downward_name = friendly_method(str(downward["method"])) + (f' at budget {downward["budget"]}' if len(budgets) > 1 else "")
    insights.append(
        f'{upward_name} has the largest upward mean probability shift '
        f'({float(upward["mean_delta"]):+.4f}); {downward_name} has the largest downward shift '
        f'({float(downward["mean_delta"]):+.4f}).'
    )
    lowest_coverage = min(groups, key=lambda group: float(group["coverage_rate"]))
    highest_coverage = max(groups, key=lambda group: float(group["coverage_rate"]))
    if float(lowest_coverage["coverage_rate"]) != float(highest_coverage["coverage_rate"]):
        lowest_name = friendly_method(str(lowest_coverage["method"])) + (f' at budget {lowest_coverage["budget"]}' if len(budgets) > 1 else "")
        highest_name = friendly_method(str(highest_coverage["method"])) + (f' at budget {highest_coverage["budget"]}' if len(budgets) > 1 else "")
        insights.append(
            f'Scored coverage ranges from {float(lowest_coverage["coverage_rate"]):.1%} for '
            f'{lowest_name} to {float(highest_coverage["coverage_rate"]):.1%} for '
            f'{highest_name}; effectiveness estimates should be read with that applicability difference.'
        )
    largest_nodes = max(groups, key=lambda group: float(group["mean_abs_nodes"]))
    largest_edges = max(groups, key=lambda group: float(group["mean_abs_edges"]))
    nodes_name = friendly_method(str(largest_nodes["method"])) + (f' at budget {largest_nodes["budget"]}' if len(budgets) > 1 else "")
    edges_name = friendly_method(str(largest_edges["method"])) + (f' at budget {largest_edges["budget"]}' if len(budgets) > 1 else "")
    insights.append(
        f'{nodes_name} produces the largest mean absolute node change '
        f'({float(largest_nodes["mean_abs_nodes"]):.2f}), while {edges_name} produces the largest mean absolute edge change '
        f'({float(largest_edges["mean_abs_edges"]):.2f}).'
    )
    return insights


def budget_response_pattern(rates: list[float]) -> str:
    """Classify an observed budget-response series without implying causality."""
    if len(set(rates)) == 1:
        return "constant"
    if all(right >= left for left, right in zip(rates, rates[1:])):
        return "non-decreasing"
    if all(right <= left for left, right in zip(rates, rates[1:])):
        return "non-increasing"
    return "non-monotonic"


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def bilingual_findings(
    groups: list[dict[str, object]], rows: list[dict[str, str]], language: str
) -> list[str]:
    """Generate parallel English or Chinese observations from the same aggregates."""
    if not groups:
        return ["No scored comparisons are available." if language == "en" else "没有可用于统计的有效对比结果。"]
    targeted = explicit_attack_success(rows)
    outcome = "ASR" if targeted else ("prediction flip rate" if language == "en" else "预测翻转率")
    budgets = sorted({int(group["budget"]) for group in groups})
    findings: list[str] = []
    if len(budgets) > 1:
        for budget in budgets:
            peers = [group for group in groups if int(group["budget"]) == budget]
            top_rate = max(float(group["success_rate"]) for group in peers)
            leaders = [group for group in peers if float(group["success_rate"]) == top_rate]
            details = "; ".join(
                f'{friendly_method(str(group["method"]))}: {float(group["success_rate"]):.1%} '
                f'({int(group["successes"])}/{int(group["outcome_scored"])}, 95% CI '
                f'[{float(group["success_low"]):.1%}, {float(group["success_high"]):.1%}])'
                for group in leaders
            )
            if language == "en":
                findings.append(f"At budget {budget}, the highest observed {outcome} is: {details}.")
            else:
                findings.append(f"在预算 {budget} 下，观测到的最高{outcome}为：{details}。")
        pattern_zh = {
            "constant": "保持不变",
            "non-decreasing": "非递减",
            "non-increasing": "非递增",
            "non-monotonic": "非单调",
        }
        for method in sorted({str(group["method"]) for group in groups}):
            series = sorted(
                (group for group in groups if group["method"] == method),
                key=lambda group: int(group["budget"]),
            )
            rates = [float(group["success_rate"]) for group in series]
            sequence = " -> ".join(
                f'B{int(group["budget"])}={float(group["success_rate"]):.1%}' for group in series
            )
            pattern = budget_response_pattern(rates)
            if language == "en":
                findings.append(
                    f'{friendly_method(method)} has an observed {pattern} budget response ({sequence}).'
                )
            else:
                findings.append(
                    f'{friendly_method(method)} 的预算响应呈{pattern_zh[pattern]}模式（{sequence}）。'
                )
    else:
        top_rate = max(float(group["success_rate"]) for group in groups)
        leaders = [group for group in groups if float(group["success_rate"]) == top_rate]
        leader_details = "; ".join(
            f'{friendly_method(str(group["method"]))}: {float(group["success_rate"]):.1%} '
            f'({int(group["successes"])}/{int(group["outcome_scored"])}, 95% CI '
            f'[{float(group["success_low"]):.1%}, {float(group["success_high"]):.1%}])'
            for group in leaders
        )
        top_effect = max(groups, key=lambda group: float(group["mean_abs_delta"]))
        if language == "en":
            findings.append(f"At the fixed setting, the highest observed {outcome} is: {leader_details}.")
            findings.append(
                f'{friendly_method(str(top_effect["method"]))} has the largest mean absolute probability change '
                f'({float(top_effect["mean_abs_delta"]):.4f}, n={int(top_effect["scored"])}).'
            )
        else:
            findings.append(f"在固定设置下，观测到的最高{outcome}为：{leader_details}。")
            findings.append(
                f'{friendly_method(str(top_effect["method"]))} 的平均绝对概率变化最大'
                f'（{float(top_effect["mean_abs_delta"]):.4f}，n={int(top_effect["scored"])}）。'
            )
    low_coverage = [group for group in groups if int(group["scored"]) < int(group["attempted"]) / 2]
    if low_coverage:
        names = ", ".join(friendly_method(str(group["method"])) for group in low_coverage)
        if language == "en":
            findings.append(
                f"Coverage warning: {names} were scored on fewer than half of attempted cases; their estimates are less representative of the full input set."
            )
        else:
            findings.append(
                f"覆盖率提示：{names} 的有效评分样本少于尝试样本的一半，其估计值对完整输入集的代表性较弱。"
            )
    upward = max(groups, key=lambda group: float(group["mean_delta"]))
    downward = min(groups, key=lambda group: float(group["mean_delta"]))
    largest_nodes = max(groups, key=lambda group: float(group["mean_abs_nodes"]))
    largest_edges = max(groups, key=lambda group: float(group["mean_abs_edges"]))

    def named(group: dict[str, object]) -> str:
        suffix = f' at budget {group["budget"]}' if language == "en" else f'（预算 {group["budget"]}）'
        return friendly_method(str(group["method"])) + (suffix if len(budgets) > 1 else "")

    if language == "en":
        findings.append(
            f'{named(upward)} has the largest upward mean probability shift ({float(upward["mean_delta"]):+.4f}); '
            f'{named(downward)} has the largest downward shift ({float(downward["mean_delta"]):+.4f}).'
        )
        findings.append(
            f'{named(largest_nodes)} has the largest mean absolute node change ({float(largest_nodes["mean_abs_nodes"]):.2f}); '
            f'{named(largest_edges)} has the largest mean absolute edge change ({float(largest_edges["mean_abs_edges"]):.2f}).'
        )
    else:
        findings.append(
            f'{named(upward)} 的平均预测概率向上变化最大（{float(upward["mean_delta"]):+.4f}）；'
            f'{named(downward)} 的平均预测概率向下变化最大（{float(downward["mean_delta"]):+.4f}）。'
        )
        findings.append(
            f'{named(largest_nodes)} 的平均绝对节点变化最大（{float(largest_nodes["mean_abs_nodes"]):.2f}）；'
            f'{named(largest_edges)} 的平均绝对边变化最大（{float(largest_edges["mean_abs_edges"]):.2f}）。'
        )
    return findings


def render_analysis_document(rows: list[dict[str, str]], output: Path, title: str) -> None:
    """Write a reproducible bilingual Markdown companion beside a run dashboard."""
    scored = [row for row in rows if is_scored(row)]
    if not scored:
        raise ValueError("the comparison CSV has no successful rows with complete numeric prediction data")
    groups = comparison_groups(rows)
    chart_groups = [group for group in groups if int(group["scored"]) > 0]
    outcome_rows = (
        [row for row in scored if attack_eligible(row)]
        if explicit_attack_success(scored)
        else scored
    )
    successes = sum(attack_succeeded(row) for row in outcome_rows)
    sample_label, sample_count = input_sample_count(output.parent, scored)
    targeted = explicit_attack_success(scored)
    outcome_en = "successful attacks" if targeted else "prediction flips"
    outcome_zh = "成功攻击" if targeted else "预测翻转"

    table_rows: list[str] = []
    for group in sorted(groups, key=lambda item: (int(item["budget"]), str(item["method"]))):
        if int(group["scored"]) > 0:
            rate = f'{float(group["success_rate"]):.1%}'
            interval = f'[{float(group["success_low"]):.1%}, {float(group["success_high"]):.1%}]'
            mean_delta = f'{float(group["mean_delta"]):+.4f}'
            mean_absolute = (
                f'{float(group["mean_abs_delta"]):.4f} '
                f'[{float(group["abs_low"]):.4f}, {float(group["abs_high"]):.4f}]'
            )
            coverage = f'{float(group["coverage_rate"]):.1%}'
            nodes = f'{float(group["mean_abs_nodes"]):.2f}'
            edges = f'{float(group["mean_abs_edges"]):.2f}'
        else:
            rate = interval = mean_delta = mean_absolute = coverage = nodes = edges = "N/A"
        table_rows.append(
            "| {method} | {budget} | {scored}/{attempted} | {coverage} | {successes} | {rate} | {interval} | {delta} | {absolute} | {nodes} | {edges} |".format(
                method=markdown_cell(friendly_method(str(group["method"]))),
                budget=markdown_cell(group_setting_label(group)), scored=group["scored"], attempted=group["attempted"],
                coverage=coverage, successes=group["successes"], rate=rate, interval=interval,
                delta=mean_delta, absolute=mean_absolute, nodes=nodes, edges=edges,
            )
        )

    en_findings = "\n".join(f"- {item}" for item in bilingual_findings(chart_groups, scored, "en"))
    zh_findings = "\n".join(f"- {item}" for item in bilingual_findings(chart_groups, scored, "zh"))
    table_text = "\n".join(table_rows)
    document = f"""# Experiment Analysis / 实验分析

**Run / 实验：** {title}<br>
**Source / 数据源：** `prediction_comparison.csv`

## 中文说明

### 范围与总体结果

- 输入规模：{sample_count}（{sample_label}）。
- 尝试生成的变体：{len(rows)}；有效评分对比：{len(scored)}；不可应用或不完整：{len(rows) - len(scored)}。
- 观测到的{outcome_zh}：{successes}。
- 所有图表和结论都坚持一次只比较一个变量：多预算实验只改变预算，固定设置实验只改变扰动方法。

### 数据规律

{zh_findings}

### 解释边界

- 这些结论描述本次 run 中的关联和趋势，不代表因果关系。
- 比率使用 95% Wilson 置信区间；平均概率变化使用正态近似 95% 置信区间。
- 小样本、低覆盖率、单次随机种子、数据集偏移和模型重训练不确定性均可能影响结论。
- 应结合下方有效评分数与置信区间判断差异，而不应仅按点估计排序。

## English Notes

### Scope and overall result

- Input size: {sample_count} ({sample_label}).
- Attempted variants: {len(rows)}; scored comparisons: {len(scored)}; not applicable or incomplete: {len(rows) - len(scored)}.
- Observed {outcome_en}: {successes}.
- Every comparison changes one variable at a time: budget only for multi-budget experiments, and method only for fixed-setting experiments.

### Observed patterns

{en_findings}

### Interpretation limits

- These findings describe associations and trends within this run; they are not causal claims.
- Rates use 95% Wilson intervals; mean probability changes use normal-approximation 95% intervals.
- Small samples, low coverage, a single random seed, dataset shift, and model-retraining uncertainty can affect the conclusions.
- Compare scored counts and confidence intervals rather than ranking methods only by point estimates.

## Statistical Evidence / 统计证据

| Method / 方法 | Budget or setting / 预算或设置 | Scored/attempted / 有效/尝试 | Coverage / 覆盖率 | Events / 事件数 | Rate / 比率 | 95% Wilson CI | Mean delta / 平均概率变化 | Mean absolute delta [95% CI] / 平均绝对变化 [95% CI] | Mean \\|Δ nodes\\| / 平均节点变化 | Mean \\|Δ edges\\| / 平均边变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table_text}
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def statistical_table(groups: list[dict[str, object]], rows: list[dict[str, str]]) -> str:
    body = []
    for group in sorted(groups, key=lambda item: (int(item["budget"]), str(item["method"]))):
        if int(group["scored"]) > 0:
            outcome = f'{int(group["successes"])}/{int(group["outcome_scored"])} ({float(group["success_rate"]):.1%})'
            interval = f'[{float(group["success_low"]):.1%}, {float(group["success_high"]):.1%}]'
            coverage = f'{float(group["coverage_rate"]):.1%}'
            delta = f'{float(group["mean_delta"]):+.4f}'
            absolute = f'{float(group["mean_abs_delta"]):.4f}'
            nodes = f'{float(group["mean_abs_nodes"]):.2f}'
            edges = f'{float(group["mean_abs_edges"]):.2f}'
        else:
            outcome = interval = coverage = delta = absolute = nodes = edges = "not estimable"
        body.append(
            '<tr><td>{method}</td><td class="num">{budget}</td><td class="num">{seeds}</td><td class="num">{scored}/{attempted}</td>'
            '<td class="num">{coverage}</td><td class="num">{outcome}</td><td class="num">{interval}</td>'
            '<td class="num">{delta}</td><td class="num">{absolute}</td><td class="num">{nodes}</td><td class="num">{edges}</td></tr>'.format(
                method=html.escape(friendly_method(str(group["method"]))), budget=html.escape(group_setting_label(group)),
                seeds=group["seed_count"], scored=group["scored"], attempted=group["attempted"], coverage=coverage,
                outcome=outcome, interval=interval, delta=delta, absolute=absolute, nodes=nodes, edges=edges,
            )
        )
    return (
        '<div class="table-scroll summary-table-scroll"><table class="summary-table"><thead><tr>'
        f'<th>Method</th><th>Budget / setting</th><th>Seeds</th><th>Scored / attempted</th><th>Coverage</th><th>{html.escape(success_term(rows))}</th>'
        '<th>95% CI</th><th>Mean delta probability</th><th>Mean absolute delta</th>'
        '<th>Mean |Δ nodes|</th><th>Mean |Δ edges|</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def seed_stability_table(rows: list[dict[str, str]]) -> str:
    """Show per-seed outcomes without treating repeated seeds as new samples."""
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        method, strength = perturbation_configuration(row)
        if row.get("seed", ""):
            grouped[(method, strength or "fixed setting", row["seed"])].append(row)
    if len({seed for _, _, seed in grouped}) < 2:
        return ""

    body = []
    for (method, strength, seed), attempted in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            strength_sort_key(item[0][1]),
            int(item[0][2]),
        ),
    ):
        scored = [row for row in attempted if is_scored(row)]
        outcome_rows = (
            [row for row in scored if attack_eligible(row)]
            if explicit_attack_success(attempted)
            else scored
        )
        successes = sum(attack_succeeded(row) for row in outcome_rows)
        rate = successes / len(outcome_rows) if outcome_rows else 0.0
        deltas = [abs(number(row, "delta_prob")) for row in scored]
        body.append(
            '<tr><td>{method}</td><td class="num">{setting}</td><td class="num">{seed}</td>'
            '<td class="num">{scored}/{attempted}</td><td class="num">{successes}/{eligible} ({rate:.1%})</td>'
            '<td class="num">{delta}</td></tr>'.format(
                method=html.escape(friendly_method(method)),
                setting=html.escape(strength.replace("budget ", "")),
                seed=html.escape(seed),
                scored=len(scored),
                attempted=len(attempted),
                successes=successes,
                eligible=len(outcome_rows),
                rate=rate,
                delta=f"{statistics.fmean(deltas):.4f}" if deltas else "not estimable",
            )
        )
    return (
        '<section><h2>Seed stability evidence</h2>'
        '<p class="explain">Each row holds method and budget fixed. Differences across rows therefore show sensitivity to target-selection randomness.</p>'
        '<div class="table-scroll"><table class="summary-table"><thead><tr><th>Method</th>'
        '<th>Budget / setting</th><th>Seed</th><th>Scored / attempted</th><th>Outcome rate</th>'
        f'<th>Mean absolute delta</th></tr></thead><tbody>{"".join(body)}</tbody></table></div></section>'
    )


def available_runs() -> list[Path]:
    """Return every archived run that has a comparison table."""
    return sorted(
        candidate for candidate in Path("outputs").glob("run_*")
        if (candidate / "prediction_comparison.csv").is_file()
    )


def build_graph_comparison_rows(run_root: Path) -> list[dict[str, str]]:
    """Combine comparable random and Winner-XFG results without mixing code variants."""
    sources = (
        ("random_graph", run_root / "graph_random" / "prediction_comparison.csv"),
        ("winner_xfg", run_root / "graph_targeted" / "prediction_comparison.csv"),
    )
    if any(not path.is_file() for _, path in sources):
        return []

    combined: list[dict[str, str]] = []
    budget_sets: list[set[str]] = []
    seed_sets: list[set[str]] = []
    for family, path in sources:
        rows = read_rows(path)
        if not explicit_attack_success(rows):
            return []
        budgets = {row["budget"] for row in rows if row["budget"]}
        seeds = {row["seed"] for row in rows if row["seed"]}
        budget_sets.append(budgets)
        seed_sets.append(seeds)
        for row in rows:
            combined.append(
                {
                    **row,
                    "method_family": family,
                    "action": f"{family}::{row['action']}",
                }
            )
    if len(budget_sets[0]) < 2 or budget_sets[0] != budget_sets[1]:
        return []
    if not seed_sets[0] or seed_sets[0] != seed_sets[1]:
        return []
    return combined


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a normalized comparison table with a stable union of columns."""
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


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
    groups = comparison_groups(rows)
    chart_groups = [group for group in groups if int(group["scored"]) > 0]
    selections = sorted({selection_key(row) for row in scored})
    seeds = sorted({row["seed"] for row in scored if row["seed"]}, key=lambda value: int(value))
    budgets = sorted({int(group["budget"]) for group in chart_groups})
    has_budget_response = len(budgets) > 1
    selection_name = "configurations" if has_budget_response else "methods"
    outcome_rows = (
        [row for row in scored if attack_eligible(row)]
        if explicit_attack_success(scored)
        else scored
    )
    successes = sum(attack_succeeded(row) for row in outcome_rows)
    outcome_event_label = "successful attacks" if explicit_attack_success(scored) else "prediction flips"
    scored_sample_count, unscored = len({row["sample"] for row in scored}), len(rows) - len(scored)
    run_root = (
        output.parent.parent
        if output.parent.name in {"graph_random", "graph_targeted", "graph_comparison"}
        else output.parent
    )
    input_label, input_count = input_sample_count(run_root, scored)
    insight_items = "".join(f'<li>{html.escape(item)}</li>' for item in evidence_insights(chart_groups, scored))
    table_rows = "".join(
        "<tr data-selection=\"{selection}\" data-seed=\"{seed}\"><td>{sample}</td><td>{action}</td><td class=\"num\">{budget}</td><td class=\"num\">{seed}</td>"
        "<td class=\"num\">{base:.6f}</td><td class=\"num\">{variant:.6f}</td><td class=\"num\">{delta:+.6f}</td>"
        "<td class=\"num\">{nodes:+.0f}</td><td class=\"num\">{edges:+.0f}</td><td>{outcome}</td></tr>".format(
            selection=html.escape(selection_key(row)), action=html.escape(row["action"]), sample=html.escape(row["sample"]),
            budget=html.escape(row["budget"] or "fixed"),
            seed=html.escape(row["seed"] or "fixed"),
            base=number(row, "base_prob"), variant=number(row, "variant_prob"),
            delta=number(row, "delta_prob"), nodes=number(row, "delta_nodes"), edges=number(row, "delta_edges"),
            outcome=(
                "baseline ineligible"
                if explicit_attack_success(scored) and not attack_eligible(row)
                else ("success" if attack_succeeded(row) else "no change")
            ),
        ) for row in scored
    )
    controls = "".join(
        f'<label><input type="checkbox" value="{html.escape(selection)}" checked> {html.escape(selection)}</label>'
        for selection in selections
    )
    control_fields: list[str] = []
    if run_options:
        run_selector_options = "".join(
            f'<option value="{html.escape(destination)}"{" selected" if name == current_run else ""}>{html.escape(name)}</option>'
            for name, destination in run_options
        )
        control_fields.append(
            '<label class="selector-field" for="run-selector"><span>Experiment run</span>'
            f'<select id="run-selector">{run_selector_options}</select></label>'
        )
    if len(seeds) > 1:
        seed_options = '<option value="all">All seeds</option>' + "".join(
            f'<option value="{html.escape(seed)}">Seed {html.escape(seed)}</option>'
            for seed in seeds
        )
        control_fields.append(
            '<label class="selector-field" for="seed-selector"><span>Evidence seed</span>'
            f'<select id="seed-selector">{seed_options}</select></label>'
        )
    report_options: list[str] = []
    for label, relative in (
        ("Code perturbations", "dashboard.html"),
        ("Random graph baseline", "graph_random/dashboard.html"),
        ("Winner-XFG targeted", "graph_targeted/dashboard.html"),
        ("Random vs Winner-XFG", "graph_comparison/dashboard.html"),
    ):
        candidate = run_root / relative
        if (candidate.parent / "prediction_comparison.csv").is_file():
            destination = Path(os.path.relpath(candidate, output.parent)).as_posix()
            selected_option = " selected" if candidate.resolve() == output.resolve() else ""
            report_options.append(
                f'<option value="{html.escape(destination)}"{selected_option}>{html.escape(label)}</option>'
            )
    if report_options:
        control_fields.append(
            '<label class="selector-field" for="report-selector"><span>Result view</span>'
            f'<select id="report-selector">{"".join(report_options)}</select></label>'
        )
    try:
        all_runs_href = Path(os.path.relpath(Path("outputs/index.html"), output.parent)).as_posix()
    except ValueError:
        all_runs_href = Path("outputs/index.html").resolve().as_uri()
    dashboard_controls = (
        f'<div class="dashboard-controls">{"".join(control_fields)}'
        f'<a class="all-runs-link" href="{html.escape(all_runs_href)}">All runs</a></div>'
        if control_fields else ""
    )

    analysis_link = (
        f'<p class="analysis-link"><a href="{ANALYSIS_FILENAME}">'
        'Bilingual analysis notes / 中英文分析说明</a></p>'
    )

    if has_budget_response:
        comparison_section = (
            '<section><h2>Effectiveness under controlled budget changes</h2>'
            '<p class="explain">Horizontal panels hold budget fixed and compare methods. Vertical response panels hold the method fixed and change only perturbation budget.</p>'
            '<h3>Horizontal method comparison at each fixed budget</h3>'
            f'{horizontal_budget_comparisons(chart_groups, "success_rate", success_term(scored), percent=True)}'
            '<h3>Vertical budget response for each fixed method</h3>'
            f'<div class="chart-block"><h3>{html.escape(success_term(scored))}</h3>{svg_budget_lines(chart_groups, "success_rate", success_term(scored), percent=True)}</div>'
            f'<div class="chart-block"><h3>Effect magnitude</h3>{svg_budget_lines(chart_groups, "mean_abs_delta", "Mean absolute probability change")}</div>'
            f'<div class="chart-block"><h3>Effect direction</h3><p class="explain">Positive values raise predicted vulnerability probability; negative values lower it.</p>{svg_budget_signed_lines(chart_groups, "mean_delta", "Mean signed probability change")}</div>'
            f'<div class="chart-block"><h3>Sample-level effect distribution</h3>{svg_budget_delta_small_multiples(scored)}</div></section>'
            '<section><h2>Applicability under controlled budget changes</h2>'
            '<p class="explain">Coverage is the proportion of attempted variants that produced a complete, scoreable model comparison.</p>'
            f'{svg_budget_lines(chart_groups, "coverage_rate", "Scored coverage rate", percent=True)}</section>'
            '<section><h2>Realised structural perturbation</h2>'
            '<p class="explain">Requested budget is separated from the structure actually changed. Each response still varies budget only.</p>'
            f'<div class="chart-block"><h3>Node changes</h3>{svg_budget_lines(chart_groups, "mean_abs_nodes", "Mean absolute node change")}</div>'
            f'<div class="chart-block"><h3>Edge changes</h3>{svg_budget_lines(chart_groups, "mean_abs_edges", "Mean absolute edge change")}</div></section>'
        )
    else:
        explicit_budgets = sorted({int(row["budget"]) for row in scored if row["budget"]})
        fixed_setting = f'budget {explicit_budgets[0]}' if explicit_budgets else 'one configured application'
        comparison_section = (
            '<section><h2>Effectiveness at a controlled fixed setting</h2>'
            f'<p class="explain">Every panel holds the experiment at {fixed_setting}; only perturbation method changes. Realised structural change is reported separately.</p>'
            f'<div class="chart-block"><h3>{html.escape(success_term(scored))}</h3>{svg_fixed_comparison(chart_groups, "success_rate", success_term(scored), percent=True)}</div>'
            f'<div class="chart-block"><h3>Effect magnitude</h3>{svg_fixed_comparison(chart_groups, "mean_abs_delta", "Mean absolute probability change")}</div>'
            f'<div class="chart-block"><h3>Effect direction</h3><p class="explain">Positive values raise predicted vulnerability probability; negative values lower it.</p>{svg_fixed_signed_comparison(chart_groups, "mean_delta", "Mean signed probability change")}</div>'
            f'<div class="chart-block"><h3>Sample-level effect distribution</h3>{svg_fixed_delta_boxplots(scored)}</div></section>'
            '<section><h2>Applicability at the fixed setting</h2>'
            '<p class="explain">Coverage shows whether a method can be applied and scored across the attempted inputs.</p>'
            f'{svg_fixed_comparison(chart_groups, "coverage_rate", "Scored coverage rate", percent=True)}</section>'
            '<section><h2>Realised structural perturbation at the fixed setting</h2>'
            '<p class="explain">These panels compare how much graph structure each method actually changes while the configured application count stays fixed.</p>'
            f'<div class="chart-block"><h3>Node changes</h3>{svg_fixed_comparison(chart_groups, "mean_abs_nodes", "Mean absolute node change")}</div>'
            f'<div class="chart-block"><h3>Edge changes</h3>{svg_fixed_comparison(chart_groups, "mean_abs_edges", "Mean absolute edge change")}</div></section>'
        )

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><style>
*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6fa;color:#172033}}main{{max-width:1480px;margin:0 auto;padding:28px}}h1{{font-size:clamp(1.7rem,2.4vw,2.5rem);margin:0 0 6px}}h2{{font-size:1.35rem;margin:0 0 8px}}h3{{font-size:1.08rem;margin:28px 0 4px}}.sub,.explain{{color:#5d687c;max-width:92ch}}.dashboard-controls{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:14px;margin:18px 0 10px}}.selector-field{{display:grid;gap:6px;font-weight:600;color:#334155}}.selector-field select{{min-width:min(360px,80vw);padding:9px 34px 9px 11px;border:1px solid #b8c2d1;border-radius:7px;background:#fff;color:#172033}}.all-runs-link{{padding:9px 2px}}.summary-strip{{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}}.summary-item{{min-width:170px;padding:12px 16px;border-left:4px solid #2563eb;background:#eef4ff}}.summary-item strong{{display:block;font-size:1.7rem}}section{{background:#fff;border:1px solid #dce2ec;border-radius:10px;padding:22px;margin:18px 0}}.chart-block+ .chart-block{{border-top:1px solid #e5e7eb;margin-top:30px;padding-top:4px}}.chart-wrap{{overflow-x:auto;margin-top:16px}}.comparison-chart{{display:block;width:100%;min-width:820px;height:auto}}.comparison-chart .grid{{stroke:#dce2ec;stroke-width:1}}.comparison-chart .zero-line{{stroke:#64748b;stroke-width:2}}.axis-label,.point-label,.legend-label,.method-label{{font-size:13px;fill:#334155}}.axis-title{{font-size:14px;font-weight:600;fill:#172033}}.point-label{{font-weight:600}}.insights{{margin:12px 0 0;padding-left:22px}}.insights li{{margin:9px 0;max-width:105ch}}.method-picker{{margin:14px 0;border:1px solid #dce2ec;border-radius:8px;background:#f8fafc}}.method-picker summary{{cursor:pointer;padding:12px 14px;font-weight:600}}.picker-actions{{padding:10px 14px;border-top:1px solid #dce2ec}}#action-checks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:7px;padding:6px 14px 14px}}#action-checks label{{overflow-wrap:anywhere}}input,select{{font:inherit}}.table-scroll{{overflow:auto;max-height:620px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px 10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#eef4ff;z-index:1}}.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.summary-table{{min-width:980px}}.variant-table{{min-width:1160px}}.method-note{{font-size:13px;color:#5d687c;margin-top:10px}}@media(max-width:700px){{main{{padding:16px}}section{{padding:16px}}.summary-item{{flex:1 1 140px}}.selector-field{{width:100%}}.selector-field select{{width:100%;min-width:0}}}}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<p class="sub">Controlled comparison of DeepWuKong predictions under one changing experimental variable at a time.</p>
{dashboard_controls}{analysis_link}
<div class="summary-strip">
  <div class="summary-item"><strong>{input_count}</strong>{html.escape(input_label.lower())}</div>
  <div class="summary-item"><strong>{len(scored)}</strong>scored comparisons</div>
  <div class="summary-item"><strong>{len(seeds) or 1}</strong>random seeds</div>
  <div class="summary-item"><strong>{successes}</strong>{html.escape(outcome_event_label)}</div>
  <div class="summary-item"><strong>{unscored}</strong>not applicable / incomplete</div>
</div>
{comparison_section}
{seed_stability_table(rows)}
<section><h2>Evidence-backed observations</h2><p class="explain">These statements are generated from the same aggregates shown above. They are descriptive associations, not causal claims.</p><ul class="insights">{insight_items}</ul></section>
<section><h2>Statistical evidence</h2><p class="explain">Single-seed rates use 95% Wilson intervals. Multi-seed rate intervals are calculated across seed-level rates, so repeated variants are not presented as independent samples. Probability means use scored variant-level intervals.</p>{statistical_table(groups, scored)}</section>
<section><h2>Variant evidence</h2><p class="explain">Use this table to trace every aggregate back to individual samples. Filtering changes only the evidence table, not the fixed comparison charts above.</p>
<p id="selection-summary"></p><details class="method-picker"><summary>Choose {selection_name}</summary><div class="picker-actions"><label><input id="select-all" type="checkbox" checked> All</label></div><div id="action-checks">{controls}</div></details>
<div class="table-scroll"><table class="variant-table"><thead><tr><th>Sample</th><th>Method</th><th>Budget / setting</th><th>Seed</th><th>Baseline</th><th>Variant</th><th>Delta probability</th><th>Delta nodes</th><th>Delta edges</th><th>Outcome</th></tr></thead><tbody>{table_rows}</tbody></table></div></section>
<p class="method-note">Confidence intervals quantify uncertainty within this run; they do not account for dataset shift or model retraining uncertainty.</p>
</main><script>const boxes=[...document.querySelectorAll('#action-checks input')];const allBox=document.getElementById('select-all');const summary=document.getElementById('selection-summary');const runSelector=document.getElementById('run-selector');const reportSelector=document.getElementById('report-selector');const seedSelector=document.getElementById('seed-selector');function selected(){{return new Set(boxes.filter(box=>box.checked).map(box=>box.value));}}function filterRows(){{const chosen=selected();const chosenSeed=seedSelector?seedSelector.value:'all';allBox.checked=chosen.size===boxes.length;allBox.indeterminate=chosen.size>0&&chosen.size<boxes.length;let visible=0;document.querySelectorAll('tbody tr[data-selection]').forEach(row=>{{const show=chosen.has(row.dataset.selection)&&(chosenSeed==='all'||row.dataset.seed===chosenSeed);row.hidden=!show;if(show)visible+=1;}});summary.textContent=`Showing ${{visible}} evidence rows across ${{chosen.size}} of ${{boxes.length}} {selection_name}.`;}}allBox.addEventListener('change',()=>{{boxes.forEach(box=>box.checked=allBox.checked);filterRows();}});boxes.forEach(box=>box.addEventListener('change',filterRows));if(seedSelector)seedSelector.addEventListener('change',filterRows);if(runSelector)runSelector.addEventListener('change',()=>{{window.location.href=runSelector.value;}});if(reportSelector)reportSelector.addEventListener('change',()=>{{window.location.href=reportSelector.value;}});filterRows();</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    render_analysis_document(rows, output.parent / ANALYSIS_FILENAME, title)


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

    def options_for(report_output: Path) -> list[tuple[str, str]]:
        return [
            (
                candidate.name,
                Path(os.path.relpath(candidate / "dashboard.html", report_output.parent)).as_posix(),
            )
            for candidate in runs
        ]

    run_options = options_for(output)
    combined_rows = build_graph_comparison_rows(args.run_dir)
    if combined_rows:
        write_rows(
            args.run_dir / "graph_comparison" / "prediction_comparison.csv",
            combined_rows,
        )
    render_report(
        read_rows(comparison), output, f"DeepWuKong perturbation report: {args.run_dir.name}",
        run_options, args.run_dir.name,
    )
    if combined_rows:
        combined_dir = args.run_dir / "graph_comparison"
        combined_output = combined_dir / "dashboard.html"
        render_report(
            combined_rows,
            combined_output,
            f"Random graph vs Winner-XFG: {args.run_dir.name}",
            options_for(combined_output),
            args.run_dir.name,
        )
        print(f"Wrote {combined_output}")
        for label, child in (
            ("Random graph", args.run_dir / "graph_random"),
            ("Winner-XFG", args.run_dir / "graph_targeted"),
        ):
            child_comparison = child / "prediction_comparison.csv"
            if child_comparison.is_file():
                child_output = child / "dashboard.html"
                render_report(
                    read_rows(child_comparison),
                    child_output,
                    f"{label} perturbation report: {args.run_dir.name}",
                    options_for(child_output),
                    args.run_dir.name,
                )
    render_index(runs, Path("outputs") / "index.html")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
