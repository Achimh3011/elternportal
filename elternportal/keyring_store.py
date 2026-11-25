"""Reading portal credentials from the system keyring."""

import logging

import keyring
import keyring.errors

log = logging.getLogger(__name__)


def zugangsdaten(slug: str) -> tuple[str, str]:
    """Read username and password for a portal from the system keyring.

    One entry per portal holds both values: the login username is the
    entry key, the password its secret. Populate it via
    `python -m keyring set elternportal/<slug> <benutzer>`.

    Args:
        slug: Portal slug (the subdomain part of eltern-portal.org).

    Returns:
        Tuple of (username, password).

    Raises:
        RuntimeError: If the entry is missing or the keyring backend
            is unavailable.
    """
    dienst = f"elternportal/{slug}"
    try:
        credential = keyring.get_credential(dienst, None)
    except keyring.errors.KeyringError as fehler:
        raise RuntimeError(f"Keyring nicht lesbar ({fehler})") from fehler
    if credential is None or not credential.username or not credential.password:
        raise RuntimeError(
            f"Keyring-Eintrag fehlt für {dienst} - mit `python -m keyring set {dienst} <benutzer>` anlegen"
        )
    log.debug("Zugangsdaten für %s aus dem Keyring gelesen (Benutzer: %s)", slug, credential.username)
    return credential.username, credential.password
