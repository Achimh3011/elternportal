"""Sending new messages as mail via SMTP."""

import logging
import mimetypes
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from elternportal.config import SmtpKonfiguration
from elternportal.store import AnhangInfo

log = logging.getLogger(__name__)

_TIMEOUT = 30


def sende_mail(
    smtp: SmtpKonfiguration,
    benutzer: str,
    passwort: str,
    empfaenger: tuple[str, ...],
    betreff: str,
    text: str,
    anhaenge: list[AnhangInfo],
    datum: datetime,
) -> None:
    """Send one message as a single mail, attachments as MIME parts.

    Args:
        smtp: Global mail server settings (server, port, starttls, sender).
        benutzer: SMTP login username.
        passwort: SMTP login password.
        empfaenger: Recipient addresses of this mail.
        betreff: Subject line.
        text: Plain text body of the message.
        anhaenge: Saved attachments to attach (read from their stored files).
        datum: Timestamp of the portal message; becomes the Date header.
    """
    nachricht = _nachricht(smtp.absender or benutzer, empfaenger, betreff, text, anhaenge, datum)
    with smtplib.SMTP(smtp.server, smtp.port, timeout=_TIMEOUT) as verbindung:
        if smtp.starttls:
            verbindung.starttls()
        verbindung.login(benutzer, passwort)
        verbindung.send_message(nachricht)
    log.info("Mail %r an %s versendet", betreff, ", ".join(empfaenger))


def _nachricht(
    absender: str,
    empfaenger: tuple[str, ...],
    betreff: str,
    text: str,
    anhaenge: list[AnhangInfo],
    datum: datetime,
) -> EmailMessage:
    """Build the mail message with attachments."""
    nachricht = EmailMessage()
    nachricht["From"] = absender
    nachricht["To"] = ", ".join(empfaenger)
    nachricht["Subject"] = betreff
    nachricht["Date"] = _datum_header(datum)
    domain = absender.partition("@")[2] or "elternportal.local"
    nachricht["Message-ID"] = make_msgid(domain=domain)
    nachricht.set_content(text)
    for info in anhaenge:
        _anhang_hinzufuegen(nachricht, info)
    return nachricht


def _datum_header(datum: datetime) -> str:
    """RFC 5322 date of the portal message; now if the portal supplied none."""
    zeit = datum if datum != datetime.min else datetime.now()
    return format_datetime(zeit.astimezone())


def _anhang_hinzufuegen(nachricht: EmailMessage, info: AnhangInfo) -> None:
    """Attach one saved file, guessing its MIME type from the filename."""
    name = info.anhang.name or info.pfad.name
    typ, _ = mimetypes.guess_type(name)
    maintype, subtype = typ.split("/") if typ else ("application", "octet-stream")
    nachricht.add_attachment(info.pfad.read_bytes(), maintype=maintype, subtype=subtype, filename=name)
