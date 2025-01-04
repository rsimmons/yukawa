import os
from dataclasses import dataclass

# To generate a random key (e.g. for AUTH_KEY or SESSION_KEY):
# ''.join(random.choices(string.ascii_letters+string.digits, k=32))

@dataclass(frozen=True)
class Config:
    ENFORCE_HTTPS: bool
    AUTH_TOKEN_EXPIRATION: int
    AUTH_EMAIL_SUBJECT: str
    AUTH_EMAIL_SENDER: str
    DB_URL: str
    DB_ECHO: bool
    MAIL_ENABLED: bool
    MAIL_LOGGED: bool
    POSTMARK_SERVER_TOKEN: str | None
    AUTH_KEY: str
    AUTH_URL_PREFIX: str
    SESSION_KEY: str
    CORS_ORIGINS: list[str]
    CLIP_URL_PREFIX: str
    SRS_LOG_VERBOSE: bool

env = os.environ.get('FLASK_ENV')
print(f'FLASK_ENV is {env!r}')

if env == 'development':
    DEV_HOST = 'localhost'
    # DEV_HOST = '192.168.7.113' # ethernet
    # DEV_HOST = '192.168.7.134' # wifi

    config = Config(
        ENFORCE_HTTPS = False,
        AUTH_TOKEN_EXPIRATION = 10*60,
        AUTH_EMAIL_SUBJECT = 'Log in to Yukawa',
        AUTH_EMAIL_SENDER = 'Yukawa <russ@rsimmons.org>',
        DB_URL = f'postgresql+psycopg://postgres@localhost/yukawa',
        DB_ECHO = True,
        MAIL_ENABLED = False,
        MAIL_LOGGED = True,
        POSTMARK_SERVER_TOKEN = None,
        AUTH_KEY='DevAuthKey',
        AUTH_URL_PREFIX=f'http://{DEV_HOST}:4173/?authtoken=',
        SESSION_KEY='DevSessionKey',
        CORS_ORIGINS=['*'],
        CLIP_URL_PREFIX=f'http://{DEV_HOST}:9001/',
        SRS_LOG_VERBOSE=True,
    )
elif env == 'production':
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_HOST = os.environ['DB_HOST']

    config = Config(
        ENFORCE_HTTPS = True,
        AUTH_TOKEN_EXPIRATION = 10*60,
        AUTH_EMAIL_SUBJECT = 'Log in to Yukawa',
        AUTH_EMAIL_SENDER = 'Yukawa <russ@rsimmons.org>',
        DB_URL = f'postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/yukawa',
        DB_ECHO = False,
        MAIL_ENABLED = True,
        MAIL_LOGGED = False,
        POSTMARK_SERVER_TOKEN = os.environ['POSTMARK_SERVER_TOKEN'],
        AUTH_KEY = os.environ['AUTH_KEY'],
        AUTH_URL_PREFIX = 'https://yukawa.app/?authtoken=',
        SESSION_KEY = os.environ['SESSION_KEY'],
        CORS_ORIGINS = ['https://yukawa.app', 'https://yukawa-frontend.netlify.app'],
        CLIP_URL_PREFIX = 'https://yukawa-clips.s3.us-west-2.amazonaws.com/',
        SRS_LOG_VERBOSE = False,
    )
else:
    raise ValueError(f'unknown FLASK_ENV {env!r}')
