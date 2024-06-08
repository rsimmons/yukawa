# Structure of user SRS data object (stored as JSON)
#
# atom - map from atom id to
#   lt - last time asked (UNIX time)
#   iv - interval (in seconds)
#   lg - last grade (boolean)
# clip - map from clip filename (without lang/path) to
#   lt - last time asked (UNIX time)
#   ct - count of times asked
#   lg - last clip heard-correctly grade ('y' | 'n' | 'm')
# clip_text - map from clip text (clean, un-annotated) to
#   lt - last time asked (UNIX time)
#   ct - count of times asked
#   lg - last clip understood-correctly grade ('y' | 'n' | 'm')
# last_intro_time - last time new (or presumed-forgetten) atoms were introduced, or None

import time
import random

from content import load_prepare_content
from config import Config

INIT_INTERVAL_AFTER_SUCCESS = 60
INIT_INTERVAL_AFTER_FAILURE = 10
INTERVAL_SUCCESS_MULTIPLIER = 2
INTERVAL_FAILURE_DIVISOR = 2
MIN_INTERVAL = 10
MIN_OVERDUE_INTERVAL = 600
REL_OVERDUE_THRESHOLD = 3
MAX_INTERVAL_MULTIPLIER = 5 # the maximum interval multiplier for a successful review
MIN_INTRO_DELAY = 60

print('loading content...')
CONTENT = load_prepare_content()
print('loaded content')

def srs_debug(*args):
    if Config.SRS_LOG_VERBOSE:
        print('SRS:', *args)

def init_srs_data():
    return {
        'atom': {},
        'clip': {},
        'clip_text': {},
        'last_intro_time': None,
    }

def make_question(lang, frag, clip):
    # get atom meanings
    atom_info = {}
    for span in frag.spans:
        if 'a' in span:
            atom_id = span['a']
            if atom_id not in atom_info:
                content_atom_info = CONTENT[lang]['base']['atom_map'][atom_id]
                atom_info[atom_id] = {
                    'meaning': content_atom_info.get('meaning'),
                    'notes': content_atom_info.get('notes'),
                }

    question = {
        'clip_id': clip['id'],
        'clip_fn': clip['file'],
        'spans': frag.spans,
        'plain_text': frag.plain_text,
        'translations': frag.translations,
        'notes': frag.notes,
        'atom_info': atom_info,
    }

    srs_debug('question')
    srs_debug('  clip_id:', question['clip_id'])
    srs_debug('  plain_text:', question['plain_text'])
    srs_debug('  atoms:', ' '.join(sorted(set(s['a'] for s in question['spans'] if 'a' in s))))
    srs_debug()

    return question

def pick_question(lang, srs_data, t):
    t = int(t)

    srs_debug()
    srs_debug('PICKING QUESTION')
    # srs_debug('srs_data', srs_data)
    atom_due = {}
    srs_debug('atoms')
    for atom_id, atom_data in srs_data['atom'].items():
        elapsed = t - atom_data['lt']
        rel_elapsed = elapsed / atom_data['iv']

        if (elapsed > MIN_OVERDUE_INTERVAL) and (rel_elapsed > REL_OVERDUE_THRESHOLD):
            atom_due[atom_id] = 'overdue'
        elif rel_elapsed >= 1:
            atom_due[atom_id] = 'due'
        else:
            atom_due[atom_id] = 'not_due'

        srs_debug(' ', atom_id, atom_due[atom_id], 'elapsed', elapsed, 'interval', atom_data['iv'])

    review_clips = [] # {'clip': ..., 'frag': ..., 'info': ...} for clips that would not introduce new/forgotten atoms
    intro_clips = [] # {'clip': ..., 'frag': ...} for clips that would introduce new/forgotten atoms
    for (atom_set, frags_unlocked) in CONTENT[lang]['progression']:
        if all(atom_due.get(atom_id, 'untracked') in ['due', 'not_due'] for atom_id in atom_set):
            for frag in frags_unlocked:
                # gather info needed to score this fragment
                due_count = 0
                for atom_id in frag.atoms:
                    due_status = atom_due.get(atom_id, 'untracked')
                    assert not (due_status in ['overdue', 'untracked'])
                    if due_status == 'due':
                        due_count += 1

                last_time_text_asked = 0
                if frag.plain_text in srs_data['clip_text']:
                    last_time_text_asked = srs_data['clip_text'][frag.plain_text]['lt']

                for clip in frag.clips:
                    clip_id = clip['id']
                    last_time_clip_asked = 0
                    if clip_id in srs_data['clip']:
                        last_time_clip_asked = srs_data['clip'][clip_id]['lt']

                    review_clips.append({
                        'clip': clip,
                        'frag': frag,
                        'info': {
                            'due_count': due_count,
                            'last_time_clip_asked': last_time_clip_asked,
                            'last_time_text_asked': last_time_text_asked,
                        },
                    })
        else:
            srs_debug('frontier fragments have atom set:', ' '.join(sorted(atom_set)))
            for frag in frags_unlocked:
                for clip in frag.clips:
                    intro_clips.append({
                        'clip': clip,
                        'frag': frag,
                    })
            break

    review_clips.sort(key=lambda x: (-x['info']['due_count'], x['info']['last_time_text_asked'], x['info']['last_time_clip_asked']))
    best_review_clip = review_clips[0] if review_clips else None
    last_intro_time = srs_data['last_intro_time']

    if best_review_clip and (best_review_clip['info']['due_count'] > 0):
        srs_debug('there are clips with due atoms, do review')
        return make_question(lang, best_review_clip['frag'], best_review_clip['clip'])
    elif intro_clips and ((last_intro_time is None) or ((t - last_intro_time) > MIN_INTRO_DELAY)):
        srs_debug('there are no clips with due atoms, and no recent intro, so do intro')
        intro = random.choice(intro_clips)
        return make_question(lang, intro['frag'], intro['clip'])
    else:
        srs_debug('there are no clips with due atoms, and we cannot do an intro, so do review')
        assert best_review_clip is not None
        return make_question(lang, best_review_clip['frag'], best_review_clip['clip'])

# interval and elapsed may be None is this is the first time the atom is being asked
def update_interval(interval, elapsed, grade):
    if interval is None:
        return INIT_INTERVAL_AFTER_SUCCESS if grade else INIT_INTERVAL_AFTER_FAILURE
    else:
        if grade:
            # this formula is unusual, but works at important points:
            # - if elapsed==interval then the new interval will be interval*INTERVAL_SUCCESS_MULTIPLIER
            # - if elapsed==0 then the interval will be unchanged
            # furthermore, we limit how much the interval can grow, in case it was asked very late and they got it right by a fluke
            new_interval = interval + (elapsed * (INTERVAL_SUCCESS_MULTIPLIER - 1))
            return int(min(new_interval, interval*MAX_INTERVAL_MULTIPLIER))
        else:
            return int(max(MIN_INTERVAL, interval / INTERVAL_FAILURE_DIVISOR))

# grade is {'heard': 'y' | 'n' | 'm', 'understood': 'y' | 'n' | 'm', 'atoms_failed': (array of atom_ids)}
def record_grades(lang, srs_data, clip_id, grades, t):
    t = int(t)

    srs_debug()
    srs_debug('RECORDING GRADES')
    frag = CONTENT[lang]['base']['clip_id_to_frag'][clip_id]
    assert frag is not None

    heard = grades['heard']
    assert heard in ['y', 'n', 'm']

    understood = grades['understood']
    assert understood in ['y', 'n', 'm']

    atom_grades = {atom_id: True for atom_id in frag.atoms}
    for atom_id in grades['atoms_failed']:
        assert atom_id in frag.atoms
        atom_grades[atom_id] = False
    srs_debug('atom grades')
    for atom_id, success in atom_grades.items():
        srs_debug(' ', atom_id, success)

    srs_data['clip'][clip_id] = {
        'lt': t,
        'ct': srs_data['clip'].get(clip_id, {}).get('ct', 0) + 1,
        'lg': grades['heard'],
    }

    plain_text = frag.plain_text
    srs_data['clip_text'][plain_text] = {
        'lt': t,
        'ct': srs_data['clip_text'].get(plain_text, {}).get('ct', 0) + 1,
        'lg': grades['understood'],
    }

    for atom_id, understood in atom_grades.items():
        prev_interval = None
        if atom_id in srs_data['atom']:
            prev_interval = srs_data['atom'][atom_id]['iv']
        elapsed = None
        if atom_id in srs_data['atom']:
            elapsed = t - srs_data['atom'][atom_id]['lt']

        new_interval = update_interval(prev_interval, elapsed, understood)
        srs_data['atom'][atom_id] = {
            'lt': t,
            'iv': new_interval,
            'lg': understood,
        }
        srs_debug(f'atom {atom_id} grade {understood} elapsed {elapsed} interval {prev_interval} -> {new_interval} ')

    srs_debug()

if __name__ == '__main__':
    srs_data = init_srs_data()

    t = time.time()
    for i in range(5):
        q = pick_question('es', srs_data, t)

        t += 10
        record_grades('es', srs_data, q['clip_id'], {
            'heard': 'y',
            'understood': 'y',
            'atoms_failed': [],
        }, t)

        t += 120
