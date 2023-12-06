from flask import jsonify, g

from app import app
from app.auth import require_session
from app.db import ping_db

@app.route('/')
def hello_world():
    return '<p>Hello, World!</p>'

@app.route('/ping')
def ping():
    return f'<p>pong: {ping_db()}</p>'

@app.route('/user')
@require_session
def user():
    return jsonify({
        'status': 'ok',
        'user_id': g.user_id,
    })
