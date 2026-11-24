"""Tests for the Elternbriefe parser."""

from elternportal.briefe import ist_briefe_seite, parse_briefe


def test_briefe_erkannt(fixture_html):
    assert ist_briefe_seite(fixture_html("elternbriefe.html"))
    assert not ist_briefe_seite(fixture_html("schwarzes_brett.html"))


def test_text_brief_parsen(fixture_html):
    briefs = parse_briefe(fixture_html("elternbriefe.html"))
    brief = briefs[0]
    assert brief.nummer == "12"
    assert brief.ident == "912"
    assert brief.eb_id == "912"
    assert brief.titel == "Kuchenbuffet beim Sommerfest"
    assert (brief.datum.year, brief.datum.month, brief.datum.day) == (2025, 7, 5)
    assert brief.klassen == "5b"
    assert brief.bestaetigt is False
    assert brief.anhaenge == ()
    assert "bitte bringt Kuchen mit." in brief.body_html


def test_brief_mit_anhaengen_parsen(fixture_html):
    briefs = parse_briefe(fixture_html("elternbriefe.html"))
    brief = briefs[1]
    assert brief.ident == "911"
    assert brief.nummer == "11"
    assert brief.bestaetigt is True
    assert brief.klassen == "5b, 6a"
    namen = [anhang.name for anhang in brief.anhaenge]
    assert namen == ["Praktikum Anschreiben.docx", "Praktikumstagebuch.docx"]
    assert all("get_file" in anhang.url for anhang in brief.anhaenge)


def test_altbrief_ohne_absatzmarken(fixture_html):
    """Older letters use plain text with <br> instead of <p> paragraphs."""
    briefs = parse_briefe(fixture_html("elternbriefe.html"))
    brief = briefs[2]
    assert brief.ident == "910"
    assert brief.titel == "Altbrief"
    assert brief.bestaetigt is True
    assert len(brief.anhaenge) == 1
    assert "Altbrief.pdf" not in brief.body_html
    assert "Klasse/n" not in brief.body_html
    assert "hier kommt Text ohne Absatzmarken." in brief.body_html


def test_leere_seite_liefert_keine_briefe():
    assert parse_briefe("<html><body></body></html>") == []
