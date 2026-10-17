"""Export/import name tables in Scenario/FixData.bin.

  cities:   47 records x 22 bytes = name[5] + kana reading[7] + stats[10]
  officers: 571 records x 20 bytes = name[9] + kana reading[11]
  SP slots: 129 more officer records (571-699): placeholders, historical and
            Water Margin heroes in FixData; ChallengeFixData (Battle Road) keeps
            regular officers in 600-699, so these are matched by jp name.
  items:    48 records x 35 bytes from 0x428A = name[13] + reading[16] + stats[6]
Officer ids used in the script ({04}=N codes) are 1-based: id = index + 1.

English names longer than the name field overwrite the reading field
(cities up to 11 chars, officers up to 19, + null); stats are never touched.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import script

CITY_OFF, CITY_SIZE, CITY_COUNT = 0x0, 22, 47
CITY_NAME, CITY_TEXT = 5, 12      # name field, name+reading
OFF_OFF, OFF_SIZE, OFF_COUNT = 0x40A, 20, 571
SP_COUNT = 229               # slots 571-799 (Battle Road uses 700+ too)
ITEM_OFF, ITEM_SIZE, ITEM_NAME, ITEM_TEXT, ITEM_COUNT = 0x428A, 35, 13, 29, 48

def _field(b):
    return script.decode(b.split(b'\0')[0])

def export(fixdata, out_dir):
    d = open(fixdata, 'rb').read()
    cities = []
    for i in range(CITY_COUNT):
        r = d[CITY_OFF + i * CITY_SIZE:][:CITY_SIZE]
        cities.append({'id': i, 'jp': _field(r[:CITY_NAME]), 'reading': _field(r[CITY_NAME:CITY_TEXT]), 'en': ''})
    officers = []
    for i in range(OFF_COUNT):
        r = d[OFF_OFF + i * OFF_SIZE:][:OFF_SIZE]
        officers.append({'id': i, 'jp': _field(r[:9]), 'reading': _field(r[9:]), 'en': ''})
    for name, rows in (('cities', cities), ('officers', officers)):
        json.dump(rows, open(os.path.join(out_dir, 'names_%s.json' % name), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

def apply(data, script_dir):
    d = bytearray(data)
    for row in json.load(open(os.path.join(script_dir, 'names_cities.json'), encoding='utf-8')):
        if row['en']:
            b = script.encode(row['en'])
            o = CITY_OFF + row['id'] * CITY_SIZE
            if len(b) < CITY_NAME:              # short name: also blank the kana reading
                d[o:o + CITY_TEXT] = b.ljust(CITY_TEXT, b'\0')
            else:
                assert len(b) < CITY_TEXT, row
                d[o:o + CITY_TEXT] = b.ljust(CITY_TEXT, b'\0')
    def put_officer(i, en):
        b = script.encode(en)
        o = OFF_OFF + i * OFF_SIZE
        if len(b) <= 8:
            d[o:o + 9] = b.ljust(9, b'\0')
        else:
            assert len(b) < OFF_SIZE, en
            d[o:o + OFF_SIZE] = b.ljust(OFF_SIZE, b'\0')
    officers = json.load(open(os.path.join(script_dir, 'names_officers.json'), encoding='utf-8'))
    sp = json.load(open(os.path.join(script_dir, 'names_sp.json'), encoding='utf-8'))
    by_jp = {r['jp']: r['en'] for r in officers + sp if r['en']}
    for row in officers:
        if row['en']:
            put_officer(row['id'], row['en'])
    for i in range(OFF_COUNT, OFF_COUNT + SP_COUNT):
        jp = _field(d[OFF_OFF + i * OFF_SIZE:][:9])
        if jp in by_jp:
            put_officer(i, by_jp[jp])
    for row in json.load(open(os.path.join(script_dir, 'names_items.json'), encoding='utf-8')):
        if row['en']:
            b = script.encode(row['en'])
            o = ITEM_OFF + row['id'] * ITEM_SIZE
            assert len(b) < ITEM_TEXT, row
            d[o:o + ITEM_TEXT] = b.ljust(ITEM_TEXT, b'\0')
    return bytes(d)

STAGE_SIZE, STAGE_NAME, STAGE_LEN = 56, 6, 17   # Challenge/ChallengeStage.bin: 20 Battle Road stages

def apply_stages(data, script_dir):
    d = bytearray(data)
    for row in json.load(open(os.path.join(script_dir, 'names_stages.json'), encoding='utf-8')):
        if row['en']:
            b = script.encode(row['en'])
            assert len(b) < STAGE_LEN, row
            o = row['id'] * STAGE_SIZE + STAGE_NAME
            d[o:o + STAGE_LEN] = b.ljust(STAGE_LEN, b'\0')
    return bytes(d)

if __name__ == '__main__':
    export(sys.argv[1], sys.argv[2])
