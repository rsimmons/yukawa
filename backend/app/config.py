import os

class CommonConfig(object):
    AUTH_TOKEN_EXPIRATION = 10*60

    AUTH_EMAIL_SUBJECT = 'Log in to Yukawa'
    AUTH_EMAIL_SENDER = 'Yukawa <russ+yukawa@rsimmons.org>'

env = os.environ.get('FLASK_ENV')
print(f'FLASK_ENV is {env!r}')
if env == 'development':
    class Config(CommonConfig):
        DB_URL = f'postgresql+psycopg://postgres@localhost/yukawa'
        DB_ECHO = True

        MAIL_ENABLED = False
        MAIL_LOGGED = True

        AUTH_KEY = 'DevAuthKey'
        AUTH_URL_PREFIX = 'http://localhost:5173/auth?token='

        SESSION_KEY = 'DevSessionKey'
elif env == 'production':
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_HOST = os.environ['DB_HOST']

    class Config(CommonConfig):
        DB_URL = f'postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/yukawa'

        MAIL_ENABLED = True
        MAIL_LOGGED = False

        AUTH_KEY = os.environ['AUTH_KEY']
        AUTH_URL_PREFIX = 'http://example.com/auth?token='

        SESSION_KEY = os.environ['SESSION_KEY']
else:
    raise ValueError(f'unknown FLASK_ENV {env!r}')
