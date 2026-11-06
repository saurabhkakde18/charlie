"""
pdf_generator.py — Universal PDF Document Generator for JARVIS

Creates clean, high-fidelity PDF documents from text, Markdown, tabular
data (CSV/Excel), images, Word documents (.docx), and presentations (.pptx).
Thread-safe, headless, and cross-platform.
"""

from __future__ import annotations

import html
import io
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that writes dynamic total page count ('Page X of Y')."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        page_w, page_h = self._pagesize
        margin = 40

        # Footer divider line
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(margin, 35, page_w - margin, 35)

        # Footer labels
        footer_left = f"JARVIS · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        footer_right = f"Page {self._pageNumber} of {total_pages}"
        self.drawString(margin, 22, footer_left)
        self.drawRightString(page_w - margin, 22, footer_right)

        self.restoreState()


def _format_inline_markdown(text: str) -> str:
    """Safely convert inline markdown (bold, italic, code) to ReportLab markup."""
    safe = html.escape(text)
    # bold: **text** or __text__
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"__(.+?)__", r"<b>\1</b>", safe)
    # italic: *text* or _text_
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
    safe = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", safe)
    # inline code: `code`
    safe = re.sub(
        r"`(.+?)`",
        r'<font face="Courier" color="#1d4ed8" size="8.5"><b>\1</b></font>',
        safe,
    )
    return safe


def _create_stylesheet() -> dict[str, ParagraphStyle]:
    """Build a consistent set of typography styles for generated PDFs."""
    base = getSampleStyleSheet()

    styles: dict[str, ParagraphStyle] = {}
    styles["Normal"] = ParagraphStyle(
        "PDF_Normal",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
    )
    styles["DocTitle"] = ParagraphStyle(
        "PDF_DocTitle",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    styles["Subtitle"] = ParagraphStyle(
        "PDF_Subtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14,
    )
    styles["Heading1"] = ParagraphStyle(
        "PDF_H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    styles["Heading2"] = ParagraphStyle(
        "PDF_H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    styles["Heading3"] = ParagraphStyle(
        "PDF_H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )
    styles["Bullet"] = ParagraphStyle(
        "PDF_Bullet",
        parent=styles["Normal"],
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )
    styles["Blockquote"] = ParagraphStyle(
        "PDF_Blockquote",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        leftIndent=18,
        rightIndent=18,
        textColor=colors.HexColor("#475569"),
        spaceBefore=6,
        spaceAfter=6,
    )
    styles["TableHeader"] = ParagraphStyle(
        "PDF_TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.white,
        alignment=0,
    )
    styles["TableCell"] = ParagraphStyle(
        "PDF_TableCell",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    styles["Code"] = ParagraphStyle(
        "PDF_Code",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6,
    )
    return styles


def _setup_document(output_path: str | Path, title: str) -> tuple[SimpleDocTemplate, Path]:
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=50,
        title=title,
        author="JARVIS Universal File Processor",
    )
    return doc, out


def generate_pdf_from_text(
    title: str,
    text: str,
    output_path: str | Path,
    author: str = "JARVIS",
) -> Path:
    """Generate a structured, paginated PDF from plain text."""
    doc, out = _setup_document(output_path, title or "Document")
    styles = _create_stylesheet()
    story: list[Any] = []

    # Title & Metadata
    clean_title = title.strip() or "Document"
    story.append(Paragraph(html.escape(clean_title), styles["DocTitle"]))
    story.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} · Author: {html.escape(author)}",
            styles["Subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # Split text into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        story.append(Paragraph("<i>(Empty document)</i>", styles["Normal"]))
    else:
        for p in paragraphs:
            # Handle single newlines inside paragraph as soft linebreaks
            lines = p.split("\n")
            escaped_p = "<br/>".join(html.escape(line) for line in lines)
            story.append(Paragraph(escaped_p, styles["Normal"]))
            story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def generate_pdf_from_markdown(
    title: str,
    md_text: str,
    output_path: str | Path,
    author: str = "JARVIS",
) -> Path:
    """Parse Markdown headings, lists, quotes, tables, and code blocks into a PDF."""
    doc, out = _setup_document(output_path, title or "Document")
    styles = _create_stylesheet()
    story: list[Any] = []

    # Header section
    clean_title = title.strip() or "Document"
    story.append(Paragraph(html.escape(clean_title), styles["DocTitle"]))
    story.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} · {html.escape(author)}",
            styles["Subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    lines = md_text.splitlines()
    in_code_block = False
    code_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Handle code blocks
        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = html.escape("\n".join(code_lines))
                story.append(Preformatted(code_text, styles["Code"]))
                story.append(Spacer(1, 6))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not stripped:
            story.append(Spacer(1, 6))
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceBefore=6, spaceAfter=8))
            continue

        # Headings
        if stripped.startswith("# "):
            story.append(Paragraph(_format_inline_markdown(stripped[2:].strip()), styles["Heading1"]))
            story.append(Spacer(1, 4))
            continue
        if stripped.startswith("## "):
            story.append(Paragraph(_format_inline_markdown(stripped[3:].strip()), styles["Heading2"]))
            story.append(Spacer(1, 3))
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(_format_inline_markdown(stripped[4:].strip()), styles["Heading3"]))
            story.append(Spacer(1, 2))
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_text = stripped.lstrip("> ").strip()
            story.append(Paragraph(f"“{_format_inline_markdown(quote_text)}”", styles["Blockquote"]))
            continue

        # Bullet list
        if stripped.startswith(("- ", "* ", "+ ")):
            item_text = stripped[2:].strip()
            story.append(Paragraph(f"• {_format_inline_markdown(item_text)}", styles["Bullet"]))
            continue

        # Numbered list
        num_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if num_match:
            num, item_text = num_match.group(1), num_match.group(2)
            story.append(Paragraph(f"{num}. {_format_inline_markdown(item_text)}", styles["Bullet"]))
            continue

        # Standard paragraph
        story.append(Paragraph(_format_inline_markdown(stripped), styles["Normal"]))
        story.append(Spacer(1, 4))

    # Catch unclosed code block if file ends
    if in_code_block and code_lines:
        code_text = html.escape("\n".join(code_lines))
        story.append(Preformatted(code_text, styles["Code"]))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def generate_pdf_from_table(
    title: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    output_path: str | Path,
    summary: str = "",
    author: str = "JARVIS",
) -> Path:
    """Generate a clean tabular report with header styling and cell wrapping."""
    doc, out = _setup_document(output_path, title or "Data Report")
    styles = _create_stylesheet()
    story: list[Any] = []

    # Title & Metadata
    clean_title = title.strip() or "Data Report"
    story.append(Paragraph(html.escape(clean_title), styles["DocTitle"]))
    story.append(
        Paragraph(
            f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} · {len(rows):,} records",
            styles["Subtitle"],
        )
    )
    if summary:
        story.append(Paragraph(_format_inline_markdown(summary), styles["Normal"]))
        story.append(Spacer(1, 8))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

    if not headers and not rows:
        story.append(Paragraph("<i>No data records found.</i>", styles["Normal"]))
        doc.build(story, canvasmaker=NumberedCanvas)
        return out

    # Compute column widths to fit doc.width
    num_cols = max(len(headers), max((len(r) for r in rows), default=0))
    if num_cols == 0:
        story.append(Paragraph("<i>Empty dataset.</i>", styles["Normal"]))
        doc.build(story, canvasmaker=NumberedCanvas)
        return out

    col_width = doc.width / num_cols

    # Wrap each cell in a Paragraph for auto-wrapping
    table_data: list[list[Paragraph]] = []
    if headers:
        header_row = [
            Paragraph(html.escape(str(h)), styles["TableHeader"])
            for h in headers
        ]
        table_data.append(header_row)

    for row in rows:
        row_cells = []
        for i in range(num_cols):
            val = row[i] if i < len(row) else ""
            val_str = "" if val is None else str(val)
            row_cells.append(Paragraph(html.escape(val_str), styles["TableCell"]))
        table_data.append(row_cells)

    report_table = Table(table_data, colWidths=[col_width] * num_cols, repeatRows=1 if headers else 0)
    report_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    story.append(report_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def convert_image_to_pdf(
    image_path: str | Path,
    output_path: str | Path,
    title: str = "",
) -> Path:
    """Scale and embed an image into a high-resolution printable PDF."""
    try:
        from PIL import Image as PILImage
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image conversion.") from exc

    img_path = Path(image_path).resolve()
    if not img_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    doc, out = _setup_document(output_path, title or img_path.name)
    styles = _create_stylesheet()
    story: list[Any] = []

    if title:
        story.append(Paragraph(html.escape(title), styles["DocTitle"]))
        story.append(Spacer(1, 8))

    # Read image dimensions and calculate fit
    with PILImage.open(img_path) as im:
        orig_w, orig_h = im.size

    avail_w = doc.width
    avail_h = doc.height - (50 if title else 20)

    scale = min(avail_w / orig_w, avail_h / orig_h, 1.0)
    fit_w = orig_w * scale
    fit_h = orig_h * scale

    story.append(RLImage(str(img_path), width=fit_w, height=fit_h))
    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def convert_docx_to_pdf(docx_path: str | Path, output_path: str | Path) -> Path:
    """Extract paragraphs and tables from a Word document and export to PDF."""
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError("python-docx is required to convert Word documents.") from exc

    doc_file = Path(docx_path).resolve()
    if not doc_file.is_file():
        raise FileNotFoundError(f"File not found: {docx_path}")

    word_doc = docx.Document(doc_file)
    doc, out = _setup_document(output_path, doc_file.stem)
    styles = _create_stylesheet()
    story: list[Any] = []

    # Title header
    story.append(Paragraph(html.escape(doc_file.stem.replace("_", " ").title()), styles["DocTitle"]))
    story.append(Paragraph(f"Converted from {html.escape(doc_file.name)}", styles["Subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    for p in word_doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            story.append(Spacer(1, 4))
            continue
        style_name = (p.style.name or "").lower()
        if "heading 1" in style_name:
            story.append(Paragraph(html.escape(txt), styles["Heading1"]))
        elif "heading 2" in style_name:
            story.append(Paragraph(html.escape(txt), styles["Heading2"]))
        elif "heading 3" in style_name:
            story.append(Paragraph(html.escape(txt), styles["Heading3"]))
        else:
            story.append(Paragraph(html.escape(txt), styles["Normal"]))
            story.append(Spacer(1, 5))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out


def convert_pptx_to_pdf(pptx_path: str | Path, output_path: str | Path) -> Path:
    """Extract slide titles and bullet points from a PowerPoint deck and format into a PDF summary."""
    try:
        from pptx import Presentation
    except ImportError as exc:
        raise RuntimeError("python-pptx is required to convert presentations.") from exc

    pres_file = Path(pptx_path).resolve()
    if not pres_file.is_file():
        raise FileNotFoundError(f"File not found: {pptx_path}")

    prs = Presentation(pres_file)
    doc, out = _setup_document(output_path, pres_file.stem)
    styles = _create_stylesheet()
    story: list[Any] = []

    story.append(Paragraph(html.escape(pres_file.stem.replace("_", " ").title()), styles["DocTitle"]))
    story.append(Paragraph(f"Presentation Summary · {len(prs.slides)} Slides · {pres_file.name}", styles["Subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    for idx, slide in enumerate(prs.slides, 1):
        slide_title = f"Slide {idx}"
        slide_texts: list[str] = []

        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                lines = [line.strip() for line in shape.text.splitlines() if line.strip()]
                if not lines:
                    continue
                # If first shape has text, treat as slide title if not set
                if slide_title == f"Slide {idx}":
                    slide_title = f"Slide {idx}: {lines[0]}"
                    slide_texts.extend(lines[1:])
                else:
                    slide_texts.extend(lines)

        story.append(Paragraph(html.escape(slide_title), styles["Heading2"]))
        story.append(Spacer(1, 3))

        if slide_texts:
            for line in slide_texts:
                story.append(Paragraph(f"• {html.escape(line)}", styles["Bullet"]))
        else:
            story.append(Paragraph("<i>(Visual slide or diagram)</i>", styles["Normal"]))

        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#f1f5f9"), spaceAfter=10))

    doc.build(story, canvasmaker=NumberedCanvas)
    return out

