from __future__ import annotations

import argparse
import os
import sys
from typing import List

from .code_generator import generate_test_file


def _collect_python_files(path: str) -> List[str]:
    if os.path.isfile(path):
        return [path] if path.endswith(".py") else []
    if os.path.isdir(path):
        files = [
            os.path.join(path, name)
            for name in os.listdir(path)
            if name.endswith(".py") and not name.startswith("__")
        ]
        return sorted(files)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto Test Generator PoC (AST-based, safe green-suite mode)"
    )
    parser.add_argument("input", help="A Python file or a directory of Python files.")
    parser.add_argument(
        "--out",
        "-o",
        default="tests_output",
        help="Directory where generated pytest files will be written.",
    )
    parser.add_argument(
        "--module",
        "-m",
        help="Optional import prefix, e.g. demo_inputs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and print extracted metadata without writing pytest files.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-file processing details.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: path does not exist -> {args.input}")
        sys.exit(1)

    files = _collect_python_files(args.input)
    if not files:
        print("Error: no eligible Python files were found.")
        sys.exit(1)

    summary = {
        "files": len(files),
        "generated_files": 0,
        "syntax_errors": 0,
        "supported_functions": 0,
        "skipped_functions": 0,
        "generated_tests": 0,
    }

    for file_path in files:
        if args.verbose:
            mode = "DRY-RUN" if args.dry_run else "GENERATE"
            print(f"[{mode}] {file_path}")

        result = generate_test_file(
            file_path,
            args.out,
            module_path=args.module,
            dry_run=args.dry_run,
        )

        functions = result.get("functions", [])
        skipped_functions = result.get("skipped_functions", [])
        summary["supported_functions"] += max(0, len(functions) - len(skipped_functions))
        summary["skipped_functions"] += len(skipped_functions)
        summary["generated_tests"] += result.get("generated_tests", 0)

        if result["status"] == "syntax_error":
            summary["syntax_errors"] += 1
            print(f"  - Skipped syntax error: {result['message']}")
            continue

        if result["status"] == "generated":
            summary["generated_files"] += 1
            if args.verbose:
                print(f"  - Wrote: {result['output_file']} ({result['generated_tests']} tests)")

        if args.dry_run:
            for func in functions:
                print(f"  - {func['name']}({', '.join(a['name'] for a in func['args'])}) -> {func['return_type']}")
                if func.get("unsupported_reason"):
                    print(f"      unsupported: {func['unsupported_reason']}")
                else:
                    print(f"      branches: {func.get('branches', [])}")
                    print(f"      raises: {func.get('raises', False)} / unconditional_raise: {func.get('unconditional_raise', False)}")

    print("\n--- Auto Test Generator Summary ---")
    print(f"Scanned files           : {summary['files']}")
    print(f"Supported functions     : {summary['supported_functions']}")
    print(f"Skipped functions       : {summary['skipped_functions']}")
    print(f"Generated test cases    : {summary['generated_tests']}")
    if not args.dry_run:
        print(f"Generated test files    : {summary['generated_files']}")
    print(f"Syntax-error files      : {summary['syntax_errors']}")
    print("-----------------------------------")


if __name__ == "__main__":
    main()