"""Configuration handling for fetch-elternportal.

The configuration lives in an INI file below the XDG config directory
(`~/.config/elternportal/fetch-elternportal.conf`). Every section name is
the portal slug (the subdomain part of `eltern-portal.org`). The DEFAULT
section holds default values for `bereiche` and `output_dir`; each portal
section may override either of them.
"""

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

import platformdirs
import rich_click as click

log = logging.getLogger(__name__)

BEREICHE_URLS = {
    "elternbriefe": "aktuelles/elternbriefe",
    "brett": "aktuelles/schwarzes_brett",
    "fachlehrer": "meldungen/kommunikation_fachlehrer",
    "klassenleitung": "meldungen/kommunikation",
}

_CONFIG_DIR = Path(platformdirs.user_config_dir()) / "elternportal"
CONFIG_DATEI = _CONFIG_DIR / "fetch-elternportal.conf"
_DATA_DIR = Path(platformdirs.user_data_dir()) / "elternportal"
STATE_DATEI = _DATA_DIR / "state.json"

_DEFAULT_KONFIG = {
    "bereiche": "elternbriefe, fachlehrer, klassenleitung, brett",
    "output_dir": str(Path.home() / "elternportal-nachrichten"),
}


@dataclass(frozen=True)
class PortalKonfiguration:
    """Settings of a single portal."""

    slug: str
    pass_eintrag: str
    bereiche: tuple[str, ...]
    output_dir: Path


@dataclass(frozen=True)
class Konfiguration:
    """Complete application configuration."""

    portale: tuple[PortalKonfiguration, ...]


def lade_konfiguration(config_pfad: Path | None = None) -> Konfiguration:
    """Read the configuration from the config file chain.

    Args:
        config_pfad: Optional additional config file, read last.

    Returns:
        Parsed configuration with all configured portals.
    """
    parser = ConfigParser()
    parser["DEFAULT"] = _DEFAULT_KONFIG
    dateien = [str(CONFIG_DATEI)] if CONFIG_DATEI.exists() else []
    if config_pfad is not None:
        dateien.append(str(config_pfad))
    gelesen = parser.read(dateien)
    log.info("Konfiguration gelesen aus %s", ", ".join(gelesen) or "(keine Datei, Defaults)")
    return Konfiguration(portale=_portale(parser))


def _portale(parser: ConfigParser) -> tuple[PortalKonfiguration, ...]:
    portale = []
    for slug in parser.sections():
        bereiche = _bereiche(parser, slug)
        pass_eintrag = parser[slug].get("pass_eintrag", fallback="")
        if not pass_eintrag:
            raise click.ClickException(f"Sektion [{slug}] enthält keinen pass_eintrag.")
        portale.append(
            PortalKonfiguration(
                slug=slug, pass_eintrag=pass_eintrag, bereiche=bereiche, output_dir=_output_dir(parser, slug)
            )
        )
    if not portale:
        raise click.ClickException(f"Keine Portale konfiguriert. Lege {CONFIG_DATEI} an (siehe README).")
    return tuple(portale)


def _output_dir(parser: ConfigParser, slug: str) -> Path:
    roh = parser[slug].get("output_dir", fallback=parser["DEFAULT"]["output_dir"])
    return Path(roh).expanduser()


def _bereiche(parser: ConfigParser, slug: str) -> tuple[str, ...]:
    roh = parser[slug].get("bereiche", fallback=parser["DEFAULT"]["bereiche"])
    bereiche = tuple(t.strip() for t in roh.split(",") if t.strip())
    unbekannt = set(bereiche) - set(BEREICHE_URLS)
    if unbekannt:
        raise click.ClickException(
            f"Portal [{slug}]: unbekannte Bereiche {', '.join(sorted(unbekannt))}. Erlaubt: {', '.join(BEREICHE_URLS)}."
        )
    return bereiche
