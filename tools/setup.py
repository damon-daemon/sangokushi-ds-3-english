"""Create the working folder script/ from your own ROM and the English in tl/.

script/ holds the Japanese text extracted from the ROM next to the English, so it
is generated on each machine and never distributed. Run this once after cloning
(and again after editing tl/), then tools/build.py.

usage: .venv/bin/python tools/setup.py [clean.nds]
"""
import hashlib, json, os, sys
import ndspy.rom

sys.path.insert(0, os.path.dirname(__file__))
import script, names, arm9str, tl
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gen'))
import msgsec00

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'script')
TL = os.path.join(ROOT, 'tl')
CLEAN_SHA1 = 'b2e33ee0826db5862ed096ae93086c93d51713da'

def export_messages(rom):
    for n in range(68):
        name = 'msgsec%02d' % n
        d = bytes(rom.getFileByName('Message/%s.dat' % name))
        rows = []
        for i, e in enumerate(script.entries(d) if len(d) >= 2 else []):
            rows.append({'id': i, 'jp': script.decode(e), 'en': ''})
        json.dump(rows, open(os.path.join(SCRIPT, name + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

def export_names(rom):
    fix = bytes(rom.getFileByName('Scenario/FixData.bin'))
    stage = bytes(rom.getFileByName('Challenge/ChallengeStage.bin'))
    def jp_of(kind, i):
        if kind == 'cities':
            o = names.CITY_OFF + i * names.CITY_SIZE
            return names._field(fix[o:o + names.CITY_NAME])
        if kind in ('officers', 'sp'):
            o = names.OFF_OFF + i * names.OFF_SIZE
            return names._field(fix[o:o + 9])
        if kind == 'items':
            o = names.ITEM_OFF + i * names.ITEM_SIZE
            return names._field(fix[o:o + names.ITEM_NAME])
        o = i * names.STAGE_SIZE + names.STAGE_NAME
        return names._field(stage[o:o + names.STAGE_LEN])
    for kind in ('cities', 'officers', 'sp', 'items', 'stages'):
        rows = json.load(open(os.path.join(TL, 'names_%s.json' % kind), encoding='utf-8'))
        for r in rows:
            r['jp'] = jp_of(kind, r['id'])
        json.dump(rows, open(os.path.join(SCRIPT, 'names_%s.json' % kind), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sangokushi_ds_3.nds')
    sha1 = hashlib.sha1(open(path, 'rb').read()).hexdigest()
    if sha1 != CLEAN_SHA1:
        sys.exit('%s: SHA-1 %s does not match the clean dump (%s)' % (path, sha1, CLEAN_SHA1))
    rom = ndspy.rom.NintendoDSRom.fromFile(path)
    os.makedirs(SCRIPT, exist_ok=True)
    export_messages(rom)
    msgsec00.apply(os.path.join(SCRIPT, 'msgsec00.json'))
    for n in range(1, 68):
        batch = os.path.join(TL, 'msgsec%02d.txt' % n)
        if os.path.exists(batch):
            tl.apply('msgsec%02d' % n, batch)
    arm9str.export(path)
    export_names(rom)
    print('script/ ready; now run tools/build.py')

if __name__ == '__main__':
    main()
