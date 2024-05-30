import re
import yaml
from pathlib import Path

LANGS = [
    'es',
]

RE_WORD_OR_BRACKETED = re.compile(r'(\[(?P<aword>[^\]]+)\]\((?P<aid>[^\)]+)\))|(\[(?P<bword>[^\]]+)\])|(?P<word>\w+)')

class Fragment:
    def __init__(self, *, anno_text, spans, atoms, plain_text, clips, translations):
        self.anno_text = anno_text
        self.spans = spans
        self.atoms = atoms
        self.plain_text = plain_text
        self.clips = clips
        self.translations = translations

def parse_annotated_text(text):
    result = []

    idx = 0
    for hit in RE_WORD_OR_BRACKETED.finditer(text):
        word = None
        atom_id = None
        if hit.group('word'):
            word = hit.group('word')
            atom_id = word.lower()
        elif hit.group('bword'):
            word = hit.group('bword')
            atom_id = word.lower()
        elif hit.group('aword'):
            word = hit.group('aword')
            atom_id = hit.group('aid')

        assert word is not None
        assert atom_id is not None

        if hit.start() > idx:
            result.append({
                't': text[idx:hit.start()],
            })
        result.append({
            't': word,
            'a': atom_id,
        })

        idx = hit.end()

    if idx < len(text):
        result.append({
            't': text[idx:],
        })

    return result

def plain_text_from_annotated_text(annotated_text):
    return ''.join(item['t'] for item in annotated_text)

def atom_set_from_annotated_text(annotated_text):
    return set(item['a'] for item in annotated_text if 'a' in item)

def load_content(lang):
    with open(f'resources/{lang}/atoms.yaml') as f:
        raw_atoms = yaml.safe_load(f)

    atom_map = {}
    for atom in raw_atoms:
        atom_map[atom['id']] = atom

    with open(f'resources/{lang}/fragments.yaml') as f:
        raw_fragments = yaml.safe_load(f)

    frag_objs = []
    for frag in raw_fragments:
        anno_text = frag['text']
        spans = parse_annotated_text(anno_text)
        plain_text = plain_text_from_annotated_text(spans)
        atom_set = atom_set_from_annotated_text(spans)

        if len(atom_set) < 2:
            continue

        # modify fragment a bit, in-place
        assert 'trans' in frag, f'no trans for frag {anno_text}'
        if isinstance(frag['trans'], str):
            frag['trans'] = [frag['trans']]
        elif isinstance(frag['trans'], list):
            pass
        else:
            assert False

        if 'clips' not in frag:
            frag['clips'] = []
        for clip in frag['clips']:
            clip['id'] = Path(clip['file']).stem

        frag_objs.append(Fragment(anno_text=anno_text, spans=spans, atoms=atom_set, plain_text=plain_text, clips=frag['clips'], translations=frag['trans']))

    return {
        'atoms': raw_atoms,
        'atom_map': atom_map,
        'fragments': frag_objs,
    }

def validate_content(content):
    atom_ids = set()
    for atom in content['atoms']:
        if atom['id'] in atom_ids:
            print(f'ERROR: duplicate atom id {atom["id"]}')
            assert False
        atom_ids.add(atom['id'])

    frag_annotexts = set()
    for frag in content['fragments']:
        if frag.anno_text in frag_annotexts:
            print(f'ERROR: duplicate fragment text {frag.anno_text}')
            assert False
        frag_annotexts.add(frag.anno_text)

        for atom_id in frag.atoms:
            if atom_id not in atom_ids:
                print(f'ERROR: atom {atom_id} not found in atom list')
                print(frag.anno_text)
                assert False

def build_progression(content, debug):
    # compute atom frequencies across fragments
    atom_id_freq = {}
    for frag in content['fragments']:
        for atom_id in frag.atoms:
            atom_id_freq[atom_id] = atom_id_freq.get(atom_id, 0) + 1

    cumul_atom_ids = set()
    remaining_atom_ids = set(atom['id'] for atom in content['atoms'])

    remaining_fragments = set(frag for frag in content['fragments'] if frag.clips)

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

        if debug:
            print('NEXT:', ', '.join(next_atomset), 'BIGSTEP' if len(next_atomset) > 1 else '')
            for frag in next_frags_unlocked:
                print('    ', frag.plain_text)
            print()

        for next_atom_id in next_atomset:
            cumul_atom_ids.add(next_atom_id)
            remaining_atom_ids.remove(next_atom_id)
        remaining_fragments -= set(next_frags_unlocked)

    return progression

def load_prepare_content(debug=False):
    result = {}

    for lang in LANGS:
        content = load_content(lang)
        validate_content(content)
        progression = build_progression(content, debug)

        result[lang] = {
            'base': content,
            'progression': progression,
        }

    return result

if __name__ == '__main__':
    load_prepare_content(True)
