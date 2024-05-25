import argparse
import json
from pathlib import Path

import webvtt
import requests

from index_settings import INDEX_SETTINGS

def jdump(obj):
    return json.dumps(obj, ensure_ascii=False)

def simplify_lang_code(lang):
    return lang.split('-')[0] if '-' in lang else lang

def iter_videos(archive_dir, dir, lang):
    for p in dir.iterdir():
        if p.is_dir():
            yield from iter_videos(archive_dir, p, lang)
        elif p.suffix in ('.webm', '.mp4', '.mkv'):
            vid = {
                'vid_fn': str(p.relative_to(archive_dir)),
            }

            # find all files with matching prefix
            potential_sub_paths = []
            for related_fn in dir.glob(p.stem + '.*'):
                if related_fn == p:
                    continue
                elif str(related_fn).endswith('.info.json'):
                    with open(related_fn) as info_f:
                        info = json.load(info_f)
                        vid['title'] = info['title']
                elif related_fn.suffix == '.vtt':
                    if len(related_fn.suffixes) == 1:
                        # no language suffix, assume it is the right language
                        potential_sub_paths.append(related_fn)
                    elif simplify_lang_code(related_fn.suffixes[-2]) == f'.{lang}':
                        potential_sub_paths.append(related_fn)

            if len(potential_sub_paths) > 1:
                print(f'WARNING: multiple potential subs found for video {p}')
            if potential_sub_paths:
                captions_fn = sorted(potential_sub_paths)[0]
                vid['captions_fn'] = str(captions_fn.relative_to(archive_dir))
                vid['captions'] = []
                with open(captions_fn) as subs_f:
                    cues = webvtt.read_buffer(subs_f)
                    for cue in cues:
                        vid['captions'].append({
                            'start': cue.start_in_seconds,
                            'end': cue.end_in_seconds,
                            'text': cue.text,
                        })

            yield vid

def get_index_for_lang(lang):
    return f'yukawa-captions-{lang}'

def create_fresh_index(lang):
    index_settings = INDEX_SETTINGS[lang]
    index = get_index_for_lang(lang)

    # check if index exists
    resp = requests.head(f'http://localhost:9200/{index}')
    if resp.status_code == 200:
        # delete if it already exists
        print(f'deleting existing index: {index}')
        resp = requests.delete(f'http://localhost:9200/{index}')
        resp.raise_for_status()
    elif resp.status_code != 404:
        resp.raise_for_status()

    print(f'creating index: {index}')
    resp = requests.put(f'http://localhost:9200/{index}', json=index_settings)

def index_captions(archive_dir, lang):
    create_fresh_index(lang)

    index = get_index_for_lang(lang)

    for vid_info in iter_videos(archive_dir, archive_dir / lang, lang):
        if 'captions' in vid_info:
            print(f'indexing captions: {vid_info["vid_fn"]} ({len(vid_info["captions"])})')

            lines = []
            for caption in vid_info['captions']:
                doc = {
                    'text': caption['text'],
                    'info': {
                        'vid_fn': vid_info['vid_fn'],
                        'captions_fn': vid_info['captions_fn'],
                        'start': caption['start'],
                        'end': caption['end'],
                    },
                }
                lines.append(jdump({'index': {}}) + '\n')
                lines.append(jdump(doc) + '\n')
            data = ''.join(lines)

            resp = requests.post(f'http://localhost:9200/{index}/_bulk', headers={'Content-Type': 'application/x-ndjson'}, data=data.encode('utf-8'))
            resp.raise_for_status()

    resp = requests.post(f'http://localhost:9200/{index}/_refresh')
    resp.raise_for_status()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='command')

    parser_index_subs = subparsers.add_parser('index_captions')
    parser_index_subs.add_argument('archive_dir', type=Path)
    parser_index_subs.add_argument('lang')

    args = parser.parse_args()

    if args.command == 'index_captions':
        index_captions(args.archive_dir, args.lang)
    else:
        raise Exception('invalid command')
