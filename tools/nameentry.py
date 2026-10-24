"""Name entry (officer editor name, Hero Battle Road army name): Latin letters.

The stock screens only offer kana and kanji: an index page of hiragana (nameset)
opens a candidate list (nameinput) for the tapped kana; its 記号 cell opens a
list of full-width letters, digits, symbols and level-2 kanji, built from four
SJIS code ranges and filtered by the font. All the editing code (append, delete,
cursor, drawing) assumes 2-byte characters, and the full-width Latin glyphs
are gone (patch_arm9 stores the ASCII font over them).

So each Latin character is entered as the pair 0x7F + ASCII. 0x7F is a blank
glyph of width 0, so the pair draws as the plain letter and the 2-byte engine
works unchanged. The 記号 page lists 0x7F20-0x7F7A, the name screens open on
it, and the 0x7F bytes are stripped when the name is stored (and re-added when
an existing name is edited). Names hold up to 8 characters (stock: 4).
"""
import struct
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
import ndspy.code

PAD = 0x7F

SYMBOL_RANGES = 0x020FA04C     # 4 x (u16 lo, u16 hi) for the 記号 page
SYMBOL_FILTER = 0x020B68C8     # bl has_glyph (range codes only; kana variants are unfiltered)
SYMBOL_LABEL = 0x02104908      # "記号" on the index page (8-byte slot)
FIRST_SCREEN = 0x020FA040      # u32 first screen per mode: 0 name, 1 reading, 2 army name
OPEN_FIRST = 0x020B2A50        # bl open_screen(ctrl, screen) at the start of entry
OPEN_SCREEN = 0x020B2B00
BUILD_LIST = 0x020B691C        # build_list(nameinput, key): what the controller calls on code 3
INIT_COPY = 0x020B2A30         # bl strcpy(buf, initial text)
STAY_OPEN = 0x020B6030         # str r3, [r2, #0x14]: after a pick, go back to the index page
MAX_CHARS = [0x020B5FF8]       # mov r2, #4: append limit on nameinput
CELLS = [0x020B604C, 0x020B63BC, 0x020B4FC0, 0x020B53F0]          # mov r3, #4: typed-name cells
STRIDE = {0x020B63A8: 'r1', 0x020B53DC: 'r1', 0x020B63D4: 'r0', 0x020B5408: 'r0'}  # mov rX, #0x13
OV5_STORE = 0x021315E0         # bl strncpy(record buf, name, 9)
OV4_STORE = 0x0212568C         # bl set_army_name(obj, name): copies 8 + NUL
SET_ARMY_NAME = 0x020CCF24
# Registering a new officer requires a non-empty name and reading (vt+0x140).
# patch_arm9 points that getter at the record's last byte (always empty) to hide
# English names spilling into the reading, so check the name twice instead.
OV5_READING_CHECK = 0x021346D8 # ldr r2, [r2, #0x140]
STRNCPY = 0x0200F7E4
STRCPY = 0x0200F7B0
HAS_GLYPH = 0x020B67C8

STOCK_RANGES = bytes.fromhex('4f82 5882 6082 9a82 4181 4e82 9f98 4ffc')
RANGES = [(0x7F41, 0x7F5A), (0x7F61, 0x7F7A), (0x7F30, 0x7F39), (0x7F20, 0x7F2E)]  # A-Z a-z 0-9 space-.
CELLS_N = 8
STRIDE_PX = 9                  # 8 cells in the box drawn for 4 x 19 px

# A lead byte is 0x81-0x9F or 0xE0-0xFC: ((c ^ 0x20) - 0xA1) < 0x3C, unsigned.
CAVES = {
    # strip(dst, src, n): copy without 0x7F, at most n-1 bytes, never splitting a
    # 2-byte character; always NUL-terminated. dst may equal src.
    'strip': '''
        sub   r2, r2, #1
    loop: ldrb r3, [r1], #1
        cmp   r3, #0x7f
        beq   loop
        eor   ip, r3, #0x20
        sub   ip, ip, #0xa1
        cmp   ip, #0x3c
        sublo r2, r2, #1
        subs  r2, r2, #1
        movmi r3, #0
        strb  r3, [r0], #1
        cmp   r3, #0
        bxeq  lr
        cmp   ip, #0x3c
        ldrblo r3, [r1], #1
        strblo r3, [r0], #1
        b     loop
    ''',
    # Battle Road army name: strip in place, then the stock setter.
    'army': '''
        push  {r0, r1, lr}
        mov   r0, r1
        mov   r2, #9
        bl    {strip}
        pop   {r0, r1, lr}
        b     %#x
    ''' % SET_ARMY_NAME,
    # expand(dst, src): strcpy that pads single-byte characters to 0x7F + c,
    # stopping at 16 bytes (8 characters; buf is 20). Returns dst.
    'expand': '''
        push  {r0}
        add   r2, r0, #16
    loop: ldrb r3, [r1], #1
        cmp   r0, r2
        movhs r3, #0
        cmp   r3, #0
        strbeq r3, [r0]
        popeq {r0}
        bxeq  lr
        eor   ip, r3, #0x20
        sub   ip, ip, #0xa1
        cmp   ip, #0x3c
        strblo r3, [r0], #1
        ldrblo r3, [r1], #1
        movhs ip, #0x7f
        strbhs ip, [r0], #1
        strb  r3, [r0], #1
        b     loop
    ''',
    # Opening straight on the candidate screen: build its list as the controller
    # does after switching to it (key 0 = the Latin page).
    'open': '''
        push  {r0, r1, lr}
        bl    %#x
        pop   {r0, r1}
        cmp   r1, #2
        popne {pc}
        ldr   r0, [r0, #0x50]
        cmp   r0, #0
        movne r1, #0
        blne  %#x
        pop   {pc}
    ''' % (OPEN_SCREEN, BUILD_LIST),
}

def _asm(ks, src, addr):
    return bytes(ks.asm(src, addr)[0])

def _check(a9, ks, addr, src):
    assert a9.read(addr, 4) == _asm(ks, src, addr), '%#x: expected %s' % (addr, src)

def apply(rom, a9, free):
    """Patch arm9 (an Arm9 wrapper) and overlays 4/5. free: list of [lo, hi) spans
    of unused arm9 bytes for the code caves (taken from the front)."""
    ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)

    # code caves (sizes first, then place: 'army' calls 'strip')
    sizes = {k: len(_asm(ks, v.replace('{strip}', '0x02000000'), 0x02000000)) for k, v in CAVES.items()}
    addr = {}
    for k in sorted(sizes, key=lambda k: -sizes[k]):
        for g in sorted(free, key=lambda g: g[1] - g[0]):
            lo = (g[0] + 3) & ~3
            if g[1] - lo >= sizes[k]:
                addr[k] = lo; g[0] = lo + sizes[k]
                break
        else:
            raise ValueError('nameentry: no free arm9 space for %s (%d bytes)' % (k, sizes[k]))
    for k, src in CAVES.items():
        code = _asm(ks, src.replace('{strip}', '%#x' % addr['strip']), addr[k])
        assert len(code) == sizes[k]
        a9.write(addr[k], code)

    # Latin page: four 0x7F + ASCII ranges, no font filter; index-page label
    assert a9.read(SYMBOL_RANGES, 16) == STOCK_RANGES
    a9.write(SYMBOL_RANGES, b''.join(struct.pack('<HH', lo, hi) for lo, hi in RANGES))
    _check(a9, ks, SYMBOL_FILTER, 'bl %#x' % HAS_GLYPH)
    a9.write(SYMBOL_FILTER, _asm(ks, 'mov r0, #1', SYMBOL_FILTER))
    assert a9.read(SYMBOL_LABEL, 8) == '記号'.encode('shift_jis') + b'\0' * 4
    a9.write(SYMBOL_LABEL, b'ABC'.ljust(8, b'\0'))

    # open on the Latin page for names; the reading (mode 1) keeps its katakana screen
    assert struct.unpack('<3I', a9.read(FIRST_SCREEN, 12)) == (1, 0, 1)
    a9.write(FIRST_SCREEN, struct.pack('<3I', 2, 0, 2))
    _check(a9, ks, OPEN_FIRST, 'bl %#x' % OPEN_SCREEN)
    a9.write(OPEN_FIRST, _asm(ks, 'bl %#x' % addr['open'], OPEN_FIRST))
    # stay on the candidate page after each pick (Back still returns to the index)
    _check(a9, ks, STAY_OPEN, 'str r3, [r2, #0x14]')
    a9.write(STAY_OPEN, _asm(ks, 'nop', STAY_OPEN))

    # 8 characters, drawn 9 px apart
    for p in MAX_CHARS:
        _check(a9, ks, p, 'mov r2, #4'); a9.write(p, _asm(ks, 'mov r2, #%d' % CELLS_N, p))
    for p in CELLS:
        _check(a9, ks, p, 'mov r3, #4'); a9.write(p, _asm(ks, 'mov r3, #%d' % CELLS_N, p))
    for p, r in STRIDE.items():
        _check(a9, ks, p, 'mov %s, #0x13' % r); a9.write(p, _asm(ks, 'mov %s, #%d' % (r, STRIDE_PX), p))

    # existing names come in as plain ASCII: pad them to pairs
    _check(a9, ks, INIT_COPY, 'bl %#x' % STRCPY)
    a9.write(INIT_COPY, _asm(ks, 'bl %#x' % addr['expand'], INIT_COPY))

    # store: strip the 0x7F pads
    ovs = rom.loadArm9Overlays()
    o = ovs[5]; off = OV5_READING_CHECK - o.ramAddress
    assert bytes(o.data[off:off + 4]) == _asm(ks, 'ldr r2, [r2, #0x140]', OV5_READING_CHECK)
    o.data[off:off + 4] = _asm(ks, 'ldr r2, [r2, #0x134]', OV5_READING_CHECK)
    for ov, site, old, new in [(5, OV5_STORE, STRNCPY, addr['strip']), (4, OV4_STORE, SET_ARMY_NAME, addr['army'])]:
        o = ovs[ov]; off = site - o.ramAddress
        assert bytes(o.data[off:off + 4]) == _asm(ks, 'bl %#x' % old, site), 'ov%d %#x' % (ov, site)
        o.data[off:off + 4] = _asm(ks, 'bl %#x' % new, site)
        rom.files[o.fileID] = o.save(compress=True)
    rom.arm9OverlayTable = ndspy.code.saveOverlayTable(ovs)
    return addr
