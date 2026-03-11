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
    parser.add_argument(
        "--test-report",
        action="store_true",
        help="Generate a detailed HTML report of all test cases results.",
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
        _run_pytest(args.out, args.module, args.report, args.input, args.test_report)


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


import json
from datetime import datetime


def _generate_test_dashboard(json_path: str, output_path: str) -> None:
    try:
        if not os.path.exists(json_path):
            return
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Group tests by file
        files_map = {}
        for test in data.get('tests', []):
            nodeid = test.get('nodeid', '')
            file_name = nodeid.split('::')[0]
            if file_name not in files_map:
                files_map[file_name] = {'tests': [], 'passed': 0, 'failed': 0, 'total': 0}
            
            files_map[file_name]['tests'].append(test)
            files_map[file_name]['total'] += 1
            if test.get('outcome') == 'passed':
                files_map[file_name]['passed'] += 1
            else:
                files_map[file_name]['failed'] += 1

        summary = data.get('summary', {})
        total_passed = summary.get('passed', 0)
        total_failed = summary.get('failed', 0)
        total_tests = summary.get('total', 0)
        duration = round(data.get('duration', 0), 2)
        
        # Simple, Clean HTML Template
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Generation Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f4f4f7; color: #333; margin: 0; padding: 40px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        h1 {{ margin: 0 0 10px 0; color: #1a1a1a; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 30px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid #eee; }}
        .stat-box {{ flex: 1; padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center; }}
        .stat-label {{ font-size: 12px; text-transform: uppercase; color: #888; margin-bottom: 5px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; }}
        .file-group {{ border: 1px solid #eee; border-radius: 6px; margin-bottom: 10px; overflow: hidden; }}
        .file-header {{ background: #fff; padding: 15px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }}
        .file-header:hover {{ background: #fcfcfc; }}
        .file-name {{ font-weight: 600; color: #2c3e50; }}
        .file-stats {{ font-size: 12px; }}
        .badge {{ padding: 2px 8px; border-radius: 12px; font-weight: 600; text-transform: uppercase; }}
        .pass {{ border: 1px solid #28a745; color: #28a745; background: #e8f5e9; }}
        .fail {{ border: 1px solid #dc3545; color: #dc3545; background: #fdeaea; }}
        .details {{ display: none; padding: 20px; background: #fafafa; border-top: 1px solid #eee; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; font-size: 12px; color: #999; padding-bottom: 10px; text-transform: uppercase; }}
        td {{ padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
        code {{ background: #eee; padding: 2px 4px; border-radius: 3px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Test Generation Report</h1>
        <p class="meta">Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="stats">
            <div class="stat-box"><div class="stat-label">Total Tests</div><div class="stat-value">{total_tests}</div></div>
            <div class="stat-box"><div class="stat-label">Passed</div><div class="stat-value" style="color: #28a745">{total_passed}</div></div>
            <div class="stat-box"><div class="stat-label">Failed</div><div class="stat-value" style="color: #dc3545">{total_failed}</div></div>
            <div class="stat-box"><div class="stat-label">Duration</div><div class="stat-value">{duration}s</div></div>
        </div>

        {"".join([f'''
        <div class="file-group">
            <div class="file-header" onclick="toggle('{i}')">
                <span class="file-name">{fname.split('/')[-1].split('\\')[-1]}</span>
                <div class="file-stats">
                    <span class="badge pass">{fmeta['passed']} Passed</span>
                    {f'<span class="badge fail">{fmeta["failed"]} Failed</span>' if fmeta['failed'] > 0 else ''}
                </div>
            </div>
            <div class="details" id="details-{i}">
                <table>
                    <thead>
                        <tr><th>Test Case (Parameters)</th><th style="text-align:right">Time</th><th style="text-align:right">Result</th></tr>
                    </thead>
                    <tbody>
                        {"".join([f'''
                        <tr>
                            <td><code>{t.get('nodeid', '').split('::')[-1]}</code></td>
                            <td style="text-align:right">{round(t.get('duration', 0)*1000, 1)}ms</td>
                            <td style="text-align:right">
                                <span class="badge {'pass' if t.get('outcome') == 'passed' else 'fail'}" style="font-size: 10px">
                                    {t.get('outcome')}
                                </span>
                            </td>
                        </tr>
                        ''' for t in fmeta['tests']])}
                    </tbody>
                </table>
            </div>
        </div>
        ''' for i, (fname, fmeta) in enumerate(files_map.items())])}
    </div>

    <script>
        function toggle(id) {{
            var el = document.getElementById('details-' + id);
            el.style.display = (el.style.display === 'block') ? 'none' : 'block';
        }}
    </script>
</body>
</html>
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        print(f"Error generating report: {e}")


def _run_pytest(test_dir: str, module_path: str | None, report_type: str, input_path: str, test_report: bool = False) -> None:
    if HAS_RICH:
        console.print(Panel(f"[bold green]Running pytest on {test_dir}...[/bold green]"))

    json_report = "report_data.json"
    cmd = [sys.executable, "-m", "pytest", test_dir, f"--json-report", f"--json-report-file={json_report}"]
    
    if module_path:
        cmd.extend([f"--cov={module_path}"])
        if report_type == "html":
            cmd.extend(["--cov-report=html:htmlcov"])
        elif report_type == "xml":
            cmd.extend(["--cov-report=xml:coverage.xml"])
        else:
            cmd.extend(["--cov-report=term-missing"])

    # Automatically add input directory to PYTHONPATH so pytest can find the modules
    env = os.environ.copy()
    current_pp = env.get("PYTHONPATH", "")
    additional_path = os.path.abspath(input_path if os.path.isdir(input_path) else os.path.dirname(input_path))
    env["PYTHONPATH"] = f"{additional_path}{os.pathsep}{current_pp}" if current_pp else additional_path

    try:
        subprocess.run(cmd, check=False, env=env)
        
        # Simple Report Generation
        dashboard_path = os.path.abspath("test_dashboard.html")
        _generate_test_dashboard(json_report, dashboard_path)
        
        if HAS_RICH:
            console.print(f"[bold cyan]Report generated:[/bold cyan] {dashboard_path}")
        
        webbrowser.open(dashboard_path)

        # Opening other reports if requested
        if report_type == "html":
            html_index = os.path.abspath("htmlcov/index.html")
            if os.path.exists(html_index):
                webbrowser.open(html_index)
        
        if test_report:
            # We already have data, but if users want the old report format:
            cmd_html = [sys.executable, "-m", "pytest", test_dir, "--html=test_report.html", "--self-contained-html"]
            subprocess.run(cmd_html, check=False, env=env)
            webbrowser.open(os.path.abspath("test_report.html"))
                
    except Exception as e:
        if HAS_RICH:
            console.print(f"[bold red]Error running pytest:[/bold red] {e}")
        else:
            print(f"Error running pytest: {e}")


if __name__ == "__main__":
    main()