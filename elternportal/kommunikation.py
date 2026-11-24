"""Parser for teacher communication (Fachlehrer threads, Klassenleitung conversations)."""

import hashlib
import re
from datetime import datetime

from lxml import etree
from lxml import html as lhtml

from elternportal.models import Anhang, Konversation, Nachricht, Thread, ThreadLink

_DATUM_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4}),? (\d{2}:\d{2})")
_ONCLICK_RE = re.compile(r"showMessageFachlehrer\((\d+),\s*(\d+)\)")


def ist_fachlehrer_seite(page_html: str) -> bool:
    """Check whether the page contains the Fachlehrer message table."""
    return bool(lhtml.fromstring(page_html).xpath("//table[@id='messages-fachlehrer-table']"))


def parse_thread_links(page_html: str) -> list[ThreadLink]:
    """Extract conversation links from the Fachlehrer overview page."""
    rows = lhtml.fromstring(page_html).xpath("//tr[@class='message-row']")
    links = []
    for row in rows:
        match = _ONCLICK_RE.search(row.get("onclick", ""))
        if match is None:
            continue
        zellen = row.xpath("./td")
        datum = _parse_datum(zellen[-1].text_content()) if zellen else datetime.min
        links.append(
            ThreadLink(
                lehrer_id=int(match.group(1)),
                thread_id=int(match.group(2)),
                lehrer=zellen[0].text_content().strip(),
                letzte_nachricht=datum,
            )
        )
    return links


def parse_thread(page_html: str, link: ThreadLink) -> Thread:
    """Extract one complete Fachlehrer conversation thread.

    Args:
        page_html: Rendered thread detail page.
        link: ThreadLink the page was fetched for.

    Returns:
        Thread with all messages and attachments.
    """
    root = lhtml.fromstring(page_html)
    grid = root.xpath("//div[@id='message-thread-grid']")
    betreff = ""
    kind = ""
    verlauf: list[list] = []
    for zeile in grid[0].xpath("./div[contains(@class, 'row')]") if grid else []:
        label = _label_text(zeile)
        if label.startswith("Betreff:"):
            betreff = zeile.xpath("string(.//div[contains(@class, 'twelve')])").strip()
        elif label.startswith("Für:"):
            kind = zeile.xpath("string(.//div[contains(@class, 'twelve')])").strip()
        else:
            _verlauf_zeile(zeile, verlauf)
    return Thread(
        ident=link.ident,
        lehrer=link.lehrer,
        betreff=betreff,
        kind=kind,
        letzte_nachricht=link.letzte_nachricht,
        nachrichten=tuple(
            Nachricht(absender=absender, datum=datum, body_html=body, anhaenge=tuple(anhaenge))
            for absender, datum, body, anhaenge in verlauf
        ),
    )


def _verlauf_zeile(zeile: etree._Element, verlauf: list[list]) -> None:
    absender = _absender(zeile)
    anhaenge = _anhaenge(zeile)
    if absender is None:
        if verlauf and anhaenge:
            verlauf[-1][3].extend(anhaenge)
        return
    segment = zeile.xpath(".//div[contains(@class, 'ui segment')]")
    if not segment and not anhaenge:
        return
    body = "\n".join(etree.tostring(seg, encoding="unicode", with_tail=False) for seg in segment) if segment else ""
    verlauf.append([absender, _parse_datum(_label_text(zeile)), body, list(anhaenge)])


def _absender(zeile: etree._Element) -> str | None:
    text = _label_text(zeile)
    match = re.match(r"(\S[^:\n]*):", text)
    return match.group(1).strip() if match else None


def _label_text(zeile: etree._Element) -> str:
    links = zeile.xpath("./div[contains(@class, 'four')]")
    if not links:
        return ""
    return " ".join(links[0].text_content().split())


def _anhaenge(zeile: etree._Element) -> tuple[Anhang, ...]:
    links = zeile.xpath(".//a[contains(@href, 'get_file')]")
    return tuple(Anhang(url=link.get("href", ""), name=" ".join(link.itertext()).strip()) for link in links)


def ist_klassenleitung_seite(page_html: str) -> bool:
    """Check whether the page shows the Klassenleitung communication heading."""
    kopf = lhtml.fromstring(page_html).xpath("//h2[contains(., 'Kommunikation Eltern/Klassenleitung')]")
    return bool(kopf)


def parse_klassenleitung(page_html: str) -> list[Konversation]:
    """Extract all Klassenleitung conversations (incl. past school years).

    Args:
        page_html: Rendered content of meldungen/kommunikation.

    Returns:
        Conversations in page order.
    """
    root = lhtml.fromstring(page_html)
    konversationen = []
    for accordion in root.xpath("//div[contains(@class, 'accordion')]"):
        titelzeilen = accordion.xpath("./div[contains(@class, 'title')]")
        inhalte = accordion.xpath("./div[contains(@class, 'content')]")
        for titel, inhalt in zip(titelzeilen, inhalte, strict=False):
            konversation = _parse_konversation(titel, inhalt)
            if konversation is not None:
                konversationen.append(konversation)
    return konversationen


def _parse_konversation(titel: etree._Element, inhalt: etree._Element) -> Konversation | None:
    betreff = " ".join(titel.xpath("string(./span[not(contains(@class, 'pull-right'))])").split())
    betreff = betreff.replace("(Beantwortet)", "").strip()
    if not betreff:
        return None
    datum = _parse_datum(titel.text_content())
    nachrichten = _parse_verlauf(inhalt, datum)
    return Konversation(
        ident=_konversations_ident(inhalt, betreff, datum),
        titel=betreff,
        datum=datum,
        beantwortet="(Beantwortet)" in titel.text_content(),
        nachrichten=tuple(nachrichten),
    )


def _parse_verlauf(inhalt: etree._Element, anfrage_datum: datetime) -> list[Nachricht]:
    nachrichten = []
    absender = "Eltern"
    for element in inhalt.xpath("./h4 | ./p"):
        text = element.text_content().strip()
        if element.tag == "h4":
            if "Antwort" in text:
                absender = "Klassenleitung"
            continue
        datum = anfrage_datum if absender == "Eltern" else _parse_datum(element.getprevious().text_content())
        nachrichten.append(
            Nachricht(
                absender=absender,
                datum=datum,
                body_html=etree.tostring(element, encoding="unicode", with_tail=False),
                anhaenge=(),
            )
        )
    return nachrichten


def _konversations_ident(inhalt: etree._Element, betreff: str, datum: datetime) -> str:
    loesch = inhalt.xpath(".//button[@name='id']/@value")
    if loesch:
        return loesch[0]
    return "h" + hashlib.sha256(f"{betreff}{datum}".encode()).hexdigest()[:12]


def _parse_datum(text: str) -> datetime:
    match = _DATUM_RE.search(text)
    if match is None:
        return datetime.min
    return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d.%m.%Y %H:%M")
