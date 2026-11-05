"""
plugins/data_dashboard.py — Interactive Visual Dashboard & Charting Plugin for Charlie.

Generates self-contained, responsive, dark-mode analytical dashboards from any
uploaded file (Excel, CSV, TSV, JSON) or provided text data, renders interactive
charts, KPI cards, and data tables, and launches them directly in the browser.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger("data_dashboard")

PLUGIN = {
    "name": "data_dashboard",
    "description": (
        "Generate interactive visual dashboards with charts, KPI cards, and data tables from any "
        "uploaded file (Excel .xlsx/.xls, CSV, JSON) or provided tabular data. "
        "Automatically opens the visual dashboard in the browser and displays a summary in the HUD. "
        "Use this when the user asks to 'make a dashboard', 'visualize this data', 'create charts', "
        "'give me visuals', 'analyze this spreadsheet', or gives an Excel/CSV file to visualize."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Path to the Excel (.xlsx/.xls), CSV, or JSON file. If omitted, uses currently uploaded file.",
            },
            "title": {
                "type": "STRING",
                "description": "Optional title for the dashboard (e.g. 'Purchase Register Analysis')",
            },
            "data_text": {
                "type": "STRING",
                "description": "Optional raw tabular or CSV text if data is provided directly in conversation.",
            },
            "auto_open": {
                "type": "BOOLEAN",
                "description": "Whether to automatically open the dashboard in browser (default: true).",
            },
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Generate visual dashboard, open in browser, and report summary."""
    try:
        import pandas as pd
    except ImportError:
        return "pandas and openpyxl are required. Run: pip install pandas openpyxl"

    from core.dashboard_generator import create_and_open_dashboard, analyze_dataframe

    file_path = str(parameters.get("file_path", "")).strip()
    title = str(parameters.get("title", "")).strip()
    data_text = str(parameters.get("data_text", "")).strip()
    auto_open = bool(parameters.get("auto_open", True))

    # Fallback to player.current_file if file_path not explicitly provided
    if not file_path and player and getattr(player, "current_file", None):
        file_path = str(player.current_file)

    df: Optional[pd.DataFrame] = None
    src_name = ""
    out_dir = Path.home() / "Downloads"

    if file_path:
        p = Path(file_path).expanduser().resolve()
        if not p.exists():
            return f"Data file not found at: {file_path}"
        src_name = p.name
        out_dir = p.parent
        ext = p.suffix.lower()

        try:
            if ext in (".xlsx", ".xls", ".xlsm"):
                df = pd.read_excel(p)
            elif ext in (".csv", ".tsv", ".txt"):
                try:
                    df = pd.read_csv(p, encoding="utf-8", encoding_errors="replace")
                except Exception:
                    df = pd.read_csv(p, sep="\t", encoding="utf-8", encoding_errors="replace")
            elif ext == ".json":
                df = pd.read_json(p)
            else:
                return f"Unsupported file format: {ext}. Please use Excel (.xlsx/.xls), CSV, or JSON."
        except Exception as e:
            return f"Failed to read dataset from {p.name}: {e}"

    elif data_text:
        src_name = "Provided Data"
        try:
            df = pd.read_csv(io.StringIO(data_text))
        except Exception:
            try:
                df = pd.read_json(io.StringIO(data_text))
            except Exception as e:
                return f"Could not parse provided data text: {e}"

    else:
        return "Please drop an Excel or CSV file onto the HUD or specify a file path to create a dashboard."

    if df is None or len(df) == 0:
        return "The dataset contains no rows or could not be loaded."

    if not title:
        stem = Path(file_path).stem if file_path else "Data"
        clean_stem = stem.replace("_", " ").replace("-", " ").title()
        title = f"{clean_stem} Dashboard"

    dash_stem = Path(file_path).stem if file_path else "data"
    output_html_path = out_dir / f"{dash_stem}_dashboard.html"

    try:
        saved_path, summary = create_and_open_dashboard(
            df=df,
            output_path=output_html_path,
            title=title,
            source_name=src_name,
            auto_open=auto_open,
        )
    except Exception as e:
        logger.exception(f"Error creating dashboard: {e}")
        return f"Failed to generate dashboard: {e}"

    # Build concise HUD summary text
    kpi_lines = []
    for k in summary.get("kpis", []):
        kpi_lines.append(f"• {k['label']}: {k['value']} ({k.get('sub', '')})")

    hud_text = (
        f"📊 {title}\n"
        f"File: {src_name} ({summary['total_rows']:,} rows, {summary['total_cols']} columns)\n\n"
        f"Key Metrics:\n" + "\n".join(kpi_lines) + "\n\n"
        f"Interactive charts & table opened in browser:\n{saved_path}"
    )

    if player:
        try:
            player.show_content(f"📊 {title[:32]}", hud_text)
            player.write_log(f"DATA: Generated dashboard for {src_name} ({summary['total_rows']:,} rows)")
        except Exception:
            pass

    chart_count = len(summary.get("charts", []))
    return (
        f"I've generated an interactive visual dashboard for {title} with {summary['total_rows']:,} records "
        f"and {chart_count} charts, and opened it in your browser."
    )
