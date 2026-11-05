"""
core/dashboard_generator.py — High-Tech Interactive Visual Dashboard Generator for Charlie.

Generates self-contained, responsive, dark-mode analytical dashboards from any
pandas DataFrame (Excel, CSV, JSON, or tabular data), renders interactive charts,
KPI summary cards, and searchable data tables, and opens them in the browser.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None
    np = None


def _format_num(val: Any) -> str:
    """Format numbers into human-readable compact or currency strings."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "N/A"
    try:
        f = float(val)
        if abs(f) >= 1_000_000_000:
            return f"{f / 1_000_000_000:.2f}B"
        if abs(f) >= 1_000_000:
            return f"{f / 1_000_000:.2f}M"
        if abs(f) >= 1_000:
            return f"{f:,.2f}"
        if f.is_integer():
            return f"{int(f):,}"
        return f"{f:.2f}"
    except (ValueError, TypeError):
        return str(val)


def analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract metrics, column types, KPIs, and chart configurations from a DataFrame."""
    total_rows = len(df)
    total_cols = len(df.columns)
    
    # Identify column classifications
    numeric_cols = []
    categorical_cols = []
    datetime_cols = []
    
    for col in df.columns:
        # Check datetime
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            # If unique values are very few compared to rows and integers, could be categorical
            if df[col].nunique() < 10 and total_rows > 50:
                categorical_cols.append(col)
            else:
                numeric_cols.append(col)
        else:
            # Try to see if it parses cleanly as date
            sample = df[col].dropna().head(10).astype(str)
            is_date = False
            if len(sample) > 0 and all(re.search(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", s) for s in sample):
                try:
                    df[col] = pd.to_datetime(df[col], errors="ignore")
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        datetime_cols.append(col)
                        is_date = True
                except Exception:
                    pass
            if not is_date:
                categorical_cols.append(col)

    # Compute high-level KPI cards
    kpis = [
        {"label": "Total Records", "value": f"{total_rows:,}", "sub": f"{total_cols} Columns", "icon": "📁"}
    ]

    primary_num = numeric_cols[0] if numeric_cols else None
    secondary_num = numeric_cols[1] if len(numeric_cols) > 1 else None
    primary_cat = categorical_cols[0] if categorical_cols else None

    if primary_num:
        total_sum = df[primary_num].sum()
        avg_val = df[primary_num].mean()
        max_val = df[primary_num].max()
        kpis.append({
            "label": f"Total {primary_num}",
            "value": _format_num(total_sum),
            "sub": f"Max: {_format_num(max_val)}",
            "icon": "💎"
        })
        kpis.append({
            "label": f"Average {primary_num}",
            "value": _format_num(avg_val),
            "sub": f"Median: {_format_num(df[primary_num].median())}",
            "icon": "📈"
        })

    if primary_cat:
        top_cat = df[primary_cat].value_counts()
        if len(top_cat) > 0:
            top_name = str(top_cat.index[0])
            top_count = top_cat.iloc[0]
            kpis.append({
                "label": f"Top {primary_cat}",
                "value": top_name[:20],
                "sub": f"{top_count:,} occurrences ({top_count/max(1, total_rows)*100:.1f}%)",
                "icon": "🏆"
            })

    # Prepare Chart Data
    charts = []

    # Chart 1: Categorical Bar Chart (Group by primary_cat)
    if primary_cat:
        if primary_num:
            cat_grp = df.groupby(primary_cat)[primary_num].sum().sort_values(ascending=False).head(10)
            charts.append({
                "id": "chart_cat_bar",
                "title": f"{primary_num} by {primary_cat} (Top 10)",
                "type": "bar",
                "labels": [str(x)[:22] for x in cat_grp.index.tolist()],
                "datasets": [{
                    "label": f"Total {primary_num}",
                    "data": [round(float(v), 2) for v in cat_grp.values.tolist()],
                    "bg": "rgba(0, 229, 255, 0.6)",
                    "border": "#00e5ff"
                }]
            })
        else:
            cat_counts = df[primary_cat].value_counts().head(10)
            charts.append({
                "id": "chart_cat_bar",
                "title": f"Frequency by {primary_cat}",
                "type": "bar",
                "labels": [str(x)[:22] for x in cat_counts.index.tolist()],
                "datasets": [{
                    "label": "Count",
                    "data": cat_counts.values.tolist(),
                    "bg": "rgba(0, 229, 255, 0.6)",
                    "border": "#00e5ff"
                }]
            })

    # Chart 2: Time Trend Line Chart (if date exists)
    if datetime_cols and primary_num:
        date_col = datetime_cols[0]
        try:
            # Resample or group by date
            temp_df = df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col], errors="coerce")
            temp_df = temp_df.dropna(subset=[date_col]).sort_values(date_col)
            if len(temp_df) > 0:
                date_grp = temp_df.groupby(temp_df[date_col].dt.strftime("%Y-%m-%d"))[primary_num].sum()
                if len(date_grp) > 30:
                    # Resample to weekly/monthly
                    date_grp = temp_df.groupby(temp_df[date_col].dt.strftime("%Y-%m"))[primary_num].sum()
                charts.append({
                    "id": "chart_time_trend",
                    "title": f"{primary_num} Trend over Time",
                    "type": "line",
                    "labels": date_grp.index.tolist(),
                    "datasets": [{
                        "label": f"{primary_num} Timeline",
                        "data": [round(float(v), 2) for v in date_grp.values.tolist()],
                        "bg": "rgba(0, 255, 136, 0.15)",
                        "border": "#00ff88",
                        "fill": True
                    }]
                })
        except Exception:
            pass

    # Chart 3: Doughnut Chart (Distribution)
    secondary_cat = categorical_cols[1] if len(categorical_cols) > 1 else primary_cat
    if secondary_cat:
        val_counts = df[secondary_cat].value_counts().head(6)
        charts.append({
            "id": "chart_distribution",
            "title": f"Share by {secondary_cat}",
            "type": "doughnut",
            "labels": [str(x)[:20] for x in val_counts.index.tolist()],
            "datasets": [{
                "label": "Share",
                "data": val_counts.values.tolist(),
                "colors": [
                    "#00e5ff", "#ff6b00", "#00ff88", "#a855f7", "#ffd600", "#ff0055"
                ]
            }]
        })

    # Chart 4: Multi-variable bar or second metric if available
    if primary_cat and secondary_num and secondary_num != primary_num:
        sec_grp = df.groupby(primary_cat)[secondary_num].sum().sort_values(ascending=False).head(8)
        charts.append({
            "id": "chart_secondary_bar",
            "title": f"{secondary_num} by {primary_cat}",
            "type": "bar",
            "labels": [str(x)[:20] for x in sec_grp.index.tolist()],
            "datasets": [{
                "label": f"Total {secondary_num}",
                "data": [round(float(v), 2) for v in sec_grp.values.tolist()],
                "bg": "rgba(255, 107, 0, 0.6)",
                "border": "#ff6b00"
            }]
        })

    return {
        "total_rows": total_rows,
        "total_cols": total_cols,
        "columns": df.columns.tolist(),
        "kpis": kpis,
        "charts": charts,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "preview_rows": df.head(100).to_dict(orient="records"),
    }


def generate_html_dashboard(df: pd.DataFrame, title: str = "Visual Data Dashboard", source_name: str = "") -> str:
    """Build a complete, standalone, interactive HTML dashboard."""
    info = analyze_dataframe(df)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # KPI cards HTML
    kpi_cards_html = ""
    for k in info["kpis"]:
        kpi_cards_html += f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="kpi-icon">{k['icon']}</span>
                <span class="kpi-label">{html.escape(k['label'])}</span>
            </div>
            <div class="kpi-value">{html.escape(k['value'])}</div>
            <div class="kpi-sub">{html.escape(k['sub'])}</div>
        </div>
        """

    # Charts HTML
    chart_containers_html = ""
    for ch in info["charts"]:
        chart_containers_html += f"""
        <div class="chart-card">
            <div class="chart-title">{html.escape(ch['title'])}</div>
            <div class="chart-box">
                <canvas id="{ch['id']}"></canvas>
            </div>
        </div>
        """

    # Table headers and rows (first 100 rows preview)
    cols = info["columns"]
    th_html = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    
    tbody_html = ""
    for row in info["preview_rows"]:
        tbody_html += "<tr>"
        for c in cols:
            val = row.get(c, "")
            tbody_html += f"<td>{html.escape(str(val))}</td>"
        tbody_html += "</tr>"

    charts_json = json.dumps(info["charts"])

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} — Charlie Visual Intelligence</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #07090e;
            --surface: #0f141d;
            --surface-hover: #161e2b;
            --border: #1e293b;
            --cyan: #00e5ff;
            --cyan-glow: rgba(0, 229, 255, 0.2);
            --orange: #ff6b00;
            --green: #00ff88;
            --purple: #a855f7;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Courier New", monospace;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: var(--font-family);
            padding: 24px 32px 64px;
            min-height: 100vh;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 20px;
            margin-bottom: 28px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .reactor-badge {{
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 2px solid var(--cyan);
            box-shadow: 0 0 15px var(--cyan-glow);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--cyan);
            font-size: 18px;
            background: rgba(0, 229, 255, 0.08);
        }}
        .title-group h1 {{
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: var(--text-main);
        }}
        .meta-badges {{
            display: flex;
            gap: 10px;
            margin-top: 4px;
        }}
        .badge {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text-muted);
        }}
        .badge.cyan {{
            color: var(--cyan);
            border-color: rgba(0, 229, 255, 0.3);
        }}
        .btn {{
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--cyan);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .btn:hover {{
            background: var(--cyan);
            color: #000;
            box-shadow: 0 0 12px var(--cyan-glow);
        }}

        /* KPI Section */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .kpi-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px 20px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(0, 229, 255, 0.4);
        }}
        .kpi-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }}
        .kpi-icon {{
            font-size: 16px;
        }}
        .kpi-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kpi-value {{
            font-size: 26px;
            font-weight: 700;
            color: var(--cyan);
            margin-bottom: 4px;
            font-family: "Courier New", monospace;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
        }}

        /* Charts Grid */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(460px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }}
        .chart-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }}
        .chart-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-main);
            margin-bottom: 16px;
            border-left: 3px solid var(--cyan);
            padding-left: 10px;
        }}
        .chart-box {{
            position: relative;
            height: 280px;
            width: 100%;
        }}

        /* Data Table */
        .table-section {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }}
        .table-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .table-title {{
            font-size: 15px;
            font-weight: 600;
            color: var(--text-main);
            border-left: 3px solid var(--orange);
            padding-left: 10px;
        }}
        .search-box {{
            background: var(--bg);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 13px;
            width: 250px;
            outline: none;
        }}
        .search-box:focus {{
            border-color: var(--cyan);
            box-shadow: 0 0 8px var(--cyan-glow);
        }}
        .table-wrap {{
            overflow-x: auto;
            max-height: 480px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background: #090d14;
            color: var(--cyan);
            font-weight: 600;
            padding: 12px 14px;
            border-bottom: 2px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            color: var(--text-main);
            font-family: "Courier New", monospace;
        }}
        tr:hover td {{
            background: var(--surface-hover);
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <div class="reactor-badge">◉</div>
            <div class="title-group">
                <h1>{html.escape(title)}</h1>
                <div class="meta-badges">
                    <span class="badge cyan">Charlie Intelligence</span>
                    <span class="badge">{info['total_rows']:,} Rows</span>
                    <span class="badge">{info['total_cols']} Columns</span>
                    <span class="badge">Generated {now_str}</span>
                    {f'<span class="badge cyan">{html.escape(source_name)}</span>' if source_name else ''}
                </div>
            </div>
        </div>
        <div>
            <button class="btn" onclick="window.print()">🖨 Print / Export PDF</button>
        </div>
    </header>

    <div class="kpi-grid">
        {kpi_cards_html}
    </div>

    <div class="charts-grid">
        {chart_containers_html}
    </div>

    <div class="table-section">
        <div class="table-header">
            <div class="table-title">Dataset Records Preview</div>
            <input type="text" id="tableSearch" class="search-box" placeholder="Search rows..." onkeyup="filterTable()">
        </div>
        <div class="table-wrap">
            <table id="dataTable">
                <thead>
                    <tr>{th_html}</tr>
                </thead>
                <tbody>
                    {tbody_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const chartConfigs = {charts_json};
        
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.borderColor = 'rgba(30, 41, 59, 0.6)';
        Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace';

        chartConfigs.forEach(cfg => {{
            const ctx = document.getElementById(cfg.id);
            if (!ctx) return;

            let dataSets = [];
            if (cfg.type === 'doughnut') {{
                dataSets = [{{
                    data: cfg.datasets[0].data,
                    backgroundColor: cfg.datasets[0].colors,
                    borderColor: '#0f141d',
                    borderWidth: 2
                }}];
            }} else {{
                dataSets = cfg.datasets.map(ds => ({{
                    label: ds.label,
                    data: ds.data,
                    backgroundColor: ds.bg || 'rgba(0, 229, 255, 0.5)',
                    borderColor: ds.border || '#00e5ff',
                    borderWidth: 2,
                    fill: ds.fill || false,
                    tension: 0.3
                }}));
            }}

            new Chart(ctx, {{
                type: cfg.type,
                data: {{
                    labels: cfg.labels,
                    datasets: dataSets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: cfg.type === 'doughnut' || dataSets.length > 1,
                            position: 'bottom'
                        }}
                    }},
                    scales: cfg.type === 'doughnut' ? {{}} : {{
                        y: {{ beginAtZero: true, grid: {{ color: 'rgba(30, 41, 59, 0.5)' }} }},
                        x: {{ grid: {{ display: false }} }}
                    }}
                }}
            }});
        }});

        function filterTable() {{
            const input = document.getElementById("tableSearch");
            const filter = input.value.toLowerCase();
            const table = document.getElementById("dataTable");
            const tr = table.getElementsByTagName("tr");

            for (let i = 1; i < tr.length; i++) {{
                let show = false;
                const tds = tr[i].getElementsByTagName("td");
                for (let j = 0; j < tds.length; j++) {{
                    if (tds[j]) {{
                        const txt = tds[j].textContent || tds[j].innerText;
                        if (txt.toLowerCase().indexOf(filter) > -1) {{
                            show = true;
                            break;
                        }}
                    }}
                }}
                tr[i].style.display = show ? "" : "none";
            }}
        }}
    </script>
</body>
</html>
"""
    return html_template


def create_and_open_dashboard(
    df: pd.DataFrame,
    output_path: Optional[Path] = None,
    title: str = "Data Analytics Dashboard",
    source_name: str = "",
    auto_open: bool = True,
) -> Tuple[Path, Dict[str, Any]]:
    """Build and save dashboard HTML file and open it in browser."""
    if output_path is None:
        base_dir = Path.home() / "Downloads"
        if not base_dir.exists():
            base_dir = Path.cwd()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = base_dir / f"dashboard_{timestamp}.html"

    html_content = generate_html_dashboard(df, title=title, source_name=source_name)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
    except (PermissionError, OSError):
        import tempfile
        fallback_dir = Path(tempfile.gettempdir()) / "charlie_dashboards"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = fallback_dir / f"{output_path.stem}_{ts}.html"
        output_path.write_text(html_content, encoding="utf-8")

    if auto_open:
        try:
            # Use webbrowser or os.startfile on Windows
            webbrowser.open(output_path.as_uri())
        except Exception:
            try:
                if sys.platform == "win32":
                    os.startfile(str(output_path))
            except Exception:
                pass

    summary = analyze_dataframe(df)
    return output_path, summary
