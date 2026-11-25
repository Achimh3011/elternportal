"""CLI: fetch new messages from all configured portals as Markdown."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx2
import rich_click as click
from click_loglevel import LogLevel

from elternportal import ausgabe, brett, briefe, keyring_store, kommunikation, passstore, render
from elternportal.client import LoginFehlgeschlagen, PortalClient
from elternportal.config import BEREICHE_URLS, STATE_DATEI, lade_konfiguration, PortalKonfiguration
from elternportal.models import BrettEintrag, Brief, Konversation, ThreadLink
from elternportal.render import Dokument
from elternportal.store import State, pruefsumme, schreibe_dokument, speichere_anhaenge

log = logging.getLogger(__name__)

_BEREICHE = {
    "elternbriefe": ("Elternbriefe", briefe.ist_briefe_seite, briefe.parse_briefe, render.brief_dokument),
    "brett": ("Schwarzes Brett", brett.ist_brett_seite, brett.parse_brett, render.brett_dokument),
    "klassenleitung": (
        "Klassenleitung",
        kommunikation.ist_klassenleitung_seite,
        kommunikation.parse_klassenleitung,
        render.konversation_dokument,
    ),
}


@dataclass(frozen=True)
class LaufKontext:
    """Everything a single portal run needs."""

    client: PortalClient
    portal: PortalKonfiguration
    kind: str
    output_dir: Path
    state: State
    trocken: bool
    bestaetigen: bool
    ausgeben: bool
    letzte: int


@dataclass(frozen=True)
class Kandidat:
    """One parsed message candidate for --letzte runs."""

    bereich: str
    datum: datetime
    eintrag: BrettEintrag | Brief | Konversation | ThreadLink


@click.command()
@click.option("--portal", "-p", "slugs", multiple=True, help="Nur diese Portale abrufen (mehrfach angebbar).")
@click.option(
    "--config", "config_pfad", type=click.Path(path_type=Path), default=None, help="Alternative Konfigurationsdatei."
)
@click.option("--dry-run", "trocken", is_flag=True, default=False, help="Nur anzeigen, nichts speichern.")
@click.option(
    "--neu",
    "neu_holen",
    is_flag=True,
    default=False,
    help="Neue Meldungen abholen und speichern (ohne dieses Flag wird nur gezählt).",
)
@click.option(
    "--keine-bestaetigung",
    "bestaetigen",
    is_flag=True,
    default=False,
    help="Elternbriefe NICHT als gelesen bestätigen.",
)
@click.option(
    "--keine-ausgabe",
    "ausgeben",
    is_flag=True,
    default=False,
    help="Neue Meldungen weder im Terminal ausgeben noch Anhänge öffnen.",
)
@click.option(
    "--letzte",
    "letzte",
    type=click.IntRange(min=1),
    default=None,
    help="Die n neuesten Meldungen pro Portal abholen, unabhängig vom Lesestatus (0 = nur neue).",
)
@click.option(
    "--keyring",
    "keyring_erzwingen",
    is_flag=True,
    default=False,
    help="Zugangsdaten aus dem System-Keyring lesen, auch wenn ein pass_eintrag konfiguriert ist.",
)
@click.option("--log-level", "-l", type=LogLevel(), default=logging.WARNING)
def main(
    slugs: tuple[str, ...],
    config_pfad: Path | None,
    trocken: bool,
    neu_holen: bool,
    bestaetigen: bool,
    ausgeben: bool,
    letzte: int | None,
    keyring_erzwingen: bool,
    log_level: int,
) -> None:
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
        _portal_abholen(
            portal, state, trocken, neu_holen, not bestaetigen, not ausgeben, letzte or 0, keyring_erzwingen
        )
    if not trocken:
        state.sichern()


def _zugangsdaten(portal: PortalKonfiguration, keyring_erzwingen: bool) -> tuple[str, str]:
    """Read credentials from pass or the system keyring, whichever applies.

    The keyring is used when explicitly requested or when the portal has
    no `pass_eintrag` configured; otherwise the pass store wins.
    """
    if keyring_erzwingen or not portal.pass_eintrag:
        return keyring_store.zugangsdaten(portal.slug)
    return passstore.zugangsdaten(portal.pass_eintrag)


def _portal_abholen(
    portal,
    state: State,
    trocken: bool,
    neu_holen: bool,
    bestaetigen: bool,
    ausgeben: bool,
    letzte: int,
    keyring_erzwingen: bool,
) -> None:
    try:
        benutzer, passwort = _zugangsdaten(portal, keyring_erzwingen)
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
            kontext = LaufKontext(
                client, portal, kind_name, portal.output_dir, state, trocken, bestaetigen, ausgeben, letzte
            )
            if letzte:
                _letzte_abholen(kontext)
            elif neu_holen:
                for bereich in portal.bereiche:
                    _bereich_abholen(kontext, bereich)
            else:
                _portal_zaehlen(kontext)
    except (LoginFehlgeschlagen, httpx2.HTTPError) as fehler:
        click.secho(f"Portal {portal.slug} abgebrochen: {fehler}", err=True, fg="red")
    finally:
        client.schliessen()


def _bereich_abholen(kontext: LaufKontext, bereich: str) -> None:
    seite = kontext.client.seite_holen(BEREICHE_URLS[bereich])
    if bereich == "fachlehrer":
        _fachlehrer_abholen(kontext, seite)
        return
    name, ist_seite, parse, dokument_fabrik = _BEREICHE[bereich]
    brief_liste = _listen_abholen(kontext, bereich, seite, name, ist_seite, parse, dokument_fabrik)
    if bereich == "elternbriefe":
        _briefe_bestaetigen(kontext, brief_liste)


def _portal_zaehlen(kontext: LaufKontext) -> None:
    """Count new and known messages per bereich without fetching anything."""
    gesamt = 0
    for bereich in kontext.portal.bereiche:
        seite = kontext.client.seite_holen(BEREICHE_URLS[bereich])
        gesamt += _bereich_zaehlen(kontext, bereich, seite)
    if gesamt:
        click.secho(f"{kontext.portal.slug}: {gesamt} neue Meldungen - mit --neu abholen.", fg="cyan")
    else:
        click.secho(f"{kontext.portal.slug}: keine neuen Meldungen.", fg="green")


def _bereich_zaehlen(kontext: LaufKontext, bereich: str, seite: str) -> int:
    """Return the number of new messages in one bereich."""
    _, summen, name = _bereich_parsen(kontext, bereich, seite)
    if name is None:
        return 0
    neu = sum(1 for ident, summe in summen.items() if _ist_neu(kontext, bereich, ident, summe))
    click.echo(f"{kontext.portal.slug}/{name}: {neu} neu, {len(summen) - neu} bekannt")
    return neu


def _bereich_parsen(kontext: LaufKontext, bereich: str, seite: str) -> tuple[list, dict[str, str], str | None]:
    """Parse one bereich page into entries with their checksums and display name."""
    if bereich == "fachlehrer":
        if not kommunikation.ist_fachlehrer_seite(seite):
            click.secho(f"{kontext.portal.slug}: Bereich Fachlehrer nicht verfügbar.", fg="yellow")
            return [], {}, None
        links = kommunikation.parse_thread_links(seite)
        return links, {link.ident: render.threadlink_pruefsumme(link) for link in links}, "Fachlehrer"
    name, ist_seite, parse, _ = _BEREICHE[bereich]
    if not ist_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich {name} nicht verfügbar.", fg="yellow")
        return [], {}, None
    eintraege = parse(seite)
    return eintraege, {eintrag.ident: pruefsumme(eintrag) for eintrag in eintraege}, name


def _letzte_abholen(kontext: LaufKontext) -> None:
    """Fetch the n most recent messages per portal regardless of read state."""
    kandidaten: list[Kandidat] = []
    brief_liste: list[Brief] = []
    for bereich in kontext.portal.bereiche:
        seite = kontext.client.seite_holen(BEREICHE_URLS[bereich])
        _bereich_sammeln(kontext, bereich, seite, kandidaten, brief_liste)
    kandidaten.sort(key=lambda kandidat: kandidat.datum, reverse=True)
    for kandidat in kandidaten[: kontext.letzte]:
        _kandidat_speichern(kontext, kandidat)
    click.secho(f"{kontext.portal.slug}: {min(len(kandidaten), kontext.letzte)} letzte Meldungen geholt.", fg="green")
    _briefe_bestaetigen(kontext, brief_liste)


def _bereich_sammeln(
    kontext: LaufKontext, bereich: str, seite: str, kandidaten: list[Kandidat], brief_liste: list[Brief]
) -> None:
    if bereich == "fachlehrer":
        if not kommunikation.ist_fachlehrer_seite(seite):
            click.secho(f"{kontext.portal.slug}: Bereich Fachlehrer nicht verfügbar.", fg="yellow")
            return
        kandidaten.extend(
            Kandidat("fachlehrer", link.letzte_nachricht, link) for link in kommunikation.parse_thread_links(seite)
        )
        return
    name, ist_seite, parse, _ = _BEREICHE[bereich]
    if not ist_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich {name} nicht verfügbar.", fg="yellow")
        return
    eintraege = parse(seite)
    kandidaten.extend(Kandidat(bereich, _datum_von(eintrag), eintrag) for eintrag in eintraege)
    if bereich == "elternbriefe":
        brief_liste.extend(eintrag for eintrag in eintraege if isinstance(eintrag, Brief))


def _kandidat_speichern(kontext: LaufKontext, kandidat: Kandidat) -> None:
    eintrag = kandidat.eintrag
    if isinstance(eintrag, ThreadLink):
        thread = kommunikation.parse_thread(
            kontext.client.seite_holen(f"meldungen/kommunikation_fachlehrer/{eintrag.lehrer_id}/{eintrag.thread_id}"),
            eintrag,
        )
        dokument = render.thread_dokument(thread, kontext.kind)
        summe = render.threadlink_pruefsumme(eintrag)
    elif isinstance(eintrag, Brief):
        dokument = render.brief_dokument(eintrag, kontext.kind)
        summe = pruefsumme(eintrag)
    elif isinstance(eintrag, BrettEintrag):
        dokument = render.brett_dokument(eintrag, kontext.kind)
        summe = pruefsumme(eintrag)
    else:
        dokument = render.konversation_dokument(eintrag, kontext.kind)
        summe = pruefsumme(eintrag)
    _dokument_speichern(kontext, kandidat.bereich, dokument, summe)


def _datum_von(eintrag: BrettEintrag | Brief | Konversation | ThreadLink) -> datetime:
    return getattr(eintrag, "letzte_nachricht", None) or getattr(eintrag, "datum", datetime.min)


def _listen_abholen(
    kontext: LaufKontext, bereich: str, seite: str, name: str, ist_seite, parse, dokument_fabrik
) -> list[Brief]:
    """Fetch one list section, save new entries and return all parsed entries."""
    if not ist_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich {name} nicht verfügbar.", fg="yellow")
        return []
    neu = 0
    eintraege = parse(seite)
    for eintrag in eintraege:
        summe = pruefsumme(eintrag)
        if _ist_neu(kontext, bereich, eintrag.ident, summe) and _dokument_speichern(
            kontext, bereich, dokument_fabrik(eintrag, kontext.kind), summe
        ):
            neu += 1
    _bereich_melden(kontext, name, neu)
    return eintraege


def _fachlehrer_abholen(kontext: LaufKontext, seite: str) -> None:
    if not kommunikation.ist_fachlehrer_seite(seite):
        click.secho(f"{kontext.portal.slug}: Bereich Fachlehrer nicht verfügbar.", fg="yellow")
        return
    neu = 0
    for link in kommunikation.parse_thread_links(seite):
        summe = render.threadlink_pruefsumme(link)
        if not _ist_neu(kontext, "fachlehrer", link.ident, summe):
            continue
        thread = kommunikation.parse_thread(
            kontext.client.seite_holen(f"meldungen/kommunikation_fachlehrer/{link.lehrer_id}/{link.thread_id}"), link
        )
        if _dokument_speichern(kontext, "fachlehrer", render.thread_dokument(thread, kontext.kind), summe):
            neu += 1
    _bereich_melden(kontext, "Fachlehrer", neu)


def _briefe_bestaetigen(kontext: LaufKontext, brief_liste: list[Brief]) -> None:
    """Confirm receipt of every unconfirmed Elternbrief, including known ones."""
    if kontext.trocken or not kontext.bestaetigen:
        return
    offene = [brief for brief in brief_liste if not brief.bestaetigt and brief.eb_id]
    for brief in offene:
        try:
            kontext.client.brief_bestaetigen(brief.eb_id)
        except httpx2.HTTPError as fehler:
            click.secho(f"Bestätigung fehlgeschlagen für #{brief.nummer}: {fehler}", err=True, fg="red")
    if offene:
        click.secho(f"{kontext.portal.slug}: {len(offene)} Elternbriefe als gelesen bestätigt.", fg="cyan")


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
    if kontext.ausgeben:
        ausgabe.zeige_dokument(dokument, infos)
    return True


def _bereich_melden(kontext: LaufKontext, name: str, neu: int) -> None:
    if neu:
        click.secho(f"{kontext.portal.slug}: {neu} neue Einträge in {name}.", fg="green")


def _ist_neu(kontext: LaufKontext, bereich: str, ident: str, summe: str) -> bool:
    """Whether a message is unknown or changed compared to the stored state."""
    state_ident = _state_ident(ident, kontext.kind)
    return not kontext.state.ist_bekannt(kontext.portal.slug, bereich, state_ident, summe)


def _state_ident(ident: str, kind: str) -> str:
    return f"{ident}@{render.dateikurzel(kind)}" if kind else ident
