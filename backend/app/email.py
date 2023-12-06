import json
import requests

from app import app, log

def send_email(subject, sender, recipient, text_body, html_body):
    if app.config['MAIL_ENABLED']:
        requests.post('https://api.postmarkapp.com/email',
            headers={
                'Accept': 'application/json',
                'X-Postmark-Server-Token': app.config['POSTMARK_SERVER_TOKEN'],
            },
            json={
                'From': sender,
                'To': recipient,
                'Subject': subject,
                'TextBody': text_body,
                'HtmlBody': html_body,
                'MessageStream': 'yukawa-prod-transactional',
            },
        )

    if app.config['MAIL_LOGGED']:
        email_json = json.dumps({
            'sender': sender,
            'recipient': recipient,
            'subject': subject,
            'text_body': text_body,
            'html_body': html_body,
        }, ensure_ascii=False)
        log(f'send email: {email_json}')
