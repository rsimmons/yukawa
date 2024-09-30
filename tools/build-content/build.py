import argparse
import tempfile
import os
import random
import string
import hashlib
import json

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

def build_fragments(args):
    voices = args.voices.split('|')

    source_fragments_meta_path = f'{args.meta_dir}/new_fragments.yaml'

    with open(source_fragments_meta_path) as f:
        source_fragments_meta = yaml.safe_load(f)

    frags_manifest = []
    for frag in source_fragments_meta:
        assert ('text' in frag) and isinstance(frag['text'], str), 'text missing or not str'
        assert ('trans' in frag) and (isinstance(frag['trans'], str) or isinstance(frag['trans'], list)), 'trans missing or not str or list'
        assert ('images' in frag) and isinstance(frag['images'], list), 'images missing or not list'

        frag_manifest = {}

        # parse annotations from text, get plaintext
        anno = parse_annotated_text(frag['text'])
        plaintext = plain_text_from_annotated_text(anno)
        frag_manifest['plaintext'] = plaintext

        frag_manifest['audio'] = generate_audios(plaintext, voices, args.output_media_dir)

        # reformat sources images
        frag_manifest['images'] = []
        with tempfile.TemporaryDirectory() as tmpdirn:
            for source_image_fn in frag['images']:
                output_image_fn = prepare_image(f'{args.source_media_dir}/{source_image_fn}', VISUALS_WIDTH, VISUALS_HEIGHT, args.output_media_dir)
                frag_manifest['images'].append(output_image_fn)

        frags_manifest.append(frag_manifest)

    # write out fragments manifest
    with open(f'{args.meta_dir}/new_fragments.json', 'w') as f:
        f.write(json.dumps(frags_manifest))

def build_quizzes(args):
    voices = args.voices.split('|')

    source_quizzes_meta_path = f'{args.meta_dir}/quizzes.yaml'

    with open(source_quizzes_meta_path) as f:
        source_quizzes_meta = yaml.safe_load(f)

    quizzes_manifest = []
    for quiz in source_quizzes_meta:
        assert ('target_atoms' in quiz) and isinstance(quiz['target_atoms'], list), 'target_atom missing or not list'
        assert ('text' in quiz) and isinstance(quiz['text'], str), 'text missing or not str'
        assert ('trans' in quiz) and (isinstance(quiz['trans'], str) or isinstance(quiz['trans'], list)), 'trans missing or not str or list'
        assert ('choices' in quiz) and isinstance(quiz['choices'], dict), 'choices missing or not dict'
        assert ('correct' in quiz['choices']) and isinstance(quiz['choices']['correct'], list), 'choices->correct missing or not list'
        assert ('incorrect' in quiz['choices']) and isinstance(quiz['choices']['incorrect'], list), 'choices->incorrect missing or not list'
        assert len(quiz['choices']['correct']) >= 1, 'choices->correct must have at least one item'
        assert len(quiz['choices']['incorrect']) >= 3, 'choices->incorrect must have at least three items'
        for choice in quiz['choices']['correct']:
            assert ('image' in choice) and isinstance(choice['image'], str), 'choice->image missing or not str'
        for choice in quiz['choices']['incorrect']:
            assert ('image' in choice) and isinstance(choice['image'], str), 'choice->image missing or not str'

        quiz_manifest = {}

        # parse annotations from text, get plaintext
        anno = parse_annotated_text(quiz['text'])
        plaintext = plain_text_from_annotated_text(anno)
        quiz_manifest['plaintext'] = plaintext

        quiz_manifest['audio'] = generate_audios(plaintext, voices, args.output_media_dir)

        quiz_manifest['choices'] = {'correct': [], 'incorrect': []}
        for choice in quiz['choices']['correct']:
            output_image_fn = prepare_image(f'{args.source_media_dir}/{choice["image"]}', VISUALS_WIDTH_HALF, VISUALS_HEIGHT_HALF, args.output_media_dir)
            quiz_manifest['choices']['correct'].append({'image': output_image_fn})
        for choice in quiz['choices']['incorrect']:
            output_image_fn = prepare_image(f'{args.source_media_dir}/{choice["image"]}', VISUALS_WIDTH_HALF, VISUALS_HEIGHT_HALF, args.output_media_dir)
            quiz_manifest['choices']['incorrect'].append({'image': output_image_fn})

        quizzes_manifest.append(quiz_manifest)

    # write out quizzes manifest
    with open(f'{args.meta_dir}/quizzes.json', 'w') as f:
        f.write(json.dumps(quizzes_manifest))

parser = argparse.ArgumentParser()
parser.add_argument('--lang', help='language code', required=True)
parser.add_argument('--meta-dir', help='source and output metadata', required=True)
parser.add_argument('--source-media-dir', help='source media directory', required=True)
parser.add_argument('--output-media-dir', help='output media directory', required=True)
parser.add_argument('--voices', help='|-separated list of voices to use', required=True)

args = parser.parse_args()

build_fragments(args)
build_quizzes(args)
