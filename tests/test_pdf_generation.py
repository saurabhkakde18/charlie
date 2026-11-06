"""
test_pdf_generation.py — Comprehensive Unit & Integration Tests for PDF Generation

Tests:
1. Core PDF Generation from plain text, markdown, tabular data, and images.
2. File Processor action='to_pdf' conversions for text, markdown, csv, and images.
3. PDF page extraction via file_processor.
4. Dashboard server endpoints: POST /api/generate-pdf and GET /uploads/{filename}.
5. Response headers: application/pdf, Content-Disposition: attachment, auth security.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from actions.file_processor import file_processor
from core import pdf_generator
from dashboard.server import DashboardServer
from starlette.requests import Request


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "pdf_test_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def test_generate_pdf_from_text(temp_workspace: Path):
    out_file = temp_workspace / "text_doc.pdf"
    content = "First paragraph of the test document.\n\nSecond paragraph with multiple sentences."
    result = pdf_generator.generate_pdf_from_text(
        title="Plain Text Test",
        text=content,
        output_path=out_file,
    )
    assert result.exists()
    assert result.is_file()
    assert result.stat().st_size > 500
    with open(result, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"


def test_generate_pdf_from_markdown(temp_workspace: Path):
    out_file = temp_workspace / "md_doc.pdf"
    md_content = """# Executive Summary
## Key Findings
- **High Performance**: Optimized for fast generation.
- *Cross-platform*: Works across Windows, macOS, and Linux.
- Inline code: `pdf_generator.generate_pdf_from_markdown`

> "Quality is not an act, it is a habit."

```python
def hello():
    return "world"
```

1. First ordered step
2. Second ordered step
"""
    result = pdf_generator.generate_pdf_from_markdown(
        title="Markdown Report",
        md_text=md_content,
        output_path=out_file,
    )
    assert result.exists()
    assert result.stat().st_size > 1000
    with open(result, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_generate_pdf_from_table(temp_workspace: Path):
    out_file = temp_workspace / "table_doc.pdf"
    headers = ["Metric", "Q1 Actual", "Q2 Target", "Status"]
    rows = [
        ["Revenue", "$120,000", "$150,000", "On Track"],
        ["Customer Acquisition", "450", "500", "Near Target"],
        ["Server Uptime", "99.98%", "99.95%", "Exceeded"],
    ]
    result = pdf_generator.generate_pdf_from_table(
        title="Quarterly Performance",
        headers=headers,
        rows=rows,
        output_path=out_file,
        summary="Summary of quarterly metrics.",
    )
    assert result.exists()
    assert result.stat().st_size > 1000
    with open(result, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_convert_image_to_pdf(temp_workspace: Path):
    img_path = temp_workspace / "sample_chart.png"
    img = Image.new("RGB", (300, 200), color=(37, 99, 235))
    img.save(img_path)

    out_file = temp_workspace / "chart.pdf"
    result = pdf_generator.convert_image_to_pdf(
        image_path=img_path,
        output_path=out_file,
        title="Visual Chart",
    )
    assert result.exists()
    assert result.stat().st_size > 800
    with open(result, "rb") as f:
        assert f.read(5) == b"%PDF-"


def test_file_processor_text_to_pdf(temp_workspace: Path):
    txt_file = temp_workspace / "meeting_notes.txt"
    txt_file.write_text("Agenda:\n1. Review quarterly numbers\n2. Next steps\n", encoding="utf-8")

    resp = file_processor({"file_path": str(txt_file), "action": "to_pdf"})
    assert "Exported document to PDF" in str(resp)

    expected_pdf = temp_workspace / "meeting_notes_converted.pdf"
    assert expected_pdf.exists()
    assert expected_pdf.stat().st_size > 500


def test_file_processor_csv_to_pdf(temp_workspace: Path):
    csv_file = temp_workspace / "inventory.csv"
    csv_file.write_text("Item,Quantity,Location\nWidget A,120,Aisle 4\nWidget B,85,Aisle 2\n", encoding="utf-8")

    resp = file_processor({"file_path": str(csv_file), "action": "to_pdf"})
    assert "Exported dataset to PDF report" in str(resp)

    expected_pdf = temp_workspace / "inventory_report.pdf"
    assert expected_pdf.exists()
    assert expected_pdf.stat().st_size > 800


def test_file_processor_image_to_pdf(temp_workspace: Path):
    img_file = temp_workspace / "diagram.png"
    Image.new("RGB", (150, 150), color=(16, 185, 129)).save(img_file)

    resp = file_processor({"file_path": str(img_file), "action": "to_pdf"})
    assert "Converted image to PDF" in str(resp)

    expected_pdf = temp_workspace / "diagram_converted.pdf"
    assert expected_pdf.exists()
    assert expected_pdf.stat().st_size > 800


def test_file_processor_extract_pages(temp_workspace: Path):
    # First generate a multi-page PDF using plain text
    big_text = ("This is a page paragraph.\n\n" * 40)
    base_pdf = temp_workspace / "multi_page.pdf"
    pdf_generator.generate_pdf_from_text("Multi Page Document", big_text, base_pdf)

    resp = file_processor({"file_path": str(base_pdf), "action": "extract_pages", "pages": "1"})
    assert "Extracted 1 page(s)" in str(resp)

    extracted_pdf = temp_workspace / "multi_page_pages_1.pdf"
    assert extracted_pdf.exists()
    assert extracted_pdf.stat().st_size > 500


def _run_sync(coro):
    """Run an async coroutine synchronously without event loop / network socket."""
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    raise RuntimeError("Coroutine did not resolve synchronously")


def test_dashboard_server_pdf_endpoints(temp_workspace: Path):
    srv = DashboardServer()
    # Override uploads directory to temporary workspace
    srv._uploads_dir = temp_workspace

    valid_token = "secure_test_token_jarvis"
    srv._tokens[valid_token] = 9999999999.0  # far future timestamp

    gen_ep = next(r.endpoint for r in srv.app.routes if getattr(r, "path", "") == "/api/generate-pdf")
    dl_ep = next(r.endpoint for r in srv.app.routes if getattr(r, "path", "") == "/uploads/{filename}")

    # 1. Test Generate PDF via JSON payload
    req_body = {
        "title": "Server Test Report",
        "content": "# Test Header\n- Point 1\n- Point 2",
        "format": "markdown",
        "filename": "server_report.pdf",
    }
    scope_gen = {
        "type": "http",
        "method": "POST",
        "path": "/api/generate-pdf",
        "headers": [
            (b"authorization", f"Bearer {valid_token}".encode("utf-8")),
            (b"content-type", b"application/json"),
        ],
        "query_string": b"",
    }
    req_gen = Request(scope_gen)
    req_gen._mock_json = req_body

    res_gen = _run_sync(gen_ep(req_gen))
    assert res_gen.status_code == 200

    resp_data = json.loads(res_gen.body.decode("utf-8"))
    assert resp_data.get("ok") is True
    file_name = resp_data.get("name")
    assert file_name is not None
    assert file_name.endswith(".pdf")

    # 2. Test Download with token in query param
    scope_dl_query = {
        "type": "http",
        "method": "GET",
        "path": f"/uploads/{file_name}",
        "headers": [],
        "query_string": f"token={valid_token}".encode("utf-8"),
    }
    req_dl_query = Request(scope_dl_query)
    res_dl = _run_sync(dl_ep(file_name, req_dl_query, token=valid_token))

    assert res_dl.status_code == 200
    assert res_dl.media_type == "application/pdf"
    assert "attachment" in res_dl.headers.get("content-disposition", "")
    assert f'filename="{file_name}"' in res_dl.headers.get("content-disposition", "")

    # 3. Test Download with Bearer authorization header
    scope_dl_header = {
        "type": "http",
        "method": "GET",
        "path": f"/uploads/{file_name}",
        "headers": [(b"authorization", f"Bearer {valid_token}".encode("utf-8"))],
        "query_string": b"",
    }
    req_dl_header = Request(scope_dl_header)
    res_dl_header = _run_sync(dl_ep(file_name, req_dl_header, token=""))
    assert res_dl_header.status_code == 200
    assert res_dl_header.media_type == "application/pdf"

    # 4. Test Unauthorized Download
    scope_unauth = {
        "type": "http",
        "method": "GET",
        "path": f"/uploads/{file_name}",
        "headers": [],
        "query_string": b"token=bad_token",
    }
    req_unauth = Request(scope_unauth)
    res_unauth = _run_sync(dl_ep(file_name, req_unauth, token="bad_token"))
    assert res_unauth.status_code == 401

    # 5. Direct Binary Download on generation
    req_body_direct = {
        "title": "Direct Binary Download",
        "content": "Sample content",
        "format": "text",
        "download": True,
    }
    req_gen_direct = Request(scope_gen)
    req_gen_direct._mock_json = req_body_direct
    res_direct = _run_sync(gen_ep(req_gen_direct))
    assert res_direct.status_code == 200
    assert res_direct.media_type == "application/pdf"
    assert "attachment" in res_direct.headers.get("content-disposition", "")
