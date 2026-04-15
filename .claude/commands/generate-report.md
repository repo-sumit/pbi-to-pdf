Generate an A4 PDF report from a Power BI dashboard export.

## Usage

```
/generate-report "C:\path\to\dashboard.pbix"
/generate-report "C:\path\to\dashboard.pbip"
/generate-report "C:\path\to\dashboard.pdf"
/generate-report "C:\path\to\dashboard.pptx"
```

The argument `$ARGUMENTS` is the path to the source file or PBIP folder.

---

## What to do

### Stage 1 — Extract

```bash
python run_report.py "$ARGUMENTS" --prepare
```

This writes:
- `temp/analysis_request.json` (page list + metadata)
- `temp/slide_N.png` (one PNG per page)
- `temp/pbip_context.json` (only for PBIP/PBIX — model + DAX queries)

If the command fails because dependencies are missing, install them once:

```bash
pip install -r requirements.txt
python run_report.py "$ARGUMENTS" --prepare
```

### Stage 2 — Read the analysis request

```
Read temp/analysis_request.json
```

If `temp/pbip_context.json` exists, also read it — it lists every measure
with its DAX formula and a pre-built query per page. Execute the queries
through `mcp__powerbi-modeling__dax_query_operations` and treat the
returned values as authoritative (never estimate from screenshots when
DAX is available).

### Stage 3 — Analyse each page

For every page in the request:

```
Read temp/slide_N.png
```

Act as a senior analyst advising an IT decision maker.

For each page:
- Extract every visible number with EXACT units ("13K" not "13,000").
- Only mention platforms / teams / features visible on this page.
- Generate a memorable headline that answers "so what?" — never a data dump.
- Generate up to 3 insights formatted `"Bold line || Supporting evidence"`.
- Use opportunity framing — never crisis or failure language.
- Where the data supports it, attach a `"chart"` spec so the PDF renders a
  vector chart instead of relying on the screenshot. Tables MUST stay
  tables (`"type": "table"`) — never collapse to bar/column.

Across the whole report:
- `deck_title` — compelling 5–10 word story-driven title.
- `deck_subtitle` — `"[Platform] · [Org] · [Date range]"`.
- `executive_summary` — 5 bullets, highest business impact first.
- `recommendations` — 3–5 specific actions traceable to dashboard data.

### Stage 4 — Save insights

Write everything to `temp/insights.json`. The schema is documented in
`CLAUDE.md`.

### Stage 5 — Verify (mandatory)

```bash
python run_report.py --verify
```

If warnings appear, fix them in `temp/insights.json` and re-run `--verify`
until clean:
- **Missing chart spec** — add a `"chart"` to at least one insight on that page.
- **Generic headline** — rewrite to pass the "would a VP forward this?" test.
- **Slide count mismatch** — make sure every page in `analysis_request.json`
  has a matching entry in `insights.json`.

### Stage 6 — Build the PDF

```bash
python run_report.py --build --input "$ARGUMENTS"
```

The default save location is `<input_dir>/<input_stem>_report.pdf`. Pass
`--output` to override.

### Stage 7 — Confirm

Tell the user:
- The output PDF path
- How many pages were analysed
- The deck title that was used
