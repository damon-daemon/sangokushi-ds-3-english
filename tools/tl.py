"""Translation helper: validate, auto-wrap and apply English lines.

Batch file format (one block per entry, blank lines ignored):

    @<id>
    English text, possibly over several physical lines (joined with spaces).
    \\_ is a literal space (for centring padding that line stripping would eat).
    {uXXXX} stands for a private-use character (icons, odd jump args) as `show` prints it.
    Use \\n for a forced line break and || for an explicit break that must be kept.
    A block containing just '=' copies the Japanese verbatim (entries with no text).

usage:
    tl.py apply  msgsecNN batch.txt   # validate + wrap + write 'en' into script/msgsecNN.json
    tl.py show   msgsecNN [from] [to] # print jp entries (codes visible) for translating
    tl.py stats                       # progress per file
    tl.py autofill msgsecNN           # copy entries with no visible text verbatim

Rules checked for every entry (see font-and-text-engine memory):
  * structural codes (anything {XX} except inline ones) appear in the same order
  * inline variables {02}{xx}ﾈ: same multiset per variant; speech inserts {01}C..{00}: a subset
  * same number of variants ({05}{05}{05} separators)
  * text encodes to cp932 and uses no full-width Latin/digits
  * wrapped lines fit the widest original line of that variant
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
import font6x12, script

VAR = r'\{02\}\{[0-9A-F]{2}\}[a-z]?ﾈ'      # {02}<var>[field]ﾈ: inserted name
SPEECH = r'\{01\}C(?:\{[0-9A-F]{2}\}|[^{])\{00\}'   # inserts msgsec00 entry (speaker's pronoun/ending)
INLINE = re.compile(r'%s|%s|\{1B\}C\d|\{1B\}[KH]' % (VAR, SPEECH))
CODE = re.compile(r'\{[0-9A-F]{2}\}')
GAIJI = re.compile(r'\{F[A-C]\}(?:\{[0-9A-F]{2}\}|[^{])')   # custom kanji: text, not a code
END = '{05}{05}{05}'
NAME_PX = 48                      # assumed width of an inserted name/variable
SINGLE_LINE_PX = 200              # allowed width for one-line prompts
FLOW_PX = 600                     # wider jp lines are engine-wrapped paragraphs
TAB_PX = 104                      # \t in a batch pads to this column (two-column lists)

def load_widths():
    path = os.path.join(ROOT, 'build', 'arm9_stock.bin')
    if not os.path.exists(path):
        import ndspy.rom
        rom = ndspy.rom.NintendoDSRom.fromFile(os.path.join(ROOT, 'sangokushi_ds_3.nds'))
        data = bytes(rom.loadArm9().sections[0].data)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
    a = open(path, 'rb').read()
    game = {ch: a[0x20E2634 - 0x02000000 + i * 9:][:9] for i, ch in enumerate(font6x12.GAME_GLYPHS)}
    return font6x12.table(game)[1]

W = None

def px(text):
    """Display width of one line (codes removed, variables counted as NAME_PX)."""
    global W
    if W is None:
        W = load_widths()
    text = GAIJI.sub('漢', text)
    text = re.sub(SPEECH, '', text)          # speech inserts: mostly empty in English
    text = re.sub(VAR, '\0', text)
    text = text.replace('%s', '\0')                   # printf names (city/ruler) count as a name
    text = re.sub(r'\{02\}(?:\{[0-9A-F]{2}\}|[!-~])', '\0', text)   # bare variables ({02}( {02}- ...)
    text = INLINE.sub('', text)
    total = 0
    for ch in CODE.sub('', text):
        if ch == '\0':
            total += NAME_PX
        elif ' ' <= ch <= '\x7f':
            total += W[ord(ch) - 0x20]
        else:
            total += 12
    return total

def codes_outside_inline(s):
    """Structural codes in order; {02} keeps its id byte (variables/args like {02}( {02}e)."""
    masked = INLINE.sub(lambda m: '#' * len(m.group()), GAIJI.sub('漢', s))
    arg = r'(?:\{[0-9A-F]{2}\}|[^{])'
    # {01}J<entry><table>: jump to another message; its args may look like kana
    return re.findall(r'\{01\}J%s%s|\{02\}%s?|\{[0-9A-F]{2}\}' % (arg, arg, arg), masked)

KANA = re.compile(r'\{1B\}[KH]')

def check(jp, en):
    errs = []
    # half-width-kana mode toggles mean nothing in English: compare without them
    if [c for c in codes_outside_inline(jp) if not KANA.fullmatch(c)] != \
       [c for c in codes_outside_inline(en) if not KANA.fullmatch(c)]:
        errs.append('structural codes differ:\n   jp %s\n   en %s' % (''.join(codes_outside_inline(jp)),
                                                                  ''.join(codes_outside_inline(en))))
    jv, ev = jp.split(END), en.split(END)
    if len(jv) != len(ev):
        errs.append('variant count %d != %d' % (len(jv), len(ev)))
    else:
        for i, (a, b) in enumerate(zip(jv, ev)):
            if sorted(re.findall(VAR, a)) != sorted(re.findall(VAR, b)):
                errs.append('variant %d inserts differ: %s vs %s' % (i, re.findall(VAR, a), re.findall(VAR, b)))
            # speech inserts may be dropped (e.g. "I" in object position written as "me"),
            # but never added
            extra = collections.Counter(re.findall(SPEECH, b)) - collections.Counter(re.findall(SPEECH, a))
            if extra:
                errs.append('variant %d speech inserts not in jp: %s' % (i, list(extra.elements())))
    for tok in ('%s', '%d', '%u', 'number1', 'number2', 'number3'):
        if jp.count(tok) != en.count(tok):
            errs.append('placeholder %r count %d != %d' % (tok, jp.count(tok), en.count(tok)))
    if re.search('[０-９Ａ-Ｚａ-ｚ]', ''.join(script.JUMP.split(en)[::2])):
        errs.append('full-width Latin/digits in English')
    try:
        script.encode(en)
    except Exception as e:
        errs.append('encode: %s' % e)
    return errs

def expand_tab(line):
    """Replace a tab with 2px spaces up to the TAB_PX column."""
    if '\t' not in line:
        return line
    a, b = line.split('\t', 1)
    while px(a) < TAB_PX:
        a += ' '
    return a + b

def header(jp_v):
    """Leading command/condition run of a variant ({01}/{04}-{07} commands and their
    ASCII args) that has no visible width; '' if the variant starts with text."""
    masked = INLINE.sub(lambda m: '\x01' * len(m.group()), jp_v)
    h = jp_v[:len(re.match(r'(?:\{[0-9A-F]{2}\}|[ -~])*', masked).group())]
    cmds = re.sub(r'\{02\}(?:\{[0-9A-F]{2}\}|.)', '', h)
    return h if re.search(r'\{0[14-7]\}', cmds) else ''

def file_floor(rows):
    """75th percentile of multi-line jp line widths in a file: the usual box width.
    Writers often broke lines early, so one entry's own lines underestimate the box."""
    ws = []
    for r in rows:
        for v in r['jp'].split(END):
            if '\n' in v:
                ws += [px(l.rstrip('\u3000 ')) for l in v[len(header(v)):].split('\n')]
    ws.sort()
    return ws[len(ws) * 3 // 4] if ws else 0

FLOOR = 0
# Measured in-game: the top-screen description frame (menus, options, Art of War,
# tutorial) shows ~222px and the engine re-wraps anything wider mid-word.
BOX_PX = {'msgsec01': 216, 'msgsec02': 216, 'msgsec03': 216, 'msgsec29': 216}
CAP = None

def wrap_variant(jp_v, en_v):
    """Word-wrap en_v to the widest line of jp_v (at least the file's FLOOR)."""
    h = header(jp_v)
    if not en_v.startswith(h):
        h = ''
    jp_v, en_v = jp_v[len(h):], en_v[len(h):]
    jp_lines = jp_v.split('\n')
    # trailing full-width spaces only pad over old text; they are not box width
    # (a line that also starts with full-width spaces is centred: its padding is box width)
    limit = max([FLOOR] + [px(l if l.startswith('\u3000') else l.rstrip('\u3000 ')) for l in jp_lines])
    if CAP and limit <= FLOW_PX:
        limit = min(limit, CAP)

    if limit > FLOW_PX:                   # paragraphs far wider than any box (bios): the
        return h + en_v, 10 ** 6, 1, 1     # game flows them itself, leave them alone
    if '\n' not in jp_v:                  # single-line prompts are never wrapped;
        return h + en_v, max(limit, SINGLE_LINE_PX), 1, 1   # their bars are wider than the jp text
    out = []
    for para in en_v.split('\n'):
        line = ''
        for word in re.split(r'(?<= )', para):
            if line and px(line + word.rstrip(' ')) > limit:
                out.append(line.rstrip(' ')); line = word
            else:
                line += word
        out.append(line.rstrip(' '))
    out = [expand_tab(l) for l in out]
    return h + '\n'.join(out), limit, len(out), len(jp_lines)

def prepare(jp, en):
    """Apply wrapping per variant; return (text, warnings)."""
    warns = []
    jv, ev = jp.split(END), en.split(END)
    if len(jv) != len(ev):
        return en, warns
    res = []
    for i, (a, b) in enumerate(zip(jv, ev)):
        b = b.replace('{1B}K{1B}H', '')            # kana toggles: dropped in English
        b2, limit, n_en, n_jp = wrap_variant(a, b)
        h = header(a) if b2.startswith(header(a)) else ''
        widest = max(px(l) for l in b2[len(h):].split('\n'))
        if widest > limit:
            warns.append('variant %d: line %dpx > box %dpx' % (i, widest, limit))
        if n_en > max(n_jp, 3 if n_jp > 1 else 1):
            warns.append('variant %d: %d lines (jp %d)' % (i, n_en, n_jp))
        res.append(b2)
    return END.join(res), warns

def parse_batch(path):
    blocks, cur, buf = {}, None, []
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        m = re.fullmatch(r'@(\d+)\s*', line)
        if m:
            if cur is not None:
                blocks[cur] = buf
            cur, buf = int(m.group(1)), []
        elif cur is not None and line.strip():
            buf.append(line.strip())
    if cur is not None:
        blocks[cur] = buf
    return {k: re.sub(r'\{u([0-9A-F]{4})\}', lambda m: chr(int(m.group(1), 16)),   # {uE06E}: PUA char
                      ' '.join(v)).replace(' || ', '\n').replace('||', '\n').replace('\\n ', '\n').replace('\\n', '\n').replace('\\t', '\t').replace('\\_', ' ')
            for k, v in blocks.items()}

def apply(name, batch):
    path = os.path.join(ROOT, 'script', name + '.json')
    rows = json.load(open(path, encoding='utf-8'))
    global FLOOR, CAP
    FLOOR = file_floor(rows)
    CAP = BOX_PX.get(name)

    blocks = parse_batch(batch)
    bad = 0
    for i, en in blocks.items():
        jp = rows[i]['jp']
        if en == '=':                            # no visible text: copy verbatim
            rows[i]['en'] = jp; continue
        # speech insert with id 0x0A ({01}C<newline>{00}) must not look like a line break
        jp = jp.replace('{01}C\n{00}', '{01}C{0A}{00}')
        jp = re.sub(r'\{01\}J\n', '{01}J{0A}', jp)    # jump to entry 0x0A
        text, warns = prepare(jp, en)
        errs = check(jp, text)
        for e in errs:
            print('%s@%d ERROR %s' % (name, i, e)); bad += 1
        for w in warns:
            print('%s@%d warn  %s' % (name, i, w))
        if not errs:
            rows[i]['en'] = text
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # size checks: 16-bit offsets, and the loader (0x02038D80) reads at most 0xB000 bytes
    # of a file into its slot (msgsec00 has a 0x1A00 slot); anything past that is lost
    size = len(script.build(os.path.join(ROOT, 'script'), name + '.dat'))
    cap = 0x1A00 if name == 'msgsec00' else 0xB000
    if size > cap:
        print('%s: ERROR file is %d bytes, over the %d-byte load limit' % (name, size, cap))
    done = sum(1 for r in rows if r['en'])
    print('%s: applied %d, errors %d, translated %d/%d' % (name, len(blocks) - bad, bad, done, len(rows)))

def invisible(jp):
    """True if an entry has no visible text (only jumps, conditions and other codes)."""
    t = re.sub(r'\{01\}J(?:\{[0-9A-F]{2}\}|.)(?:\{[0-9A-F]{2}\}|.)', '', jp)
    t = CODE.sub('', t)
    return not re.search(r'[^\x00-\x7f]', t)

def autofill(name):
    """Copy entries with no visible text verbatim into 'en'."""
    path = os.path.join(ROOT, 'script', name + '.json')
    rows = json.load(open(path, encoding='utf-8'))
    n = 0
    for r in rows:
        if not r['en'] and invisible(r['jp']):
            r['en'] = r['jp']; n += 1
    json.dump(rows, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('%s: autofilled %d entries with no visible text' % (name, n))

def show(name, a=0, b=None):
    rows = json.load(open(os.path.join(ROOT, 'script', name + '.json'), encoding='utf-8'))
    for r in rows[a:b]:
        jp = re.sub('[\ue000-\uf8ff]', lambda m: '{u%04X}' % ord(m.group()), r['jp'])
        print('@%d%s %s' % (r['id'], ' [done]' if r['en'] else '', jp.replace('\n', '⏎')))

def stats():
    tot = done = 0
    for f in sorted(os.listdir(os.path.join(ROOT, 'script'))):
        if f.startswith('msgsec'):
            rows = json.load(open(os.path.join(ROOT, 'script', f), encoding='utf-8'))
            d = sum(1 for r in rows if r['en']); tot += len(rows); done += d
            if rows: print('%s %d/%d' % (f[:-5], d, len(rows)))
    print('total %d/%d' % (done, tot))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'apply':
        apply(sys.argv[2], sys.argv[3])
    elif cmd == 'show':
        show(sys.argv[2], *(int(x) for x in sys.argv[3:5]))
    elif cmd == 'stats':
        stats()
    elif cmd == 'autofill':
        autofill(sys.argv[2])
