# pbi-to-pdf

**Power BI dashboards → polished A4 PDF reports, designed for Claude Code.**

You point the CLI at a Power BI export, and Claude Code (running in your
terminal) reads each dashboard page, generates analyst-grade insights,
and the toolkit renders them into a portrait A4 PDF you can hand to an
executive.

No Anthropic API key is required — the analysis runs inside your active
Claude Code session.

---

## What this is (and isn't)

| | |
|---|---|
| **Primary output** | A portrait A4 PDF report (`<input>_report.pdf`) |
| **Primary driver** | Claude Code as the senior analyst in the loop |
| **Optional power-up** | Live DAX queries via the Power BI Modeling MCP for `.pbix` and `.pbip` |
| **Not a deck generator** | The deck-generation path was removed — this is a report tool |

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

## Install

Requires Python 3.8+.

```bash
git clone https://github.com/repo-sumit/pbi-to-pdf.git
cd pbi-to-pdf
pip install -r requirements.txt
```

Or one-shot:

```bash
python check_setup.py --auto-install
```

### Optional: deep DAX analysis for `.pbix` / `.pbip`

```bash
python setup_pbi_mcp.py          # download + register the MCP server
python setup_pbi_mcp.py --check  # confirm it's wired up
```

After the MCP is installed, **restart Claude Code** so it picks the
server up. Then open the report in Power BI Desktop before running
the report command — the MCP needs the live model to be reachable.

---

## Generate a report

The single end-to-end command:

```bash
python run_report.py "C:/path/to/dashboard.pbix"
```

This runs three stages:

1. **Extract** — `temp/slide_N.png` per page + `temp/analysis_request.json`.
   PBIP/PBIX also writes `temp/pbip_context.json` (model + DAX queries).
2. **Analyse** — Claude Code reads the manifest, the screenshots and/or
   the live model, and writes `temp/insights.json`.
3. **Build** — `lib/reporting/pdf_builder.py` renders the A4 PDF.

Default save path: `<input_dir>/<input_stem>_report.pdf`.

### Inside Claude Code

The most idiomatic way to run it is the bundled slash command:

```text
/generate-report "C:/path/to/dashboard.pbix"
```

`.claude/commands/generate-report.md` walks Claude through extract →
read manifest → analyse → write `temp/insights.json` → verify → build.

### Variants

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
```

---

## What the PDF looks like

A typical report contains, in order:

1. **Cover** — deck title, subtitle, source name + type, generated timestamp.
2. **Executive summary** — five synthesised findings, highest impact first.
3. **Recommendations** — 3–5 specific, data-grounded next steps.
4. **One section per dashboard page**:
   - Page title + headline (the "so what?")
   - KPI strip (when the page exposes scalar metrics)
   - Source dashboard screenshot (with caption)
   - "Key insights" — up to 3 bullets in `Bold || Detail` format
   - Tables and charts rendered as crisp vector visuals
5. **Appendix** — source metadata + every number cited, by page (so a
   reviewer can trace each figure back to the dashboard).

Tables stay tables, KPI groups render as one strip per page, charts
are kept-together with their titles, and pagination flows to fill
vertical space rather than one-chart-per-page.

---

## How the deep-analysis path works

When `.pbip` or `.pbix` is the input and the Power BI Modeling MCP is
ready, the extractor walks the model and writes `temp/pbip_context.json`
with:

- every page and its visuals,
- every measure with its full DAX formula,
- a pre-built `EVALUATE` query per page.

Claude executes those queries through
`mcp__powerbi-modeling__dax_query_operations.execute_query` and uses the
returned values verbatim — never visual estimates. The build stage
renders matplotlib charts directly from those numbers, so the PDF is
trace-back-able to the live model.

If the MCP isn't installed, the script prints a clear warning and falls
back to image analysis. Nothing breaks; only the precision drops.

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

## Project layout

| Path | Purpose |
|---|---|
| `run_report.py` | Single CLI entry point for the whole pipeline |
| `lib/pipeline.py` | Stage orchestration, MCP detection, Claude prompt, verifier |
| `lib/extraction/` | Format-specific extractors (PDF / PPTX / PBIP / PBIX) |
| `lib/analysis/insights.py` | `Insight`, `BulletPoint`, `ChartSpec` dataclasses |
| `lib/reporting/pdf_builder.py` | A4 ReportLab renderer |
| `lib/reporting/report_schema.py` | `insights.json` → `ReportData` adapter |
| `lib/reporting/charts.py` | Matplotlib chart-spec → PNG renderer |
| `setup_pbi_mcp.py` | Installs the Power BI Modeling MCP server |
| `check_setup.py` | Dependency check / auto-install |
| `CLAUDE.md` | Authoritative analyst playbook for Claude Code |
| `docs/DASHBOARD_READING_RULES.md` | Page-reading rules to apply before analysis |
| `.claude/commands/generate-report.md` | `/generate-report` slash command |
| `temp/` | Working directory (auto-generated, gitignored) |

---

## Errors & fallbacks

| Situation | What happens |
|---|---|
| Power BI MCP not installed | Warning printed; PBIP/PBIX run with image analysis |
| Power BI Desktop not open | MCP queries fail; rerun with the project open |
| `temp/insights.json` never appears | After 5 minutes the run exits with the next-step command |
| `--verify` reports errors (e.g. missing `executive_summary`) | Build aborts; fix `temp/insights.json` and re-run |
| `--verify` reports warnings only | Build continues; warnings are printed |
| A page screenshot can't be rendered | The PDF section omits it and continues with insights/charts |
| A chart spec is malformed | That spec is skipped; the page still renders |

`temp/` is treated as a per-run working directory — safe to delete
between runs; everything in it is regenerable.

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

MIT — see [`LICENSE`](LICENSE).
