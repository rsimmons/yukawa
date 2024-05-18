import os
import json

class CommonConfig(object):
    pass

env = os.environ.get('FLASK_ENV')
print(f'FLASK_ENV is {env!r}')
if env == 'development':
    class Config(CommonConfig):
        CORS_ENABLED = True
        ES_BASE_URL = 'http://localhost:9200'
elif env == 'production':
    class Config(CommonConfig):
        CORS_ENABLED = False
else:
    raise ValueError(f'unknown FLASK_ENV {env!r}')
