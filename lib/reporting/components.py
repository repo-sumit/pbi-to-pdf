"""
Reusable component renderers for the A4 PDF report.

Every component takes the data structures from ``lib.reporting.report_schema``
and returns a list of ReportLab Flowables. Components share styling
through ``lib.reporting.theme`` — never hardcode colors / sizes inline.

Public API
----------
- render_cover_page(report, styles)
- render_executive_summary(report, styles)
- render_section(section, styles)
- render_appendix(report, styles)
- render_kpi_strip(specs, styles)
- render_insight_card(bullet, styles)
- render_recommendation_card(rec, styles)
- render_table(spec, styles)
- render_chart(spec, styles)
- render_callout(text, severity, styles, title=None)
- render_section_header(eyebrow, title, headline, styles)
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    Image,
    KeepInFrame,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from lib.analysis.insights import ChartSpec
from lib.reporting import theme as t
from lib.reporting.charts import render_chart_to_png
from lib.reporting.report_schema import (
    Recommendation,
    ReportBullet,
    ReportData,
    ReportSection,
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _escape(s: str) -> str:
    """Escape ReportLab Paragraph markup characters."""
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _hex(color: colors.Color) -> str:
    """Return a ReportLab-compatible '#rrggbb' string for a Color."""
    raw = color.hexval()           # "0xRRGGBB"
    return "#" + raw[2:]


def _format_timestamp(iso_ts: str) -> str:
    if not iso_ts:
        return ""
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return iso_ts
    return dt.strftime("%d %b %Y · %H:%M")


def _hairline_rule(width: float = t.CONTENT_WIDTH,
                   color: colors.Color = t.DIVIDER,
                   stroke: float = t.HAIRLINE) -> Table:
    """Single thin horizontal rule, used as a section divider."""
    rule = Table([[""]], colWidths=[width], rowHeights=[stroke])
    rule.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LINEBELOW", (0, 0), (-1, -1), 0, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return rule


def _fit_image_pt(path: str, max_w_pt: float, max_h_pt: float) -> Optional[Image]:
    """Load PNG/JPG and scale into the box, preserving aspect ratio."""
    try:
        with PILImage.open(path) as im:
            w, h = im.size
    except (OSError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    scale = min(max_w_pt / w, max_h_pt / h)
    return Image(path, width=w * scale, height=h * scale)


# ---------------------------------------------------------------------------
# Cover page
# ---------------------------------------------------------------------------

def render_cover_page(report: ReportData, styles: dict) -> List:
    """Premium cover: eyebrow, large title, subtitle, accent rule, metadata."""
    out: List = [
        Spacer(1, 90),
        Paragraph("EXECUTIVE REPORT", styles["section_eyebrow"]),
        Spacer(1, t.SPACE_M),
        Paragraph(_escape(report.title or "Dashboard Report"), styles["cover_title"]),
    ]
    if report.subtitle:
        out.append(Paragraph(_escape(report.subtitle), styles["cover_subtitle"]))

    # Slim accent rule
    rule = Table([[""]], colWidths=[60], rowHeights=[2.5])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), t.PRIMARY)]))
    out.append(rule)
    out.append(Spacer(1, t.SPACE_XL))

    # Optional cover KPI strip
    if report.cover_kpis:
        kpi = render_kpi_strip(report.cover_kpis, styles)
        if kpi:
            out.extend(kpi)
            out.append(Spacer(1, t.SPACE_XL))

    # Metadata block — quiet, structured, two columns
    meta = report.metadata
    meta_rows = [
        ("Source",      meta.source_name),
        ("Type",        meta.source_type.upper()),
        ("Generated",   _format_timestamp(meta.generated_at)),
        ("Sections",    str(len(report.sections))),
    ]
    meta_table = Table(
        [[Paragraph(label, styles["cover_meta_label"]),
          Paragraph(_escape(value), styles["cover_meta"])]
         for label, value in meta_rows],
        colWidths=[80, t.CONTENT_WIDTH - 80],
        hAlign="LEFT",
    )
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), t.HAIRLINE, t.DIVIDER),
    ]))
    out.append(meta_table)
    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------

def _format_value(v: object) -> str:
    """Render KPI / cell values without spurious trailing zeros.

    Floats whose fractional part is 0 collapse to the integer form
    (4381.0 -> '4,381'). Numbers >= 1000 get thousands separators.
    Everything else is passed through as-is.
    """
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if v.is_integer():
            return f"{int(v):,}"
        # Trim to at most 2 decimals, drop trailing zeros
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def _kpi_items_from_specs(specs: Iterable[ChartSpec]) -> List[dict]:
    items: List[dict] = []
    for spec in specs:
        t_ = (spec.type or "").lower().strip()
        if t_ in ("kpi", "card"):
            items.append({"value": _format_value(spec.value),
                          "label": spec.label,
                          "subtitle": spec.subtitle})
        elif t_ in ("kpi_row", "multi_row_card"):
            if spec.data:
                for dp in spec.data:
                    items.append({"value": _format_value(dp.value),
                                  "label": dp.label, "subtitle": ""})
            elif spec.series:
                for itm in spec.series:
                    if isinstance(itm, dict):
                        items.append({"value": _format_value(itm.get("value", "")),
                                      "label": itm.get("label", ""),
                                      "subtitle": itm.get("subtitle", "")})
    return items


def render_kpi_strip(specs: List[ChartSpec], styles: dict,
                     max_per_row: int = 4) -> List[Flowable]:
    """Render KPI cards in a horizontal strip. Wraps into multiple rows."""
    items = _kpi_items_from_specs(specs)
    if not items:
        return []

    rows = [items[i:i + max_per_row] for i in range(0, len(items), max_per_row)]
    flowables: List[Flowable] = []

    for row in rows:
        n = len(row)
        col_w = t.CONTENT_WIDTH / n
        cells = []
        for itm in row:
            parts: List = [
                Paragraph(_escape(str(itm["value"] or "—")), styles["kpi_value"]),
                Paragraph(_escape(itm["label"] or ""), styles["kpi_label"]),
            ]
            if itm.get("subtitle"):
                parts.append(Paragraph(_escape(itm["subtitle"]), styles["kpi_sub"]))
            cells.append(parts)

        tbl = Table([cells], colWidths=[col_w] * n, hAlign="LEFT")
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), t.SURFACE_ALT),
            ("BOX", (0, 0), (-1, -1), t.HAIRLINE, t.DIVIDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), t.SPACE_M),
            ("BOTTOMPADDING", (0, 0), (-1, -1), t.SPACE_M),
            ("LEFTPADDING", (0, 0), (-1, -1), t.SPACE_S),
            ("RIGHTPADDING", (0, 0), (-1, -1), t.SPACE_S),
        ])
        # Vertical hairline separators between cards
        for i in range(1, n):
            style.add("LINEBEFORE", (i, 0), (i, -1), t.HAIRLINE, t.DIVIDER)
        tbl.setStyle(style)
        flowables.append(tbl)
        flowables.append(Spacer(1, t.SPACE_S))

    return flowables


# ---------------------------------------------------------------------------
# Insight & recommendation cards
# ---------------------------------------------------------------------------

def _accent_card(content: List[Flowable], accent_color: colors.Color,
                 background: colors.Color = t.SURFACE_ALT) -> Table:
    """A card with a left accent bar — used for insights, recommendations, callouts."""
    inner = Table([[content]], colWidths=[t.CONTENT_WIDTH - t.ACCENT_BAR - t.SPACE_M])
    inner.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    card = Table(
        [[Spacer(t.ACCENT_BAR, 1), inner]],
        colWidths=[t.ACCENT_BAR, t.CONTENT_WIDTH - t.ACCENT_BAR],
    )
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), accent_color),  # left accent bar
        ("BACKGROUND", (1, 0), (1, -1), background),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("TOPPADDING", (0, 0), (0, -1), 0),
        ("BOTTOMPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), t.SPACE_M),
        ("RIGHTPADDING", (1, 0), (1, -1), t.SPACE_M),
        ("TOPPADDING", (1, 0), (1, -1), t.SPACE_S),
        ("BOTTOMPADDING", (1, 0), (1, -1), t.SPACE_S),
    ]))
    return card


def render_insight_card(bullet: ReportBullet, styles: dict,
                        accent: colors.Color = t.ACCENT) -> Flowable:
    """Render one insight as a left-accent card (bold heading + detail)."""
    content: List[Flowable] = []
    if bullet.bold:
        content.append(Paragraph(_escape(bullet.bold), styles["bullet_bold"]))
    if bullet.detail:
        content.append(Paragraph(_escape(bullet.detail), styles["bullet_detail"]))
    if not content:
        content.append(Paragraph("&nbsp;", styles["body"]))
    return _accent_card(content, accent_color=accent)


def render_recommendation_card(rec: Recommendation, styles: dict,
                               number: Optional[int] = None) -> Flowable:
    """Render one recommendation as a card with priority tag + body."""
    accent = t.severity_color(rec.priority)

    header_parts: List[str] = []
    if number is not None:
        header_parts.append(
            f"<font color='{_hex(t.TEXT_MUTED)}'>{number:02d}</font>"
        )
    if rec.priority:
        header_parts.append(
            f"<font color='{_hex(accent)}'><b>{rec.priority.upper()}</b></font>"
        )
    header_html = "  ·  ".join(header_parts) if header_parts else ""

    content: List[Flowable] = []
    if header_html:
        content.append(Paragraph(header_html, styles["tag"]))
    content.append(Paragraph(_escape(rec.text), styles["card_body"]))
    return _accent_card(content, accent_color=accent)


# ---------------------------------------------------------------------------
# Callout
# ---------------------------------------------------------------------------

def render_callout(text: str, severity: str, styles: dict,
                   title: Optional[str] = None) -> Flowable:
    """Generic callout box with severity-coloured left border."""
    accent = t.severity_color(severity)
    content: List[Flowable] = []
    if title:
        tag = severity.upper() if severity else "NOTE"
        content.append(Paragraph(
            f"<font color='{_hex(accent)}'><b>{tag}</b></font>",
            styles["tag"],
        ))
        content.append(Paragraph(_escape(title), styles["callout_title"]))
    content.append(Paragraph(_escape(text), styles["callout_body"]))
    return _accent_card(content, accent_color=accent, background=t.SURFACE_ALT)


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

def render_executive_summary(report: ReportData, styles: dict) -> List:
    """Scan-first summary page: KPIs, top insights, top recommendations."""
    out: List = [
        Paragraph("Executive Summary", styles["section_title"]),
        _hairline_rule(),
        Spacer(1, t.SPACE_M),
    ]
    # Note: the cover page already shows the KPI strip; we don't repeat it
    # here to keep this page scan-first (findings + actions only).

    # Insights (top 5)
    if report.executive_summary:
        out.append(Paragraph("Key Findings", styles["subheading"]))
        for line in report.executive_summary[:5]:
            bullet = ReportBullet.from_text(line)
            out.append(render_insight_card(bullet, styles, accent=t.ACCENT))
            out.append(Spacer(1, t.SPACE_S))

    # Recommendations (top 5)
    if report.recommendations:
        out.append(Spacer(1, t.SPACE_M))
        out.append(Paragraph("Recommended Actions", styles["subheading"]))
        for idx, rec in enumerate(report.recommendations[:5], start=1):
            out.append(render_recommendation_card(rec, styles, number=idx))
            out.append(Spacer(1, t.SPACE_S))

    out.append(PageBreak())
    return out


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------

def render_section_header(eyebrow: str, title: str, headline: str,
                          styles: dict) -> List[Flowable]:
    """Eyebrow ('PAGE 03') + section title + supporting headline + divider."""
    parts: List[Flowable] = [
        Paragraph(_escape(eyebrow.upper()), styles["section_eyebrow"]),
        Paragraph(_escape(title), styles["section_title"]),
    ]
    if headline:
        parts.append(Paragraph(_escape(headline), styles["headline"]))
    parts.append(_hairline_rule())
    parts.append(Spacer(1, t.SPACE_M))
    return [KeepTogether(parts)]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"^\s*[-+]?\d[\d,\.]*\s*[%KMB]?\s*$", re.I)


def _is_numeric(cell: object) -> bool:
    if cell is None:
        return False
    return bool(_NUMBER_RE.match(str(cell)))


def render_table(spec: ChartSpec, styles: dict) -> Optional[Flowable]:
    """Publication-quality table: subtle header, zebra stripes, right-aligned numbers."""
    cols = spec.table_columns or []
    rows = spec.table_rows or []
    if not cols or not rows:
        return None

    header = [Paragraph(_escape(str(c)), styles["table_header"]) for c in cols]

    # Decide alignment per column from the first data row
    first_row = rows[0]
    numeric_cols = [
        i for i, val in enumerate(first_row) if _is_numeric(val)
    ]

    body_rows: List[List] = []
    for r in rows:
        cells: List = []
        for i, val in enumerate(r):
            txt = "" if val is None else str(val)
            style = styles["table_body_num"] if i in numeric_cols else styles["table_body"]
            cells.append(Paragraph(_escape(txt), style))
        body_rows.append(cells)

    data = [header] + body_rows
    col_w = t.CONTENT_WIDTH / max(len(cols), 1)
    tbl = Table(data, colWidths=[col_w] * len(cols), hAlign="LEFT", repeatRows=1)

    style = TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), t.SURFACE_ALT),
        ("LINEBELOW", (0, 0), (-1, 0), t.THIN, t.DIVIDER_STRONG),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        # Body — light row separators only, no vertical lines
        ("LINEBELOW", (0, 1), (-1, -1), t.HAIRLINE, t.DIVIDER),
        # Zebra striping
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [t.SURFACE, t.SURFACE_SUBTLE]),
    ])

    if 0 <= spec.highlight_col < len(cols):
        col = spec.highlight_col
        style.add("BACKGROUND", (col, 1), (col, -1), t.SURFACE_ALT)

    tbl.setStyle(style)
    return tbl


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def render_chart(spec: ChartSpec, styles: dict,
                 width_pt: float = t.CHART_WIDTH_PT,
                 height_pt: float = t.CHART_MAX_H_PT) -> Optional[Flowable]:
    """Render a chart spec to PNG and wrap as a Flowable."""
    width_in  = width_pt  / inch
    height_in = height_pt / inch
    try:
        png = render_chart_to_png(spec, width_in=width_in,
                                  height_in=height_in, dpi=200)
    except Exception:
        return None
    if not png:
        return None
    return Image(io.BytesIO(png), width=width_pt, height=height_pt)


# ---------------------------------------------------------------------------
# Per-section rendering — opener page + (optional) evidence page
# ---------------------------------------------------------------------------
#
# Layout philosophy:
#   - The OPENER page is the executive view: headline, KPIs, key insights.
#     No tiny illegible thumbnails. Reads cleanly even when there's empty
#     space at the bottom.
#   - The EVIDENCE page is the supporting view: full-width source
#     screenshot (only if it'll be readable), tables, and reconstructed
#     charts. Skipped entirely if the section has no visual evidence.
#
# A decision layer (`_screenshot_decision`) inspects the screenshot
# against the layout budget and picks one of three outcomes:
#   1. RENDER — the screenshot is shown full-size on its own page.
#   2. OMIT   — the screenshot exists but can't be shown legibly; the
#               evidence page falls back to charts/tables/just-skip.
#   3. NONE   — there is no screenshot at all.
# ---------------------------------------------------------------------------

from enum import Enum


class _ScreenshotDecision(Enum):
    RENDER = "render"
    OMIT   = "omit"
    NONE   = "none"


def is_screenshot_legible(image_path: str,
                          target_w_pt: float = t.SCREENSHOT_TARGET_W_PT,
                          target_h_pt: float = t.SCREENSHOT_TARGET_H_PT) -> bool:
    """Return True if a screenshot rendered at the target box would be readable.

    Three conditions must all hold:
      1. The image file exists and opens.
      2. The target box is at least the configured minimum (so that text
         labels inside the dashboard remain visible after scaling).
      3. The source image has at least the minimum native resolution
         (otherwise the image is already too low-res to enlarge).
    """
    if target_w_pt < t.SCREENSHOT_MIN_W_PT or target_h_pt < t.SCREENSHOT_MIN_H_PT:
        return False
    try:
        with PILImage.open(image_path) as im:
            w, h = im.size
    except (OSError, ValueError):
        return False
    if max(w, h) < t.SCREENSHOT_MIN_NATIVE_PX:
        return False
    return True


def should_render_source_screenshot(section: ReportSection) -> _ScreenshotDecision:
    """Decide whether a section's source screenshot makes it into the PDF."""
    if not section.screenshot_path:
        return _ScreenshotDecision.NONE
    if not Path(section.screenshot_path).exists():
        return _ScreenshotDecision.NONE
    if is_screenshot_legible(section.screenshot_path):
        return _ScreenshotDecision.RENDER
    return _ScreenshotDecision.OMIT


def _section_has_evidence(section: ReportSection,
                          screenshot_decision: _ScreenshotDecision) -> bool:
    """True if the section has any visual evidence worth its own page."""
    if screenshot_decision is _ScreenshotDecision.RENDER:
        return True
    return bool(section.tables or section.charts)


def render_source_screenshot(section: ReportSection, styles: dict,
                             target_w_pt: float = t.SCREENSHOT_TARGET_W_PT,
                             target_h_pt: float = t.SCREENSHOT_TARGET_H_PT
                             ) -> Optional[Flowable]:
    """Render the screenshot at the target evidence-page size, with caption."""
    img = _fit_image_pt(section.screenshot_path,
                        max_w_pt=target_w_pt, max_h_pt=target_h_pt)
    if img is None:
        return None
    return KeepTogether([
        img,
        Spacer(1, t.SPACE_XS),
        Paragraph("Source dashboard page", styles["caption"]),
    ])


def render_visual_evidence_block(section: ReportSection,
                                 styles: dict) -> List[Flowable]:
    """Tables + reconstructed charts as evidence-page flowables."""
    out: List[Flowable] = []

    for spec in section.tables:
        block: List[Flowable] = []
        if spec.title:
            block.append(Paragraph(_escape(spec.title), styles["subheading"]))
        tbl = render_table(spec, styles)
        if tbl is not None:
            block.append(tbl)
            out.append(KeepTogether(block))
            out.append(Spacer(1, t.SPACE_M))

    # Charts carry their own embedded title; don't duplicate it here.
    for spec in section.charts:
        chart = render_chart(spec, styles)
        if chart is not None:
            out.append(chart)
            out.append(Spacer(1, t.SPACE_M))

    return out


def render_section_opener(section: ReportSection, styles: dict,
                          *, page_no: int, total_pages: int) -> List:
    """Executive view of a section: headline + KPIs + key insights only.

    Never renders the source screenshot. If the source content is missing
    ("Insufficient data for analysis"), shows a friendly callout instead.
    """
    eyebrow = f"PAGE {page_no:02d} OF {total_pages:02d}"
    out: List = []
    out.extend(render_section_header(eyebrow, section.title, section.headline,
                                     styles))

    if section.headline.strip().lower() == "insufficient data for analysis":
        out.append(render_callout(
            "This page did not expose enough quantitative data for a "
            "trustworthy analysis. Add the underlying data, then re-run "
            "the report.",
            severity="info", styles=styles,
            title="Insufficient data",
        ))
        out.append(PageBreak())
        return out

    if section.kpis:
        out.extend(render_kpi_strip(section.kpis, styles))
        out.append(Spacer(1, t.SPACE_M))

    if section.bullets:
        out.append(Paragraph("Key Insights", styles["subheading"]))
        for bullet in section.bullets:
            out.append(render_insight_card(bullet, styles, accent=t.ACCENT))
            out.append(Spacer(1, t.SPACE_S))

    out.append(PageBreak())
    return out


def render_section_evidence(section: ReportSection, styles: dict,
                            *, page_no: int, total_pages: int,
                            screenshot_decision: _ScreenshotDecision) -> List:
    """Supporting evidence page: large screenshot + tables + charts.

    Returns ``[]`` if the section has nothing worth a separate page.

    Layout decisions:
      - Screenshot ONLY: render at full target size (~600 pt tall).
      - Screenshot + charts/tables: shrink the screenshot to a still-
        legible mid-size (~350 pt) so the supporting visuals fit on the
        same page. If the resulting box would be illegible, the
        screenshot is dropped and only the charts/tables are shown.
      - Charts/tables only: render directly, no screenshot section.
      - Anything that doesn't fit naturally spills to the next page via
        ReportLab's Frame overflow.
    """
    if not _section_has_evidence(section, screenshot_decision):
        return []

    eyebrow = f"PAGE {page_no:02d} OF {total_pages:02d}  ·  SOURCE EVIDENCE"
    out: List = [
        Paragraph(_escape(eyebrow), styles["section_eyebrow"]),
        Paragraph(_escape(section.title), styles["subheading"]),
        _hairline_rule(),
        Spacer(1, t.SPACE_M),
    ]

    if screenshot_decision is _ScreenshotDecision.RENDER:
        # Co-locate with charts/tables when present.
        has_other = bool(section.tables or section.charts)
        target_h = (t.SCREENSHOT_MIN_H_PT + 70) if has_other \
                   else t.SCREENSHOT_TARGET_H_PT
        # Re-check legibility at the chosen target height.
        if is_screenshot_legible(section.screenshot_path,
                                 target_h_pt=target_h):
            screenshot_flow = render_source_screenshot(
                section, styles, target_h_pt=target_h,
            )
            if screenshot_flow is not None:
                out.append(screenshot_flow)
                out.append(Spacer(1, t.SPACE_L))

    out.extend(render_visual_evidence_block(section, styles))
    out.append(PageBreak())
    return out


def render_section(section: ReportSection, styles: dict,
                   *, page_no: int, total_pages: int) -> List:
    """Compose a section's opener + (optional) evidence pages."""
    decision = should_render_source_screenshot(section)
    out: List = []
    out.extend(render_section_opener(section, styles,
                                     page_no=page_no, total_pages=total_pages))
    out.extend(render_section_evidence(section, styles,
                                       page_no=page_no, total_pages=total_pages,
                                       screenshot_decision=decision))
    return out


# ---------------------------------------------------------------------------
# Appendix
# ---------------------------------------------------------------------------

def render_appendix(report: ReportData, styles: dict) -> List:
    """Structured appendix: source metadata + numbers cited per page."""
    out: List = [
        Paragraph("Appendix", styles["section_title"]),
        _hairline_rule(),
        Spacer(1, t.SPACE_M),
    ]

    # Source metadata table
    out.append(Paragraph("Source & Method", styles["subheading"]))
    meta = report.metadata
    method = "Live DAX (Power BI Modeling MCP)" if meta.source_type in ("pbip", "pbix") \
             else "Image-based analysis"
    rows = [
        ("Source name", meta.source_name),
        ("Source type", meta.source_type.upper()),
        ("Input path", meta.input_path),
        ("Generated at", _format_timestamp(meta.generated_at)),
        ("Analysis method", method),
        ("Sections rendered", str(len(report.sections))),
    ]
    meta_tbl = Table(
        [[Paragraph(_escape(k), styles["appendix_label"]),
          Paragraph(_escape(v), styles["appendix_value"])]
         for k, v in rows],
        colWidths=[110, t.CONTENT_WIDTH - 110],
        hAlign="LEFT",
    )
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), t.HAIRLINE, t.DIVIDER),
    ]))
    out.append(meta_tbl)
    out.append(Spacer(1, t.SPACE_L))

    # Numbers cited per page
    out.append(Paragraph("Numbers Cited", styles["subheading"]))
    rows = []
    for section in report.sections:
        nums = ", ".join(section.numbers_used) if section.numbers_used else "—"
        rows.append([
            Paragraph(f"{section.slide_number:02d}", styles["appendix_label"]),
            Paragraph(_escape(section.title), styles["appendix_label"]),
            Paragraph(_escape(nums), styles["appendix_value"]),
        ])
    if rows:
        nums_tbl = Table(
            [[Paragraph("#", styles["table_header"]),
              Paragraph("Page", styles["table_header"]),
              Paragraph("Numbers cited on this page", styles["table_header"])]] + rows,
            colWidths=[28, 130, t.CONTENT_WIDTH - 158],
            hAlign="LEFT",
            repeatRows=1,
        )
        nums_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), t.SURFACE_ALT),
            ("LINEBELOW", (0, 0), (-1, 0), t.THIN, t.DIVIDER_STRONG),
            ("LINEBELOW", (0, 1), (-1, -1), t.HAIRLINE, t.DIVIDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [t.SURFACE, t.SURFACE_SUBTLE]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        out.append(nums_tbl)

    return out
