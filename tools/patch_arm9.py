"""ARM9 patches: half-width ASCII font.

The stock half-width glyph lookup (0x020438CC) linearly searches an 18-entry
list ("0123456789-+/(),.:") and falls back to a blank glyph, so ASCII letters
render as nothing. We replace it with a direct lookup into a 96-glyph table
(ASCII 0x20-0x7F, 6x12 1bpp, 9 bytes each) stored over the full-width digit and
Latin letter glyphs, which the build converts to ASCII everywhere in the script.
"""
import os, struct, sys
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

sys.path.insert(0, os.path.dirname(__file__))
import font6x12

HW_LIST = 0x020E25E0      # 18 half-width chars
HW_GLYPHS = 0x020E2634    # 18 x 9-byte glyphs
FW_GLYPHS = 0x020E26D8    # full-width glyphs, 18 bytes each
FW_INDEX = 0x020F4594     # u16 index table for SJIS 0x8140..0x9FFF
HOOK = 0x020438CC         # inside glyph-pointer lookup, half-width branch
FALLBACK = 0x0204393C     # stock "use blank glyph" path

# Variable-width font. The stock 18-glyph table (HW_GLYPHS, 162 bytes) is dead
# after HOOK and holds the width table + shared width routine; the other hooks
# go in the space left after the ASCII glyph table (see apply()).
WIDTHS = HW_GLYPHS                    # 96 bytes, advance per char 0x20-0x7F
WIDTH_FN = WIDTHS + 96                # r0 = char -> r0 = advance; preserves all other regs
TRAMP_LAYOUT = WIDTH_FN + 32
DRAW_ADVANCE = 0x0204349C             # drawer:  add r7, r7, #6     (char at [sb])
LAYOUT_ADVANCE = 0x02042CBC           # layout:  add r6, r6, #6     (char in r1)
MEASURE_ADVANCE = 0x02043A60          # measure: add ip, ip, #6     (char in sb; r0 live)
DRAW_CLIP = 0x02043454                # drawer:  ldr r0, [sp, #0x20] (= right edge fp - 6)
# Line-wrap look-ahead ("does the next char fit?") assumed 6px; if not, the rest
# of the string moves to a new line, which single-line list cells never show.
LAYOUT_LOOKAHEAD = 0x02042CC8         # layout:  add r0, r1, #6  (next char r7, pen r1)
DRAW_LOOKAHEAD = 0x020434A0           # drawer:  add r0, r7, #6  (next char r8, pen r7)
MEASURE_LOOKAHEAD = 0x02043A68        # measure: add r7, ip, #6  (next char r6, pen ip)
# The measure routine (0x02043964) counts lines before centred/aligned drawing.

# Alignment (0x020431A0): centred x = left + ((right - left - width) lsr 1).
# A line 1px wider than its cell (the allowed trailing gap column) made this
# wrap to a huge x and the whole string vanished; clamp the slack at 0.
ALIGN_DEFAULT_BRANCH = 0x020431B8     # b 0x020431E4  (mode >= 3: return left)
ALIGN_CENTRE = 0x020431D8             # sub r0, r0, r2 / add r0, r3, r0, lsr #1 / mov r0, r3

# Officer reading getter (vtable slot 0x140): returns record+9. English names
# overflow into the reading, so point it at record+19 (always the null pad)
# and the reading box shows nothing instead of garbage kana.
READING_GETTER_ADD = 0x0202AD00       # add r0, r0, #9
# Reading box text (vtable slot 0x144) converts record+9 half-width kana to
# full-width katakana; start it at record+19 too so the box is blank.
READING_KANA_LOAD = 0x0202AD34        # ldrb r8, [r0, #9]
# Same pair for city records (22 bytes, name[5] + reading[7]): English names run
# into the reading; byte 11 is always the name's null, so read from there.
CITY_READING_GETTER_ADD = 0x02030B54  # add r0, r0, #5
CITY_READING_KANA_LOAD = 0x02030B88   # ldrb r8, [r0, #5]

class Arm9:
    def __init__(self, code):
        self.code = code
    def _sec(self, addr, n):
        for s in self.code.sections:
            if s.ramAddress <= addr and addr + n <= s.ramAddress + len(s.data):
                return s
        raise KeyError(hex(addr))
    def read(self, addr, n):
        s = self._sec(addr, n); o = addr - s.ramAddress
        return bytes(s.data[o:o + n])
    def write(self, addr, data):
        s = self._sec(addr, len(data)); o = addr - s.ramAddress
        if not isinstance(s.data, bytearray): s.data = bytearray(s.data)
        s.data[o:o + len(data)] = data

def fw_index(a, code):
    return struct.unpack('<H', a.read(FW_INDEX + (code - 0x8140) * 2, 2))[0]

def apply(code):
    a = Arm9(code)
    # sanity: stock code and data present
    assert a.read(HW_LIST, 18) == font6x12.GAME_GLYPHS.encode(), 'unexpected arm9 (half-width list)'
    # Full-width ０-９ and Ａ-ｚ glyphs are contiguous; the build converts all of
    # them to ASCII, so this area holds the ASCII glyph table and the hooks.
    codes = list(range(0x824F, 0x8259)) + list(range(0x8260, 0x827A)) + list(range(0x8281, 0x829B))
    idx = [fw_index(a, c) for c in codes]
    assert idx == list(range(idx[0], idx[0] + len(idx))), 'full-width digit/Latin glyphs not contiguous'
    table_addr = FW_GLYPHS + idx[0] * 18
    area_end = FW_GLYPHS + (idx[-1] + 1) * 18

    game = {ch: a.read(HW_GLYPHS + i * 9, 9) for i, ch in enumerate(font6x12.GAME_GLYPHS)}
    glyphs, widths = font6x12.table(game)
    a.write(table_addr, glyphs)

    ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    asm = lambda src, addr: bytes(ks.asm(src, addr)[0])
    sites = {DRAW_ADVANCE: 'add r7, r7, #6', LAYOUT_ADVANCE: 'add r6, r6, #6',
             MEASURE_ADVANCE: 'add ip, ip, #6', DRAW_CLIP: 'ldr r0, [sp, #0x20]',
             LAYOUT_LOOKAHEAD: 'add r0, r1, #6', DRAW_LOOKAHEAD: 'add r0, r7, #6',
             MEASURE_LOOKAHEAD: 'add r7, ip, #6', READING_GETTER_ADD: 'add r0, r0, #9',
             READING_KANA_LOAD: 'ldrb r8, [r0, #9]', ALIGN_DEFAULT_BRANCH: 'b 0x020431e4',
             CITY_READING_GETTER_ADD: 'add r0, r0, #5', CITY_READING_KANA_LOAD: 'ldrb r8, [r0, #5]'}
    for addr, src in sites.items():
        assert a.read(addr, 4) == asm(src, addr), hex(addr)

    # width(c) = WIDTHS[c - 0x20] for c in 0x20..0x7F, else the stock 6px
    width_fn = asm('''
        str    r1, [sp, #-4]!
        sub    r0, r0, #0x20
        cmp    r0, #0x60
        movhs  r0, #6
        sublo  r1, pc, #%d
        ldrblo r0, [r1, r0]
        ldr    r1, [sp], #4
        bx     lr
    ''' % (WIDTH_FN + 0x18 - WIDTHS), WIDTH_FN)     # pc = WIDTH_FN+0x10+8
    assert len(width_fn) == 32
    hook = lambda body, addr, save='lr', ret='pc': asm('push {%s}\n%s\npop {%s}' % (save, body, ret), addr)
    w = 'bl %#x' % WIDTH_FN
    hooks = [
        # (site, body, saved regs)
        (DRAW_ADVANCE, 'ldrb r0, [sb]\n%s\nadd r7, r7, r0' % w, ''),
        # glyph is drawn only if pen <= r0: right edge - (real width - 1) instead of - 6
        # (the last column of each glyph is its blank gap/shadow column)
        (DRAW_CLIP, 'ldrb r0, [sb]\n%s\nrsb r0, r0, fp\nadd r0, r0, #1' % w, ''),
        (LAYOUT_LOOKAHEAD, 'mov r0, r7\n%s\nadd r0, r0, r1\nsub r0, r0, #1' % w, ''),
        (DRAW_LOOKAHEAD, 'mov r0, r8\n%s\nadd r0, r0, r7\nsub r0, r0, #1' % w, ''),
        (MEASURE_ADVANCE, 'mov r0, sb\n%s\nadd ip, ip, r0' % w, 'r0, '),
        (MEASURE_LOOKAHEAD, 'mov r0, r6\n%s\nadd r7, ip, r0\nsub r7, r7, #1' % w, 'r0, '),
    ]
    a.write(WIDTHS, widths)
    a.write(WIDTH_FN, width_fn)
    layout = hook('mov r0, r1\n%s\nadd r6, r6, r0' % w, TRAMP_LAYOUT)
    assert TRAMP_LAYOUT + len(layout) <= HW_GLYPHS + 18 * 9
    a.write(TRAMP_LAYOUT, layout)
    a.write(LAYOUT_ADVANCE, asm('bl %#x' % TRAMP_LAYOUT, LAYOUT_ADVANCE))
    t = (table_addr + len(glyphs) + 3) & ~3
    for site, body, save in hooks:
        b = hook(body, t, save + 'lr', save + 'pc')
        assert t + len(b) <= area_end, 'out of hook space'
        a.write(t, b)
        a.write(site, asm('bl %#x' % t, site))
        t += len(b)
    a.write(READING_GETTER_ADD, asm('add r0, r0, #19', READING_GETTER_ADD))
    a.write(READING_KANA_LOAD, asm('ldrb r8, [r0, #19]', READING_KANA_LOAD))
    a.write(CITY_READING_GETTER_ADD, asm('add r0, r0, #11', CITY_READING_GETTER_ADD))
    a.write(CITY_READING_KANA_LOAD, asm('ldrb r8, [r0, #11]', CITY_READING_KANA_LOAD))

    stock = asm('sub r0, r0, r2\nadd r0, r3, r0, lsr #1\nbx lr\nmov r0, r3', ALIGN_CENTRE)
    assert a.read(ALIGN_CENTRE, 16) == stock
    a.write(ALIGN_DEFAULT_BRANCH, asm('b 0x020431bc', ALIGN_DEFAULT_BRANCH))   # same: mov r0, r3; bx lr
    a.write(ALIGN_CENTRE, asm('subs r0, r0, r2\nmovmi r0, #0\nadd r0, r3, r0, lsr #1\nbx lr', ALIGN_CENTRE))

    asm = f'''
        and   r1, r1, #0xff
        sub   r0, r1, #0x20
        cmp   r0, #0x60
        bhs   {FALLBACK:#x}
        ldr   r1, [pc, #8]
        add   r0, r0, r0, lsl #3
        add   r0, r1, r0
        pop   {{r4, pc}}
    '''
    enc, _ = ks.asm(asm, HOOK)
    code_bytes = bytes(enc) + struct.pack('<I', table_addr)
    assert HOOK + len(code_bytes) <= 0x02043918
    a.write(HOOK, code_bytes)

    return table_addr
