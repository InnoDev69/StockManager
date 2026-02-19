import smtplib
from email.mime.text import MIMEText
from tools.logger import logger
from dotenv import load_dotenv
import os

load_dotenv()

class EmailSender:
    def __init__(self, smtp_server, smtp_port, username, password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.user_email = username
        self.password = password

    def send_email(self, recipient_email, subject, body):
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.user_email
        msg['To'] = recipient_email

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.user_email, self.password)
                server.send_message(msg)
            logger.info("Email sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            
email_sender = EmailSender(
    smtp_server=os.getenv('SMTP_SERVER'),
    smtp_port=int(os.getenv('SMTP_PORT')),
    username=os.getenv('SMTP_USERNAME'),
    password=os.getenv('SMTP_PASSWORD')
)