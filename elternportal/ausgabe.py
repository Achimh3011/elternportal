"""Terminal output for newly fetched messages."""

import platform
import subprocess
from pathlib import Path

import rich_click as click

from elternportal.render import Dokument
from elternportal.store import AnhangInfo

_OEFFNER = {"linux": "xdg-open", "darwin": "open"}
_ERLAUBTE_ZEICHEN = set(".,;:!?-_()[]{}\"'„“”«»/\\@€%&=*+#<>|~^°§…\u2013\u2014")
_MIN_TEXT_LAENGE = 100
_MIN_SAUBER_QUOTE = 0.9


def anzeige_text(dokument: Dokument, anhang_infos: list[AnhangInfo]) -> str:
    """The message text for display: the body, or the extracted attachment text.

    Messages without a text body fall back to the extracted text of the
    first reasonably readable attachment; if none is readable, the
    result is empty.

    Args:
        dokument: Rendered document to display.
        anhang_infos: Saved attachments with extracted texts.

    Returns:
        The text to show or mail, possibly empty.
    """
    if dokument.body.strip():
        return dokument.body.strip()
    return next(((info.text or "").strip() for info in anhang_infos if _lesbar(info.text)), "")


def zeige_dokument(dokument: Dokument, anhang_infos: list[AnhangInfo]) -> None:
    """Print a new message to the terminal, opening files where needed.

    Messages with a text body are printed as Markdown and their
    attachments are opened externally. Messages without a text body
    are printed from the extracted attachment text if that is
    reasonably readable, otherwise the attachments are opened.

    Args:
        dokument: Rendered document to display.
        anhang_infos: Saved attachments with extracted texts.
    """
    click.secho(f"═══ {dokument.titel} ═══", bold=True)
    text = anzeige_text(dokument, anhang_infos)
    if text:
        click.echo(text)
    if not text or dokument.body.strip():
        _anhaenge_oeffnen(anhang_infos)


def oeffne_datei(pfad: Path) -> None:
    """Open a file with the platform's default application."""
    programm = _OEFFNER.get(platform.system().lower())
    if programm is None:
        click.secho(f"Kann {pfad.name} nicht automatisch öffnen (unbekanntes System).", fg="yellow")
        return
    subprocess.run([programm, str(pfad)], check=False)


def _anhaenge_oeffnen(anhang_infos: list[AnhangInfo]) -> None:
    for info in anhang_infos:
        oeffne_datei(info.pfad)


def _lesbar(text: str | None) -> bool:
    """Whether extracted attachment text is reasonably clean for display."""
    if not text or len(text) < _MIN_TEXT_LAENGE:
        return False
    sauber = sum(1 for zeichen in text if zeichen.isalnum() or zeichen.isspace() or zeichen in _ERLAUBTE_ZEICHEN)
    return sauber / len(text) >= _MIN_SAUBER_QUOTE
