#!/usr/bin/env python3
"""
pbi-to-pdf — Power BI dashboards to A4 PDF reports, designed for Claude Code.

Three-stage pipeline orchestrated from a single CLI:

  1. Extract  — dump dashboard pages to temp/slide_N.png and write
                temp/analysis_request.json (PBIP/PBIX also writes
                temp/pbip_context.json for live DAX queries via MCP).
  2. Analyse  — Claude Code reads the screenshots / live model and writes
                temp/insights.json.
  3. Build    — render the polished portrait A4 PDF report.

USAGE
    # End-to-end (default):
    python run_report.py "C:/path/to/dashboard.pbix"

    # Choose the output location:
    python run_report.py "dashboard.pdf" --output "out/Q2_report.pdf"

    # Be prompted for the save location (interactive TTY only):
    python run_report.py "dashboard.pbip" --ask-output

    # Stage 1 only (extract):
    python run_report.py "dashboard.pbix" --prepare

    # Stage 3 only (re-render from existing temp/insights.json):
    python run_report.py --build --input "dashboard.pbix"

    # Stage 2.5 only (verify a hand-edited insights.json):
    python run_report.py --verify

OUTPUT
    Default save path:  <input_dir>/<input_stem>_report.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.pipeline import (
    detect_file_type,
    prepare_for_analysis,
    trigger_claude_analysis,
    verify_insights,
    wait_for_insights,
)
from lib.reporting import generate_report


# ---------------------------------------------------------------------------
# Output path resolution
# ---------------------------------------------------------------------------

def default_report_path(source_path: str) -> Path:
    """Default save path:  <input_dir>/<input_stem>_report.pdf."""
    source = Path(source_path)
    if source.is_dir():
        pbip_files = list(source.glob("*.pbip"))
        stem = pbip_files[0].stem if pbip_files else source.name
        return source / f"{stem}_report.pdf"
    return source.parent / f"{source.stem}_report.pdf"


def resolve_output_path(source_path: str, output_arg: str | None,
                        ask: bool) -> Path:
    """Apply the three-tier save-location rule.

    1. If ``--output`` was passed, use it.
    2. Else default to ``<input_dir>/<stem>_report.pdf``.
    3. If ``--ask-output`` and we have a TTY, allow the user to override.
    """
    if output_arg:
        return Path(output_arg).expanduser().resolve()

    default = default_report_path(source_path).resolve()

    if ask and sys.stdin.isatty():
        try:
            reply = input(
                f"Where should I save the report?\n"
                f"  [Enter] = {default}\n"
                f"  (or type an absolute path): "
            ).strip()
        except EOFError:
            reply = ""
        if reply:
            return Path(reply).expanduser().resolve()

    return default


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def _run_prepare(input_path: str, context: str | None,
                 capture_ui: bool) -> int:
    if not Path(input_path).exists():
        print(f"Error: input does not exist: {input_path}")
        return 1
    request_file = prepare_for_analysis(input_path, capture_ui=capture_ui)
    trigger_claude_analysis(request_file, context=context)
    print("\nNext: have Claude Code generate temp/insights.json, then run:")
    print(f"    python run_report.py --build --input \"{input_path}\"")
    return 0


def _run_build(input_path: str | None, output_arg: str | None,
               ask_output: bool, insights_file: str) -> int:
    # Resolve the source from the request file when not explicitly given.
    if not input_path:
        try:
            req = json.loads(Path("temp/analysis_request.json").read_text(encoding="utf-8"))
            input_path = req["source_file"]
        except (OSError, json.JSONDecodeError, KeyError):
            print("Error: --build requires --input, or an existing temp/analysis_request.json")
            return 1

    result = verify_insights(insights_file)
    if not result["passed"]:
        print("\nBuild aborted — fix the errors above before rebuilding.")
        return 1

    output_path = resolve_output_path(input_path, output_arg, ask_output)
    generate_report(input_path, str(output_path), insights_file=insights_file)
    print(f"\nOK Report written: {output_path}")
    return 0


def _run_full(input_path: str, output_arg: str | None, ask_output: bool,
              insights_file: str, context: str | None,
              capture_ui: bool) -> int:
    if not Path(input_path).exists():
        print(f"Error: input does not exist: {input_path}")
        return 1

    try:
        source_type = detect_file_type(input_path)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    output_path = resolve_output_path(input_path, output_arg, ask_output)

    print("\n" + "=" * 70)
    print("POWER BI -> PDF REPORT")
    print("=" * 70)
    print(f"\nSource: {input_path}   ({source_type.upper()})")
    print(f"Output: {output_path}")
    print("\nStages:")
    print("  1. Extract dashboard content")
    print("  2. Claude Code analyses pages -> temp/insights.json")
    print("  3. Render A4 PDF report")

    print("\n" + "=" * 70)
    print("STAGE 1: EXTRACT")
    print("=" * 70)
    request_file = prepare_for_analysis(input_path, capture_ui=capture_ui)

    trigger_claude_analysis(request_file, context=context)

    if not wait_for_insights(insights_file):
        print("\nNo insights file appeared. To finish later, run:")
        print(f"    python run_report.py --build --input \"{input_path}\"")
        return 0

    result = verify_insights(insights_file)
    if not result["passed"]:
        print("\nBuild aborted — fix the errors above and re-run with --build.")
        return 1

    print("\n" + "=" * 70)
    print("STAGE 3: BUILD PDF")
    print("=" * 70)
    generate_report(input_path, str(output_path),
                    insights_file=insights_file, source_type=source_type)
    print(f"\nOK Report ready: {output_path}")
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_report.py",
        description=(
            "pbi-to-pdf — Power BI dashboards to A4 PDF reports, designed "
            "for Claude Code."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
  # End-to-end (auto-saves <input_dir>/<input_stem>_report.pdf):
  python run_report.py "C:/path/to/dashboard.pbix"

  # Choose output location:
  python run_report.py "dashboard.pdf" --output "out/Q2_report.pdf"

  # Stage 1 only (extract dashboards, print analysis prompt):
  python run_report.py "dashboard.pbix" --prepare

  # Stage 3 only (re-render from existing temp/insights.json):
  python run_report.py --build --input "dashboard.pbix"

  # Verify a hand-edited insights.json:
  python run_report.py --verify
""",
    )
    parser.add_argument("input", nargs="?",
                        help="Path to PBIX, PBIP (file or folder), PDF, or PPTX source")
    parser.add_argument("--input", "-i", dest="input_flag",
                        help=argparse.SUPPRESS)  # alternate -i/--input form
    parser.add_argument("--output", "-o",
                        help="Output PDF path (default: <input_dir>/<stem>_report.pdf)")
    parser.add_argument("--ask-output", action="store_true",
                        help="Prompt for save location when --output is not given")
    parser.add_argument("--prepare", action="store_true",
                        help="Stage 1 only — extract dashboards and print Claude prompt")
    parser.add_argument("--build", action="store_true",
                        help="Stage 3 only — render PDF from existing temp/insights.json")
    parser.add_argument("--verify", action="store_true",
                        help="Verify temp/insights.json without rendering anything")
    parser.add_argument("--insights", default="temp/insights.json",
                        help="Path to insights JSON (default: temp/insights.json)")
    parser.add_argument("--context", default=None,
                        help="Optional analysis focus passed into Claude's prompt "
                             "(e.g. 'spotlight Finance' or 'frame for the CISO')")
    parser.add_argument("--capture-ui", action="store_true",
                        help="PBIP/PBIX only: allow the extractor to drive Power BI "
                             "Desktop via UI automation (keystrokes, focus stealing) "
                             "to grab live screenshots. Default off — the safe "
                             "fallback is to use any companion .pdf/.pptx export "
                             "already on disk.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Resolve positional vs --input flag (--input wins when both are given)
    input_path = args.input_flag or args.input

    if args.verify:
        result = verify_insights(args.insights)
        return 0 if result["passed"] else 1

    if args.prepare:
        if not input_path:
            print("Error: --prepare requires an input path.")
            return 1
        return _run_prepare(input_path, context=args.context,
                            capture_ui=args.capture_ui)

    if args.build:
        return _run_build(input_path, args.output, args.ask_output, args.insights)

    if not input_path:
        parser.print_help()
        return 1

    return _run_full(input_path, args.output, args.ask_output,
                     args.insights, context=args.context,
                     capture_ui=args.capture_ui)


if __name__ == "__main__":
    sys.exit(main())
