import random
import string
import argparse
from pathlib import Path

import yaml

def migrate_meta(dir, meta_fn):
    meta = yaml.safe_load(Path(meta_fn).read_text())
    meta_map = {m['id']: m for m in meta}

    for p in Path(dir).iterdir():
        if p.is_dir():
            sourceid_fn = p / 'SOURCEID'
            meta_fn = p / 'meta.yaml'
            if meta_fn.exists():
                print(f'Skipping {meta_fn}')
            else:
                source_id = sourceid_fn.read_text().strip()
                assert source_id in meta_map
                with meta_fn.open('w') as f:
                    f.write(f'id: {source_id}\n')
                    f.write(f'title: {meta_map[source_id]["title"]}\n')
                    f.write(f'year: {meta_map[source_id]["year"]}\n')
                print(f'Created {meta_fn}')

parser = argparse.ArgumentParser()
parser.add_argument('dir', help='directory to create meta.yaml files')
parser.add_argument('meta_fn', help='metadata file to migrate')

args = parser.parse_args()

print(f'Migrating metadata files in {args.dir} with metadata file {args.meta_fn} ...')
migrate_meta(args.dir, args.meta_fn)
