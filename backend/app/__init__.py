from flask import Flask
from flask_mail import Mail

from app.config import Config

mail = Mail()

app = Flask(__name__)
app.config.from_object(Config)

mail.init_app(app)

# Not necessary to keep ASCII, and impedes debugging Japanese
app.config['JSON_AS_ASCII'] = False

def log(msg):
    print(msg, flush=True)

from app import views
from app import auth
