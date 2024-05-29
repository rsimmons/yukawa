# Structure of user SRS data object (stored as JSON)
#
# atom - map from atom id to
#   lt - last time asked (UNIX time)
#   iv - interval (in seconds)
#   lg - last grade (boolean)
# clip - map from clip filename (without lang/path) to
#   lt - last time asked (UNIX time)
#   ct - count of times asked
#   lg - last full-clip understood grade ('y' | 'n' | 'm')
# clip_text - map from clip text (clean, un-annotated) to
#   lt - last time asked (UNIX time)
#   ct - count of times asked
#   lg - last full text-understood grade (after seeing clip) ('y' | 'n' | 'm')
# last_intro_time - last time new (or presumed-forgetten) atoms were introduced, or None

import time
import random

from content import load_prepare_content

INIT_INTERVAL_AFTER_SUCCESS = 60
INIT_INTERVAL_AFTER_FAILURE = 10
INTERVAL_SUCCESS_MULTIPLIER = 2
INTERVAL_FAILURE_DIVISOR = 2
MIN_INTERVAL = 10
MIN_OVERDUE_INTERVAL = 600
REL_OVERDUE_THRESHOLD = 3
MAX_INTERVAL_MULTIPLIER = 5 # the maximum interval multiplier for a successful review

print('loading content...')
CONTENT = load_prepare_content()
print('loaded content')

def init_srs_data():
    return {
        'atom': {},
        'clip': {},
        'clip_text': {},
        'last_intro_time': None,
    }

def make_question(lang, frag, clip):
    return {
        'clip_id': clip['id'],
        'clip_fn': clip['file'],
        'spans': frag.spans,
        'plain_text': frag.plain_text,
    }

def pick_question(lang, srs_data, t):
    atom_due = {}
    for atom_id, atom_data in srs_data['atom'].items():
        elapsed = t - atom_data['lt']
        rel_elapsed = elapsed / atom_data['iv']

        if (elapsed > MIN_OVERDUE_INTERVAL) and (rel_elapsed > REL_OVERDUE_THRESHOLD):
            atom_due[atom_id] = 'overdue'
        elif rel_elapsed >= 1:
            atom_due[atom_id] = 'due'
        else:
            atom_due[atom_id] = 'not_due'

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
                        },
                    })
        else:
            for frag in frags_unlocked:
                for clip in frag.clips:
                    intro_clips.append({
                        'clip': clip,
                        'frag': frag,
                    })
            break

    if (srs_data['last_intro_time'] is None) or (t - srs_data['last_intro_time'] > 60):
        intro = random.choice(intro_clips)
        return make_question(lang, intro['frag'], intro['clip'])
    else:
        review_clips.sort(key=lambda x: (-x['info']['due_count'], x['info']['last_time_text_asked'], x['info']['last_time_clip_asked']))
        review = review_clips[0]
        return make_question(lang, review['frag'], review['clip'])

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
            return min(new_interval, interval*MAX_INTERVAL_MULTIPLIER)
        else:
            return max(MIN_INTERVAL, interval / INTERVAL_FAILURE_DIVISOR)

# grade is {'clip_understood': 'y' | 'n' | 'm', 'text_understood': 'y' | 'n' | 'm', 'atoms': (map from atom id to boolean)}
def record_grade(lang, srs_data, question, grade, t):
    atom_ids = set()
    for atom in CONTENT[lang]['atoms']:
        atom_ids.add(atom['id'])

    assert grade['clip_understood'] in ['y', 'n', 'm']
    assert grade['text_understood'] in ['y', 'n', 'm']
    for atom_id, understood in grade['atoms'].items():
        assert understood in [True, False]
        assert atom_id in atom_ids

    srs_data['clip'][question['clip_id']] = {
        'lt': t,
        'ct': srs_data['clip'].get(question['clip_id'], {}).get('ct', 0) + 1,
        'lg': grade['clip_understood'],
    }

    srs_data['clip_text'][question['plain_text']] = {
        'lt': t,
        'ct': srs_data['clip_text'].get(question['plain_text'], {}).get('ct', 0) + 1,
        'lg': grade['text_understood'],
    }

    for atom_id, understood in grade['atoms'].items():
        prev_interval = None
        if atom_id in srs_data['atom']:
            prev_interval = srs_data['atom'][atom_id]['iv']
        elapsed = None
        if atom_id in srs_data['atom']:
            elapsed = t - srs_data['atom'][atom_id]['lt']

        new_interval = update_interval(prev_interval, elapsed, understood)
        print('atom before', atom_id, srs_data['atom'].get(atom_id, None))
        srs_data['atom'][atom_id] = {
            'lt': t,
            'iv': new_interval,
            'lg': understood,
        }
        print('atom after', atom_id, srs_data['atom'][atom_id])

if __name__ == '__main__':
    srs_data = init_srs_data()

    t = time.time()
    for i in range(5):
        print('PICKING QUESTION')
        q = pick_question('es', srs_data, t)
        print(q)
        print()

        atom_grades = {}
        for s in q['spans']:
            if 'a' in s:
                atom_grades[s['a']] = True

        t += 10
        print('RECORDING GRADE')
        record_grade('es', srs_data, q, {
            'clip_understood': 'y',
            'text_understood': 'y',
            'atoms': atom_grades,
        }, t)
        print()

        t += 120
