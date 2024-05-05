import random

from flask import request, jsonify, g
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

@app.route('/random_clip', methods=['POST'])
@require_session
def random_clip():
    clips = app.config['CLIPS']
    clip = random.choice(clips)

    sorted_trans = sorted(clip['translations'], key=lambda t: (t['src'] == 'subs'), reverse=True)
    best_trans = sorted_trans[0]
    translation = best_trans.get('text')
    if translation is None:
        translation = '\n'.join(s['text'] for s in best_trans['subs'])

    return jsonify({
        'clip_id': clip['clip_id'],
        'media_url': app.config['CLIP_URL_PREFIX'] + clip['source_id'] + '/' + clip['media'][0],
        'transcription': '\n'.join(sub['text'] for sub in clip['subs']),
        'translation': translation,
    })

@app.route('/report_clip_understood', methods=['POST'])
@require_session
def report_clip_understood():
    req = request.get_json()
    print('report_clip_understood:', req)

    return jsonify({
        'status': 'ok',
    })
