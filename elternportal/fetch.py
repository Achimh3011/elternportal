"""CLI: fetch new messages from all configured portals as Markdown."""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx2
import rich_click as click
from click_loglevel import LogLevel

from elternportal import brett, briefe, kommunikation, render
from elternportal.client import LoginFehlgeschlagen, PortalClient
from elternportal.config import BEREICHE_URLS, STATE_DATEI, lade_konfiguration, PortalKonfiguration
from elternportal.passstore import zugangsdaten
from elternportal.render import Dokument
from elternportal.store import State, pruefsumme, schreibe_dokument, speichere_anhaenge

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaufKontext:
    """Everything a single portal run needs."""

    client: PortalClient
    portal: PortalKonfiguration
    kind: str
    output_dir: Path
    state: State
    trocken: bool


@click.command()
@click.option("--portal", "-p", "slugs", multiple=True, help="Nur diese Portale abrufen (mehrfach angebbar).")
@click.option(
    "--config", "config_pfad", type=click.Path(path_type=Path), default=None, help="Alternative Konfigurationsdatei."
)
@click.option("--dry-run", "trocken", is_flag=True, default=False, help="Nur anzeigen, nichts speichern.")
@click.option("--log-level", "-l", type=LogLevel(), default=logging.WARNING)
def main(slugs: tuple[str, ...], config_pfad: Path | None, trocken: bool, log_level: int) -> None:
    """Neue Nachrichten aus den Eltern-Portal/en als Markdown abholen."""
    logging.basicConfig(level=log_level)
    konfig = lade_konfiguration(config_pfad)
    unbekannt = set(slugs) - {portal.slug for portal in konfig.portale}
    if unbekannt:
        raise click.ClickException(f"Unbekannte Portale: {', '.join(sorted(unbekannt))}")
    state = State(STATE_DATEI)
    for portal in konfig.portale:
        if slugs and portal.slug not in slugs:
            continue
        _portal_abholen(portal, konfig.output_dir, state, trocken)
    if not trocken:
        state.sichern()


def _portal_abholen(portal, output_dir: Path, state: State, trocken: bool) -> None:
    try:
        benutzer, passwort = zugangsdaten(portal.pass_eintrag)
        client = PortalClient(portal.slug, benutzer, passwort)
    except (RuntimeError, httpx2.HTTPError) as fehler:
        click.secho(f"Portal {portal.slug} übersprungen: {fehler}", err=True, fg="red")
        return
    try:
        client.login()
        kinder = client.kinder() or [("", "")]
        for kind_id, kind_name in kinder:
            if len(kinder) > 1 and kind_id:
                client.kind_waehlen(kind_id)
            kontext = LaufKontext(client, portal, kind_name, output_dir, state, trocken)
            for bereich in portal.bereiche:
                _bereich_abholen(kontext, bereich)
    except (LoginFehlgeschlagen, httpx2.HTTPError) as fehler:
        click.secho(f"Portal {portal.slug} abgebrochen: {fehler}", err=True, fg="red")
    finally:
        client.schliessen()


def _bereich_abholen(kontext: LaufKontext, bereich: str) -> None:
    seite = kontext.client.seite_holen(BEREICHE_URLS[bereich])
    if bereich == "elternbriefe":
        _listen_abholen(
            kontext, bereich, seite, "Elternbriefe", briefe.ist_briefe_seite, briefe.parse_briefe, render.brief_dokument
        )
    elif bereich == "brett":
        _listen_abholen(
            kontext, bereich, seite, "Schwarzes Brett", brett.ist_brett_seite, brett.parse_brett, render.brett_dokument
        )
    elif bereich == "klassenleitung":
        _listen_abholen(
            kontext,
            bereich,
            seite,
            "Klassenleitung",
            kommunikation.ist_klassenleitung_seite,
            kommunikation.parse_klassenleitung,
            render.konversation_dokument,
        )
    elif bereich == "fachlehrer":
        _fachlehrer_abholen(kontext, seite)


def _listen_abholen(
    kontext: LaufKontext, bereich: str, seite: str, name: str, ist_seite, parse, dokument_fabrik
) -> None:
    if not ist_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich {name} nicht verfügbar.", fg="yellow")
        return
    neu = 0
    for eintrag in parse(seite):
        ident = _state_ident(eintrag.ident, kontext.kind)
        summe = pruefsumme(eintrag)
        if kontext.state.ist_bekannt(kontext.portal.slug, bereich, ident, summe):
            continue
        if _dokument_speichern(kontext, bereich, dokument_fabrik(eintrag, kontext.kind), summe):
            neu += 1
    _bereich_melden(kontext, name, neu)


def _fachlehrer_abholen(kontext: LaufKontext, seite: str) -> None:
    if not kommunikation.ist_fachlehrer_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich Fachlehrer nicht verfügbar.", fg="yellow")
        return
    neu = 0
    for link in kommunikation.parse_thread_links(seite):
        ident = _state_ident(link.ident, kontext.kind)
        summe = render.threadlink_pruefsumme(link)
        if kontext.state.ist_bekannt(kontext.portal.slug, "fachlehrer", ident, summe):
            continue
        thread = kommunikation.parse_thread(
            kontext.client.seite_holen(f"meldungen/kommunikation_fachlehrer/{link.lehrer_id}/{link.thread_id}"), link
        )
        if _dokument_speichern(kontext, "fachlehrer", render.thread_dokument(thread, kontext.kind), summe):
            neu += 1
    _bereich_melden(kontext, "Fachlehrer", neu)


def _dokument_speichern(kontext: LaufKontext, bereich: str, dokument: Dokument, summe: str) -> bool:
    ident = _state_ident(dokument.ident, kontext.kind)
    if kontext.trocken:
        click.secho(f"NEU {kontext.portal.slug}/{bereich}: {dokument.titel}", fg="yellow")
        return False
    inhalte = {anhang.url: kontext.client.anhang_holen(anhang.url) for anhang in dokument.anhaenge}
    ziel = kontext.output_dir / kontext.portal.slug / bereich
    ziel.mkdir(parents=True, exist_ok=True)
    infos = speichere_anhaenge(ziel, dokument.anhaenge, inhalte)
    datei = schreibe_dokument(dokument, kontext.portal.slug, ziel, infos)
    kontext.state.merken(kontext.portal.slug, bereich, ident, summe)
    click.secho(f"Neu: {datei}", fg="green")
    return True


def _bereich_melden(kontext: LaufKontext, name: str, neu: int) -> None:
    if neu:
        click.secho(f"{kontext.portal.slug}: {neu} neue Einträge in {name}.", fg="green")


def _state_ident(ident: str, kind: str) -> str:
    return f"{ident}@{render.dateikurzel(kind)}" if kind else ident
