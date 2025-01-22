import time
import json

from flask import request, jsonify, g
from flask_cors import CORS

from app import app, db
from app.auth import require_session
from app.db import ping_db
import srs
from app.lang import LANGS

print('enabling CORS')
CORS(app, origins=app.config['CORS_ORIGINS'])

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
    assert result is not None, f'user {g.user_id} not found'

    return jsonify({
        'status': 'ok',
        'user_id': g.user_id,
        'email': result.email,
    })

# @app.route('/random_clip', methods=['POST'])
# @require_session
# def random_clip():
#     clips = app.config['CLIPS']
#     clip = random.choice(clips)

#     sorted_trans = sorted(clip['translations'], key=lambda t: (t['src'] == 'subs'), reverse=True)
#     best_trans = sorted_trans[0]
#     translation = best_trans.get('text')
#     if translation is None:
#         translation = '\n'.join(s['text'] for s in best_trans['subs'])

#     return jsonify({
#         'clip_id': clip['clip_id'],
#         'media_url': app.config['CLIP_URL_PREFIX'] + clip['source_id'] + '/' + clip['media'][0],
#         'transcription': '\n'.join(sub['text'] for sub in clip['subs']),
#         'translation': translation,
#     })

@app.route('/report_clip_understood', methods=['POST'])
@require_session
def report_clip_understood():
    req = request.get_json()
    print('report_clip_understood:', req)

    return jsonify({
        'status': 'ok',
    })

@app.route('/pick_activity', methods=['POST'])
@require_session
def pick_activity():
    req = request.get_json()

    lang = req['lang']
    assert lang in LANGS
    t = time.time()

    with db.engine.connect() as conn:
        user_srs_row = conn.execute(
            db.user_srs.select().where(db.user_srs.c.user_id == g.user_id).where(db.user_srs.c.lang == lang)
        ).one_or_none()

    if user_srs_row:
        srs_data = user_srs_row.data
    else:
        srs_data = srs.init_srs_data()

    activity, atoms_info = srs.pick_activity(lang, srs_data, t)

    # log_obj = {
    #     'lang': lang,
    #     'user_id': g.user_id,
    #     'clip_id': question['clip_id'],
    #     't': t,
    # }
    # log_obj_json = json.dumps(log_obj)
    # print(f'pick_activity {log_obj_json}', flush=True)
    print(f'pick_activity {activity}', flush=True)

    return jsonify({
        'status': 'ok',
        'media_url_prefix': app.config['CLIP_URL_PREFIX'] + lang + '/',
        'activity': activity,
        'atoms_info': atoms_info,
    })

@app.route('/report_result', methods=['POST'])
@require_session
def report_result():
    req = request.get_json()

    lang = req['lang']
    assert lang in LANGS

    t = time.time()

    with db.engine.connect() as conn:
        user_srs_row = conn.execute(
            db.user_srs.select().where(db.user_srs.c.user_id == g.user_id).where(db.user_srs.c.lang == lang)
        ).one_or_none()

    if user_srs_row:
        srs_data = user_srs_row.data
    else:
        srs_data = srs.init_srs_data()

    srs_report = srs.report_result(lang, srs_data, req['result'], t)

    log_obj = {
        'lang': lang,
        'user_id': g.user_id,
        'result': req['result'],
        'srs': srs_report,
        't': t,
    }
    log_obj_json = json.dumps(log_obj)
    print(f'report_result {log_obj_json}', flush=True)

    with db.engine.begin() as conn:
        if user_srs_row:
            conn.execute(
                db.user_srs.update().where(db.user_srs.c.id == user_srs_row.id).values(data=srs_data)
            )
        else:
            conn.execute(
                db.user_srs.insert().values(user_id=g.user_id, lang=lang, data=srs_data)
            )

    return jsonify({
        'status': 'ok',
    })
