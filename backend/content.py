import re
import yaml

RE_WORD_OR_BRACKETED = re.compile(r'(\[(?P<aword>[^\]]+)\]\((?P<aid>[^\)]+)\))|(\[(?P<bword>[^\]]+)\])|(?P<word>\w+)')

class Fragment:
    def __init__(self, text, atoms, plain_text):
        self.text = text
        self.atoms = atoms
        self.plain_text = plain_text

def load_content(lang):
    with open(f'resources/{lang}/atoms.yaml') as f:
        atoms = yaml.safe_load(f)

    with open(f'resources/{lang}/fragments.yaml') as f:
        fragments = yaml.safe_load(f)

    frag_objs = []
    for frag in fragments:
        # print(frag['text'])
        frag_atoms = set()
        for hit in RE_WORD_OR_BRACKETED.finditer(frag['text']):
            word = None
            atom_id = None
            if hit.group('word'):
                word = hit.group('word').lower()
                atom_id = word
            elif hit.group('bword'):
                word = hit.group('bword').lower()
                atom_id = word
            elif hit.group('aword'):
                word = hit.group('aword').lower()
                atom_id = hit.group('aid')

            # print(f'  {word} ({atom_id})')

            frag_atoms.add(atom_id)

        plain_text = RE_WORD_OR_BRACKETED.sub(lambda m: m.group('word') or m.group('bword') or m.group('aword'), frag['text'])

        frag_objs.append(Fragment(frag['text'], frag_atoms, plain_text))

    return (atoms, frag_objs)

def validate_content(atoms, fragments):
    atom_ids = set()
    for atom in atoms:
        if atom['id'] in atom_ids:
            print(f'ERROR: duplicate atom id {atom["id"]}')
            assert False
        atom_ids.add(atom['id'])

    frag_texts = set()
    for frag in fragments:
        if frag.text in frag_texts:
            print(f'ERROR: duplicate fragment text {frag.text}')
            assert False
        frag_texts.add(frag.text)

        for atom_id in frag.atoms:
            if atom_id not in atom_ids:
                print(f'ERROR: atom {atom_id} not found in atom list')
                print(frag.text)
                assert False

def build_progression(atoms, fragments):
    atom_map = {}
    for atom in atoms:
        atom_map[atom['id']] = atom

    # compute atom frequencies across fragments
    atom_id_freq = {}
    for frag in fragments:
        for atom_id in frag.atoms:
            atom_id_freq[atom_id] = atom_id_freq.get(atom_id, 0) + 1

    cumul_atom_ids = set()
    remaining_atom_ids = set(atom['id'] for atom in atoms)

    remaining_fragments = set(fragments)

    # items are (atoms_tuple, fragments_unlocked)
    progression = []

    while remaining_atom_ids and remaining_fragments:
        atomset_frags = {}
        for frag in remaining_fragments:
            needed_atoms = set(a for a in frag.atoms if a not in cumul_atom_ids)
            na = tuple(sorted(needed_atoms))
            atomset_frags.setdefault(na, []).append(frag)

        scored_atomsets = []
        for atomset, frags in atomset_frags.items():
            # fewer atoms is better, and more frequent atoms are better
            score = (len(atomset), -sum(atom_id_freq[a] for a in atomset))
            scored_atomsets.append((score, atomset, frags))

        scored_atomsets.sort(key=lambda x: x[0])

        # print('SCORE:', scored_atoms[0])
        next_atomset = scored_atomsets[0][1]
        next_frags_unlocked = scored_atomsets[0][2]

        progression.append((next_atomset, next_frags_unlocked))

        print('NEXT:', ', '.join(next_atomset), 'BIGSTEP' if len(next_atomset) > 1 else '')
        for frag in next_frags_unlocked:
            print('    ', frag.plain_text)
        print()

        for next_atom_id in next_atomset:
            cumul_atom_ids.add(next_atom_id)
            remaining_atom_ids.remove(next_atom_id)
        remaining_fragments -= set(next_frags_unlocked)

    return progression

if __name__ == '__main__':
    (atoms, fragments) = load_content('es')
    validate_content(atoms, fragments)
    build_progression(atoms, fragments)
