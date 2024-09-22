# for now, all this has been duplicated from backend/content.py
import re

RE_WORD_OR_BRACKETED = re.compile(r'(\[(?P<aword>[^\]]+)\]\((?P<aid>[^\)]+)\))|(\[(?P<bword>[^\]]+)\])|(?P<word>\w+)')

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
