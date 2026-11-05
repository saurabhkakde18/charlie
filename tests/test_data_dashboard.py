import tempfile
from pathlib import Path
import pandas as pd
import pytest

from core.dashboard_generator import analyze_dataframe, generate_html_dashboard, create_and_open_dashboard
from plugins import data_dashboard


def test_dashboard_analysis_and_generation():
    df = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "Region": ["North", "South", "East", "West", "North", "South", "East", "West", "North", "South"],
        "Revenue": [10000, 15000, 12000, 8000, 19000, 22000, 14000, 9500, 17500, 21000],
        "Units": [10, 14, 11, 8, 18, 20, 13, 9, 16, 19],
    })

    analysis = analyze_dataframe(df)
    assert analysis["total_rows"] == 10
    assert analysis["total_cols"] == 4
    assert len(analysis["kpis"]) >= 3
    assert len(analysis["charts"]) >= 2

    html = generate_html_dashboard(df, title="Sales Performance")
    assert "<!DOCTYPE html>" in html
    assert "Sales Performance" in html
    assert "chart.js" in html.lower()
    assert "dataTable" in html


def test_plugin_run_with_data_text():
    csv_text = "City,Population,Score\nNew York,8000000,88\nLondon,9000000,92\nTokyo,14000000,96"
    res = data_dashboard.run({"data_text": csv_text, "title": "City Stats", "auto_open": False}, player=None)
    assert "interactive visual dashboard" in res.lower()
    assert "City Stats" in res


def test_plugin_run_with_file(tmp_path):
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text("Product,Price,Quantity\nLaptop,1200,5\nMouse,25,40\nMonitor,300,12", encoding="utf-8")

    res = data_dashboard.run({"file_path": str(csv_file), "auto_open": False}, player=None)
    assert "interactive visual dashboard" in res.lower()
    dash_html = tmp_path / "test_data_dashboard.html"
    assert dash_html.exists()
    assert dash_html.stat().st_size > 1000


def test_plugin_missing_data():
    res = data_dashboard.run({}, player=None)
    assert "please drop an excel or csv file" in res.lower()
