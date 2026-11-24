"""Tests for the communication parsers (Fachlehrer, Klassenleitung)."""

from datetime import datetime

from elternportal.kommunikation import (
    ist_fachlehrer_seite,
    ist_klassenleitung_seite,
    parse_klassenleitung,
    parse_thread,
    parse_thread_links,
)
from elternportal.models import ThreadLink


def test_fachlehrer_seite_erkannt(fixture_html):
    assert ist_fachlehrer_seite(fixture_html("fachlehrer_liste.html"))
    assert not ist_fachlehrer_seite(fixture_html("klassenleitung.html"))


def test_thread_links_parsen(fixture_html):
    links = parse_thread_links(fixture_html("fachlehrer_liste.html"))
    assert len(links) == 2
    assert links[0].ident == "21-5001"
    assert links[0].lehrer == "Erika Mustermann"
    assert links[0].letzte_nachricht == datetime(2026, 11, 23, 13, 44)
    assert links[1].ident == "13-5002"
    assert links[1].lehrer == "Max Beispiellehrer"


def test_thread_parsen_mit_anhaengen(fixture_html):
    link = ThreadLink(
        lehrer_id=21, thread_id=5001, lehrer="Erika Mustermann", letzte_nachricht=datetime(2026, 11, 23, 13, 44)
    )
    thread = parse_thread(fixture_html("fachlehrer_thread.html"), link)
    assert thread.ident == "21-5001"
    assert thread.betreff == "Reminder: Weihnachtspäckchenaktion"
    assert thread.kind == "Max Musterkind"
    assert len(thread.nachrichten) == 2
    erste, zweite = thread.nachrichten
    assert erste.absender == "Erika Mustermann"
    assert erste.datum == datetime(2026, 11, 23, 13, 44)
    assert [anhang.name for anhang in erste.anhaenge] == ["Flyer_Weihnachtspäckchenaktion.pdf"]
    assert zweite.absender == "Sie"
    assert zweite.anhaenge == ()
    assert "wir packen ein Päckchen." in zweite.body_html


def test_klassenleitung_seite_erkannt(fixture_html):
    assert ist_klassenleitung_seite(fixture_html("klassenleitung.html"))
    assert not ist_klassenleitung_seite(fixture_html("fachlehrer_liste.html"))


def test_konversationen_parsen(fixture_html):
    konversationen = parse_klassenleitung(fixture_html("klassenleitung.html"))
    assert len(konversationen) == 2
    erste, zweite = konversationen
    assert erste.titel == "Beratungsgespräch"
    assert erste.beantwortet is True
    assert erste.datum == datetime(2024, 7, 10)
    assert len(erste.nachrichten) == 2
    anfrage, antwort = erste.nachrichten
    assert anfrage.absender == "Eltern"
    assert antwort.absender == "Klassenleitung"
    assert antwort.datum == datetime(2024, 7, 11)
    assert "Montag" in antwort.body_html
    assert zweite.ident == "6245"
    assert zweite.beantwortet is False
    assert len(zweite.nachrichten) == 1
