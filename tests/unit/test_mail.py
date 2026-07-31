from google_health_agent.config import Settings
from google_health_agent.mail import ConsoleMailer, DisabledMailer, SMTPMailer


class FakeSMTP:
    instance = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logged_in = None
        self.message = None
        FakeSMTP.instance = self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def starttls(self):
        return None

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.message = message


def test_console_mailer(capsys) -> None:
    ConsoleMailer().send("Synthetic subject", "SYNTHETIC DATA")
    assert "SYNTHETIC DATA" in capsys.readouterr().out


def test_disabled_mailer_never_writes_report_content(capsys) -> None:
    DisabledMailer().send("Private subject", "PRIVATE HEALTH CONTENT")
    assert capsys.readouterr().out == ""


def test_smtp_mailer_with_mock_transport(monkeypatch) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    settings = Settings(
        mailer="smtp",
        smtp_host="smtp.example.com",
        smtp_username="demo-user",
        smtp_password="mock-password",
        mail_from="sender@example.com",
        mail_to="recipient@example.com",
    )
    SMTPMailer(settings).send("Synthetic subject", "SYNTHETIC DATA")
    assert FakeSMTP.instance
    assert FakeSMTP.instance.logged_in == ("demo-user", "mock-password")
    assert FakeSMTP.instance.message["To"] == "recipient@example.com"
