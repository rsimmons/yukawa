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
def generate_audios(plaintext, voices, output_dir):
    audio_fns = []
    for voice in voices:
        audio_key = f'tts:{ELEVEN_MODEL}:{voice}:{plaintext}'
        audio_key_hash = hashlib.md5(audio_key.encode()).hexdigest()
        audio_fn = f'tts-{audio_key_hash}.mp3'
        audio_path = f'{output_dir}/{audio_fn}'
        if not os.path.exists(audio_path):
            audio = client.generate(
                text=plaintext,
                voice=voice,
                model=ELEVEN_MODEL,
                output_format='mp3_44100_192',
            )
            save(audio, audio_path)
        # print(f'Audio for "{plaintext}" voice {voice} in {audio_fn}')
        audio_fns.append(audio_fn)
    return audio_fns

def is_string_list(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)

def build(args):
    def validate_atom_list(atom_list):
        assert is_string_list(atom_list), 'atom list must be list of strings'
        for atom_id in atom_list:
            assert atom_id in all_atom_ids, f'unknown atom id {atom_id}'

    def build_text_trans_audio(item, manifest):
        assert 'text' in item, 'text missing'
        assert isinstance(item['text'], str), 'text must be str'
        assert 'trans' in item, 'trans missing'
        assert isinstance(item['trans'], str) or is_string_list(item['trans']), 'trans not str or str list'

        anno = parse_annotated_text(item['text'])
        plaintext = plain_text_from_annotated_text(anno)

        manifest['text'] = plaintext
        manifest['trans'] = [item['trans']] if isinstance(item['trans'], str) else item
        manifest['anno'] = anno

        manifest['audio'] = generate_audios(plaintext, voices, args.output_media_dir)

    # returns list of image filenames
    def build_image_pattern(image_pattern, manifest, purpose):
        if purpose == 'pres':
            width = VISUALS_WIDTH
            height = VISUALS_HEIGHT
        elif purpose == 'quiz':
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

    def build_pres(pres):
        if pres['kind'] == 'rand':
            assert 'reps' in pres, 'rand reps missing'
            assert isinstance(pres['reps'], int), 'rand reps must be int'
            assert 'items' in pres, 'rand items missing'
            assert isinstance(pres['items'], list), 'rand items must be list'

            pres_manifest = {
                'kind': 'rand',
                'reps': pres['reps'],
                'items': [],
            }
            for item in pres['items']:
                item_manifest = {}

                build_text_trans_audio(item, item_manifest)

                build_images(item, item_manifest, 'pres')

                pres_manifest['items'].append(item_manifest)

            return pres_manifest
        elif pres['kind'] == 'seq':
            assert False, 'seq pres not implemented'
        elif pres['kind'] == 'audio':
            pres_manifest = {
                'kind': 'audio',
            }
            build_text_trans_audio(pres, pres_manifest)

            return pres_manifest
        else:
            assert False, f'unknown kind {pres["kind"]}'

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

    voices = args.voices.split('|')

    with open(f'{args.meta_dir}/content.yaml') as f:
        source_content = yaml.safe_load(f)

    manifest['lessons'] = []
    manifest['quizzes'] = []
    for piece in source_content:
        if piece['kind'] == 'lesson':
            assert 'intro_atoms' in piece, 'lesson intro_atoms missing'
            validate_atom_list(piece['intro_atoms'])
            assert len(piece['intro_atoms']) >= 1, 'lesson intro_atoms must have at least one item'
            if 'ignore_atoms' in piece:
                validate_atom_list(piece['ignore_atoms'])
            assert 'pres' in piece, 'lesson pres missing'

            piece_manifest = {
                'intro_atoms': piece['intro_atoms'],
                'ignore_atoms': piece['ignore_atoms'] if 'ignore_atoms' in piece else [],
            }

            piece_manifest['pres'] = build_pres(piece['pres'])

            manifest['lessons'].append(piece_manifest)
        elif piece['kind'] == 'quiz':
            def build_choice(choice, correct):
                choice_manifest = {}

                build_images(choice, choice_manifest, 'quiz')

                if not correct:
                    if 'fail_atoms' in choice:
                        validate_atom_list(choice['fail_atoms'])
                    choice_manifest['fail_atoms'] = choice['fail_atoms'] if 'fail_atoms' in choice else []

                return choice_manifest

            assert 'target_atoms' in piece, 'quiz target_atoms missing'
            assert 'pres' in piece, 'quiz pres missing'
            assert 'choices' in piece, 'quiz choices missing'

            quiz_manifest = {}

            validate_atom_list(piece['target_atoms'])
            quiz_manifest['target_atoms'] = piece['target_atoms']

            quiz_manifest['pres'] = build_pres(piece['pres'])

            assert 'correct' in piece['choices'], 'quiz choices correct missing'
            assert 'incorrect' in piece['choices'], 'quiz choices incorrect missing'
            quiz_manifest['choices'] = {'correct': [], 'incorrect': []}

            for choice in piece['choices']['correct']:
                quiz_manifest['choices']['correct'].append(build_choice(choice, True))
            for choice in piece['choices']['incorrect']:
                quiz_manifest['choices']['incorrect'].append(build_choice(choice, False))

            assert len(piece['choices']['correct']) >= 1, 'quiz choices correct must have at least one item'
            assert len(piece['choices']['incorrect']) >= 3, 'quiz choices incorrect must have at least three items'

            manifest['quizzes'].append(quiz_manifest)
        else:
            print(f'unknown kind {piece["kind"]}')

    with open(f'{args.meta_dir}/build.json', 'w') as f:
        f.write(json.dumps(manifest))

parser = argparse.ArgumentParser()
parser.add_argument('--lang', help='language code', required=True)
parser.add_argument('--meta-dir', help='source metadata', required=True)
parser.add_argument('--source-media-dir', help='source media directory', required=True)
parser.add_argument('--output-media-dir', help='output media directory', required=True)
parser.add_argument('--voices', help='|-separated list of voices to use', required=True)

args = parser.parse_args()

build(args)
