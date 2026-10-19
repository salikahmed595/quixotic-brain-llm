"""Email — PRD §5 FR-AUTH-02 (verification), FR-AUTH-06 (password reset), FR-AUTH-04 (pending-user event).

The PRD names no mail provider, so the backend is a required setting (docs/PRD_GAPS.md §1): `smtp` for any SMTP service
(Amazon SES, Google Workspace, Microsoft 365, ...) or `console` for local development, which writes the message, including
its link, to the server log instead of sending it."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from ..config import Settings

log = logging.getLogger("mail")


class Mailer(Protocol):
    def send(self, to: str, subject: str, text: str) -> None: ...


class ConsoleMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, text: str) -> None:
        self.sent.append((to, subject, text))
        log.warning("EMAIL (console backend, not sent) to=%s subject=%s\n%s", to, subject, text)


class SMTPMailer:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.s.mail_from, to, subject
        msg.set_content(text)
        ctx = ssl.create_default_context()
        conn = (smtplib.SMTP_SSL(self.s.smtp_host, self.s.smtp_port, timeout=15, context=ctx) if self.s.smtp_ssl
                else smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=15))
        with conn as smtp:
            if self.s.smtp_starttls and not self.s.smtp_ssl:
                smtp.starttls(context=ctx)
            if self.s.smtp_username:
                smtp.login(self.s.smtp_username, self.s.smtp_password or "")
            smtp.send_message(msg)


def make_mailer(settings: Settings) -> Mailer:
    return SMTPMailer(settings) if settings.mail_backend == "smtp" else ConsoleMailer()


def send_safely(mailer: Mailer, to: str, subject: str, text: str) -> bool:
    """Never lets a mail failure leak details to the person signing up; the server log keeps the reason."""
    try:
        mailer.send(to, subject, text)
        return True
    except Exception:
        log.exception("could not send email to %s (%s)", to, subject)
        return False


def verification_email(name: str, link: str) -> tuple[str, str]:
    return ("Verify your email for Quixotic AI",
            f"Hi {name},\n\nPlease confirm your email address by opening this link:\n\n{link}\n\n"
            "Verifying your email does not give access yet: an administrator still has to approve your account.\n\n"
            "If you did not sign up, you can ignore this message.\n")


def reset_email(name: str, link: str) -> tuple[str, str]:
    return ("Reset your Quixotic AI password",
            f"Hi {name},\n\nSomeone asked to reset the password of your Quixotic AI account. To choose a new password, open:\n\n"
            f"{link}\n\nThe link works once. If you did not ask for this, you can ignore this message; your password stays the same.\n")


def decision_email(name: str, approved: bool, url: str) -> tuple[str, str]:
    if approved:
        return ("Your Quixotic AI account is approved",
                f"Hi {name},\n\nAn administrator approved your account. You can sign in at {url}\n")
    return ("Your Quixotic AI account request",
            f"Hi {name},\n\nYour account request was not approved. If you think this is a mistake, please contact your administrator.\n")
