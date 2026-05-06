# pbi-to-pdf

**Power BI dashboards → polished A4 PDF reports, designed for Claude Code.**

You point the CLI at a Power BI export, and Claude Code (running in your
terminal) reads each dashboard page, generates analyst-grade insights,
and the toolkit renders them into a portrait A4 PDF you can hand to an
executive.

No Anthropic API key is required — the analysis runs inside your active
Claude Code session.

---

## Overview

`pbi-to-pdf` is a **Claude-Code-first** report generator. The product
purpose is to compress a multi-page Power BI dashboard down to a
1–2-page-per-section executive PDF that has:

- a story-driven cover title and subtitle,
- a synthesised executive summary (findings + numbered recommendations),
- one section per dashboard page with a "so what?" headline, a KPI
  strip, key-insight cards, and an evidence page (source screenshot,
  reconstructed charts, tables).

The system is intentionally split so that **Claude is the analyst** and
the Python code is the extractor + renderer. Numbers, headlines,
recommendations, and chart specs come from Claude. Geometry, typography,
chart drawing, and pagination are deterministic Python.

### Main user flow

1. User runs `python run_report.py "<dashboard>"` (or `/generate-report`
   inside Claude Code).
2. **Stage 1 — Extract.** Per-format extractor dumps each dashboard
   page to `temp/` as a PNG, plus a manifest `temp/analysis_request.json`.
   For `.pbip`/`.pbix`, an enriched `temp/pbip_context.json` is also
   written with every measure's DAX and a pre-built `EVALUATE` query.
3. **Stage 2 — Analyse.** The CLI prints a Claude-Code-facing prompt
   and polls for `temp/insights.json`. Claude reads the manifest, the
   screenshots and/or queries the live model via the optional Power BI
   Modeling MCP, and writes the insights file.
4. **Stage 2.5 — Verify.** `verify_insights()` runs schema and quality
   checks. Errors block the build; warnings are printed.
5. **Stage 3 — Build.** [lib/reporting/pdf_builder.py](lib/reporting/pdf_builder.py)
   renders the A4 PDF to `<input_dir>/<input_stem>_report.pdf`.

---

## What this is (and isn't)

| | |
|---|---|
| **Primary output** | A portrait A4 PDF report (`<input>_report.pdf`) |
| **Primary driver** | Claude Code as the senior analyst in the loop |
| **Optional power-up** | Live DAX queries via the Power BI Modeling MCP for `.pbix` and `.pbip` |
| **Not a deck generator** | The PPTX/deck-generation path was cut to keep the report path coherent |
| **Not an unattended service** | Stage 2 expects an interactive Claude Code session to populate `temp/insights.json` |

---

## Key Features

- **Format-agnostic input.** Accepts `.pdf`, `.pptx`, `.pbip` (folder
  or `.pbip` file), and `.pbix` (ZIP) with one CLI.
- **Live DAX mode for `.pbip` / `.pbix`.** When the
  [`powerbi-modeling` MCP](https://github.com/microsoft/powerbi-modeling-mcp)
  is registered and Power BI Desktop is open, Claude executes
  pre-built `EVALUATE` queries against the live model. Numbers come
  from query results, not visual estimation.
- **Graceful fallback.** Without the MCP, `.pbip`/`.pbix` automatically
  degrade to image analysis. A clear warning is printed; nothing breaks.
- **Companion-export discovery.** When a `.pbip` is opened without the
  MCP, the extractor looks for a sibling `.pdf`/`.pptx` export (e.g.
  File → Export → PDF saved next to the project) and uses its pages as
  evidence screenshots. Self-generated outputs are filtered out by
  suffix and by checking for the `EXECUTIVE REPORT` cover marker
  ([lib/extraction/pbip_extractor.py:2256](lib/extraction/pbip_extractor.py#L2256)).
- **Optional UI automation.** With `--capture-ui`, the PBIP/PBIX
  extractors can drive Power BI Desktop directly (keystrokes, focus
  stealing) to grab live screenshots. Off by default for safety.
- **Content-aware page splitting** for portrait PDF inputs. Long
  vertically-scrollable Power BI exports are split into 16:9 strips at
  whitespace boundaries detected from background brightness, so cuts
  never go through chart cards or table rows
  ([lib/extraction/pdf_extractor.py:121](lib/extraction/pdf_extractor.py#L121)).
- **Deterministic rendering.** A4 portrait, 18 mm margins, restrained
  blue + neutral palette, header rule + "Page N of M" footer, Inter
  with Helvetica fallback. All tokens centralised in
  [lib/reporting/theme.py](lib/reporting/theme.py).
- **23+ chart types.** `kpi`, `kpi_row`, `bar`, `column`, `line`,
  `area`, `donut`, `pie`, `table`, `treemap`, `funnel`, `gauge`,
  `heatmap`, `scatter`, `waterfall`, `combo`, plus stacked / 100% /
  ribbon / radar / bubble / multi-row-card aliases. Tables stay tables
  — the verifier and the renderer both refuse to collapse them.
- **Insight verifier.** Catches missing `executive_summary`, vanilla
  headlines (matched against a stop-phrase list), missing chart specs,
  generic deck titles, and slide-count mismatches before the build
  runs ([lib/pipeline.py:454](lib/pipeline.py#L454)).
- **Severity-aware recommendations.** Recommendations can be prefixed
  with `[High]`, `(Priority: Medium)`, or `Critical:` and are coloured
  accordingly ([lib/reporting/report_schema.py:78](lib/reporting/report_schema.py#L78)).
- **Bold-or-detail bullets.** Insight bullets use a `||` separator
  that splits into a bold headline line and a normal-weight detail
  line in the PDF.
- **Cover KPI strip.** Either explicitly via `cover_kpis` in
  `insights.json` or auto-derived from the first section's KPI specs.
- **Three-tier output path.** `--output` flag → default
  `<input_dir>/<stem>_report.pdf` → `--ask-output` interactive prompt.
- **Re-renderable.** `--build` re-runs Stage 3 from a hand-edited
  `temp/insights.json` without re-extracting.

---

## Tech Stack

### Runtime

| Layer | Technology |
|---|---|
| Language | Python 3.8+ |
| PDF rendering | [ReportLab](https://www.reportlab.com/) ≥ 4.0 |
| PDF rasterisation | [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) ≥ 1.23, optional [pypdfium2](https://pypi.org/project/pypdfium2/) |
| PPTX parsing | [python-pptx](https://python-pptx.readthedocs.io/) ≥ 0.6.21 |
| Image handling | [Pillow](https://python-pillow.org/) ≥ 9.0 |
| Chart rendering | [matplotlib](https://matplotlib.org/) ≥ 3.7 (Agg backend, headless) |
| Text fallback | [markitdown](https://github.com/microsoft/markitdown) ≥ 0.0.1 |
| Optional UI automation | `pywin32`, `pywinauto` (Windows only — listed but commented in [requirements.txt](requirements.txt)) |

### External integrations

| Integration | Role |
|---|---|
| Claude Code | Stage-2 analyst — reads images / live model, writes `temp/insights.json` |
| [Power BI Modeling MCP](https://github.com/microsoft/powerbi-modeling-mcp) | Lets Claude execute DAX against the running Power BI Desktop process |
| Power BI Desktop | Required *only* when using the MCP or `--capture-ui` |

### Build / packaging

- No build system. Python is run directly from source.
- No CI/CD configured (no `.github/workflows`, no `Dockerfile`, no
  `Makefile`). Setup is manual via `pip install -r requirements.txt`
  or `python check_setup.py --auto-install`.

---

## Supported inputs

| Format | Mode | Best for |
|---|---|---|
| `.pdf`  | Image analysis | Quick exports from Power BI Service |
| `.pptx` | Image analysis | "Export to PowerPoint" output |
| `.pbip` | Live DAX (preferred) | Source of truth — measure DAX is exposed cleanly |
| `.pbix` | Live DAX | Requires Power BI Desktop open during the run |

When the optional Power BI Modeling MCP isn't available, `.pbip` and
`.pbix` fall back to image analysis automatically.

---

## Installation

Requires Python 3.8+ on Windows / macOS / Linux. (Some optional
extractor paths — UI automation, PBIP companion PDF export — are
Windows-only.)

```bash
git clone <your-fork-or-clone-url>
cd pbi-to-pdf
pip install -r requirements.txt
```

Or one-shot dependency check + install:

```bash
python check_setup.py --auto-install
```

`check_setup.py` validates Python ≥ 3.8 and the six core packages
listed in [requirements.txt](requirements.txt).

### Optional: deep DAX analysis for `.pbix` / `.pbip`

```bash
python setup_pbi_mcp.py          # download VSIX from VS Marketplace, extract, register in .mcp.json
python setup_pbi_mcp.py --check  # status check only
python setup_pbi_mcp.py --force  # reinstall even if already configured
```

After the MCP is installed, **restart Claude Code** so it picks the
server up. Then open the report in Power BI Desktop before running
the report command — the MCP needs the live model to be reachable.

The setup script writes to `.mcp.json` in the project root. The default
manual install location is `C:\MCPServers\PowerBIModelingMCP\` (see
[setup_pbi_mcp.py:34](setup_pbi_mcp.py#L34)).

---

## Running the Project

### End-to-end (default)

```bash
python run_report.py "C:/path/to/dashboard.pbix"
```

Three stages run back-to-back:

1. **Extract** — `temp/slide_N.png` per page (or `temp/pbip_page_N.png`
   when extracting from a PBIP companion export) plus
   `temp/analysis_request.json`. PBIP/PBIX also writes
   `temp/pbip_context.json` (model + DAX queries).
2. **Analyse** — Claude Code reads the manifest, the screenshots
   and/or the live model, and writes `temp/insights.json`. The CLI
   polls for up to 5 minutes.
3. **Build** — [lib/reporting/pdf_builder.py](lib/reporting/pdf_builder.py)
   renders the A4 PDF.

Default save path: `<input_dir>/<input_stem>_report.pdf`.

### Inside Claude Code

The most idiomatic way to run it is the bundled slash command:

```
/generate-report "C:/path/to/dashboard.pbix"
```

[.claude/commands/generate-report.md](.claude/commands/generate-report.md)
walks Claude through extract → read manifest → analyse → write
`temp/insights.json` → verify → build.

### Stage-only commands

```bash
# Choose where the PDF goes
python run_report.py "dashboard.pdf" --output "out/Q2_report.pdf"

# Be prompted for the save location (interactive TTY only)
python run_report.py "dashboard.pbip" --ask-output

# Steer the analysis focus (passed into Claude's prompt)
python run_report.py "dashboard.pbip" --context "Focus on Finance and MoM change"
python run_report.py "dashboard.pdf"  --context "Audience is the CISO; emphasise security"

# Stage 1 only (extract + print Claude prompt — no polling, no build)
python run_report.py "dashboard.pbix" --prepare

# Stage 3 only (re-render PDF from existing temp/insights.json)
python run_report.py --build --input "dashboard.pbix"

# Stage 2.5 only (verify a hand-edited insights.json)
python run_report.py --verify

# Allow UI automation (PBIP/PBIX only) — sends keystrokes to PBI Desktop
python run_report.py "dashboard.pbip" --capture-ui

# Use a custom insights path
python run_report.py --build --input "dashboard.pbix" --insights "alt.json"
```

All flags are documented in [run_report.py:189](run_report.py#L189).

### What the PDF looks like

A typical report contains, in order:

1. **Cover** — deck title, subtitle, optional KPI strip, source name +
   type, generated timestamp.
2. **Executive summary** — synthesised findings (cards) + recommended
   actions (numbered, severity-coloured).
3. **One section per dashboard page**, split into:
   - **Opener page** — headline, KPI strip, "Key Insights" cards.
   - **Evidence page** (only when supporting visuals exist) — source
     screenshot at a readable size + tables + reconstructed charts.

Tables stay tables, KPI groups render as one strip per page, charts
are kept-together with their titles, and pagination flows to fill
vertical space rather than one-chart-per-page.

---

## Architecture

### High-level flow

```
                                    ┌────────────────────┐
   <source.pbix/.pbip/.pdf/.pptx> ─►│  lib/extraction/   │
                                    │  per-format        │
                                    │  extractor         │
                                    └─────────┬──────────┘
                                              │  writes
                                              ▼
                              temp/analysis_request.json
                              temp/slide_N.png  (one per page)
                              temp/pbip_context.json  (PBIP/PBIX only)
                                              │
                                              │  Claude Code reads,
                                              │  optionally queries DAX
                                              │  via powerbi-modeling MCP
                                              ▼
                              temp/insights.json  (analyst output)
                                              │
                                              │  verify_insights()
                                              ▼
                                    ┌────────────────────┐
                                    │  lib/reporting/    │
                                    │  build_report_data │
                                    │  + pdf_builder     │
                                    └─────────┬──────────┘
                                              ▼
                              <input_stem>_report.pdf
```

### Directory structure

| Path | Purpose |
|---|---|
| [run_report.py](run_report.py) | Single CLI entry point for the whole pipeline |
| [check_setup.py](check_setup.py) | Dependency check / `--auto-install` |
| [setup_pbi_mcp.py](setup_pbi_mcp.py) | Installs and registers the Power BI Modeling MCP |
| [lib/pipeline.py](lib/pipeline.py) | Stage orchestration, MCP detection, Claude prompt, verifier |
| [lib/extraction/](lib/extraction/) | Format-specific extractors |
| ├─ [extractor.py](lib/extraction/extractor.py) | Generic markdown / regex metric extractor |
| ├─ [pdf_extractor.py](lib/extraction/pdf_extractor.py) | PDF → per-page PNG, with content-aware strip splitting |
| ├─ [pbip_extractor.py](lib/extraction/pbip_extractor.py) | TMDL parse, page discovery, DAX query builder, companion image finder, optional UI capture |
| ├─ [pbix_extractor.py](lib/extraction/pbix_extractor.py) | ZIP-based PBIX (reuses PBIP visual parsing) |
| └─ [text_layer_extractor.py](lib/extraction/text_layer_extractor.py) | PPTX text + metric enrichment |
| [lib/analysis/insights.py](lib/analysis/insights.py) | `Insight`, `BulletPoint`, `ChartSpec`, `ChartDataPoint` dataclasses + JSON parsers |
| [lib/reporting/](lib/reporting/) | PDF builder + chart renderer + design system |
| ├─ [report_schema.py](lib/reporting/report_schema.py) | `insights.json` → `ReportData` adapter |
| ├─ [report_generator.py](lib/reporting/report_generator.py) | Orchestrator — loads insights, builds, renders |
| ├─ [pdf_builder.py](lib/reporting/pdf_builder.py) | A4 ReportLab assembly + footer/header chrome |
| ├─ [components.py](lib/reporting/components.py) | Cover, executive summary, section opener, evidence page flowables |
| ├─ [charts.py](lib/reporting/charts.py) | Matplotlib chart renderer (~23 chart types) |
| └─ [theme.py](lib/reporting/theme.py) | Design tokens (typography, colour, spacing, page geometry) |
| [docs/DASHBOARD_READING_RULES.md](docs/DASHBOARD_READING_RULES.md) | Rules Claude must apply before analysis |
| [CLAUDE.md](CLAUDE.md) | Authoritative analyst playbook (insight quality, schemas, anti-patterns) |
| [.claude/commands/generate-report.md](.claude/commands/generate-report.md) | `/generate-report` slash command for Claude Code |
| [.claude/settings.json](.claude/settings.json) | Permissions allowlist for Claude Code (Bash python/pip/grep/ls) |
| [.mcp.json](.mcp.json) | Local MCP server registration (gitignored — machine-specific) |
| `temp/` | Per-run working directory (gitignored — auto-generated, regenerable) |
| `requirements.txt` | Pinned-floor Python dependencies |

### Module responsibilities

- **`lib/pipeline.py`** — the only module that knows about all
  formats. Owns format detection ([detect_file_type](lib/pipeline.py#L41)),
  MCP status announcement ([announce_pbi_mcp_status](lib/pipeline.py#L110)),
  the printable Claude prompts (`_IMAGE_PROMPT_BODY`,
  `_PBIP_PROMPT_BODY`), the polling helper
  ([wait_for_insights](lib/pipeline.py#L553)) and the verifier
  ([verify_insights](lib/pipeline.py#L461)).
- **`lib/extraction/*`** — each module writes to the same
  `temp/analysis_request.json` schema regardless of input. PBIP/PBIX
  additionally write the enriched `temp/pbip_context.json`.
- **`lib/reporting/report_schema.py`** — adapts the analyst-facing
  `insights.json` shape into the `ReportData` shape the renderer
  expects, splitting bullet visuals into `kpis`, `tables`, `charts`,
  and `bullets` buckets.
- **`lib/reporting/components.py`** — flowable factories for cover,
  executive summary, section opener, and evidence page. Owns the
  "should this section get an evidence page?" decision via
  `_section_has_evidence()` and `should_render_source_screenshot()`.
- **`lib/reporting/charts.py`** — matplotlib renderer, headless
  backend, single typography stack (Inter → Helvetica → Arial → DejaVu
  Sans).
- **`lib/reporting/theme.py`** — single source of truth for tokens.
  Other modules import constants — no raw numbers / hex codes
  elsewhere.

---

## Business Logic / Application Logic

### Stage 1 — Extract

Per-format extractors normalise to one schema:

```jsonc
// temp/analysis_request.json
{
  "source_file": "C:/path/to/dashboard.pbix",
  "source_type": "pdf|pptx|pbip|pbix",
  "total_slides": 3,
  "slides": [
    {
      "slide_number": 1,
      "title": "Participation View",
      "image_path": "temp/pbip_page_1.png",  // or null when no image
      "slide_type": "general|trends|leaderboard|health_check|...",
      "source_type": "pbip"
    }
  ]
}
```

For PBIP/PBIX, an additional context file:

```jsonc
// temp/pbip_context.json
{
  "pbip_path": "...",
  "pages":   [ /* visuals, fields, filters */ ],
  "model":   { "tables": [...], "measures": [...], "relationships": [...] },
  "dax_queries": [
    { "page": "Performance View",
      "queries": [ { "purpose": "...", "dax": "EVALUATE ..." } ] }
  ]
}
```

Special handling:

- **PDF strip splitting.** Portrait PDF pages with a width:height ratio
  far from 16:9 are split into N strips at clean horizontal split
  points (background-cap heuristic). Driven by
  [_compute_n_strips](lib/extraction/pdf_extractor.py#L41) and
  [_find_split_point](lib/extraction/pdf_extractor.py#L121).
- **PPTX cover skipping.** Power BI PPTX exports always have a title
  page first; the PPTX path skips slide 0
  ([lib/pipeline.py:192](lib/pipeline.py#L192)).
- **PBIP companion discovery.** When the MCP isn't usable for image
  capture, the PBIP extractor searches for a sibling `.pdf`/`.pptx`
  export. Match priority: exact stem, prefix match (first 15 chars),
  any non-output PDF/PPTX. Self-generated outputs are excluded by
  suffix (`_report`, `_executive`, `-Executive-Insights`) **and** by
  inspecting the first PDF page for the literal `EXECUTIVE REPORT`
  marker that our cover always contains
  ([lib/extraction/pbip_extractor.py:2256](lib/extraction/pbip_extractor.py#L2256)).
- **UI capture (`--capture-ui`).** Off by default. When enabled, the
  PBIP/PBIX extractors can drive Power BI Desktop via UIAutomation —
  PDF export then live screenshot fallback. May steal focus from
  other applications.

### Stage 2 — Analyse (Claude)

Claude is expected to:

1. Read `temp/analysis_request.json`.
2. If `temp/pbip_context.json` exists *and* the MCP is reachable, run
   each `dax_queries[*].queries[*].dax` via
   `mcp__powerbi-modeling__dax_query_operations.execute_query` and use
   the returned values verbatim.
3. Otherwise read `temp/slide_N.png` (or `temp/pbip_page_N.png`,
   `temp/page_N.png`) for each page.
4. Apply the rules in [docs/DASHBOARD_READING_RULES.md](docs/DASHBOARD_READING_RULES.md).
5. Write `temp/insights.json`.

The full analyst playbook (insight quality rules, anti-vanilla
patterns, chart-spec catalogue, fidelity tiers, headline rules,
PBI-visual → ChartSpec mapping) lives in [CLAUDE.md](CLAUDE.md).

### Stage 2.5 — Verify

[verify_insights()](lib/pipeline.py#L461) emits errors and warnings:

| Class | Trigger | Effect |
|---|---|---|
| Error | `insights.json` missing or invalid JSON | Build aborted |
| Error | `slides` array missing or empty | Build aborted |
| Error | `executive_summary` missing | Build aborted |
| Warn | Page has no chart spec (and headline ≠ "Insufficient data for analysis") | PDF will rely on screenshot only |
| Warn | Slide-count mismatch vs `analysis_request.json` | Some pages may be missing |
| Warn | Headline matches a vanilla pattern (`"shows the"`, `"there are"`, `"summary of"`, `"distribution of"`, …) | PDF builds; warning logged |
| Warn | Missing `recommendations` | PDF builds; recommendations strongly encouraged |
| Warn | Generic deck title (empty or `"Executive Insights"`) | PDF builds; warning logged |

The full vanilla pattern list is at
[lib/pipeline.py:454](lib/pipeline.py#L454).

### Stage 3 — Build

[generate_report()](lib/reporting/report_generator.py#L20) loads
`insights.json`, calls
[build_report_data()](lib/reporting/report_schema.py#L209) which:

- splits each page's `insights[].chart` into KPI strip / table list /
  chart list buckets via `_classify_chart()`,
- splits each `insights[].text` on `||` into bold + detail
  ([ReportBullet.from_text](lib/reporting/report_schema.py#L62)),
- parses recommendations for an optional priority prefix
  ([Recommendation.from_text](lib/reporting/report_schema.py#L84)),
- resolves screenshot paths against the temp dir,
- auto-derives `cover_kpis` from the first section's KPIs when not
  explicitly provided.

[pdf_builder.render_report_pdf()](lib/reporting/pdf_builder.py#L85)
then assembles flowables using `BaseDocTemplate` + a single
`Frame`/`PageTemplate`, with a custom `_ChromeCanvas` that adds a
header rule and `Page N / M` footer to every page except the cover.

Trailing `PageBreak` flowables are stripped so the document never ends
on a blank page.

### Output naming and location

| Rule | Path |
|---|---|
| `--output X` given | `X` |
| Default | `<input_dir>/<input_stem>_report.pdf` |
| `--ask-output` and TTY | Prompted, default Enter accepts |

When the input is a directory containing a `.pbip`, the directory's
first `.pbip` stem is used.

---

## API Documentation

There are no HTTP endpoints. The "API" is a small Python module
surface re-exported by `lib.reporting`:

| Function / class | Source | Use |
|---|---|---|
| `generate_report(source_path, output_path, insights_file=..., source_type=None)` | [lib/reporting/report_generator.py:20](lib/reporting/report_generator.py#L20) | Stage 3 entry point — programmatic build |
| `build_report_data(insights_data, source_path=, source_type=, ...)` | [lib/reporting/report_schema.py:209](lib/reporting/report_schema.py#L209) | Adapt insights JSON dict to `ReportData` |
| `render_report_pdf(report, output_path)` | [lib/reporting/pdf_builder.py:85](lib/reporting/pdf_builder.py#L85) | Render a `ReportData` to disk |
| `prepare_for_analysis(source_path, capture_ui=False)` | [lib/pipeline.py:142](lib/pipeline.py#L142) | Stage 1 dispatcher |
| `trigger_claude_analysis(request_file, context=None)` | [lib/pipeline.py:258](lib/pipeline.py#L258) | Print Claude prompt for Stage 2 |
| `wait_for_insights(insights_path, max_wait=300, interval=2)` | [lib/pipeline.py:553](lib/pipeline.py#L553) | Poll for the analyst output |
| `verify_insights(insights_file, request_file)` | [lib/pipeline.py:461](lib/pipeline.py#L461) | Validate before render |
| `detect_file_type(file_path)` | [lib/pipeline.py:41](lib/pipeline.py#L41) | `→ "pdf"\|"pptx"\|"pbip"\|"pbix"` |
| `is_pbi_mcp_ready()` | [lib/pipeline.py:104](lib/pipeline.py#L104) | Silent MCP availability check |
| `parse_chart_spec(raw)`, `parse_bullet_points(raw_list)` | [lib/analysis/insights.py:66](lib/analysis/insights.py#L66) | JSON → dataclasses |

CLI flags are listed under "[Stage-only commands](#stage-only-commands)".
The slash command surface is documented at
[.claude/commands/generate-report.md](.claude/commands/generate-report.md).

---

## Data Model / Database

There is **no database**. All persisted state lives on the filesystem
under `temp/`. The canonical data model is a sequence of JSON files
plus the in-memory Python dataclasses defined in
[lib/analysis/insights.py](lib/analysis/insights.py) and
[lib/reporting/report_schema.py](lib/reporting/report_schema.py).

### `temp/insights.json` — analyst output (canonical)

```jsonc
{
  "deck_title":    "Compelling 5–10 word story-driven title",
  "deck_subtitle": "Platform · Org · Month Year – Month Year",
  "executive_summary": [
    "finding with specific number → business implication"
  ],
  "recommendations": [
    "[High] Action verb + what to do + expected outcome"
  ],
  "cover_kpis": [                       // optional; auto-derived if omitted
    {"type": "kpi", "value": "256", "label": "Active Users"}
  ],
  "slides": [
    {
      "slide_number": 1,
      "title": "Insight-led title (can differ from source)",
      "headline": "Memorable takeaway answering 'so what?'",
      "insights": [
        {
          "text": "Bold line 6-8 words || Supporting evidence with data",
          "chart": { "type": "kpi", "value": "...", "label": "..." }
        },
        { "text": "Second insight || Detail",       "chart": null },
        { "text": "Third insight (action) || Detail", "chart": null }
      ],
      "numbers_used": ["134", "1,275", "11%"]
    }
  ]
}
```

### `ReportData` (in-memory) — build target

```text
ReportData
  ├── metadata        ReportMetadata(source_name, source_type, input_path, generated_at)
  ├── title           str
  ├── subtitle        str
  ├── cover_kpis      List[ChartSpec]
  ├── executive_summary  List[str]
  ├── recommendations    List[Recommendation(text, priority?)]
  └── sections        List[ReportSection]
        ├── slide_number, title, headline
        ├── screenshot_path  (resolved or None)
        ├── bullets   List[ReportBullet(bold, detail)]
        ├── kpis      List[ChartSpec]   # type ∈ {kpi, kpi_row, card, multi_row_card}
        ├── tables    List[ChartSpec]   # type == table
        ├── charts    List[ChartSpec]   # everything else
        └── numbers_used List[str]
```

### `ChartSpec` types

Defined at [lib/analysis/insights.py:20](lib/analysis/insights.py#L20).
Renderer dispatch in [lib/reporting/charts.py](lib/reporting/charts.py):

| Family | Types |
|---|---|
| KPI | `kpi`, `kpi_row`, `card`, `multi_row_card` |
| Bar/column | `bar`, `column`, `bar_stacked`, `bar_stacked_100`, `column_stacked`, `column_stacked_100` |
| Line/area | `line`, `area`, `combo`, `column_line`, `ribbon` |
| Distribution | `pie`, `donut`, `funnel`, `treemap`, `waterfall` |
| Geometric | `scatter`, `bubble`, `radar`, `gauge` |
| Tabular | `table`, `heatmap` |

### `temp/pbip_context.json`

Built only for `.pbip`/`.pbix` inputs. Contains the parsed semantic
model (tables, columns, measures with full DAX, relationships) and a
list of `EVALUATE`-style queries grouped per page. Fields, structure,
and DAX-build logic are in
[lib/extraction/pbip_extractor.py](lib/extraction/pbip_extractor.py).

### Migrations / seed data

Not applicable — no persistent store.

---

## Environment Variables

The runtime does **not** read any custom environment variables. The
following standard Windows variables are *consulted* by the optional
extractor and MCP installer, but no `.env` file is required.

| Variable | Purpose | Required | Default | Used in |
|---|---|---|---|---|
| `USERPROFILE` | Locate `~/.vscode/extensions/` when scanning for an existing MCP install | Optional | Falls back to `Path.home()` | [setup_pbi_mcp.py:56](setup_pbi_mcp.py#L56) |
| `HOME` / OS user dir | Locate `~/.claude/mcp-settings.json` for global MCP config | Optional | `Path.home()` | [lib/pipeline.py:90](lib/pipeline.py#L90) |

There is no `.env.example` and none is needed. No API keys, secrets,
or service credentials are referenced anywhere in the code.

Configuration files instead of env vars:

| File | Purpose | Committed? |
|---|---|---|
| [.mcp.json](.mcp.json) | Project-local MCP server registration (Power BI Modeling) | **No** — gitignored, machine-specific path |
| [.claude/settings.json](.claude/settings.json) | Claude Code permission allowlist | Yes |
| [.claude/settings.local.json](.claude/settings.local.json) | Per-machine Claude overrides | **No** — gitignored |
| `~/.claude/mcp-settings.json` | Claude Code global MCP config | Outside repo |

---

## Testing

**No automated test suite is present.** No `tests/`, `pytest.ini`,
`tox.ini`, or test scripts ship with this repo.

Inferred manual test loop:

1. `python check_setup.py` — verify dependencies.
2. `python run_report.py "<sample.pdf>" --prepare` — confirm
   extraction without invoking Claude.
3. Hand-write or hand-edit a minimal `temp/insights.json` covering the
   schema in [Data Model / Database](#data-model--database).
4. `python run_report.py --verify` — exercises
   [verify_insights()](lib/pipeline.py#L461).
5. `python run_report.py --build --input "<sample.pdf>"` — render the
   PDF and inspect visually.

For PBIP/PBIX paths, also:

6. `python setup_pbi_mcp.py --check` — confirm MCP registration.
7. Open the file in Power BI Desktop, run a small DAX query through
   the MCP from inside Claude Code, confirm results.

> Future improvement: add `pytest` smoke tests for the verifier and
> `build_report_data` adapter — both are pure functions and easy to
> cover.

---

## Deployment

There is no deployment target. `pbi-to-pdf` is a local CLI:

- No `Dockerfile` / container packaging.
- No CI/CD pipelines (`.github/workflows`, `.circleci`, GitLab
  pipelines).
- No cloud configuration (no `serverless.yml`, no Terraform, no
  Pulumi, no `cdk.json`).
- No release automation. The PDF is the artefact; the script lives
  alongside the user's Power BI files.

Distribution is "clone the repo, install dependencies, run the
script". For team-wide use, the recommended pattern is a shared Git
remote + `python check_setup.py --auto-install` on first run.

---

## Security / Permissions

No authentication or authorisation surface — this is a local CLI that
reads user-supplied dashboard files and writes PDFs to the local
filesystem.

Security-relevant aspects:

- **Local file access only.** All inputs are paths the user passes
  in; all outputs are paths under `<input_dir>` or wherever
  `--output` points.
- **MCP is local.** The Power BI Modeling MCP runs as a local process
  and connects only to a Power BI Desktop instance on the same
  machine. The MCP is registered with `--readonly --skipconfirmation`
  flags ([setup_pbi_mcp.py:169](setup_pbi_mcp.py#L169)) — read-only
  DAX queries; no model mutation.
- **Claude Code permissions.** [.claude/settings.json](.claude/settings.json)
  grants Bash access only to `python`, `pip`, common read tools
  (`cat`, `head`, `find`, `grep`, `ls`, `wc`), Windows process tools
  (`tasklist`, `netstat`), and PowerShell. WebFetch is restricted to
  `github.com` and `raw.githubusercontent.com` (used by
  `setup_pbi_mcp.py` for downloading the VSIX).
- **UI automation is opt-in.** `--capture-ui` is off by default
  because it sends keystrokes and steals window focus.
- **Self-output filtering.** The companion-export finder explicitly
  refuses to ingest the script's own previous outputs (suffix +
  `EXECUTIVE REPORT` text-marker check) so the report never embeds
  pages of itself as "source dashboard" evidence.
- **No secrets in code.** No API keys, tokens, or connection strings
  are checked in or read at runtime.
- **Input validation.** `detect_file_type()` strictly whitelists the
  four supported extensions; everything else raises `ValueError`.

---

## Error Handling & Logging

There is no structured logging framework. All status output is
human-readable `print()` to stdout, prefixed with `OK`, `WARN`, or
`ERROR`. Notable patterns:

- **JSON tolerance.**
  [_load_mcp_server_config()](lib/pipeline.py#L70) accepts the
  unescaped Windows backslashes Claude Code writes natively into
  `.mcp.json` and re-escapes before parsing.
- **Backend failover.** PDF extraction tries PyMuPDF (`fitz`) first,
  falls back to `pypdfium2`, raises `IOError` only if both fail
  ([lib/extraction/pdf_extractor.py:391](lib/extraction/pdf_extractor.py#L391)).
- **Per-page failure isolation.** A page that fails to render or has
  a malformed chart spec is skipped — the rest of the report
  continues.
- **MCP unreachable.** `announce_pbi_mcp_status()` prints a banner but
  never raises. The pipeline downgrades to image mode.
- **Insights polling.** `wait_for_insights()` times out after 5
  minutes and prints the next-step command rather than hanging.
- **Verifier.** Errors block the build; warnings are printed and
  build proceeds.
- **Trailing PageBreak strip.** `pdf_builder` removes trailing
  `PageBreak` flowables so the document never ends on a blank page.
- **Encoding safety.** PBIP TMDL files are read with
  `errors='replace'`; extractor titles are sanitised to remove
  emoji / supplementary-plane glyphs that the Windows console can't
  encode.

There is no remote logging, no metrics emission, and no monitoring
hook.

---

## Known Constraints

- **Stage 2 requires Claude Code.** This is by design — Claude is the
  analyst — but it does mean the pipeline cannot run unattended.
  `wait_for_insights()` will time out after 5 minutes if no insights
  file appears.
- **Offline TMDL doesn't support DAX execution.** A `.pbip` whose
  semantic model is on disk but not loaded into a running Power BI
  Desktop will be detected by the extractor but the MCP queries will
  fail. The fallback is image analysis from a sibling export.
  (Observed in real runs; surfaced as the "DAX execution failed" path.)
- **PBIX `DataModel` is XPress9-compressed.** Modern PBIX files cannot
  expose model metadata from the ZIP alone. The extractor parses
  `DataModelSchema` JSON when older PBIX files include it; otherwise
  the model is empty
  ([lib/extraction/pbix_extractor.py:1](lib/extraction/pbix_extractor.py#L1)).
- **UI automation is Windows-only.** `--capture-ui` and the
  companion-export-via-Power-BI-Desktop path require `pywin32` /
  `pywinauto` / `pypdfium2`; these are commented in
  [requirements.txt](requirements.txt) and listed only in the install
  hint.
- **Companion match heuristic.** The companion finder uses the first
  15 characters of the `.pbip` stem as a prefix match. Reports with
  near-identical names in the same folder may match the wrong file.
  Mitigated by the `EXECUTIVE REPORT` content check, but not 100%
  proof against arbitrary user-named PDFs.
- **No automated tests.**
- **No CI/CD.**
- **`temp/` is shared per project.** Concurrent runs on the same
  checkout will clobber each other's `analysis_request.json` /
  `insights.json`.
- **`numbers_used` is informational only.** The current renderer does
  not surface a numbered appendix; the field is preserved on
  `ReportSection` but unused in the layout. (Was intended for an
  appendix that was removed in the deck-cleanup refactor.)

---

## Future Improvements

- **Add a smoke-test suite.** `pytest` tests for
  `verify_insights()`, `build_report_data()`, the PDF strip splitter,
  and `_find_companion_export()` would all be pure-function
  green-field tests.
- **Run `verify` automatically as a pre-commit hook** to keep
  hand-edited `insights.json` files from drifting from the schema.
- **Re-introduce the numbers appendix** so `numbers_used` actually
  shows up in the PDF.
- **Cross-platform `--capture-ui`.** The current implementation is
  pinned to Win32 UIAutomation. A pyautogui or AppleScript fallback
  would broaden the OS support.
- **Schema-validate `insights.json`.** Today the verifier checks for
  semantic gaps. A JSON Schema (or `pydantic` model) would catch
  type-level mistakes earlier.
- **Per-run temp directory.** Today `temp/` is shared. Adding
  `temp/<run-uuid>/` would make concurrent runs safe.
- **Companion-finder UX.** Surface which file was selected (or why
  none was) so users can drop in a manually-renamed export and trust
  the choice.
- **Replace the `print()` status output with `logging`** so verbose
  vs. quiet modes are easy to toggle and machine-readable logs are
  available.
- **Package distribution.** Today `pip install` only works against a
  clone. A `pyproject.toml` + a console-script entry point
  (`pbi-to-pdf = run_report:main`) would simplify distribution.

---

## Customising the analysis

There are three ways to influence what Claude focuses on:

1. **`--context "..."`** — free-text steering injected into the
   Claude prompt. Best for "frame for the CFO" or "spotlight HR".
2. **Edit `temp/insights.json` and rebuild** — run
   `python run_report.py --build --input "<source>"` to re-render any
   hand-tweaked insights. Useful when a stakeholder wants to swap a
   headline or add a recommendation.
3. **Skip stage 1 in subsequent runs** — once `temp/` is populated,
   `--build` is the fast path.

---

## Errors & fallbacks (cheat-sheet)

| Situation | What happens |
|---|---|
| Power BI MCP not installed | Warning printed; PBIP/PBIX run with image analysis |
| Power BI Desktop not open | MCP queries fail; rerun with the project open |
| `temp/insights.json` never appears | After 5 minutes the run exits with the next-step command |
| `--verify` reports errors (e.g. missing `executive_summary`) | Build aborts; fix `temp/insights.json` and re-run |
| `--verify` reports warnings only | Build continues; warnings are printed |
| A page screenshot can't be rendered | The PDF section omits it and continues with insights/charts |
| A chart spec is malformed | That spec is skipped; the page still renders |
| Companion export missing for `.pbip` | Either run `--capture-ui`, or export PDF manually next to the `.pbip`, or rely on DAX-only |

`temp/` is treated as a per-run working directory — safe to delete
between runs; everything in it is regenerable.

---

## Contribution Guidelines

> No `CONTRIBUTING.md` exists in the repo. The following is inferred
> from the existing code style and is offered as a starting baseline.

- **Python style.** PEP 8, 4-space indents, type hints on public
  function signatures, dataclasses for record types. Module
  docstrings explain the *why*; in-function comments explain the
  *what* only when non-obvious.
- **No new top-level dependencies** without updating
  [requirements.txt](requirements.txt) and
  [check_setup.py](check_setup.py).
- **Design tokens go in [lib/reporting/theme.py](lib/reporting/theme.py).**
  Components must import constants — no raw hex codes or pixel
  numbers in component files.
- **Branching.** Work on a feature branch, target `main`. Squash on
  merge.
- **Commits.** Short imperative subject ("fix companion-finder skips
  self-generated reports"). Reference relevant files / line numbers
  in the body where useful.
- **Pull requests.** Include a one-paragraph "what" + "why" + a brief
  manual-test plan, since there's no automated suite.
- **Don't touch `temp/`** in commits — it's gitignored for a reason.

---

## What was removed in this refactor

This repo previously also generated executive PowerPoint decks and
shipped a parallel Copilot Chat workflow. Those paths were cut to make
the report path coherent.

- `convert_dashboard.py`, `run_pipeline.py` — replaced by `run_report.py`
- `lib/rendering/` — PPTX builder, native chart builder, PPTX validator
- `COPILOT.md`, `.github/copilot-instructions.md`, `requirements-copilot.txt`
- `convert-to-exec-deck.cmd`, `install-alias.ps1`
- `Example-Storyboard-Analytics.pptx`, `demo.gif`
- `lib/extraction/ocr_extractor.py` (Copilot-only path)
- Deck-only docs in `docs/` (the analyst-facing
  `DASHBOARD_READING_RULES.md` is preserved)

If you need the deck-generation path, check out a tag from before this
refactor.

---

## License

MIT — see [LICENSE](LICENSE).
