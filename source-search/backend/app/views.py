import time

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
            'mediaUrl': 'http://localhost:9000/' + hit_source['info']['vid_fn'],
            'captionsUrl': 'http://localhost:9000/' + hit_source['info']['captions_fn'],
        })

    return jsonify(response)
