from __future__ import annotations

from typing import Any, Dict, List


def _dedupe(values: List[Any]) -> List[Any]:
    ordered = []
    for item in values:
        if item not in ordered:
            ordered.append(item)
    return ordered


def _normalize_annotation(annotation: str) -> str:
    text = (annotation or "Any").replace("typing.", "")
    if text == "list" or text.startswith("List[") or text.startswith("list["):
        return "list"
    if text == "dict" or text.startswith("Dict[") or text.startswith("dict["):
        return "dict"
    if text.startswith("Optional["):
        inner = text[len("Optional["):-1]
        return _normalize_annotation(inner)
    if "|" in text and "None" in text:
        parts = [p.strip() for p in text.split("|") if p.strip() != "None"]
        if len(parts) == 1:
            return _normalize_annotation(parts[0])
    return text


def _base_values(annotation: str, default: Any = None) -> List[Any]:
    norm = _normalize_annotation(annotation)
    base = {
        "int": [0, 1, -1],
        "float": [0.0, 1.5, -2.5],
        "str": ["", "test", "Tiếng Việt", " "],
        "bool": [True, False],
        "list": [[], [1, 2, 3]],
        "dict": [{}, {"k": 1}],
        "Any": [None, 0, "demo"],
    }.get(norm, [None])

    if default is not None:
        base = [default] + base
    return _dedupe(base)


def _matches(value: Any, op: str, pivot: Any) -> bool:
    if op == "Eq":
        return value == pivot
    if op == "NotEq":
        return value != pivot
    if op == "Lt":
        return value < pivot
    if op == "LtE":
        return value <= pivot
    if op == "Gt":
        return value > pivot
    if op == "GtE":
        return value >= pivot
    return False


def _values_for_int_branch(op: str, value: int, raise_when: str | None) -> Dict[str, List[Any]]:
    truthy_map = {
        "Eq": [value],
        "NotEq": [value - 1, value + 1],
        "Lt": [value - 1],
        "LtE": [value - 1, value],
        "Gt": [value + 1],
        "GtE": [value, value + 1],
    }
    falsy_map = {
        "Eq": [value - 1, value + 1],
        "NotEq": [value],
        "Lt": [value, value + 1],
        "LtE": [value + 1],
        "Gt": [value, value - 1],
        "GtE": [value - 1],
    }
    truthy = truthy_map.get(op, [value])
    falsy = falsy_map.get(op, [value])

    if raise_when == "truthy":
        return {"safe": falsy, "raise": truthy}
    if raise_when == "falsy":
        return {"safe": truthy, "raise": falsy}
    return {"safe": truthy + falsy, "raise": []}


def _values_for_str_branch(op: str, value: str, raise_when: str | None) -> Dict[str, List[Any]]:
    alt = f"{value}_alt"
    truthy_map = {
        "Eq": [value],
        "NotEq": [alt],
    }
    falsy_map = {
        "Eq": [alt],
        "NotEq": [value],
    }
    truthy = truthy_map.get(op, [value])
    falsy = falsy_map.get(op, [alt])

    if raise_when == "truthy":
        return {"safe": falsy, "raise": truthy}
    if raise_when == "falsy":
        return {"safe": truthy, "raise": falsy}
    return {"safe": truthy + falsy, "raise": []}


def build_arg_strategy(arg_spec: Dict[str, Any], branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    annotation = arg_spec.get("annotation", "Any")
    base_safe = _base_values(annotation, arg_spec.get("default"))
    safe_values = list(base_safe)
    raise_values: List[Any] = []

    norm = _normalize_annotation(annotation)
    relevant = [b for b in branches if b.get("arg") == arg_spec["name"]]

    filtered_safe = []
    for candidate in safe_values:
        unsafe = False
        for branch in relevant:
            if branch.get("raise_when") == "truthy":
                try:
                    if _matches(candidate, branch["op"], branch["value"]):
                        unsafe = True
                except Exception:
                    pass
            elif branch.get("raise_when") == "falsy":
                try:
                    if not _matches(candidate, branch["op"], branch["value"]):
                        unsafe = True
                except Exception:
                    pass
        if not unsafe:
            filtered_safe.append(candidate)
    safe_values = filtered_safe

    for branch in relevant:
        value = branch.get("value")
        op = branch.get("op")
        raise_when = branch.get("raise_when")

        if norm == "int" and isinstance(value, int) and not isinstance(value, bool):
            split = _values_for_int_branch(op, value, raise_when)
            safe_values.extend(split["safe"])
            raise_values.extend(split["raise"])
        elif norm == "str" and isinstance(value, str):
            split = _values_for_str_branch(op, value, raise_when)
            safe_values.extend(split["safe"])
            raise_values.extend(split["raise"])
        elif norm == "bool" and isinstance(value, bool):
            truthy = [value]
            falsy = [not value]
            if raise_when == "truthy":
                safe_values.extend(falsy)
                raise_values.extend(truthy)
            elif raise_when == "falsy":
                safe_values.extend(truthy)
                raise_values.extend(falsy)
            else:
                safe_values.extend(truthy + falsy)

    safe_values = _dedupe(safe_values)
    raise_values = _dedupe(raise_values)

    if any(b.get("raise_when") in {"truthy", "falsy"} for b in relevant):
        safe_values = [v for v in safe_values if v not in raise_values]

    if not safe_values:
        safe_values = _dedupe(_base_values(annotation, arg_spec.get("default")))

    smoke_value = safe_values[0] if safe_values else None
    return {
        "safe": safe_values,
        "raise": raise_values,
        "smoke": smoke_value,
    }