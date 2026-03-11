from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional


def _literal_value(node: ast.AST) -> Any:
    """Extract simple literal values used in comparisons/defaults."""
    if isinstance(node, ast.Constant):
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
    ):
        value = node.operand.value
        if isinstance(value, (int, float)):
            return -value if isinstance(node.op, ast.USub) else value
    return None


def _annotation_to_text(node: Optional[ast.AST]) -> str:
    if node is None:
        return "Any"
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            return node.value.id
        return "Any"


def _raise_type_name(node: ast.Raise) -> Optional[str]:
    exc = node.exc
    if exc is None:
        return "Exception"
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Call):
        func = exc.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    if isinstance(exc, ast.Attribute):
        return exc.attr
    return None


class _BlockRaiseInspector(ast.NodeVisitor):
    """Inspect a statement block while refusing to enter nested defs/classes."""

    def __init__(self) -> None:
        self.has_raise = False
        self.exception_types: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Raise(self, node: ast.Raise) -> None:
        self.has_raise = True
        exc_name = _raise_type_name(node)
        if exc_name:
            self.exception_types.append(exc_name)


def _inspect_block_for_raise(statements: List[ast.stmt]) -> Dict[str, Any]:
    inspector = _BlockRaiseInspector()
    for stmt in statements:
        inspector.visit(stmt)
    unique = list(dict.fromkeys(inspector.exception_types))
    return {
        "has_raise": inspector.has_raise,
        "exception_types": unique,
    }


class BodyVisitor(ast.NodeVisitor):
    """Collect branches and raise metadata inside one function body only."""

    def __init__(self) -> None:
        self.branches: List[Dict[str, Any]] = []
        self.raises = False
        self.unconditional_raise = False
        self.exception_types: List[str] = []
        self._conditional_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Raise(self, node: ast.Raise) -> None:
        self.raises = True
        if self._conditional_depth == 0:
            self.unconditional_raise = True
        exc_name = _raise_type_name(node)
        if exc_name:
            self.exception_types.append(exc_name)

    def visit_If(self, node: ast.If) -> None:
        self._capture_if_branch(node)

        self._conditional_depth += 1
        try:
            for stmt in node.body:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)
        finally:
            self._conditional_depth -= 1

    def visit_Match(self, node: ast.Match) -> None:
        # We only traverse cases to discover raise statements.
        self._conditional_depth += 1
        try:
            for case in node.cases:
                for stmt in case.body:
                    self.visit(stmt)
        finally:
            self._conditional_depth -= 1

    def _capture_if_branch(self, node: ast.If) -> None:
        compare = node.test
        if not isinstance(compare, ast.Compare) or len(compare.ops) != 1 or len(compare.comparators) != 1:
            return

        left = compare.left
        right = compare.comparators[0]

        arg_name = None
        value = None

        if isinstance(left, ast.Name):
            arg_name = left.id
            value = _literal_value(right)
        elif isinstance(right, ast.Name):
            arg_name = right.id
            value = _literal_value(left)

        if arg_name is None:
            return
        if value is None and value is not False and value != 0:
            return

        body_meta = _inspect_block_for_raise(node.body)
        else_meta = _inspect_block_for_raise(node.orelse)

        raise_when = None
        exception_type = None
        if body_meta["has_raise"] and not else_meta["has_raise"]:
            raise_when = "truthy"
            exception_type = body_meta["exception_types"][0] if len(body_meta["exception_types"]) == 1 else None
        elif else_meta["has_raise"] and not body_meta["has_raise"]:
            raise_when = "falsy"
            exception_type = else_meta["exception_types"][0] if len(else_meta["exception_types"]) == 1 else None

        try:
            source = ast.unparse(compare)
        except Exception:
            source = ""

        self.branches.append({
            "arg": arg_name,
            "op": type(compare.ops[0]).__name__,
            "value": value,
            "source": source,
            "raise_when": raise_when,
            "exception_type": exception_type,
        })


class FuncExtractor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.functions: List[Dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("__"):
            return

        unsupported_reason = None
        if node.args.vararg or node.args.kwarg:
            unsupported_reason = "varargs/kwargs are outside the PoC scope"

        args_meta: List[Dict[str, Any]] = []
        positional = list(node.args.posonlyargs) + list(node.args.args)
        defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)

        for idx, arg in enumerate(positional):
            args_meta.append({
                "name": arg.arg,
                "annotation": _annotation_to_text(arg.annotation),
                "kind": "positional_only" if idx < len(node.args.posonlyargs) else "positional_or_keyword",
                "has_default": defaults[idx] is not None,
                "default": _literal_value(defaults[idx]) if defaults[idx] is not None else None,
            })

        for kw_arg, kw_default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            args_meta.append({
                "name": kw_arg.arg,
                "annotation": _annotation_to_text(kw_arg.annotation),
                "kind": "keyword_only",
                "has_default": kw_default is not None,
                "default": _literal_value(kw_default) if kw_default is not None else None,
            })

        body_visitor = BodyVisitor()
        for stmt in node.body:
            body_visitor.visit(stmt)

        func_info = {
            "name": node.name,
            "args": args_meta,
            "return_type": _annotation_to_text(node.returns),
            "branches": body_visitor.branches,
            "raises": body_visitor.raises,
            "unconditional_raise": body_visitor.unconditional_raise,
            "exception_types": list(dict.fromkeys(body_visitor.exception_types)),
            "unsupported_reason": unsupported_reason,
            "docstring": ast.get_docstring(node),
        }
        self.functions.append(func_info)


def parse_file(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=file_path)
    extractor = FuncExtractor()
    extractor.visit(tree)
    return extractor.functions