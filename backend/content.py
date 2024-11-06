import json

LANGS = [
    'es',
]

def load_lang_content(lang):
    with open(f'resources/{lang}/build.json') as f:
        build = json.load(f)

    return build

def load_prepare_content(debug=False):
    result = {}

    for lang in LANGS:
        content = load_lang_content(lang)
        result[lang] = content

    return result

if __name__ == '__main__':
    load_prepare_content(True)
