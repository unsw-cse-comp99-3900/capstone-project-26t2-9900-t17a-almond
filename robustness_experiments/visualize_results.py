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
    return any(str(row.get("attack_success", "")).strip() for row in rows) or any(
        str(row.get("baseline_eligible", "")).strip()
        and str(row.get("true_label", "")).strip()
        for row in rows
    )


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
        seed_success_rates: list[float] = []
        if len(seeds) > 1:
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
        elif outcome_rows:
            seed_success_rates = [rate]
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
            "seed_rate_count": len(seed_success_rates),
            "seed_rate_std": (
                statistics.stdev(seed_success_rates) if len(seed_success_rates) > 1 else 0.0
            ),
            "seed_rate_min": min(seed_success_rates, default=rate),
            "seed_rate_max": max(seed_success_rates, default=rate),
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


CHART_TERM_DETAILS = {
    "key-series-line": (
        "The same colour connects estimates from the same perturbation method at measured budgets; the segment is a visual guide, not an unmeasured result. "
        "/ 同一种颜色连接同一扰动方法在已测Budget上的估计值；线段只帮助观察趋势，不代表中间未测试Budget也有结果。"
    ),
    "key-point": (
        "A circle is the aggregate point estimate at one exact method-budget setting, calculated from valid scored observations; it is not an individual sample or a confidence interval. "
        "/ 圆点是某个确定方法与Budget组合下、由有效评分记录汇总得到的点估计；它不是单个样本，也不是置信区间。"
    ),
    "key-bar-vertical": (
        "Bar height encodes the aggregate point estimate from the zero baseline. Bar width and area have no statistical meaning. "
        "/ 柱高从零基线开始表示汇总点估计；柱宽和柱面积没有额外统计含义。"
    ),
    "key-diverging-bar-vertical": (
        "Distance from zero shows the magnitude of the mean signed change; the side of zero shows whether predicted vulnerability probability rose or fell. "
        "/ 柱子离零线的距离表示平均带符号变化的大小；位于零线上方或下方表示漏洞预测概率上升或下降。"
    ),
    "key-zero": (
        "The zero line means no probability change relative to the baseline prediction; it is not the model's classification threshold. "
        "/ 零线表示相对基线预测概率没有变化；它不是模型将样本判为漏洞的分类阈值。"
    ),
    "key-n": (
        "n is the number of valid scoreable observations used for that estimate after filtering. It may include repeated seeds and is not automatically the number of independent source programs. "
        "/ n是过滤后真正参与该估计的有效可评分记录数；它可能包含重复Seed，不能自动当成独立源代码数量。"
    ),
    "key-box": (
        "The box spans Q1 to Q3—the 25th to 75th percentiles—so it contains the middle 50% of observed sample-level changes. It is not a confidence interval or standard deviation. "
        "/ 箱体从第25百分位数Q1延伸到第75百分位数Q3，包含中间50%的样本级变化；它不是置信区间，也不是标准差。"
    ),
    "key-median": (
        "The median is the 50th percentile: half the observed changes are no greater and half are no smaller. It is less sensitive to extreme values than the mean. "
        "/ 中位数是第50百分位数：一半观测变化不大于它，另一半不小于它；它比均值更不容易被极端值拉动。"
    ),
    "key-range": (
        "Whiskers connect the smallest and largest values actually observed in this run. They are sensitive to extremes and are not 95% confidence intervals. "
        "/ 须线连接本次run实际观测到的最小值和最大值，容易受极端样本影响，而且不是95%置信区间。"
    ),
    "key-paired-bars": (
        "The two bars at one budget are calculated from the same sample-budget-seed keys scoreable by both families, so the input cohort is controlled. "
        "/ 同一Budget下的两根柱只使用Random与Winner-XFG双方都能评分的相同sample-budget-seed键，因此输入队列保持一致。"
    ),
    "key-bar": (
        "The paired-chart bar height is successful action variants divided by all scored action variants in the shared cohort. "
        "/ 配对图柱高等于共同队列中的成功攻击变体数除以全部有效攻击变体数。"
    ),
    "key-label": (
        "The percentage printed above a bar is the observed rate from this run, rounded for display; exact counts remain available in the evidence tables. "
        "/ 柱顶百分比是本次run的观测比率，显示时经过四舍五入；精确计数仍保留在证据表中。"
    ),
}


def chart_key(*items: tuple[str, str], explanation: str | None = None) -> str:
    """Render a visible, reusable legend for statistical chart marks."""
    body = "".join(
        f'<span class="chart-key-item"><span class="chart-key-symbol {html.escape(symbol)}" '
        f'aria-hidden="true"></span><span class="chart-key-copy">'
        f'<strong class="chart-key-term">{html.escape(label)}</strong>'
        f'<span class="chart-key-detail">{html.escape(CHART_TERM_DETAILS.get(symbol, ""))}</span>'
        '</span></span>'
        for symbol, label in items
    )
    explanation_html = (
        '<p class="chart-explanation"><strong>Chart explanation / 图表讲解:</strong> '
        f'{html.escape(explanation)}</p>'
        if explanation else ""
    )
    return (
        '<div class="chart-key" role="note" aria-label="How to read this chart">'
        '<strong>Terminology / 名词解释:</strong>'
        f'<div class="chart-key-items">{body}</div>'
        f'{explanation_html}</div>'
    )


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
    maximum = max((float(group[metric]) for group in groups), default=1.0) * 1.15
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
            value_text = f"{value:.0%}" if percent else f"{value:.3f}"
            label_y = label_positions[(method, int(point["budget"]))] + 5
            marks.append(
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
        f'aria-label="{html.escape(label)} observed estimates by budget">'
        f'<title>{html.escape(label)} by budget</title><desc>Each line is one method. Budget is the only changing variable along the x axis. The chart shows observed estimates; uncertainty intervals remain in the Statistical evidence table.</desc>'
        f'{"".join(marks)}{"".join(legend)}'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 18}" text-anchor="middle">Budget</text>'
        f'<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
        + chart_key(
            ("key-series-line", "Coloured line = one fixed method across budgets"),
            ("key-point", "Circle = observed estimate"),
            explanation=(
                "Control: each coloured line keeps the perturbation method fixed; only budget changes from left to right. "
                "Use the slope to judge budget response, and compare points at the same budget to compare methods fairly. "
                "The graph shows observed values; exact 95% intervals remain in Statistical evidence."
            ),
        )
    )


def svg_fixed_comparison(
    groups: list[dict[str, object]],
    metric: str,
    label: str,
    percent: bool = False,
    maximum: float | None = None,
) -> str:
    """Compare methods at one fixed setting using vertical observed-value bars."""
    shown = sorted(groups, key=lambda group: float(group[metric]), reverse=True)
    width = max(1080, 150 + len(shown) * 125)
    height, left, right, top, bottom = 620, 90, 42, 42, 180
    plot_width, plot_height = width - left - right, height - top - bottom
    observed_maximum = max((float(group[metric]) for group in shown), default=1.0) * 1.15
    if maximum is not None:
        x_max = maximum
    elif percent:
        x_max = min(1.0, max(0.1, math.ceil(observed_maximum * 10) / 10))
    else:
        x_max = max(0.01, math.ceil(observed_maximum * 20) / 20)
    def y_for(value: float) -> float:
        return top + plot_height - max(0.0, min(value, x_max)) / x_max * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = x_max * tick / 5
        y = y_for(value)
        tick_text = f"{value:.0%}" if percent else f"{value:.3f}"
        marks.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>')
        marks.append(f'<text class="axis-label" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{tick_text}</text>')
    group_width = plot_width / max(1, len(shown))
    bar_width = min(76.0, group_width * 0.58)
    for index, group in enumerate(shown):
        x = left + (index + 0.5) * group_width
        value = float(group[metric])
        colour = SERIES_COLOURS[0]
        value_text = f"{value:.1%}" if percent else f"{value:.4f}"
        evidence_count = (
            int(group["outcome_scored"])
            if metric == "success_rate"
            else int(group["scored"])
        )
        bar_y = y_for(value)
        bar_height = max(1.0, y_for(0.0) - bar_y)
        label_y = max(top + 12, bar_y - 9)
        method_y = top + plot_height + 28
        marks.append(
            f'<rect class="estimate-bar vertical-estimate-bar" x="{x - bar_width / 2:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{colour}" fill-opacity="0.72" rx="2"/>'
            f'<text class="point-label" x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle">{value_text} (n={evidence_count})</text>'
            f'<text class="method-label rotated-method-label" x="{x:.1f}" y="{method_y:.1f}" text-anchor="end" transform="rotate(-38 {x:.1f} {method_y:.1f})">{html.escape(friendly_method(str(group["method"])))}</text>'
        )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart vertical-bar-chart" style="min-width:{width}px" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(label)} observed-value vertical bar chart by method at a fixed setting">'
        f'<title>{html.escape(label)} at a fixed setting</title><desc>Methods are compared at the same configured perturbation setting. Bar heights show observed estimates; uncertainty intervals remain in the Statistical evidence table.</desc>'
        f'{"".join(marks)}<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 8}" text-anchor="middle">Perturbation method</text>'
        '</svg></div>'
        + chart_key(
            ("key-bar-vertical", "Bar height = observed estimate"),
            ("key-n", "n = eligible scored variants used for this estimate"),
            explanation=(
                "Control: the configured perturbation setting is fixed; only the perturbation method changes between bars. "
                "A taller bar means a larger observed value under the same setting. Read n before treating small differences as meaningful, "
                "and consult Statistical evidence for the exact 95% intervals."
            ),
        )
    )


def signed_domain(groups: list[dict[str, object]], metric: str) -> tuple[float, float]:
    """Create a zero-inclusive domain for directional effects."""
    values = [float(group[metric]) for group in groups]
    minimum, maximum = min(0.0, min(values)), max(0.0, max(values))
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
            label_y = label_positions[(method, int(point["budget"]))] + 5
            marks.append(
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
        f'aria-label="{html.escape(label)} observed estimates by budget">'
        f'<title>{html.escape(label)} by budget</title><desc>Each line fixes the method and changes only budget. Values above zero increase the predicted vulnerability probability; values below zero decrease it. Uncertainty intervals remain in the Statistical evidence table.</desc>'
        f'{"".join(marks)}{"".join(legend)}'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 18}" text-anchor="middle">Budget</text>'
        f'<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        '</svg></div>'
        + chart_key(
            ("key-series-line", "Coloured line = one fixed method across budgets"),
            ("key-point", "Circle = mean signed probability change"),
            ("key-zero", "Dark reference line = no average change"),
            explanation=(
                "Control: each line fixes one perturbation method and changes only budget. Values above zero raise the model's predicted "
                "vulnerability probability on average; values below zero lower it. A line moving farther from zero shows a stronger directional budget response."
            ),
        )
    )


def svg_fixed_signed_comparison(groups: list[dict[str, object]], metric: str, label: str) -> str:
    """Compare signed method effects as vertical diverging bars around zero."""
    shown = sorted(groups, key=lambda group: float(group[metric]))
    width = max(1080, 150 + len(shown) * 125)
    height, left, right, top, bottom = 650, 90, 42, 42, 180
    plot_width, plot_height = width - left - right, height - top - bottom
    x_min, x_max = signed_domain(shown, metric)

    def y_for(value: float) -> float:
        return top + (x_max - value) / (x_max - x_min) * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = x_min + (x_max - x_min) * tick / 5
        y = y_for(value)
        marks.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + plot_width}" y2="{y:.1f}"/>')
        marks.append(f'<text class="axis-label" x="{left - 12}" y="{y + 5:.1f}" text-anchor="end">{value:+.3f}</text>')
    marks.append(
        f'<line class="zero-line" x1="{left}" y1="{y_for(0):.1f}" x2="{left + plot_width}" y2="{y_for(0):.1f}"/>'
    )
    group_width = plot_width / max(1, len(shown))
    bar_width = min(76.0, group_width * 0.58)
    for index, group in enumerate(shown):
        x = left + (index + 0.5) * group_width
        value = float(group[metric])
        colour = "#2563eb" if value < 0 else "#d97706"
        zero_y, value_y = y_for(0.0), y_for(value)
        bar_y, bar_height = min(zero_y, value_y), max(1.0, abs(value_y - zero_y))
        label_y = value_y - 10 if value >= 0 else value_y + 20
        method_y = top + plot_height + 28
        marks.append(
            f'<rect class="estimate-bar signed-estimate-bar vertical-estimate-bar" x="{x - bar_width / 2:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{colour}" fill-opacity="0.72" rx="2"/>'
            f'<text class="point-label" x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle">{value:+.4f} (n={int(group["scored"])})</text>'
            f'<text class="method-label rotated-method-label" x="{x:.1f}" y="{method_y:.1f}" text-anchor="end" transform="rotate(-38 {x:.1f} {method_y:.1f})">{html.escape(friendly_method(str(group["method"])))}</text>'
        )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart vertical-bar-chart" style="min-width:{width}px" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{html.escape(label)} vertical diverging bar chart by method at a fixed setting">'
        f'<title>{html.escape(label)} at a fixed setting</title><desc>Methods are compared at one fixed configured setting. Vertical bars encode observed mean signed change and the darker horizontal reference line is zero. Uncertainty intervals remain in the Statistical evidence table.</desc>'
        f'{"".join(marks)}<text class="axis-title" transform="translate(20 {top + plot_height / 2:.1f}) rotate(-90)" text-anchor="middle">{html.escape(label)}</text>'
        f'<text class="axis-title" x="{left + plot_width / 2:.1f}" y="{height - 8}" text-anchor="middle">Perturbation method</text>'
        '</svg></div>'
        + chart_key(
            ("key-diverging-bar-vertical", "Bar height and direction = mean signed change"),
            ("key-zero", "Dark horizontal line = no average change"),
            ("key-n", "n = scored variants used for the mean"),
            explanation=(
                "Control: all bars use the same configured perturbation setting; only method changes. Bars above zero increase predicted "
                "vulnerability probability on average, while bars below zero decrease it. Compare distance from zero for effect strength and n for evidence size."
            ),
        )
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
        + chart_key(
            ("key-box", "Box = middle 50% of sample changes (Q1 to Q3)"),
            ("key-median", "Thick line inside box = median"),
            ("key-range", "Whiskers = observed minimum to maximum"),
            ("key-zero", "Dark reference line = no probability change"),
            explanation=(
                "Control: the configured setting is fixed and only perturbation method changes between rows. The box describes typical sample-level effects, "
                "while the whiskers show the actual extremes in this run, not a confidence interval. A box crossing zero means samples did not all change in one direction."
            ),
        )
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
    columns = min(3, max(1, len(methods)))
    rows_count = math.ceil(len(methods) / columns)
    width, left, right = 1200, 82, 24
    top, bottom, column_gap, row_gap = 28, 38, 42, 52
    panel_width = (width - left - right - column_gap * (columns - 1)) / columns
    panel_plot_height, title_space, label_space = 250, 32, 62
    panel_height = title_space + panel_plot_height + label_space
    height = top + rows_count * panel_height + (rows_count - 1) * row_gap + bottom
    slot_width = panel_width / max(1, len(budgets))
    box_half_width = min(11.0, slot_width * 0.32)
    cap_half_width = min(7.0, slot_width * 0.22)

    def y_for(value: float, plot_top: float) -> float:
        return plot_top + (maximum - value) / (maximum - minimum) * panel_plot_height

    marks: list[str] = []
    for method_index, method in enumerate(methods):
        row_index, column_index = divmod(method_index, columns)
        panel_left = left + column_index * (panel_width + column_gap)
        panel_top = top + row_index * (panel_height + row_gap)
        plot_top = panel_top + title_space
        plot_bottom = plot_top + panel_plot_height
        marks.append(
            f'<text class="method-label panel-title" x="{panel_left + panel_width / 2:.1f}" y="{panel_top + 17:.1f}" text-anchor="middle">{html.escape(friendly_method(method))}</text>'
        )
        for tick in range(6):
            value = minimum + (maximum - minimum) * tick / 5
            y = y_for(value, plot_top)
            marks.append(
                f'<line class="grid" x1="{panel_left:.1f}" y1="{y:.1f}" x2="{panel_left + panel_width:.1f}" y2="{y:.1f}"/>'
            )
            if column_index == 0:
                marks.append(
                    f'<text class="axis-label" x="{panel_left - 10:.1f}" y="{y + 5:.1f}" text-anchor="end">{value:+.2f}</text>'
                )
        marks.append(
            f'<line class="zero-line" x1="{panel_left:.1f}" y1="{y_for(0, plot_top):.1f}" x2="{panel_left + panel_width:.1f}" y2="{y_for(0, plot_top):.1f}"/>'
        )
        for budget_index, budget in enumerate(budgets):
            values = grouped.get((method, budget), [])
            if not values:
                continue
            low, q1, median, q3, high = distribution_summary(values)
            x = panel_left + (budget_index + 0.5) * slot_width
            colour = SERIES_COLOURS[method_index % len(SERIES_COLOURS)]
            label_y = plot_bottom + 19
            marks.append(
                f'<line x1="{x:.1f}" y1="{y_for(low, plot_top):.1f}" x2="{x:.1f}" y2="{y_for(high, plot_top):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - cap_half_width:.1f}" y1="{y_for(low, plot_top):.1f}" x2="{x + cap_half_width:.1f}" y2="{y_for(low, plot_top):.1f}" stroke="{colour}"/>'
                f'<line x1="{x - cap_half_width:.1f}" y1="{y_for(high, plot_top):.1f}" x2="{x + cap_half_width:.1f}" y2="{y_for(high, plot_top):.1f}" stroke="{colour}"/>'
                f'<rect x="{x - box_half_width:.1f}" y="{y_for(q3, plot_top):.1f}" width="{2 * box_half_width:.1f}" height="{max(1.0, y_for(q1, plot_top) - y_for(q3, plot_top)):.1f}" fill="{colour}" fill-opacity="0.22" stroke="{colour}"/>'
                f'<line x1="{x - box_half_width:.1f}" y1="{y_for(median, plot_top):.1f}" x2="{x + box_half_width:.1f}" y2="{y_for(median, plot_top):.1f}" stroke="{colour}" stroke-width="3"/>'
                f'<text class="axis-label budget-label" x="{x:.1f}" y="{label_y:.1f}" text-anchor="end" transform="rotate(-45 {x:.1f} {label_y:.1f})">B{budget}</text>'
            )
    return (
        f'<div class="chart-wrap"><svg class="comparison-chart distribution-facets" viewBox="0 0 {width} {height}" role="img" aria-label="Sample probability change distributions by budget, faceted by method">'
        '<title>Sample-level probability change distributions by budget</title><desc>Each panel fixes one method and changes only budget. Methods are arranged in a grid so budget labels and distributions do not overlap. Every panel shares the same probability-change scale.</desc>'
        f'{"".join(marks)}<text class="axis-title" transform="translate(18 {height / 2:.1f}) rotate(-90)" text-anchor="middle">Signed probability change</text></svg></div>'
        + chart_key(
            ("key-box", "Box = middle 50% of sample changes (Q1 to Q3)"),
            ("key-median", "Thick line inside box = median"),
            ("key-range", "Whiskers = observed minimum to maximum"),
            ("key-zero", "Dark reference line = no probability change"),
            explanation=(
                "Control: each panel keeps one perturbation method fixed; only budget changes from B1 to B25 inside that panel. "
                "The box shows the typical middle half of sample-level probability changes, the thick line is the median, and whiskers are the observed minimum and maximum—not a 95% confidence interval. "
                "Values above zero raise predicted vulnerability probability and values below zero lower it. Look for the whole box moving away from zero as evidence of a systematic budget effect; longer whiskers alone mainly indicate more extreme individual samples."
            ),
        )
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
    maximum = None
    if percent:
        observed_maximum = max((float(group[metric]) for group in groups), default=1.0) * 1.15
        maximum = min(1.0, max(0.1, math.ceil(observed_maximum * 10) / 10))
    for budget in sorted({int(group["budget"]) for group in groups}):
        peers = [group for group in groups if int(group["budget"]) == budget]
        panels.append(
            f'<div class="chart-block"><h3>Budget {budget}</h3>'
            f'{svg_fixed_comparison(peers, metric, f"{label} at budget {budget}", percent=percent, maximum=maximum)}</div>'
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


def bilingual_chart_guide_markdown() -> str:
    """Return the shared bilingual chart-reading reference for every run."""
    return """## Chart Reading Guide / 图表理解对照表

| 中文术语 | English term | 中文理解 | English interpretation |
|---|---|---|---|
| 点估计 | Point estimate | 根据本次有效数据算出的单个比率或均值。它是当前最佳估计，但不是没有误差的真实值。 | The single rate or mean calculated from scored data. It is the best estimate from this run, not an error-free population truth. |
| 竖向柱状图 | Vertical bar chart | 每根柱代表一种方法，柱高表示观测比率或均值。只有在Budget、样本和模型等条件相同时才适合直接比较。 | Each bar represents one method and its height is the observed rate or mean. Heights are directly comparable only when budget, samples, model, and other controlled conditions are the same. |
| 95%置信区间 | 95% confidence interval | 如果反复进行许多次可比实验并每次按同样方式构造区间，大约95%的区间会覆盖总体真实比率或均值。它不是“95%的样本位于区间中”，也不是“真实值有95%概率在当前区间内”。 | If many comparable experiments were repeated and intervals were constructed the same way, about 95% of those intervals would contain the underlying population rate or mean. It is not the range containing 95% of samples, nor a statement that the fixed true value has a 95% probability of lying in this particular interval. |
| 误差线/端帽线 | Error bar / capped interval | 为提高可读性，当前Dashboard不再把95%置信区间画成柱子或圆点旁的误差线；精确上下界仍保留在“Statistical evidence”统计证据表中。 | For readability, the current dashboard does not draw 95% confidence intervals as error bars beside bars or points; the exact bounds remain in the Statistical evidence table. |
| 有效样本数n | Effective count (n) | `n`是计算点估计时真正使用的有效评分次数。n小通常使区间更宽；多Seed重复不能自动当成更多独立源代码。 | `n` is the number of scoreable observations used for the estimate. Small n usually produces wider intervals; repeated seeds must not automatically be treated as additional independent source programs. |
| 攻击成功率 | Attack Success Rate (ASR) | 在基线预测正确且攻击合格的结果中，扰动实现攻击目标的比例。 | Among baseline-correct, attack-eligible results, the proportion for which the perturbation achieved the attack objective. |
| 预测翻转率 | Prediction Flip Rate | 扰动前后最终分类标签发生变化的比例。翻转可能朝任意方向，因此不一定全部等于攻击成功。 | The proportion whose final class label changed after perturbation. A flip may occur in either direction and is not always equivalent to a successful attack. |
| 效应幅度 | Effect magnitude | 概率变化的绝对值，回答“模型被推动了多远”，不考虑方向，也不要求最终标签翻转。 | The absolute probability change. It answers how far the model moved, regardless of direction or whether the final label flipped. |
| 效应方向 | Effect direction | 带符号的平均概率变化。负值表示模型预测漏洞的概率下降，正值表示上升。 | The signed mean probability change. Negative values lower predicted vulnerability probability; positive values raise it. |
| 零参考线 | Zero reference line | 表示平均没有变化。柱或点位于零线上方或下方，分别代表正向或负向变化。 | Represents no average change. Marks above or below it indicate positive or negative movement. |
| Budget响应折线 | Budget-response line | 固定同一种方法，只改变Budget。连接线用于观察趋势，不表示两个Budget之间所有中间值都被测量。 | Holds the method fixed and changes only budget. The connecting line shows the observed trend and does not imply that every intermediate budget was measured. |
| 箱体Q1–Q3 | Box, Q1 to Q3 | 箱体覆盖中间50%的样本变化，从第25百分位数到第75百分位数。箱体越大，说明样本反应差异越大。 | The box covers the middle 50% of sample changes, from the 25th to the 75th percentile. A larger box indicates greater variation across samples. |
| 中位数 | Median | 箱体内部的粗线；一半样本小于它，另一半大于它，比均值更不容易被极端值拉动。 | The thick line inside the box. Half the observations are below it and half above it; it is less sensitive to extreme values than the mean. |
| 须线 | Whiskers | 当前Dashboard中的须线连接实际观测到的最小值和最大值，不是95%置信区间。 | In this dashboard the whiskers span the observed minimum and maximum; they are not 95% confidence intervals. |
| 覆盖率 | Coverage / applicability | 成功产生完整、可评分结果的尝试比例。高ASR但覆盖率很低的方法可能只对少量特殊样本有效。 | The proportion of attempts producing a complete, scoreable comparison. A method with high ASR but low coverage may work only on a small special subset. |
| 配对共同队列 | Paired common cohort | 只比较Random与Winner-XFG双方都能评分的相同样本、Budget和Seed，减少输入组成不同造成的不公平。 | Compares only sample, budget, and seed keys scoreable by both Random and Winner-XFG, reducing unfairness caused by different input composition. |
"""


def bilingual_chart_conclusions_markdown(
    groups: list[dict[str, object]], rows: list[dict[str, str]]
) -> str:
    """Generate chart-by-chart, data-dependent conclusions in paired Chinese and English."""
    if not groups:
        return ""
    budgets = sorted({int(group["budget"]) for group in groups})
    multi_budget = len(budgets) > 1
    outcome_zh = "攻击成功率" if explicit_attack_success(rows) else "预测翻转率"
    outcome_en = "attack success rate" if explicit_attack_success(rows) else "prediction flip rate"
    conclusions: list[tuple[str, str, str]] = []

    def condition_name(group: dict[str, object], language: str) -> str:
        method = friendly_method(str(group["method"]))
        if not multi_budget:
            return method
        return (
            f'{method}（Budget {int(group["budget"])}）'
            if language == "zh"
            else f'{method} at budget {int(group["budget"])}'
        )

    top_rate = max(groups, key=lambda group: float(group["success_rate"]))
    rate_scope_zh = "在所有已观测的方法–Budget组合中" if multi_budget else "在固定设置的方法比较中"
    rate_scope_en = "Across all observed method–budget combinations" if multi_budget else "In the fixed-setting method comparison"
    conclusions.append(
        (
            "有效性 / Effectiveness",
            f'{rate_scope_zh}，{condition_name(top_rate, "zh")} 的观测{outcome_zh}最高，为'
            f'{float(top_rate["success_rate"]):.1%}（{int(top_rate["successes"])}/{int(top_rate["outcome_scored"])}）。'
            "这是本次run的描述性最高值；跨Budget的最高值不能被解释为只由方法差异造成，也不等于已证明总体显著更优。",
            f'{rate_scope_en}, {condition_name(top_rate, "en")} has the highest observed '
            f'{outcome_en}: {float(top_rate["success_rate"]):.1%} ({int(top_rate["successes"])}/{int(top_rate["outcome_scored"])}). '
            "This is the descriptive maximum in this run; a maximum across budgets cannot be attributed to method alone and does not prove population-level superiority.",
        )
    )

    if multi_budget:
        endpoint_changes: list[tuple[float, str, dict[str, object], dict[str, object]]] = []
        for method in sorted({str(group["method"]) for group in groups}):
            series = sorted(
                (group for group in groups if str(group["method"]) == method),
                key=lambda group: int(group["budget"]),
            )
            if len(series) >= 2:
                change = float(series[-1]["success_rate"]) - float(series[0]["success_rate"])
                endpoint_changes.append((abs(change), method, series[0], series[-1]))
        if endpoint_changes:
            _, method, first, last = max(endpoint_changes, key=lambda item: item[0])
            change = float(last["success_rate"]) - float(first["success_rate"])
            direction_zh = "上升" if change > 0 else "下降" if change < 0 else "不变"
            direction_en = "increase" if change > 0 else "decrease" if change < 0 else "no change"
            conclusions.append(
                (
                    "Budget响应 / Budget response",
                    f'{friendly_method(method)} 从Budget {int(first["budget"])}到{int(last["budget"])}的端点变化幅度最大：'
                    f'{float(first["success_rate"]):.1%} → {float(last["success_rate"]):.1%}，即{direction_zh}{abs(change):.1%}。'
                    "端点差异概括总体变化，但不能替代对中间Budget是否单调的逐点检查。",
                    f'{friendly_method(method)} has the largest endpoint change from budget {int(first["budget"])} to {int(last["budget"])}: '
                    f'{float(first["success_rate"]):.1%} → {float(last["success_rate"]):.1%}, an absolute {direction_en} of {abs(change):.1%}. '
                    "The endpoint contrast summarizes the overall shift but does not replace checking whether intermediate budgets are monotonic.",
                )
            )

    largest_magnitude = max(groups, key=lambda group: float(group["mean_abs_delta"]))
    conclusions.append(
        (
            "效应幅度 / Effect magnitude",
            f'{condition_name(largest_magnitude, "zh")} 的平均绝对概率变化最大，为'
            f'{float(largest_magnitude["mean_abs_delta"]):.4f}。这表示模型分数平均被推动得最远，但不说明推动方向，也不保证最终分类翻转。',
            f'{condition_name(largest_magnitude, "en")} has the largest mean absolute probability change, '
            f'{float(largest_magnitude["mean_abs_delta"]):.4f}. This means it moves model scores farthest on average, but says neither the direction nor that the final class flips.',
        )
    )

    upward = max(groups, key=lambda group: float(group["mean_delta"]))
    downward = min(groups, key=lambda group: float(group["mean_delta"]))
    conclusions.append(
        (
            "效应方向 / Effect direction",
            f'{condition_name(upward, "zh")} 的平均向上变化最大（{float(upward["mean_delta"]):+.4f}）；'
            f'{condition_name(downward, "zh")} 的平均向下变化最大（{float(downward["mean_delta"]):+.4f}）。'
            "方向表示漏洞预测概率相对基线升降，不直接等同于攻击是否成功。",
            f'{condition_name(upward, "en")} has the largest upward mean shift ({float(upward["mean_delta"]):+.4f}); '
            f'{condition_name(downward, "en")} has the largest downward mean shift ({float(downward["mean_delta"]):+.4f}). '
            "Direction describes movement in predicted vulnerability probability relative to baseline and is not itself attack success.",
        )
    )

    distributions: list[dict[str, object]] = []
    grouped_deltas: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        if is_scored(row):
            method, strength = perturbation_configuration(row)
            budget_match = re.search(r"(\d+)$", row.get("budget", "") or strength or "1")
            budget = int(budget_match.group(1)) if budget_match else 1
            grouped_deltas[(method, budget)].append(number(row, "delta_prob"))
    for (method, budget), values in grouped_deltas.items():
        low, q1, median, q3, high = distribution_summary(values)
        distributions.append(
            {
                "method": method,
                "budget": budget,
                "median": median,
                "iqr": q3 - q1,
                "low": low,
                "high": high,
            }
        )
    if distributions:
        strongest_median = max(distributions, key=lambda item: abs(float(item["median"])))
        widest_iqr = max(distributions, key=lambda item: float(item["iqr"]))

        def distribution_name(item: dict[str, object], language: str) -> str:
            method = friendly_method(str(item["method"]))
            if not multi_budget:
                return method
            return (
                f'{method}（Budget {int(item["budget"])}）'
                if language == "zh"
                else f'{method} at budget {int(item["budget"])}'
            )

        median_value = float(strongest_median["median"])
        if abs(median_value) < 0.00005:
            median_zh = "所有方法–Budget箱体的中位数在四位小数精度下都接近零，未显示典型样本稳定地向某一方向移动"
            median_en = "All method–budget boxplot medians are near zero at four-decimal precision, so the typical sample does not show a stable directional shift"
        else:
            median_zh = (
                f'{distribution_name(strongest_median, "zh")} 的中位数离零最远'
                f'（{median_value:+.4f}）'
            )
            median_en = (
                f'{distribution_name(strongest_median, "en")} has the median farthest from zero '
                f'({median_value:+.4f})'
            )
        conclusions.append(
            (
                "样本级分布 / Sample-level distribution",
                f'{median_zh}；'
                f'{distribution_name(widest_iqr, "zh")} 的箱体IQR最宽（{float(widest_iqr["iqr"]):.4f}）。'
                "中位数描述典型样本的方向和幅度，IQR表示中间50%样本的反应一致性；须线极值不能单独证明稳定攻击效果。",
                f'{median_en}; '
                f'{distribution_name(widest_iqr, "en")} has the widest box IQR ({float(widest_iqr["iqr"]):.4f}). '
                "The median describes the direction and magnitude of a typical sample, while IQR describes consistency in the middle 50%. Whisker extremes alone do not establish a stable attack effect.",
            )
        )

    lowest_coverage = min(groups, key=lambda group: float(group["coverage_rate"]))
    conclusions.append(
        (
            "适用性 / Applicability",
            f'{condition_name(lowest_coverage, "zh")} 的覆盖率最低，为{float(lowest_coverage["coverage_rate"]):.1%}'
            f'（{int(lowest_coverage["scored"])}/{int(lowest_coverage["attempted"])}）。覆盖率低意味着效果估计只来自较小的可成功运行子集。',
            f'{condition_name(lowest_coverage, "en")} has the lowest coverage, {float(lowest_coverage["coverage_rate"]):.1%} '
            f'({int(lowest_coverage["scored"])}/{int(lowest_coverage["attempted"])}). Low coverage means the effect estimate comes from a smaller successfully executed subset.',
        )
    )

    largest_nodes = max(groups, key=lambda group: float(group["mean_abs_nodes"]))
    largest_edges = max(groups, key=lambda group: float(group["mean_abs_edges"]))
    conclusions.append(
        (
            "结构变化 / Realised structural change",
            f'{condition_name(largest_nodes, "zh")} 的平均绝对节点变化最大（{float(largest_nodes["mean_abs_nodes"]):.2f}）；'
            f'{condition_name(largest_edges, "zh")} 的平均绝对边变化最大（{float(largest_edges["mean_abs_edges"]):.2f}）。'
            "它们说明扰动实际改了多少结构，不等于模型受影响程度。",
            f'{condition_name(largest_nodes, "en")} has the largest mean absolute node change ({float(largest_nodes["mean_abs_nodes"]):.2f}); '
            f'{condition_name(largest_edges, "en")} has the largest mean absolute edge change ({float(largest_edges["mean_abs_edges"]):.2f}). '
            "These values quantify realised structural change, not how strongly the model was affected.",
        )
    )

    paired = paired_common_summaries(rows)
    if paired:
        paired_lookup = {
            (str(summary["family"]), int(summary["budget"])): summary
            for summary in paired
        }
        paired_differences = []
        for budget in sorted({int(summary["budget"]) for summary in paired}):
            random_summary = paired_lookup.get(("random_graph", budget))
            winner_summary = paired_lookup.get(("winner_xfg", budget))
            if random_summary and winner_summary:
                difference = float(winner_summary["variant_attack_success_rate"]) - float(random_summary["variant_attack_success_rate"])
                paired_differences.append((abs(difference), difference, budget, random_summary, winner_summary))
        if paired_differences:
            _, difference, budget, random_summary, winner_summary = max(paired_differences, key=lambda item: item[0])
            higher_zh = "Winner-XFG" if difference > 0 else "Random" if difference < 0 else "两者相同"
            higher_en = "Winner-XFG" if difference > 0 else "Random" if difference < 0 else "neither family"
            conclusions.append(
                (
                    "Random与Winner-XFG配对比较 / Paired family comparison",
                    f'在共同可评分队列中，两类方法差距最大的Budget是{budget}：Random为'
                    f'{float(random_summary["variant_attack_success_rate"]):.1%}，Winner-XFG为'
                    f'{float(winner_summary["variant_attack_success_rate"]):.1%}，{higher_zh}高出{abs(difference):.1%}。'
                    "该比较控制了sample、Budget和Seed，但仍是变体级描述性差异。",
                    f'Within the shared scoreable cohort, the largest family gap occurs at budget {budget}: Random is '
                    f'{float(random_summary["variant_attack_success_rate"]):.1%} and Winner-XFG is '
                    f'{float(winner_summary["variant_attack_success_rate"]):.1%}; {higher_en} is higher by {abs(difference):.1%}. '
                    "This controls sample, budget, and seed, but remains a descriptive variant-level contrast.",
                )
            )

    rows_markdown = "\n".join(
        f'| {markdown_cell(chart)} | {markdown_cell(zh)} | {markdown_cell(en)} |'
        for chart, zh, en in conclusions
    )
    return f"""## Chart-by-chart Conclusions / 各图表推论

以下推论由当前run的数据自动生成，并与Dashboard中的控制变量图一一对应；它们保留描述性边界，不替代显著性检验。
The conclusions below are generated from this run and correspond to the controlled-variable charts in the dashboard; they remain descriptive and do not replace significance tests.

| 图表 / Chart | 中文推论 | English inference |
|---|---|---|
{rows_markdown}
"""


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
    chart_guide = bilingual_chart_guide_markdown()
    chart_conclusions = bilingual_chart_conclusions_markdown(chart_groups, scored)
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

{chart_conclusions}

{chart_guide}

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
            '<tr><td>{method}</td><td class="num">{budget}</td><td class="num">{seeds}</td><td class="num">{seed_spread}</td><td class="num">{scored}/{attempted}</td>'
            '<td class="num">{coverage}</td><td class="num">{outcome}</td><td class="num">{interval}</td>'
            '<td class="num">{delta}</td><td class="num">{absolute}</td><td class="num">{nodes}</td><td class="num">{edges}</td></tr>'.format(
                method=html.escape(friendly_method(str(group["method"]))), budget=html.escape(group_setting_label(group)),
                seeds=group["seed_count"],
                seed_spread=(
                    f'{float(group["success_rate"]):.1%} ± {float(group["seed_rate_std"]):.1%} '
                    f'[{float(group["seed_rate_min"]):.1%}, {float(group["seed_rate_max"]):.1%}]'
                    if int(group["seed_rate_count"]) > 1
                    else "single seed"
                ),
                scored=group["scored"], attempted=group["attempted"], coverage=coverage,
                outcome=outcome, interval=interval, delta=delta, absolute=absolute, nodes=nodes, edges=edges,
            )
        )
    return (
        '<div class="table-scroll summary-table-scroll"><table class="summary-table"><thead><tr>'
        f'<th>Method</th><th>Budget / setting</th><th>Seeds</th><th>Seed rate mean ± SD [range]</th><th>Scored / attempted</th><th>Coverage</th><th>{html.escape(success_term(rows))}</th>'
        '<th>95% CI</th><th>Mean delta probability</th><th>Mean absolute delta</th>'
        '<th>Mean |Δ nodes|</th><th>Mean |Δ edges|</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def sample_level_summaries(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Aggregate repeated seeds back to independent source samples."""
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        method, strength = perturbation_configuration(row)
        grouped[(method, strength or "fixed setting")].append(row)

    summaries: list[dict[str, object]] = []
    for (method, strength), attempted_rows in sorted(
        grouped.items(), key=lambda item: (item[0][0], strength_sort_key(item[0][1]))
    ):
        targeted = explicit_attack_success(attempted_rows)
        eligible_attempted = (
            [row for row in attempted_rows if attack_eligible(row)]
            if targeted
            else attempted_rows
        )
        scored = [row for row in eligible_attempted if is_scored(row)]
        by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in scored:
            by_sample[row["sample"]].append(row)
        successful_samples = sum(
            any(attack_succeeded(row) for row in sample_rows)
            for sample_rows in by_sample.values()
        )
        all_seed_success_samples = sum(
            all(attack_succeeded(row) for row in sample_rows)
            for sample_rows in by_sample.values()
        )
        per_sample_rates = [
            sum(attack_succeeded(row) for row in sample_rows) / len(sample_rows)
            for sample_rows in by_sample.values()
        ]
        budget_match = re.search(r"(\d+)$", strength)
        summaries.append(
            {
                "method": method,
                "budget": int(budget_match.group(1)) if budget_match else 1,
                "setting": strength,
                "eligible_samples": len({row["sample"] for row in eligible_attempted}),
                "scored_samples": len(by_sample),
                "any_seed_success_samples": successful_samples,
                "any_seed_success_rate": (
                    successful_samples / len(by_sample) if by_sample else 0.0
                ),
                "all_scored_seeds_success_samples": all_seed_success_samples,
                "mean_per_sample_seed_success_rate": (
                    statistics.fmean(per_sample_rates) if per_sample_rates else 0.0
                ),
                "mean_scored_variants_per_sample": (
                    statistics.fmean(len(sample_rows) for sample_rows in by_sample.values())
                    if by_sample
                    else 0.0
                ),
            }
        )
    return summaries


def seed_level_summaries(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Retain one descriptive row per method, budget, and random seed."""
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        method, strength = perturbation_configuration(row)
        if row.get("seed", ""):
            grouped[(method, strength or "fixed setting", row["seed"])].append(row)

    summaries: list[dict[str, object]] = []
    for (method, strength, seed), attempted_rows in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], strength_sort_key(item[0][1]), int(item[0][2])),
    ):
        scored = [row for row in attempted_rows if is_scored(row)]
        outcome_rows = (
            [row for row in scored if attack_eligible(row)]
            if explicit_attack_success(attempted_rows)
            else scored
        )
        successes = sum(attack_succeeded(row) for row in outcome_rows)
        budget_match = re.search(r"(\d+)$", strength)
        summaries.append(
            {
                "method": method,
                "budget": int(budget_match.group(1)) if budget_match else 1,
                "seed": int(seed),
                "attempted": len(attempted_rows),
                "scored": len(scored),
                "eligible_scored": len(outcome_rows),
                "successes": successes,
                "success_rate": successes / len(outcome_rows) if outcome_rows else 0.0,
                "coverage_rate": len(scored) / len(attempted_rows) if attempted_rows else 0.0,
                "mean_absolute_delta": (
                    statistics.fmean(abs(number(row, "delta_prob")) for row in scored)
                    if scored
                    else None
                ),
            }
        )
    return summaries


def paired_common_summaries(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Compare graph families only on shared scoreable sample/budget/seed keys."""
    families = {"random_graph", "winner_xfg"}
    eligible_scored: dict[str, list[dict[str, str]]] = {family: [] for family in families}
    for row in rows:
        family = row.get("method_family", "")
        if family in families and is_scored(row) and attack_eligible(row):
            eligible_scored[family].append(row)
    key_sets = {
        family: {
            (row["sample"], row["budget"], row["seed"])
            for row in family_rows
        }
        for family, family_rows in eligible_scored.items()
    }
    common_keys = key_sets["random_graph"].intersection(key_sets["winner_xfg"])
    if not common_keys:
        return []

    summaries: list[dict[str, object]] = []
    budgets = sorted({int(key[1]) for key in common_keys})
    for budget in budgets:
        budget_keys = {key for key in common_keys if int(key[1]) == budget}
        for family in ("random_graph", "winner_xfg"):
            family_rows = [
                row
                for row in eligible_scored[family]
                if (row["sample"], row["budget"], row["seed"]) in budget_keys
            ]
            by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
            for row in family_rows:
                by_key[(row["sample"], row["budget"], row["seed"])].append(row)
            successes = sum(attack_succeeded(row) for row in family_rows)
            any_action_successes = sum(
                any(attack_succeeded(row) for row in key_rows)
                for key_rows in by_key.values()
            )
            summaries.append(
                {
                    "family": family,
                    "budget": budget,
                    "common_sample_seed_keys": len(budget_keys),
                    "common_samples": len({key[0] for key in budget_keys}),
                    "scored_action_variants": len(family_rows),
                    "attack_successes": successes,
                    "variant_attack_success_rate": (
                        successes / len(family_rows) if family_rows else 0.0
                    ),
                    "any_action_success_keys": any_action_successes,
                    "any_action_success_rate": (
                        any_action_successes / len(by_key) if by_key else 0.0
                    ),
                }
            )
    return summaries


def svg_paired_family_budget_bars(summaries: list[dict[str, object]]) -> str:
    """Compare Random and Winner-XFG overall ASR at each shared budget."""
    families = ("random_graph", "winner_xfg")
    family_labels = {
        "random_graph": "Random overall",
        "winner_xfg": "Winner-XFG overall",
    }
    family_colours = {
        "random_graph": "#2563eb",
        "winner_xfg": "#d97706",
    }
    lookup = {
        (str(summary["family"]), int(summary["budget"])): summary
        for summary in summaries
    }
    budgets = sorted(
        {
            int(summary["budget"])
            for summary in summaries
            if all((family, int(summary["budget"])) in lookup for family in families)
        }
    )
    if not budgets:
        return ""

    width, height = 1080, 500
    left, right, top, bottom = 90, 44, 54, 92
    plot_width, plot_height = width - left - right, height - top - bottom
    maximum = max(
        float(lookup[(family, budget)]["variant_attack_success_rate"])
        for budget in budgets
        for family in families
    )
    y_max = min(1.0, max(0.1, math.ceil(maximum * 10) / 10))

    def y_for(value: float) -> float:
        return top + plot_height - value / y_max * plot_height

    marks: list[str] = []
    for tick in range(6):
        value = y_max * tick / 5
        y = y_for(value)
        marks.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" '
            f'x2="{left + plot_width}" y2="{y:.1f}"/>'
        )
        marks.append(
            f'<text class="axis-label" x="{left - 12}" y="{y + 5:.1f}" '
            f'text-anchor="end">{value:.0%}</text>'
        )

    group_width = plot_width / len(budgets)
    bar_width = min(112.0, group_width * 0.28)
    gap = min(24.0, group_width * 0.06)
    for budget_index, budget in enumerate(budgets):
        centre = left + (budget_index + 0.5) * group_width
        total_width = bar_width * len(families) + gap
        start = centre - total_width / 2
        for family_index, family in enumerate(families):
            summary = lookup[(family, budget)]
            value = float(summary["variant_attack_success_rate"])
            successes = int(summary["attack_successes"])
            variants = int(summary["scored_action_variants"])
            x = start + family_index * (bar_width + gap)
            y = y_for(value)
            bar_height = top + plot_height - y
            label_y = max(top - 8, y - 9)
            marks.append(
                f'<rect class="paired-family-bar" data-family="{family}" '
                f'data-budget="{budget}" x="{x:.1f}" y="{y:.1f}" '
                f'width="{bar_width:.1f}" height="{bar_height:.1f}" '
                f'fill="{family_colours[family]}" rx="3">'
                f'<title>{family_labels[family]}, budget {budget}: '
                f'{value:.1%} ({successes}/{variants})</title></rect>'
            )
            marks.append(
                f'<text class="point-label" x="{x + bar_width / 2:.1f}" '
                f'y="{label_y:.1f}" text-anchor="middle">{value:.1%}</text>'
            )
        marks.append(
            f'<text class="axis-label" x="{centre:.1f}" '
            f'y="{top + plot_height + 32}" text-anchor="middle">B{budget}</text>'
        )

    legend_x = left + plot_width / 2 - 190
    for index, family in enumerate(families):
        x = legend_x + index * 245
        marks.append(
            f'<rect x="{x:.1f}" y="{height - 38}" width="18" height="18" '
            f'fill="{family_colours[family]}" rx="2"/>'
            f'<text class="legend-label" x="{x + 27:.1f}" y="{height - 24}">'
            f'{family_labels[family]}</text>'
        )

    return (
        '<div class="chart-wrap"><svg class="comparison-chart" '
        'viewBox="0 0 1080 500" role="img" '
        'aria-label="Random overall versus Winner-XFG overall attack success rate by budget">'
        '<title>Random overall vs Winner-XFG overall by budget</title>'
        '<desc>Each budget contains two bars calculated on sample, budget, and seed keys '
        'scoreable by both graph families. Bar height is variant attack success rate.</desc>'
        f'{"".join(marks)}'
        f'<text class="axis-title" transform="translate(22 {top + plot_height / 2:.1f}) '
        'rotate(-90)" text-anchor="middle">Variant attack success rate</text>'
        '</svg></div>'
        + chart_key(
            ("key-paired-bars", "Paired bars = Random and Winner-XFG on the same cohort"),
            ("key-bar", "Bar height = variant attack success rate"),
            ("key-label", "Label above bar = observed percentage"),
            explanation=(
                "Control: both bars at one budget use the same scoreable sample-budget-seed cohort; only graph perturbation family changes. "
                "Compare the paired bar heights within a budget, then compare pairs across budgets. This separates family differences from changes in sample availability."
            ),
        )
    )


def sample_level_table(rows: list[dict[str, str]]) -> str:
    summaries = sample_level_summaries(rows)
    if not summaries or not any(row.get("seed", "") for row in rows):
        return ""
    body = "".join(
        '<tr><td>{method}</td><td class="num">{budget}</td><td class="num">{scored}/{eligible}</td>'
        '<td class="num">{successes}/{scored} ({rate:.1%})</td><td class="num">{mean_rate:.1%}</td>'
        '<td class="num">{variants:.1f}</td></tr>'.format(
            method=html.escape(friendly_method(str(summary["method"]))),
            budget=summary["budget"],
            scored=summary["scored_samples"],
            eligible=summary["eligible_samples"],
            successes=summary["any_seed_success_samples"],
            rate=float(summary["any_seed_success_rate"]),
            mean_rate=float(summary["mean_per_sample_seed_success_rate"]),
            variants=float(summary["mean_scored_variants_per_sample"]),
        )
        for summary in summaries
    )
    return (
        '<section><h2>Independent-sample outcomes</h2>'
        '<p class="explain">Each source sample is counted once. “Any-seed success” asks whether at least one scored seed changed the outcome; the mean rate retains how consistently seeds succeeded within each sample.</p>'
        '<div class="table-scroll"><table class="summary-table"><thead><tr><th>Method</th>'
        '<th>Budget</th><th>Scored / eligible samples</th><th>Any-seed successful samples</th>'
        '<th>Mean within-sample seed success</th><th>Mean scored variants per sample</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div></section>'
    )


def paired_common_table(rows: list[dict[str, str]]) -> str:
    summaries = paired_common_summaries(rows)
    if not summaries:
        return ""
    family_chart = svg_paired_family_budget_bars(summaries)
    body = "".join(
        '<tr><td>{family}</td><td class="num">{budget}</td><td class="num">{samples}</td>'
        '<td class="num">{keys}</td><td class="num">{successes}/{variants} ({variant_rate:.1%})</td>'
        '<td class="num">{any_success}/{keys} ({any_rate:.1%})</td></tr>'.format(
            family=html.escape(
                "Random graph" if summary["family"] == "random_graph" else "Winner-XFG"
            ),
            budget=summary["budget"],
            samples=summary["common_samples"],
            keys=summary["common_sample_seed_keys"],
            successes=summary["attack_successes"],
            variants=summary["scored_action_variants"],
            variant_rate=float(summary["variant_attack_success_rate"]),
            any_success=summary["any_action_success_keys"],
            any_rate=float(summary["any_action_success_rate"]),
        )
        for summary in summaries
    )
    return (
        '<section><h2>Paired common-cohort comparison</h2>'
        '<p class="explain">Only sample, budget, and seed keys scoreable in both graph families are included. Variant ASR averages over each family’s actions; “any action” is also shown but is descriptive because the families contain different numbers of actions.</p>'
        '<div class="chart-block"><h3>Random overall vs Winner-XFG overall by budget</h3>'
        f'{family_chart}</div>'
        '<div class="table-scroll"><table class="summary-table"><thead><tr><th>Graph family</th>'
        '<th>Budget</th><th>Common samples</th><th>Common sample-seed keys</th>'
        '<th>Variant ASR</th><th>Any-action success per paired key</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div></section>'
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


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
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
            '<p class="explain">Fixed-budget vertical bar panels hold budget fixed and compare methods. Budget-response line panels hold the method fixed and change only perturbation budget. Charts show observed estimates without confidence-interval error bars for readability; exact 95% intervals remain in Statistical evidence and the bilingual companion notes.</p>'
            '<h3>Method comparison at each fixed budget</h3>'
            f'{horizontal_budget_comparisons(chart_groups, "success_rate", success_term(scored), percent=True)}'
            '<h3>Budget response for each fixed method</h3>'
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
            f'<p class="explain">Every panel holds the experiment at {fixed_setting}; only perturbation method changes. Realised structural change is reported separately. Charts show observed estimates without confidence-interval error bars for readability; exact 95% intervals remain in Statistical evidence and the bilingual companion notes.</p>'
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
*{{box-sizing:border-box}}body{{font-family:Inter,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6fa;color:#172033}}main{{max-width:1480px;margin:0 auto;padding:28px}}h1{{font-size:clamp(1.7rem,2.4vw,2.5rem);margin:0 0 6px}}h2{{font-size:1.35rem;margin:0 0 8px}}h3{{font-size:1.08rem;margin:28px 0 4px}}.sub,.explain{{color:#5d687c;max-width:92ch}}.dashboard-controls{{display:flex;flex-wrap:wrap;align-items:flex-end;gap:14px;margin:18px 0 10px}}.selector-field{{display:grid;gap:6px;font-weight:600;color:#334155}}.selector-field select{{min-width:min(360px,80vw);padding:9px 34px 9px 11px;border:1px solid #b8c2d1;border-radius:7px;background:#fff;color:#172033}}.all-runs-link{{padding:9px 2px}}.summary-strip{{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}}.summary-item{{min-width:170px;padding:12px 16px;border-left:4px solid #2563eb;background:#eef4ff}}.summary-item strong{{display:block;font-size:1.7rem}}section{{background:#fff;border:1px solid #dce2ec;border-radius:10px;padding:22px;margin:18px 0}}.chart-block+ .chart-block{{border-top:1px solid #e5e7eb;margin-top:30px;padding-top:4px}}.chart-wrap{{overflow-x:auto;margin-top:16px}}.comparison-chart{{display:block;width:100%;min-width:820px;height:auto}}.comparison-chart .grid{{stroke:#dce2ec;stroke-width:1}}.comparison-chart .zero-line{{stroke:#64748b;stroke-width:2}}.axis-label,.point-label,.legend-label,.method-label{{font-size:13px;fill:#334155}}.axis-title{{font-size:14px;font-weight:600;fill:#172033}}.point-label{{font-weight:600}}.chart-key{{margin:10px 0 0;padding:13px 15px;border:1px solid #dce2ec;border-radius:7px;background:#f8fafc;color:#475569;font-size:13px}}.chart-key strong{{color:#172033}}.chart-key-items{{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));align-items:start;gap:12px 20px;margin-top:10px}}.chart-key-item{{display:flex;align-items:flex-start;gap:9px;min-width:0}}.chart-key-copy{{display:grid;gap:3px;line-height:1.42}}.chart-key-term{{font-size:13px}}.chart-key-detail{{color:#5d687c}}.chart-key-symbol{{position:relative;display:inline-block;flex:0 0 auto;width:28px;height:14px;margin-top:3px}}.key-bar,.key-paired-bars,.key-diverging-bar{{height:10px;background:#2563eb;border-radius:2px}}.key-bar-vertical,.key-diverging-bar-vertical{{width:14px;height:14px;margin-left:7px;background:#2563eb;border-radius:2px}}.key-diverging-bar-vertical{{background:linear-gradient(0deg,#2563eb 0 48%,#64748b 48% 52%,#d97706 52% 100%)}}.key-paired-bars{{background:linear-gradient(90deg,#2563eb 0 45%,transparent 45% 55%,#d97706 55% 100%)}}.key-diverging-bar{{background:linear-gradient(90deg,#2563eb 0 48%,#64748b 48% 52%,#d97706 52% 100%)}}.key-series-line{{height:0;border-top:3px solid #2563eb}}.key-series-line::after,.key-point::after{{content:"";position:absolute;width:8px;height:8px;border-radius:50%;background:#2563eb;left:10px;top:-5px;border:1px solid #fff}}.key-point{{height:0;border-top:1px solid transparent}}.key-zero{{height:0;border-top:3px solid #64748b;top:7px}}.key-box{{height:12px;background:#2563eb38;border:1px solid #2563eb}}.key-median{{height:14px;border-left:3px solid #2563eb;margin-left:13px}}.key-range{{height:0;border-top:1px solid #2563eb;top:7px}}.key-range::before,.key-range::after{{content:"";position:absolute;top:-5px;height:10px;border-left:1px solid #2563eb}}.key-range::before{{left:0}}.key-range::after{{right:0}}.key-n::after{{content:"n";position:absolute;inset:0;text-align:center;font-weight:700;color:#172033}}.key-label::after{{content:"12.3%";position:absolute;inset:0;font-size:10px;font-weight:700;color:#172033}}.chart-explanation{{max-width:120ch;margin:12px 0 0;padding-top:10px;border-top:1px solid #dce2ec;line-height:1.55;color:#334155}}.distribution-facets .panel-title{{font-size:15px;font-weight:700;fill:#172033}}.distribution-facets .budget-label{{font-size:12px}}.insights{{margin:12px 0 0;padding-left:22px}}.insights li{{margin:9px 0;max-width:105ch}}.method-picker{{margin:14px 0;border:1px solid #dce2ec;border-radius:8px;background:#f8fafc}}.method-picker summary{{cursor:pointer;padding:12px 14px;font-weight:600}}.picker-actions{{padding:10px 14px;border-top:1px solid #dce2ec}}#action-checks{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:7px;padding:6px 14px 14px}}#action-checks label{{overflow-wrap:anywhere}}input,select{{font:inherit}}.table-scroll{{overflow:auto;max-height:620px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px 10px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#eef4ff;z-index:1}}.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}.summary-table{{min-width:980px}}.variant-table{{min-width:1160px}}.method-note{{font-size:13px;color:#5d687c;margin-top:10px}}@media(max-width:700px){{main{{padding:16px}}section{{padding:16px}}.summary-item{{flex:1 1 140px}}.selector-field{{width:100%}}.selector-field select{{width:100%;min-width:0}}.chart-key-items{{grid-template-columns:1fr}}}}
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
{sample_level_table(rows)}
{paired_common_table(rows)}
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
    write_rows(output.parent / "sample_level_summary.csv", sample_level_summaries(rows))
    seed_summaries = seed_level_summaries(rows)
    if seed_summaries:
        write_rows(output.parent / "seed_level_summary.csv", seed_summaries)
    paired_summaries = paired_common_summaries(rows)
    if paired_summaries:
        write_rows(output.parent / "paired_common_summary.csv", paired_summaries)
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
