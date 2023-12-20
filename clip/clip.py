import os
import sys
import datetime
import subprocess
import tempfile
import pprint
import warnings
import random
import string
import json
import time
from pathlib import Path

import srt
import whisper
import diff_match_patch as dmp

from ja import JapaneseAnalyzer
from en import EnglishAnalyzer

FORCE_BREAK_TIME = 3
MAX_CLIP_LENGTH = 14 # does not include margins
IDEAL_MARGIN = 0.5 # this is also the maximum, may end up being less
MIN_AFTER_MARGIN = 0.1
SIMILARITY_THRESHOLD = 0.75

def random_id():
    # ~71 bits of entropy
    return ''.join(random.choice(string.ascii_letters+string.digits) for i in range(12))

def extract_audio(vid_fn, start_time, end_time, audio_fn):
    # extract to wav to avoid re-encoding
    cmdline = ['ffmpeg', '-ss', str(start_time.total_seconds()), '-accurate_seek', '-i', vid_fn, '-t', str((end_time - start_time).total_seconds()), '-map', '0:a:0', '-ac', '1', '-acodec', 'pcm_s16le', '-y', audio_fn]
    with open(os.devnull, 'w') as devnull:
        subprocess.check_call(cmdline, stderr=devnull)

def extract_video(vid_fn, start_time, end_time, out_fn):
    OUTPUT_WIDTH = 854
    OUTPUT_HEIGHT = 480
    cmdline = [
        'ffmpeg',
        '-ss', str(start_time.total_seconds()),
        '-accurate_seek',
        '-i', vid_fn,
        '-t', str((end_time - start_time).total_seconds()),
        # make correct width and height, padding with black in one dimension if necessary. from https://superuser.com/a/547406
        #'-vf', 'scale=(sar*iw)*min({width}/(sar*iw)\\,{height}/ih):ih*min({width}/(sar*iw)\\,{height}/ih),pad={width}:{height}:({width}-(sar*iw)*min({width}/(sar*iw)\\,{height}/ih))/2:({height}-ih*min({width}/(sar*iw)\\,{height}/ih))/2,setdar=16:9'.format(width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT),
        '-vf', 'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:-1:-1:color=black,setdar=16:9,setsar=1'.format(width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT),
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

# a group is a list of contiguous subtitles
# returns a flat list of new groups (sequences of contiguous subtitles),
# each group a dict with keys 'subs', 'margin_before', 'margin_after',
# both margins in seconds indicating how much speech-free time should be
# available before/after to extend the clip time beyond the sub times
def divide_group(subs, margin_before, margin_after):
    #print('divide_group', subs)
    assert len(subs) > 0

    # if below total time/character thresholds, keep subs as is
    if (subs[-1].end - subs[0].start) < datetime.timedelta(seconds=MAX_CLIP_LENGTH):
        #print('keeping intact')
        return [{'subs': subs, 'margin_before': margin_before, 'margin_after': margin_after}]
    #print('splitting')

    if len(subs) == 1:
        assert False, 'single subtitle cue is too big to be a clip'

    # get scores for each split point
    split_scores = [] # list of dicts with 'gap' (in seconds), 'imbalance' (float, lower better), and 'index'
    total_chars = sum(len(sub.content) for sub in subs)
    for i in range(len(subs)-1):
        # don't split if there is a "continuation arrow" (→) ending the first subtitle
        if subs[i].content.strip()[-1] in ['→', '➡', '―']:
            continue

        gap = (subs[i+1].start - subs[i].end).total_seconds()

        running_chars = sum(len(sub.content) for sub in subs[:i+1])
        imbalance = abs(running_chars - (0.5*total_chars))/total_chars

        split_scores.append({'gap': gap, 'imbalance': imbalance, 'index': i})

    # sort by biggest gap, then (if tied) lowest imbalance
    split_scores.sort(key=lambda x: (-x['gap'], x['imbalance']))
    #print('sorted split scores:', split_scores)

    best_split_index = split_scores[0]['index']
    before_split_subs = subs[:best_split_index+1]
    after_split_subs = subs[best_split_index+1:]

    # recursively divide each split
    time_between = (after_split_subs[0].start - before_split_subs[-1].end).total_seconds()
    result = []
    result.extend(divide_group(before_split_subs, margin_before, time_between))
    result.extend(divide_group(after_split_subs, time_between, margin_after))
    return result

def text_similarity(analyzer, text_a, text_b):
    tokenstr_a = analyzer.audible_tokenstr(text_a)
    tokenstr_b = analyzer.audible_tokenstr(text_b)

    dmp_obj = dmp.diff_match_patch()
    diffs = dmp_obj.diff_main(tokenstr_a, tokenstr_b, False)
    # diffs is a list of (op, text) tuples

    # print('text_a:')
    # print(text_a)
    # print('tokenstr_a:')
    # print(tokenstr_a)
    # print('text_b:')
    # print(text_b)
    # print('tokenstr_b:')
    # print(tokenstr_b)
    # print('diffs:', diffs)

    match_char_count = 0
    diff_char_count = 0
    for (op, text) in diffs:
        if op == dmp_obj.DIFF_EQUAL:
            match_char_count += len(text.strip())
        else:
            diff_char_count += len(text.strip())
    sim = match_char_count / (match_char_count + diff_char_count)

    return sim

def load_clean_subs(sub_fn, analyzer):
    with open(sub_fn, 'r', encoding='utf-8') as sub_file:
        sub_data = sub_file.read()

    subs = list(srt.parse(sub_data))

    cleaned_subs = []
    for sub in subs:
        clean_text = analyzer.clean_text(sub.content)
        if clean_text != sub.content:
            print('BEGIN CLEANED SUBTITLE:')
            print(sub.content)
            print('---')
            print(clean_text)
            print('END CLEANED SUBTITLE')
            print()

        if analyzer.skip_text(clean_text):
            print('@WARNING: SKIPPING SUBTITLE')
            print(clean_text)
            print()
            continue

        cleaned_subs.append(srt.Subtitle(sub.index, sub.start, sub.end, clean_text))

    return cleaned_subs

# find subs that sufficiently overlap the given time window
# O(n) in number of subs, I'm lazy and it's fine
def find_overlapping_subs(subs, start_time, end_time):
    OVERLAP_THRESHOLD = 0.5 # at least this fraction of the subtitle must overlap with the time window

    overlapping_subs = []
    for sub in subs:
        overlap_start = max(sub.start, start_time)
        overlap_end = min(sub.end, end_time)
        if overlap_end > overlap_start:
            overlap_seconds = (overlap_end - overlap_start).total_seconds()
            sub_seconds = (sub.end - sub.start).total_seconds()
            if (overlap_seconds/sub_seconds) >= OVERLAP_THRESHOLD:
                overlapping_subs.append(sub)

    return overlapping_subs

# trans (translation) is None or (trans_sub_fn, trans_analyzer)
def process(source_id, vid_fn, sub_fn, analyzer, trans):
    t0 = time.time()

    cleaned_subs = load_clean_subs(sub_fn, analyzer)

    cleaned_trans_subs = []
    if trans:
        (trans_sub_fn, trans_analyzer) = trans
        cleaned_trans_subs = load_clean_subs(trans_sub_fn, trans_analyzer)

    coarse_groups = []
    group = []
    prev_end = None # time the last subtitle ended
    for sub in cleaned_subs:
        if (prev_end is None) or ((sub.start - prev_end) < datetime.timedelta(seconds=FORCE_BREAK_TIME)):
            group.append(sub)
        else:
            coarse_groups.append(group)
            group = [sub]
        prev_end = sub.end
    if group:
        coarse_groups.append(group)

    OUTDIR = './output'
    Path(OUTDIR).mkdir(parents=True, exist_ok=True)
    sims = []
    clip_count = 0
    try:
        for group in coarse_groups:
            # print('BEGIN COARSE GROUP')
            # for sub in group:
            #     print('--')
            #     print(sub.content)
            # print('--')
            # print('END COARSE GROUP')
            # print()
            # print()

            for clip_group in divide_group(group, FORCE_BREAK_TIME, FORCE_BREAK_TIME):
                clip_subs = clip_group['subs']

                SAFETY_MARGIN = 0.1 # to make sure we don't get speech from another subtitle
                margin_before = min(IDEAL_MARGIN, max(clip_group['margin_before']-SAFETY_MARGIN, 0))
                margin_after = max(min(IDEAL_MARGIN, max(clip_group['margin_after']-SAFETY_MARGIN, 0)), MIN_AFTER_MARGIN)

                clip_start = clip_subs[0].start - datetime.timedelta(seconds=margin_before)
                clip_end = clip_subs[-1].end + datetime.timedelta(seconds=margin_after)
                dur = clip_end - clip_start

                print('BEGIN CLIP', 'from', clip_start, 'to', clip_end, 'duration', dur.total_seconds())
                print('SUBS')
                print('--')
                for sub in clip_subs:
                    print(sub.content)
                    print('--')

                with tempfile.NamedTemporaryFile(suffix='.wav', dir='.') as audio_file:
                    audio_fn = audio_file.name
                    extract_audio(vid_fn, clip_start, clip_end, audio_fn)
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', 'FP16 is not supported on CPU; using FP32 instead')
                        whisper_result = whisper_model.transcribe(audio_fn, language='ja', initial_prompt='映画の字幕です。')
                    # pprint.pprint(whisper_result)

                human_text = '\n'.join(sub.content for sub in clip_subs)
                asr_text = whisper_result['text']

                print('ASR TEXT:', asr_text)

                sim = text_similarity(analyzer, human_text, asr_text)
                sims.append(sim)
                print('SIMILARITY:', sim)

                if sim < SIMILARITY_THRESHOLD:
                    print('@WARNING: LOW SIMILARITY, SKIPPING')
                    print()
                    print()
                    continue

                trans_subs = []
                if trans:
                    trans_subs = find_overlapping_subs(cleaned_trans_subs, clip_start, clip_end)
                    if not trans_subs:
                        print('@WARNING: NO TRANSLATION SUBS, SKIPPING')
                        print()
                        print()
                        continue

                    print('TRANSLATION SUBS')
                    print('--')
                    for sub in trans_subs:
                        print(sub.content)
                        print('--')

                #clip_fn = os.path.join(OUTDIR, f'{clip_count:04d}.mp4')
                clip_id = f'{source_id}_{random_id()}'
                clip_fn = os.path.join(OUTDIR, f'{clip_id}.mp4')

                extract_video(vid_fn, clip_start, clip_end, clip_fn)
                print('CLIP FILE:', clip_fn)

                # make clip info object
                clip_info = {}

                # these are redundant, but for sanity checking
                clip_info['clip_id'] = clip_id
                clip_info['source_id'] = source_id

                clip_info['duration'] = dur.total_seconds()

                retimed_subs = []
                for sub in clip_subs:
                    retimed_subs.append({
                        'start': (sub.start - clip_start).total_seconds(),
                        'end': (sub.end - clip_start).total_seconds(),
                        'text': sub.content,
                    })
                clip_info['subs'] = retimed_subs

                translations = []
                if trans:
                    assert trans_subs
                    retimed_trans_subs = []
                    for sub in trans_subs:
                        retimed_trans_subs.append({
                            # these get clamped to the clip duration
                            'start': max((sub.start - clip_start).total_seconds(), 0),
                            'end': min((sub.end - clip_start).total_seconds(), dur.total_seconds()),
                            'text': sub.content,
                        })
                    translations.append({
                        'lang': 'en',
                        'machine': False,
                        'subs': retimed_trans_subs,
                    })
                clip_info['translations'] = translations

                clip_info['asr_similarity'] = sim

                info_fn = os.path.join(OUTDIR, f'{clip_id}.json')
                with open(info_fn, 'w', encoding='utf-8') as info_file:
                    info_file.write(json.dumps(clip_info, indent=2, ensure_ascii=False))

                print('END CLIP')
                print()
                print()

                clip_count += 1
    except KeyboardInterrupt:
        print('INTERRUPTED')

    dt = time.time() - t0

    print(clip_count, 'clips generated in', dt, 'seconds', f'({dt/clip_count} seconds per clip)')

    print('average similarity:', sum(sims) / len(sims))
    for thresh in [0.9, SIMILARITY_THRESHOLD, 0.5]:
        print(f'similarity above {thresh}:', sum(1 for sim in sims if sim > thresh) / len(sims))

BCP_ALT_SUB_CODES = {
    'ja': ['jpn', 'jp'],
    'en': ['eng'],
}

def find_matching_subfile(vid_fn, bcp, match_uncoded):
    allow_codes = [bcp] + BCP_ALT_SUB_CODES.get(bcp, [])

    vid_dir, vid_basename = os.path.split(os.path.abspath(vid_fn))
    vid_prefix, vid_ext = os.path.splitext(vid_basename)
    assert vid_ext in ['.mp4', '.mkv', '.webm']

    potential_sub_fns = [] # list of (code, fn) tuples
    for sub_fn in os.listdir(vid_dir):
        if sub_fn.startswith(vid_prefix):
            sub_prefix, sub_ext = os.path.splitext(sub_fn)
            if sub_ext == '.srt':
                sub_mid = sub_prefix[len(vid_prefix):]
                sub_code = ''.join(c for c in sub_mid if c.isalpha())
                if (match_uncoded and (not sub_code)) or (sub_code.lower() in allow_codes):
                    potential_sub_fns.append((sub_code, sub_fn))

    if len(potential_sub_fns) == 0:
        return None
    if len(potential_sub_fns) == 1:
        return os.path.join(vid_dir, potential_sub_fns[0][1])
    else:
        assert False, 'multiple potential subtitle files found'

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: clip.py <video file>')
        sys.exit(1)

    vid_fn = sys.argv[1]
    if not os.path.exists(vid_fn):
        print('video file does not exist')
        sys.exit(1)

    bcp = 'ja'
    sub_fn = find_matching_subfile(vid_fn, bcp, match_uncoded=True)
    if sub_fn is None:
        print('could not find matching subtitle file')
        sys.exit(1)
    print('found subtitle file:', sub_fn)

    trans_sub_fn = find_matching_subfile(vid_fn, 'en', match_uncoded=False)
    trans = None
    if trans_sub_fn:
        print('found translated subtitle file:', trans_sub_fn)
        trans_analyzer = EnglishAnalyzer()
        trans = (trans_sub_fn, trans_analyzer)
    else:
        assert False, 'no translated subtitle file found'

    print('loading Whisper model...')
    whisper_model = whisper.load_model('large-v3')
    print('done')

    ja_analyzer = JapaneseAnalyzer()
    process(random_id(), vid_fn, sub_fn, ja_analyzer, trans)
