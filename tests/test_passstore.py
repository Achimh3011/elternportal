"""Tests for reading credentials from the pass password store."""

from subprocess import CompletedProcess

import pytest

from elternportal.passstore import zugangsdaten


def _pass_result(stdout: str) -> CompletedProcess:
    return CompletedProcess(args=["pass"], returncode=0, stdout=stdout, stderr="")


def test_zugangsdaten_aus_user_zeile(mocker):
    mocker.patch(
        "elternportal.passstore.run",
        return_value=_pass_result("geheim\nuser: eltern@example.org\nmail: eltern@example.org\n"),
    )
    benutzer, passwort = zugangsdaten("familie/portal")
    assert benutzer == "eltern@example.org"
    assert passwort == "geheim"


def test_zugangsdaten_fallback_mail_zeile(mocker):
    mocker.patch(
        "elternportal.passstore.run",
        return_value=_pass_result("geheim\nbenutzername: andere@mail.org\n"),
    )
    benutzer, passwort = zugangsdaten("familie/portal")
    assert benutzer == "andere@mail.org"
    assert passwort == "geheim"


def test_gpg_hinweis_zeilen_werden_ignoriert(mocker):
    mocker.patch(
        "elternportal.passstore.run",
        return_value=_pass_result("gpg: Hinweis: irgendwas\ngeheim\nuser: eltern@example.org\n"),
    )
    benutzer, passwort = zugangsdaten("familie/portal")
    assert benutzer == "eltern@example.org"
    assert passwort == "geheim"


def test_fehlende_user_zeile_wirft_fehler(mocker):
    mocker.patch(
        "elternportal.passstore.run",
        return_value=_pass_result("geheim\nsite: https://portal.example.org\n"),
    )
    with pytest.raises(RuntimeError, match="user"):
        zugangsdaten("familie/portal")


def test_leerer_eintrag_wirft_fehler(mocker):
    mocker.patch("elternportal.passstore.run", return_value=_pass_result("\n\n"))
    with pytest.raises(RuntimeError, match="leer"):
        zugangsdaten("familie/portal")
