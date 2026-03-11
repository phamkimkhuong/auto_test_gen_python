from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from typing import Any, Dict, List

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .code_generator import generate_test_file

console = Console() if HAS_RICH else None


def _print_rich_summary(summary: Dict[str, Any], dry_run: bool) -> None:
    if not HAS_RICH:
        print("\n--- Auto Test Generator Summary ---")
        for k, v in summary.items():
            print(f"{k.replace('_', ' ').capitalize():<24}: {v}")
        print("-----------------------------------")
        return

    table = Table(title="[bold blue]Auto Test Generator Summary[/bold blue]")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta", justify="right")

    table.add_row("Scanned files", str(summary["files"]))
    table.add_row("Supported functions", str(summary["supported_functions"]))
    table.add_row("Skipped functions", str(summary["skipped_functions"]))
    table.add_row("Generated test cases", str(summary["generated_tests"]))
    if not dry_run:
        table.add_row("Generated test files", str(summary["generated_files"]))
    table.add_row("Syntax-error files", str(summary["syntax_errors"]))

    console.print(table)


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
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run pytest immediately after generation.",
    )
    parser.add_argument(
        "--report",
        choices=["term", "html", "xml"],
        default="term",
        help="Type of coverage report to generate if --run is used.",
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

    if HAS_RICH and not args.dry_run:
        with Progress() as progress:
            task = progress.add_task("[green]Generating tests...", total=len(files))
            for file_path in files:
                result = generate_test_file(
                    file_path,
                    args.out,
                    module_path=args.module,
                    dry_run=args.dry_run,
                )
                _update_summary(summary, result, args.verbose)
                progress.update(task, advance=1)
    else:
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
            _update_summary(summary, result, args.verbose)
            if args.dry_run:
                _print_dry_run_details(result)

    _print_rich_summary(summary, args.dry_run)

    if args.run and not args.dry_run:
        _run_pytest(args.out, args.module, args.report)


def _update_summary(summary: Dict[str, Any], result: Dict[str, Any], verbose: bool) -> None:
    functions = result.get("functions", [])
    skipped_functions = result.get("skipped_functions", [])
    summary["supported_functions"] += max(0, len(functions) - len(skipped_functions))
    summary["skipped_functions"] += len(skipped_functions)
    summary["generated_tests"] += result.get("generated_tests", 0)

    if result["status"] == "syntax_error":
        summary["syntax_errors"] += 1
        return

    if result["status"] == "generated":
        summary["generated_files"] += 1


def _print_dry_run_details(result: Dict[str, Any]) -> None:
    functions = result.get("functions", [])
    for func in functions:
        name_str = f"{func['name']}({', '.join(a['name'] for a in func['args'])}) -> {func['return_type']}"
        if func.get("is_async"):
            name_str = f"async {name_str}"
        print(f"  - {name_str}")
        if func.get("unsupported_reason"):
            print(f"      unsupported: {func['unsupported_reason']}")
        else:
            print(f"      branches: {func.get('branches', [])}")
            print(
                f"      raises: {func.get('raises', False)} / unconditional_raise: {func.get('unconditional_raise', False)}"
            )


def _run_pytest(test_dir: str, module_path: str | None, report_type: str) -> None:
    if HAS_RICH:
        console.print(Panel(f"[bold green]Running pytest on {test_dir}...[/bold green]"))

    cmd = [sys.executable, "-m", "pytest", test_dir]
    if module_path:
        cmd.extend([f"--cov={module_path}"])
        if report_type == "html":
            cmd.extend(["--cov-report=html:htmlcov"])
        elif report_type == "xml":
            cmd.extend(["--cov-report=xml:coverage.xml"])
        else:
            cmd.extend(["--cov-report=term-missing"])

    try:
        subprocess.run(cmd, check=False)
        if report_type == "html":
            html_index = os.path.abspath("htmlcov/index.html")
            if os.path.exists(html_index):
                if HAS_RICH:
                    console.print(f"[bold yellow]Opening HTML report:[/bold yellow] {html_index}")
                # Using abspath directly is often more reliable on Windows
                webbrowser.open(html_index)
    except Exception as e:
        if HAS_RICH:
            console.print(f"[bold red]Error running pytest:[/bold red] {e}")
        else:
            print(f"Error running pytest: {e}")


if __name__ == "__main__":
    main()