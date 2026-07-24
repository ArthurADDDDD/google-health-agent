import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from google_health_agent.config import Settings
from google_health_agent.errors import ConfigurationError


class Mailer(ABC):
    @abstractmethod
    def send(self, subject: str, markdown: str) -> None:
        """Deliver a generated brief."""


class ConsoleMailer(Mailer):
    def send(self, subject: str, markdown: str) -> None:
        print(f"{subject}\n\n{markdown}")


class SMTPMailer(Mailer):
    def __init__(self, settings: Settings) -> None:
        required = {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_USERNAME": settings.smtp_username,
            "SMTP_PASSWORD": settings.smtp_password,
            "MAIL_FROM": settings.mail_from,
            "MAIL_TO": settings.mail_to,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigurationError(f"Missing SMTP configuration: {', '.join(missing)}")
        self.settings = settings

    def send(self, subject: str, markdown: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.mail_from
        message["To"] = self.settings.mail_to
        message.set_content(markdown)
        assert self.settings.smtp_host
        assert self.settings.smtp_username
        assert self.settings.smtp_password
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as client:
            client.starttls()
            client.login(
                self.settings.smtp_username,
                self.settings.smtp_password.get_secret_value(),
            )
            client.send_message(message)
