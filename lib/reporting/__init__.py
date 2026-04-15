"""PDF report generation package — primary output of pbi-to-pdf."""

from lib.reporting.report_generator import generate_report
from lib.reporting.report_schema import (
    Recommendation,
    ReportBullet,
    ReportData,
    ReportMetadata,
    ReportSection,
    build_report_data,
)

__all__ = [
    "generate_report",
    "build_report_data",
    "ReportData",
    "ReportMetadata",
    "ReportSection",
    "ReportBullet",
    "Recommendation",
]
