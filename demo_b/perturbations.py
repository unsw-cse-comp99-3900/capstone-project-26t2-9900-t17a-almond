from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}


@dataclass(frozen=True)
class PerturbationResult:
    source_text: str
    applied_count: int
    notes: str


@dataclass(frozen=True)
class Operator:
    name: str
    graph_action: str
    expected_graph_effect: str
    apply: Callable[[str], PerturbationResult]


def line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def split_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def newline_for(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
    return "\n"


def find_first_function_body_line(lines: list[str]) -> int | None:
    """Return the line index containing the first likely function-opening brace."""
    pending_signature = False
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if re.search(r"\)\s*$", stripped) and ";" not in stripped:
            pending_signature = True
            continue
        if "{" in stripped:
            before_brace = stripped.split("{", 1)[0]
            if pending_signature or re.search(r"\)\s*$", before_brace):
                return idx
        if stripped.endswith(";"):
            pending_signature = False
    return None


DECLARATION_HEAD_RE = re.compile(
    r"^(?:auto|bool|char|const|double|enum|extern|float|int|long|register|short|signed|"
    r"size_t|ssize_t|static|struct|typedef|uint|uint8_t|uint16_t|uint32_t|uint64_t|"
    r"union|unsigned|volatile)\b"
)
CUSTOM_DECLARATION_RE = re.compile(
    r"^(?:(?:const|volatile|static|extern|register|signed|unsigned|long|short)\s+)*"
    r"(?:(?:struct|union|enum|class)\s+)?"
    r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*(?:\s*<[^;(){}]+>)?"
    r"(?:\s+|\s*[*&]+\s*)[A-Za-z_]\w*"
    r"(?:\s*\[[^\]]*\])?(?:\s*=[^;]+)?\s*;$"
)


def is_probably_declaration(stripped: str) -> bool:
    if stripped.startswith(
        (
            "return ",
            "goto ",
            "throw ",
            "delete ",
            "new ",
            "sizeof ",
            "co_return ",
            "co_yield ",
            "co_await ",
        )
    ):
        return False
    return bool(DECLARATION_HEAD_RE.match(stripped) or CUSTOM_DECLARATION_RE.match(stripped))


def is_simple_statement_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped.endswith(";"):
        return False
    if not stripped or stripped.startswith(("#", "//", "/*", "*")):
        return False
    if stripped.startswith(("case ", "default:", "else", "do ", "for ", "if ", "switch ", "while ")):
        return False
    if stripped in {";", "break;", "continue;"}:
        return False
    if is_probably_declaration(stripped):
        return False
    if stripped.count("(") != stripped.count(")"):
        return False
    return True


def simple_statement_indices(lines: list[str]) -> list[int]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    return [idx for idx in range(body_start + 1, len(lines)) if is_simple_statement_candidate(lines[idx])]


def apply_dead_statement_insertion(text: str) -> PerturbationResult:
    lines = split_lines(text)
    body_line = find_first_function_body_line(lines)
    if body_line is None:
        return PerturbationResult(text, 0, "no function body opening brace found")

    nl = newline_for(lines)
    indent = line_indent(lines[body_line]) + "    "
    inserted = [
        f"{indent}int dwk_dummy = 0;{nl}",
        f"{indent}dwk_dummy += 0;{nl}",
    ]

    insert_at = body_line + 1
    lines[insert_at:insert_at] = inserted
    return PerturbationResult("".join(lines), 1, "inserted one harmless dummy integer statement pair after first function brace")


def apply_control_wrapper(text: str) -> PerturbationResult:
    lines = split_lines(text)
    candidates = simple_statement_indices(lines)
    if not candidates:
        return PerturbationResult(text, 0, "no safe single-line statement candidate found")

    nl = newline_for(lines)
    idx = candidates[0]
    original = lines[idx]
    indent = line_indent(original)
    stripped = original.strip()
    lines[idx : idx + 1] = [
        f"{indent}if (1) {{{nl}",
        f"{indent}    {stripped}{nl}",
        f"{indent}}}{nl}",
    ]
    return PerturbationResult("".join(lines), 1, "wrapped one safe single-line statement with an if (1) block")


ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>\s*)(?P<lhs>[A-Za-z_]\w*)\s*=\s*(?P<rhs>[A-Za-z_]\w*|[A-Za-z_]\w*\s*[-+*/%]\s*[A-Za-z_]\w*|\d+)\s*;\s*(?P<comment>//.*)?$"
)


def assignment_split_indices(lines: list[str]) -> list[tuple[int, re.Match[str]]]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    matches: list[tuple[int, re.Match[str]]] = []
    for idx in range(body_start + 1, len(lines)):
        match = ASSIGNMENT_RE.match(lines[idx].rstrip("\r\n"))
        if match:
            lhs = match.group("lhs")
            rhs = match.group("rhs")
            if lhs != rhs:
                matches.append((idx, match))
    return matches


def apply_temporary_variable_split(text: str) -> PerturbationResult:
    lines = split_lines(text)
    candidates = assignment_split_indices(lines)
    if not candidates:
        return PerturbationResult(text, 0, "no simple integer-like assignment candidate found")

    nl = newline_for(lines)
    idx, match = candidates[0]
    indent = match.group("indent")
    lhs = match.group("lhs")
    rhs = match.group("rhs").strip()
    comment = f" {match.group('comment')}" if match.group("comment") else ""
    lines[idx : idx + 1] = [
        f"{indent}int dwk_tmp = {rhs};{comment}{nl}",
        f"{indent}{lhs} = dwk_tmp;{nl}",
    ]
    return PerturbationResult("".join(lines), 1, "split one simple assignment through a temporary integer variable")


OPERATORS = {
    "dead_statement": Operator(
        name="dead_statement",
        graph_action="node_add",
        expected_graph_effect="adds harmless statement nodes and local DEF/USE-like structure near function entry",
        apply=apply_dead_statement_insertion,
    ),
    "control_wrapper": Operator(
        name="control_wrapper",
        graph_action="control_edge_add",
        expected_graph_effect="adds if(1) control structure around existing statements, usually affecting CONTROLS edges",
        apply=apply_control_wrapper,
    ),
    "temp_variable_split": Operator(
        name="temp_variable_split",
        graph_action="data_edge_rewire",
        expected_graph_effect="rewrites simple assignments through temporary variables, usually affecting DEF/USE/REACHES edges",
        apply=apply_temporary_variable_split,
    ),
}


def discover_sources(input_path: Path, recursive: bool) -> list[Path]:
    if input_path.is_file():
        return [input_path.resolve()]
    iterator: Iterable[Path] = input_path.rglob("*") if recursive else input_path.glob("*")
    return sorted(
        (path.resolve() for path in iterator if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES),
        key=lambda path: str(path).lower(),
    )


def safe_stem(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "sample"


def deepwukong_command(deepwukong_root: Path, variant_file: Path, output_root: Path) -> str:
    run_dir = output_root / variant_file.stem
    return (
        f'python "{deepwukong_root / "scripts" / "run_demo_pipeline.py"}" '
        f'--input "{variant_file}" '
        f'--output "{run_dir}" '
        "--no-timestamp-output"
    )


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_file",
        "variant_file",
        "action",
        "graph_action",
        "expected_graph_effect",
        "applied_count",
        "status",
        "notes",
        "deepwukong_command",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_command(command: str, cwd: Path) -> int:
    proc = subprocess.run(command, cwd=str(cwd), shell=True)
    return int(proc.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate simple source-level perturbations for DeepWuKong robustness experiments."
    )
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "input_sources")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "perturbed_sources" / "generated",
    )
    parser.add_argument(
        "--deepwukong-root",
        type=Path,
        default=PROJECT_ROOT / "baselines" / "deepwukong",
    )
    parser.add_argument(
        "--deepwukong-output",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "generated" / "deepwukong_perturbations",
    )
    parser.add_argument("--actions", nargs="+", default=list(OPERATORS), choices=sorted(OPERATORS))
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--run-deepwukong", action="store_true", help="Run DeepWuKong for each generated variant.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_root = args.output.resolve()
    deepwukong_root = args.deepwukong_root.resolve()
    dwk_outputs = args.deepwukong_output.resolve()
    variants_dir = output_root / "sources"
    rows: list[dict[str, str]] = []

    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    sources = discover_sources(input_path, recursive=args.recursive)
    if not sources:
        raise FileNotFoundError(f"No C/C++ sources found under: {input_path}")

    variants_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        original = source.read_text(encoding="utf-8", errors="replace")
        for action_name in args.actions:
            action = OPERATORS[action_name]
            result = action.apply(original)
            variant_file = variants_dir / f"{safe_stem(source)}__{action.name}{source.suffix}"
            status = "generated" if result.applied_count > 0 else "skipped"
            command = deepwukong_command(deepwukong_root, variant_file, dwk_outputs)
            if result.applied_count > 0:
                variant_file.write_text(result.source_text, encoding="utf-8", newline="")
                if args.run_deepwukong:
                    code = run_command(command, cwd=deepwukong_root)
                    status = "ran" if code == 0 else f"run_failed_{code}"
            rows.append(
                {
                    "source_file": str(source),
                    "variant_file": str(variant_file) if result.applied_count > 0 else "",
                    "action": action.name,
                    "graph_action": action.graph_action,
                    "expected_graph_effect": action.expected_graph_effect,
                    "applied_count": str(result.applied_count),
                    "status": status,
                    "notes": result.notes,
                    "deepwukong_command": command if result.applied_count > 0 else "",
                }
            )

    manifest = output_root / "manifest.csv"
    write_manifest(manifest, rows)
    generated = sum(1 for row in rows if row["status"] in {"generated", "ran"})
    skipped = sum(1 for row in rows if row["status"] == "skipped")
    print(f"Sources: {len(sources)}")
    print(f"Generated variants: {generated}")
    print(f"Skipped variants: {skipped}")
    print(f"Manifest: {manifest}")
    print(f"Variant source directory: {variants_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
