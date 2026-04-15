#!/usr/bin/env python3
"""
Dashboard → PDF Report

Report-mode sibling of convert_dashboard.py. Reuses the extraction and
insight-generation pipeline; swaps the final PPTX deck for a PDF report.

Usage:
    python run_report.py --input "path/to/dashboard.pbix"
    python run_report.py --input "path/to/dashboard.pdf" --output "out/report.pdf"
    python run_report.py --build --input "path/to/dashboard.pbix"   # reuse existing temp/insights.json

Save-location rules:
    1. If --output is passed, use it.
    2. Else, default to   <input_dir>/<input_stem>_report.pdf
    3. If --ask-output (and a TTY is attached), prompt for an override.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Reuse the deck tool's extract + analyze trigger helpers.
from convert_dashboard import (
    _resolve_assistant,
    detect_file_type,
    prepare_for_analysis,
    show_copilot_instructions,
    trigger_claude_analysis,
)
from lib.reporting import generate_report


# ---------------------------------------------------------------------------
# Output-path logic
# ---------------------------------------------------------------------------

def default_report_path(source_path: str) -> Path:
    """Compute the default report output path next to the source input."""
    source = Path(source_path)

    if source.is_dir():
        pbip_files = list(source.glob("*.pbip"))
        stem = pbip_files[0].stem if pbip_files else source.name
        return source / f"{stem}_report.pdf"

    return source.parent / f"{source.stem}_report.pdf"


def resolve_output_path(source_path: str, output_arg: str | None, ask: bool) -> Path:
    """Apply the three-tier save-location rule."""
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
# Main
# ---------------------------------------------------------------------------

def _wait_for_insights(insights_path: str, max_wait: int = 300, interval: int = 2) -> bool:
    """Poll for the analyst to drop insights.json. Returns True when ready."""
    print("\n" + "=" * 70)
    print("Waiting for insights file...")
    print("=" * 70)

    elapsed = 0
    p = Path(insights_path)
    while elapsed < max_wait:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("slides"):
                    print(f"OK analysis complete ({elapsed}s)")
                    return True
            except (json.JSONDecodeError, KeyError):
                pass
        time.sleep(interval)
        elapsed += interval

    print(f"Warning: insights file not ready after {max_wait}s.")
    return False


def run(args: argparse.Namespace) -> int:
    # --- --build-only: skip extract + analyze, just render from existing insights.json
    if args.build:
        source_path = args.input
        if not source_path:
            try:
                req = json.loads(Path("temp/analysis_request.json").read_text(encoding="utf-8"))
                source_path = req["source_file"]
            except (OSError, json.JSONDecodeError, KeyError):
                print("Error: --build requires --input, or an existing temp/analysis_request.json")
                return 1

        output_path = resolve_output_path(source_path, args.output, args.ask_output)
        generate_report(source_path, str(output_path), insights_file=args.insights)
        return 0

    # --- Full pipeline: extract → analyze → report
    if not args.input:
        print("Error: --input is required (path to PBIX / PBIP / PDF / PPTX source).")
        return 1

    source_path = args.input
    if not Path(source_path).exists():
        print(f"Error: input does not exist: {source_path}")
        return 1

    # Validate source type early.
    try:
        source_type = detect_file_type(source_path)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    output_path = resolve_output_path(source_path, args.output, args.ask_output)

    print("\n" + "=" * 70)
    print("POWER BI -> PDF REPORT")
    print("=" * 70)
    print(f"\nSource: {source_path}   ({source_type.upper()})")
    print(f"Output: {output_path}")
    print("\nThis will run 3 steps:")
    print("  1. Extract dashboard content")
    print("  2. AI assistant analyzes pages -> temp/insights.json")
    print("  3. Render PDF report")

    assistant = _resolve_assistant(args.assistant)

    # STEP 1: Extract
    print("\n" + "=" * 70)
    print("STEP 1: EXTRACTING DASHBOARDS")
    print("=" * 70)
    request_file = prepare_for_analysis(source_path, use_text_layer=(assistant == "copilot"))

    # STEP 2: Trigger analysis
    if assistant == "copilot":
        show_copilot_instructions(request_file, context=args.context)
    else:
        trigger_claude_analysis(request_file, context=args.context)

    if not _wait_for_insights(args.insights):
        if assistant == "copilot":
            print("Run Copilot Chat to generate temp/insights.json, then re-run:")
            print(f"    python run_report.py --build --input \"{source_path}\" "
                  f"--output \"{output_path}\"")
            return 0
        print("Proceeding with whatever insights exist on disk...")

    # STEP 3: Render PDF
    print("\n" + "=" * 70)
    print("STEP 3: BUILDING REPORT")
    print("=" * 70)
    generate_report(
        source_path,
        str(output_path),
        insights_file=args.insights,
        source_type=source_type,
    )

    print("\n" + "=" * 70)
    print("OK REPORT GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nReport generated successfully: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_report.py",
        description="Generate a PDF report from a Power BI dashboard source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simplest: auto-saves <input_dir>/<input_stem>_report.pdf
  python run_report.py --input "path/to/dashboard.pbix"

  # Explicit output location:
  python run_report.py --input "path/to/dashboard.pbix" --output "out/report.pdf"

  # Prompt for save location (interactive TTY only):
  python run_report.py --input "path/to/dashboard.pbip" --ask-output

  # Render only (reuse existing temp/insights.json):
  python run_report.py --build --input "path/to/dashboard.pbix"
""",
    )
    parser.add_argument("--input", "-i", help="Path to PBIX / PBIP (file or folder) / PDF / PPTX")
    parser.add_argument("--output", "-o", help="Output PDF path (default: <input_dir>/<stem>_report.pdf)")
    parser.add_argument("--build", action="store_true",
                        help="Skip extract + analyze; render from existing temp/insights.json")
    parser.add_argument("--insights", default="temp/insights.json",
                        help="Path to insights JSON (default: temp/insights.json)")
    parser.add_argument("--ask-output", action="store_true",
                        help="Interactively prompt for save location when --output is not given")
    parser.add_argument("--context", default=None,
                        help="Optional analysis focus passed to the AI assistant")
    parser.add_argument("--assistant", default="auto", choices=["claude", "copilot", "auto"],
                        help="Which assistant to use for insights generation")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
