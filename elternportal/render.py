"""Convert parsed models into generic documents for the Markdown store."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from elternportal.markdown import html_to_markdown
from elternportal.models import BrettEintrag, Brief, Konversation, Thread, ThreadLink

_UMSCHREIBUNGEN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_KEIN_KURZEL_RE = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class Dokument:
    """Generic representation of one message to store as Markdown."""

    ident: str
    bereich: str
    datei_kurzel: str
    titel: str
    datum: datetime
    felder: dict[str, str] = field(default_factory=dict)
    body: str = ""
    anhaenge: tuple = ()


def dateikurzel(text: str, laenge: int = 40) -> str:
    """Turn a title into a filesystem-friendly name fragment."""
    kurz = text.lower().translate(_UMSCHREIBUNGEN)
    kurz = _KEIN_KURZEL_RE.sub("-", kurz).strip("-")
    while "--" in kurz:
        kurz = kurz.replace("--", "-")
    return kurz[:laenge].rstrip("-") or "ohne-titel"


def brief_dokument(brief: Brief, kind: str) -> Dokument:
    """Render an Elternbrief into a document."""
    return Dokument(
        ident=brief.ident,
        bereich="elternbriefe",
        datei_kurzel=f"{brief.nummer}-{dateikurzel(brief.titel)}",
        titel=brief.titel,
        datum=brief.datum,
        felder={
            "nummer": brief.nummer,
            "klassen": brief.klassen,
            "bestaetigt": str(brief.bestaetigt).lower(),
            "kind": kind,
        },
        body=html_to_markdown(brief.body_html),
        anhaenge=brief.anhaenge,
    )


def brett_dokument(eintrag: BrettEintrag, kind: str) -> Dokument:
    """Render a Schwarzes Brett entry into a document."""
    return Dokument(
        ident=eintrag.ident,
        bereich="brett",
        datei_kurzel=f"{eintrag.ident}-{dateikurzel(eintrag.titel)}",
        titel=eintrag.titel,
        datum=eintrag.datum,
        felder={"kind": kind},
        body=html_to_markdown(eintrag.body_html),
        anhaenge=eintrag.anhaenge,
    )


def thread_dokument(thread: Thread, kind: str) -> Dokument:
    """Render a Fachlehrer conversation into a document."""
    return Dokument(
        ident=thread.ident,
        bereich="fachlehrer",
        datei_kurzel=f"{thread.ident.split('-')[-1]}-{dateikurzel(thread.betreff or thread.lehrer)}",
        titel=f"{thread.betreff} ({thread.lehrer})",
        datum=thread.letzte_nachricht,
        felder={
            "lehrer": thread.lehrer,
            "betreff": thread.betreff,
            "letzte_nachricht": _uhrzeit(thread.letzte_nachricht),
            "kind": thread.kind or kind,
        },
        body=_nachrichten_body(thread.nachrichten),
        anhaenge=tuple(anhang for nachricht in thread.nachrichten for anhang in nachricht.anhaenge),
    )


def konversation_dokument(konversation: Konversation, kind: str) -> Dokument:
    """Render a Klassenleitung conversation into a document."""
    return Dokument(
        ident=konversation.ident,
        bereich="klassenleitung",
        datei_kurzel=f"{konversation.ident}-{dateikurzel(konversation.titel)}",
        titel=konversation.titel,
        datum=konversation.datum,
        felder={
            "beantwortet": str(konversation.beantwortet).lower(),
            "letzte_nachricht": _uhrzeit(konversation.datum),
            "kind": kind,
        },
        body=_nachrichten_body(konversation.nachrichten),
        anhaenge=(),
    )


def threadlink_pruefsumme(link: ThreadLink) -> str:
    """Stable checksum input for a thread as seen on the overview page."""
    return f"{link.lehrer_id}-{link.thread_id}-{link.letzte_nachricht:%Y%m%d%H%M}-{link.lehrer}"


def _nachrichten_body(nachrichten) -> str:
    abschnitte = []
    for nachricht in nachrichten:
        kopf = f"### {nachricht.absender}"
        if nachricht.datum is not None:
            kopf += f" ({_uhrzeit(nachricht.datum)})"
        inhalt = html_to_markdown(nachricht.body_html).strip()
        abschnitte.append(f"{kopf}\n\n{inhalt}" if inhalt else kopf)
    return "\n\n---\n\n".join(abschnitte)


def _uhrzeit(datum: datetime) -> str:
    if datum == datetime.min:
        return "unbekannt"
    return f"{datum:%d.%m.%Y %H:%M}"
