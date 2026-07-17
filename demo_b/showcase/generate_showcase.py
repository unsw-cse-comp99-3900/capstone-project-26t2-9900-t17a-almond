from __future__ import annotations

import argparse
import csv
import difflib
import html
import json
import os
import re
import subprocess
import sys
import shutil
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SHOWCASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SHOWCASE_DIR.parents[1]
BASELINE_ROOT = PROJECT_ROOT / "baselines" / "deepwukong"
PIPELINE = BASELINE_ROOT / "scripts" / "run_demo_pipeline.py"
DEFAULT_SOURCE = PROJECT_ROOT / "input_sources" / "devign" / "05_codexglue_devign_6599.c"
DEFAULT_OUTPUT = SHOWCASE_DIR / "deepwukong_pdg_showcase.html"
ACTIONS = ("dead_statement", "control_wrapper", "temp_variable_split")
SVG_NS = "http://www.w3.org/2000/svg"
DOCKER_IMAGE = "deepwukong-rtx5060-cu128:experimental"

sys.path.insert(0, str(PROJECT_ROOT))
from demo_b.code.code_perturbations import OPERATORS, is_probably_declaration  # noqa: E402


@dataclass(frozen=True)
class PdgEdge:
    source: int
    target: int
    kind: str


@dataclass(frozen=True)
class Pdg:
    nodes: tuple[int, ...]
    edges: tuple[PdgEdge, ...]

    @property
    def control_count(self) -> int:
        return sum(edge.kind == "control" for edge in self.edges)

    @property
    def data_count(self) -> int:
        return sum(edge.kind == "data" for edge in self.edges)


@dataclass(frozen=True)
class InferenceRun:
    name: str
    source_text: str
    probability: float
    label: int
    threshold: float
    xfg_count: int
    pdg: Pdg
    svg: str


ACTION_COPY = {
    "dead_statement": {
        "label": "dead_statement",
        "short": "No-op insertion",
        "summary": "Adds a harmless local and a no-op update immediately after the function opens.",
        "effect": "The new statements introduce line nodes and local data-flow structure without changing execution.",
    },
    "control_wrapper": {
        "label": "control_wrapper",
        "short": "Control wrapper",
        "summary": "Wraps the first executable assignment in if (1), while declarations remain in function scope.",
        "effect": "The always-true branch adds control structure around an existing assignment without changing its value.",
    },
    "temp_variable_split": {
        "label": "temp_variable_split",
        "short": "Temporary split",
        "summary": "Routes the first simple assignment through a temporary integer variable.",
        "effect": "One assignment becomes a definition and a use, which rewires line-level data dependence.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fresh DeepWuKong inference and generate the standalone PDG showcase."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def validate_control_wrapper(source_text: str) -> str:
    lines = source_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "if (1) {" and index + 1 < len(lines):
            wrapped = lines[index + 1].strip()
            if not wrapped.endswith(";") or is_probably_declaration(wrapped):
                raise RuntimeError("control_wrapper did not wrap an executable statement")
            return wrapped
    raise RuntimeError("control_wrapper did not emit an if (1) wrapper")


def run_inference(name: str, source_text: str, workspace: Path, source_suffix: str) -> tuple[Path, dict[str, Any]]:
    run_root = workspace / name
    input_dir = run_root / "input"
    output_dir = run_root / "output"
    input_dir.mkdir(parents=True)
    source_file = input_dir / f"specimen{source_suffix}"
    source_file.write_text(source_text, encoding="utf-8")
    command = [
        sys.executable,
        str(PIPELINE),
        "--input",
        str(source_file),
        "--output",
        str(output_dir),
        "--config",
        str(BASELINE_ROOT / "configs" / "demo_config.json"),
        "--no-timestamp-output",
    ]
    print(f"[{name}] running fresh DeepWuKong inference", flush=True)
    process = subprocess.run(
        command,
        cwd=BASELINE_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if process.returncode != 0:
        detail = (process.stderr.strip() or process.stdout.strip())[-4000:]
        raise RuntimeError(f"DeepWuKong inference failed for {name}: {detail}")
    predictions_path = output_dir / "predictions.json"
    if not predictions_path.is_file():
        raise RuntimeError(f"DeepWuKong inference for {name} did not produce predictions.json")
    payload = json.loads(predictions_path.read_text(encoding="utf-8"))
    prediction = payload.get("prediction")
    if not isinstance(prediction, dict) or prediction.get("joern_status") != "success":
        raise RuntimeError(f"DeepWuKong inference for {name} did not complete Joern parsing")
    return output_dir, payload


def count_tsv_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def find_leaf_tables(output_dir: Path, source_name: str) -> tuple[Path, Path]:
    candidates: list[tuple[tuple[int, int, int], Path, Path]] = []
    for nodes_path in output_dir.rglob("nodes.csv"):
        edges_path = nodes_path.with_name("edges.csv")
        if not edges_path.is_file():
            continue
        node_rows = count_tsv_data_rows(nodes_path)
        edge_rows = count_tsv_data_rows(edges_path)
        if node_rows == 0 or edge_rows == 0:
            continue
        parent_text = str(nodes_path.parent).lower()
        score = (
            int(source_name.lower() in parent_text),
            len(nodes_path.relative_to(output_dir).parts),
            node_rows + edge_rows,
        )
        candidates.append((score, nodes_path, edges_path))
    if not candidates:
        raise RuntimeError("Joern output did not contain a populated leaf nodes/edges table pair")
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, nodes_path, edges_path = candidates[0]
    return nodes_path, edges_path


def parse_location_line(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"\s*(\d+)", value)
    return int(match.group(1)) if match else None


def parse_pdg(nodes_path: Path, edges_path: Path) -> Pdg:
    key_to_line: dict[str, int] = {}
    with nodes_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            key = row.get("key")
            line = parse_location_line(row.get("location"))
            if key and line is not None:
                key_to_line[key] = line

    retained: dict[str, list[tuple[int, int]]] = {"control": [], "data": []}
    with edges_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            source = key_to_line.get(row.get("start", ""))
            target = key_to_line.get(row.get("end", ""))
            if source is None or target is None:
                continue
            edge_type = row.get("type")
            if edge_type == "CONTROLS":
                retained["control"].append((source, target))
            elif edge_type == "REACHES":
                retained["data"].append((source, target))

    effective: dict[tuple[int, int], str] = {}
    for pair in retained["control"]:
        effective[pair] = "control"
    for pair in retained["data"]:
        effective[pair] = "data"
    edges = tuple(
        PdgEdge(source, target, kind)
        for (source, target), kind in sorted(effective.items(), key=lambda item: (item[0][0], item[0][1]))
    )
    nodes = tuple(sorted({line for edge in edges for line in (edge.source, edge.target)}))
    if not nodes or not edges:
        raise RuntimeError("The source produced no located CONTROLS or REACHES PDG edges")
    return Pdg(nodes=nodes, edges=edges)


def dot_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def source_snippet(source_text: str, line: int) -> str:
    lines = source_text.splitlines()
    if not 1 <= line <= len(lines):
        return ""
    snippet = re.sub(r"\s+", " ", lines[line - 1].strip())
    if not snippet:
        return "blank line"
    return "\n".join(
        textwrap.wrap(snippet, width=34, break_long_words=False, break_on_hyphens=False)
    )


def render_pdg_svg(pdg: Pdg, source_text: str, graph_id: str, label: str, workspace: Path) -> str:
    dot_lines = [
        "digraph pdg {",
        '  graph [bgcolor="transparent", rankdir="TB", pad="0.16", nodesep="0.24", ranksep="0.38", splines="spline", outputorder="edgesfirst"];',
        '  node [shape="box", style="rounded,filled", color="#CBD5E1", fillcolor="#F8FAFC", fontcolor="#172033", fontname="Arial", fontsize="10", penwidth="1", margin="0.09,0.06"];',
        '  edge [arrowsize="0.56", penwidth="1.45", fontname="Arial", fontsize="8"];',
    ]
    for line in pdg.nodes:
        label_text = f"L{line}  {source_snippet(source_text, line)}"
        dot_lines.append(
            f'  n{line} [label={dot_quote(label_text)}, id="{graph_id}-node-{line}", class="line-node"];'
        )
    for index, edge in enumerate(pdg.edges):
        color = "#2563EB" if edge.kind == "control" else "#D97706"
        style = "solid" if edge.kind == "control" else "dashed"
        dot_lines.append(
            f'  n{edge.source} -> n{edge.target} [color="{color}", fontcolor="{color}", style="{style}", id="{graph_id}-edge-{index}", class="{edge.kind}-edge"];'
        )
    dot_lines.append("}")
    dot_path = workspace / f"{graph_id}.dot"
    dot_path.write_text("\n".join(dot_lines) + "\n", encoding="utf-8")
    process = subprocess.run(
        ["dot", "-Tsvg", str(dot_path)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(f"Graphviz failed for {label}: {process.stderr.strip()[-2000:]}")

    root = ET.fromstring(process.stdout)
    ET.register_namespace("", SVG_NS)
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    root.set("class", "pdg-svg")
    root.set("role", "group")
    root.set("aria-label", f"{label} program dependence graph")
    root.set("preserveAspectRatio", "xMidYMid meet")
    root.set("data-zoom", "1")
    graph_title_set = False
    for group in root.findall(f".//{{{SVG_NS}}}g"):
        classes = set(group.get("class", "").split())
        title_element = group.find(f"{{{SVG_NS}}}title")
        title_text = (title_element.text or "") if title_element is not None else ""
        if "graph" in classes and title_element is not None and not graph_title_set:
            title_element.text = f"{label} PDG"
            graph_title_set = True
        if "node" in classes:
            match = re.fullmatch(r"n(\d+)", title_text)
            if not match:
                continue
            line = match.group(1)
            group.set("data-line", line)
            group.set("tabindex", "0")
            group.set("role", "button")
            group.set("aria-label", f"Trace dependencies for source line {line}: {source_snippet(source_text, int(line))}")
        elif "edge" in classes:
            match = re.fullmatch(r"n(\d+)->n(\d+)", title_text)
            if not match:
                continue
            group.set("data-from", match.group(1))
            group.set("data-to", match.group(2))
            group.set("aria-hidden", "true")
    return ET.tostring(root, encoding="unicode", method="xml")


def make_inference_run(
    name: str,
    source_text: str,
    output_dir: Path,
    payload: dict[str, Any],
    workspace: Path,
) -> InferenceRun:
    prediction = payload["prediction"]
    details = payload.get("details", {})
    source_name = "specimen"
    nodes_path, edges_path = find_leaf_tables(output_dir, source_name)
    pdg = parse_pdg(nodes_path, edges_path)
    xfg_count = int(details.get("features", {}).get("xfg", {}).get("xfg_count", 0))
    svg = render_pdg_svg(
        pdg,
        source_text,
        graph_id=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
        label="Original" if name == "original" else ACTION_COPY[name]["short"],
        workspace=workspace,
    )
    return InferenceRun(
        name=name,
        source_text=source_text,
        probability=float(prediction["vulnerability_probability"]),
        label=int(prediction["predicted_label"]),
        threshold=float(prediction["threshold"]),
        xfg_count=xfg_count,
        pdg=pdg,
        svg=svg,
    )


def format_score(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) < 0.001:
        return f"{value:.6e}".replace("e-0", "e-").replace("e+0", "e+")
    return f"{value:.6f}".rstrip("0").rstrip(".")


def label_text(value: int) -> str:
    return "Vulnerable" if value == 1 else "Non-vulnerable"


def render_inline_diff(original: str, variant: str) -> str:
    original_lines = original.splitlines()
    variant_lines = variant.splitlines()
    rows = [
        '<span class="inline-line inline-header" aria-hidden="true">'
        '<span></span><span>OLD</span><span>NEW</span><span>CODE</span></span>'
    ]

    def append_row(kind: str, marker: str, old_number: int | None, new_number: int | None, line: str) -> None:
        if not line.strip():
            return
        rows.append(
            f'<span class="inline-line diff-{kind}">'
            f'<span class="inline-marker" aria-hidden="true">{marker}</span>'
            f'<span class="inline-number" aria-hidden="true">{old_number or ""}</span>'
            f'<span class="inline-number" aria-hidden="true">{new_number or ""}</span>'
            f'<span class="inline-code">{html.escape(line)}</span>'
            "</span>"
        )

    matcher = difflib.SequenceMatcher(a=original_lines, b=variant_lines, autojunk=False)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            for offset, line in enumerate(original_lines[old_start:old_end]):
                append_row("context", "", old_start + offset + 1, new_start + offset + 1, line)
        if tag in {"delete", "replace"}:
            for offset, line in enumerate(original_lines[old_start:old_end]):
                append_row("remove", "−", old_start + offset + 1, None, line)
        if tag in {"insert", "replace"}:
            for offset, line in enumerate(variant_lines[new_start:new_end]):
                append_row("add", "+", None, new_start + offset + 1, line)
    return "\n".join(rows)


def run_to_payload(run: InferenceRun) -> dict[str, Any]:
    return {
        "svg": run.svg,
        "probability": run.probability,
        "probability_display": format_score(run.probability),
        "label": run.label,
        "label_display": label_text(run.label),
        "threshold": run.threshold,
        "xfg_count": run.xfg_count,
        "nodes": len(run.pdg.nodes),
        "edges": len(run.pdg.edges),
        "control_edges": run.pdg.control_count,
        "data_edges": run.pdg.data_count,
    }


def build_page(function_name: str, source_text: str, original: InferenceRun, variants: dict[str, InferenceRun]) -> str:
    original_payload = run_to_payload(original)
    action_payload: dict[str, Any] = {}
    for action, run in variants.items():
        item = run_to_payload(run)
        item.update(ACTION_COPY[action])
        delta = run.probability - original.probability
        item["delta"] = delta
        item["delta_display"] = ("+" if delta > 0 else "") + format_score(delta)
        item["inline_diff"] = render_inline_diff(source_text, run.source_text)
        action_payload[action] = item
    page_data = {
        "function_name": function_name,
        "original": original_payload,
        "actions": action_payload,
    }
    json_data = json.dumps(page_data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return (
        HTML_TEMPLATE.replace("__FUNCTION_NAME__", html.escape(function_name))
        .replace("__SHOWCASE_DATA__", json_data)
    )


@contextmanager
def inference_workspace() -> Any:
    path = Path(tempfile.mkdtemp(prefix="dwk-showcase-"))
    try:
        yield path
    finally:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "chown",
                "-v",
                f"{path}:/work",
                DOCKER_IMAGE,
                "-R",
                f"{os.getuid()}:{os.getgid()}",
                "/work",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    args = parse_args()
    source_path = args.source.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    variants_text: dict[str, str] = {}
    for action in ACTIONS:
        result = OPERATORS[action].apply(source_text)
        if result.applied_count != 1:
            raise RuntimeError(f"{action} could not be applied exactly once: {result.notes}")
        variants_text[action] = result.source_text
    wrapped_statement = validate_control_wrapper(variants_text["control_wrapper"])
    print(f"[control_wrapper] executable statement selected: {wrapped_statement}", flush=True)

    with inference_workspace() as workspace:
        run_inputs = {"original": source_text, **variants_text}
        runs: dict[str, InferenceRun] = {}
        for name, text in run_inputs.items():
            output_dir, payload = run_inference(name, text, workspace, source_path.suffix or ".c")
            runs[name] = make_inference_run(name, text, output_dir, payload, workspace)
            print(
                f"[{name}] complete: {len(runs[name].pdg.nodes)} PDG line nodes, "
                f"{len(runs[name].pdg.edges)} effective edges, "
                f"probability {format_score(runs[name].probability)}",
                flush=True,
            )
        function_name = str(json.loads((workspace / "original" / "output" / "predictions.json").read_text(encoding="utf-8"))["prediction"].get("function_name") or "source function")
        page = build_page(function_name, source_text, runs["original"], {name: runs[name] for name in ACTIONS})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    print(f"Wrote standalone showcase: {output_path}", flush=True)
    return 0


HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>DeepWuKong PDG perturbation atlas</title>
<style>
:root {
  --ink: oklch(25% 0.028 258);
  --ink-soft: oklch(43% 0.022 258);
  --paper: oklch(98% 0.008 83);
  --canvas: oklch(95.5% 0.01 83);
  --surface: oklch(99.5% 0.004 83);
  --line: oklch(86% 0.014 258);
  --line-strong: oklch(74% 0.025 258);
  --control: #2563EB;
  --control-soft: oklch(94% 0.035 258);
  --data: #D97706;
  --data-soft: oklch(94% 0.047 72);
  --success: oklch(43% 0.11 153);
  --focus: oklch(54% 0.17 255);
  --shadow: 0 12px 30px oklch(25% 0.02 258 / 0.1), 0 2px 6px oklch(25% 0.02 258 / 0.08);
  --s1: 4px;
  --s2: 8px;
  --s3: 12px;
  --s4: 16px;
  --s5: 24px;
  --s6: 32px;
  --s7: 48px;
  --r1: 4px;
  --r2: 8px;
  --r3: 12px;
  --r4: 20px;
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
  --font-ui: "Aptos", "Segoe UI Variable", "Helvetica Neue", sans-serif;
  --font-display: "STIX Two Text", "Libertinus Serif", Georgia, serif;
  --font-code: "Berkeley Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--canvas);
  font-family: var(--font-ui);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
button { font: inherit; }
button, [tabindex="0"] { touch-action: manipulation; }
button:focus-visible, [tabindex="0"]:focus-visible, a:focus-visible {
  outline: 3px solid color-mix(in oklch, var(--focus) 38%, transparent);
  outline-offset: 3px;
}
.skip-link {
  position: fixed;
  inset: var(--s3) auto auto var(--s3);
  z-index: 20;
  padding: var(--s2) var(--s3);
  color: var(--surface);
  background: var(--ink);
  border-radius: var(--r1);
  transform: translateY(-180%);
  transition: transform 160ms var(--ease);
}
.skip-link:focus { transform: translateY(0); }
.shell { max-width: 1520px; margin: 0 auto; padding: var(--s4) var(--s5) var(--s7); }
.masthead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s4);
  min-height: 48px;
  padding-bottom: var(--s4);
  border-bottom: 1px solid var(--line-strong);
}
.wordmark { display: flex; align-items: center; gap: var(--s3); font-weight: 750; letter-spacing: -0.012em; }
.wordmark-mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  color: var(--surface);
  background: var(--ink);
  border-radius: var(--r1);
  font: 700 13px/1 var(--font-code);
}
.run-status { display: flex; align-items: center; gap: var(--s2); color: var(--ink-soft); font-size: 13px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px color-mix(in oklch, var(--success) 14%, transparent); }
.intro {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.65fr);
  gap: var(--s7);
  align-items: end;
  padding: var(--s6) 0 var(--s5);
}
.eyebrow { margin: 0 0 var(--s2); color: var(--control); font: 700 12px/1.2 var(--font-code); letter-spacing: 0.08em; text-transform: uppercase; }
h1 { margin: 0; font: 650 clamp(32px, 4vw, 56px)/0.98 var(--font-display); letter-spacing: -0.025em; text-wrap: balance; }
h1 code { font: 600 0.72em/1.1 var(--font-code); color: var(--ink-soft); }
.intro-note { margin: 0; max-width: 52ch; color: var(--ink-soft); text-wrap: pretty; }
.tabs-shell { display: flex; align-items: center; justify-content: space-between; gap: var(--s4); margin-bottom: var(--s3); }
.tabs-label { color: var(--ink-soft); font-size: 13px; }
.tablist { display: flex; gap: var(--s1); padding: var(--s1); background: color-mix(in oklch, var(--line) 55%, var(--surface)); border-radius: var(--r2); }
.tab {
  min-height: 40px;
  padding: 0 var(--s4);
  border: 0;
  border-radius: calc(var(--r2) - var(--s1));
  color: var(--ink-soft);
  background: transparent;
  font: 650 13px/1 var(--font-code);
  cursor: pointer;
  transition: transform 120ms var(--ease), color 160ms var(--ease), background-color 160ms var(--ease), box-shadow 160ms var(--ease);
}
.tab[aria-selected="true"] { color: var(--ink); background: var(--surface); box-shadow: 0 1px 3px oklch(25% 0.02 258 / 0.14); }
.tab:active, .tool-button:active { transform: scale(0.96); }
.graph-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s4); }
.graph-panel { min-width: 0; overflow: hidden; background: var(--surface); border-radius: var(--r3); box-shadow: var(--shadow); }
.graph-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--s4); padding: var(--s4); border-bottom: 1px solid var(--line); }
.panel-kicker { margin: 0 0 var(--s1); color: var(--ink-soft); font: 700 11px/1.2 var(--font-code); letter-spacing: 0.07em; text-transform: uppercase; }
.graph-panel h2 { margin: 0; font: 650 22px/1.12 var(--font-display); letter-spacing: -0.012em; }
.graph-counts { margin: var(--s1) 0 0; color: var(--ink-soft); font-size: 12px; font-variant-numeric: tabular-nums; }
.graph-tools { display: flex; gap: var(--s1); }
.tool-button {
  display: grid;
  place-items: center;
  min-width: 40px;
  height: 40px;
  padding: 0 var(--s2);
  color: var(--ink);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r1);
  cursor: pointer;
  font: 700 15px/1 var(--font-code);
  transition: transform 120ms var(--ease), background-color 160ms var(--ease), border-color 160ms var(--ease);
}
.tool-button.reset { width: auto; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
.graph-canvas {
  position: relative;
  height: clamp(430px, 47vw, 650px);
  overflow: hidden;
  background-color: var(--paper);
  background-image: linear-gradient(to right, color-mix(in oklch, var(--line) 38%, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in oklch, var(--line) 38%, transparent) 1px, transparent 1px);
  background-size: 24px 24px;
}
.graph-target, .pdg-svg { width: 100%; height: 100%; display: block; }
.pdg-svg.is-pannable { cursor: grab; touch-action: none; user-select: none; }
.pdg-svg.is-dragging, .pdg-svg.is-dragging .node { cursor: grabbing; }
.pdg-svg .node, .pdg-svg .edge { transition: opacity 130ms var(--ease), filter 130ms var(--ease); }
.pdg-svg .node { cursor: crosshair; }
.pdg-svg .node polygon, .pdg-svg .node path { transition: stroke-width 130ms var(--ease), fill 130ms var(--ease); }
.pdg-svg .trace-dim { opacity: 0.14; }
.pdg-svg .node.trace-hit { opacity: 1; filter: drop-shadow(0 2px 3px oklch(25% 0.02 258 / 0.18)); }
.pdg-svg .node.trace-hit polygon, .pdg-svg .node.trace-hit path { stroke: var(--ink); stroke-width: 2; fill: var(--surface); }
.pdg-svg .edge.trace-hit { opacity: 1; filter: drop-shadow(0 1px 1px oklch(25% 0.02 258 / 0.16)); }
.trace-status { min-height: 38px; padding: var(--s2) var(--s4); color: var(--ink-soft); background: var(--surface); border-top: 1px solid var(--line); font-size: 12px; }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s4); padding: var(--s3) var(--s4); background: var(--surface); border-top: 1px solid var(--line); color: var(--ink-soft); font-size: 12px; }
.legend strong { color: var(--ink); }
.legend-item { display: inline-flex; align-items: center; gap: var(--s2); }
.edge-swatch { width: 34px; height: 0; border-top: 2px solid var(--control); }
.edge-swatch.data { border-top-color: var(--data); border-top-style: dashed; }
.metric-rail {
  display: grid;
  grid-template-columns: minmax(180px, 1.2fr) repeat(4, minmax(120px, 0.8fr));
  gap: 0;
  margin: var(--s4) 0 var(--s6);
  overflow: hidden;
  background: var(--ink);
  color: var(--surface);
  border-radius: var(--r2);
}
.metric { min-width: 0; padding: var(--s3) var(--s4); border-right: 1px solid oklch(98% 0.005 258 / 0.16); }
.metric:last-child { border-right: 0; }
.metric-label { display: block; margin-bottom: var(--s1); color: oklch(88% 0.018 258); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
.metric-value { display: block; overflow-wrap: anywhere; font: 650 15px/1.3 var(--font-code); font-variant-numeric: tabular-nums; }
.action-brief { display: grid; grid-template-columns: minmax(0, 0.7fr) minmax(0, 1.3fr); gap: var(--s5); align-items: start; margin-bottom: var(--s6); }
.action-brief h2, .code-section h2 { margin: 0 0 var(--s2); font: 650 25px/1.1 var(--font-display); letter-spacing: -0.012em; }
.action-brief p { margin: 0; color: var(--ink-soft); text-wrap: pretty; }
.action-effect { padding-top: var(--s1); font-family: var(--font-code); font-size: 13px; }
.code-section { display: block; }
.code-column { min-width: 0; }
.code-heading { display: flex; align-items: baseline; justify-content: space-between; gap: var(--s3); margin-bottom: var(--s3); }
.code-heading p { margin: 0; color: var(--ink-soft); font-size: 12px; }
.code-frame { max-height: 620px; overflow: auto; margin: 0; padding: var(--s2) 0; background: var(--ink); color: oklch(92% 0.012 258); border-radius: var(--r2); box-shadow: var(--shadow); font: 11.5px/1.45 var(--font-code); tab-size: 4; }
.inline-line { display: grid; grid-template-columns: 24px 42px 42px minmax(max-content, 1fr); min-height: 17px; }
.inline-header { position: sticky; top: calc(-1 * var(--s2)); z-index: 1; padding-block: var(--s1); color: oklch(68% 0.025 258); background: var(--ink); border-bottom: 1px solid oklch(42% 0.025 258); font-size: 10px; letter-spacing: 0.06em; }
.inline-marker { text-align: center; user-select: none; }
.inline-number { padding-right: var(--s2); color: oklch(65% 0.025 258); text-align: right; user-select: none; }
.inline-code { padding-right: var(--s4); white-space: pre; }
.diff-add { color: oklch(86% 0.13 148); background: oklch(37% 0.08 148 / 0.38); }
.diff-remove { color: oklch(86% 0.11 28); background: oklch(38% 0.08 28 / 0.34); }
.method-note { margin-top: var(--s5); padding: var(--s4) 0 0; border-top: 1px solid var(--line-strong); color: var(--ink-soft); font-size: 12px; text-wrap: pretty; }
.method-note strong { color: var(--ink); }
@media (hover: hover) {
  .tool-button:hover { background: var(--surface); border-color: var(--line-strong); }
  .tab:hover:not([aria-selected="true"]) { color: var(--ink); }
}
@media (max-width: 900px) {
  .shell { padding-inline: var(--s4); }
  .intro { grid-template-columns: 1fr; gap: var(--s4); }
  .graph-grid, .code-section { grid-template-columns: 1fr; }
  .graph-canvas { height: 520px; }
  .metric-rail { grid-template-columns: repeat(2, 1fr); }
  .metric:first-child { grid-column: 1 / -1; }
  .metric:nth-child(odd) { border-right: 0; }
}
@media (max-width: 600px) {
  .shell { padding: var(--s3) var(--s3) var(--s6); }
  .masthead { align-items: flex-start; }
  .run-status { max-width: 160px; text-align: right; }
  .intro { padding-top: var(--s5); }
  .tabs-shell { align-items: flex-start; flex-direction: column; }
  .tablist { display: grid; grid-template-columns: 1fr; width: 100%; }
  .tab { width: 100%; padding-inline: var(--s3); text-align: left; }
  .graph-panel-head { flex-direction: column; }
  .graph-tools { width: 100%; }
  .tool-button.reset { margin-left: auto; }
  .graph-canvas { height: 440px; }
  .legend { align-items: flex-start; flex-direction: column; gap: var(--s2); }
  .metric-rail { grid-template-columns: 1fr 1fr; }
  .metric { border-bottom: 1px solid oklch(98% 0.005 258 / 0.16); }
  .action-brief { grid-template-columns: 1fr; gap: var(--s3); }
  .code-heading { align-items: flex-start; flex-direction: column; }
  .code-frame { max-height: 560px; font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
</style>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to graph atlas</a>
<div class="shell">
  <header class="masthead">
    <div class="wordmark"><span class="wordmark-mark" aria-hidden="true">DWK</span><span>DeepWuKong graph laboratory</span></div>
    <div class="run-status"><span class="status-dot" aria-hidden="true"></span><span>Fresh inference set, 4/4 complete</span></div>
  </header>
  <main id="main-content">
    <section class="intro" aria-labelledby="page-title">
      <div>
        <p class="eyebrow">Program dependence graph atlas</p>
        <h1 id="page-title">Perturbation atlas: <code>__FUNCTION_NAME__()</code></h1>
      </div>
      <p class="intro-note">Compare one original line-level PDG with three semantics-preserving source actions. The graphs show only located control and data dependencies used by the DeepWuKong graph pipeline.</p>
    </section>

    <section aria-label="Perturbation comparison">
      <div class="tabs-shell">
        <span class="tabs-label">Select an active perturbation</span>
        <div class="tablist" role="tablist" aria-label="Perturbation actions">
          <button class="tab" id="tab-dead_statement" role="tab" aria-selected="true" aria-controls="comparison-panel" data-action="dead_statement">dead_statement</button>
          <button class="tab" id="tab-control_wrapper" role="tab" aria-selected="false" aria-controls="comparison-panel" data-action="control_wrapper" tabindex="-1">control_wrapper</button>
          <button class="tab" id="tab-temp_variable_split" role="tab" aria-selected="false" aria-controls="comparison-panel" data-action="temp_variable_split" tabindex="-1">temp_variable_split</button>
        </div>
      </div>

      <div id="comparison-panel" role="tabpanel" aria-labelledby="tab-dead_statement">
        <div class="graph-grid">
          <article class="graph-panel" data-graph-panel="original">
            <header class="graph-panel-head">
              <div><p class="panel-kicker">Reference</p><h2>Original PDG</h2><p class="graph-counts" id="original-counts"></p></div>
              <div class="graph-tools" aria-label="Original graph zoom controls">
                <button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out original graph">−</button>
                <button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in original graph">+</button>
                <button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset original graph zoom">Reset</button>
              </div>
            </header>
            <div class="graph-canvas"><div class="graph-target" id="original-graph"></div></div>
            <div class="trace-status" aria-live="polite">Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.</div>
          </article>
          <article class="graph-panel" data-graph-panel="selected">
            <header class="graph-panel-head">
              <div><p class="panel-kicker">Selected action</p><h2 id="selected-graph-title"></h2><p class="graph-counts" id="selected-counts"></p></div>
              <div class="graph-tools" aria-label="Selected graph zoom controls">
                <button class="tool-button" type="button" data-zoom="out" aria-label="Zoom out selected graph">−</button>
                <button class="tool-button" type="button" data-zoom="in" aria-label="Zoom in selected graph">+</button>
                <button class="tool-button reset" type="button" data-zoom="reset" aria-label="Reset selected graph zoom">Reset</button>
              </div>
            </header>
            <div class="graph-canvas"><div class="graph-target" id="selected-graph"></div></div>
            <div class="trace-status" aria-live="polite">Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.</div>
          </article>
        </div>
        <div class="legend" aria-label="PDG edge legend">
          <strong>Exact edge legend</strong>
          <span class="legend-item"><span class="edge-swatch" aria-hidden="true"></span>Control, solid blue</span>
          <span class="legend-item"><span class="edge-swatch data" aria-hidden="true"></span>Data, dashed orange</span>
          <span>Nodes represent source lines, not Joern AST nodes.</span>
        </div>

        <div class="metric-rail" aria-label="Inference and graph comparison">
          <div class="metric"><span class="metric-label">Prediction</span><span class="metric-value" id="metric-transition"></span></div>
          <div class="metric"><span class="metric-label">Original score</span><span class="metric-value" id="metric-original-score"></span></div>
          <div class="metric"><span class="metric-label">Selected score</span><span class="metric-value" id="metric-selected-score"></span></div>
          <div class="metric"><span class="metric-label">Probability delta</span><span class="metric-value" id="metric-delta"></span></div>
          <div class="metric"><span class="metric-label">XFG slices</span><span class="metric-value" id="metric-xfg"></span></div>
        </div>

        <div class="action-brief">
          <div><p class="eyebrow" id="action-kicker"></p><h2 id="action-summary"></h2></div>
          <p class="action-effect" id="action-effect"></p>
        </div>
      </div>
    </section>

    <section class="code-section" aria-label="Source code with inline perturbation diff">
      <div class="code-column">
        <div class="code-heading"><div><p class="eyebrow">Complete source with inline changes</p><h2 id="diff-heading">Inline diff</h2></div><p>Original and selected line numbers; blank lines omitted.</p></div>
        <pre class="code-frame" id="diff-output" tabindex="0" aria-label="Complete source code with selected perturbation changes inline"></pre>
      </div>
    </section>

    <p class="method-note"><strong>PDG construction.</strong> Located Joern node keys map to integer source lines. Only <code>CONTROLS</code> and <code>REACHES</code> edges with two located endpoints are retained. Control edges are added first, then data edges, so data replaces control for the same ordered line pair. Self-loops remain; isolated lines are omitted. Counts above are effective PDG line nodes and edges, not raw CPG table counts. File probability is the maximum vulnerable probability across XFG slices at a 0.5 threshold.</p>
  </main>
</div>
<script id="showcase-data" type="application/json">__SHOWCASE_DATA__</script>
<script>
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('showcase-data').textContent);
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  let activeAction = 'dead_statement';

  const byId = (id) => document.getElementById(id);
  const graphSummary = (item) => `${item.nodes} line nodes · ${item.edges} effective edges · ${item.control_edges} control · ${item.data_edges} data`;

  function getBaseViewBox(svg) {
    if (!svg.dataset.baseViewBox) svg.dataset.baseViewBox = svg.getAttribute('viewBox');
    return svg.dataset.baseViewBox.split(/\s+/).map(Number);
  }

  function syncPanState(svg) {
    svg.classList.toggle('is-pannable', Number(svg.dataset.zoom || 1) > 1);
  }

  function clampViewBox(svg, x, y, width, height) {
    const [baseX, baseY, baseWidth, baseHeight] = getBaseViewBox(svg);
    const clampedX = width >= baseWidth
      ? baseX + (baseWidth - width) / 2
      : Math.min(baseX + baseWidth - width, Math.max(baseX, x));
    const clampedY = height >= baseHeight
      ? baseY + (baseHeight - height) / 2
      : Math.min(baseY + baseHeight - height, Math.max(baseY, y));
    return [clampedX, clampedY, width, height];
  }

  function resetViewBox(svg) {
    if (!svg) return;
    svg.setAttribute('viewBox', getBaseViewBox(svg).join(' '));
    svg.dataset.zoom = '1';
    syncPanState(svg);
  }

  function zoomGraph(panel, direction) {
    const svg = panel.querySelector('svg');
    if (!svg) return;
    const base = getBaseViewBox(svg);
    const current = svg.getAttribute('viewBox').split(/\s+/).map(Number);
    let zoom = Number(svg.dataset.zoom || 1);
    zoom = direction === 'in' ? Math.min(zoom * 1.25, 3.052) : direction === 'out' ? Math.max(zoom / 1.25, 0.64) : 1;
    const width = base[2] / zoom;
    const height = base[3] / zoom;
    const centerX = direction === 'reset' ? base[0] + base[2] / 2 : current[0] + current[2] / 2;
    const centerY = direction === 'reset' ? base[1] + base[3] / 2 : current[1] + current[3] / 2;
    svg.setAttribute('viewBox', clampViewBox(svg, centerX - width / 2, centerY - height / 2, width, height).join(' '));
    svg.dataset.zoom = String(zoom);
    syncPanState(svg);
  }

  function wirePan(svg) {
    let drag = null;
    const stopDrag = (event) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      drag = null;
      svg.classList.remove('is-dragging');
    };
    svg.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || Number(svg.dataset.zoom || 1) <= 1) return;
      drag = {
        pointerId: event.pointerId,
        clientX: event.clientX,
        clientY: event.clientY,
        viewBox: svg.getAttribute('viewBox').split(/\s+/).map(Number),
      };
      svg.setPointerCapture(event.pointerId);
      svg.classList.add('is-dragging');
      event.preventDefault();
    });
    svg.addEventListener('pointermove', (event) => {
      if (!drag || drag.pointerId !== event.pointerId) return;
      const rect = svg.getBoundingClientRect();
      const unitsPerPixel = Math.max(drag.viewBox[2] / rect.width, drag.viewBox[3] / rect.height);
      const x = drag.viewBox[0] - (event.clientX - drag.clientX) * unitsPerPixel;
      const y = drag.viewBox[1] - (event.clientY - drag.clientY) * unitsPerPixel;
      svg.setAttribute('viewBox', clampViewBox(svg, x, y, drag.viewBox[2], drag.viewBox[3]).join(' '));
    });
    svg.addEventListener('pointerup', stopDrag);
    svg.addEventListener('pointercancel', stopDrag);
  }

  function clearTrace(svg, status) {
    svg.querySelectorAll('.trace-dim, .trace-hit').forEach((element) => element.classList.remove('trace-dim', 'trace-hit'));
    status.textContent = 'Focus or hover a line node to trace dependencies. Zoom in, then drag to pan.';
  }

  function traceNode(svg, node, status) {
    const line = node.dataset.line;
    const edges = Array.from(svg.querySelectorAll('.edge'));
    const incident = edges.filter((edge) => edge.dataset.from === line || edge.dataset.to === line);
    const neighbors = new Set([line]);
    incident.forEach((edge) => {
      neighbors.add(edge.dataset.from);
      neighbors.add(edge.dataset.to);
    });
    svg.querySelectorAll('.node, .edge').forEach((element) => element.classList.add('trace-dim'));
    svg.querySelectorAll('.node').forEach((candidate) => {
      if (neighbors.has(candidate.dataset.line)) candidate.classList.add('trace-hit');
    });
    incident.forEach((edge) => edge.classList.add('trace-hit'));
    status.textContent = `Line ${line}: ${incident.length} incident ${incident.length === 1 ? 'edge' : 'edges'}, ${Math.max(0, neighbors.size - 1)} neighboring ${neighbors.size === 2 ? 'line' : 'lines'}.`;
  }

  function wireGraph(panel) {
    const svg = panel.querySelector('svg');
    const status = panel.querySelector('.trace-status');
    if (!svg) return;
    resetViewBox(svg);
    wirePan(svg);
    svg.querySelectorAll('.node').forEach((node) => {
      node.addEventListener('pointerenter', () => traceNode(svg, node, status));
      node.addEventListener('pointerleave', () => {
        if (!node.matches(':focus')) clearTrace(svg, status);
      });
      node.addEventListener('focus', () => traceNode(svg, node, status));
      node.addEventListener('blur', () => clearTrace(svg, status));
    });
  }

  function render(actionName, focusTab = false) {
    activeAction = actionName;
    const action = data.actions[actionName];
    byId('original-graph').innerHTML = data.original.svg;
    byId('selected-graph').innerHTML = action.svg;
    byId('original-counts').textContent = graphSummary(data.original);
    byId('selected-counts').textContent = graphSummary(action);
    byId('selected-graph-title').textContent = action.short + ' PDG';
    byId('metric-transition').textContent = `${data.original.label_display} → ${action.label_display}`;
    byId('metric-original-score').textContent = data.original.probability_display;
    byId('metric-selected-score').textContent = action.probability_display;
    byId('metric-delta').textContent = action.delta_display;
    byId('metric-xfg').textContent = `${data.original.xfg_count} → ${action.xfg_count}`;
    byId('action-kicker').textContent = action.label;
    byId('action-summary').textContent = action.summary;
    byId('action-effect').textContent = action.effect;
    byId('diff-heading').textContent = `${action.label} inline diff`;
    byId('diff-output').innerHTML = action.inline_diff;
    tabs.forEach((tab) => {
      const selected = tab.dataset.action === actionName;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected) {
        tab.setAttribute('aria-controls', 'comparison-panel');
        byId('comparison-panel').setAttribute('aria-labelledby', tab.id);
        if (focusTab) tab.focus();
      }
    });
    document.querySelectorAll('.graph-panel').forEach(wireGraph);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => render(tab.dataset.action));
    tab.addEventListener('keydown', (event) => {
      let next = index;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = tabs.length - 1;
      else return;
      event.preventDefault();
      render(tabs[next].dataset.action, true);
    });
  });

  document.querySelectorAll('.graph-panel').forEach((panel) => {
    panel.querySelectorAll('[data-zoom]').forEach((button) => {
      button.addEventListener('click', () => zoomGraph(panel, button.dataset.zoom));
    });
  });

  render(activeAction);
})();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    raise SystemExit(main())
