# Claude Code instructions — pbi-to-pdf

## What this project is

A Claude Code-first tool that turns a Power BI dashboard export into a
polished portrait **A4 PDF report** that an executive can read, print,
or forward.

You — Claude — are the analyst in the loop. The CLI extracts dashboard
pages and a PDF renderer turns your insights into the final report; in
between, **you** read the screenshots (or query the live model via MCP)
and write `temp/insights.json`.

No API key is needed. The whole pipeline runs from the active Claude
Code session.

---

## Supported inputs

| Format | Mode | Notes |
|---|---|---|
| `.pdf`  | Image analysis | Each page becomes one PNG |
| `.pptx` | Image analysis | Power BI "Export to PowerPoint" output |
| `.pbip` | Live DAX (preferred) | Best — measure DAX is exposed cleanly |
| `.pbix` | Live DAX | Requires Power BI Desktop open |

Live DAX requires the optional `powerbi-modeling` MCP server (see
`setup_pbi_mcp.py`). Without it, `.pbip` and `.pbix` fall back to image
analysis automatically.

---

## End-to-end command

```bash
python run_report.py "C:/path/to/dashboard.pbix"
```

This runs the whole pipeline:

1. **Extract** — pages → `temp/slide_N.png`, manifest → `temp/analysis_request.json`,
   PBIP/PBIX also writes `temp/pbip_context.json`.
2. **Analyse (you)** — read the manifest + screenshots / DAX, write `temp/insights.json`.
3. **Build** — render the A4 PDF report.

Stage 2 is **your** job — the script will print a Claude-facing prompt
and then poll `temp/insights.json` until it appears.

### Stage-only commands

```bash
python run_report.py "dashboard.pbix" --prepare       # Stage 1 only
python run_report.py --verify                          # Stage 2.5 only
python run_report.py --build --input "dashboard.pbix"  # Stage 3 only
```

The build stage runs `--verify` automatically and aborts on errors.

---

## Your analysis task

1. `Read temp/analysis_request.json`
2. If `temp/pbip_context.json` exists, read it and execute its DAX
   queries via `mcp__powerbi-modeling__dax_query_operations.execute_query`.
3. Otherwise `Read temp/slide_N.png` for each page listed.
4. Act as a senior analyst advising an IT decision maker.
5. Write `temp/insights.json`.

> **Read `docs/DASHBOARD_READING_RULES.md` before analysing.**

### `temp/insights.json` schema

```json
{
  "deck_title":    "Compelling 5–10 word story-driven title",
  "deck_subtitle": "Platform · Org · Month Year – Month Year",
  "executive_summary": [
    "Finding with specific number → business implication"
  ],
  "recommendations": [
    "Action verb + what to do + expected outcome"
  ],
  "slides": [ /* one object per page — see below */ ]
}
```

### Per-page object

```json
{
  "slide_number": 1,
  "title": "Insight-led title (can differ from the source)",
  "headline": "Memorable takeaway answering 'so what?' — not a data dump",
  "insights": [
    {"text": "Bold line 6-8 words || Supporting evidence with data",
     "chart": { /* spec or null */ }},
    {"text": "Second insight || Detail",          "chart": null},
    {"text": "Third insight (action) || Detail",  "chart": null}
  ],
  "numbers_used": ["134", "1,275", "11%"]
}
```

The `||` separator splits the bold heading (rendered large) from the
normal-weight detail. Maximum **3 insights per page**.

**Insight progression (recommended order):**

1. *Scale / scope* — what is the magnitude of the finding?
2. *Pattern / opportunity* — what is the actionable pattern in the data?
3. *Action* — what should the executive do next?

**Missing data:** if a page has no extractable numbers, set
`headline` to `"Insufficient data for analysis"`, leave
`numbers_used` empty, and do not invent insights to fill space.

---

## Deck-level fields

### `deck_title` — 5–10 words, compelling, positively framed

- ✅ "Copilot Impact Confirmed: $14.7M in Value with 84% Active Adoption"
- ✅ "From Reach to Routine: Building AI Habits Across the Organization"
- ❌ "Executive Insights" / "Copilot Usage Report" / any negative framing

### `deck_subtitle`

`"[Platform 1] · [Platform 2] · [Org] · [Date range]"` — always populate.

### `executive_summary` — 5 bullets

Synthesise across **all** pages, highest business impact first, each
with specific numbers, format: `"finding → implication"`.

### `recommendations` — 3–5 specific actions

Traceable to dashboard data.
- ✅ "Pilot agent training with HR Generalists (140 actions/user) to establish best practices"
- ❌ "Improve training"

---

## Chart specs

A chart spec turns into a vector chart in the PDF. Without one, the
section falls back to the source dashboard screenshot.

**Every page that has quantitative data should ship at least one chart
spec.** Common misses: KPI cards encoded as text, tables paraphrased
into prose, small charts overlooked.

### Chart types

| Visual               | `type` |
|---|---|
| Single KPI           | `"kpi"` |
| Row of KPIs          | `"kpi_row"` |
| Horizontal bars      | `"bar"` |
| Vertical columns     | `"column"` |
| Stacked bars         | `"bar_stacked"` / `"bar_stacked_100"` |
| Stacked columns      | `"column_stacked"` / `"column_stacked_100"` |
| Trend line(s)        | `"line"` |
| Filled area          | `"area"` |
| Columns + line       | `"combo"` (dual-axis) |
| Waterfall            | `"waterfall"` |
| Pie / Donut          | `"pie"` / `"donut"` |
| Table                | `"table"` — **never collapse to bar/column** |
| Heatmap              | `"heatmap"` |
| Treemap              | `"treemap"` |
| Scatter              | `"scatter"` |
| Funnel               | `"funnel"` |
| Gauge                | `"gauge"` |

### Examples

```json
// kpi_row — primary metrics summary
{"type": "kpi_row", "items": [
  {"value": "256",   "label": "Active Users"},
  {"value": "33.77", "label": "Weekly Actions"},
  {"value": "52.6%", "label": "Power Users"}
]}

// bar — ranking
{"type": "bar", "title": "Weekly Actions by Manager",
 "highlight": "Dana Bourque",
 "data": [{"label": "Dana Bourque", "value": 48.95},
          {"label": "Matt Sheard",  "value": 38.09}]}

// table — preserve as a table, never as bars
{"type": "table",
 "columns": ["Manager", "Users", "Weekly Actions"],
 "rows":   [["Dana Bourque", "4",  "48.95"],
            ["Matt Sheard",  "52", "38.09"]]}

// line — trend
{"type": "line", "title": "Monthly Active Users",
 "series": [{"name": "Agents",
             "points": [{"x": "Jan", "y": 120}, {"x": "Feb", "y": 145}]}]}

// donut
{"type": "donut", "title": "Usage Distribution",
 "data": [{"label": "Power",   "value": 52.6},
          {"label": "Regular", "value": 31.2},
          {"label": "Light",   "value": 16.2}]}

// waterfall
{"type": "waterfall", "title": "Revenue Bridge",
 "data": [{"label": "Q1 Revenue", "value": 100, "color": "#003278"},
          {"label": "New Sales",  "value":  30},
          {"label": "Churn",      "value": -12},
          {"label": "Q2 Total",   "value": 118, "color": "#003278"}]}
```

### Fidelity tiers

| Tier | Types | Action |
|---|---|---|
| **High** — always reconstruct | `kpi`, `kpi_row`, `bar`, `column`, `donut`, `pie`, `table` | Always include |
| **Medium** — reconstruct with care | `line`, `area`, `column_stacked`, `bar_stacked`, `treemap`, `funnel` | Verify series shape |
| **Low** — prefer screenshot | `scatter`, `combo`, `heatmap`, `ribbon` | Use `"chart": null` unless DAX provides exact data |

---

## PBIP / PBIX deep-analysis workflow

When `temp/pbip_context.json` exists, query the live model via MCP
instead of estimating from screenshots.

1. `Read temp/pbip_context.json` — pages, visuals, measures (with full
   DAX), pre-built `dax_queries`.
2. Execute every query via
   `mcp__powerbi-modeling__dax_query_operations.execute_query(database="...", dax="EVALUATE ...")`.
3. **Every number in insights MUST come from a DAX result, not visual
   estimation.**
4. If DAX returns no rows for a page, fall back to `temp/slide_N.png`.
5. If both are empty, mark the page `"Insufficient data for analysis"`.

### PBI visual → ChartSpec mapping

| PBI visual type | ChartSpec `type` |
|---|---|
| `tableEx` / `table` / `pivotTable` / `matrix` | `"table"` |
| `barChart` / `clusteredBarChart` | `"bar"` |
| `stackedBarChart` / `hundredPercentStackedBarChart` | `"bar_stacked"` / `"bar_stacked_100"` |
| `columnChart` / `clusteredColumnChart` | `"column"` |
| `stackedColumnChart` / `hundredPercentStackedColumnChart` | `"column_stacked"` / `"column_stacked_100"` |
| `lineChart` | `"line"` |
| `areaChart` / `stackedAreaChart` | `"area"` |
| `lineClusteredColumnComboChart` | `"combo"` |
| `donutChart` / `pieChart` | `"donut"` / `"pie"` |
| `card` / `multiRowCard` | `"kpi"` / `"kpi_row"` |
| `waterfallChart` | `"waterfall"` |
| `scatterChart` | `"scatter"` |
| `treemap` | `"treemap"` |
| `filledMap` / `map` / `shapeMap` | `"heatmap"` |

**MANDATORY — DAX is authoritative.** If DAX returns 89% and the visual
shows 87%, write 89%.

**MANDATORY — metric label = DAX formula + active filter.** Never add
a time unit ("per week") that isn't in the DAX or in an active page filter.

| DAX formula | Active filter | Correct label |
|---|---|---|
| `DIVIDE([S],[U])` | Slicer Mar–Jun 2025 | "sessions per user (Mar–Jun 2025)" |
| `DIVIDE([S],[U])` | (none) | "sessions per user (selected period)" |
| `DIVIDE([S],[U]) / [Weeks]` | (any) | "sessions per user per week" |

---

## Critical data rules

### Metric segment isolation

**Never mix numbers from different platform segments** (Licensed /
Unlicensed / Agent). OCR and `text_metrics` flatten all segments into
one stream — always read the label below each number in the actual
image to confirm pairing.

### Units and labels

- **Match units exactly:** if the dashboard shows `13K`, write `13K`,
  not `13,000` or `13`.
- **Only cite visible entities:** can you point to the team / platform
  / feature name on this exact page? Yes → cite it. No → don't.

### Pre-analysis checklist (run for every page)

- [ ] Filter selections identified (active = highlighted/dark)
- [ ] All table row/column labels read
- [ ] Chart axis scales and units checked
- [ ] Legend colours verified
- [ ] Every number matched to its label

---

## Insight quality rules

### Headline
Clear, memorable "so what?" — not a data dump of numbers.
Numbers belong in the supporting insights as evidence, not the headline.

### Do
- **Opportunity framing:** "opportunity to expand from 11%" ✅ — "only 11% shows deployment failure" ❌
- **Exact units:** "217 prompts/user (5.7× average)" ✅ — "some users show higher engagement" ❌
- **Answer "so what?":** every insight implies an action.
- **Visibility rule:** only mention platforms/teams/features visible on
  this specific page.
- **VP-forward test:** if a VP wouldn't forward this bullet to their
  boss, rewrite it.

### Don't
- Critical / extreme language: "crisis", "catastrophically", "blocking"
  → use "opportunity", "challenge", "limiting".
- Mention entities not visible on this specific page.
- Generic statements that could apply to any dashboard.
- Numbers you can't point to on the dashboard.
- Force insights on blank pages → mark "Insufficient data for analysis".

### Anti-vanilla transformations

- ❌ "There are 1,275 active users"
  ✅ "1,275 active users = 68% penetration — 480-seat expansion opportunity"
- ❌ "Usage varies by department"
  ✅ "Operations outpaces Marketing 3:1 on weekly actions — replicate their onboarding playbook"
- ❌ "Skills are distributed across categories"
  ✅ "3 of 8 skill categories account for 80% of confirmations — focus L&D on the long tail"

---

## Pre-build quality checklist

Run before saving `temp/insights.json`:

- ✅ Units match exactly (13 vs 13K vs 13M — use what's shown)
- ✅ All entities mentioned are visible on that specific page
- ✅ Insights concise (1–2 sentences each, not paragraphs)
- ✅ Opportunity framing (not failure / crisis language)
- ✅ Every number traceable to the dashboard
- ✅ No vanilla statements (pass VP-forward test)
- ✅ Every page with quantitative data has ≥ 1 chart spec
- ✅ `deck_title` populated and compelling
- ✅ `deck_subtitle` populated with scope and date range
- ✅ Executive summary covers ALL pages, highest impact first
- ✅ Recommendations are specific actions traceable to numbers

---

## Output specs

- A4 portrait (210 mm × 297 mm), 0.55″ margins
- Helvetica family, blue accent colours (cover #002060, accent #0072C6)
- Page sequence: cover → executive summary → recommendations →
  one section per dashboard page (headline, KPI strip, screenshot,
  insights, tables, charts) → appendix (numbers cited per page)

---

## Files reference

| Path | Purpose |
|---|---|
| `run_report.py` | Single CLI for the entire pipeline |
| `lib/pipeline.py` | Stage orchestration + Claude prompt + verifier |
| `lib/extraction/` | PBIP / PBIX / PDF / PPTX extractors |
| `lib/analysis/insights.py` | `Insight`, `BulletPoint`, `ChartSpec` dataclasses |
| `lib/reporting/` | A4 PDF builder + matplotlib chart renderer |
| `setup_pbi_mcp.py` | Installs the optional Power BI Modeling MCP |
| `check_setup.py` | Verifies Python deps |
| `temp/` | Working directory — auto-generated, not committed |
| `docs/DASHBOARD_READING_RULES.md` | **Read before any analysis** |
