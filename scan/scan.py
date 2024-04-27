import json
import boto3

CLIPS_BUCKET = 'yukawa-clips'
LANG = 'ja'

if __name__ == '__main__':
    clips = []

    # scan for all top-level folders in bucket yukawa-clips
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects')

    for page in paginator.paginate(Bucket=CLIPS_BUCKET, Delimiter='/', Prefix=LANG+'/'):
        for pref in page.get('CommonPrefixes', []):
            source_prefix = pref['Prefix']
            print('Scanning source:', source_prefix)

            clips_jsonl_key = source_prefix + 'clips.jsonl'

            clips_jsonl_obj = s3.get_object(Bucket=CLIPS_BUCKET, Key=clips_jsonl_key)
            clips_jsonl = clips_jsonl_obj['Body'].read().decode('utf-8')

            # split and parse jsonl
            clip_lines = clips_jsonl.strip().split('\n')
            for clip_line in clip_lines:
                clip_obj = json.loads(clip_line)
                clips.append(clip_obj)
            print('added', len(clip_lines), 'clips metadata')

    print('Total clips:', len(clips))

    # write clips out to single local JSON file
    clips_json = json.dumps(clips, indent=2)
    OUT_FN = 'all_clips.json'
    with open(OUT_FN, 'w') as f:
        f.write(clips_json)
    print('Wrote', OUT_FN)
