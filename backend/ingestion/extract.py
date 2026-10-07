"""Extract text -> Clean text (PRD §13.3). Output is a list of (section, text) blocks.

Section names (shown in sources, §30) come from Markdown '#' headings and DOCX heading styles.
PDF/TXT/JSON/CSV carry no section. How JSON and CSV are turned into text is not specified in the
PRD (docs/PRD_GAPS.md): JSON is pretty-printed, CSV is kept as its own text.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Block:
    section: Optional[str]
    text: str


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_blocks(text: str) -> list[Block]:
    blocks: list[Block] = []
    section, buf = None, []

    def flush():
        body = clean_text("\n".join(buf))
        if body:
            blocks.append(Block(section, body))
        buf.clear()

    for line in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^#{1,6}\s+(.*\S)\s*$", line)
        if m:
            flush()
            section = m.group(1)
        else:
            buf.append(line)
    flush()
    return blocks


_BULLET = re.compile(r"^([•●▪◦‣⁃·]|[-*])\s*(?=\S)")
_PAGE_NO = re.compile(r"^(page\s+)?\d{1,4}(\s*/\s*\d{1,4})?$", re.I)
# "9. Department-Based Knowledge Access" / "6.1 Custom Software Development": a short numbered line with no final punctuation
_HEADING = re.compile(r"^\d{1,2}(\.\d{1,2})*\.?\s+[A-Z؀-ۿ][^.!?:;]{2,80}$")


def _shape(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def pdf_blocks(pages: list[str]) -> list[Block]:
    """PDF text -> section blocks. Page headers/footers (a line that repeats on most pages, and bare page numbers) are
    dropped, bullet glyphs become '- ', lines wrapped by the page layout are re-joined, and a numbered heading starts a new
    section so sources can say 'Section 9' (PRD §30)."""
    lines_per_page = [[l.strip() for l in clean_text(p).split("\n")] for p in pages]
    seen: dict[str, int] = {}
    for lines in lines_per_page:
        for shape in {_shape(l) for l in lines if l}:
            seen[shape] = seen.get(shape, 0) + 1
    repeated = {k for k, n in seen.items() if len(pages) >= 3 and n >= max(3, 0.6 * len(pages))}
    blocks: list[Block] = []
    section, top, para = None, None, []
    body: list[str] = []

    def end_para():
        if para:
            body.append(" ".join(para))
            para.clear()

    def end_section():
        end_para()
        text = clean_text("\n".join(body))
        if text:
            blocks.append(Block(section, text))
        body.clear()

    for lines in lines_per_page:
        for line in lines:
            if not line:
                end_para()
                continue
            if _shape(line) in repeated or _PAGE_NO.match(line):
                continue
            m = _BULLET.match(line)
            bullet = m is not None
            if m:
                line = line[m.end():].strip()
            if not bullet and _HEADING.match(line):
                end_section()
                num = line.split()[0].rstrip(".")
                if "." not in num:
                    top = line                                                          # "6. Major Services"
                section = f"{top} > {line}" if top and "." in num and num.split(".")[0] == top.split()[0].rstrip(".") else line
                continue
            if bullet:
                end_para()
                para.append("- " + line)
            elif para and not para[-1].endswith((".", "!", "?", ":", "۔")) and (line[0].islower() or para[-1].startswith("- ")):
                para.append(line)                              # a wrapped line, not a new paragraph
            else:
                end_para()
                para.append(line)
    end_section()
    return blocks


def extract_blocks(extension: str, data: bytes) -> list[Block]:
    if extension == "pdf":
        from pypdf import PdfReader
        pages = [p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages]
        return pdf_blocks(pages)
    if extension == "docx":
        from docx import Document
        blocks, section, buf = [], None, []

        def flush():
            body = clean_text("\n".join(buf))
            if body:
                blocks.append(Block(section, body))
            buf.clear()

        for item in Document(io.BytesIO(data)).iter_inner_content():          # paragraphs AND tables, in document order
            if hasattr(item, "rows"):                                         # a table: one line per row, cells joined by " | "
                for row in item.rows:
                    cells = []
                    for cell in row.cells:                                    # merged cells repeat their text: keep it once
                        t = " ".join(cell.text.split())
                        if t and (not cells or cells[-1] != t):
                            cells.append(t)
                    if cells:
                        buf.append(" | ".join(cells))
            elif (item.style.name or "").lower().startswith("heading") and item.text.strip():
                flush()
                section = item.text.strip()
            else:
                buf.append(item.text)
        flush()
        return blocks
    text = data.decode("utf-8", errors="replace")
    if extension == "md":
        return markdown_blocks(text)
    if extension == "json":
        text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    text = clean_text(text)                                  # txt, csv, json
    return [Block(None, text)] if text else []
