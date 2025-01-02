# Structure of user SRS data object (stored as JSON)
#
# atom - map from atom id to
#   lt - last time asked (UNIX time)
#   iv - interval (in seconds)
#     interval is None if the atom needs to be introduced but is tracked for some reason
#     interval is 0 if the atom has been introduced but not yet reviewed

import random

from content import load_prepare_content
from config import Config

INIT_INTERVAL_AFTER_SUCCESS = 60
INIT_INTERVAL_AFTER_FAILURE = None # this will cause re-intro
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

def add_atoms_info(lang, activity):
    atoms_info = {}

    all_atoms = set()
    all_atoms.update(activity['intro_atoms'])
    all_atoms.update(activity['req_atoms'])
    all_atoms.update(activity['tested_atoms'])
    for atom_id in all_atoms:
        content_atom_info = CONTENT[lang]['atom_map'][atom_id]
        atoms_info[atom_id] = {
            'meaning': content_atom_info.get('meaning'),
            'notes': content_atom_info.get('notes'),
        }

    activity['atoms_info'] = atoms_info

    return activity

def atom_dueness(interval, elapsed):
    assert elapsed is not None

    if interval is None:
        # this is for atoms that have not been introduced yet, but we have a record for.
        # so "untracked" might not be the ideal name, but it's good enough for now.
        return 'untracked'

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
    for generator in CONTENT[lang]['generator_objects']:
        generated_activity_score = generator.generate_review_activity(atom_due)
        if generated_activity_score is not None:
            activity, score = generated_activity_score
            scored_review_activities.append({
                'activity': activity,
                'score': score,
            })

    def atom_can_be_introduced(atom_id):
        return ((atom_due.get(atom_id, 'untracked') in ['untracked', 'overdue']) or
            ((atom_id in srs_data['atom']) and (srs_data['atom'][atom_id]['iv'] is None)))

    next_intro_activity = None
    for intro_atoms in CONTENT[lang]['intro_order']:
        if any(atom_can_be_introduced(a) for a in intro_atoms):
            for generator in CONTENT[lang]['generator_objects']:
                activity = generator.generate_intro_activity(intro_atoms, atom_due)
                if activity is not None:
                    next_intro_activity = activity
                    break
            else:
                assert False, 'no intro activity found'
        if next_intro_activity is not None:
            break

    random.shuffle(scored_review_activities)
    scored_review_activities.sort(key=lambda x: x['score'], reverse=True)
    best_review_activity = scored_review_activities[0]['activity'] if scored_review_activities else None

    if best_review_activity:
        srs_debug('doing review activity')
        return add_atoms_info(lang, best_review_activity)
    elif next_intro_activity is not None:
        srs_debug('doing intro activity')
        return add_atoms_info(lang, next_intro_activity)
    else:
        assert False, 'no activities available'

# interval and elapsed may be None is this is the first time the atom is being asked
def update_interval(interval, elapsed, grade):
    if interval is None:
        if grade == 'introduced':
            # this is expected after the atom is first introduced
            return 0
        elif grade == 'failed':
            # this can happen if the atom is not tracked yet, but it was used as a distractor
            # in a review question and the user chose it, so it is considered "also failed"
            # (in addition to the tested atom(s))
            return None
        else:
            assert False
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
