import os
import sys
import datetime
import subprocess
import tempfile
import pprint
import warnings
from pathlib import Path

import srt
import whisper
import diff_match_patch as dmp

from ja import JapaneseAnalyzer

FORCE_BREAK_TIME = 2
MAX_CLIP_LENGTH = 10

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
        cmdline += ['-strict', '-2', '-acodec', 'aac', '-vcodec', 'h264', '-f', 'mp4']
    elif out_fn.endswith('.webm'):
        cmdline += ['-acodec', 'libvorbis', '-vcodec', 'libvpx', '-crf', '10', '-b:v', '1M', '-f', 'webm']
    else:
        assert False, 'unknown output format'

    cmdline += ['-y', out_fn]

    with open(os.devnull, 'w') as devnull:
        subprocess.check_call(cmdline, stderr=devnull)

# a group is a list of adjacent subtitles
# returns a flat list of new groups
def divide_group(group):
    # print('divide_group', group)
    assert len(group) > 0

    # if below total time/character thresholds, keep group as is
    if (group[-1].end - group[0].start) < datetime.timedelta(seconds=MAX_CLIP_LENGTH):
        return [group]

    if len(group) == 1:
        assert False, 'single subtitle cue is too big to be a clip'

    # find biggest time gap
    biggest_gap = None
    biggest_gap_index = None
    for i in range(len(group)-1):
        gap = group[i+1].start - group[i].end
        if (gap.total_seconds() > 0) and ((biggest_gap is None) or (gap > biggest_gap)):
            biggest_gap = gap
            biggest_gap_index = i
    if biggest_gap is not None:
        # divide at biggest gap
        # print('time split, biggest gap is', biggest_gap)
        splits = [group[:biggest_gap_index+1], group[biggest_gap_index+1:]]
    else:
        # there are no time gaps, so divide as evenly as possible by character counts
        print('BEGIN NOGAP', 'duration', (group[-1].end - group[0].start).total_seconds(), 'SUBS:')
        for sub in group:
            print('--')
            print(sub.content)
        print('--')
        print('END NOGAP')
        print()
        print()

        total_chars = sum(len(sub.content) for sub in group)
        half_chars = 0.5*total_chars
        closest_chars = None
        closest_chars_index = None
        for i in range(len(group)-1):
            chars = sum(len(sub.content) for sub in group[:i+1])
            if (closest_chars is None) or (abs(chars - half_chars) < abs(closest_chars - half_chars)):
                closest_chars = chars
                closest_chars_index = i
        # print('char split, closest fraction is', closest_chars)
        splits = [group[:closest_chars_index+1], group[closest_chars_index+1:]]

    # recursively divide each split
    result = []
    for split in splits:
        result.extend(divide_group(split))
    return result

def text_similarity(analyzer, text_a, text_b):
    tokenstr_a = analyzer.make_tokenstr(text_a)
    tokenstr_b = analyzer.make_tokenstr(text_b)

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

def process(vid_fn, sub_fn, analyzer):
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

            if not clean_text:
                print('SKIPPING EMPTY SUBTITLE')
                print()
                continue

            print()
        cleaned_subs.append(srt.Subtitle(sub.index, sub.start, sub.end, clean_text))

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

            for clip_subs in divide_group(group):
                clip_start = clip_subs[0].start
                clip_end = clip_subs[-1].end
                dur = clip_end - clip_start
                print('BEGIN CLIP', 'duration', dur.total_seconds())
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

                human_text = '\n'.join(analyzer.clean_text(sub.content) for sub in clip_subs)
                asr_text = whisper_result['text']

                print('CLEANED HUMAN TEXT:')
                print(human_text)
                print('ASR TEXT:', asr_text)

                sim = text_similarity(analyzer, human_text, asr_text)
                sims.append(sim)
                print('SIMILARITY:', sim)

                clip_fn = os.path.join(OUTDIR, f'{clip_count:04d}.mp4')
                extract_video(vid_fn, clip_start, clip_end, clip_fn)
                print('CLIP FILE:', clip_fn)

                print('END CLIP')
                print()
                print()

                clip_count += 1
    except KeyboardInterrupt:
        print('INTERRUPTED')

    print('average similarity:', sum(sims) / len(sims))
    for thresh in [0.9, 0.8, 0.5]:
        print(f'similarity above {thresh}:', sum(1 for sim in sims if sim > thresh) / len(sims))

BCP_ALT_SUB_CODES = {
    'ja': ['jpn', 'jp'],
}

def find_matching_subfile(vid_fn, bcp):
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
                if (not sub_code) or (sub_code.lower() in allow_codes):
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
    sub_fn = find_matching_subfile(vid_fn, bcp)
    if sub_fn is None:
        print('could not find matching subtitle file')
        sys.exit(1)
    print('found subtitle file:', sub_fn)

    print('loading Whisper model...')
    whisper_model = whisper.load_model('large-v3')
    print('done')

    ja_analyzer = JapaneseAnalyzer()
    process(vid_fn, sub_fn, ja_analyzer)
