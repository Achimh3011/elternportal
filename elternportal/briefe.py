"""Parser for the Elternbriefe list (aktuelles/elternbriefe)."""

import copy
import re
from datetime import datetime

from lxml import etree
from lxml import html as lhtml

from elternportal.models import Anhang, Brief

_DATUM_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})[,: ]+(\d{2}:\d{2}(?::\d{2})?)")


def ist_briefe_seite(page_html: str) -> bool:
    """Check whether the page contains the Elternbriefe table."""
    return bool(lhtml.fromstring(page_html).xpath("//table[contains(@class, 'very basic')]"))


def parse_briefe(page_html: str) -> list[Brief]:
    """Extract all Elternbriefe from the letters list page.

    Args:
        page_html: Rendered content of aktuelles/elternbriefe.

    Returns:
        Briefs in page order (newest first).
    """
    table = lhtml.fromstring(page_html).xpath("//table[contains(@class, 'very basic')]")
    if not table:
        return []
    briefs = []
    rows = table[0].xpath(".//tr")
    for index, row in enumerate(rows):
        if _ist_kopfzeile(row) and index + 1 < len(rows):
            brief = _parse_brief(row, rows[index + 1])
            if brief is not None:
                briefs.append(brief)
    return briefs


def _ist_kopfzeile(row: etree._Element) -> bool:
    zelle = row.xpath("./td")[0] if row.xpath("./td") else None
    return zelle is not None and zelle.text is not None and zelle.text.strip().startswith("#")


def _parse_brief(kopf: etree._Element, inhalt: etree._Element) -> Brief | None:
    zellen = kopf.xpath("./td")
    titel_element = inhalt.xpath("./td/*[contains(@onclick, 'eb_bestaetigung')]")
    if not titel_element:
        return None
    element = titel_element[0]
    nummer = zellen[0].text.strip().lstrip("#")
    return Brief(
        ident=_ident_aus_status(zellen[-1]) or nummer,
        nummer=nummer,
        titel=element.xpath("string(./h4)").strip(),
        datum=_parse_datum(etree.tostring(element, encoding="unicode")),
        klassen=element.xpath("string(following-sibling::span[contains(@class, 'small')])")
        .strip()
        .removeprefix("Klasse/n:")
        .strip(),
        bestaetigt=_bestaetigt(zellen[-1]),
        body_html=_body_html(element.getparent()),
        anhaenge=_anhaenge(element.getparent()),
    )


def _ident_aus_status(status_zelle: etree._Element) -> str:
    return status_zelle.get("id", "").removeprefix("empf_")


def _bestaetigt(status_zelle: etree._Element) -> bool:
    text = " ".join("".join(status_zelle.itertext()).split())
    return "bestätigt" in text and "noch nicht" not in text


def _anhaenge(zelle: etree._Element) -> tuple[Anhang, ...]:
    links = zelle.xpath("./a[contains(@class, 'dynamic-file')][not(contains(@class, 'link_nachrichten'))]")
    return tuple(Anhang(url=link.get("href", ""), name=" ".join(link.itertext()).strip()) for link in links)


def _body_html(zelle: etree._Element | None) -> str:
    if zelle is None:
        return ""
    absaetze = zelle.xpath("./p")
    if absaetze:
        return "\n".join(etree.tostring(p, encoding="unicode", with_tail=False) for p in absaetze)
    return _rest_html(zelle)


def _rest_html(zelle: etree._Element) -> str:
    """Body text of older letters: cell content without title, files and classes."""
    kopie = copy.deepcopy(zelle)
    kopie.tag = "div"
    for stoerer in kopie.xpath(
        "./*[contains(@onclick, 'eb_bestaetigung')]"
        " | ./*[contains(@class, 'dynamic-file')]"
        " | .//span[contains(@class, 'small')]"
    ):
        _entferne_mit_tail(stoerer)
    if not kopie.text_content().strip():
        return ""
    return etree.tostring(kopie, encoding="unicode", with_tail=False)


def _entferne_mit_tail(element: etree._Element) -> None:
    """Remove an element while re-attaching its tail text to the previous node."""
    parent = element.getparent()
    if element.tail:
        vorherige = element.getprevious()
        if vorherige is not None:
            vorherige.tail = (vorherige.tail or "") + element.tail
        else:
            parent.text = (parent.text or "") + element.tail
    parent.remove(element)


def _parse_datum(html_text: str) -> datetime:
    match = _DATUM_RE.search(html_text)
    if match is None:
        return datetime.min
    try:
        return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d.%m.%Y %H:%M:%S")
    except ValueError:
        return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d.%m.%Y %H:%M")
