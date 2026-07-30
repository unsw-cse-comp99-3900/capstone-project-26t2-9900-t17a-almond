from __future__ import annotations

from typing import Any, Iterable, Sequence


DEFAULT_GRAPH_BUDGETS: tuple[int, ...] = (1, 3, 5)
DEFAULT_GRAPH_SEEDS: tuple[int, ...] = (7, 17, 29, 42, 61, 73, 89, 101, 137, 2026)


def normalized_unique_ints(
    values: Iterable[int],
    *,
    name: str,
    minimum: int | None = None,
    sort_values: bool = True,
) -> list[int]:
    normalized = list(dict.fromkeys(int(value) for value in values))
    if not normalized:
        raise ValueError(f"{name} must contain at least one value")
    if minimum is not None and any(value < minimum for value in normalized):
        raise ValueError(f"all {name} values must be at least {minimum}")
    return sorted(normalized) if sort_values else normalized


def resolve_experiment_values(
    plural_values: Sequence[int] | None,
    singular_value: int | None,
    *,
    default: Sequence[int],
    name: str,
    minimum: int | None = None,
    sort_values: bool = True,
) -> list[int]:
    if plural_values is not None:
        selected = plural_values
    elif singular_value is not None:
        selected = [singular_value]
    else:
        selected = default
    return normalized_unique_ints(
        selected,
        name=name,
        minimum=minimum,
        sort_values=sort_values,
    )


def operation_signature(operation: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(operation.get("step", 0)),
        str(operation.get("action", "")),
        tuple(int(node) for node in operation.get("target_nodes", ())),
        tuple(tuple(edge) for edge in operation.get("removed_edges", ())),
        tuple(tuple(edge) for edge in operation.get("added_edges", ())),
        str(operation.get("details", "")),
    )


def operations_form_nested_prefix(
    previous_operations: Sequence[dict[str, Any]],
    current_operations: Sequence[dict[str, Any]],
) -> bool:
    if len(previous_operations) > len(current_operations):
        return False
    previous = tuple(operation_signature(operation) for operation in previous_operations)
    current_prefix = tuple(
        operation_signature(operation)
        for operation in current_operations[: len(previous_operations)]
    )
    return previous == current_prefix


def xfg_tensor_is_scoreable(data: Any) -> bool:
    """Reject XFG tensors that cannot be batched or scored by DeepWuKong."""
    node_features = getattr(data, "x", None)
    edge_index = getattr(data, "edge_index", None)
    if node_features is None or edge_index is None:
        return False
    return bool(node_features.numel() > 0 and edge_index.numel() > 0)
