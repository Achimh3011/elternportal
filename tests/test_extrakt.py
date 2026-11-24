"""Tests for attachment text extraction (PDF via pdftotext, DOCX via zipfile)."""

import zipfile
from pathlib import Path

from elternportal.extrakt import extrahiere_text, inline_limit_erreicht

_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_pdf_text_extraction(tmp_path):
    pdf = _baue_pdf(tmp_path / "brief.pdf", "Hallo aus dem PDF")
    text = extrahiere_text(pdf)
    assert text is not None
    assert "Hallo aus dem PDF" in text


def test_docx_text_extraction(tmp_path):
    docx = _baue_docx(tmp_path / "brief.docx", ["Erste Zeile", "Zweite Zeile"])
    text = extrahiere_text(docx)
    assert text == "Erste Zeile\nZweite Zeile"


def test_unterstuetzte_dateien_geliefert(tmp_path):
    datei = tmp_path / "foto.png"
    datei.write_bytes(b"\x89PNG")
    assert extrahiere_text(datei) is None


def test_defekte_datei_liefert_none(tmp_path):
    docx = tmp_path / "kaputt.docx"
    docx.write_bytes(b"kein zip")
    assert extrahiere_text(docx) is None


def test_inline_limit():
    assert not inline_limit_erreicht("kurz")
    assert inline_limit_erreicht("x" * 5001)


def _baue_docx(pfad: Path, absaetze: list[str]) -> Path:
    koerper = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in absaetze)
    dokument = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{_WORD_NS}"><w:body>{koerper}</w:body></w:document>'
    )
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("word/document.xml", dokument)
    return pfad


def _baue_pdf(pfad: Path, text: str) -> Path:
    """Build a minimal valid PDF with a single text line."""
    zeilen = [
        "%PDF-1.1",
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj",
        "4 0 obj\n<< /Length _STREAM_LEN_ >>\nstream\nBT\n/F1 18 Tf\n72 700 Td\n(?) Tj\nET\nendstream\nendobj",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj",
    ]
    stream = f"BT\n/F1 18 Tf\n72 700 Td\n({text}) Tj\nET"
    zeilen[4] = f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj"
    pdf = "\n".join(zeilen)
    offsets = []
    position = 0
    for zeile in zeilen:
        offsets.append(position)
        position += len(zeile) + 1
    xref = f"xref\n0 {len(zeilen) + 1}\n0000000000 65535 f \n"
    xref += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    trailer = f"trailer\n<< /Size {len(zeilen) + 1} /Root 1 0 R >>\nstartxref\n{position}\n%%EOF\n"
    pfad.write_text(pdf + "\n" + xref + trailer, encoding="latin-1")
    return pfad
