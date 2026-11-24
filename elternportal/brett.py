"""Parser for the Schwarzes Brett (aktuelles/schwarzes_brett)."""

import hashlib
import re
from datetime import datetime

from lxml import etree
from lxml import html as lhtml

from elternportal.models import Anhang, BrettEintrag

_DATUM_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})(?: \d{2}:\d{2}:\d{2})?")
_REPO_RE = re.compile(r"repo=(\d+)")


def ist_brett_seite(page_html: str) -> bool:
    """Check whether the page shows the Schwarzes Brett heading."""
    kopf = lhtml.fromstring(page_html).xpath("//h2[normalize-space()='Schwarzes Brett']")
    return bool(kopf)


def parse_brett(page_html: str) -> list[BrettEintrag]:
    """Extract active entries of the Schwarzes Brett.

    Archived entries are ignored; they are historical versions of
    entries that were active before.

    Args:
        page_html: Rendered content of aktuelles/schwarzes_brett.

    Returns:
        Active Brett entries in page order.
    """
    root = lhtml.fromstring(page_html)
    eintraege = []
    for karte in root.xpath("//div[contains(@class, 'grid')]//div[contains(@class, 'grid-item')]"):
        eintrag = _parse_karte(karte)
        if eintrag is not None:
            eintraege.append(eintrag)
    return eintraege


def _parse_karte(karte: etree._Element) -> BrettEintrag | None:
    kopf = karte.xpath(".//h4")
    datum_p = karte.xpath(".//p[contains(text(), 'eingestellt am')]")
    if not kopf or not datum_p:
        return None
    titel = kopf[0].text_content().strip()
    datum_text = _DATUM_RE.search(datum_p[0].text_content())
    datum = datetime.strptime(datum_text.group(1), "%d.%m.%Y") if datum_text else datetime.min
    body = _body_html(karte)
    anhaenge = _anhaenge(karte)
    return BrettEintrag(
        ident=_ident(anhaenge, titel, datum),
        titel=titel,
        datum=datum,
        body_html=body,
        anhaenge=anhaenge,
    )


def _body_html(karte: etree._Element) -> str:
    absaetze = karte.xpath(".//div[contains(@class, 'well')]/p[not(contains(@style, 'font-size: 10px'))]")
    return "\n".join(etree.tostring(p, encoding="unicode", with_tail=False) for p in absaetze)


def _anhaenge(karte: etree._Element) -> tuple[Anhang, ...]:
    links = karte.xpath(".//a[contains(@href, 'get_file')]")
    return tuple(Anhang(url=link.get("href", ""), name=" ".join(link.itertext()).strip()) for link in links)


def _ident(anhaenge: tuple[Anhang, ...], titel: str, datum: datetime) -> str:
    for anhang in anhaenge:
        match = _REPO_RE.search(anhang.url)
        if match:
            return match.group(1)
    kurzel = hashlib.sha256(f"{titel}{datum}".encode()).hexdigest()[:12]
    return f"h{kurzel}"
