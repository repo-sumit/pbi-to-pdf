"""
PDF report renderer using ReportLab.

Produces a portrait A4 PDF with:
  1. Cover page              (title, subtitle, metadata)
  2. Executive summary       (bullet list)
  3. Recommendations         (action items)
  4. Per-page sections       (headline, screenshot, KPIs, tables, charts, bullets)
  5. Appendix                (source metadata + numbers cited per page)

Charts are rendered via the matplotlib pipeline in
``lib.reporting.charts.render_chart_to_png``.

Layout philosophy: titles stay bonded to the visual they introduce via
KeepTogether. Charts are sized to let two fit per page when possible, and
pages flow to fill vertical space rather than one-chart-per-page.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from lib.analysis.insights import ChartSpec
from lib.reporting.report_schema import (
    ReportBullet,
    ReportData,
    ReportSection,
)
from lib.reporting.charts import render_chart_to_png


# ---------------------------------------------------------------------------
# Palette — matches AnalyticsStyleGuide in lib/rendering/builder.py
# ---------------------------------------------------------------------------

DARK_BLUE = colors.HexColor("#002060")
ACCENT_BLUE = colors.HexColor("#0072C6")
PURPLE_ACCENT = colors.HexColor("#7030A0")
DARK_GRAY = colors.HexColor("#404040")
MID_GRAY = colors.HexColor("#707070")
LIGHT_GRAY = colors.HexColor("#D9D9D9")
BEIGE_BG = colors.HexColor("#F5EFE7")
WHITE = colors.white

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 0.55 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

# Chart geometry — sized so two charts fit on one A4 page alongside text.
CHART_HEIGHT_IN = 2.6    # each chart ~2.6" tall
SCREENSHOT_MAX_H_IN = 3.2


# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=DARK_BLUE,
            alignment=0,
            spaceAfter=10,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=14,
            leading=18,
            textColor=MID_GRAY,
            spaceAfter=18,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=DARK_GRAY,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=DARK_BLUE,
            spaceBefore=4,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=DARK_BLUE,
            spaceBefore=6,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "headline": ParagraphStyle(
            "headline",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=ACCENT_BLUE,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=DARK_GRAY,
            spaceAfter=3,
        ),
        "bullet_bold": ParagraphStyle(
            "bullet_bold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=DARK_BLUE,
            leftIndent=12,
            bulletIndent=0,
            spaceAfter=1,
        ),
        "bullet_detail": ParagraphStyle(
            "bullet_detail",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=DARK_GRAY,
            leftIndent=12,
            spaceAfter=4,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            textColor=MID_GRAY,
            spaceAfter=4,
        ),
        "appendix_body": ParagraphStyle(
            "appendix_body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=DARK_GRAY,
            spaceAfter=4,
        ),
    }


# ---------------------------------------------------------------------------
# Page decoration (header/footer on content pages)
# ---------------------------------------------------------------------------

class _ContentCanvas(rl_canvas.Canvas):
    """Canvas with footer (page N of M) and a thin header rule."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states: list = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_chrome(total)
            super().showPage()
        super().save()

    def _draw_chrome(self, total: int):
        # Cover page (page 1) has no chrome.
        if self._pageNumber == 1:
            return
        # Header rule
        self.setStrokeColor(LIGHT_GRAY)
        self.setLineWidth(0.5)
        self.line(MARGIN, PAGE_HEIGHT - MARGIN + 6, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN + 6)
        # Footer
        self.setFont("Helvetica", 8)
        self.setFillColor(MID_GRAY)
        self.drawString(MARGIN, 0.35 * inch, "Dashboard Report")
        self.drawRightString(
            PAGE_WIDTH - MARGIN,
            0.35 * inch,
            f"Page {self._pageNumber} of {total}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fit_image(path: str, max_w: float, max_h: float) -> Optional[Image]:
    """Load PNG/JPG and scale to fit box while preserving aspect."""
    try:
        with PILImage.open(path) as im:
            w, h = im.size
    except (OSError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    scale = min(max_w / w, max_h / h)
    return Image(path, width=w * scale, height=h * scale)


def _chart_image(spec: ChartSpec, width_in: float, height_in: float) -> Optional[Image]:
    """Render ChartSpec → PNG → ReportLab Image. Returns None on failure."""
    try:
        png_bytes = render_chart_to_png(spec, width_in=width_in, height_in=height_in, dpi=180)
    except Exception:
        return None
    if not png_bytes:
        return None
    img = Image(io.BytesIO(png_bytes), width=width_in * inch, height=height_in * inch)
    return img


def _table_from_spec(spec: ChartSpec) -> Optional[Table]:
    """Build a ReportLab Table from a ChartSpec of type 'table'."""
    cols = spec.table_columns or []
    rows = spec.table_rows or []
    if not cols or not rows:
        return None

    data = [list(cols)] + [list(r) for r in rows]
    max_col_w = CONTENT_WIDTH / max(len(cols), 1)
    col_widths = [max_col_w] * len(cols)
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT")

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BEIGE_BG]),
        ("GRID", (0, 0), (-1, -1), 0.25, LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])

    if 0 <= spec.highlight_col < len(cols):
        col = spec.highlight_col
        style.add("TEXTCOLOR", (col, 1), (col, -1), ACCENT_BLUE)
        style.add("FONTNAME", (col, 1), (col, -1), "Helvetica-Bold")

    tbl.setStyle(style)
    return tbl


def _kpi_strip(specs: List[ChartSpec]) -> Optional[Table]:
    """Render KPI cards as a single horizontal strip using a ReportLab Table."""
    cells: List[List] = []
    items: List[dict] = []

    for spec in specs:
        t = (spec.type or "").lower().strip()
        if t in ("kpi", "card"):
            items.append({"value": spec.value, "label": spec.label, "subtitle": spec.subtitle})
        elif t in ("kpi_row", "multi_row_card"):
            raw_items = getattr(spec, "data", None)
            # ChartSpec doesn't expose items directly; kpi_row stores in .data as ChartDataPoint (value + label)
            if raw_items:
                for dp in raw_items:
                    items.append({"value": str(dp.value), "label": dp.label, "subtitle": ""})
            # Fallback: some analysts put kpi_row items in .series as dicts
            elif spec.series:
                for itm in spec.series:
                    if isinstance(itm, dict):
                        items.append({
                            "value": str(itm.get("value", "")),
                            "label": itm.get("label", ""),
                            "subtitle": itm.get("subtitle", ""),
                        })

    if not items:
        return None

    styles = _styles()
    value_style = ParagraphStyle(
        "kpi_value",
        parent=styles["h1"],
        fontSize=20,
        leading=24,
        textColor=ACCENT_BLUE,
        alignment=1,
        spaceAfter=2,
    )
    label_style = ParagraphStyle(
        "kpi_label",
        parent=styles["caption"],
        fontSize=9,
        leading=11,
        textColor=DARK_GRAY,
        alignment=1,
        spaceAfter=0,
    )

    cell_row: List = []
    for itm in items:
        parts = [Paragraph(str(itm["value"] or "—"), value_style),
                 Paragraph(itm["label"] or "", label_style)]
        if itm.get("subtitle"):
            parts.append(Paragraph(itm["subtitle"], label_style))
        cell_row.append(parts)
    cells.append(cell_row)

    col_w = CONTENT_WIDTH / len(items)
    tbl = Table(cells, colWidths=[col_w] * len(items), hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BEIGE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return tbl


def _bullets_flowables(bullets: List[ReportBullet], styles: dict) -> List:
    out: List = []
    for b in bullets:
        if b.bold:
            out.append(Paragraph(f"• {_escape(b.bold)}", styles["bullet_bold"]))
        if b.detail:
            out.append(Paragraph(_escape(b.detail), styles["bullet_detail"]))
    return out


def _escape(s: str) -> str:
    """Escape ReportLab Paragraph markup characters."""
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def _format_timestamp(iso_ts: str) -> str:
    """Turn '2026-04-15T18:03:30+05:30' into '2026-04-15 18:03' for display.

    Falls back to the original string on any parse failure.
    """
    if not iso_ts:
        return ""
    try:
        dt = datetime.fromisoformat(iso_ts)
    except ValueError:
        return iso_ts
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Flowable assembly
# ---------------------------------------------------------------------------

def _cover_flowables(report: ReportData, styles: dict) -> List:
    meta = report.metadata
    lines = [
        Spacer(1, 2.2 * inch),
        Paragraph(_escape(report.title), styles["cover_title"]),
    ]
    if report.subtitle:
        lines.append(Paragraph(_escape(report.subtitle), styles["cover_subtitle"]))

    lines.append(Spacer(1, 0.25 * inch))
    # Accent rule
    rule = Table([[""]], colWidths=[3 * inch], rowHeights=[3])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_BLUE)]))
    lines.append(rule)
    lines.append(Spacer(1, 0.35 * inch))

    meta_rows = [
        ("Source file", meta.source_name),
        ("Source type", meta.source_type.upper()),
        ("Generated", _format_timestamp(meta.generated_at)),
    ]
    meta_tbl = Table(
        [[Paragraph(f"<b>{k}</b>", styles["cover_meta"]),
          Paragraph(_escape(str(v)), styles["cover_meta"])]
         for k, v in meta_rows],
        colWidths=[1.4 * inch, CONTENT_WIDTH - 1.4 * inch],
        hAlign="LEFT",
    )
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    lines.append(meta_tbl)
    lines.append(PageBreak())
    return lines


def _summary_flowables(report: ReportData, styles: dict) -> List:
    out: List = []
    if report.executive_summary:
        out.append(Paragraph("Executive Summary", styles["h1"]))
        for bullet in report.executive_summary:
            out.append(Paragraph(f"• {_escape(bullet)}", styles["bullet_bold"]))
        out.append(Spacer(1, 0.15 * inch))

    if report.recommendations:
        out.append(Paragraph("Recommendations", styles["h1"]))
        for rec in report.recommendations:
            out.append(Paragraph(f"&#187; {_escape(rec)}", styles["bullet_bold"]))
        out.append(Spacer(1, 0.15 * inch))

    if out:
        out.append(PageBreak())
    return out


def _section_flowables(section: ReportSection, styles: dict) -> List:
    out: List = [
        Paragraph(f"Page {section.slide_number}. {_escape(section.title)}", styles["h1"]),
    ]
    if section.headline:
        out.append(Paragraph(_escape(section.headline), styles["headline"]))

    # KPI strip (one row, all cards)
    if section.kpis:
        strip = _kpi_strip(section.kpis)
        if strip is not None:
            out.append(strip)
            out.append(Spacer(1, 0.10 * inch))

    # Screenshot of the dashboard page (if available)
    if section.screenshot_path:
        img = _fit_image(
            section.screenshot_path,
            max_w=CONTENT_WIDTH,
            max_h=SCREENSHOT_MAX_H_IN * inch,
        )
        if img is not None:
            out.append(KeepTogether([img, Paragraph("Source dashboard page", styles["caption"])]))
            out.append(Spacer(1, 0.08 * inch))

    # Text bullets
    if section.bullets:
        out.append(Paragraph("Key insights", styles["h2"]))
        out.extend(_bullets_flowables(section.bullets, styles))

    # Tables — bind title to table so they never split across pages
    for spec in section.tables:
        block: List = []
        if spec.title:
            block.append(Paragraph(_escape(spec.title), styles["h2"]))
        tbl = _table_from_spec(spec)
        if tbl is not None:
            block.append(tbl)
            out.append(KeepTogether(block))
            out.append(Spacer(1, 0.10 * inch))

    # Other charts — bind title to chart image so they never split across pages
    for spec in section.charts:
        block: List = []
        if spec.title:
            block.append(Paragraph(_escape(spec.title), styles["h2"]))
        chart = _chart_image(spec, width_in=CONTENT_WIDTH / inch, height_in=CHART_HEIGHT_IN)
        if chart is not None:
            block.append(chart)
            out.append(KeepTogether(block))
            out.append(Spacer(1, 0.10 * inch))

    out.append(PageBreak())
    return out


def _appendix_flowables(report: ReportData, styles: dict) -> List:
    out: List = [Paragraph("Appendix", styles["h1"])]

    meta = report.metadata
    meta_rows = [
        ["Source name", meta.source_name],
        ["Source type", meta.source_type.upper()],
        ["Input path", meta.input_path],
        ["Generated at", _format_timestamp(meta.generated_at)],
        ["Sections", str(len(report.sections))],
    ]
    tbl = Table(meta_rows, colWidths=[1.3 * inch, CONTENT_WIDTH - 1.3 * inch])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK_BLUE),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, LIGHT_GRAY),
    ]))
    out.append(tbl)
    out.append(Spacer(1, 0.2 * inch))

    out.append(Paragraph("Numbers cited, by page", styles["h2"]))
    for section in report.sections:
        if section.numbers_used:
            label = f"<b>Page {section.slide_number} — {_escape(section.title)}:</b> " \
                    f"{_escape(', '.join(section.numbers_used))}"
        else:
            label = f"<b>Page {section.slide_number} — {_escape(section.title)}:</b> " \
                    f"<i>no numbers cited</i>"
        out.append(Paragraph(label, styles["appendix_body"]))

    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_report_pdf(report: ReportData, output_path: str) -> str:
    """Render a ReportData object to a PDF file. Returns the output path."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=report.title or "Dashboard Report",
        author="pbi-to-pdf",
    )

    frame = Frame(
        MARGIN,
        MARGIN,
        CONTENT_WIDTH,
        PAGE_HEIGHT - 2 * MARGIN,
        id="content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    styles = _styles()
    story: List = []
    story.extend(_cover_flowables(report, styles))
    story.extend(_summary_flowables(report, styles))
    for section in report.sections:
        story.extend(_section_flowables(section, styles))
    story.extend(_appendix_flowables(report, styles))

    doc.build(story, canvasmaker=_ContentCanvas)
    return str(out)
