import random

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

def get_anno_atoms_set(anno):
    atoms = set()
    for span in anno:
        if 'a' in span:
            atoms.add(span['a'])
    return atoms

class SimpleGenerator:
    def __init__(self, spec):
        self.spec = spec

    def _expand_section(self, section, chosen_voice_slots):
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

    def _expand_activity(self):
        chosen_voice_slots = []
        for slot in self.spec['voice_slots']:
            if slot['vary']:
                chosen_voice_slots.append(slot)
            else:
                chosen_voice = random.choice(slot['options'])
                chosen_voice_slots.append({
                    'vary': False,
                    'voice': chosen_voice,
                })

        return {
            'intro_atoms': self.spec['intro_atoms'],
            'req_atoms': self.spec['req_atoms'],
            'tested_atoms': self.spec['tested_atoms'],
            'sections': [self._expand_section(s, chosen_voice_slots) for s in self.spec['sections']],
        }

    def generate_intro_activity(self, intro_atoms, atom_due):
        if set(intro_atoms) == set(self.spec['intro_atoms']):
            return self._expand_activity()

    def generate_review_activity(self, atom_due):
        # check if this activity tests any atoms that are due
        tested_due_count = len([ta for ta in self.spec['tested_atoms'] if atom_due.get(ta, 'untracked') == 'due'])
        if tested_due_count > 0:
            # check if all atoms needed by this activity are known or due for review
            if all(atom_due.get(atom_id, 'untracked') in ['due', 'not_due'] for atom_id in self.spec['req_atoms']):
                return (self._expand_activity(), tested_due_count)

class PoolGenerator:
    def __init__(self, spec):
        self.spec = spec

    def generate_intro_activity(self, intro_atoms, atom_due):
        if not self.spec['provide_intros']:
            return None

        for item in self.spec['items']:
            item_atoms = get_anno_atoms_set(item['anno'])

            # are all the atoms we want to introduce in this item?
            item_covers_intros = all(atom_id in item_atoms for atom_id in intro_atoms)

            # are the requirements to use this item as an intro met, i.e. are all atoms appearing in this item either known or being introduced?
            item_reqs_met = all((atom_id in intro_atoms) or (atom_due.get(atom_id, 'untracked') == 'not_due') for atom_id in item_atoms)

            if item_covers_intros and item_reqs_met:
                activity = {}

                activity['intro_atoms'] = intro_atoms
                activity['req_atoms'] = []
                activity['tested_atoms'] = []

                activity['sections'] = []

                slides_section = {
                    'kind': 'tts_slides',
                    'slides': [],
                }

                rep = min(3, len(item['images_full']))

                sampled_images = random.sample(item['images_full'], rep)
                sampled_audios = random.sample(list(item['audio'].values()), rep)

                for i, (audio_fn, image_fn) in enumerate(zip(sampled_audios, sampled_images)):
                    slide = {
                        'text': item['text'],
                        'trans': item['trans'],
                        'anno': item['anno'],
                        'audio_fn': audio_fn,
                        'image_fn': image_fn,
                    }
                    slides_section['slides'].append(slide)

                activity['sections'].append(slides_section)

                return activity

        return None

    def generate_review_activity(self, atom_due):
        candidates = [] # list of (score, activity)
        for item in self.spec['items']:
            # calculate how many due atoms would be tested by this item
            item_atoms = get_anno_atoms_set(item['anno'])
            assert len(item_atoms) == 1
            item_tested_atoms = item_atoms
            item_req_atoms = set()
            tested_due_count = len([ta for ta in item_tested_atoms if atom_due.get(ta, 'untracked') == 'due'])
            if tested_due_count > 0:
                # check if all atoms needed by this activity are known or due for review
                if all(atom_due.get(atom_id, 'untracked') in ['due', 'not_due'] for atom_id in item_req_atoms):
                    activity = {}

                    activity['intro_atoms'] = []
                    activity['req_atoms'] = []
                    activity['tested_atoms'] = list(item_tested_atoms)

                    activity['sections'] = []

                    qmti_section = {
                        'kind': 'qmti',
                        'text': item['text'],
                        'trans': item['trans'],
                        'anno': item['anno'],
                        'tested_atoms': list(item_tested_atoms),
                        'audio_fn': random.choice(list(item['audio'].values())),
                    }

                    picked_choices = []

                    picked_choices.append({
                        'correct': True,
                        'image_fn': random.choice(item['images_choice']),
                    })

                    other_items = [i for i in self.spec['items'] if i != item]
                    scored_other_items = []
                    for other_item in other_items:
                        other_item_atoms = get_anno_atoms_set(other_item['anno'])
                        assert len(other_item_atoms) == 1
                        other_item_atom = next(iter(other_item_atoms))
                        other_item_due = atom_due.get(other_item_atom, 'untracked')
                        if other_item_due == 'untracked':
                            score = 4
                        elif other_item_due == 'overdue':
                            score = 3
                        elif other_item_due == 'due':
                            score = 2
                        elif other_item_due == 'not_due':
                            score = 1
                        else:
                            score = 0
                        scored_other_items.append((score, other_item))
                    random.shuffle(scored_other_items)
                    scored_other_items.sort(reverse=True, key=lambda x: x[0])
                    assert len(scored_other_items) >= 3
                    for score, other_item in scored_other_items[:3]:
                        picked_choices.append({
                            'correct': False,
                            'image_fn': random.choice(other_item['images_choice']),
                            'fail_atoms': list(get_anno_atoms_set(other_item['anno'])),
                        })

                    random.shuffle(picked_choices)

                    qmti_section['choices'] = picked_choices

                    activity['sections'].append(qmti_section)

                    candidates.append((tested_due_count, activity))

        candidates.sort(reverse=True, key=lambda x: x[0])

        if candidates:
            return (candidates[0][1], candidates[0][0])
        else:
            return None

GENERATOR_MAP = {
    'simple': SimpleGenerator,
    'pool': PoolGenerator,
}

def construct_generator(spec):
    return GENERATOR_MAP[spec['kind']](spec)
