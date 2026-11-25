"""Sending new messages as mail via SMTP."""

import logging
import mimetypes
import smtplib
from email.message import EmailMessage

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
    """
    nachricht = _nachricht(smtp.absender or benutzer, empfaenger, betreff, text, anhaenge)
    with smtplib.SMTP(smtp.server, smtp.port, timeout=_TIMEOUT) as verbindung:
        if smtp.starttls:
            verbindung.starttls()
        verbindung.login(benutzer, passwort)
        verbindung.send_message(nachricht)
    log.info("Mail %r an %s versendet", betreff, ", ".join(empfaenger))


def _nachricht(
    absender: str, empfaenger: tuple[str, ...], betreff: str, text: str, anhaenge: list[AnhangInfo]
) -> EmailMessage:
    """Build the mail message with attachments."""
    nachricht = EmailMessage()
    nachricht["From"] = absender
    nachricht["To"] = ", ".join(empfaenger)
    nachricht["Subject"] = betreff
    nachricht.set_content(text)
    for info in anhaenge:
        _anhang_hinzufuegen(nachricht, info)
    return nachricht


def _anhang_hinzufuegen(nachricht: EmailMessage, info: AnhangInfo) -> None:
    """Attach one saved file, guessing its MIME type from the filename."""
    name = info.anhang.name or info.pfad.name
    typ, _ = mimetypes.guess_type(name)
    maintype, subtype = typ.split("/") if typ else ("application", "octet-stream")
    nachricht.add_attachment(info.pfad.read_bytes(), maintype=maintype, subtype=subtype, filename=name)
