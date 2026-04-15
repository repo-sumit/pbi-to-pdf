"""
Top-level orchestrator that turns insights.json into a PDF report.

Loads the canonical analyst output (``temp/insights.json``), adapts it
to ``ReportData`` via :mod:`lib.reporting.report_schema`, and renders
the final A4 PDF via :mod:`lib.reporting.pdf_builder`. Used as Stage 3
of the pipeline orchestrated from ``run_report.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from lib.reporting.pdf_builder import render_report_pdf
from lib.reporting.report_schema import build_report_data


def generate_report(
    source_path: str,
    output_path: str,
    insights_file: str = "temp/insights.json",
    *,
    source_type: Optional[str] = None,
    analysis_request_path: str = "temp/analysis_request.json",
) -> str:
    """Load insights.json, adapt to ReportData, render PDF.

    Args:
        source_path: Path the user supplied (PBIX/PBIP/PDF/PPTX).
        output_path: Where to write the PDF.
        insights_file: Canonical analyst output. Defaults to temp/insights.json.
        source_type: Optional override; if None, inferred from source_path extension.
        analysis_request_path: Used to resolve per-slide screenshot paths.

    Returns:
        The absolute output path written.
    """
    insights_path = Path(insights_file)
    if not insights_path.exists():
        raise FileNotFoundError(
            f"Insights file not found: {insights_file}. "
            "Run the extract + analyze steps first."
        )

    with insights_path.open("r", encoding="utf-8") as f:
        insights_data = json.load(f)

    if not insights_data.get("slides"):
        raise ValueError(
            f"{insights_file} contains no slides — analyst step did not complete."
        )

    resolved_type = source_type or _infer_source_type(source_path)

    print("\n" + "=" * 70)
    print("BUILDING PDF REPORT")
    print("=" * 70)
    print(f"\nOK Loaded insights for {len(insights_data['slides'])} slides")

    report = build_report_data(
        insights_data,
        source_path=source_path,
        source_type=resolved_type,
        analysis_request_path=analysis_request_path,
    )

    written = render_report_pdf(report, output_path)
    print(f"\nOK Report generated successfully: {written}")
    return written


def _infer_source_type(source_path: str) -> str:
    p = Path(source_path)
    suffix = p.suffix.lower()
    if suffix == ".pptx":
        return "pptx"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".pbix":
        return "pbix"
    if suffix == ".pbip" or (p.is_dir() and any(p.glob("*.pbip"))):
        return "pbip"
    return "unknown"
