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
    client, tmp_path, *, bestaetigen: bool = True, trocken: bool = False, ausgeben: bool = True
) -> LaufKontext:
    portal = PortalKonfiguration(slug="los", pass_eintrag="familie/los", bereiche=())
    return LaufKontext(client, portal, "Kind", tmp_path, State(tmp_path / "state.json"), trocken, bestaetigen, ausgeben)


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
