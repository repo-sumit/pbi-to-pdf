"""
Report schema — adapts insights.json into a normalized report structure.

The canonical analyst output is ``temp/insights.json``. This module reads
that JSON plus ``temp/analysis_request.json`` and exposes an in-memory
structure the PDF renderer (``lib.reporting.components``) consumes:

    ReportData
      ├── metadata        (source, timestamps, type)
      ├── title/subtitle  (from insights deck_title/deck_subtitle)
      ├── cover_kpis      [ChartSpec]   — optional, top-of-report KPI strip
      ├── executive_summary [str]
      ├── recommendations   [Recommendation]   — text + optional priority
      ├── sections [ReportSection]
      │     ├── title, headline
      │     ├── screenshot_path
      │     ├── kpis   (chart.type ∈ {kpi, kpi_row})
      │     ├── tables (chart.type == table)
      │     ├── charts (everything else)
      │     └── bullets (text bullets, bold || detail split)
      └── numbers_used (per section, surfaced in the appendix)

No new JSON file is written — insights.json stays canonical. Report
metadata (generated_at, input_path, source_type) is captured at runtime.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.analysis.insights import (
    BulletPoint,
    ChartSpec,
    parse_bullet_points,
    parse_chart_spec,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ReportMetadata:
    source_name: str
    source_type: str        # "pptx" | "pdf" | "pbip" | "pbix"
    input_path: str
    generated_at: str       # ISO 8601


@dataclass
class ReportBullet:
    bold: str               # "Bold line 6-8 words"
    detail: str             # "Supporting evidence with data"

    @classmethod
    def from_text(cls, text: str) -> "ReportBullet":
        """Split on '||' separator used in insights.json insight text."""
        if "||" in text:
            bold, _, detail = text.partition("||")
            return cls(bold=bold.strip(), detail=detail.strip())
        # Fall back to splitting on the first em-dash / arrow / colon when
        # the analyst forgot the '||' separator.
        for sep in ("→", "->", "—", " - ", ": "):
            if sep in text:
                head, _, tail = text.partition(sep)
                head, tail = head.strip(), tail.strip()
                if head and tail:
                    return cls(bold=head, detail=tail)
        return cls(bold=text.strip(), detail="")


@dataclass
class Recommendation:
    text: str
    priority: Optional[str] = None   # "High" | "Medium" | "Low" | "Critical" | None

    @classmethod
    def from_text(cls, text: str) -> "Recommendation":
        """Parse optional priority prefix from a recommendation string.

        Supported forms (case-insensitive):
          "[High] do the thing"
          "(Priority: Medium) do the thing"
          "High: do the thing"
          "do the thing"   (no priority)
        """
        if not text:
            return cls(text="")

        patterns = [
            re.compile(r"^\[\s*(?P<p>critical|high|medium|low)\s*\]\s*(?P<rest>.+)$", re.I),
            re.compile(r"^\(\s*(?:priority\s*[:\-]\s*)?(?P<p>critical|high|medium|low)\s*\)\s*(?P<rest>.+)$", re.I),
            re.compile(r"^(?P<p>critical|high|medium|low)\s*[:\-]\s*(?P<rest>.+)$", re.I),
        ]
        for pat in patterns:
            m = pat.match(text)
            if m:
                return cls(text=m.group("rest").strip(),
                           priority=m.group("p").strip().capitalize())
        return cls(text=text.strip(), priority=None)


@dataclass
class ReportSection:
    slide_number: int
    title: str
    headline: str
    screenshot_path: Optional[str]       # absolute or repo-relative path, or None
    bullets: List[ReportBullet] = field(default_factory=list)
    kpis: List[ChartSpec] = field(default_factory=list)    # type in {kpi, kpi_row}
    tables: List[ChartSpec] = field(default_factory=list)  # type == table
    charts: List[ChartSpec] = field(default_factory=list)  # everything else
    numbers_used: List[str] = field(default_factory=list)


@dataclass
class ReportData:
    metadata: ReportMetadata
    title: str
    subtitle: str
    executive_summary: List[str]
    recommendations: List[Recommendation]
    sections: List[ReportSection]
    cover_kpis: List[ChartSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

_KPI_TYPES = {"kpi", "kpi_row", "card", "multi_row_card"}
_TABLE_TYPES = {"table"}


def _classify_chart(spec: ChartSpec) -> str:
    t = (spec.type or "").lower().strip()
    if t in _KPI_TYPES:
        return "kpi"
    if t in _TABLE_TYPES:
        return "table"
    return "chart"


def _split_bullet_visuals(
    points: List[BulletPoint],
) -> Tuple[List[ReportBullet], List[ChartSpec], List[ChartSpec], List[ChartSpec]]:
    """Return (text_bullets, kpis, tables, other_charts)."""
    bullets: List[ReportBullet] = []
    kpis: List[ChartSpec] = []
    tables: List[ChartSpec] = []
    charts: List[ChartSpec] = []

    for bp in points:
        if bp.text:
            bullets.append(ReportBullet.from_text(bp.text))
        if bp.chart is not None:
            bucket = _classify_chart(bp.chart)
            if bucket == "kpi":
                kpis.append(bp.chart)
            elif bucket == "table":
                tables.append(bp.chart)
            else:
                charts.append(bp.chart)

    return bullets, kpis, tables, charts


def _load_slide_image_map(analysis_request_path: Path) -> Dict[int, Optional[str]]:
    """Map slide_number → image_path from analysis_request.json. Missing file → empty."""
    if not analysis_request_path.exists():
        return {}
    try:
        req = json.loads(analysis_request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    mapping: Dict[int, Optional[str]] = {}
    for slide in req.get("slides", []):
        num = slide.get("slide_number")
        if isinstance(num, int):
            mapping[num] = slide.get("image_path")
    return mapping


def _resolve_image(image_path: Optional[str], temp_dir: Path) -> Optional[str]:
    """Return an existing path for the slide image, or None."""
    if not image_path:
        return None
    p = Path(image_path)
    if p.is_absolute() and p.exists():
        return str(p)
    # insights pipeline stores paths like "temp/slide_2.png" relative to repo root
    candidate = Path.cwd() / p
    if candidate.exists():
        return str(candidate)
    # Also try resolving relative to temp_dir's parent
    candidate2 = temp_dir.parent / p
    if candidate2.exists():
        return str(candidate2)
    return None


def build_report_data(
    insights_data: Dict[str, Any],
    *,
    source_path: str,
    source_type: str,
    analysis_request_path: str = "temp/analysis_request.json",
    temp_dir: str = "temp",
) -> ReportData:
    """Adapt insights.json dict → ReportData.

    Args:
        insights_data: Parsed contents of temp/insights.json.
        source_path:   Path the user supplied on the CLI.
        source_type:   One of 'pptx', 'pdf', 'pbip', 'pbix'.
        analysis_request_path: Location of analysis_request.json (for image paths).
        temp_dir:      Temp working directory.
    """
    temp_dir_path = Path(temp_dir)
    image_map = _load_slide_image_map(Path(analysis_request_path))

    source = Path(source_path)
    metadata = ReportMetadata(
        source_name=source.name or source_path,
        source_type=source_type,
        input_path=str(source.resolve()) if source.exists() else source_path,
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )

    sections: List[ReportSection] = []
    for raw in insights_data.get("slides", []):
        slide_num = raw.get("slide_number")
        if not isinstance(slide_num, int):
            # Skip malformed entries — renderer should never see them.
            continue

        bullet_points = parse_bullet_points(raw.get("insights", []))
        bullets, kpis, tables, charts = _split_bullet_visuals(bullet_points)

        image_path = _resolve_image(image_map.get(slide_num), temp_dir_path)

        sections.append(
            ReportSection(
                slide_number=slide_num,
                title=raw.get("title", f"Page {slide_num}"),
                headline=raw.get("headline", ""),
                screenshot_path=image_path,
                bullets=bullets,
                kpis=kpis,
                tables=tables,
                charts=charts,
                numbers_used=list(raw.get("numbers_used", [])),
            )
        )

    sections.sort(key=lambda s: s.slide_number)

    # Cover KPI strip — explicit if provided, else auto-derive from the
    # first section's KPI specs (if any).
    cover_kpis: List[ChartSpec] = []
    raw_cover = insights_data.get("cover_kpis")
    if raw_cover:
        for raw in raw_cover:
            spec = parse_chart_spec(raw) if isinstance(raw, dict) else None
            if spec is not None:
                cover_kpis.append(spec)
    else:
        for section in sections:
            if section.kpis:
                cover_kpis = list(section.kpis)
                break

    recommendations = [
        Recommendation.from_text(str(r))
        for r in insights_data.get("recommendations", [])
        if r
    ]

    return ReportData(
        metadata=metadata,
        title=insights_data.get("deck_title") or "Dashboard Report",
        subtitle=insights_data.get("deck_subtitle") or "",
        executive_summary=list(insights_data.get("executive_summary", [])),
        recommendations=recommendations,
        sections=sections,
        cover_kpis=cover_kpis,
    )
