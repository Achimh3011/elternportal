"""Reading portal credentials from the pass password store."""

import logging
from subprocess import run

log = logging.getLogger(__name__)

_BENUTZER_LABELS = ("user", "benutzername", "login", "mail")


def zugangsdaten(eintrag: str) -> tuple[str, str]:
    """Read username and password for a portal from `pass`.

    The first non-empty line holds the password, the username is taken
    from a `user:` line (falling back to `benutzername:`, `login:`, `mail:`).

    Args:
        eintrag: Path of the entry inside the password store,
            e.g. "familie/eltern@gym-a".

    Returns:
        Tuple of (username, password).

    Raises:
        RuntimeError: If the entry is missing, empty or has no username line.
    """
    zeilen = _zeilen(eintrag)
    benutzer = _label_wert(zeilen[1:])
    if not benutzer:
        raise RuntimeError(f"pass-Eintrag {eintrag!r} enthält keine user:-Zeile")
    log.debug("Zugangsdaten für %s gelesen (Benutzer: %s)", eintrag, benutzer)
    return benutzer, zeilen[0]


def passwort(eintrag: str) -> str:
    """Read only the password of a `pass` entry (first non-empty line).

    Used when the username is configured elsewhere, e.g. the `benutzer`
    option of the [SMTP] section.

    Args:
        eintrag: Path of the entry inside the password store.

    Returns:
        The password.

    Raises:
        RuntimeError: If the entry is missing or empty.
    """
    zeilen = _zeilen(eintrag)
    log.debug("Passwort für %s gelesen", eintrag)
    return zeilen[0]


def _zeilen(eintrag: str) -> list[str]:
    resultat = run(["pass", "show", eintrag], capture_output=True, text=True, check=True)
    zeilen = [z.strip() for z in resultat.stdout.splitlines() if z.strip() and not z.startswith("gpg:")]
    if not zeilen:
        raise RuntimeError(f"pass-Eintrag {eintrag!r} ist leer")
    return zeilen


def _label_wert(zeilen: list[str]) -> str:
    for zeile in zeilen:
        for label in _BENUTZER_LABELS:
            if zeile.lower().startswith(f"{label}:"):
                return zeile.split(":", 1)[1].strip()
    return ""
