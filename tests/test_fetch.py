"""Tests for the fetch CLI helpers (read confirmation pass)."""

from datetime import datetime

from elternportal.config import PortalKonfiguration
from elternportal.fetch import LaufKontext, _briefe_bestaetigen
from elternportal.models import Brief
from elternportal.store import State


def _brief(nummer: str, eb_id: str, bestaetigt: bool) -> Brief:
    return Brief(
        ident=eb_id or nummer,
        nummer=nummer,
        titel="Titel",
        datum=datetime(2026, 1, 1),
        klassen="",
        bestaetigt=bestaetigt,
        body_html="",
        anhaenge=(),
        eb_id=eb_id,
    )


def _kontext(
    client, tmp_path, *, bestaetigen: bool = True, trocken: bool = False, ausgeben: bool = True, letzte: int = 0
) -> LaufKontext:
    portal = PortalKonfiguration(slug="los", pass_eintrag="familie/los", bereiche=(), output_dir=tmp_path)
    return LaufKontext(
        client, portal, "Kind", tmp_path, State(tmp_path / "state.json"), trocken, bestaetigen, ausgeben, letzte
    )


def test_unbestaetigte_briefe_werden_bestätigt(mocker, tmp_path):
    client = mocker.Mock()
    brief_liste = [
        _brief("3", "913", bestaetigt=False),
        _brief("2", "912", bestaetigt=True),
        _brief("1", "", bestaetigt=False),
    ]
    _briefe_bestaetigen(_kontext(client, tmp_path), brief_liste)
    client.brief_bestaetigen.assert_called_once_with("913")


def test_bestaetigung_abschaltbar(mocker, tmp_path):
    client = mocker.Mock()
    _briefe_bestaetigen(_kontext(client, tmp_path, bestaetigen=False), [_brief("3", "913", bestaetigt=False)])
    client.brief_bestaetigen.assert_not_called()


def test_bestaetigung_nicht_im_dry_run(mocker, tmp_path):
    client = mocker.Mock()
    _briefe_bestaetigen(_kontext(client, tmp_path, trocken=True), [_brief("3", "913", bestaetigt=False)])
    client.brief_bestaetigen.assert_not_called()


def test_bestätigungsfehler_bricht_nicht_ab(mocker, tmp_path):
    import httpx2

    client = mocker.Mock()
    client.brief_bestaetigen.side_effect = httpx2.HTTPError("Server disconnected")
    _briefe_bestaetigen(
        _kontext(client, tmp_path), [_brief("3", "913", bestaetigt=False), _brief("4", "914", bestaetigt=False)]
    )
    assert client.brief_bestaetigen.call_count == 2


def test_dokument_wird_nur_bei_ausgabe_angezeigt(mocker, tmp_path):
    from datetime import datetime as _datetime

    from elternportal.fetch import _dokument_speichern
    from elternportal.render import Dokument

    zeige = mocker.patch("elternportal.fetch.ausgabe.zeige_dokument")
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-titel",
        titel="Titel",
        datum=_datetime(2026, 11, 24),
        body="Text",
    )
    client = mocker.Mock()
    assert _dokument_speichern(_kontext(client, tmp_path), "elternbriefe", dokument, "summe") is True
    zeige.assert_called_once()
    zeige.reset_mock()
    assert _dokument_speichern(_kontext(client, tmp_path, ausgeben=False), "elternbriefe", dokument, "summe") is True
    zeige.assert_not_called()


def _letzte_kontext(client, tmp_path, bereiche, n) -> LaufKontext:
    portal = PortalKonfiguration(slug="los", pass_eintrag="familie/los", bereiche=bereiche, output_dir=tmp_path)
    return LaufKontext(client, portal, "Kind", tmp_path, State(tmp_path / "state.json"), False, True, False, n)


def test_letzte_holt_die_n_neuesten_briefe(mocker, tmp_path, fixture_html):
    from elternportal.fetch import _letzte_abholen

    client = mocker.Mock()
    client.seite_holen.side_effect = lambda pfad: fixture_html("elternbriefe.html")
    client.anhang_holen.side_effect = lambda url: b"x"
    kontext = _letzte_kontext(client, tmp_path, ("elternbriefe",), 2)
    _letzte_abholen(kontext)
    dateien = sorted(pfad.name for pfad in (tmp_path / "elternbriefe").glob("*.md"))
    assert dateien == ["2025-07-05-12-kuchenbuffet-beim-sommerfest.md", "2026-11-20-11-sozialpraktikum.md"]
    client.brief_bestaetigen.assert_called_once_with("912")


def test_letzte_waehlt_zeitlich_neuesten_thread(mocker, tmp_path, fixture_html):
    from elternportal.fetch import _letzte_abholen

    liste = fixture_html("fachlehrer_liste.html")
    detail = fixture_html("fachlehrer_thread.html")
    client = mocker.Mock()
    client.seite_holen.side_effect = lambda pfad: detail if pfad.endswith("21/5001") else liste
    client.anhang_holen.side_effect = lambda url: b"x"
    kontext = _letzte_kontext(client, tmp_path, ("fachlehrer",), 1)
    _letzte_abholen(kontext)
    dateien = list((tmp_path / "fachlehrer").glob("*.md"))
    assert [pfad.name for pfad in dateien] == ["2026-11-23-5001-reminder-weihnachtspaeckchenaktion.md"]


def test_zaehlen_gibt_nur_anzahlen_aus(mocker, tmp_path, fixture_html, capsys):
    from elternportal import briefe
    from elternportal.fetch import _portal_zaehlen
    from elternportal.store import pruefsumme

    briefe_seite = fixture_html("elternbriefe.html")
    client = mocker.Mock()
    client.seite_holen.side_effect = lambda pfad: briefe_seite
    kontext = _letzte_kontext(client, tmp_path, ("elternbriefe",), 0)
    bekannt = briefe.parse_briefe(briefe_seite)[0]
    kontext.state.merken("los", "elternbriefe", f"{bekannt.ident}@kind", pruefsumme(bekannt))
    _portal_zaehlen(kontext)
    ausgabe = capsys.readouterr().out
    assert "los/Elternbriefe: 2 neu, 1 bekannt" in ausgabe
    assert "mit --neu abholen" in ausgabe
    client.anhang_holen.assert_not_called()
    assert not (tmp_path / "elternbriefe").exists()


def test_zaehlen_ohne_neue_meldungen(mocker, tmp_path, fixture_html, capsys):
    from elternportal import briefe
    from elternportal.fetch import _portal_zaehlen
    from elternportal.store import pruefsumme

    briefe_seite = fixture_html("elternbriefe.html")
    client = mocker.Mock()
    client.seite_holen.side_effect = lambda pfad: briefe_seite
    kontext = _letzte_kontext(client, tmp_path, ("elternbriefe",), 0)
    for eintrag in briefe.parse_briefe(briefe_seite):
        kontext.state.merken("los", "elternbriefe", f"{eintrag.ident}@kind", pruefsumme(eintrag))
    _portal_zaehlen(kontext)
    ausgabe = capsys.readouterr().out
    assert "los/Elternbriefe: 0 neu, 3 bekannt" in ausgabe
    assert "keine neuen Meldungen" in ausgabe


def _portal(pass_eintrag: str, tmp_path) -> PortalKonfiguration:
    return PortalKonfiguration(slug="los", pass_eintrag=pass_eintrag, bereiche=(), output_dir=tmp_path)


def test_zugangsdaten_aus_pass_wenn_eintrag_gesetzt(mocker, tmp_path):
    from elternportal.fetch import _zugangsdaten

    von_pass = mocker.patch("elternportal.fetch.passstore.zugangsdaten", return_value=("eltern", "geheim"))
    assert _zugangsdaten(_portal("familie/los", tmp_path), False) == ("eltern", "geheim")
    von_pass.assert_called_once_with("familie/los")


def test_keyring_flag_erzwingt_keyring_trotz_pass_eintrag(mocker, tmp_path):
    from elternportal.fetch import _zugangsdaten

    von_keyring = mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("eltern", "geheim"))
    assert _zugangsdaten(_portal("familie/los", tmp_path), True) == ("eltern", "geheim")
    von_keyring.assert_called_once_with("los")


def test_ohne_pass_eintrag_wird_keyring_verwendet(mocker, tmp_path):
    from elternportal.fetch import _zugangsdaten

    von_keyring = mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("eltern", "geheim"))
    assert _zugangsdaten(_portal("", tmp_path), False) == ("eltern", "geheim")
    von_keyring.assert_called_once_with("los")


def _smtp_kontext(tmp_path, empfaenger, mail=True):
    import dataclasses

    from elternportal.config import SmtpKonfiguration

    portal = dataclasses.replace(_portal("familie/los", tmp_path), empfaenger=empfaenger)
    smtp = SmtpKonfiguration(server="mail.example.com", port=587, starttls=True, pass_eintrag="", absender="")
    return dataclasses.replace(_kontext(None, tmp_path), portal=portal, smtp=smtp, mail=mail)


def test_dokument_wird_gemailt_wenn_mail_aktiv(mocker, tmp_path):
    from datetime import datetime as _datetime

    from elternportal.fetch import _dokument_speichern
    from elternportal.render import Dokument

    sende = mocker.patch("elternportal.fetch.mail.sende_mail")
    zeige = mocker.patch("elternportal.fetch.ausgabe.zeige_dokument")
    mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("smtp", "geheim"))
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-titel",
        titel="Titel",
        datum=_datetime(2026, 11, 25),
        body="Text",
    )
    assert _dokument_speichern(_smtp_kontext(tmp_path, ("an@example.com",)), "elternbriefe", dokument, "summe") is True
    sende.assert_called_once()
    assert sende.call_args.args[4] == "[los] Titel"
    assert sende.call_args.args[5] == "Text"
    assert sende.call_args.args[7] == _datetime(2026, 11, 25)
    zeige.assert_not_called()


def test_mail_text_faellt_auf_anhangstext_zurueck(mocker, tmp_path):
    from datetime import datetime as _datetime

    from elternportal.fetch import _mail_versenden
    from elternportal.render import Dokument

    sende = mocker.patch("elternportal.fetch.mail.sende_mail")
    mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("smtp", "geheim"))
    mocker.patch("elternportal.fetch.ausgabe.anzeige_text", return_value="Extrahierter Anhangstext")
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-titel",
        titel="Titel",
        datum=_datetime(2026, 11, 25),
        body="",
    )
    _mail_versenden(_smtp_kontext(tmp_path, ("an@example.com",)), dokument, [])
    assert sende.call_args.args[5] == "Extrahierter Anhangstext"


def test_ohne_empfaenger_wird_keine_mail_gesendet(mocker, tmp_path):
    from datetime import datetime as _datetime

    from elternportal.fetch import _dokument_speichern
    from elternportal.render import Dokument

    sende = mocker.patch("elternportal.fetch.mail.sende_mail")
    zeige = mocker.patch("elternportal.fetch.ausgabe.zeige_dokument")
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-titel",
        titel="Titel",
        datum=_datetime(2026, 11, 25),
        body="Text",
    )
    assert _dokument_speichern(_smtp_kontext(tmp_path, ()), "elternbriefe", dokument, "summe") is True
    sende.assert_not_called()
    zeige.assert_called_once()


def test_mailfehler_bricht_speicherung_nicht_ab(mocker, tmp_path):
    import smtplib
    from datetime import datetime as _datetime

    from elternportal.fetch import _dokument_speichern
    from elternportal.render import Dokument

    mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("smtp", "geheim"))
    mocker.patch("elternportal.fetch.mail.sende_mail", side_effect=smtplib.SMTPException("boom"))
    dokument = Dokument(
        ident="912",
        bereich="elternbriefe",
        datei_kurzel="12-titel",
        titel="Titel",
        datum=_datetime(2026, 11, 25),
        body="Text",
    )
    assert _dokument_speichern(_smtp_kontext(tmp_path, ("an@example.com",)), "elternbriefe", dokument, "summe") is True


def test_smtp_zugangsdaten_aus_pass_wenn_eintrag_gesetzt(mocker, tmp_path):
    import dataclasses

    from elternportal.fetch import _smtp_zugangsdaten

    von_pass = mocker.patch("elternportal.fetch.passstore.zugangsdaten", return_value=("smtp", "geheim"))
    kontext = _smtp_kontext(tmp_path, (), mail=False)
    smtp = dataclasses.replace(kontext.smtp, pass_eintrag="mail/smtp")
    assert _smtp_zugangsdaten(smtp, False) == ("smtp", "geheim")
    von_pass.assert_called_once_with("mail/smtp")


def test_smtp_zugangsdaten_aus_keyring_ohne_eintrag(mocker, tmp_path):
    from elternportal.fetch import _smtp_zugangsdaten

    von_keyring = mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("smtp", "geheim"))
    assert _smtp_zugangsdaten(_smtp_kontext(tmp_path, (), mail=False).smtp, False) == ("smtp", "geheim")
    von_keyring.assert_called_once_with("smtp")


def test_smtp_benutzer_uebersteuert_pass_zeile(mocker, tmp_path):
    import dataclasses

    from elternportal.fetch import _smtp_zugangsdaten

    von_pass = mocker.patch("elternportal.fetch.passstore.passwort", return_value="geheim")
    smtp = dataclasses.replace(
        _smtp_kontext(tmp_path, (), mail=False).smtp, benutzer="mc12345", pass_eintrag="mail/smtp"
    )
    assert _smtp_zugangsdaten(smtp, False) == ("mc12345", "geheim")
    von_pass.assert_called_once_with("mail/smtp")


def test_smtp_benutzer_uebersteuert_keyring_user(mocker, tmp_path):
    import dataclasses

    from elternportal.fetch import _smtp_zugangsdaten

    mocker.patch("elternportal.fetch.keyring_store.zugangsdaten", return_value=("keyring-user", "geheim"))
    smtp = dataclasses.replace(_smtp_kontext(tmp_path, (), mail=False).smtp, benutzer="mc12345")
    assert _smtp_zugangsdaten(smtp, False) == ("mc12345", "geheim")


def test_state_laden_migriert_aus_alt_datei(mocker, tmp_path):
    from elternportal.config import PortalKonfiguration
    from elternportal.fetch import _state_laden
    from elternportal.store import State

    alt = tmp_path / "alt-state.json"
    alt_state = State(alt)
    alt_state.merken("los", "elternbriefe", "1", "abc")
    alt_state.sichern()
    mocker.patch("elternportal.fetch.STATE_DATEI_ALT", alt)
    portal = PortalKonfiguration(slug="los", pass_eintrag="familie/los", bereiche=(), output_dir=tmp_path / "los")
    state = _state_laden(portal, trocken=False)
    assert state.ist_bekannt("los", "elternbriefe", "1", "abc")
    assert (tmp_path / "los" / "state.json").exists()


def test_state_laden_ohne_migration_im_dry_run(mocker, tmp_path):
    from elternportal.config import PortalKonfiguration
    from elternportal.fetch import _state_laden
    from elternportal.store import State

    alt = tmp_path / "alt-state.json"
    alt_state = State(alt)
    alt_state.merken("los", "elternbriefe", "1", "abc")
    alt_state.sichern()
    mocker.patch("elternportal.fetch.STATE_DATEI_ALT", alt)
    portal = PortalKonfiguration(slug="los", pass_eintrag="familie/los", bereiche=(), output_dir=tmp_path / "los")
    state = _state_laden(portal, trocken=True)
    assert not state.ist_bekannt("los", "elternbriefe", "1", "abc")
    assert not (tmp_path / "los").exists()


def test_ohne_smtp_benutzer_wird_pass_user_gelesen(mocker, tmp_path):
    import dataclasses

    from elternportal.fetch import _smtp_zugangsdaten

    von_pass = mocker.patch("elternportal.fetch.passstore.zugangsdaten", return_value=("smtp-user", "geheim"))
    smtp = dataclasses.replace(_smtp_kontext(tmp_path, (), mail=False).smtp, pass_eintrag="mail/smtp")
    assert _smtp_zugangsdaten(smtp, False) == ("smtp-user", "geheim")
    von_pass.assert_called_once_with("mail/smtp")
