import argparse
import hashlib
import subprocess
import os
import tempfile

from google.cloud import texttospeech

LANG_VOICES = {
    'es': [('es-ES', 'es-ES-Studio-C'), ('es-ES', 'es-ES-Studio-F')],
}

client = texttospeech.TextToSpeechClient()

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16
)

def generate_clip(lang, text, voice_lang, voice_name, output_dir):
    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=voice_lang,
        name=voice_name,
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    # generate clip filename based on hash of text
    clip_id = hashlib.md5(text.encode('utf-8')).hexdigest() + '-goog-' + voice.name

    with tempfile.TemporaryDirectory() as tmpdirname:
        clip_tmp_fn = os.path.join(tmpdirname, clip_id + '.wav')

        # The response's audio_content is binary.
        with open(clip_tmp_fn, 'wb') as out:
            # Write the response to the output file.
            out.write(response.audio_content)

        # encode as mp3
        clip_tmp_mp3_fn = clip_tmp_fn.replace('.wav', '.mp3')
        subprocess.run(['lame', '--silent', '-q0', '-V5', clip_tmp_fn, clip_tmp_mp3_fn])

        # move to output directory
        clip_fn = os.path.join(output_dir, clip_id + '.mp3')
        os.rename(clip_tmp_mp3_fn, clip_fn)

    return clip_id

def generate_clips(lang, output_dir):
    while True:
        try:
            text = input('Text> ')
        except EOFError:
            break
        except KeyboardInterrupt:
            break

        for (voice_lang, voice_name) in LANG_VOICES[lang]:
            clip_id = generate_clip(lang, text, voice_lang, voice_name, output_dir)
            print(clip_id)

parser = argparse.ArgumentParser()

parser.add_argument('lang', help='language code')
parser.add_argument('output_dir', help='output directory')

args = parser.parse_args()

generate_clips(args.lang, args.output_dir)
