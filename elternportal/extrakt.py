"""Text extraction from PDF and DOCX attachments."""

import logging
import zipfile
from pathlib import Path
from subprocess import run

from lxml import etree

log = logging.getLogger(__name__)

_MAX_INLINE_ZEICHEN = 5000
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extrahiere_text(pfad: Path) -> str | None:
    """Extract plain text from a saved attachment, if the type is supported.

    Args:
        pfad: Path of the already saved attachment.

    Returns:
        Extracted text, or None if unsupported, empty or broken.
    """
    suffix = pfad.suffix.lower()
    try:
        if suffix == ".pdf":
            return _pdf_text(pfad)
        if suffix == ".docx":
            return _docx_text(pfad)
    except OSError, zipfile.BadZipFile, etree.XMLSyntaxError:
        log.warning("Textextraktion schlug fehl für %s", pfad.name, exc_info=True)
        return None
    log.debug("Keine Textextraktion für %s", pfad.name)
    return None


def inline_limit_erreicht(text: str) -> bool:
    """Whether extracted text is too long to inline into the Markdown file."""
    return len(text) > _MAX_INLINE_ZEICHEN


def _pdf_text(pfad: Path) -> str | None:
    resultat = run(["pdftotext", "-layout", pfad.as_posix(), "-"], capture_output=True, text=True, check=False)
    if resultat.returncode != 0:
        log.warning("pdftotext schlug fehl für %s: %s", pfad.name, resultat.stderr.strip())
        return None
    return resultat.stdout.strip() or None


def _docx_text(pfad: Path) -> str | None:
    with zipfile.ZipFile(pfad) as archiv:
        xml = archiv.read("word/document.xml")
    wurzel = etree.fromstring(xml)
    absaetze = wurzel.xpath("//w:p", namespaces={"w": _WORD_NS})
    text = "\n".join("".join(t.text or "" for t in p.xpath(".//w:t", namespaces={"w": _WORD_NS})) for p in absaetze)
    return text.strip() or None
