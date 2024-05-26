import time
import os
import subprocess
import random
import string
from io import StringIO

from flask import request, jsonify, g
from flask_cors import CORS
import requests

from app import app

if app.config['CORS_ENABLED']:
    print('enabling CORS')
    CORS(app)

@app.route('/')
def hello_world():
    return '<p>Hello, World!</p>'

@app.route('/search')
def search():
    query = request.args['query']
    lang = request.args['lang']

    phrases = query.split()
    assert phrases

    subqueries = []
    exact_phrases = []
    for phrase in phrases:
        if phrase.startswith('"') and phrase.endswith('"') and (len(phrase) >= 3):
            exact_phrase = phrase[1:-1]
            if ('*' in exact_phrase) or ('?' in exact_phrase):
                # if someone uses these, just skip it, because they have special meaning
                continue
            subqueries.append({'wildcard': {'text.wc': {'value': '*' + exact_phrase + '*'}}})
            exact_phrases.append(exact_phrase)
        else:
            subqueries.append({'match_phrase': {'text': phrase}})

    index = 'yukawa-captions-' + lang

    t0 = time.time()
    main_resp = requests.get(f'{app.config["ES_BASE_URL"]}/{index}/_search', json={
        'query': {
            'bool': {
                'must': subqueries,
            }
        },
        'highlight': {
            'type': 'unified',
            'fields': {
                'text': {
                    'number_of_fragments': 0, # forces it to return entire field
                },
            },
        },
        'size': 1000,
    })
    dt = time.time() - t0
    main_resp.raise_for_status()
    print('es_request_time', f'{dt}', flush=True)

    response = {}

    # FORMAT RESULT COUNT
    main_resp_body = main_resp.json()
    hitcount_value = main_resp_body['hits']['total']['value']

    response['hitCount'] = hitcount_value

    if main_resp_body['hits']['total']['relation'] == 'eq':
        response['hitsLimited'] = False
    elif main_resp_body['hits']['total']['relation'] == 'gte':
        response['hitsLimited'] = True
    else:
        assert False

    response['hits'] = []
    for hit in main_resp_body['hits']['hits']:
        hit_source = hit['_source']
        response['hits'].append({
            'id': hit['_id'],
            'start': hit_source['info']['start'],
            'end': hit_source['info']['end'],
            'text': hit_source['text'],
            'highlight': hit.get('highlight', {}).get('text', None),
            'src_title': hit_source['info']['src_title'],
            'src_url': hit_source['info']['src_url'],
            'vid_fn': hit_source['info']['vid_fn'], # TODO: this seems hacky to return both this and media_url
            'media_url': app.config['MEDIA_BASE_URL'] + hit_source['info']['vid_fn'],
            'captions_url': app.config['MEDIA_BASE_URL'] + hit_source['info']['captions_fn'],
        })

    return jsonify(response)

def generate_id():
    return ''.join(random.choice(string.ascii_letters+string.digits) for i in range(12))

def extract_video(vid_fn, start_time, end_time, out_fn):
    OUTPUT_WIDTH = 854
    OUTPUT_HEIGHT = 480
    cmdline = [
        'ffmpeg',
        '-ss', str(start_time),
        '-accurate_seek',
        '-i', vid_fn,
        '-t', str(end_time - start_time),
        # make correct width and height, padding with black in one dimension if necessary. from https://superuser.com/a/547406
        '-vf', 'scale=(sar*iw)*min({width}/(sar*iw)\\,{height}/ih):ih*min({width}/(sar*iw)\\,{height}/ih),pad={width}:{height}:({width}-(sar*iw)*min({width}/(sar*iw)\\,{height}/ih))/2:({height}-ih*min({width}/(sar*iw)\\,{height}/ih))/2,setsar=1'.format(width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT),
        # I tried this filter instead for resizing, but it didn't work when input had SAR 4:3 DAR 16:9 (60 Gohan Taisakushitsu)
        #'-vf', 'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:-1:-1:color=black,setdar=16:9,setsar=1'.format(width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT),
        '-ac', '2',
    ]
    if out_fn.endswith('.mp4'):
        cmdline += ['-strict', '-2', '-acodec', 'aac', '-vcodec', 'libx264', '-preset', 'slow', '-f', 'mp4']
    elif out_fn.endswith('.webm'):
        cmdline += ['-acodec', 'libvorbis', '-vcodec', 'libvpx', '-crf', '10', '-b:v', '1M', '-f', 'webm']
    else:
        assert False, 'unknown output format'

    cmdline += ['-y', out_fn]

    with open(os.devnull, 'w') as devnull:
        subprocess.check_call(cmdline, stderr=devnull)

@app.route('/cut', methods=['POST'])
def cut():
    data = request.json
    assert isinstance(data, dict)

    lang = data['lang']
    vid_fn = data['vid_fn']
    start = data['start']
    end = data['end']

    vid_path = os.path.join(app.config['MEDIA_BASE_DIR'], vid_fn)

    clip_id = generate_id()
    clip_fn = f'{clip_id}.mp4'
    clip_path = os.path.join(app.config['CLIP_OUTPUT_DIR'], lang, clip_fn)

    print(f'cutting {vid_path} from {start} to {end} to {clip_path}')

    extract_video(vid_path, start, end, clip_path)

    return jsonify({
        'status': 'ok',
        'clip_fn': clip_fn,
    })
