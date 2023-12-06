import os

class CommonConfig(object):
    AUTH_TOKEN_EXPIRATION = 10*60

env = os.environ.get('FLASK_ENV')
print(f'FLASK_ENV is {env!r}')
if env == 'development':
    class Config(CommonConfig):
        MAIL_ENABLED = False
        MAIL_LOGGED = True
        AUTH_KEY = 'DevAuthKey'
        DB_URL = f'postgresql+psycopg://postgres@localhost/yukawa'
elif env == 'production':
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_HOST = os.environ['DB_HOST']

    class Config(CommonConfig):
        MAIL_ENABLED = True
        MAIL_LOGGED = False
        AUTH_KEY = os.environ['AUTH_KEY']
        DB_URL = f'postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/yukawa'
else:
    raise ValueError(f'unknown FLASK_ENV {env!r}')
