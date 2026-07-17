from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
    apply: Callable[[str, int], PerturbationResult]


@dataclass(frozen=True)
class SourceRecord:
    path: Path
    dataset_kind: str
    sample_id: str
    split: str = ""
    label: str = ""
    label_name: str = ""
    paired_file: str = ""
    key_line: str = ""
    flaw_or_mixed_lines: str = ""
    cve_id: str = ""
    cwe_id: str = ""
    changed_functions: str = ""


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


def apply_dead_statement_insertion(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    body_line = find_first_function_body_line(lines)
    if body_line is None:
        return PerturbationResult(text, 0, "no function body opening brace found")

    nl = newline_for(lines)
    indent = line_indent(lines[body_line]) + "    "
    inserted: list[str] = []
    for index in range(1, count + 1):
        inserted.extend(
            [
                f"{indent}int dwk_dummy_{index} = {index - 1};{nl}",
                f"{indent}dwk_dummy_{index} += 0;{nl}",
            ]
        )

    insert_at = body_line + 1
    lines[insert_at:insert_at] = inserted
    return PerturbationResult(
        "".join(lines),
        count,
        f"inserted {count} harmless dummy integer statement pair(s) after first function brace",
    )


def apply_control_wrapper(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    candidates = simple_statement_indices(lines)
    if not candidates:
        return PerturbationResult(text, 0, "no safe single-line statement candidate found")

    nl = newline_for(lines)
    selected = candidates[:count]
    for idx in reversed(selected):
        original = lines[idx]
        indent = line_indent(original)
        stripped = original.strip()
        lines[idx : idx + 1] = [
            f"{indent}if (1) {{{nl}",
            f"{indent}    {stripped}{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"wrapped {len(selected)} safe single-line statement(s) with if (1) blocks",
    )


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


def apply_temporary_variable_split(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    candidates = assignment_split_indices(lines)
    if not candidates:
        return PerturbationResult(text, 0, "no simple integer-like assignment candidate found")

    nl = newline_for(lines)
    selected = candidates[:count]
    for temp_id, (idx, match) in reversed(list(enumerate(selected, start=1))):
        indent = match.group("indent")
        lhs = match.group("lhs")
        rhs = match.group("rhs").strip()
        comment = f" {match.group('comment')}" if match.group("comment") else ""
        temp_name = f"dwk_tmp_{temp_id}"
        lines[idx : idx + 1] = [
            f"{indent}int {temp_name} = {rhs};{comment}{nl}",
            f"{indent}{lhs} = {temp_name};{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"split {len(selected)} simple assignment(s) through temporary integer variables",
    )


SECURITY_SINK_ARG_INDEX = {
    "epoll_wait": 2,
    "memcpy": 2,
    "memmove": 2,
    "memset": 2,
    "read": 2,
    "recv": 2,
    "snprintf": 1,
    "strncpy": 2,
    "wcsncat": 2,
    "wcsncpy": 2,
    "write": 2,
}
CALL_LINE_RE = re.compile(r"(?P<prefix>\b(?P<name>[A-Za-z_]\w*)\s*\()(?P<args>.*)(?P<suffix>\)\s*;\s*(?://.*)?)$")
NESTED_DEREF_RE = re.compile(
    r"(?P<base>\b[A-Za-z_]\w*)\s*->\s*(?P<mid>[A-Za-z_]\w*)\s*->\s*(?P<field>[A-Za-z_]\w*)"
)
ARRAY_WRITE_RE = re.compile(
    r"^(?P<indent>\s*)(?P<array>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)*)\s*"
    r"\[\s*(?P<index>[^\]]+)\s*\]\s*(?P<op>[+\-*/%&|^]?=)(?P<rhs>.*;\s*(?://.*)?)$"
)
WIDE_CHAR_SINK_RE = re.compile(
    r"^(?P<indent>\s*)(?P<name>wcscat|wcscpy)\s*\(\s*(?P<dest>[^,]+?)\s*,\s*(?P<src>.+?)\s*\)\s*;\s*(?P<comment>//.*)?$"
)
COUNT_READ_PAIR_RE = re.compile(
    r"(?P<prefix>\b[A-Za-z_]\w*(?:\s*(?:->|\.)\s*)?)(?P<stem>[A-Za-z_]\w*)_count\b"
)
ALLOC_ADD_RE = re.compile(
    r"\b(?:malloc|calloc|realloc|pvPortMalloc)\s*\([^;]*?(?P<a>sizeof\s*\([^)]*\)|[A-Za-z_]\w*)\s*\+\s*(?P<b>[A-Za-z_]\w*)[^;]*\)"
)
MUL_ASSIGN_RE = re.compile(
    r"=\s*\(?\s*(?P<a>[A-Za-z_]\w*)\s*\*\s*(?P<b>[A-Za-z_]\w*)\s*\)?\s*;"
)


def split_call_arguments(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for idx, char in enumerate(args):
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:idx].strip())
            start = idx + 1
    parts.append(args[start:].strip())
    return parts


def find_sensitive_call_targets(lines: list[str]) -> list[tuple[int, re.Match[str], list[str], int]]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    targets: list[tuple[int, re.Match[str], list[str], int]] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        match = CALL_LINE_RE.search(lines[idx].rstrip("\r\n"))
        if not match:
            continue
        name = match.group("name")
        arg_index = SECURITY_SINK_ARG_INDEX.get(name)
        args = split_call_arguments(match.group("args"))
        if arg_index is not None and len(args) > arg_index:
            targets.append((idx, match, args, arg_index))
    return targets


def apply_range_clamp(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = find_sensitive_call_targets(lines)
    if not targets:
        return PerturbationResult(text, 0, "no sensitive call with a clampable size/count argument found")

    nl = newline_for(lines)
    selected = targets[:count]
    for clamp_id, (idx, match, args, arg_index) in reversed(list(enumerate(selected, start=1))):
        indent = line_indent(lines[idx])
        original_arg = args[arg_index]
        clamp_name = f"dwk_clamped_value_{clamp_id}"
        args[arg_index] = clamp_name
        rewritten = f"{indent}{match.group('prefix')}{', '.join(args)}{match.group('suffix')}{nl}"
        lines[idx : idx + 1] = [
            f"{indent}int {clamp_name} = (int)({original_arg});{nl}",
            f"{indent}if ({clamp_name} < 0) {{{nl}",
            f"{indent}    {clamp_name} = 0;{nl}",
            f"{indent}}}{nl}",
            f"{indent}if ({clamp_name} > 4096) {{{nl}",
            f"{indent}    {clamp_name} = 4096;{nl}",
            f"{indent}}}{nl}",
            rewritten,
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"clamped {len(selected)} sensitive sink size/count argument(s) through bounded local variables",
    )


def apply_safe_source_substitution(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return PerturbationResult(text, 0, "no function body opening brace found")

    applied = 0
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        match = NESTED_DEREF_RE.search(lines[idx])
        if not match:
            continue
        base = match.group("base")
        mid = match.group("mid")
        field = match.group("field")
        original = match.group(0)
        guarded = f"(({base} && {base}->{mid}) ? {base}->{mid}->{field} : 0)"
        lines[idx] = lines[idx][: match.start()] + guarded + lines[idx][match.end() :]
        applied += 1
        if applied >= count:
            break
    if applied == 0:
        return PerturbationResult(text, 0, "no nested pointer dereference source found")
    return PerturbationResult(
        "".join(lines),
        applied,
        f"replaced {applied} nested pointer source expression(s) with guarded fallback expressions",
    )


def apply_sink_bound_guard(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = find_sensitive_call_targets(lines)
    if not targets:
        return PerturbationResult(text, 0, "no sensitive sink call found for bound guard insertion")

    nl = newline_for(lines)
    selected = targets[:count]
    for guard_id, (idx, _match, args, arg_index) in reversed(list(enumerate(selected, start=1))):
        indent = line_indent(lines[idx])
        arg = args[arg_index]
        lines[idx:idx] = [
            f"{indent}if ((size_t)({arg}) > 4096U) {{{nl}",
            f"{indent}    return 0;{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"inserted {len(selected)} early-return bound guard(s) before sensitive sink calls",
    )


def apply_postcondition_validation(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    joined = "".join(lines)
    compact_joined = re.sub(r"\s+", "", joined)
    pairs: list[tuple[str, str]] = []
    for match in COUNT_READ_PAIR_RE.finditer(joined):
        prefix = re.sub(r"\s+", "", match.group("prefix"))
        stem = match.group("stem")
        count_expr = f"{prefix}{stem}_count"
        read_expr = f"{prefix}{stem}_read"
        if read_expr in compact_joined and (count_expr, read_expr) not in pairs:
            pairs.append((count_expr, read_expr))
    if not pairs:
        return PerturbationResult(text, 0, "no matching *_count/*_read pair found for postcondition validation")

    nl = newline_for(lines)
    selected = pairs[:count]
    inserted = 0
    for idx in range(len(lines) - 1, -1, -1):
        stripped = lines[idx].strip()
        if not stripped.startswith("return "):
            continue
        indent = line_indent(lines[idx])
        guards: list[str] = []
        for count_expr, read_expr in selected:
            guards.extend(
                [
                    f"{indent}if ({count_expr} != {read_expr}) {{{nl}",
                    f"{indent}    return 0;{nl}",
                    f"{indent}}}{nl}",
                ]
            )
        lines[idx:idx] = guards
        inserted = len(selected)
        break
    if inserted == 0:
        return PerturbationResult(text, 0, "no return statement found for postcondition validation insertion")
    return PerturbationResult(
        "".join(lines),
        inserted,
        f"inserted {inserted} postcondition validation guard(s) for count/read consistency",
    )


def apply_integer_overflow_guard(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return PerturbationResult(text, 0, "no function body opening brace found")

    nl = newline_for(lines)
    targets: list[tuple[int, str, str]] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        match = ALLOC_ADD_RE.search(stripped) or MUL_ASSIGN_RE.search(stripped)
        if match:
            targets.append((idx, match.group("a"), match.group("b")))
    if not targets:
        return PerturbationResult(text, 0, "no allocation size addition or multiplication expression found")

    selected = targets[:count]
    for idx, left, right in reversed(selected):
        indent = line_indent(lines[idx])
        lines[idx:idx] = [
            f"{indent}if ((size_t)({left}) != 0U && (size_t)({right}) > ((size_t)-1) / (size_t)({left})) {{{nl}",
            f"{indent}    return 0;{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"inserted {len(selected)} integer overflow guard(s) before allocation or size arithmetic",
    )


def normalized_expr(expr: str) -> str:
    return re.sub(r"\s+", "", expr)


def parse_array_write(line: str) -> tuple[str, str, str, str, str] | None:
    head = re.match(
        r"^(?P<indent>\s*)(?P<array>[A-Za-z_]\w*(?:\s*(?:->|\.)\s*[A-Za-z_]\w*)*)\s*\[",
        line,
    )
    if not head:
        return None

    start = head.end() - 1
    depth = 0
    end = None
    for pos in range(start, len(line)):
        char = line[pos]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                end = pos
                break
    if end is None:
        return None

    rest = line[end + 1 :].strip()
    op_match = re.match(r"(?P<op>[+\-*/%&|^]?=)(?P<rhs>.*;\s*(?://.*)?)$", rest)
    if not op_match:
        return None

    return (
        head.group("indent"),
        head.group("array"),
        line[start + 1 : end].strip(),
        op_match.group("op"),
        op_match.group("rhs").strip(),
    )


def array_write_targets(lines: list[str]) -> list[tuple[int, tuple[str, str, str, str, str]]]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    targets: list[tuple[int, tuple[str, str, str, str, str]]] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        parsed = parse_array_write(lines[idx].rstrip("\r\n"))
        if parsed:
            targets.append((idx, parsed))
    return targets


def apply_array_index_bound_guard(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = array_write_targets(lines)
    if not targets:
        return PerturbationResult(text, 0, "no array write found for index bound guard")

    nl = newline_for(lines)
    selected = targets[:count]
    for idx, parsed in reversed(selected):
        indent, array_expr, index_expr, op, rhs = parsed
        array_expr = normalized_expr(array_expr)
        original = f"{array_expr}[{index_expr}] {op}{rhs}"
        bound_expr = f"(sizeof({array_expr}) / sizeof(({array_expr})[0]))"
        lines[idx : idx + 1] = [
            f"{indent}if ((int)({index_expr}) >= 0 && (size_t)({index_expr}) < {bound_expr}) {{{nl}",
            f"{indent}    {original}{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"wrapped {len(selected)} array write(s) with index lower/upper bound guards",
    )


def wide_char_sink_targets(lines: list[str]) -> list[tuple[int, re.Match[str]]]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    targets: list[tuple[int, re.Match[str]]] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        match = WIDE_CHAR_SINK_RE.match(lines[idx].rstrip("\r\n"))
        if match:
            targets.append((idx, match))
    return targets


def apply_wide_char_sink_guard(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = wide_char_sink_targets(lines)
    if not targets:
        return PerturbationResult(text, 0, "no wcscat/wcscpy wide-character sink found")

    nl = newline_for(lines)
    selected = targets[:count]
    for guard_id, (idx, match) in reversed(list(enumerate(selected, start=1))):
        indent = match.group("indent")
        name = match.group("name")
        dest = match.group("dest").strip()
        src = match.group("src").strip()
        comment = f" {match.group('comment')}" if match.group("comment") else ""
        remaining = f"dwk_wide_remaining_{guard_id}"
        replacement = "wcsncat" if name == "wcscat" else "wcsncpy"
        lines[idx : idx + 1] = [
            f"{indent}size_t {remaining} = 4096U;{comment}{nl}",
            f"{indent}if ({remaining} > 0U) {{{nl}",
            f"{indent}    {replacement}({dest}, {src}, {remaining} - 1U);{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"rewrote {len(selected)} wcscat/wcscpy sink(s) to bounded wide-character operations",
    )


SENSITIVE_LINE_RE = re.compile(
    r"\b(?:alloca|calloc|free|malloc|memcpy|memmove|memset|read|realloc|recv|snprintf|sprintf|"
    r"strcat|strcpy|strlen|strncpy|wcscat|wcscpy|wcsncat|wcsncpy|write)\s*\("
)
STRUCTURAL_TARGET_RE = re.compile(r"(?:->|\[[^\]]+\]|\*[A-Za-z_]\w*|[A-Za-z_]\w*\s*[-+*/%]\s*[A-Za-z_]\w*)")
CALL_ARG_RE = re.compile(
    r"\b(?:memcpy|memmove|memset|read|recv|snprintf|sprintf|strcat|strcpy|strlen|strncpy|"
    r"wcscat|wcscpy|wcsncat|wcsncpy|write)\s*"
    r"\(\s*(?P<arg>[A-Za-z_]\w*(?:\s*->\s*[A-Za-z_]\w*|\s*\.\s*[A-Za-z_]\w*)?)"
)
GENERIC_CALL_ARG_RE = re.compile(
    r"\b(?!(?:if|for|switch|while|return|sizeof)\b)[A-Za-z_]\w*\s*\(\s*(?P<arg>[^,;)]+)"
)


def targeted_statement_indices(lines: list[str]) -> list[int]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    targets: list[int] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        if SENSITIVE_LINE_RE.search(stripped) or STRUCTURAL_TARGET_RE.search(stripped):
            targets.append(idx)
    return targets


def apply_pattern_dead_code(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = targeted_statement_indices(lines)
    body_line = find_first_function_body_line(lines)
    if not targets and body_line is None:
        return PerturbationResult(text, 0, "no function body opening brace found")

    nl = newline_for(lines)
    selected = targets[:count] if targets else [body_line + 1]  # type: ignore[operator]
    for block_id, idx in reversed(list(enumerate(selected, start=1))):
        indent = line_indent(lines[idx]) if idx < len(lines) else "    "
        lines[idx:idx] = [
            f"{indent}if (0) {{{nl}",
            f"{indent}    char dwk_src_{block_id}[8] = {{0}};{nl}",
            f"{indent}    char dwk_dst_{block_id}[8] = {{0}};{nl}",
            f"{indent}    int dwk_len_{block_id} = (int)sizeof(dwk_dst_{block_id});{nl}",
            f"{indent}    if (dwk_len_{block_id} > 0) {{{nl}",
            f"{indent}        dwk_dst_{block_id}[dwk_len_{block_id} - 1] = dwk_src_{block_id}[0];{nl}",
            f"{indent}    }}{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"inserted {len(selected)} unreachable pointer/array/length pattern block(s) near sensitive or structural lines",
    )


def data_flow_alias_indices(lines: list[str]) -> list[tuple[int, str, str]]:
    body_start = find_first_function_body_line(lines)
    if body_start is None:
        return []
    targets: list[tuple[int, str, str]] = []
    for idx in range(body_start + 1, len(lines)):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*")):
            continue
        match = CALL_ARG_RE.search(stripped)
        if match:
            arg = re.sub(r"\s+", "", match.group("arg"))
            targets.append((idx, arg, "pointer"))
            continue
        match = GENERIC_CALL_ARG_RE.search(stripped)
        if match:
            arg = match.group("arg").strip()
            if arg:
                kind = "integer" if any(token in arg for token in ("+", "-", "*", "/", "%", "(", ")")) else "pointer"
                targets.append((idx, arg, kind))
    return targets


def apply_data_flow_alias(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = data_flow_alias_indices(lines)
    if not targets:
        return apply_temporary_variable_split(text, count)

    nl = newline_for(lines)
    selected = targets[:count]
    for alias_id, (idx, arg, kind) in reversed(list(enumerate(selected, start=1))):
        indent = line_indent(lines[idx])
        if kind == "integer":
            lines[idx:idx] = [
                f"{indent}int dwk_flow_value_{alias_id} = (int)({arg});{nl}",
                f"{indent}dwk_flow_value_{alias_id} += 0;{nl}",
            ]
        else:
            lines[idx:idx] = [
                f"{indent}void *dwk_alias_{alias_id} = (void *)({arg});{nl}",
                f"{indent}dwk_alias_{alias_id} = (void *)((char *)dwk_alias_{alias_id} + 0);{nl}",
            ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"inserted {len(selected)} alias-preserving data-flow no-op(s) near call arguments",
    )


def apply_xfg_targeted_dead_code(text: str, count: int = 1) -> PerturbationResult:
    lines = split_lines(text)
    targets = targeted_statement_indices(lines)
    if not targets:
        return PerturbationResult(text, 0, "no sensitive, pointer, array, or arithmetic target line found")

    nl = newline_for(lines)
    selected = targets[:count]
    for block_id, idx in reversed(list(enumerate(selected, start=1))):
        indent = line_indent(lines[idx])
        lines[idx:idx] = [
            f"{indent}if (0) {{{nl}",
            f"{indent}    int dwk_xfg_guard_{block_id} = {block_id};{nl}",
            f"{indent}    dwk_xfg_guard_{block_id} += 0;{nl}",
            f"{indent}}}{nl}",
        ]
    return PerturbationResult(
        "".join(lines),
        len(selected),
        f"inserted {len(selected)} unreachable no-op block(s) near XFG-relevant target lines",
    )


OPERATORS = {
    "data_flow_alias": Operator(
        name="data_flow_alias",
        graph_action="data_edge_rewire",
        expected_graph_effect="adds alias-preserving data-flow no-ops near sink/call arguments or falls back to temp split",
        apply=apply_data_flow_alias,
    ),
    "dead_statement": Operator(
        name="dead_statement",
        graph_action="node_add",
        expected_graph_effect="adds harmless statement nodes and local DEF/USE-like structure near function entry",
        apply=apply_dead_statement_insertion,
    ),
    "xfg_targeted_dead_code": Operator(
        name="xfg_targeted_dead_code",
        graph_action="targeted_node_add",
        expected_graph_effect="adds unreachable no-op nodes near sensitive calls, pointer operations, arrays, or arithmetic lines",
        apply=apply_xfg_targeted_dead_code,
    ),
    "range_clamp": Operator(
        name="range_clamp",
        graph_action="security_fix_data_sanitize",
        expected_graph_effect="adds bounded local variables before sensitive sink size/count arguments",
        apply=apply_range_clamp,
    ),
    "safe_source_substitution": Operator(
        name="safe_source_substitution",
        graph_action="security_fix_source_replace",
        expected_graph_effect="replaces nested pointer sources with guarded fallback expressions",
        apply=apply_safe_source_substitution,
    ),
    "sink_bound_guard": Operator(
        name="sink_bound_guard",
        graph_action="security_fix_control_guard",
        expected_graph_effect="adds early-return bound checks immediately before sensitive sink calls",
        apply=apply_sink_bound_guard,
    ),
    "postcondition_validation": Operator(
        name="postcondition_validation",
        graph_action="security_fix_postcondition_guard",
        expected_graph_effect="adds consistency checks before successful returns after parsing/counting work",
        apply=apply_postcondition_validation,
    ),
    "integer_overflow_guard": Operator(
        name="integer_overflow_guard",
        graph_action="security_fix_arithmetic_guard",
        expected_graph_effect="adds overflow checks before allocation or size arithmetic",
        apply=apply_integer_overflow_guard,
    ),
    "array_index_bound_guard": Operator(
        name="array_index_bound_guard",
        graph_action="security_fix_array_index_guard",
        expected_graph_effect="wraps array writes with lower/upper index bound checks",
        apply=apply_array_index_bound_guard,
    ),
    "wide_char_sink_guard": Operator(
        name="wide_char_sink_guard",
        graph_action="security_fix_wide_string_sink",
        expected_graph_effect="rewrites wcscat/wcscpy calls to bounded wide-character operations",
        apply=apply_wide_char_sink_guard,
    ),
    "pattern_dead_code": Operator(
        name="pattern_dead_code",
        graph_action="pattern_node_add",
        expected_graph_effect="adds unreachable pointer/array/length pattern nodes near sensitive APIs or structural lines",
        apply=apply_pattern_dead_code,
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


def read_metadata_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def input_contains(input_path: Path, candidate: Path) -> bool:
    input_path = input_path.resolve()
    candidate = candidate.resolve()
    if input_path.is_file():
        return input_path == candidate
    try:
        candidate.relative_to(input_path)
        return True
    except ValueError:
        return False


def dataset_root_for(input_path: Path, kind: str) -> Path | None:
    resolved = input_path.resolve()
    candidates = [resolved] if resolved.is_dir() else [resolved.parent]
    candidates.extend(candidates[0].parents)
    for candidate in candidates:
        if candidate.name.lower() == kind and (candidate / "metadata.csv").is_file():
            return candidate
    return None


def detect_dataset_kind(input_path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    resolved = input_path.resolve()
    names = {part.lower() for part in resolved.parts}
    if "cvefixes" in names:
        return "cvefixes"
    if "cwe119" in names:
        return "cwe119"
    if "devign" in names:
        return "devign"
    return "devign"


def discover_cwe119_records(input_path: Path, recursive: bool) -> list[SourceRecord]:
    root = dataset_root_for(input_path, "cwe119")
    if root is None:
        sources = discover_sources(input_path, recursive=recursive)
        return [SourceRecord(path=source, dataset_kind="cwe119", sample_id=safe_stem(source)) for source in sources]

    records: list[SourceRecord] = []
    metadata = read_metadata_rows(root / "metadata.csv")
    for row in metadata:
        source = (PROJECT_ROOT / row["source_file"]).resolve()
        if not input_contains(input_path, source):
            continue
        split = source.parent.name
        records.append(
            SourceRecord(
                path=source,
                dataset_kind="cwe119",
                sample_id=row.get("sample_id") or safe_stem(source),
                split=split,
                label=row.get("label", ""),
                label_name=row.get("label_name", ""),
                key_line=row.get("key_line", ""),
                flaw_or_mixed_lines=row.get("flaw_or_mixed_lines", ""),
                cwe_id="CWE-119",
            )
        )
    if records:
        return sorted(records, key=lambda item: item.sample_id.lower())
    sources = discover_sources(input_path, recursive=recursive)
    return [SourceRecord(path=source, dataset_kind="cwe119", sample_id=safe_stem(source), split=source.parent.name) for source in sources]


def discover_cvefixes_records(input_path: Path, recursive: bool) -> list[SourceRecord]:
    root = dataset_root_for(input_path, "cvefixes")
    if root is None:
        sources = discover_sources(input_path, recursive=recursive)
        return [SourceRecord(path=source, dataset_kind="cvefixes", sample_id=safe_stem(source)) for source in sources]

    records: list[SourceRecord] = []
    for row in read_metadata_rows(root / "metadata.csv"):
        sample_id = row.get("sample_id", "")
        cve_id = row.get("cve_id", "")
        stem = f"{sample_id}_{cve_id.lower()}" if sample_id and cve_id else ""
        vulnerable = next((root / "vulnerable").glob(f"{stem}.*"), None) if stem else None
        fixed = next((root / "fixed").glob(f"{stem}.*"), None) if stem else None
        for split, source, paired in (("vulnerable", vulnerable, fixed), ("fixed", fixed, vulnerable)):
            if source is None or not input_contains(input_path, source):
                continue
            records.append(
                SourceRecord(
                    path=source.resolve(),
                    dataset_kind="cvefixes",
                    sample_id=f"{sample_id}_{cve_id.lower()}",
                    split=split,
                    label="1" if split == "vulnerable" else "0",
                    label_name=split,
                    paired_file=str(paired.resolve()) if paired else "",
                    cve_id=cve_id,
                    cwe_id=row.get("cwe_id", ""),
                    changed_functions=row.get("changed_functions", ""),
                )
            )
    if records:
        return sorted(records, key=lambda item: (item.sample_id.lower(), item.split))
    sources = discover_sources(input_path, recursive=recursive)
    return [SourceRecord(path=source, dataset_kind="cvefixes", sample_id=safe_stem(source), split=source.parent.name) for source in sources]


def discover_source_records(input_path: Path, recursive: bool, dataset: str = "auto") -> list[SourceRecord]:
    kind = detect_dataset_kind(input_path, dataset)
    if kind == "cwe119":
        return discover_cwe119_records(input_path, recursive=recursive)
    if kind == "cvefixes":
        return discover_cvefixes_records(input_path, recursive=recursive)
    sources = discover_sources(input_path, recursive=recursive)
    return [SourceRecord(path=source, dataset_kind="devign", sample_id=safe_stem(source)) for source in sources]


def safe_stem(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "sample"


def dataset_slug(input_path: Path) -> str:
    path = input_path if input_path.suffix.lower() not in SOURCE_SUFFIXES else input_path.parent
    return safe_stem(path)


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
        "dataset_kind",
        "sample_id",
        "split",
        "label",
        "label_name",
        "paired_file",
        "key_line",
        "flaw_or_mixed_lines",
        "cve_id",
        "cwe_id",
        "changed_functions",
        "source_file",
        "variant_file",
        "action",
        "count",
        "graph_action",
        "expected_graph_effect",
        "applied_count",
        "status",
        "notes",
        "deepwukong_command",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_command(command: str, cwd: Path) -> int:
    proc = subprocess.run(command, cwd=str(cwd), shell=True)
    return int(proc.returncode)


def generation_status(applied_count: int, requested_count: int) -> str:
    if applied_count <= 0:
        return "skipped"
    if applied_count < requested_count:
        return "partial"
    return "generated"


def normalize_counts(values: list[int]) -> list[int]:
    counts: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value < 1:
            raise ValueError(f"Counts must be positive integers: {value}")
        if value not in seen:
            counts.append(value)
            seen.add(value)
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate simple source-level perturbations for DeepWuKong robustness experiments."
    )
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "input_sources" / "devign")
    parser.add_argument(
        "--dataset",
        choices=["auto", "devign", "cwe119", "cvefixes"],
        default="auto",
        help="Input layout. auto detects devign, cwe119, or cvefixes from the input path.",
    )
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
    parser.add_argument("--action", dest="actions", nargs="+", choices=sorted(OPERATORS), help=argparse.SUPPRESS)
    parser.add_argument(
        "--counts",
        nargs="+",
        type=int,
        default=[1],
        help="Perturbation budgets to generate from the original source, e.g. --counts 1 2 3 5.",
    )
    parser.add_argument("--count", dest="counts", nargs="+", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--run-deepwukong", action="store_true", help="Run DeepWuKong for each generated variant.")
    args = parser.parse_args()
    args.counts = normalize_counts(args.counts)
    return args


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
    source_records = discover_source_records(input_path, recursive=args.recursive, dataset=args.dataset)
    if not source_records:
        raise FileNotFoundError(f"No C/C++ sources found under: {input_path}")

    variants_dir.mkdir(parents=True, exist_ok=True)
    for record in source_records:
        source = record.path
        original = source.read_text(encoding="utf-8", errors="replace")
        for action_name in args.actions:
            action = OPERATORS[action_name]
            for count in args.counts:
                result = action.apply(original, count)
                variant_file = variants_dir / f"{record.sample_id}__{action.name}__c{count}{source.suffix}"
                status = generation_status(result.applied_count, count)
                command = deepwukong_command(deepwukong_root, variant_file, dwk_outputs)
                if result.applied_count > 0:
                    variant_file.write_text(result.source_text, encoding="utf-8", newline="")
                    if args.run_deepwukong:
                        code = run_command(command, cwd=deepwukong_root)
                        if code == 0:
                            status = "run_partial" if status == "partial" else "ran"
                        else:
                            status = f"run_failed_{code}"
                rows.append(
                    {
                        "dataset_kind": record.dataset_kind,
                        "sample_id": record.sample_id,
                        "split": record.split,
                        "label": record.label,
                        "label_name": record.label_name,
                        "paired_file": record.paired_file,
                        "key_line": record.key_line,
                        "flaw_or_mixed_lines": record.flaw_or_mixed_lines,
                        "cve_id": record.cve_id,
                        "cwe_id": record.cwe_id,
                        "changed_functions": record.changed_functions,
                        "source_file": str(source),
                        "variant_file": str(variant_file) if result.applied_count > 0 else "",
                        "action": action.name,
                        "count": str(count),
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
    partial = sum(1 for row in rows if row["status"] in {"partial", "run_partial"})
    skipped = sum(1 for row in rows if row["status"] == "skipped")
    dataset_counts: dict[str, int] = {}
    for record in source_records:
        dataset_counts[record.dataset_kind] = dataset_counts.get(record.dataset_kind, 0) + 1
    print(f"Dataset inputs: {', '.join(f'{name}={count}' for name, count in sorted(dataset_counts.items()))}")
    print(f"Sources: {len(source_records)}")
    print(f"Generated variants: {generated}")
    print(f"Partial variants: {partial}")
    print(f"Skipped variants: {skipped}")
    print(f"Manifest: {manifest}")
    print(f"Variant source directory: {variants_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
