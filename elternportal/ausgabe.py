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
    if dokument.body.strip():
        click.echo(dokument.body.strip())
        _anhaenge_oeffnen(anhang_infos)
        return
    text = next((info.text for info in anhang_infos if _lesbar(info.text)), None)
    if text:
        click.echo(text.strip())
    else:
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
