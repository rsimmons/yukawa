from sudachipy import tokenizer, dictionary

# key is (reading_form, normalized_form), value is new reading_form
MORPHEME_SUBSTS = {
    ('ネェ', 'ね'): 'ネ',
    ('ネエ', 'ね'): 'ネ',
    ('ネッ', 'ね'): 'ネ',
    ('ネェ', 'ねえ'): 'ネ',
    ('ネエ', 'ねえ'): 'ネ',
    ('ネッ', 'ねえ'): 'ネ',

    ('ワァ', 'わあ'): 'ワア',

    ('ア', 'あっ'): 'アッ',

    ('デショ', 'です'): 'デショウ',

    ('ナアニ', '何'): 'ナニ',
    ('ナァニ', '何'): 'ナニ',

    ('サッ', 'さっ'): 'サア',
}

def _ignore_morpheme(m):
    return (m.part_of_speech()[0] in ['補助記号', '空白'])

def _get_morpheme_token(m):
    subst_key = (m.reading_form(), m.normalized_form())
    if subst_key in MORPHEME_SUBSTS:
        rf = MORPHEME_SUBSTS[subst_key]
    else:
        rf = m.reading_form()

    return rf

def _clean_text(text):
    return text.replace('～', '')

class JapaneseAnalyzer:
    bcp = 'ja'

    def __init__(self):
        self.sudachi_tokenizer_obj = dictionary.Dictionary().create()

    def make_tokenstr(self, text):
        text = _clean_text(text)
        morphemes = self.sudachi_tokenizer_obj.tokenize(text, tokenizer.Tokenizer.SplitMode.B)
        return ' '.join(_get_morpheme_token(m) for m in morphemes if not _ignore_morpheme(m))
