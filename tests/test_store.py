"""Tests for state tracking and Markdown writing."""

from datetime import datetime
from pathlib import Path

from elternportal.models import Anhang
from elternportal.render import Dokument
from elternportal.store import AnhangInfo, State, pruefsumme, schreibe_dokument, speichere_anhaenge


def test_state_zyklus(tmp_path):
    state = State(tmp_path / "state.json")
    assert not state.ist_bekannt("los", "elternbriefe", "1", "abc")
    state.merken("los", "elternbriefe", "1", "abc")
    state.sichern()
    geladen = State(tmp_path / "state.json")
    assert geladen.ist_bekannt("los", "elternbriefe", "1", "abc")
    assert not geladen.ist_bekannt("los", "elternbriefe", "1", "anders")
    assert not geladen.ist_bekannt("los", "brett", "1", "abc")


def test_uebertragung_uebernimmt_nur_das_eigene_portal(tmp_path):
    alt = State(tmp_path / "alt-state.json")
    alt.merken("los", "elternbriefe", "1", "abc")
    alt.merken("mwg", "elternbriefe", "2", "def")
    alt.sichern()
    state = State(tmp_path / "los" / "state.json")
    state.uebertrage_von(alt._pfad, "los")
    assert state.ist_bekannt("los", "elternbriefe", "1", "abc")
    assert not state.ist_bekannt("mwg", "elternbriefe", "2", "def")
    assert State(tmp_path / "los" / "state.json").ist_bekannt("los", "elternbriefe", "1", "abc")


def test_uebertragung_ueberschreibt_nichts_und_ignoriert_fehlende_alt_datei(tmp_path):
    alt = State(tmp_path / "alt-state.json")
    alt.merken("los", "elternbriefe", "1", "abc")
    alt.sichern()
    vorhanden = State(tmp_path / "los" / "state.json")
    vorhanden.merken("los", "elternbriefe", "9", "xyz")
    vorhanden.sichern()
    vorhanden.uebertrage_von(alt._pfad, "los")
    assert vorhanden.ist_bekannt("los", "elternbriefe", "9", "xyz")
    assert not vorhanden.ist_bekannt("los", "elternbriefe", "1", "abc")
    leer = State(tmp_path / "mwg" / "state.json")
    leer.uebertrage_von(tmp_path / "gibt-es-nicht.json", "mwg")
    assert not (tmp_path / "mwg").exists()


def test_uebertragung_ohne_alt_daten_schreibt_nichts(tmp_path):
    alt = State(tmp_path / "alt-state.json")
    alt.merken("mwg", "elternbriefe", "2", "def")
    alt.sichern()
    state = State(tmp_path / "los" / "state.json")
    state.uebertrage_von(alt._pfad, "los")
    assert not state._pfad.exists()


def test_pruefsumme_ist_stabil_und_inhaltssensitiv():
    from elternportal.models import Brief

    brief = Brief(
        ident="1",
        nummer="1",
        titel="Titel",
        datum=datetime(2026, 1, 1),
        klassen="5b",
        bestaetigt=False,
        body_html="<p>Hi</p>",
        anhaenge=(),
    )
    gleich = Brief(
        ident="1",
        nummer="1",
        titel="Titel",
        datum=datetime(2026, 1, 1),
        klassen="5b",
        bestaetigt=False,
        body_html="<p>Hi</p>",
        anhaenge=(),
    )
    anders = Brief(
        ident="1",
        nummer="1",
        titel="Titel",
        datum=datetime(2026, 1, 1),
        klassen="5b",
        bestaetigt=False,
        body_html="<p>Hi!</p>",
        anhaenge=(),
    )
    assert pruefsumme(brief) == pruefsumme(gleich)
    assert pruefsumme(brief) != pruefsumme(anders)


def test_pruefsumme_ignoriert_session_csrf():
    """Attachment URLs contain a per-session CSRF token that must not change sums."""
    from elternportal.models import Brief

    def brief(csrf: str) -> Brief:
        return Brief(
            ident="911",
            nummer="11",
            titel="Titel",
            datum=datetime(2026, 1, 1),
            klassen="5b",
            bestaetigt=True,
            body_html="<p>Hi</p>",
            anhaenge=(Anhang(url=f"aktuelles/get_file/?repo=1&csrf={csrf}", name="a.pdf"),),
        )

    assert pruefsumme(brief("aaaabbbbccccdddd")) == pruefsumme(brief("0123456789abcdef"))
    assert pruefsumme(brief("aaaabbbbccccdddd")) != pruefsumme(brief("x"))


def test_pruefsumme_ignoriert_bestaetigt_status():
    """Confirming a brief must not mark it as changed on the next run."""
    from elternportal.models import Brief

    def brief(bestaetigt: bool) -> Brief:
        return Brief(
            ident="911",
            nummer="11",
            titel="Titel",
            datum=datetime(2026, 1, 1),
            klassen="5b",
            bestaetigt=bestaetigt,
            body_html="<p>Hi</p>",
            anhaenge=(),
        )

    assert pruefsumme(brief(True)) == pruefsumme(brief(False))


def test_dokument_schreiben(tmp_path):
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-kuchenbuffet-beim-sommerfest",
        titel='Kuchenbuffet "beim Sommerfest"',
        datum=datetime(2025, 7, 5, 8, 15),
        felder={"kind": "Max Musterkind"},
        body="Bringt Kuchen mit.",
    )
    datei = schreibe_dokument(dokument, "los", tmp_path, [])
    assert datei.name == "2025-07-05-12-kuchenbuffet-beim-sommerfest.md"
    inhalt = datei.read_text(encoding="utf-8")
    assert inhalt.startswith("---\n")
    assert 'portal: "los"' in inhalt
    assert 'titel: "Kuchenbuffet \\"beim Sommerfest\\""' in inhalt
    assert 'kind: "Max Musterkind"' in inhalt
    assert "datum: 2025-07-05 08:15" in inhalt
    assert '# Kuchenbuffet "beim Sommerfest"' in inhalt
    assert "Bringt Kuchen mit." in inhalt
    assert "## Anhänge" not in inhalt


def test_dokument_mit_anhang_inline(tmp_path):
    pdf = tmp_path / "flyer.pdf"
    pdf.write_bytes(b"%PDF-fake")
    infos = [AnhangInfo(anhang=Anhang(url="u", name="flyer.pdf"), pfad=pdf, text="Inhalt des Flyers")]
    dokument = Dokument(
        ident="1",
        bereich="brett",
        datei_kurzel="flyer",
        titel="Flyer",
        datum=datetime(2026, 11, 18),
        body="Siehe Anhang.",
    )
    inhalt = schreibe_dokument(dokument, "los", tmp_path, infos).read_text(encoding="utf-8")
    assert "- [flyer.pdf](flyer.pdf)" in inhalt
    assert "### Text aus flyer.pdf" in inhalt
    assert "Inhalt des Flyers" in inhalt


def test_anhang_speichern_und_langer_text(tmp_path, mocker):
    datei = tmp_path / "lang.txt"
    datei.write_text("x" * 100)
    mocker.patch("elternportal.store.extrahiere_text", return_value="y" * 6000)
    dokument = Dokument(
        ident="1", bereich="brett", datei_kurzel="eintrag", titel="Eintrag", datum=datetime(2026, 11, 18), body="Körper"
    )
    anhang = Anhang(url="https://portal/file", name="lange datei.txt")
    infos = speichere_anhaenge(tmp_path, (anhang,), {anhang.url: b"in"})
    assert (tmp_path / "lange datei.txt").read_bytes() == b"in"
    assert infos[0].text == "y" * 6000
    inhalt = schreibe_dokument(dokument, "los", tmp_path, infos).read_text(encoding="utf-8")
    assert "Vollständiger Text in lange datei.txt.txt" in inhalt
    assert (tmp_path / "lange datei.txt.txt").exists()


def test_dokument_ohne_datum(tmp_path: Path):
    dokument = Dokument(
        ident="1", bereich="brett", datei_kurzel="eintrag", titel="Ohne Datum", datum=datetime.min, body="Körper"
    )
    datei = schreibe_dokument(dokument, "los", tmp_path, [])
    assert datei.name == "ohne-datum-eintrag.md"
    assert "datum:" not in datei.read_text(encoding="utf-8")
