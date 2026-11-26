"""Tests for the HTTP client and its retry behaviour."""

import httpx2
import pytest
import stamina

from elternportal.client import PortalClient


@pytest.fixture
def stamina_aktiv():
    """Enable stamina retries for one test, restoring the pytest default after."""
    stamina.set_active(True)
    yield
    stamina.set_active(False)


def test_seite_wird_geholt(mocker):
    http_klient = mocker.patch("elternportal.client.httpx2.Client")
    antwort = mocker.Mock(text="<html>ok</html>")
    http_klient.return_value.get.return_value = antwort
    portal = PortalClient("los", "benutzer", "geheim")
    assert portal.seite_holen("/start") == "<html>ok</html>"
    antwort.raise_for_status.assert_called_once()


def test_transient_fehler_wird_wiederholt(mocker, stamina_aktiv):
    http_klient = mocker.patch("elternportal.client.httpx2.Client")
    antwort = mocker.Mock(text="ok")
    http_klient.return_value.get.side_effect = [httpx2.ConnectError("Verbindung verweigert"), antwort]
    portal = PortalClient("los", "benutzer", "geheim")
    assert portal.seite_holen("/start") == "ok"
    assert http_klient.return_value.get.call_count == 2


def test_nach_drei_versuchen_wirft_der_fehler_weiter(mocker, stamina_aktiv):
    http_klient = mocker.patch("elternportal.client.httpx2.Client")
    http_klient.return_value.get.side_effect = httpx2.ConnectError("Verbindung verweigert")
    portal = PortalClient("los", "benutzer", "geheim")
    with pytest.raises(httpx2.ConnectError):
        portal.seite_holen("/start")
    assert http_klient.return_value.get.call_count == 3


def test_post_reicht_daten_weiter(mocker):
    http_klient = mocker.patch("elternportal.client.httpx2.Client")
    portal = PortalClient("los", "benutzer", "geheim")
    portal._post("/login", data={"csrf": "x"})
    http_klient.return_value.post.assert_called_once_with("/login", data={"csrf": "x"})
