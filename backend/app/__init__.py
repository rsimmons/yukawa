from flask import Flask, request, abort

from config import config

app = Flask(__name__)
app.config.from_object(config)

# Not necessary to keep ASCII, and impedes debugging Japanese
app.config['JSON_AS_ASCII'] = False

def log(msg):
    print(msg, flush=True)

@app.before_request
def ensure_secure():
    if app.config['ENFORCE_HTTPS'] and (request.path != '/'): # ignore health check
        if not (request.is_secure or (request.headers['X-Forwarded-Proto'].lower() == 'https')):
            abort(404)

from app import views
from app import auth
