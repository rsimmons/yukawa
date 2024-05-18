from flask import Flask

from app.config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Not necessary to keep ASCII, and impedes debugging Japanese
app.config['JSON_AS_ASCII'] = False

def log(msg):
    print(msg, flush=True)

from app import views
