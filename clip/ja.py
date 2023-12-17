import re

from sudachipy import tokenizer, dictionary
import jaconv

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

# clean text so as represent spoken language, removing things like descriptions
# of sounds, speaker names, etc.
def _user_clean_text(text):
    # replace halfwidth katakana with fullwidth katakana
    text = jaconv.h2z(text) # h2z only affects kana by default, which is what we want

    # remove various parentheses (including fullwidth variants) and their contents
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'（[^）]*）', '', text)
    text = re.sub(r'〔[^〕]*〕', '', text)
    text = re.sub(r'〈[^〉]*〉', '', text)
    text = text.strip()
    return text

# clean text in a way that helps the tokenizer
def _tokenization_clean_text(text):
    text = text.replace('～', '') # phonetic prolongation mark

    return text

class JapaneseAnalyzer:
    bcp = 'ja'

    def __init__(self):
        self.sudachi_tokenizer_obj = dictionary.Dictionary().create()

    def clean_text(self, text):
        return _user_clean_text(text)

    def make_tokenstr(self, text):
        text = _tokenization_clean_text(text)
        morphemes = self.sudachi_tokenizer_obj.tokenize(text, tokenizer.Tokenizer.SplitMode.B)
        return ' '.join(_get_morpheme_token(m) for m in morphemes if not _ignore_morpheme(m))

USER_CLEANUP_TESTS = [
    # fullwidth parentheses
    ('（井之頭(いのがしら)五郎(ごろう)）\n何年ぶりだ？', '何年ぶりだ？'),
    ('（物が落ちる音）\n（おばあちゃん）あっ！', 'あっ！'),
    ('（おばあちゃんが力む息）', ''),
    ('（おばあちゃん）\nあっ', 'あっ'),
    ('（五郎）あっ いえ\n（店長）わざわざ すいませんねえ', 'あっ いえ\nわざわざ すいませんねえ'),

    ('（五郎）\n信玄袋(しんげんぶくろ)？', '信玄袋？'), # fullwidth parentheses and ascii parentheses
]

if __name__ == '__main__':
    for (text, clean_text) in USER_CLEANUP_TESTS:
        output = _user_clean_text(text)
        print(repr(text), repr(output), repr(clean_text))
        assert output == clean_text
