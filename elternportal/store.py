"""State tracking and Markdown output."""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from elternportal.extrakt import extrahiere_text, inline_limit_erreicht
from elternportal.models import Anhang
from elternportal.render import Dokument, dateikurzel

log = logging.getLogger(__name__)

_VERBOTENE_ZEICHEN = '<>:"/\\|?*'
_SESSION_CSRF_RE = re.compile(r"csrf=[0-9a-f]+")
_BESTAETIGT_RE = re.compile(r"bestaetigt=(True|False)")


class State:
    """Remembers seen messages across runs in a JSON file."""

    def __init__(self, pfad: Path):
        self._pfad = pfad
        self._daten: dict[str, dict[str, dict[str, str]]] = {}
        if pfad.exists():
            self._daten = json.loads(pfad.read_text(encoding="utf-8"))

    def ist_bekannt(self, portal: str, bereich: str, ident: str, pruefsumme: str) -> bool:
        """Check whether an entry with the same checksum was already stored."""
        return self._daten.get(portal, {}).get(bereich, {}).get(ident) == pruefsumme

    def merken(self, portal: str, bereich: str, ident: str, pruefsumme: str) -> None:
        """Record an entry as seen, with its checksum."""
        self._daten.setdefault(portal, {}).setdefault(bereich, {})[ident] = pruefsumme

    def sichern(self) -> None:
        """Write the state back to disk."""
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        self._pfad.write_text(json.dumps(self._daten, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        log.debug("State nach %s geschrieben", self._pfad)

    def uebertrage_von(self, alt_pfad: Path, portal: str) -> None:
        """One-time migration from a legacy shared state file.

        Adopts this portal's subtree from the old global state file so
        switching to the per-portal files does not re-fetch everything.
        Does nothing if the own state file already exists or the legacy
        file is gone.

        Args:
            alt_pfad: Legacy state file shared by all portals.
            portal: Portal slug whose entries to adopt.
        """
        if self._pfad.exists() or not alt_pfad.exists():
            return
        alt_daten = State(alt_pfad)._daten.get(portal)
        if alt_daten:
            self._daten = {portal: alt_daten}
            self.sichern()
            log.info("State von %s nach %s überführt", alt_pfad, self._pfad)


@dataclass(frozen=True)
class AnhangInfo:
    """A saved attachment with its extracted text."""

    anhang: Anhang
    pfad: Path
    text: str | None


def pruefsumme(eintrag: object) -> str:
    """Content checksum for any (frozen) dataclass from models.

    Session-bound CSRF tokens inside attachment URLs and the read
    confirmation state are ignored so that unchanged messages stay
    unchanged across runs.
    """
    normalized = _SESSION_CSRF_RE.sub("csrf=", repr(eintrag))
    normalized = _BESTAETIGT_RE.sub("bestaetigt=", normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def speichere_anhaenge(ziel: Path, anhaenge: tuple[Anhang, ...], inhalte: dict[str, bytes]) -> list[AnhangInfo]:
    """Save attachment files next to the Markdown output."""
    infos = []
    for anhang in anhaenge:
        pfad = ziel / _sicherer_name(anhang.name)
        pfad.write_bytes(inhalte[anhang.url])
        infos.append(AnhangInfo(anhang=anhang, pfad=pfad, text=extrahiere_text(pfad)))
    return infos


def schreibe_dokument(dokument: Dokument, portal: str, ziel: Path, anhang_infos: list[AnhangInfo]) -> Path:
    """Write one message as a Markdown file.

    Args:
        dokument: Rendered document (ident, title, body, frontmatter fields).
        portal: Portal slug for the frontmatter.
        ziel: Target directory (already contains saved attachments).
        anhang_infos: Saved attachments with extracted texts.

    Returns:
        Path of the written Markdown file.
    """
    datei = ziel / f"{_datum_kurzel(dokument.datum)}-{dokument.datei_kurzel}.md"
    datei.write_text(_markdown(dokument, portal, anhang_infos), encoding="utf-8")
    return datei


def _markdown(dokument: Dokument, portal: str, anhang_infos: list[AnhangInfo]) -> str:
    teile = [_frontmatter(dokument, portal), f"# {dokument.titel}", "", dokument.body]
    anhang_abschnitt = _anhang_abschnitt(anhang_infos)
    if anhang_abschnitt:
        teile.extend(["", anhang_abschnitt])
    return "\n".join(teile).rstrip() + "\n"


def _frontmatter(dokument: Dokument, portal: str) -> str:
    zeilen = [f"portal: {_yaml(portal)}", f"bereich: {_yaml(dokument.bereich)}", f"ident: {_yaml(dokument.ident)}"]
    if dokument.titel:
        zeilen.append(f"titel: {_yaml(dokument.titel)}")
    if dokument.datum != datetime.min:
        zeilen.append(f"datum: {dokument.datum:%Y-%m-%d %H:%M}")
    zeilen.extend(f"{schluessel}: {_yaml(wert)}" for schluessel, wert in dokument.felder.items())
    return "---\n" + "\n".join(zeilen) + "\n---\n"


def _anhang_abschnitt(infos: list[AnhangInfo]) -> str:
    if not infos:
        return ""
    zeilen = ["## Anhänge"]
    for info in infos:
        name = info.anhang.name or info.pfad.name
        zeilen.append(f"- [{name}]({info.pfad.name})")
    for info in infos:
        if not info.text:
            continue
        ueberschrift = f"### Text aus {info.pfad.name}"
        if inline_limit_erreicht(info.text):
            text_pfad = info.pfad.with_suffix(info.pfad.suffix + ".txt")
            text_pfad.write_text(info.text + "\n", encoding="utf-8")
            zeilen.extend(["", ueberschrift, "", f"[Vollständiger Text in {text_pfad.name}]({text_pfad.name})"])
        else:
            zeilen.extend(["", ueberschrift, "", info.text])
    return "\n".join(zeilen)


def _datum_kurzel(datum: datetime) -> str:
    if datum == datetime.min:
        return "ohne-datum"
    return f"{datum:%Y-%m-%d}"


def _sicherer_name(name: str) -> str:
    bereinigt = name.split("/")[-1].split("\\")[-1]
    bereinigt = "".join("-" if zeichen in _VERBOTENE_ZEICHEN else zeichen for zeichen in bereinigt)
    return bereinigt.strip() or f"anhang-{dateikurzel(name)}"


def _yaml(wert: str) -> str:
    return '"' + wert.replace("\\", "\\\\").replace('"', '\\"') + '"'
