import argparse
import glob
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument('rootdir', type=str, help='videos root directory')

args = parser.parse_args()

total_time = 0
for filename in glob.iglob(os.path.join(args.rootdir, '**/*'), recursive=True):
    ext = filename.split('.')[-1]
    if ext in ['mp4', 'mkv', 'webm']:
        cmdline = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filename,
        ]
        output = subprocess.check_output(cmdline)
        t = float(output)
        total_time += t
        print(filename, t)

print(f'total time: {total_time} seconds = {total_time / 60} minutes = {total_time / 60 / 60} hours')
