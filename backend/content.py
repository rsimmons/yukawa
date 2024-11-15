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

        # index activities by intro_atoms
        activities_by_intro_atoms = {}
        for activity in content['activities']:
            intro_atoms = activity['intro_atoms']
            if not intro_atoms:
                continue
            intro_atoms_set = frozenset(intro_atoms)
            if intro_atoms_set not in activities_by_intro_atoms:
                activities_by_intro_atoms[intro_atoms_set] = []
            activities_by_intro_atoms[intro_atoms_set].append(activity)
        content['activities_by_intro_atoms'] = activities_by_intro_atoms

        result[lang] = content

    return result

if __name__ == '__main__':
    load_prepare_content(True)
