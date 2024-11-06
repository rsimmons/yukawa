# Structure of user SRS data object (stored as JSON)
#
# atom - map from atom id to
#   lt - last time asked (UNIX time)
#   iv - interval (in seconds)

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
INTRO_IF_FEWER_THAN_KNOWN_ATOMS = 5

print('loading content...')
CONTENT = load_prepare_content()
print('loaded content')

def srs_debug(*args):
    if Config.SRS_LOG_VERBOSE:
        print('SRS:', *args)

def init_srs_data():
    return {
        'atom': {},
    }

def expand_pres_item(item):
    result = {
        'text': item['text'],
        'trans': item['trans'],
        'anno': item['anno'],
    }
    if 'audio' in item:
        result['audio_fn'] = random.choice(item['audio'])
    if 'images' in item:
        result['image_fn'] = random.choice(item['images'])
    return result

def expand_pres(pres):
    if pres['kind'] == 'single':
        return {
            'items': [expand_pres_item(pres['item'])],
        }
    elif pres['kind'] == 'rand':
        expanded_items = []
        for i in range(pres['reps']):
            for item in pres['items']:
                expanded_items.append(expand_pres_item(item))

        return {
            'items': expanded_items,
        }
    else:
        assert False, 'unknown pres kind'

def expand_quiz_choices(choices):
    picked_choices = []

    correct_choices = []
    for correct in choices['correct']:
        assert 'images' in correct
        correct_choices.append({
            'correct': True,
            'image_fn': random.choice(correct['images']),
        })
    picked_choices.extend(random.sample(correct_choices, 1))

    incorrect_choices = []
    for incorrect in choices['incorrect']:
        assert 'images' in incorrect
        incorrect_choices.append({
            'correct': False,
            'image_fn': random.choice(incorrect['images']),
            'fail_atoms': incorrect['fail_atoms'],
        })
    picked_choices.extend(random.sample(incorrect_choices, 3))

    random.shuffle(picked_choices)

    return picked_choices

def expand_tagged_activity(activity):
    if activity['kind'] == 'lesson':
        lesson = activity['lesson']
        return {
            'kind': 'lesson',
            'intro_atoms': lesson['intro_atoms'],
            'pres': expand_pres(lesson['pres']),
        }
    elif activity['kind'] == 'quiz':
        quiz = activity['quiz']
        return {
            'kind': 'quiz',
            'target_atoms': quiz['target_atoms'],
            'pres': expand_pres(quiz['pres']),
            'choices': expand_quiz_choices(quiz['choices']),
        }
    else:
        assert False, 'unknown activity kind'

def atom_dueness(interval, elapsed):
    assert interval is not None
    assert elapsed is not None

    if interval == 0:
        # this is a special case for atoms that have been introduced but not yet reviewed
        return 'due'

    rel_elapsed = elapsed / interval
    if (elapsed > MIN_OVERDUE_INTERVAL) and (rel_elapsed > REL_OVERDUE_THRESHOLD):
        return 'overdue'
    elif rel_elapsed >= 1:
        return 'due'
    else:
        return 'not_due'

def pick_activity(lang, srs_data, t):
    t = int(t)

    srs_debug()
    srs_debug('PICKING ACTIVITY')
    # srs_debug('srs_data', srs_data)
    atom_due = {}
    srs_debug('atoms')
    atom_count_known = 0
    atom_count_tracked = 0
    for atom_id, atom_data in srs_data['atom'].items():
        elapsed = t - atom_data['lt']

        dueness = atom_dueness(atom_data['iv'], elapsed)
        atom_due[atom_id] = dueness
        if dueness in ['due', 'not_due']:
            atom_count_known += 1
        atom_count_tracked += 1

        srs_debug(' ', atom_id, dueness, 'elapsed', elapsed, 'interval', atom_data['iv'])

    scored_review_activities = [] # {'activity': ..., 'score': ...}, higher score better
    for quiz in CONTENT[lang]['quizzes']:
        # check if this quiz targets any atoms that are due
        target_due_count = len([target_atom for target_atom in quiz['target_atoms'] if atom_due.get(target_atom, 'untracked') == 'due'])
        if target_due_count > 0:
            # check if all atoms needed by this quiz are known or due for review
            if all(atom_due.get(atom_id, 'untracked') in ['due', 'not_due'] for atom_id in quiz['dep_atoms']):
                scored_review_activities.append({
                    'activity': {
                        'kind': 'quiz',
                        'quiz': quiz,
                    },
                    'score': target_due_count,
                })

    next_intro_activity = None
    for lesson in CONTENT[lang]['lessons']:
        # check if this lesson introduces any atoms that are not yet known or overdue
        if any(atom_due.get(target_atom, 'untracked') in ['untracked', 'overdue'] for target_atom in lesson['intro_atoms']):
            # check if all atoms needed by this lesson are known
            if all(atom_due.get(atom_id, 'untracked') in ['not_due'] for atom_id in lesson['dep_atoms']):
                next_intro_activity = {
                    'kind': 'lesson',
                    'lesson': lesson,
                }
                break
            else:
                srs_debug('lesson has unmet dependencies:', ' '.join(sorted(dep_atoms)))

    random.shuffle(scored_review_activities)
    scored_review_activities.sort(key=lambda x: x['score'], reverse=True)
    best_review_activity = scored_review_activities[0]['activity'] if scored_review_activities else None

    if best_review_activity:
        srs_debug('doing review activity')
        return expand_tagged_activity(best_review_activity)
    elif next_intro_activity is not None:
        srs_debug('doing intro activity')
        return expand_tagged_activity(next_intro_activity)
    else:
        assert False, 'no activities available'

# interval and elapsed may be None is this is the first time the atom is being asked
def update_interval(interval, elapsed, grade):
    if interval is None:
        assert grade == 'introduced'
        return 0
    else:
        assert elapsed is not None

        dueness = atom_dueness(interval, elapsed)
        if dueness == 'overdue' and grade == 'introduced':
            return 0

        assert grade in ['introduced', 'passed', 'failed', 'exposed', 'forgot']
        boost = (grade in ['passed', 'exposed'])

        if interval == 0:
            return INIT_INTERVAL_AFTER_SUCCESS if boost else INIT_INTERVAL_AFTER_FAILURE
        else:
            if boost:
                # this formula is unusual, but works at important points:
                # - if elapsed==interval then the new interval will be interval*INTERVAL_SUCCESS_MULTIPLIER
                # - if elapsed==0 then the interval will be unchanged
                # furthermore, we limit how much the interval can grow, in case it was asked very late and they got it right by a fluke
                new_interval = interval + (elapsed * (INTERVAL_SUCCESS_MULTIPLIER - 1))
                return int(min(new_interval, interval*MAX_INTERVAL_MULTIPLIER))
            else:
                return int(max(MIN_INTERVAL, interval / INTERVAL_FAILURE_DIVISOR))

# result is
# {
#   'atoms_introduced': [atom_id, ...],
#   'atoms_exposed': [atom_id, ...],
#   'atoms_forgot': [atom_id, ...],
#   'atoms_passed': [atom_id, ...],
#   'atoms_failed': [atom_id, ...],
# }
def report_result(lang, srs_data, result, t):
    t = int(t)

    srs_debug()
    srs_debug('REPORTING RESULT')

    atom_grades = {}
    for atom_id in result['atoms_introduced']:
        atom_grades[atom_id] = 'introduced'
    for atom_id in result['atoms_exposed']:
        atom_grades[atom_id] = 'exposed'
    for atom_id in result['atoms_forgot']:
        atom_grades[atom_id] = 'forgot'
    for atom_id in result['atoms_passed']:
        atom_grades[atom_id] = 'passed'
    for atom_id in result['atoms_failed']:
        atom_grades[atom_id] = 'failed'

    srs_debug('atom grades')
    for atom_id, success in atom_grades.items():
        srs_debug(' ', atom_id, success)

    report = {}
    for atom_id, grade in atom_grades.items():
        prev_interval = None
        if atom_id in srs_data['atom']:
            prev_interval = srs_data['atom'][atom_id]['iv']
        elapsed = None
        if atom_id in srs_data['atom']:
            elapsed = t - srs_data['atom'][atom_id]['lt']

        new_interval = update_interval(prev_interval, elapsed, grade)
        srs_data['atom'][atom_id] = {
            'lt': t,
            'iv': new_interval,
        }
        srs_debug(f'atom {atom_id} grade {grade} elapsed {elapsed} interval {prev_interval} -> {new_interval} ')
        report[atom_id] = {
            'elapsed': elapsed,
            'prev_interval': prev_interval,
            'new_interval': new_interval,
            'grade': grade,
        }

    srs_debug()

    return report
