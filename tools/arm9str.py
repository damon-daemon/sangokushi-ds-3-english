"""UI string pool in arm9 (command names, stats, ranks, event titles, save messages).

The pool (0x02100D80-0x02103800) holds ~840 NUL-terminated SJIS strings in
4-byte aligned slots, interleaved with pointer tables. Every string start is
the target of a pointer word somewhere in arm9 (literal pools, tables) or in
overlay 7, so the starts are found by scanning for words that point into it.

  export:  .venv/bin/python tools/arm9str.py export   -> script/arm9_strings.json
  apply(): writes English from tl/arm9.txt. A string that fits its slot
           (cap bytes + NUL) is written in place; a longer one is moved into
           space freed elsewhere in the pool and its arm9 pointers are updated.

tl/arm9.txt: one entry per line, tab-separated; `\\n` = newline, # = comment.
  <jp text>\t<english>     every slot whose jp text matches
  @<ADDR>\t<english>       one slot (overrides the jp entry)
"""
import json, os, struct, sys
import ndspy.rom

sys.path.insert(0, os.path.dirname(__file__))
import script

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LO, HI = 0x02100D80, 0x02103800
JSON = os.path.join(ROOT, 'script', 'arm9_strings.json')
TL = os.path.join(ROOT, 'tl', 'arm9.txt')

def _is_table(blob, base, a):
    o = a - base
    return a % 4 == 0 and blob[o + 2] == 0x10 and blob[o + 3] == 0x02

def export(rom_path):
    rom = ndspy.rom.NintendoDSRom.fromFile(rom_path)
    arm9 = rom.loadArm9()
    sec = next(s for s in arm9.sections if s.ramAddress <= LO < s.ramAddress + len(s.data))
    base, blob = sec.ramAddress, bytes(sec.data)
    refs = {}
    def scan(name, data, start):
        for i in range(0, len(data) - 3, 4):
            v = struct.unpack_from('<I', data, i)[0]
            if LO <= v < HI:
                refs.setdefault(v, []).append([name, start + i])
    for s in arm9.sections:
        scan('arm9', bytes(s.data), s.ramAddress)
    for k, ov in rom.loadArm9Overlays().items():
        scan('ov%d' % k, ov.data, ov.ramAddress)
    starts = sorted(a for a in refs if not _is_table(blob, base, a))
    rows = []
    for n, a in enumerate(starts):
        o = a - base
        e = blob.index(b'\0', o)
        nxt = starts[n + 1] if n + 1 < len(starts) else a + (e - o) + 1
        k = e
        while k < nxt - base and blob[k] == 0:
            k += 1
        if k < nxt - base and _is_table(blob, base, k + base):
            nxt = k + base
        if k != nxt - base:               # followed by unknown data: not a plain slot
            continue
        try:
            jp = script.decode(blob[o:e])
        except Exception:
            continue
        rows.append({'addr': '%08X' % a, 'jp': jp, 'cap': k - o - 1, 'refs': refs[a]})
    json.dump(rows, open(JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('%d strings -> %s' % (len(rows), JSON))

def load_tl():
    by_jp, by_addr = {}, {}
    if not os.path.exists(TL):
        return by_jp, by_addr
    for n, line in enumerate(open(TL, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '\t' not in line:
            raise ValueError('%s:%d: missing tab' % (TL, n))
        k, v = line.split('\t', 1)
        v = v.replace('\\n', '\n')
        if k.startswith('@'):
            by_addr[int(k[1:], 16)] = v
        else:
            by_jp[k.replace('\\n', '\n')] = v
    return by_jp, by_addr

def plan(rows=None):
    """Return ([(addr, bytes, cap, refs)], warnings) for every translated slot."""
    rows = rows or json.load(open(JSON, encoding='utf-8'))
    by_jp, by_addr = load_tl()
    out, warns = [], []
    for r in rows:
        a = int(r['addr'], 16)
        en = by_addr.get(a, by_jp.get(r['jp']))
        if not en:
            continue
        b = script.encode(script.fw_to_ascii(en))
        out.append((a, b, r['cap'], r['refs'], r['jp']))
    return out, warns

def apply(code):
    """Write translations into an ndspy MainCodeFile (arm9). Returns (#in place, #moved)."""
    from patch_arm9 import Arm9
    a9 = Arm9(code)
    items, _ = plan()
    rows = {int(r['addr'], 16): r for r in json.load(open(JSON, encoding='utf-8'))}
    fits = [it for it in items if len(it[1]) <= it[2]]
    moves = [it for it in items if len(it[1]) > it[2]]
    for a, b, cap, refs, jp in fits:
        a9.write(a, b + b'\0' * (cap + 1 - len(b)))
    # free space: tail of every in-place slot plus each moved string's whole slot;
    # slots are contiguous, so merge neighbours into larger runs
    spans = [(a + len(b) + 1, a + cap + 1) for a, b, cap, refs, jp in fits if cap > len(b)]
    spans += [(a, a + cap + 1) for a, b, cap, refs, jp in moves]
    free = []
    for lo, hi in sorted(spans):
        if free and free[-1][1] == lo:
            free[-1][1] = hi
        else:
            free.append([lo, hi])
    for a, b, cap, refs, jp in sorted(moves, key=lambda it: -len(it[1])):
        if any(m != 'arm9' for m, _ in refs):
            raise ValueError('%08X %r: too long (%d > %d) and referenced from an overlay' % (a, jp, len(b), cap))
        need = len(b) + 1
        cand = [g for g in free if g[1] - g[0] >= need]
        if not cand:
            raise ValueError('%08X %r: no free pool space for %d bytes' % (a, jp, need))
        g = min(cand, key=lambda g: g[1] - g[0])
        dst = g[0]; g[0] += need
        a9.write(dst, b + b'\0')
        for _, p in refs:
            assert struct.unpack('<I', a9.read(p, 4))[0] == a
            a9.write(p, struct.pack('<I', dst))
    for g in free:                        # leave no stale Japanese bytes behind
        a9.write(g[0], b'\0' * (g[1] - g[0]))
    return len(fits), len(moves)

def check():
    items, _ = plan()
    over = [(a, jp, len(b), cap) for a, b, cap, refs, jp in items if len(b) > cap]
    total = len(json.load(open(JSON, encoding='utf-8')))
    print('%d/%d translated, %d over slot' % (len(items), total, len(over)))
    for a, jp, n, cap in over:
        print('  %08X %d>%d %s' % (a, n, cap, jp.replace('\n', '\\n')))

if __name__ == '__main__':
    if sys.argv[1] == 'export':
        export(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'sangokushi_ds_3.nds'))
    elif sys.argv[1] == 'check':
        check()
