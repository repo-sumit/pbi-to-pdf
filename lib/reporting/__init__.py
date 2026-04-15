"""Report-generation package. Sibling to lib.rendering (deck path)."""

from lib.reporting.report_generator import generate_report
from lib.reporting.report_schema import (
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
]
