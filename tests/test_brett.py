"""Tests for the Schwarzes Brett parser."""

from elternportal.brett import ist_brett_seite, parse_brett


def test_brett_erkannt(fixture_html):
    assert ist_brett_seite(fixture_html("schwarzes_brett.html"))
    assert not ist_brett_seite(fixture_html("elternbriefe.html"))


def test_aktive_eintraege_ohne_archiv(fixture_html):
    eintraege = parse_brett(fixture_html("schwarzes_brett.html"))
    titel = [eintrag.titel for eintrag in eintraege]
    assert titel == ["Nachhilfebörse", "Elternbeiratssitzung"]


def test_eintrag_mit_anhang(fixture_html):
    eintrag = parse_brett(fixture_html("schwarzes_brett.html"))[0]
    assert eintrag.ident == "63681"
    assert (eintrag.datum.year, eintrag.datum.month, eintrag.datum.day) == (2026, 11, 18)
    assert len(eintrag.anhaenge) == 1
    assert eintrag.anhaenge[0].name == "Nachhilfebörse.pdf"
    assert "Nachhilfeangeboten" in eintrag.body_html


def test_eintrag_ohne_anhang_bekommt_hash_ident(fixture_html):
    eintrag = parse_brett(fixture_html("schwarzes_brett.html"))[1]
    assert eintrag.ident.startswith("h")
    assert len(eintrag.ident) == 13
    assert eintrag.anhaenge == ()
