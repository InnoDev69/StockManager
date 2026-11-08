import smtplib
from email.mime.text import MIMEText
import sys
from .logger import logger
from dotenv import load_dotenv
import os

if getattr(sys, 'frozen', False):
    logger.info("Running in a PyInstaller bundle", source="EMAIL_MODULE")
    load_dotenv(os.path.join(sys._MEIPASS, '.env'))
else:
    logger.info("Running in a normal Python environment", source="EMAIL_MODULE")
    load_dotenv()

def _parse_port(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

class EmailSender:
    def __init__(self, smtp_server, smtp_port, username, password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.user_email = username
        self.password = password
        # Sin configuración completa el envío queda desactivado en vez de romper el arranque
        self.enabled = all([smtp_server, smtp_port, username, password])
        if not self.enabled:
            logger.warning("Correo desactivado: falta configuración SMTP (SMTP_SERVER, SMTP_PORT, SMTP_USERNAME o SMTP_PASSWORD).", source="EMAIL_MODULE")

    def send_email(self, recipient_email, subject, body):
        if not self.enabled:
            logger.warning("No se envió el correo: el envío está desactivado.", source="EMAIL_MODULE")
            return False

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.user_email
        msg['To'] = recipient_email

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.connect(self.smtp_server, self.smtp_port)
                server.login(self.user_email, self.password)
                server.send_message(msg)
            logger.info("Email sent successfully.", source="EMAIL_MODULE")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}", source="EMAIL_MODULE")
            return False

email_sender = EmailSender(
    smtp_server=os.getenv('SMTP_SERVER'),
    smtp_port=_parse_port(os.getenv('SMTP_PORT')),
    username=os.getenv('SMTP_USERNAME'),
    password=os.getenv('SMTP_PASSWORD')
)