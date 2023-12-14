import os
import datetime
import subprocess
import tempfile
import pprint

import srt
import whisper
from sudachipy import tokenizer, dictionary
import diff_match_patch as dmp

sudachi_tokenizer_obj = dictionary.Dictionary().create()

print('loading Whisper model...')
whisper_model = whisper.load_model('large-v3')
print('done')

FORCE_BREAK_TIME = 2
MAX_CLIP_LENGTH = 10

def sudachi_get_morphemes(text):
    return sudachi_tokenizer_obj.tokenize(text, tokenizer.Tokenizer.SplitMode.B)

def extract_audio(vid_fn, start_time, end_time, audio_fn):
    # we have to re-encode to get precise start/end times
    # cmdline = ['ffmpeg', '-ss', str(start_time.total_seconds()), '-accurate_seek', '-i', vid_fn, '-t', str((end_time - start_time).total_seconds()), '-map', '0:a:0', '-acodec', 'aac', '-y', audio_fn]

    # extract to wav to avoid re-encoding
    cmdline = ['ffmpeg', '-ss', str(start_time.total_seconds()), '-accurate_seek', '-i', vid_fn, '-t', str((end_time - start_time).total_seconds()), '-map', '0:a:0', '-ac', '1', '-acodec', 'pcm_s16le', '-y', audio_fn]
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

MORPHEME_SUBSTS = {
    ('ネェ', 'ね'): 'ネ',
    ('ネエ', 'ね'): 'ネ',
    ('ネッ', 'ね'): 'ネ',
    ('ネェ', 'ねえ'): 'ネ',
    ('ネエ', 'ねえ'): 'ネ',
    ('ネッ', 'ねえ'): 'ネ',

    ('ワァ', 'わあ'): 'ワア',

    ('ア', 'あっ'): 'アッ',

    ('デショ', 'です'): 'デショウ',

    ('ナアニ', '何'): 'ナニ',
    ('ナァニ', '何'): 'ナニ',

    ('サッ', 'さっ'): 'サア',
}

def get_morpheme_token(m):
    subst_key = (m.reading_form(), m.normalized_form())
    if subst_key in MORPHEME_SUBSTS:
        rf = MORPHEME_SUBSTS[subst_key]
    else:
        rf = m.reading_form()

    return rf

def ignore_morpheme(m):
    return (m.part_of_speech()[0] in ['補助記号', '空白'])

def ja_make_tokenstr(text):
    text = text.replace('～', '') # phonetic prolongation mark, just messes up analysis

    morphemes = sudachi_get_morphemes(text)
    return ' '.join(get_morpheme_token(m) for m in morphemes if not ignore_morpheme(m))

def text_similarity(make_tokenstr, text_a, text_b):
    tokenstr_a = make_tokenstr(text_a)
    tokenstr_b = make_tokenstr(text_b)

    dmp_obj = dmp.diff_match_patch()
    diffs = dmp_obj.diff_main(tokenstr_a, tokenstr_b, False)
    # diffs is a list of (op, text) tuples

    print('text_a:')
    print(text_a)
    print('tokenstr_a:')
    print(tokenstr_a)
    print('text_b:')
    print(text_b)
    print('tokenstr_b:')
    print(tokenstr_b)
    print('diffs:', diffs)

    match_char_count = 0
    diff_char_count = 0
    for (op, text) in diffs:
        if op == dmp_obj.DIFF_EQUAL:
            match_char_count += len(text.strip())
        else:
            diff_char_count += len(text.strip())
    sim = match_char_count / (match_char_count + diff_char_count)

    return sim

def process(vid_fn, sub_fn):
    with open(sub_fn, 'r', encoding='utf-8') as sub_file:
        sub_data = sub_file.read()

    subs = list(srt.parse(sub_data))

    coarse_groups = []
    group = []
    prev_end = None # time the last subtitle ended
    for sub in subs:
        if (prev_end is None) or ((sub.start - prev_end) < datetime.timedelta(seconds=FORCE_BREAK_TIME)):
            group.append(sub)
        else:
            coarse_groups.append(group)
            group = [sub]
        prev_end = sub.end
    if group:
        coarse_groups.append(group)

    sims = []
    for group in coarse_groups:
        print('--------')
        for clip_subs in divide_group(group):
            clip_start = clip_subs[0].start
            clip_end = clip_subs[-1].end
            dur = clip_end - clip_start
            print('----', dur.total_seconds())
            for sub in clip_subs:
                print(sub.content.strip())
                print('--')

            with tempfile.NamedTemporaryFile(suffix='.wav', dir='.') as audio_file:
                audio_fn = audio_file.name
                extract_audio(vid_fn, clip_start, clip_end, audio_fn)
                whisper_result = whisper_model.transcribe(audio_fn, language='ja', word_timestamps=True, initial_prompt='映画の字幕です。')
                # pprint.pprint(whisper_result)

                human_text = '\n'.join(sub.content.strip() for sub in clip_subs)
                asr_text = whisper_result['text']

                sim = text_similarity(ja_make_tokenstr, human_text, asr_text)
                sims.append(sim)
                print('similarity:', sim)

                print()
                print()

    print('average similarity:', sum(sims) / len(sims))
    for thresh in [0.9, 0.8, 0.5]:
        print(f'similarity above {thresh}:', sum(1 for sim in sims if sim > thresh) / len(sims))

# TODO: don't update candidate split index if first sub ends with continuation arrow

process('SpiritedAway.mp4', 'SpiritedAway.srt')
