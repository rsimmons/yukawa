import re
import yaml

# RE_WORD_OR_BRACKETED = re.compile(r'(?P<word>\w+)|(\[(?P<bword>[^\]]+)\])|(\[(?P<aword>[^\]]+)\]\((?P<aid>[^\)]+)\))')
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

def sequence_atoms(atoms, fragments):
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

    while remaining_atom_ids and remaining_fragments:
        scored_atoms = []
        for atom_id in remaining_atom_ids:
            # determine how many fragments this atom would unlock
            frags_unlocked = []
            for frag in remaining_fragments:
                if all(((a in cumul_atom_ids) or (a == atom_id)) for a in frag.atoms):
                    frags_unlocked.append(frag)

            atom_freq = atom_id_freq.get(atom_id, 0)

            score = (len(frags_unlocked), atom_freq)

            scored_atoms.append((score, atom_id, frags_unlocked))

        scored_atoms.sort(reverse=True, key=lambda x: (x[0], x[1]))

        # print('SCORE:', scored_atoms[0])
        next_atom_id = scored_atoms[0][1]
        next_frags_unlocked = scored_atoms[0][2]

        print('NEXT:', next_atom_id)
        for frag in next_frags_unlocked:
            print('    ', frag.plain_text)
        print()

        cumul_atom_ids.add(next_atom_id)
        remaining_atom_ids.remove(next_atom_id)
        remaining_fragments -= set(next_frags_unlocked)

if __name__ == '__main__':
    (atoms, fragments) = load_content('es')
    validate_content(atoms, fragments)
    sequence_atoms(atoms, fragments)
