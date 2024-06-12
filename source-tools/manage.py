import argparse
import json
from pathlib import Path
import itertools
import re
from collections import Counter

import webvtt
import requests
import spacy
from spacy.lang.es import Spanish

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
                        vid['src_title'] = info['title']
                        vid['src_url'] = info['webpage_url']
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
                        'src_title': vid_info['src_title'],
                        'src_url': vid_info['src_url'],
                    },
                }
                lines.append(jdump({'index': {}}) + '\n')
                lines.append(jdump(doc) + '\n')
            data = ''.join(lines)

            resp = requests.post(f'http://localhost:9200/{index}/_bulk', headers={'Content-Type': 'application/x-ndjson'}, data=data.encode('utf-8'))
            resp.raise_for_status()

    resp = requests.post(f'http://localhost:9200/{index}/_refresh')
    resp.raise_for_status()

RE_WORD = re.compile(r'\w+')

def get_normalized_words_es(text):
    result = []
    for m in RE_WORD.finditer(text):
        norm = m.group().lower()
        result.append(norm)
    return result

def analyze_captions(archive_dir, lang, limit):
    if lang == 'es':
        nlp = Spanish()
        nlp.add_pipe("sentencizer")
    else:
        assert False

    word_freq = {} # currently these are lowercased but not stemmed/lemmatized

    print('determining token frequencies')
    for vid_info in itertools.islice(iter_videos(archive_dir, archive_dir / lang, lang), limit):
        if 'captions' in vid_info:
            for caption in vid_info['captions']:
                for word in get_normalized_words_es(caption['text']):
                    word_freq[word] = word_freq.get(word, 0) + 1

    ordered_word_freqs = sorted(word_freq.items(), key=lambda x: -x[1])
    word_rank = {word: i+1 for (i, (word, _)) in enumerate(ordered_word_freqs)}

    print('finding sentence ranks')
    ranked_sentences = []
    for vid_info in itertools.islice(iter_videos(archive_dir, archive_dir / lang, lang), limit):
        if 'captions' in vid_info:
            joined_captions = '\n'.join(caption['text'] for caption in vid_info['captions'])
            doc = nlp(joined_captions)
            for sent in doc.sents:
                clean_sent_text = sent.text.replace('​', ' ').strip().replace('\n', ' ').lstrip('- ').lstrip('-').rstrip('¿').rstrip('¡')
                if not clean_sent_text:
                    continue
                words = get_normalized_words_es(clean_sent_text)
                if not words:
                    continue
                highest_rank = max(word_rank[word] for word in words)
                ranked_sentences.append((highest_rank, clean_sent_text))

    ranked_sentences.sort()
    current_rank = 0
    prog = []
    word_num = 0
    for rank, text in ranked_sentences:
        if rank > current_rank:
            new_word = ordered_word_freqs[rank-1][0]
            current_rank = rank
            word_num += 1
            prog.append({'word': new_word, 'rank': rank, 'word_num': word_num, 'sent_count': Counter()})
        prog[-1]['sent_count'][text] += 1

    for step in prog:
        print()
        print(f'{step["word"]} #{step["word_num"]} (rank {step["rank"]})')
        for sent, count in step['sent_count'].most_common():
            print(f'  ({count}) {sent}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest='command')

    parser_index_subs = subparsers.add_parser('index_captions')
    parser_index_subs.add_argument('archive_dir', type=Path)
    parser_index_subs.add_argument('lang')

    parser_analyze_captions = subparsers.add_parser('analyze_captions')
    parser_analyze_captions.add_argument('archive_dir', type=Path)
    parser_analyze_captions.add_argument('lang')
    parser_analyze_captions.add_argument('--limit', type=int)

    args = parser.parse_args()

    if args.command == 'index_captions':
        index_captions(args.archive_dir, args.lang)
    elif args.command == 'analyze_captions':
        analyze_captions(args.archive_dir, args.lang, args.limit)
    else:
        raise Exception('invalid command')
