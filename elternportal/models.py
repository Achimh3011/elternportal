"""Data models for portal messages."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Anhang:
    """Attachment referenced by a message."""

    url: str
    name: str


@dataclass(frozen=True)
class Brief:
    """Elternbrief (letter to all parents)."""

    ident: str
    nummer: str
    titel: str
    datum: datetime
    klassen: str
    bestaetigt: bool
    body_html: str
    anhaenge: tuple[Anhang, ...]


@dataclass(frozen=True)
class Nachricht:
    """Single message inside a thread or conversation."""

    absender: str
    datum: datetime | None
    body_html: str
    anhaenge: tuple[Anhang, ...]


@dataclass(frozen=True)
class ThreadLink:
    """Row of the Fachlehrer conversation list."""

    lehrer_id: int
    thread_id: int
    lehrer: str
    letzte_nachricht: datetime

    @property
    def ident(self) -> str:
        return f"{self.lehrer_id}-{self.thread_id}"


@dataclass(frozen=True)
class Thread:
    """Complete Fachlehrer conversation thread."""

    ident: str
    lehrer: str
    betreff: str
    kind: str
    letzte_nachricht: datetime
    nachrichten: tuple[Nachricht, ...]


@dataclass(frozen=True)
class Konversation:
    """Klassenleitung conversation (Kontaktanfrage)."""

    ident: str
    titel: str
    datum: datetime
    beantwortet: bool
    nachrichten: tuple[Nachricht, ...]


@dataclass(frozen=True)
class BrettEintrag:
    """Entry of the Schwarzes Brett."""

    ident: str
    titel: str
    datum: datetime
    body_html: str
    anhaenge: tuple[Anhang, ...]
