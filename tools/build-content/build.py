import argparse
import tempfile
import os
import random
import string
import hashlib
from mutagen.mp3 import MP3
from moviepy.editor import ImageClip, AudioClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

import yaml
from PIL import Image, ImageOps
from elevenlabs import save
from elevenlabs.client import ElevenLabs

from anno import parse_annotated_text, plain_text_from_annotated_text

ELEVEN_VOICE = 'Martin Osborne 2'
ELEVEN_MODEL = 'eleven_multilingual_v2'

eleven_client = client = ElevenLabs()

VIDEO_WIDTH = 854
VIDEO_HEIGHT = 480
AUDIO_PADDING = 1.5 # how long to show image before+after audio

def generate_id():
    return ''.join(random.choice(string.ascii_letters+string.digits) for i in range(12))

def build(args):
    with open(args.source_meta) as f:
        source_meta = yaml.safe_load(f)

    for elem in source_meta:
        if elem['kind'] == 'clip':
            assert 'seq' in elem, 'seq missing'
            assert isinstance(elem['seq'], list), 'seq not list'

            scene_components = [] # each with keys image_path, audio_path, audio_dur

            with tempfile.TemporaryDirectory() as tmpdirn:
                for scene in elem['seq']:
                    assert 'visual' in scene, 'visual missing'
                    assert isinstance(scene['visual'], str), 'visual not str'
                    assert 'text' in scene, 'text missing'
                    assert isinstance(scene['text'], str), 'text not str'
                    assert 'trans' in scene, 'translation missing'
                    assert isinstance(scene['trans'], str) or isinstance(scene['trans'], list), 'translation not str or list'

                    # resize source image to new png in tempdir
                    image_fn = scene['visual']
                    assert image_fn.endswith('.png'), f'expected .png, got {image_fn}'
                    image = Image.open(f'{args.source_media_dir}/{image_fn}')
                    image_path = f'{tmpdirn}/{image_fn}'
                    ImageOps.pad(image, (VIDEO_WIDTH, VIDEO_HEIGHT), color=(0, 0, 0)).save(image_path, 'PNG')

                    # parse annotations from text, get plaintext
                    anno = parse_annotated_text(scene['text'])
                    plaintext = plain_text_from_annotated_text(anno)

                    # check if we already have TTS audio cached? hash of specially formatted key string?
                    audio_key = f'tts:{ELEVEN_MODEL}:{ELEVEN_VOICE}:{plaintext}'
                    audio_key_hash = hashlib.md5(audio_key.encode()).hexdigest()
                    audio_fn = f'{audio_key_hash}.mp3'
                    audio_path = f'{args.audio_cache_dir}/{audio_fn}'
                    if not os.path.exists(f'{args.audio_cache_dir}/{audio_fn}'):
                        audio = client.generate(
                            text=plaintext,
                            voice=ELEVEN_VOICE,
                            model=ELEVEN_MODEL,
                            output_format='mp3_44100_192',
                        )
                        save(audio, audio_path)

                    # determine duration of audio
                    audio_duration = MP3(audio_path).info.length

                    # append to scene_components
                    scene_components.append({
                        'image_path': image_path,
                        'audio_path': audio_path,
                        'audio_dur': audio_duration,
                    })

                # create video from scene_components, into tempdir
                video_clips = []
                for scene in scene_components:
                    image_clip = ImageClip(scene['image_path'], duration=scene['audio_dur']+2*AUDIO_PADDING)
                    pre_silence = AudioClip(lambda t: 0, duration=AUDIO_PADDING)
                    post_silence = AudioClip(lambda t: 0, duration=AUDIO_PADDING)
                    combined_audio = concatenate_audioclips([pre_silence, AudioFileClip(scene['audio_path']), post_silence])
                    video_clip = image_clip.set_audio(combined_audio)
                    video_clips.append(video_clip)

                final_video = concatenate_videoclips(video_clips)
                final_video_path = f'{tmpdirn}/{generate_id()}.mp4'
                final_video.write_videofile(final_video_path, codec='libx264', audio_codec='aac', fps=30, logger=None)

                # get hash of video file
                with open(final_video_path, 'rb') as f:
                    video_contents = f.read()
                    video_hash = hashlib.md5(video_contents).hexdigest()

                # move video to output_media_dir with filename that include special prefix and contents hash
                video_fn = f'genai-{video_hash}.mp4'
                video_path = f'{args.output_media_dir}/{video_fn}'
                os.rename(final_video_path, video_path)
                print(f'generated {video_path}')
        elif elem['kind'] == 'quiz_audio_image':
            pass
        else:
            assert False, f'unknown kind {elem["kind"]}'

parser = argparse.ArgumentParser()
parser.add_argument('--lang', help='language code', required=True)
parser.add_argument('--source-meta', help='source metadata YAML file', required=True)
parser.add_argument('--source-media-dir', help='source media directory', required=True)
parser.add_argument('--audio-cache-dir', help='audio cache directory', required=True)
parser.add_argument('--output-meta', help='output metadata JSON file', required=True)
parser.add_argument('--output-media-dir', help='output media directory', required=True)

args = parser.parse_args()

build(args)
