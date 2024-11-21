import json
from gen import construct_generator

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

        content['generator_objects'] = []
        for generator_spec in content['activities']:
            content['generator_objects'].append(construct_generator(generator_spec))

        result[lang] = content

    return result

if __name__ == '__main__':
    load_prepare_content(True)
