"""Export/import Message/msgsecNN.dat <-> script/msgsecNN.json.

Text encoding in JSON:
  - Shift-JIS characters (full and half-width) as themselves
  - printable ASCII as itself
  - newline byte 0x0A as "\n"
  - any other byte as {XX} (hex); a literal '{' is written {7B}
Each entry: {"id": n, "jp": original, "en": translation or ""}.
"""
import json, os, re, struct, sys

def entries(d):
    if len(d) < 2:
        return []
    n = struct.unpack_from('<H', d, 0)[0]
    offs = list(struct.unpack_from('<%dH' % n, d, 2)) + [len(d)]
    return [d[offs[i]:offs[i + 1]] for i in range(n)]

def pack(strs):
    if not strs:
        return b''
    hdr = 2 + 2 * len(strs)
    offs, pos = [], hdr
    for s in strs:
        offs.append(pos); pos += len(s)
    if offs[-1] > 0xFFFF:
        raise ValueError('message file exceeds 16-bit offset range (%d bytes)' % pos)
    return struct.pack('<H%dH' % len(strs), len(strs), *offs) + b''.join(strs)

def decode(b):
    out, i = [], 0
    while i < len(b):
        c = b[i]
        # {02}<var><field>: a field byte that looks like an SJIS lead byte is a
        # code, not the start of a character (e.g. {02}{01}{81} = "is female")
        field = i >= 2 and b[i - 2] == 0x02 and b[i - 1] < 0x20
        if i >= 4 and b[i - 4:i - 2] == b'\x01C':   # {01}C{02}{00}: speech insert 02, not a variable
            field = False
        if 0xFA <= c <= 0xFC and i + 1 < len(b) and not field:
            # custom kanji: {FA}-{FC} + one index byte (never part of an SJIS pair)
            a = b[i + 1]
            out.append('{%02X}' % c + (chr(a) if 0x20 <= a < 0x7F and a != 0x7B
                                       else bytes([a]).decode('cp932') if 0xA1 <= a <= 0xDF
                                       else '{%02X}' % a))
            i += 2
            continue
        if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(b) and not field:
            try:
                ch = b[i:i + 2].decode('cp932')
                if ch.encode('cp932') == b[i:i + 2]:
                    out.append(ch); i += 2; continue
            except UnicodeError:
                pass
        if 0xA1 <= c <= 0xDF:
            out.append(bytes([c]).decode('cp932'))
        elif c == 0x0A:
            out.append('\n')
        elif 0x20 <= c < 0x7F and c != 0x7B:
            out.append(chr(c))
        else:
            out.append('{%02X}' % c)
        i += 1
    return ''.join(out)

def encode(s):
    out, i = bytearray(), 0
    while i < len(s):
        ch = s[i]
        if ch == '{':
            j = s.index('}', i)
            out.append(int(s[i + 1:j], 16)); i = j + 1; continue
        out += ch.encode('cp932'); i += 1
    return bytes(out)

def export(fs_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    msg = os.path.join(fs_dir, 'Message')
    for name in sorted(os.listdir(msg)):
        d = open(os.path.join(msg, name), 'rb').read()
        rows = []
        for n, e in enumerate(entries(d)):
            t = decode(e)
            assert encode(t) == e, (name, n)
            rows.append({'id': n, 'jp': t, 'en': ''})
        assert pack([encode(r['jp']) for r in rows]) == d or len(d) < 2, name
        json.dump(rows, open(os.path.join(out_dir, name.replace('.dat', '.json')), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)

# Full-width ０-９/Ａ-Ｚ/ａ-ｚ glyphs are overwritten by the ASCII font and VWF
# hooks (patch_arm9.py), so any that remain are converted to ASCII at build time.
FW_LATIN = {c: c - 0xFEE0 for c in list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B))
            + list(range(0xFF41, 0xFF5B))}

JUMP = re.compile(r'(\{01\}J(?:\{[0-9A-F]{2}\}|.){1,2})')   # {01}J<entry><table>: raw arg bytes

def fw_to_ascii(s):
    """Apply FW_LATIN outside jump arguments (an arg pair can decode as e.g. 'Ｊ')."""
    return ''.join(p if i % 2 else p.translate(FW_LATIN) for i, p in enumerate(JUMP.split(s)))

def build(script_dir, name):
    """Return packed bytes for a message file, using 'en' where present."""
    rows = json.load(open(os.path.join(script_dir, name.replace('.dat', '.json')), encoding='utf-8'))
    return pack([encode(fw_to_ascii(r['en'] or r['jp'])) for r in rows])

if __name__ == '__main__':
    export(sys.argv[1], sys.argv[2])
