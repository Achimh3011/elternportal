"""Tests for the terminal output of new messages."""

from datetime import datetime
from pathlib import Path

from elternportal.ausgabe import _lesbar, anzeige_text, oeffne_datei, zeige_dokument
from elternportal.models import Anhang
from elternportal.render import Dokument
from elternportal.store import AnhangInfo


def _dokument(body: str = "") -> Dokument:
    return Dokument(
        ident="1", bereich="elternbriefe", datei_kurzel="kurzel", titel="Titel", datum=datetime(2026, 11, 24), body=body
    )


def _info(pfad: Path, text: str | None = None) -> AnhangInfo:
    return AnhangInfo(anhang=Anhang(url="u", name=pfad.name), pfad=pfad, text=text)


def test_textmeldung_wird_ausgegeben_und_anhaenge_geoeffnet(tmp_path, capsys, mocker):
    oeffnen = mocker.patch("elternportal.ausgabe.oeffne_datei")
    pdf = tmp_path / "anhang.pdf"
    pdf.write_bytes(b"x")
    zeige_dokument(_dokument(body="Hier steht der Text."), [_info(pdf)])
    ausgabe = capsys.readouterr().out
    assert "Titel" in ausgabe
    assert "Hier steht der Text." in ausgabe
    oeffnen.assert_called_once_with(pdf)


def test_ohne_text_lesbarer_anhangstext_wird_ausgegeben(tmp_path, capsys, mocker):
    oeffnen = mocker.patch("elternportal.ausgabe.oeffne_datei")
    pdf = tmp_path / "brief.pdf"
    text = "Sehr geehrte Eltern, " + "hier steht ein gut lesbarer extrahierter Text aus dem Anhang. " * 2
    zeige_dokument(_dokument(), [_info(pdf, text=text)])
    ausgabe = capsys.readouterr().out
    assert "lesbarer" in ausgabe
    oeffnen.assert_not_called()


def test_ohne_text_unlesbarer_anhang_wird_geoeffnet(tmp_path, capsys, mocker):
    oeffnen = mocker.patch("elternportal.ausgabe.oeffne_datei")
    pdf = tmp_path / "scan.pdf"
    zeige_dokument(_dokument(), [_info(pdf, text="\x00\x01\x02" * 100)])
    assert "Titel" in capsys.readouterr().out
    oeffnen.assert_called_once_with(pdf)


def test_ohne_text_und_ohne_anhaenge_macht_nichts(capsys, mocker):
    oeffnen = mocker.patch("elternportal.ausgabe.oeffne_datei")
    zeige_dokument(_dokument(), [])
    assert "Titel" in capsys.readouterr().out
    oeffnen.assert_not_called()


def test_lesbar_heuristik():
    gut = "Sehr geehrte Eltern, dies ist ein gut lesbarer, langer Text mit 100+ Zeichen zur Bewertung. " * 2
    assert _lesbar(gut)
    assert not _lesbar(None)
    assert not _lesbar("kurz")
    assert not _lesbar("h" * 200 + "\x00\x01\x02" * 100)


def test_anzeige_text_ist_der_body(tmp_path):
    assert anzeige_text(_dokument(body="Hier steht der Text."), []) == "Hier steht der Text."


def test_anzeige_text_faellt_auf_lesbaren_anhangstext_zurueck(tmp_path):
    text = "Sehr geehrte Eltern, " + "hier steht ein gut lesbarer extrahierter Text aus dem Anhang. " * 2
    pdf = tmp_path / "brief.pdf"
    assert anzeige_text(_dokument(), [_info(pdf, text=f"  {text}  ")]) == text.strip()


def test_anzeige_text_leer_ohne_lesbaren_anhangstext(tmp_path):
    pdf = tmp_path / "scan.pdf"
    assert anzeige_text(_dokument(), [_info(pdf, text="\x00\x01\x02" * 100)]) == ""
    assert anzeige_text(_dokument(), []) == ""


def test_oeffne_datei_ruft_programm_auf(mocker, tmp_path):
    run = mocker.patch("elternportal.ausgabe.subprocess.run", return_value=None)
    mocker.patch("elternportal.ausgabe.platform.system", return_value="Linux")
    datei = tmp_path / "x.pdf"
    datei.write_bytes(b"x")
    oeffne_datei(datei)
    run.assert_called_once_with(["xdg-open", str(datei)], check=False)
