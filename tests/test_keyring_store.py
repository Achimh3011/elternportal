"""Tests for reading credentials from the system keyring."""

import keyring.errors
import pytest
from keyring.credentials import SimpleCredential

from elternportal import keyring_store


def test_zugangsdaten_aus_keyring_gelesen(mocker):
    mocker.patch.object(keyring_store.keyring, "get_credential", return_value=SimpleCredential("eltern", "geheim"))
    assert keyring_store.zugangsdaten("gym-a") == ("eltern", "geheim")


def test_fehlender_eintrag_wirft_fehler_mit_hinweis(mocker):
    mocker.patch.object(keyring_store.keyring, "get_credential", return_value=None)
    with pytest.raises(RuntimeError, match="python -m keyring set elternportal/gym-a"):
        keyring_store.zugangsdaten("gym-a")


def test_eintrag_ohne_passwort_wirft_fehler(mocker):
    mocker.patch.object(keyring_store.keyring, "get_credential", return_value=SimpleCredential("eltern", ""))
    with pytest.raises(RuntimeError, match="Keyring-Eintrag fehlt"):
        keyring_store.zugangsdaten("gym-a")


def test_keyring_backend_fehler_wird_gemeldet(mocker):
    mocker.patch.object(
        keyring_store.keyring, "get_credential", side_effect=keyring.errors.KeyringError("kein Backend")
    )
    with pytest.raises(RuntimeError, match="Keyring nicht lesbar"):
        keyring_store.zugangsdaten("gym-a")
