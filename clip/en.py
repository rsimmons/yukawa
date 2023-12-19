import re

from lang_util import remove_html_tags

def any_alphanum(text):
    for c in text:
        if c.isalnum():
            return True
    return False

def _clean_text(text):
    text = remove_html_tags(text)

    # remove brackets
    text = re.sub(r'\[[^\]]*\]', '', text)

    text = text.strip()

    return text

def _skip_text(text):
    if not any_alphanum(text):
        return True

    return False

class EnglishAnalyzer:
    bcp = 'en'

    def __init__(self):
        pass

    # Clean up any weird characters, HTML tags, parenthesized sound effects,
    # speaker names, etc that we neither want to show to users nor want to
    # include in the tokenization
    def clean_text(self, text):
        return _clean_text(text)

    # Should we skip this subtitle entirely? (e.g. because it has no audible text,
    # or only includes 'uhh')
    # Assumes text has already been cleaned
    def skip_text(self, text):
        return _skip_text(text)

    # Convert text to a string of tokens, for comparing human subtitles to
    # transcription via ASR (automatic speech recognition).
    # We remove parentheses and their contents, since those are often used to
    # indicate sounds, speaker names, etc.
    # Assumes text has already been cleaned
    def audible_tokenstr(self, text):
        assert False, 'not implemented'

CLEAN_TEXT_TESTS = [
    # trimmable whitespace
    (' Nice! ', 'Nice!'),

    # HTML
    ('<i>Wow</i>', 'Wow'),

    # brackets
    ('-Oh, you\'re still here.\n-[Kuronuma] Mmm.', '-Oh, you\'re still here.\n- Mmm.'),
]

SKIP_TEXT_TESTS = [
    ('-[gentle music playing]\n-[footsteps approaching]', True),
    ('-Oh, you\'re still here.\n-[Kuronuma] Mmm.', False),
]

if __name__ == '__main__':
    for (inp, target) in CLEAN_TEXT_TESTS:
        output = _clean_text(inp)
        print(repr(inp), repr(output), repr(target))
        assert output == target

    for (inp, target) in SKIP_TEXT_TESTS:
        output = _skip_text(_clean_text(inp))
        print(repr(inp), repr(output), repr(target))
        assert output == target
