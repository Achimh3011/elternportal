"""HTTP client for one eltern-portal.org instance."""

import logging
import time

import httpx2
from lxml import html as lhtml

log = logging.getLogger(__name__)

_LOGIN_URL = "/includes/project/auth/login.php"
_REQUEST_TIMEOUT_SECONDS = 30
_REQUEST_PAUSE_SECONDS = 0.5


class LoginFehlgeschlagen(Exception):
    """Raised when the portal does not accept the credentials."""


class PortalClient:
    """Logged-in HTTP session with one portal."""

    def __init__(self, slug: str, benutzer: str, passwort: str):
        self._client = httpx2.Client(
            base_url=f"https://{slug}.eltern-portal.org",
            follow_redirects=True,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "fetch-elternportal/0.1"},
        )
        self._benutzer = benutzer
        self._passwort = passwort
        self.slug = slug

    def login(self) -> None:
        """Log into the portal; raises LoginFehlgeschlagen otherwise."""
        csrf = self._csrf_token(self.seite_holen("/"))
        antwort = self._client.post(
            _LOGIN_URL,
            data={"csrf": csrf, "username": self._benutzer, "password": self._passwort, "go_to": ""},
        )
        antwort.raise_for_status()
        if 'href="logout"' not in self.seite_holen("/start"):
            raise LoginFehlgeschlagen(f"Login auf {self.slug} nicht akzeptiert.")

    def seite_holen(self, pfad: str) -> str:
        """Fetch a portal page as text."""
        antwort = self._client.get(pfad)
        antwort.raise_for_status()
        time.sleep(_REQUEST_PAUSE_SECONDS)
        return antwort.text

    def anhang_holen(self, url: str) -> bytes:
        """Download an attachment referenced by a page."""
        antwort = self._client.get(url)
        antwort.raise_for_status()
        time.sleep(_REQUEST_PAUSE_SECONDS)
        return antwort.content

    def kinder(self) -> list[tuple[str, str]]:
        """List registered children as (id, name) pairs."""
        root = lhtml.fromstring(self.seite_holen("/start"))
        optionen = root.xpath("//select[contains(@class, 'form-control')]/option")
        return [(option.get("value", ""), option.text_content().strip()) for option in optionen]

    def kind_waehlen(self, kind_id: str) -> None:
        """Switch the session to another child."""
        antwort = self._client.get("/api/set_child.php", params={"id": kind_id})
        antwort.raise_for_status()
        log.debug("Kind %s aktiviert (Antwort: %s)", kind_id, antwort.text.strip())

    def schliessen(self) -> None:
        """End the HTTP session."""
        self._client.close()

    def _csrf_token(self, seite_html: str) -> str:
        token = lhtml.fromstring(seite_html).xpath("string(//input[@name='csrf']/@value)")
        if not token:
            raise LoginFehlgeschlagen(f"Kein CSRF-Token auf {self.slug} gefunden.")
        return token
