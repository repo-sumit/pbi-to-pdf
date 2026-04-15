# PBI to PDF

Convert Power BI dashboards into PDF reports and executive PowerPoint decks with Claude Code or GitHub Copilot Chat.

![Demo](demo.gif)

## What this project does

- Generates PDF reports from the same extraction and analysis pipeline
- Generates executive PPTX decks from `.pdf`, `.pptx`, `.pbip`, and `.pbix` inputs
- Supports screenshot-based output or vector chart rendering with `--vector-charts`
- Accepts business context so the analysis can focus on a team, theme, or time period
- Uses Power BI MCP for exact-value analysis when working with `.pbip` or `.pbix`

## Input modes

| Mode | Inputs | Data source | Typical use |
|---|---|---|---|
| Quick mode | `.pdf`, `.pptx` | Page and slide images plus OCR | Fastest path from exported dashboards to PDF reports or PPTX decks |
| Deep analysis mode | `.pbip`, `.pbix` | Live DAX queries via MCP when available, otherwise image fallback | Best when you want exact numbers and richer context in the final output |

## Requirements

- Python 3.8+
- One assistant workflow:
  - Claude Code
  - VS Code with GitHub Copilot Chat
- Optional for deep analysis: Power BI Desktop and Power BI MCP

## First-time setup

Clone your repository and install the dependency profile you plan to use.

```bash
git clone https://github.com/repo-sumit/pbi-to-pdf.git
cd pbi-to-pdf
```

Choose one dependency profile:

```bash
# Claude Code / general CLI usage
python check_setup.py --profile claude --auto-install

# GitHub Copilot Chat usage
python check_setup.py --profile copilot --auto-install
```

Manual install also works if you prefer:

```bash
# Claude / general CLI usage
pip install -r requirements.txt

# Copilot-oriented extraction extras
pip install -r requirements-copilot.txt
```

Optional for `.pbip` and `.pbix` deep analysis:

```bash
python setup_pbi_mcp.py
python setup_pbi_mcp.py --check
```

## First run

After setup, start with the output you want.

### First PDF report

```bash
python run_report.py --input "C:\path\to\dashboard.pbix"
```

### First PowerPoint deck

```bash
python convert_dashboard.py "C:\path\to\dashboard.pbip"
```

### First run with an assistant

### Claude Code

```text
claude
> create exec deck "C:\path\to\dashboard.pdf"
```

### GitHub Copilot Chat

1. Open the folder in VS Code.
2. Open Copilot Chat and switch to Agent mode.
3. Prompt:

```text
Create exec deck "C:\path\to\dashboard.pdf"
```

## Regular runs (after setup)

For day-to-day use, you can skip setup and run the script you need directly.

### PDF output

```bash
# Auto-save next to the input as <stem>_report.pdf
python run_report.py --input "C:\path\to\dashboard.pbix"

# Custom output path
python run_report.py --input "C:\path\to\dashboard.pbix" --output "C:\out\Q2_report.pdf"

# Prompt for save location
python run_report.py --input "C:\path\to\dashboard.pbip" --ask-output

# Re-render only from an existing temp/insights.json
python run_report.py --build --input "C:\path\to\dashboard.pbix"
```

### PowerPoint output

```bash
python convert_dashboard.py "C:\path\to\dashboard.pbip"
python convert_dashboard.py "C:\path\to\dashboard.pbip" --vector-charts
python convert_dashboard.py "C:\path\to\dashboard.pptx" --output "C:\out\executive.pptx"
python convert_dashboard.py "C:\path\to\dashboard.pdf" --context "Focus on Finance and month-over-month change"
```

### Helper pipeline

```bash
python run_pipeline.py --source "C:\path\to\dashboard.pbix" --assistant claude
python run_pipeline.py --source "C:\path\to\dashboard.pdf" --assistant copilot --output "C:\out\deck.pptx"
```

## Deep analysis setup for PBIP and PBIX

For `.pbip` and `.pbix`, this project can connect to Power BI Desktop through the Power BI MCP server and query exact values using DAX.

`.pbip` is usually the better input because it exposes measure definitions more clearly than `.pbix`.

### One-time setup

```bash
python setup_pbi_mcp.py
python setup_pbi_mcp.py --check
```

### Workflow

1. Open the report in Power BI Desktop.
2. Restart your assistant session.
3. Run the deck or report command again.

If MCP is not available, `.pbip` and `.pbix` inputs fall back to image-based analysis automatically.

## Output options

### Vector charts

By default, deck generation embeds Power BI page screenshots. Add `--vector-charts` to render charts directly from the extracted data.

Use this when:

- The original screenshots are low quality
- You want resolution-independent charts in the final deck
- Exact data is available through MCP and you want cleaner visuals

### Context-aware analysis

Add `--context` or include natural-language guidance in your assistant prompt to steer the analysis.

Examples:

```text
Create exec deck "C:\path\to\report.pbip" --vector-charts
Create exec deck "C:\path\to\dashboard.pdf" --context "Audience is the CISO; emphasize security and compliance metrics"
Create exec deck "C:\path\to\report.pbip" --context "Focus on HR and Operations; frame recommendations around reducing onboarding time"
```

## Supported inputs

| Input | Format | Typical mode |
|---|---|---|
| PDF export | `.pdf` | Quick mode |
| PowerPoint export | `.pptx` | Quick mode |
| Power BI project | `.pbip` | Deep analysis mode |
| Power BI file | `.pbix` | Deep analysis mode |

Quick export options from Power BI:

- PDF: `File -> Export -> Export to PDF`
- PPTX: `File -> Export -> PowerPoint`

## Project layout

| Path | Purpose |
|---|---|
| `run_report.py` | PDF report entry point |
| `convert_dashboard.py` | Main deck-generation entry point |
| `run_pipeline.py` | Setup + conversion wrapper |
| `setup_pbi_mcp.py` | Power BI MCP installer and checker |
| `check_setup.py` | Dependency validation and auto-install helper |
| `lib/extraction/` | Input parsing and extraction |
| `lib/rendering/` | PowerPoint assembly and validation |
| `lib/reporting/` | PDF report rendering |
| `docs/` | Design notes, structure, and quality rules |
| `CLAUDE.md` | Claude Code workflow guidance |
| `COPILOT.md` | Copilot workflow guidance |

## Docs

- [Project structure](docs/PROJECT_STRUCTURE.md)
- [Executive slides feature](docs/EXECUTIVE_SLIDES_FEATURE.md)
- [Constitution compliance](docs/CONSTITUTION_COMPLIANCE.md)
- [Dashboard reading rules](docs/DASHBOARD_READING_RULES.md)

## License

MIT
