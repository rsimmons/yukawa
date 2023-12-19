import re

from sudachipy import tokenizer, dictionary
import jaconv

from lang_util import remove_html_tags

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
    # replace halfwidth katakana with fullwidth katakana
    text = jaconv.h2z(text) # h2z only affects kana by default, which is what we want

    text = remove_html_tags(text)

    # remove various parentheses (including fullwidth variants) and their contents
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'（[^）]*）', '', text)
    text = re.sub(r'〔[^〕]*〕', '', text)
    text = re.sub(r'〈[^〉]*〉', '', text)

    text = text.strip()

    return text

# clean text in a way that helps the tokenizer
def _audible_text(text):
    # phonetic prolongation mark often confuses Sudachi
    text = text.replace('〜', '')
    text = text.replace('～', '')

    text = text.strip()

    return text

class JapaneseAnalyzer:
    bcp = 'ja'

    def __init__(self):
        self.sudachi_tokenizer_obj = dictionary.Dictionary().create()

    # Clean up any weird characters, HTML tags, parenthesized sound effects,
    # speaker names, etc that we neither want to show to users nor want to
    # include in the tokenization
    def clean_text(self, text):
        return _clean_text(text)

    # Should we skip this subtitle entirely? (e.g. because it has no audible text,
    # or only includes 'uhh')
    # Assumes text has already been cleaned
    def skip_text(self, text):
        audible_text = _audible_text(text)
        return not audible_text

    # Convert text to a string of tokens, for comparing human subtitles to
    # transcription via ASR (automatic speech recognition).
    # We remove parentheses and their contents, since those are often used to
    # indicate sounds, speaker names, etc.
    # Assumes text has already been cleaned
    def audible_tokenstr(self, text):
        audible_text = _audible_text(text)
        morphemes = self.sudachi_tokenizer_obj.tokenize(audible_text, tokenizer.Tokenizer.SplitMode.B)
        return ' '.join(_get_morpheme_token(m) for m in morphemes if not _ignore_morpheme(m))

CLEAN_TEXT_TESTS = [
    # trimmable whitespace
    (' 大丈夫 ', '大丈夫'),

    # HTML tags
    ('<i>大丈夫</i>です', '大丈夫です'),
    ('<c.ms Gothic>仕事のことだって</c.ms Gothic>', '仕事のことだって'),

    # halfwidth katakana
    ('はいはい ｶﾂ丼｡', 'はいはい カツ丼。'),

    # fullwidth parentheses
    ('（井之頭(いのがしら)五郎(ごろう)）\n何年ぶりだ？', '何年ぶりだ？'),
    ('（物が落ちる音）\n（おばあちゃん）あっ！', 'あっ！'),
    ('（おばあちゃんが力む息）', ''),
    ('（おばあちゃん）\nあっ', 'あっ'),
    ('（五郎）あっ いえ\n（店長）わざわざ すいませんねえ', 'あっ いえ\nわざわざ すいませんねえ'),

    # fullwidth parentheses and ascii parentheses
    ('（五郎）\n信玄袋(しんげんぶくろ)？', '信玄袋？'),
]

AUDIBLE_TEXT_TESTS = [
    ('は〜い', 'はい'), # unicode 12316
    ('は～い', 'はい'), # unicode 65374
]

if __name__ == '__main__':
    for (inp, target) in CLEAN_TEXT_TESTS:
        output = _clean_text(inp)
        print(repr(inp), repr(output), repr(target))
        assert output == target

    for (inp, target) in AUDIBLE_TEXT_TESTS:
        output = _audible_text(_clean_text(inp))
        print(repr(inp), repr(output), repr(target))
        assert output == target
