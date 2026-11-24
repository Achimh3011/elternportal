"""Tests for the document rendering."""

from datetime import datetime

from elternportal.models import (
    Anhang,
    BrettEintrag,
    Brief,
    Konversation,
    Nachricht,
    Thread,
    ThreadLink,
)
from elternportal.render import (
    brief_dokument,
    brett_dokument,
    dateikurzel,
    konversation_dokument,
    thread_dokument,
    threadlink_pruefsumme,
)


def _brief() -> Brief:
    return Brief(
        ident="912",
        nummer="12",
        titel="Kuchenbuffet beim Sommerfest",
        datum=datetime(2025, 7, 5, 8, 15),
        klassen="5b",
        bestaetigt=False,
        body_html="<p>Bringt <strong>Kuchen</strong> mit.</p>",
        anhaenge=(),
    )


def test_dateikurzel():
    assert dateikurzel("Kuchenbuffet beim Sommerfest") == "kuchenbuffet-beim-sommerfest"
    assert dateikurzel("Grüße aus München!") == "gruesse-aus-muenchen"
    assert dateikurzel("///") == "ohne-titel"
    assert dateikurzel("") == "ohne-titel"


def test_brief_dokument():
    dokument = brief_dokument(_brief(), "Max Musterkind")
    assert dokument.bereich == "elternbriefe"
    assert dokument.datei_kurzel == "12-kuchenbuffet-beim-sommerfest"
    assert dokument.felder["nummer"] == "12"
    assert dokument.felder["kind"] == "Max Musterkind"
    assert dokument.body == "Bringt **Kuchen** mit."


def test_brett_dokument():
    eintrag = BrettEintrag(
        ident="63681",
        titel="Nachhilfebörse",
        datum=datetime(2026, 11, 18),
        body_html="<p>Liste</p>",
        anhaenge=(Anhang(url="u", name="boerse.pdf"),),
    )
    dokument = brett_dokument(eintrag, "Max Musterkind")
    assert dokument.datei_kurzel == "63681-nachhilfeboerse"
    assert dokument.anhaenge == (Anhang(url="u", name="boerse.pdf"),)


def test_thread_dokument_sammelt_anhaenge():
    thread = Thread(
        ident="21-5001",
        lehrer="Erika Mustermann",
        betreff="Reminder",
        kind="Max Musterkind",
        letzte_nachricht=datetime(2026, 11, 24, 9, 12),
        nachrichten=(
            Nachricht(
                absender="Erika Mustermann",
                datum=datetime(2026, 11, 23, 13, 44),
                body_html="<div>Liebe Eltern,</div>",
                anhaenge=(Anhang(url="u1", name="flyer.pdf"),),
            ),
            Nachricht(absender="Sie", datum=datetime(2026, 11, 24, 9, 12), body_html="<div>Danke!</div>", anhaenge=()),
        ),
    )
    dokument = thread_dokument(thread, "")
    assert dokument.anhaenge == (Anhang(url="u1", name="flyer.pdf"),)
    assert "### Erika Mustermann (23.11.2026 13:44)" in dokument.body
    assert "### Sie (24.11.2026 09:12)" in dokument.body
    assert "---" in dokument.body
    assert dokument.titel == "Reminder (Erika Mustermann)"


def test_konversation_dokument():
    konversation = Konversation(
        ident="6245",
        titel="Frage zum Stundenplan",
        datum=datetime(2025, 9, 1),
        beantwortet=False,
        nachrichten=(Nachricht(absender="Eltern", datum=datetime(2025, 9, 1), body_html="<p>Wann?</p>", anhaenge=()),),
    )
    dokument = konversation_dokument(konversation, "Max Musterkind")
    assert dokument.bereich == "klassenleitung"
    assert "### Eltern (01.09.2025 00:00)" in dokument.body
    assert dokument.felder["beantwortet"] == "false"


def test_threadlink_pruefsumme_aendert_sich_mit_datum():
    basis = ThreadLink(
        lehrer_id=21, thread_id=5001, lehrer="Erika Mustermann", letzte_nachricht=datetime(2026, 11, 23, 13, 44)
    )
    aktualisiert = ThreadLink(
        lehrer_id=21, thread_id=5001, lehrer="Erika Mustermann", letzte_nachricht=datetime(2026, 11, 25, 8, 0)
    )
    assert threadlink_pruefsumme(basis) != threadlink_pruefsumme(aktualisiert)
    assert threadlink_pruefsumme(basis) == threadlink_pruefsumme(basis)
