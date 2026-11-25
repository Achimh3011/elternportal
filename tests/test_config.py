"""Tests for the configuration handling."""

from pathlib import Path

import pytest
import rich_click as click

from elternportal.config import lade_konfiguration


@pytest.fixture
def config_umgebung(mocker, tmp_path):
    """Isolate the config from the user's real config file."""
    mocker.patch("elternportal.config.CONFIG_DATEI", tmp_path / "nicht-vorhanden.conf")
    return tmp_path


def test_ohne_datei_wirft_hinweis(config_umgebung):
    with pytest.raises(click.ClickException, match="Keine Portale konfiguriert"):
        lade_konfiguration()


def test_portale_lesen(config_umgebung, tmp_path):
    datei = tmp_path / "portale.conf"
    datei.write_text(
        "[DEFAULT]\nbereiche = elternbriefe, brett\n"
        "[gym-a]\npass_eintrag = familie/los\n\n[gym-b]\npass_eintrag = familie/mwg\nbereiche = fachlehrer\n",
        encoding="utf-8",
    )
    konfig = lade_konfiguration(datei)
    assert [portal.slug for portal in konfig.portale] == ["gym-a", "gym-b"]
    assert konfig.portale[0].pass_eintrag == "familie/los"
    assert konfig.portale[0].bereiche == ("elternbriefe", "brett")
    assert konfig.portale[1].bereiche == ("fachlehrer",)


def test_modul_defaults_ohne_default_sektion(config_umgebung, tmp_path):
    datei = tmp_path / "ohne-default.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\n", encoding="utf-8")
    konfig = lade_konfiguration(datei)
    assert konfig.portale[0].bereiche == ("elternbriefe", "fachlehrer", "klassenleitung", "brett")


def test_unbekannter_bereich_wirft_fehler(config_umgebung, tmp_path):
    datei = tmp_path / "falsch.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\nbereiche = fake_bereich\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="unbekannte Bereiche"):
        lade_konfiguration(datei)


def test_fehlender_pass_eintrag_ermoeglicht_keyring(config_umgebung, tmp_path):
    datei = tmp_path / "ohne-pass.conf"
    datei.write_text("[los]\nbereiche = brett\n", encoding="utf-8")
    konfig = lade_konfiguration(datei)
    assert konfig.portale[0].pass_eintrag == ""


def test_output_dir_wird_expandiert(config_umgebung, tmp_path):
    datei: Path = tmp_path / "pfad.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\n", encoding="utf-8")
    konfig = lade_konfiguration(datei)
    assert konfig.portale[0].output_dir == Path.home() / "elternportal-nachrichten"


def test_output_dir_pro_portal_ueberschreibbar(config_umgebung, tmp_path):
    datei = tmp_path / "pfad-pro-portal.conf"
    datei.write_text(
        "[DEFAULT]\noutput_dir = ~/elternportal-nachrichten\n"
        "[los]\npass_eintrag = familie/los\n\n[mwg]\npass_eintrag = familie/mwg\n"
        f"output_dir = {tmp_path / 'mwg-nachrichten'}\n",
        encoding="utf-8",
    )
    konfig = lade_konfiguration(datei)
    assert konfig.portale[0].output_dir == Path.home() / "elternportal-nachrichten"
    assert konfig.portale[1].output_dir == tmp_path / "mwg-nachrichten"


def test_smtp_sektion_wird_geparst(config_umgebung, tmp_path):
    datei = tmp_path / "smtp.conf"
    datei.write_text(
        "[los]\npass_eintrag = familie/los\n"
        "[SMTP]\nserver = mail.example.com\nport = 587\npass_eintrag = mail/smtp\nabsender = absender@example.com\n",
        encoding="utf-8",
    )
    konfig = lade_konfiguration(datei)
    assert konfig.smtp is not None
    assert konfig.smtp.server == "mail.example.com"
    assert konfig.smtp.port == 587
    assert konfig.smtp.starttls is True
    assert konfig.smtp.pass_eintrag == "mail/smtp"
    assert konfig.smtp.absender == "absender@example.com"
    assert [portal.slug for portal in konfig.portale] == ["los"]


def test_ohne_smtp_sektion_ist_smtp_none(config_umgebung, tmp_path):
    datei = tmp_path / "ohne-smtp.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\n", encoding="utf-8")
    konfig = lade_konfiguration(datei)
    assert konfig.smtp is None


def test_smtp_ohne_server_wirft_fehler(config_umgebung, tmp_path):
    datei = tmp_path / "smtp-fehler.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\n[SMTP]\nport = 587\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="server fehlt"):
        lade_konfiguration(datei)


def test_empfaenger_werden_pro_portal_gelesen(config_umgebung, tmp_path):
    datei = tmp_path / "empfaenger.conf"
    datei.write_text(
        "[los]\npass_eintrag = familie/los\nempfaenger = an@example.com, noch@example.com\n"
        "[mwg]\npass_eintrag = familie/mwg\n",
        encoding="utf-8",
    )
    konfig = lade_konfiguration(datei)
    assert konfig.portale[0].empfaenger == ("an@example.com", "noch@example.com")
    assert konfig.portale[1].empfaenger == ()


def test_ungueltiger_empfaenger_wirft_fehler(config_umgebung, tmp_path):
    datei = tmp_path / "empfaenger-fehler.conf"
    datei.write_text("[los]\npass_eintrag = familie/los\nempfaenger = keine-adresse\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="ungültige Empfänger"):
        lade_konfiguration(datei)
