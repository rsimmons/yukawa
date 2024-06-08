import os
import json

# To generate a random key (e.g. for AUTH_KEY or SESSION_KEY):
# ''.join(random.choices(string.ascii_letters+string.digits, k=32))

# read clips from all_clips.json
# reading this here is a bit of a hack?
# with open('resources/all_clips.json') as f:
#     all_clips = json.load(f)

class CommonConfig(object):
    AUTH_TOKEN_EXPIRATION = 10*60

    AUTH_EMAIL_SUBJECT = 'Log in to Yukawa'
    AUTH_EMAIL_SENDER = 'Yukawa <russ@rsimmons.org>'

    # CLIPS = all_clips

env = os.environ.get('FLASK_ENV')
print(f'FLASK_ENV is {env!r}')
if env == 'development':
    # DEV_HOST = 'localhost'
    DEV_HOST = '192.168.7.113'

    class Config(CommonConfig):
        DB_URL = f'postgresql+psycopg://postgres@localhost/yukawa'
        DB_ECHO = True

        MAIL_ENABLED = False
        MAIL_LOGGED = True

        AUTH_KEY = 'DevAuthKey'
        AUTH_URL_PREFIX = f'http://{DEV_HOST}:4173/?authtoken='

        SESSION_KEY = 'DevSessionKey'

        CORS_ORIGINS = ['*']

        CLIP_URL_PREFIX = f'http://{DEV_HOST}:9001/'

        SRS_LOG_VERBOSE = True
elif env == 'production':
    DB_USER = os.environ['DB_USER']
    DB_PASSWORD = os.environ['DB_PASSWORD']
    DB_HOST = os.environ['DB_HOST']

    class Config(CommonConfig):
        DB_URL = f'postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/yukawa'

        MAIL_ENABLED = True
        MAIL_LOGGED = False
        POSTMARK_SERVER_TOKEN = os.environ['POSTMARK_SERVER_TOKEN']

        AUTH_KEY = os.environ['AUTH_KEY']
        AUTH_URL_PREFIX = 'https://yukawa.app/?authtoken='

        SESSION_KEY = os.environ['SESSION_KEY']

        CORS_ORIGINS = ['https://yukawa.app', 'https://yukawa-frontend.netlify.app']

        CLIP_URL_PREFIX = 'https://yukawa-clips.s3.us-west-2.amazonaws.com/'

        SRS_LOG_VERBOSE = False
else:
    raise ValueError(f'unknown FLASK_ENV {env!r}')
