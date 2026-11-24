"""Tests for the HTML to Markdown converter."""

from elternportal.markdown import html_to_markdown


def test_absaetze_und_hervorhebungen():
    assert html_to_markdown("<p>Hallo <strong>Welt</strong>!</p>") == "Hallo **Welt**!"


def test_zwei_absaetze():
    assert html_to_markdown("<p>Erster</p><p>Zweiter</p>") == "Erster\n\nZweiter"


def test_zeilenumbruch_und_divs():
    assert html_to_markdown("<div>Zeile<br />Neu</div>") == "Zeile\nNeu"


def test_link():
    assert (
        html_to_markdown("<p>Schaut <a href='https://example.org'>hier</a></p>") == "Schaut [hier](https://example.org)"
    )


def test_ueberschrift():
    assert html_to_markdown("<h4>Wichtig</h4>") == "#### Wichtig"


def test_liste():
    assert html_to_markdown("<ul><li>Eins</li><li>Zwei</li></ul>") == "- Eins\n- Zwei"


def test_leere_eingabe():
    assert html_to_markdown("") == ""
    assert html_to_markdown("   ") == ""
