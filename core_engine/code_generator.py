from __future__ import annotations

import builtins
import itertools
import os
from typing import Any, Dict, List, Optional

from .ast_parser import parse_file
from .heuristics import build_arg_strategy

_BUILTIN_EXCEPTIONS = {
    name
    for name, obj in vars(builtins).items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
}


def _normalize_return_type(annotation: str) -> str:
    text = (annotation or "Any").replace("typing.", "").strip()
    return text or "Any"


def _build_assertion(result_var: str, return_type: str) -> Optional[str]:
    rt = _normalize_return_type(return_type)

    simple_map = {
        "int": "int",
        "float": "float",
        "str": "str",
        "bool": "bool",
        "list": "list",
        "dict": "dict",
    }
    if rt in simple_map:
        return f"assert isinstance({result_var}, {simple_map[rt]})"

    if rt in {"None", "NoneType"}:
        return f"assert {result_var} is None"

    if rt.startswith("Optional[") and rt.endswith("]"):
        inner = rt[len("Optional["):-1].strip()
        inner_assert = _build_assertion(result_var, inner)
        if inner_assert and "isinstance" in inner_assert:
            py_type = inner_assert.split(", ", 1)[1].rstrip(")")
            return f"assert {result_var} is None or isinstance({result_var}, {py_type})"

    if "|" in rt and "None" in rt:
        parts = [p.strip() for p in rt.split("|") if p.strip() != "None"]
        if len(parts) == 1:
            return _build_assertion(result_var, f"Optional[{parts[0]}]")

    return None


def _call_expression(func_name: str, args: List[Dict[str, Any]], value_names: List[str]) -> str:
    positional = []
    keyword = []
    for spec, name in zip(args, value_names):
        if spec["kind"] == "keyword_only":
            keyword.append(f"{spec['name']}={name}")
        else:
            positional.append(name)
    joined = positional + keyword
    return f"{func_name}({', '.join(joined)})"


def _unique_tuples(tuples_: List[List[Any]]) -> List[List[Any]]:
    seen = set()
    out = []
    for item in tuples_:
        key = repr(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _build_safe_cases(args: List[Dict[str, Any]], branches: List[Dict[str, Any]], limit: int = 8) -> Dict[str, Any]:
    strategies = [build_arg_strategy(arg, branches) for arg in args]
    smoke = [s["smoke"] for s in strategies]

    safe_lists = []
    for s in strategies:
        values = s["safe"][:3] if s["safe"] else [None]
        safe_lists.append(values)

    candidates = _unique_tuples([list(combo) for combo in itertools.product(*safe_lists)])
    if smoke not in candidates:
        candidates.insert(0, smoke)

    return {
        "strategies": strategies,
        "smoke": smoke,
        "boundary": candidates[:limit],
    }


def _infer_exception_name(func: Dict[str, Any]) -> Optional[str]:
    if func.get("unconditional_raise"):
        types_ = func.get("exception_types", [])
        if len(types_) == 1 and types_[0] in _BUILTIN_EXCEPTIONS:
            return types_[0]
        return None

    branch_types = [
        b.get("exception_type")
        for b in func.get("branches", [])
        if b.get("raise_when") in {"truthy", "falsy"} and b.get("exception_type")
    ]
    unique = list(dict.fromkeys(branch_types))
    if len(unique) == 1 and unique[0] in _BUILTIN_EXCEPTIONS:
        return unique[0]
    return None


def _build_raise_cases(args: List[Dict[str, Any]], func: Dict[str, Any], safe_smoke: List[Any]) -> List[List[Any]]:
    if func.get("unconditional_raise"):
        return [list(safe_smoke)]

    strategies = [build_arg_strategy(arg, func.get("branches", [])) for arg in args]
    strategies_by_name = {
        spec["name"]: strategy
        for spec, strategy in zip(args, strategies)
    }

    cases = []
    for branch in func.get("branches", []):
        if branch.get("raise_when") not in {"truthy", "falsy"}:
            continue

        target = branch["arg"]
        strategy = strategies_by_name.get(target)
        if not strategy or not strategy["raise"]:
            continue

        values = list(safe_smoke)
        index = next((i for i, spec in enumerate(args) if spec["name"] == target), None)
        if index is None:
            continue

        values[index] = strategy["raise"][0]
        cases.append(values)

    return _unique_tuples(cases)


def generate_test_file(
    source_file: str,
    output_dir: str,
    module_path: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    try:
        functions = parse_file(source_file)
    except SyntaxError as e:
        return {
            "status": "syntax_error",
            "source_file": source_file,
            "message": str(e),
            "functions": [],
            "generated_tests": 0,
            "output_file": None,
        }

    supported = [f for f in functions if not f.get("unsupported_reason")]
    skipped = [f for f in functions if f.get("unsupported_reason")]

    if dry_run:
        return {
            "status": "dry_run",
            "source_file": source_file,
            "functions": functions,
            "generated_tests": 0,
            "output_file": None,
            "skipped_functions": skipped,
        }

    if not supported:
        return {
            "status": "no_supported_functions",
            "source_file": source_file,
            "functions": functions,
            "generated_tests": 0,
            "output_file": None,
            "skipped_functions": skipped,
        }

    module_name = os.path.basename(source_file).replace(".py", "")
    func_names = [f["name"] for f in supported]
    import_stmt = (
        f"from {module_path}.{module_name} import {', '.join(func_names)}"
        if module_path
        else f"from {module_name} import {', '.join(func_names)}"
    )

    lines: List[str] = ["import pytest", import_stmt, ""]
    generated_tests = 0

    for func in supported:
        name = func["name"]
        args = func["args"]
        return_type = func["return_type"]
        is_async = func.get("is_async", False)
        assert_line = _build_assertion("result", return_type)
        prefix = "await " if is_async else ""
        def_prefix = "async def" if is_async else "def"
        async_mark = ["@pytest.mark.asyncio"] if is_async else []

        if not args:
            call = f"{name}()"
            if func.get("unconditional_raise"):
                exc_name = _infer_exception_name(func)
                if exc_name:
                    lines.extend(async_mark)
                    lines.extend([
                        f"{def_prefix} test_{name}_raises():",
                        f"    with pytest.raises({exc_name}):",
                        f"        {prefix}{call}",
                        "",
                    ])
                    generated_tests += 1
                else:
                    lines.extend([
                        "@pytest.mark.skip(reason='unconditional raise detected but exact exception type unresolved')",
                        f"def test_{name}_raises_unresolved():",
                        "    pass",
                        "",
                    ])
                    generated_tests += 1
                continue

            lines.extend(async_mark)
            lines.append(f"{def_prefix} test_{name}_smoke():")
            lines.append(f"    result = {prefix}{call}")
            if assert_line:
                lines.append(f"    {assert_line}")
            else:
                lines.append("    # Execution-only smoke test: return type inference is outside the current PoC scope.")
            lines.append("")
            generated_tests += 1
            continue

        safe_bundle = _build_safe_cases(args, func.get("branches", []))
        smoke_values = safe_bundle["smoke"]
        boundary_cases = safe_bundle["boundary"]
        param_names = ", ".join(arg["name"] for arg in args)
        call_expr = _call_expression(name, args, [arg["name"] for arg in args])

        lines.extend(async_mark)
        lines.append(f"{def_prefix} test_{name}_smoke():")
        for spec, value in zip(args, smoke_values):
            lines.append(f"    {spec['name']} = {repr(value)}")
        lines.append(f"    result = {prefix}{call_expr}")
        if assert_line:
            lines.append(f"    {assert_line}")
        else:
            lines.append("    # Execution-only smoke test: return type inference is outside the current PoC scope.")
        lines.append("")
        generated_tests += 1

        if len(boundary_cases) > 1:
            serialized_cases = [tuple(case) if len(case) > 1 else case[0] for case in boundary_cases]
            lines.append(f"@pytest.mark.parametrize('{param_names}', {serialized_cases!r})")
            lines.extend(async_mark)
            lines.append(f"{def_prefix} test_{name}_boundary({param_names}):")
            lines.append(f"    result = {prefix}{call_expr}")
            if assert_line:
                lines.append(f"    {assert_line}")
            else:
                lines.append("    # Boundary execution-only test: no reliable assertion inferred for the annotated return type.")
            lines.append("")
            generated_tests += len(boundary_cases)

        raise_cases = _build_raise_cases(args, func, smoke_values)
        exc_name = _infer_exception_name(func)
        if raise_cases and exc_name:
            serialized_raise_cases = [tuple(case) if len(case) > 1 else case[0] for case in raise_cases]
            lines.append(f"@pytest.mark.parametrize('{param_names}', {serialized_raise_cases!r})")
            lines.extend(async_mark)
            lines.append(f"{def_prefix} test_{name}_raises({param_names}):")
            lines.append(f"    with pytest.raises({exc_name}):")
            lines.append(f"        {prefix}{call_expr}")
            lines.append("")
            generated_tests += len(raise_cases)
        elif func.get("raises"):
            lines.extend([
                "@pytest.mark.skip(reason='raise path detected but trigger tuple or exact exception type could not be inferred safely')",
                f"def test_{name}_raises_unresolved():",
                "    pass",
                "",
            ])
            generated_tests += 1

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"test_{module_name}.py")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    return {
        "status": "generated",
        "source_file": source_file,
        "functions": functions,
        "generated_tests": generated_tests,
        "output_file": output_file,
        "skipped_functions": skipped,
    }