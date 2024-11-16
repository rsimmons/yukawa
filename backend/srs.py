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

def weighted_random_sample(weighted_choices, n):
    assert n <= len(weighted_choices)
    remaining_choices = list(weighted_choices)
    picked_choices = []
    for i in range(n):
        total_weight = sum(weight for (weight, choice) in remaining_choices)
        r = random.random() * total_weight
        for j, (weight, choice) in enumerate(remaining_choices):
            if r < weight:
                picked_choices.append(choice)
                remaining_choices.pop(j)
                break
            r -= weight
        else:
            assert False, 'should not get here'
    return picked_choices

def expand_section(section, chosen_voice_slots):
    def choose_voice(slot_index):
        chosen_slot = chosen_voice_slots[slot_index]
        if chosen_slot['vary']:
            return random.choice(chosen_slot['options'])
        else:
            return chosen_slot['voice']

    if section['kind'] == 'tts_slides':
        expanded_section = {
            'kind': section['kind'],
            'slides': [],
        }

        for repeat in range(section['repeat']):
            for slide in section['slides']:
                expanded_slide = {
                    'text': slide['text'],
                    'trans': slide['trans'],
                    'anno': slide['anno'],
                }

                voice = choose_voice(slide['voice_slot_index'])

                expanded_slide['audio_fn'] = slide['audio'][voice]
                expanded_slide['image_fn'] = random.choice(slide['images'])

                expanded_section['slides'].append(expanded_slide)

        return expanded_section
    elif section['kind'] == 'qmti':
        expanded_section = {
            'kind': section['kind'],
            'text': section['text'],
            'trans': section['trans'],
            'anno': section['anno'],
            'on_fail': section['on_fail'],
            'tested_atoms': section['tested_atoms'],
        }

        voice = choose_voice(section['voice_slot_index'])
        expanded_section['audio_fn'] = section['audio'][voice]

        picked_choices = []

        weighted_correct_choices = []
        for correct in section['correct']:
            assert 'images' in correct
            assert len(correct['images']) > 0
            weight = 1.0 / len(correct['images'])
            for image_fn in correct['images']:
                weighted_correct_choices.append((weight, {
                    'correct': True,
                    'image_fn': image_fn,
                }))
        picked_choices.extend(weighted_random_sample(weighted_correct_choices, 1))

        weighted_incorrect_choices = []
        for incorrect in section['incorrect']:
            assert 'images' in incorrect
            assert len(incorrect['images']) > 0
            weight = 1.0 / len(incorrect['images'])
            for image_fn in incorrect['images']:
                weighted_incorrect_choices.append((weight, {
                    'correct': False,
                    'image_fn': image_fn,
                    'fail_atoms': incorrect['fail_atoms'],
                }))
        picked_choices.extend(weighted_random_sample(weighted_incorrect_choices, 3))

        random.shuffle(picked_choices)

        expanded_section['choices'] = picked_choices

        return expanded_section
    else:
        assert False, 'unknown section kind'

def expand_activity(activity):
    chosen_voice_slots = []
    for slot in activity['voice_slots']:
        if slot['vary']:
            chosen_voice_slots.append(slot)
        else:
            chosen_voice = random.choice(slot['options'])
            chosen_voice_slots.append({
                'vary': False,
                'voice': chosen_voice,
            })

    return {
        'intro_atoms': activity['intro_atoms'],
        'req_atoms': activity['req_atoms'],
        'tested_atoms': activity['tested_atoms'],
        'sections': [expand_section(s, chosen_voice_slots) for s in activity['sections']],
    }

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
    for activity in CONTENT[lang]['activities']:
        # check if this activity tests any atoms that are due
        tested_due_count = len([ta for ta in activity['tested_atoms'] if atom_due.get(ta, 'untracked') == 'due'])
        if tested_due_count > 0:
            # check if all atoms needed by this activity are known or due for review
            if all(atom_due.get(atom_id, 'untracked') in ['due', 'not_due'] for atom_id in activity['req_atoms']):
                scored_review_activities.append({
                    'activity': activity,
                    'score': tested_due_count,
                })

    next_intro_activity = None
    for intro_atoms in CONTENT[lang]['intro_order']:
        if any(atom_due.get(a, 'untracked') in ['untracked', 'overdue'] for a in intro_atoms):
            # intro_atoms is the set of atoms that we should introduce next
            intro_atoms_set = frozenset(intro_atoms)
            intro_activities = CONTENT[lang]['activities_by_intro_atoms'].get(intro_atoms_set, [])

            for activity in intro_activities:
                # check if all atoms needed by this activity are known
                if all(atom_due.get(atom_id, 'untracked') in ['not_due'] for atom_id in activity['req_atoms']):
                    next_intro_activity = activity
                    break
            else:
                assert False, 'no intro activity found'

    random.shuffle(scored_review_activities)
    scored_review_activities.sort(key=lambda x: x['score'], reverse=True)
    best_review_activity = scored_review_activities[0]['activity'] if scored_review_activities else None

    if best_review_activity:
        srs_debug('doing review activity')
        return expand_activity(best_review_activity)
    elif next_intro_activity is not None:
        srs_debug('doing intro activity')
        return expand_activity(next_intro_activity)
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
