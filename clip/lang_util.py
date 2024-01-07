import unicodedata
import re
import sys

tbl = dict.fromkeys(i for i in range(sys.maxunicode) if chr(i).isspace() or unicodedata.category(chr(i)).startswith('P') or unicodedata.category(chr(i)).startswith('S'))

def remove_spaces_punctuation(text):
    return text.translate(tbl)

def count_meaty_chars(text):
    return len(remove_spaces_punctuation(text))

def remove_html_tags(text):
    return re.sub(r'<[^>]*>', '', text)
