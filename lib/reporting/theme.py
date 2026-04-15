"""
Design system for pbi-to-pdf reports.

Single source of truth for typography, color, spacing, page geometry,
and ReportLab paragraph styles. Every component in
:mod:`lib.reporting.components` imports tokens from here so the visual
language stays consistent across all report types.

The system is intentionally generic — no domain-specific labels or
colours. Components adapt to whatever data the analyst provided.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ---------------------------------------------------------------------------
# Page geometry — A4 portrait, generous margins for executive readability.
# ---------------------------------------------------------------------------

PAGE_WIDTH, PAGE_HEIGHT = A4

PAGE_MARGIN_TOP    = 18 * mm
PAGE_MARGIN_BOTTOM = 18 * mm
PAGE_MARGIN_LEFT   = 18 * mm
PAGE_MARGIN_RIGHT  = 18 * mm

CONTENT_WIDTH  = PAGE_WIDTH  - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT
CONTENT_HEIGHT = PAGE_HEIGHT - PAGE_MARGIN_TOP  - PAGE_MARGIN_BOTTOM


# ---------------------------------------------------------------------------
# Spacing scale (points). Use these tokens — never raw numbers.
# ---------------------------------------------------------------------------

SPACE_XS  =  4
SPACE_S   =  8
SPACE_M   = 12
SPACE_L   = 16
SPACE_XL  = 24
SPACE_XXL = 32
SPACE_SECTION = 36   # between major report sections


# ---------------------------------------------------------------------------
# Colour palette — restrained, enterprise-friendly.
# Five core neutrals + four functional accents. Nothing else.
# ---------------------------------------------------------------------------

# Brand
PRIMARY        = colors.HexColor("#1F3A5F")  # deep corporate blue
ACCENT         = colors.HexColor("#3F6EA8")  # secondary blue

# Text
TEXT_PRIMARY   = colors.HexColor("#111827")  # near-black
TEXT_SECONDARY = colors.HexColor("#4B5563")  # body grey
TEXT_MUTED     = colors.HexColor("#9CA3AF")  # captions / footers

# Surfaces
SURFACE        = colors.HexColor("#FFFFFF")  # page background
SURFACE_ALT    = colors.HexColor("#F7F8FA")  # card / KPI background
SURFACE_SUBTLE = colors.HexColor("#FAFAFB")  # zebra stripes
DIVIDER        = colors.HexColor("#E5E7EB")  # hairlines
DIVIDER_STRONG = colors.HexColor("#D1D5DB")  # table borders

# Functional severity colours (muted)
SUCCESS     = colors.HexColor("#2F855A")
WARNING     = colors.HexColor("#B7791F")
CRITICAL    = colors.HexColor("#C53030")
INFO        = ACCENT
OPPORTUNITY = colors.HexColor("#2C7A7B")  # muted teal


SEVERITY_COLOR = {
    "critical":    CRITICAL,
    "high":        CRITICAL,
    "warning":     WARNING,
    "medium":      WARNING,
    "opportunity": OPPORTUNITY,
    "success":     SUCCESS,
    "low":         INFO,
    "info":        INFO,
}


def severity_color(level: str | None) -> colors.Color:
    """Return the palette colour for a severity / priority level."""
    if not level:
        return INFO
    return SEVERITY_COLOR.get(level.lower().strip(), INFO)


# ---------------------------------------------------------------------------
# Typography — try Inter, fall back to Helvetica when the .ttf isn't available.
# ---------------------------------------------------------------------------

_FONT_REGULAR_CANDIDATES = [
    Path("C:/Windows/Fonts/Inter-Regular.ttf"),
    Path("C:/Windows/Fonts/Inter.ttf"),
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/Inter-Regular.ttf",
    Path.home() / ".fonts" / "Inter-Regular.ttf",
    Path("/usr/share/fonts/truetype/inter/Inter-Regular.ttf"),
]
_FONT_BOLD_CANDIDATES = [
    Path("C:/Windows/Fonts/Inter-Bold.ttf"),
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts/Inter-Bold.ttf",
    Path.home() / ".fonts" / "Inter-Bold.ttf",
    Path("/usr/share/fonts/truetype/inter/Inter-Bold.ttf"),
]


def _register_inter_or_fallback() -> tuple[str, str]:
    """Attempt to register Inter; fall back to Helvetica if unavailable."""
    for reg in _FONT_REGULAR_CANDIDATES:
        if not reg.exists():
            continue
        bold = next((b for b in _FONT_BOLD_CANDIDATES if b.exists()), None)
        if bold is None:
            continue
        try:
            pdfmetrics.registerFont(TTFont("Inter", str(reg)))
            pdfmetrics.registerFont(TTFont("Inter-Bold", str(bold)))
            return "Inter", "Inter-Bold"
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_inter_or_fallback()


# Type scale — (size_pt, leading_pt). Leading is ~1.3-1.4x size.
TYPE_SCALE: dict[str, tuple[float, float]] = {
    "cover_title":    (28, 34),
    "cover_subtitle": (14, 20),
    "cover_meta":     (10, 14),

    "section_title": (17, 22),
    "subheading":    (12, 16),
    "headline":      (12, 17),
    "callout_title": (10.5, 14),

    "body":         (10, 14),
    "body_strong":  (10, 14),
    "body_small":   (9, 13),

    "bullet_bold":   (10.5, 14),
    "bullet_detail": (10, 14),

    "table_header": (9, 12),
    "table_body":   (8.5, 11.5),

    "kpi_value": (22, 26),
    "kpi_label": (8.5, 11),
    "kpi_sub":   (7.5, 10),

    "caption": (8.5, 11),
    "footer":  (8, 11),
    "tag":     (7.5, 10),
}


# ---------------------------------------------------------------------------
# ReportLab ParagraphStyle catalogue
# ---------------------------------------------------------------------------

def build_styles() -> dict[str, ParagraphStyle]:
    """Return the catalogue of ReportLab paragraph styles used by components."""
    base = getSampleStyleSheet()["Normal"]

    def style(name: str, *, key: str, font: str = FONT_REGULAR,
              color: colors.Color = TEXT_PRIMARY, alignment: int = 0,
              space_before: float = 0, space_after: float = 0,
              keep_with_next: int = 0, left_indent: float = 0,
              tracking: float = 0) -> ParagraphStyle:
        size, leading = TYPE_SCALE[key]
        return ParagraphStyle(
            name=name,
            parent=base,
            fontName=font,
            fontSize=size,
            leading=leading,
            textColor=color,
            alignment=alignment,
            spaceBefore=space_before,
            spaceAfter=space_after,
            keepWithNext=keep_with_next,
            leftIndent=left_indent,
            charSpace=tracking,
        )

    return {
        # ---- Cover ----
        "cover_title":    style("cover_title",    key="cover_title",
                                font=FONT_BOLD, color=PRIMARY,
                                space_after=SPACE_S),
        "cover_subtitle": style("cover_subtitle", key="cover_subtitle",
                                color=TEXT_SECONDARY,
                                space_after=SPACE_L),
        "cover_meta":     style("cover_meta",     key="cover_meta",
                                color=TEXT_SECONDARY),
        "cover_meta_label": style("cover_meta_label", key="cover_meta",
                                  font=FONT_BOLD, color=TEXT_PRIMARY),

        # ---- Section / page chrome ----
        "section_title":  style("section_title", key="section_title",
                                font=FONT_BOLD, color=PRIMARY,
                                space_after=SPACE_XS, keep_with_next=1),
        "section_eyebrow": style("section_eyebrow", key="tag",
                                 font=FONT_BOLD, color=ACCENT,
                                 tracking=0.6, space_after=SPACE_XS,
                                 keep_with_next=1),
        "headline":        style("headline",       key="headline",
                                 font=FONT_BOLD, color=PRIMARY,
                                 space_after=SPACE_M, keep_with_next=1),
        "subheading":      style("subheading",     key="subheading",
                                 font=FONT_BOLD, color=TEXT_PRIMARY,
                                 space_before=SPACE_S, space_after=SPACE_XS,
                                 keep_with_next=1),

        # ---- Body / bullets ----
        "body":            style("body",          key="body",
                                 color=TEXT_PRIMARY, space_after=SPACE_XS),
        "body_secondary":  style("body_secondary", key="body",
                                 color=TEXT_SECONDARY, space_after=SPACE_XS),
        "body_strong":     style("body_strong",   key="body_strong",
                                 font=FONT_BOLD, color=TEXT_PRIMARY,
                                 space_after=SPACE_XS),

        "bullet_bold":     style("bullet_bold",   key="bullet_bold",
                                 font=FONT_BOLD, color=TEXT_PRIMARY,
                                 space_after=2),
        "bullet_detail":   style("bullet_detail", key="bullet_detail",
                                 color=TEXT_SECONDARY, space_after=SPACE_XS),

        # ---- KPI ----
        "kpi_value":       style("kpi_value",     key="kpi_value",
                                 font=FONT_BOLD, color=PRIMARY, alignment=1),
        "kpi_label":       style("kpi_label",     key="kpi_label",
                                 color=TEXT_SECONDARY, alignment=1),
        "kpi_sub":         style("kpi_sub",       key="kpi_sub",
                                 color=TEXT_MUTED, alignment=1),

        # ---- Tables ----
        "table_header":    style("table_header",  key="table_header",
                                 font=FONT_BOLD, color=TEXT_PRIMARY),
        "table_body":      style("table_body",    key="table_body",
                                 color=TEXT_PRIMARY),
        "table_body_num":  style("table_body_num", key="table_body",
                                 color=TEXT_PRIMARY, alignment=2),

        # ---- Callouts / cards ----
        "callout_title":   style("callout_title", key="callout_title",
                                 font=FONT_BOLD, color=TEXT_PRIMARY,
                                 space_after=2, keep_with_next=1),
        "callout_body":    style("callout_body",  key="body",
                                 color=TEXT_SECONDARY),
        "card_title":      style("card_title",    key="body_strong",
                                 font=FONT_BOLD, color=TEXT_PRIMARY,
                                 space_after=2, keep_with_next=1),
        "card_body":       style("card_body",     key="body",
                                 color=TEXT_SECONDARY),

        "tag":             style("tag",           key="tag",
                                 font=FONT_BOLD, color=ACCENT,
                                 tracking=0.6),

        # ---- Misc ----
        "caption":         style("caption",       key="caption",
                                 color=TEXT_MUTED, alignment=1,
                                 space_after=SPACE_XS),
        "footer":          style("footer",        key="footer",
                                 color=TEXT_MUTED),
        "appendix_label":  style("appendix_label", key="body_strong",
                                 font=FONT_BOLD, color=TEXT_PRIMARY),
        "appendix_value":  style("appendix_value", key="body",
                                 color=TEXT_SECONDARY),
    }


# ---------------------------------------------------------------------------
# Misc layout tokens
# ---------------------------------------------------------------------------

# Stroke widths
HAIRLINE = 0.4
THIN     = 0.6
MEDIUM   = 1.0
ACCENT_BAR = 3.0    # left-border accent on cards / callouts

# Border radius (used as TableStyle ROUNDEDCORNERS)
RADIUS = 4

# Fixed component sizes
KPI_CARD_HEIGHT      = 64    # pt
CHART_MAX_H_PT       = 220   # pt — two charts fit per A4 page
CHART_WIDTH_PT       = CONTENT_WIDTH


# ---------------------------------------------------------------------------
# Source-screenshot legibility thresholds.
#
# The renderer uses these to decide whether a dashboard preview can be
# shown at a useful, readable size. If a screenshot would shrink below
# the minimum, it is omitted from the opener page and either moved to a
# dedicated evidence page (if there's room) or dropped entirely.
# ---------------------------------------------------------------------------

# Minimum target box on the page for a screenshot to count as "readable".
# Roughly equivalent to 150 mm × 100 mm — the smallest a typical
# multi-chart Power BI page can be shown without losing axis labels.
SCREENSHOT_MIN_W_PT = 420
SCREENSHOT_MIN_H_PT = 280

# Target box on the dedicated evidence page (full-width, near-full-height,
# leaving room for caption + footer chrome).
SCREENSHOT_TARGET_W_PT = CONTENT_WIDTH
SCREENSHOT_TARGET_H_PT = 600

# Minimum source-image resolution. Anything smaller is already too
# low-res to be useful even at full page width.
SCREENSHOT_MIN_NATIVE_PX = 600
