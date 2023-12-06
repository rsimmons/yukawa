import json
from flask_mail import Message

from app import app, mail, log

def send_email(subject, sender, recipients, text_body, html_body):
    if app.config['MAIL_ENABLED']:
        with app.app_context():
            msg = Message(subject, sender=sender, recipients=recipients)
            msg.body = text_body
            msg.html = html_body
            mail.send(msg)

    if app.config['MAIL_LOGGED']:
        email_json = json.dumps({
            'sender': sender,
            'recipients': recipients,
            'subject': subject,
            'text_body': text_body,
            'html_body': html_body,
        }, ensure_ascii=False)
        log(f'send email: {email_json}')
