from flask import jsonify, g
from flask_cors import CORS

from app import app, db
from app.auth import require_session
from app.db import ping_db

if app.config['CORS_ENABLED']:
    print('enabling CORS')
    CORS(app)

@app.route('/')
def hello_world():
    return '<p>Hello, World!</p>'

@app.route('/ping')
def ping():
    return f'<p>pong: {ping_db()}</p>'

@app.route('/user', methods=['POST'])
@require_session
def user():
    with db.engine.connect() as conn:
        result = conn.execute(
            db.user.select().where(db.user.c.id == g.user_id)
        ).fetchone()
    print(result)

    return jsonify({
        'status': 'ok',
        'user_id': g.user_id,
        'email': result.email,
    })
