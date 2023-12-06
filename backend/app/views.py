from app import app, log
from app.email import send_email
from app.db import ping_db

@app.route('/')
def hello_world():
    return '<p>Hello, World!</p>'

@app.route('/ping')
def ping():
    return f'<p>pong: {ping_db()}</p>'

@app.route('/mail')
def mail():
    send_email(
        subject='Test',
        sender='russ@rsimmons.org',
        recipients=['russ+test@rsimmons.org'],
        text_body='test 123',
        html_body='<p>test 123 html</p>',
    )
    return '<p>sent?</p>'
