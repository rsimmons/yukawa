import time
from flask import request, jsonify, render_template
import jwt
import humanize

from app import app, log, db
from app.email import send_email

AUTH_TOKEN_EXPIRATION = 10*60

# to generate a random key:
# ''.join(random.choices(string.ascii_letters+string.digits, k=32))

# note that while named "login", this is also used to login the first time,
# with implicit signup
@app.route('/login', methods=['POST'])
def login():
    req = request.get_json()

    email = req['email']

    log(f'login attempt to {email!r}')

    # TODO: validate email address

    # create or load user
    with db.engine.connect() as conn:
        result = conn.execute(
            db.user.select().where(db.user.c.email == email)
        ).fetchone()

    if result is None:
        with db.engine.begin() as conn:
            result = conn.execute(
                db.user.insert().values(email=email)
            )
            user_id = result.inserted_primary_key[0]
    else:
        user_id = result.id

    # create auth token
    auth_token = jwt.encode({
        'u': user_id,
        'exp': int(time.time() + app.config['AUTH_TOKEN_EXPIRATION']),
    }, app.config['AUTH_KEY'], algorithm='HS256')

    # note that this URL goes to the client, not this backend
    auth_url = app.config['AUTH_URL_PREFIX'] + auth_token

    # send email with link containing auth token
    exp_str = humanize.precisedelta(app.config['AUTH_TOKEN_EXPIRATION'])
    text_body = render_template('email/auth.txt', url=auth_url, exp=exp_str)
    html_body = render_template('email/auth.html', url=auth_url, exp=exp_str)
    send_email(
        subject=app.config['AUTH_EMAIL_SUBJECT'],
        sender=app.config['AUTH_EMAIL_SENDER'],
        recipients=[email],
        text_body=text_body,
        html_body=html_body,
    )

    return jsonify({
        'status': 'ok',
    })

@app.route('/auth', methods=['POST'])
def auth():
    req = request.get_json()

    token = req['token']

    try:
        payload = jwt.decode(token, app.config['AUTH_KEY'], algorithms=['HS256'])
    except jwt.exceptions.DecodeError:
        return jsonify({
            'status': 'invalid token',
        })
    except jwt.exceptions.ExpiredSignatureError:
        return jsonify({
            'status': 'token expired',
        })

    user_id = payload['u']

    # create session token for user_id and return it
    session_token = jwt.encode({
        'u': user_id,
    }, app.config['SESSION_KEY'], algorithm='HS256')

    return jsonify({
        'status': 'ok',
        'token': session_token,
    })
