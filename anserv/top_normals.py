import argparse
import sqlite3
import json
from collections import Counter

parser = argparse.ArgumentParser()

parser.add_argument('source_id', type=int)

args = parser.parse_args()

conn = sqlite3.connect('anserv.db', isolation_level=None)
c = conn.cursor()

# verify source id exists
c.execute('SELECT id FROM source WHERE id = ?', (args.source_id,))
if c.fetchone() is None:
    print(f'Error: source id {args.source_id} does not exist')
    exit(1)

ALGO = 'ja1'
normal_freq = Counter()
normal_doc_freq = Counter()

# use piece_source to find all piece rows for this source id
c.execute('''
SELECT piece.id, piece.analysis
FROM piece_source
INNER JOIN piece ON piece_source.piece_id = piece.id
WHERE piece_source.source_id = ?
''', (args.source_id,))

for row in c.fetchall():
    piece_id = row[0]
    analysis = row[1]

    if analysis is None:
        continue

    analysis = json.loads(analysis)
    if ALGO in analysis:
        normal_freq = analysis[ALGO]
        normal_freq.update(normal_freq)
        for normal in normal_freq:
            normal_doc_freq[normal] += 1

# print top normals
for normal, doc_freq in normal_doc_freq.most_common():
    if doc_freq < 2:
        break
    print(f'{normal} {doc_freq}')
