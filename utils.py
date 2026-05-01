import smtplib
import ssl
import certifi
from email.message import EmailMessage
from flask import current_app


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain-text email using SMTP settings from app.config."""
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')
    # MAIL_DEFAULT_SENDER can be a tuple (name, email) or a string
    if isinstance(sender, tuple):
        sender = f"{sender[0]} <{sender[1]}>"

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email
    msg.set_content(body)

    smtp_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    use_ssl = current_app.config.get('MAIL_USE_SSL', False)
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')

    # Use certifi's CA bundle so macOS/python installations without system CA certs still verify correctly.
    context = ssl.create_default_context(cafile=certifi.where())

    # Use a context manager so the connection is closed cleanly even if an error occurs.
    if use_ssl:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10, context=context) as smtp:
            smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=context)
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)