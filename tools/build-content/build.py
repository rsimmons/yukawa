import argparse
import tempfile
import os
import random
import string
import hashlib
import json
import glob

import yaml
from PIL import Image, ImageOps
from elevenlabs import save
from elevenlabs.client import ElevenLabs

from anno import parse_annotated_text, plain_text_from_annotated_text

ELEVEN_MODEL = 'eleven_multilingual_v2'

eleven_client = client = ElevenLabs()

VISUALS_WIDTH = 854
VISUALS_HEIGHT = 480
VISUALS_WIDTH_HALF = VISUALS_WIDTH // 2
VISUALS_HEIGHT_HALF = VISUALS_HEIGHT // 2

class Object(object):
    pass

def generate_id():
    return ''.join(random.choice(string.ascii_letters+string.digits) for i in range(12))

def prepare_image(src_path, output_width, output_height, output_dir):
    with tempfile.TemporaryDirectory() as tmpdirn:
        assert os.path.exists(src_path), f'{src_path} does not exist'
        image = Image.open(src_path)
        tmp_image_path = f'{tmpdirn}/{generate_id()}.jpg'
        ImageOps.pad(image, (output_width, output_height), color=(0, 0, 0)).save(tmp_image_path, 'JPEG')

        # compute hash of image file
        with open(tmp_image_path, 'rb') as f:
            image_contents = f.read()
            image_hash = hashlib.md5(image_contents).hexdigest()

        # move image to output_media_dir with filename that includes special prefix and contents hash
        output_image_fn = f'synthimg-{image_hash}.jpg'
        output_image_path = f'{output_dir}/{output_image_fn}'
        os.rename(tmp_image_path, output_image_path)

    return output_image_fn

# check if we need to generate TTS audio or already have cached, using hash of specially formatted key string
def generate_audios(plaintext, voices_map, output_dir):
    audio_fns = {}
    for voice_id, voice_name in voices_map.items():
        audio_key = f'tts:{ELEVEN_MODEL}:{voice_name}:{plaintext}'
        audio_key_hash = hashlib.md5(audio_key.encode()).hexdigest()
        audio_fn = f'tts-{audio_key_hash}.mp3'
        audio_path = f'{output_dir}/{audio_fn}'
        if not os.path.exists(audio_path):
            audio = client.generate(
                text=plaintext,
                voice=voice_name,
                model=ELEVEN_MODEL,
                output_format='mp3_44100_192',
            )
            save(audio, audio_path)
        # print(f'Audio for "{plaintext}" voice {voice} in {audio_fn}')
        audio_fns[voice_id] = audio_fn
    return audio_fns

def is_string_list(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)

def get_anno_atoms_set(anno):
    atoms = set()
    for span in anno:
        if 'a' in span:
            atoms.add(span['a'])
    return atoms

# returns list of image filenames
def build_image_pattern(image_pattern, manifest, purpose):
    if purpose == 'slide':
        width = VISUALS_WIDTH
        height = VISUALS_HEIGHT
    elif purpose == 'choice':
        width = VISUALS_WIDTH_HALF
        height = VISUALS_HEIGHT_HALF
    else:
        assert False, 'invalid build_image_pattern purpose'

    output_images = []
    for source_image_fn in glob.glob(image_pattern, root_dir=args.source_media_dir):
        output_image_fn = prepare_image(f'{args.source_media_dir}/{source_image_fn}', width, height, args.output_media_dir)
        output_images.append(output_image_fn)
    return output_images

def build_images(item, manifest, purpose):
    if 'image' in item:
        output_images = build_image_pattern(item['image'], manifest, purpose)
        manifest['images'] = output_images
    elif 'images' in item:
        assert is_string_list(item['images']), 'images must be list of strings'

        manifest['images'] = []
        for source_image_pattern in item['images']:
            output_images = build_image_pattern(source_image_pattern, manifest, purpose)
            manifest['images'].extend(output_images)
    else:
        assert False, 'no image or images'

def build_generator_simple(activity, context):
    def build_text_trans_audio(item, manifest, voice_slots):
        assert 'text' in item, 'text missing'
        assert isinstance(item['text'], str), 'text must be str'
        assert 'trans' in item, f'trans missing'
        assert isinstance(item['trans'], str) or is_string_list(item['trans']), 'trans not str or str list'

        voice_slot_index = item.get('voice', 0)
        assert isinstance(voice_slot_index, int), 'voice must be int'
        assert voice_slot_index >= 0, 'voice must be >= 0'
        assert voice_slot_index < len(voice_slots), 'voice must be < voice_slots'
        voice_options = voice_slots[voice_slot_index]['options']
        voice_options_map = {}
        for voice_id in voice_options:
            voice_options_map[voice_id] = context.all_voices_map[voice_id]

        anno = parse_annotated_text(item['text'])
        plaintext = plain_text_from_annotated_text(anno)

        manifest['text'] = plaintext
        manifest['trans'] = [item['trans']] if isinstance(item['trans'], str) else item
        manifest['anno'] = anno
        manifest['voice_slot_index'] = voice_slot_index

        manifest['audio'] = generate_audios(plaintext, voice_options_map, args.output_media_dir)

    def get_built_pres_atom_set(pres):
        if pres['kind'] in ['tts', 'tts_slides']:
            atom_set = set()
            for part in pres['parts']:
                atom_set.update(get_anno_atoms_set(part['anno']))
            return atom_set
        else:
            assert False, f'unknown kind {pres["kind"]}'

    def build_section(section, voice_slots):
        if section['kind'] == 'tts_slides':
            repeat = section.get('repeat', 1)
            assert isinstance(repeat, int), 'repeat must be int'
            assert 'slides' in section, 'tts_slides slides missing'
            assert isinstance(section['slides'], list), 'tts_slides slides must be list'

            section_manifest = {
                'kind': 'tts_slides',
                'repeat': repeat,
                'slides': [],
            }

            for slide in section['slides']:
                slide_manifest = {}
                build_text_trans_audio(slide, slide_manifest, voice_slots)
                build_images(slide, slide_manifest, 'slide')
                section_manifest['slides'].append(slide_manifest)

            return section_manifest
        elif section['kind'] == 'qmti':
            def build_choice(choice, correct):
                choice_manifest = {}

                build_images(choice, choice_manifest, 'choice')

                if not correct:
                    if 'fail_atoms' in choice:
                        assert context.all_atom_ids.issuperset(choice['fail_atoms']), 'unknown fail_atoms'
                    choice_manifest['fail_atoms'] = choice['fail_atoms'] if 'fail_atoms' in choice else []

                return choice_manifest

            section_manifest = {
                'kind': 'qmti',
            }

            build_text_trans_audio(section, section_manifest, voice_slots)

            on_fail = section.get('on_fail', 'report')
            assert on_fail in ['report', 'restart'], f'unknown on_fail {on_fail}'
            section_manifest['on_fail'] = on_fail

            tested_atoms = section.get('tested_atoms', [])
            assert isinstance(tested_atoms, list), 'tested_atoms must be list'
            if on_fail == 'report':
                assert len(tested_atoms) >= 1, 'tested_atoms must have at least one item'
            assert context.all_atom_ids.issuperset(tested_atoms), 'unknown tested_atoms'
            section_manifest['tested_atoms'] = tested_atoms

            assert 'correct' in section, 'qmti choices correct missing'
            assert isinstance(section['correct'], list), 'qmti choices correct must be list'
            assert 'incorrect' in section, 'qmti choices incorrect missing'
            assert isinstance(section['incorrect'], list), 'qmti choices incorrect must be list'

            section_manifest['correct'] = []
            section_manifest['incorrect'] = []

            for choice in section['correct']:
                section_manifest['correct'].append(build_choice(choice, True))
            for choice in section['incorrect']:
                section_manifest['incorrect'].append(build_choice(choice, False))

            assert len(section_manifest['correct']) >= 1, 'quiz choices correct must have at least one item'

            incorrect_image_count = 0
            for choice in section_manifest['incorrect']:
                incorrect_image_count += len(choice['images'])
            assert incorrect_image_count >= 3, 'quiz choices incorrect must have at least three images'

            return section_manifest
        else:
            assert False, f'unknown section kind {section["kind"]}'

    activity_manifest = {}

    intro_atoms = activity.get('intro_atoms', [])
    assert context.all_atom_ids.issuperset(intro_atoms), 'unknown intro_atoms'
    activity_manifest['intro_atoms'] = intro_atoms

    # generate voice_slots
    activity_voices = activity.get('voices', None)
    if isinstance(activity_voices, int):
        assert activity_voices >= 1, 'activity voices must be >= 1'
        voice_slots = [{'vary': False, 'options': context.all_voice_ids} for i in range(activity_voices)]
    elif isinstance(activity_voices, list):
        voice_slots = []
        for v in activity_voices:
            vary = v.get('vary', False)

            # TODO: possibly restrict options by gender, etc.
            options = context.all_voice_ids

            voice_slots.append({'vary': vary, 'options': options})
    else:
        assert activity_voices is None, f'activity voices must be list or None'
        voice_slots = [{'vary': False, 'options': context.all_voice_ids}]
    assert len(voice_slots) >= 1, 'activity voices must have at least one slot'
    activity_manifest['voice_slots'] = voice_slots

    assert 'sections' in activity, 'activity section missing'
    assert isinstance(activity['sections'], list), 'activity sections must be list'

    activity_manifest['sections'] = []
    for section in activity['sections']:
        section_manifest = build_section(section, voice_slots)
        activity_manifest['sections'].append(section_manifest)

    # compute some derived atom lists
    presented_atoms_set = set()
    tested_atoms_set = set()
    for section in activity_manifest['sections']:
        if section['kind'] == 'tts_slides':
            for slide in section['slides']:
                presented_atoms_set.update(get_anno_atoms_set(slide['anno']))
        elif section['kind'] == 'qmti':
            presented_atoms_set.update(section['tested_atoms'])
            tested_atoms_set.update(section['tested_atoms'])
    assert context.all_atom_ids.issuperset(presented_atoms_set), 'unknown presented_atoms'

    activity_manifest['tested_atoms'] = sorted(list(tested_atoms_set - set(intro_atoms)))

    assert tested_atoms_set.issubset(presented_atoms_set), 'tested atoms not all presented?'
    activity_manifest['req_atoms'] = sorted(list(presented_atoms_set - set(intro_atoms)))

    return activity_manifest

def build():
    manifest = {}

    with open(f'{args.meta_dir}/atoms.yaml') as f:
        source_atoms = yaml.safe_load(f)

    all_atom_ids = set()
    manifest['atoms'] = []
    for atom in source_atoms:
        for k in atom:
            assert k in ['id', 'meaning', 'notes'], f'unknown key {k} in atom {atom["id"]}'

        if atom['id'] in all_atom_ids:
            print(f'ERROR: duplicate atom id {atom["id"]}')
            assert False
        all_atom_ids.add(atom['id'])

        assert ('meaning' in atom) or ('notes' in atom), f'atom {atom["id"]} is missing meaning or notes'

        atom_manifest = {
            'id': atom['id'],
            'meaning': atom.get('meaning'),
            'notes': atom.get('notes'),
        }
        manifest['atoms'].append(atom_manifest)

    all_voice_ids = []
    all_voices_map = {}
    for (i, vn) in enumerate(args.voices.split('|')):
        vid = f'v{i}'
        all_voices_map[vid] = vn
        all_voice_ids.append(vid)

    with open(f'{args.meta_dir}/activities.yaml') as f:
        source_activities = yaml.safe_load(f)

    context = Object()
    context.all_atom_ids = all_atom_ids
    context.all_voice_ids = all_voice_ids
    context.all_voices_map = all_voices_map

    activity_manifests = []
    for activity in source_activities:
        assert 'kind' in activity, 'activity kind missing'
        activity_kind = activity['kind']
        if activity_kind == 'simple':
            activity_manifests.append(build_generator_simple(activity, context))
        else:
            assert False, f'unknown activity kind {activity_kind}'

    manifest['activities'] = activity_manifests

    with open(f'{args.meta_dir}/order.yaml') as f:
        source_order = yaml.safe_load(f)
    intro_order = []
    for item in source_order:
        if isinstance(item, str):
            assert item in all_atom_ids, f'order.yaml unknown atom id {item}'
            intro_order.append([item])
        elif isinstance(item, list):
            assert all_atom_ids.issuperset(item), f'order.yaml unknown atom id in {item}'
            intro_order.append(sorted(item))
        else:
            assert False, f'order.yaml unknown item type {item}'

    manifest['intro_order'] = intro_order

    with open(f'{args.meta_dir}/build.json', 'w') as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))

parser = argparse.ArgumentParser()
parser.add_argument('--lang', help='language code', required=True)
parser.add_argument('--meta-dir', help='source metadata', required=True)
parser.add_argument('--source-media-dir', help='source media directory', required=True)
parser.add_argument('--output-media-dir', help='output media directory', required=True)
parser.add_argument('--voices', help='|-separated list of voices to use', required=True)

args = parser.parse_args()

build()
