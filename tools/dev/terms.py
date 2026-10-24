# terms.py [--apply]: make skill/formation/tactic names in tl/msgsecNN.txt match the
# in-game UI names. Only touches entries whose Japanese contains the term, and only
# quoted names ("Old") or "Old formation" / "Old Formation", so prose isn't hit.
import sys, os, re, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
T = {  # jp: (new, [old...])
 '錐行': ('Awl', []), '鈎行': ('Hook', []), '箕形': ('Fan', ['Winnow']), '鶴翼': ('Crane', ['Crane Wing']),
 '魚鱗': ('Scales', ['Fish Scale', 'Fish Scales']), '偃月': ('Moon', ['Crescent']), '鋒矢': ('Arrow', ['Arrowhead']),
 '衡軛': ('Yoke', []), '長蛇': ('Snake', ['Long Snake']), '方円': ('Circle', ['Square']), '雁行': ('Geese', ['Wild Geese']),
 '突撃': ('Assault', ['Charge']), '特攻': ('Blitz', ['Charge']), '一斉': ('Joint', ['Volley']),
 '混乱': ('Panic', ['Confuse', 'Confusion']), '同討': ('Feud', ['Infighting']), '収拾': ('Order', ['Restore']),
 '仙術': ('Mystic', ['Mystic Arts']), '鼓舞': ('Rouse', ['Inspire']), '雨乞': ('Rain', ['Rainmaker']),
 '天変': ('Skies', ['Weather']), '落石': ('Rocks', ['Rockfall']), '占卜': ('Divine', ['Divination']),
 '伏兵': ('Lurk', ['Ambush']), '幻術': ('Mirage', ['Illusion']), '妖術': ('Hex', ['Sorcery']), '激励': ('Cheer', ['Encourage']),
 '火矢': ('Flame', ['Fire Arrows', 'Fire Arrow']), '奮迅': ('Fury', ['Rampage']), '乱射': ('Spray', ['Barrage']),
 '藤甲': ('Vines', ['Rattan Arm', 'Rattan Armor']), '無双': ('Mighty', ['Peerless']), '遠矢': ('Snipe', ['Long Shot']),
 '強行': ('March', ['Forced March']), '沈着': ('Calm', ['Composure']), '陣立': ('Shift', ['Q.Form', 'Quick Formation']),
 '反計': ('Foil', ['Counter', 'Counterplot']), '土砂': ('Slide', ['Landslide']), '応射': ('Reply', ['Return Fire']),
 '隠密': ('Sneak', ['Covert']), '挑発': ('Taunt', ['Provoke']), '心攻': ('Sway', ['Subvert']), '鉄壁': ('Wall', ['Iron Wall']),
 '猛獣': ('Beast', ['Beasts']), '傾国': ('Charm', ['Beauty']), '威風': ('Awe', ['Majesty']), '探知': ('Sense', ['Detect']),
 '逆境': ('Grit', ['Adversity']), '籠城': ('Hold', ['Defend']), '幸運': ('Luck', ['Fortune']),
}
def kana(s):  # script json stores half-width kana; the terms above are kanji, so no conversion needed
    return s
changes = 0
for path in sorted(glob.glob(os.path.join(ROOT, 'tl', 'msgsec*.txt'))):
    name = os.path.basename(path)[:-4]
    if 30 <= int(name[6:]) <= 40:          # biographies: historical prose, leave alone
        continue
    rows = json.load(open(os.path.join(ROOT, 'script', name + '.json'), encoding='utf-8'))
    lines = open(path, encoding='utf-8').read().split('\n')
    cur = None; dirty = False
    for i, l in enumerate(lines):
        m = re.fullmatch(r'@(\d+)', l)
        if m: cur = int(m.group(1)); continue
        if cur is None or cur >= len(rows): continue
        jp = rows[cur]['jp']; new = l
        for term, (en, olds) in T.items():
            if term not in jp: continue
            for old in olds:
                if old == 'Charge' and ('突撃' in jp) and ('特攻' in jp):
                    if '"Charge"' in new: print('AMBIG', name, cur)
                    continue
                for pat, rep in ((r'"%s"' % re.escape(old), '"%s"' % en),
                                 (r'\b%s(?= [Ff]ormation)' % re.escape(old), en)):
                    new = re.sub(pat, rep, new)
        if new != l:
            changes += 1
            if '--apply' not in sys.argv:
                print('%s@%d: %s' % (name, cur, re.sub(r'\s+', ' ', new)[:160]))
            lines[i] = new; dirty = True
    if dirty and '--apply' in sys.argv:
        open(path, 'w', encoding='utf-8').write('\n'.join(lines))
print('changed entries:', changes)
