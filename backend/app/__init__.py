from flask import Flask, request

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Not necessary to keep ASCII, and impedes debugging Japanese
app.config['JSON_AS_ASCII'] = False

def log(msg):
    print(msg, flush=True)

@app.before_request
def ensure_secure():
    if app.config['ENFORCE_HTTPS']:
        assert request.is_secure or (request.headers.get('X-Forwarded-Proto').lower() == 'https')

from app import views
from app import auth
