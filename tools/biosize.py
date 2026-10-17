"""Report English byte sizes of a bio file (msgsec30-35) against its load budget.
usage: biosize.py msgsecNN   (prints entries over 460 bytes and the projected total)"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import script
name = sys.argv[1]
rows = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'script', name + '.json'), encoding='utf-8'))
total = 2 + 2 * len(rows)
for r in rows:
    b = len(script.encode(script.fw_to_ascii(r['en'] or r['jp'])))
    total += b
    if r['en'] and b > 460:
        print('@%d %d' % (r['id'], b))
print('%s: %d of %d bytes (%d translated)' % (name, total, 0xB000, sum(1 for r in rows if r['en'])))
