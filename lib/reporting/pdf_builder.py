"""
A4 PDF report renderer — slim orchestrator.

All visual styling lives in :mod:`lib.reporting.theme`. All flowable
construction lives in :mod:`lib.reporting.components`. This module just
wires page templates, page chrome (header rule + footer with page
numbers), and the section-by-section flow.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
)
from reportlab.pdfgen import canvas as rl_canvas

from lib.reporting import components, theme as t
from lib.reporting.report_schema import ReportData


# ---------------------------------------------------------------------------
# Page chrome — footer + thin top rule on content pages.
# ---------------------------------------------------------------------------

class _ChromeCanvas(rl_canvas.Canvas):
    """Canvas with a thin header rule and a "Page N of M" footer."""

    def __init__(self, *args, report_name: str = "Dashboard Report", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states: list = []
        self._report_name = report_name

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
        # Cover page (page 1) — no chrome.
        if self._pageNumber == 1:
            return

        # Top hairline rule
        self.setStrokeColor(t.DIVIDER)
        self.setLineWidth(t.HAIRLINE)
        y_top = t.PAGE_HEIGHT - t.PAGE_MARGIN_TOP + 8
        self.line(t.PAGE_MARGIN_LEFT, y_top,
                  t.PAGE_WIDTH - t.PAGE_MARGIN_RIGHT, y_top)

        # Footer
        self.setFont(t.FONT_REGULAR, 8)
        self.setFillColor(t.TEXT_MUTED)
        y_footer = t.PAGE_MARGIN_BOTTOM - 12
        self.drawString(t.PAGE_MARGIN_LEFT, y_footer, self._report_name)
        self.drawRightString(
            t.PAGE_WIDTH - t.PAGE_MARGIN_RIGHT,
            y_footer,
            f"{self._pageNumber} / {total}",
        )


def _canvas_factory(report_name: str):
    def make(*args, **kwargs):
        return _ChromeCanvas(*args, report_name=report_name, **kwargs)
    return make


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_report_pdf(report: ReportData, output_path: str) -> str:
    """Render a ``ReportData`` object to an A4 PDF. Returns the output path."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(out),
        pagesize=(t.PAGE_WIDTH, t.PAGE_HEIGHT),
        leftMargin=t.PAGE_MARGIN_LEFT,
        rightMargin=t.PAGE_MARGIN_RIGHT,
        topMargin=t.PAGE_MARGIN_TOP,
        bottomMargin=t.PAGE_MARGIN_BOTTOM,
        title=report.title or "Dashboard Report",
        author="pbi-to-pdf",
    )

    content_frame = Frame(
        t.PAGE_MARGIN_LEFT,
        t.PAGE_MARGIN_BOTTOM,
        t.CONTENT_WIDTH,
        t.CONTENT_HEIGHT,
        id="content",
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[content_frame])])

    styles = t.build_styles()
    story: List = []

    # 1. Cover
    story.extend(components.render_cover_page(report, styles))

    # 2. Executive summary (KPIs + key findings + recommended actions)
    if (report.executive_summary or report.recommendations or report.cover_kpis):
        story.extend(components.render_executive_summary(report, styles))

    # 3. One section per dashboard page
    total = len(report.sections)
    for idx, section in enumerate(report.sections, start=1):
        story.extend(components.render_section(section, styles,
                                               page_no=idx,
                                               total_pages=total))

    # Strip any trailing PageBreak flowables so the document doesn't end
    # on a blank page. (Each section appends a PageBreak; previously the
    # appendix consumed it, but the appendix was removed.)
    while story and isinstance(story[-1], PageBreak):
        story.pop()

    report_name = report.title or "Dashboard Report"
    doc.build(story, canvasmaker=_canvas_factory(report_name))
    return str(out)
