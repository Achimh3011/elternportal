"""Tests for sending new messages as mail."""

from datetime import datetime, timedelta, timezone
from typing import Any

from elternportal.config import SmtpKonfiguration
from elternportal.mail import sende_mail
from elternportal.models import Anhang
from elternportal.store import AnhangInfo

_DATUM = datetime(2026, 11, 25, 14, 32, tzinfo=timezone(timedelta(hours=1)))


def _smtp(**kwargs: Any) -> SmtpKonfiguration:
    werte: dict[str, Any] = {
        "server": "mail.example.com",
        "port": 587,
        "starttls": True,
        "pass_eintrag": "",
        "absender": "",
    }
    werte.update(kwargs)
    return SmtpKonfiguration(**werte)


def _verbindung(mocker):
    smtp_klasse = mocker.patch("elternportal.mail.smtplib.SMTP")
    return smtp_klasse.return_value.__enter__.return_value


def test_sende_mail_baut_nachricht_und_versendet(mocker):
    verbindung = _verbindung(mocker)
    sende_mail(_smtp(), "benutzer", "geheim", ("an@example.com",), "Betreff", "Text", [], _DATUM)
    verbindung.starttls.assert_called_once()
    verbindung.login.assert_called_once_with("benutzer", "geheim")
    nachricht = verbindung.send_message.call_args.args[0]
    assert nachricht["From"] == "benutzer"
    assert nachricht["To"] == "an@example.com"
    assert nachricht["Subject"] == "Betreff"
    assert nachricht["Date"] == "Wed, 25 Nov 2026 14:32:00 +0100"


def test_absender_gewinnt_ueber_benutzer(mocker):
    verbindung = _verbindung(mocker)
    sende_mail(_smtp(absender="absender@example.com"), "benutzer", "geheim", ("an@example.com",), "B", "T", [], _DATUM)
    assert verbindung.send_message.call_args.args[0]["From"] == "absender@example.com"


def test_ohne_starttls_wird_kein_tls_verhandelt(mocker):
    verbindung = _verbindung(mocker)
    sende_mail(_smtp(starttls=False), "benutzer", "geheim", ("an@example.com",), "B", "T", [], _DATUM)
    verbindung.starttls.assert_not_called()
    verbindung.login.assert_called_once()


def test_unbekanntes_datum_faellt_auf_jetzt(mocker):
    verbindung = _verbindung(mocker)
    sende_mail(_smtp(), "benutzer", "geheim", ("an@example.com",), "B", "T", [], datetime.min)
    import email.utils

    datum = email.utils.parsedate_to_datetime(verbindung.send_message.call_args.args[0]["Date"])
    assert abs((datetime.now(datum.tzinfo) - datum).total_seconds()) < 60


def test_gespeicherte_anhaenge_werden_angehaengt(mocker, tmp_path):
    datei = tmp_path / "einladung.pdf"
    datei.write_bytes(b"%PDF-1.4 test")
    info = AnhangInfo(anhang=Anhang(url="u", name="einladung.pdf"), pfad=datei, text=None)
    verbindung = _verbindung(mocker)
    sende_mail(_smtp(), "benutzer", "geheim", ("an@example.com",), "B", "T", [info], _DATUM)
    nachricht = verbindung.send_message.call_args.args[0]
    anhaenge = list(nachricht.iter_attachments())
    assert len(anhaenge) == 1
    assert anhaenge[0].get_filename() == "einladung.pdf"
    assert anhaenge[0].get_content_type() == "application/pdf"
