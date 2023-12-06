import time
from flask import request, jsonify
import jwt
import humanize

from app import app, log
from app.email import send_email
from app.db import engine, user

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
            user.select().where(user.c.email == email)
        ).fetchone()

    if result is None:
        with db.engine.begin() as conn:
            result = conn.execute(
                user.insert().values(email=email)
            )
            user_id = result.inserted_primary_key[0]
    else:
        user_id = result.id

    # create auth token
    auth_token = jwt.encode({
        'user_id': user_id,
        'exp': time.time() + app.config['AUTH_TOKEN_EXPIRATION'],
    }, app.config['AUTH_KEY'], algorithm='HS256')

    # send email with link containing auth token
    exp_str = humanize.precisedelta(app.config['AUTH_TOKEN_EXPIRATION'])
    text_body = render_template('email/auth.txt', token=auth_token, exp=exp_str)
    html_body = render_template('email/auth.html', token=auth_token, exp=exp_str)
    send_email(
        sub
    )

    return jsonify({
        'status': 'ok',
    })

@app.route('/auth', methods=['POST'])
def auth():
    req = request.get_json()

    return jsonify({
        'status': 'ok',
    })
