import os
import json
import time
import argparse
import sqlite3
from urllib.parse import urlparse
from collections import Counter
from io import StringIO
import hashlib

import requests
import yt_dlp
import openai
from sudachipy import tokenizer, dictionary
import webvtt

parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest='command')

parser_add_yt_playlist = subparsers.add_parser('add_yt_playlist')
parser_add_yt_playlist.add_argument('--id', required=True)

parser_import_frags = subparsers.add_parser('import_frags')
parser_import_frags.add_argument('--number', type=int, required=True)

args = parser.parse_args()

conn = sqlite3.connect('anserv.db', isolation_level=None)
c = conn.cursor()

sudachi_tokenizer_obj = dictionary.Dictionary().create()

# algorithms:
# - ja1 - sudachi 0.6.7, dict core 20230927
def analyze_ja(text):
    normal_freq = Counter()
    morphemes = sudachi_tokenizer_obj.tokenize(text, tokenizer.Tokenizer.SplitMode.B)

    for m in morphemes:
        if not (m.part_of_speech()[0] in ['補助記号', '空白']):
            normal = m.normalized_form()
            normal_freq[normal] += 1

    return ('ja1', dict(normal_freq)) # convert to dict to be json-able

def format_yt_video_url(id):
    return f'https://www.youtube.com/watch?v={id}'

def format_yt_playlist_url(id):
    return f'https://www.youtube.com/playlist?list={id}'

def add_yt_thumbnail(thumbs):
    thumb = thumbs[-1]
    IMAGE_WIDTH = 336
    IMAGE_HEIGHT = 188
    assert thumb['width'] == IMAGE_WIDTH
    assert thumb['height'] == IMAGE_HEIGHT
    image_url = thumb['url']
    parsed = urlparse(image_url)
    image_ext = os.path.splitext(parsed.path)[1][1:]
    assert image_ext in ['jpg', 'png']
    image_data = requests.get(image_url).content

    image_md5 = hashlib.md5(image_data).hexdigest()
    c.execute('INSERT INTO image (extension, md5, data, width, height) VALUES (?, ?, ?, ?, ?)', (image_ext, image_md5, image_data, IMAGE_WIDTH, IMAGE_HEIGHT))
    return c.lastrowid

def add_yt_video(info):
    id = info['id']
    url = info['url']

    YT_AUDIO_DIR = 'yt-audio'
    # ensure yt-audio subdir exists
    os.makedirs(YT_AUDIO_DIR, exist_ok=True)

    with yt_dlp.YoutubeDL({
        'format': 'bestaudio',
        'outtmpl': 'yt-audio/%(id)s.%(ext)s',
    }) as ydl:
        error_code = ydl.download([url])

    if error_code:
        raise Exception(f'error downloading {url}')

    # find audio output file by looking in output dir (can't be sure of extension)
    audio_fn = None
    for fn in os.listdir(YT_AUDIO_DIR):
        if fn.startswith(id):
            audio_fn = os.path.join(YT_AUDIO_DIR, fn)
            break
    if audio_fn is None:
        raise Exception(f'audio file not found for {url}')
    audio_ext = os.path.splitext(audio_fn)[1][1:]
    assert audio_ext in ['m4a', 'webm', 'mp3']

    # get audio data
    with open(audio_fn, 'rb') as audio_file:
        audio_data = audio_file.read()

    # do speech recognition
    openai.api_key = os.getenv('OPENAI_API_KEY')

    print(f'transcribing audio {audio_fn} for video {url}')
    with open(audio_fn, 'rb') as audio_file:
        transcript = openai.Audio.transcribe('whisper-1', audio_file, response_format='vtt')

    # do analysis
    captions = []
    for caption in webvtt.read_buffer(StringIO(transcript)):
        captions.append(caption.text)
    transcript_plain = '\n'.join(captions)
    (an_algo, an) = analyze_ja(transcript_plain)
    analysis_json = json.dumps({an_algo: an}, ensure_ascii=False, sort_keys=True)

    current_time = int(time.time())

    # update the database
    c.execute('BEGIN')

    # insert image row
    print(f'inserting image row for video {url}')
    image_id = add_yt_thumbnail(info['thumbnails'])

    # insert audio row
    print(f'inserting audio row for video {url}')
    audio_md5 = hashlib.md5(audio_data).hexdigest()
    c.execute('INSERT INTO audio (extension, md5, data) VALUES (?, ?, ?)', (audio_ext, audio_md5, audio_data))
    audio_id = c.lastrowid

    # insert a new piece row
    print(f'inserting piece row for video {url}')
    c.execute('INSERT INTO piece (url, kind, title, image_id, audio_id, stt_method, text_format, text, analysis, time_fetched, time_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (url, 'video', info['title'], image_id, audio_id, 'openai-api-whisper-1', 'vtt', transcript, analysis_json, current_time, current_time))
    piece_id = c.lastrowid

    conn.commit()

    return piece_id

def add_yt_playlist(id):
    playlist_url = format_yt_playlist_url(id)

    vid_infos = []
    with yt_dlp.YoutubeDL({
        'extract_flat': 'in_playlist',
        'playlistend': 20,
    }) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        for vid_info in info['entries']:
            if vid_info['_type'] != 'url':
                continue
            if vid_info['duration'] is None: # this seems to skip unviewable videos
                continue
            if vid_info['availability'] == 'subscriber_only':
                continue
            vid_infos.append(vid_info)
    print(f'found {len(vid_infos)} videos in playlist {playlist_url}')

    # check if we already have a source row for this playlist url
    c.execute('SELECT id FROM source WHERE url = ?', (playlist_url,))
    source_row = c.fetchone()

    if source_row:
        source_id = source_row[0]
    else:
        c.execute('BEGIN')

        image_id = add_yt_thumbnail(info['thumbnails'])

        c.execute('INSERT INTO source (url, kind, title, image_id, time_updated) VALUES (?, "video", ?, ?, NULL)', (playlist_url, info['title'], image_id))
        source_id = c.lastrowid

        conn.commit()

    with yt_dlp.YoutubeDL({
        'format': 'bestaudio'
    }) as ydl:
        for vid_info in vid_infos:
            vid_url = format_yt_video_url(vid_info['id']) # to ensure it's canonical
            assert vid_url == vid_info['url']

            # check if we already have a piece row for this video url
            c.execute('SELECT id FROM piece WHERE url = ?', (vid_url,))
            piece_row = c.fetchone()

            if piece_row is not None:
                # we already have a piece row for this video, so continue
                piece_id = piece_row[0]
            else:
                print(f'adding video {vid_url}')
                piece_id = add_yt_video(vid_info)

                # insert piece_source row
                print(f'inserting piece_source row for video {vid_url} source {playlist_url}')
                c.execute('BEGIN')
                c.execute('INSERT INTO piece_source (piece_id, source_id) VALUES (?, ?)', (piece_id, source_id))
                conn.commit()

    # TODO: set time_updated

if args.command == 'add_yt_playlist':
    add_yt_playlist(args.id)
else:
    raise Exception('invalid command')
