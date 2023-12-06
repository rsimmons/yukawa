import time
from functools import wraps
from flask import request, jsonify, render_template, g
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

    current_time = int(time.time())

    # create or load user
    with db.engine.connect() as conn:
        result = conn.execute(
            db.user.select().where(db.user.c.email == email)
        ).fetchone()

    if result is None:
        with db.engine.begin() as conn:
            result = conn.execute(
                db.user.insert().values(
                    email=email,
                    created=current_time,
                    login_count=0,
                    last_login=current_time,
                )
            )
            user_id = result.inserted_primary_key[0]
    else:
        user_id = result.id

    # create auth token
    auth_token = jwt.encode({
        'u': user_id,
        'exp': int(current_time + app.config['AUTH_TOKEN_EXPIRATION']),
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

    # parse session token
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

    # extract user_id from session token
    user_id = payload['u']

    # update user login stats
    current_time = int(time.time())
    with db.engine.begin() as conn:
        conn.execute(
            db.user.update().where(db.user.c.id == user_id).values(
                login_count=db.user.c.login_count + 1,
                last_login=current_time,
            )
        )

    # create session token for user_id and return it
    session_token = jwt.encode({
        'u': user_id,
    }, app.config['SESSION_KEY'], algorithm='HS256')

    return jsonify({
        'status': 'ok',
        'token': session_token,
    })

def require_session(f):
    @wraps(f)
    def inner(*args, **kwargs):
        # get session token from header
        session_token = request.headers.get('X-Session-Token')
        if session_token is None:
            return jsonify({
                'status': 'session token required',
            }), 400

        # validate session token
        try:
            payload = jwt.decode(session_token, app.config['SESSION_KEY'], algorithms=['HS256'])
        except:
            return jsonify({
                'status': 'invalid session token',
            }), 400

        # extract user_id from session token
        user_id = payload['u']

        # store user_id in flask globals for use in route
        g.user_id = user_id

        return f(*args, **kwargs)
    return inner
