import random
import string
import argparse
from pathlib import Path

def generate_id():
    return ''.join(random.choice(string.ascii_letters+string.digits) for i in range(12))

def generate_validate_meta(dir):
    for p in Path(dir).iterdir():
        if p.is_dir():
            meta_fn = p / 'meta.yaml'
            if meta_fn.exists():
                pass
            else:
                with meta_fn.open('w') as f:
                    f.write('id: {}\n'.format(generate_id()))
                    f.write('title: \n')
                    f.write('year: \n')
                print('Created {}'.format(meta_fn))

parser = argparse.ArgumentParser()
parser.add_argument('dir', help='directory to create meta.yaml files')

args = parser.parse_args()

print('Generating meta.yaml files in {}...'.format(args.dir))
generate_validate_meta(args.dir)
