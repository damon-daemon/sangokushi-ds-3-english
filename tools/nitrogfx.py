"""Nitro 2D graphics: NCLR palettes, NCGR tiles, NSCR screens (often LZ10-wrapped).

  render <base> <out.png> [--rom rom.nds]   base = path without extension,
      e.g. Stg/BG_stg_down_main_cmd00 -> draws the screen with its tiles/palette
  tiles <ncgr> <nclr> <out.png> [pal]        dump the raw tile sheet
"""
import struct, sys
import ndspy.lz10, ndspy.rom
from PIL import Image

def unwrap(b):
    b = bytes(b)
    if b[:1] == b'\x10' and b[:4] not in (b'RLCN', b'RGCN', b'RCSN'):
        try:
            return ndspy.lz10.decompress(b)
        except Exception:
            pass
    return b

def blocks(b):
    """Nitro container -> {magic: (offset_of_block_data, data)}."""
    hsize = struct.unpack_from('<H', b, 12)[0]
    nblk = struct.unpack_from('<H', b, 14)[0]
    o, out = hsize, {}
    for _ in range(nblk):
        magic = b[o:o + 4][::-1].decode()
        size = struct.unpack_from('<I', b, o + 4)[0]
        out[magic] = (o + 8, b[o + 8:o + size])
        o += size
    return out

class Palette:
    def __init__(self, b):
        b = unwrap(b)
        _, d = blocks(b)['PLTT']
        depth, _, size, off = struct.unpack_from('<IIII', d, 0)
        raw = d[off:off + size]
        self.colors = []
        for i in range(0, len(raw) - 1, 2):
            v = struct.unpack_from('<H', raw, i)[0]
            self.colors.append(((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31))
        self.bpp = 4 if depth == 3 else 8

class Tiles:
    def __init__(self, b):
        self.file = unwrap(b)
        blk = blocks(self.file)
        self.char_off, d = blk['CHAR']
        self.h, self.w, depth, _, self.tiled, size, off = struct.unpack_from('<HHIIIII', d, 0)
        self.bpp = 4 if depth == 3 else 8
        self.data_off = self.char_off + off
        self.data = bytearray(self.file[self.data_off:self.data_off + size])
        self.tsize = 32 if self.bpp == 4 else 64
        self.count = len(self.data) // self.tsize
    def tile(self, i):
        t = self.data[i * self.tsize:(i + 1) * self.tsize]
        if self.bpp == 8:
            return list(t)
        px = []
        for c in t:
            px += [c & 15, c >> 4]
        return px
    def set_tile(self, i, px):
        if self.bpp == 8:
            b = bytes(px)
        else:
            b = bytes(px[k] | px[k + 1] << 4 for k in range(0, 64, 2))
        self.data[i * self.tsize:(i + 1) * self.tsize] = b
    def save(self):
        f = bytearray(self.file)
        f[self.data_off:self.data_off + len(self.data)] = self.data
        return bytes(f)

class Screen:
    def __init__(self, b):
        b = unwrap(b)
        _, d = blocks(b)['SCRN']
        self.w, self.h, _, size = struct.unpack_from('<HHII', d, 0)
        self.map = list(struct.unpack_from('<%dH' % (size // 2), d, 12))

def render(scr, tiles, pal):
    img = Image.new('RGB', (scr.w, scr.h))
    tw = scr.w // 8
    for n, e in enumerate(scr.map):
        if n >= tw * (scr.h // 8):
            break
        ti, hf, vf, pn = e & 0x3FF, e >> 10 & 1, e >> 11 & 1, e >> 12
        px = tiles.tile(ti) if ti < tiles.count else [0] * 64
        base = pn * 16 if tiles.bpp == 4 else 0
        for y in range(8):
            for x in range(8):
                sx, sy = (7 - x if hf else x), (7 - y if vf else y)
                c = px[sy * 8 + sx]
                col = pal.colors[base + c] if base + c < len(pal.colors) else (255, 0, 255)
                img.putpixel(((n % tw) * 8 + x, (n // tw) * 8 + y), col)
    return img

def sheet(tiles, pal, pn=0, per_row=32):
    rows = (tiles.count + per_row - 1) // per_row
    img = Image.new('RGB', (per_row * 8, rows * 8))
    for i in range(tiles.count):
        px = tiles.tile(i)
        for y in range(8):
            for x in range(8):
                c = px[y * 8 + x] + (pn * 16 if tiles.bpp == 4 else 0)
                img.putpixel(((i % per_row) * 8 + x, (i // per_row) * 8 + y), pal.colors[c] if c < len(pal.colors) else (255, 0, 255))
    return img

if __name__ == '__main__':
    rom = ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
    get = lambda n: rom.getFileByName(n)
    if sys.argv[1] == 'render':
        base = sys.argv[2]
        img = render(Screen(get(base + '.nscr')), Tiles(get(base + '.ncgr')), Palette(get(base + '.nclr')))
        img.save(sys.argv[3])
    elif sys.argv[1] == 'tiles':
        pn = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        sheet(Tiles(get(sys.argv[2])), Palette(get(sys.argv[3])), pn).save(sys.argv[4])

OBJ_SIZES = {(0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
             (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
             (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64)}

class Cells:
    """NCER cell bank: list of cells, each a list of OAM dicts."""
    def __init__(self, b):
        b = unwrap(b)
        self.file = bytearray(b)
        self.cebk_off, d = blocks(b)['CEBK']
        n, ext, off, self.mapping = struct.unpack_from('<HHII', d, 0)
        esz = 16 if ext == 1 else 8
        oam_base = off + n * esz
        self.cells = []
        for i in range(n):
            no, attr, oo = struct.unpack_from('<HHI', d, off + i * esz)
            oams = []
            for k in range(no):
                a0, a1, a2 = struct.unpack_from('<HHH', d, oam_base + oo + k * 6)
                y = a0 & 0xFF; y = y - 256 if y >= 128 else y
                x = a1 & 0x1FF; x = x - 512 if x >= 256 else x
                w, h = OBJ_SIZES[(a0 >> 14, a1 >> 14)]
                oams.append({'off': self.cebk_off + oam_base + oo + k * 6,
                             'x': x, 'y': y, 'w': w, 'h': h, 'tile': a2 & 0x3FF, 'pal': a2 >> 12,
                             'hf': a1 >> 12 & 1, 'vf': a1 >> 13 & 1, 'bpp8': a0 >> 13 & 1})
            self.cells.append(oams)

SIZE_CODES = {v: k for k, v in OBJ_SIZES.items()}

def set_oam(cells, o, x=None, y=None, w=None, h=None, tile=None):
    """Patch one OAM of cells.file in place (and its dict)."""
    for k, v in (('x', x), ('y', y), ('w', w), ('h', h), ('tile', tile)):
        if v is not None:
            o[k] = v
    a0, a1, a2 = struct.unpack_from('<HHH', cells.file, o['off'])
    shape, size = SIZE_CODES[(o['w'], o['h'])]
    a0 = a0 & 0x3F00 | o['y'] & 0xFF | shape << 14
    a1 = a1 & 0x3E00 | o['x'] & 0x1FF | size << 14
    a2 = a2 & 0xFC00 | o['tile']
    struct.pack_into('<HHH', cells.file, o['off'], a0, a1, a2)

def tile_index(cells, tiles, t):
    if not tiles.tiled:                    # character NCGR: OAM tile numbers count 32K << mapping blocks
        n = t << {1: 1, 2: 2, 3: 3}.get(cells.mapping, 0)                 # in 32-byte units
        return n // 2 if tiles.bpp == 8 else n
    shift = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3}.get(cells.mapping, 0)
    return (t << shift) * (2 if tiles.bpp == 8 else 1) if tiles.bpp == 4 else t << shift

def oam_tiles(cells, tiles, o):
    """Tile numbers of an OAM in row-major order (1D mapping)."""
    base = tile_index(cells, tiles, o['tile'])
    n = (o['w'] // 8) * (o['h'] // 8)
    return [base + k for k in range(n)]

def render_cell(cells, tiles, pal, i):
    oams = cells.cells[i]
    if not oams:
        return None
    x0 = min(o['x'] for o in oams); y0 = min(o['y'] for o in oams)
    x1 = max(o['x'] + o['w'] for o in oams); y1 = max(o['y'] + o['h'] for o in oams)
    img = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for o in reversed(oams):
        tw = o['w'] // 8
        if tiles.tiled:                    # NCBR: each OBJ stored as a linear bitmap
            base = tile_index(cells, tiles, o['tile']) * tiles.tsize
            n = o['w'] * o['h']
            raw = tiles.data[base:base + (n // 2 if tiles.bpp == 4 else n)]
            px = []
            for c in raw:
                px += [c & 15, c >> 4] if tiles.bpp == 4 else [c]
            for idx, c in enumerate(px):
                if c == 0:
                    continue
                lx, ly = idx % o['w'], idx // o['w']
                if o['hf']: lx = o['w'] - 1 - lx
                if o['vf']: ly = o['h'] - 1 - ly
                col = pal.colors[o['pal'] * 16 + c] if tiles.bpp == 4 else pal.colors[c]
                img.putpixel((o['x'] - x0 + lx, o['y'] - y0 + ly), col + (255,))
            continue
        for k, t in enumerate(oam_tiles(cells, tiles, o)):
            if t >= tiles.count:
                continue
            px = tiles.tile(t)
            for yy in range(8):
                for xx in range(8):
                    c = px[yy * 8 + xx]
                    if c == 0:
                        continue
                    lx, ly = (k % tw) * 8 + xx, (k // tw) * 8 + yy
                    if o['hf']: lx = o['w'] - 1 - lx
                    if o['vf']: ly = o['h'] - 1 - ly
                    col = pal.colors[o['pal'] * 16 + c] if tiles.bpp == 4 else pal.colors[c]
                    img.putpixel((o['x'] - x0 + lx, o['y'] - y0 + ly), col + (255,))
    return img

def sheet_with_cells(tiles, cells, pal):
    """Linear (NCBR) sheet coloured with the palette bank each OAM uses."""
    W = tiles.w * 8
    px = []
    for b in tiles.data:
        px += [b & 15, b >> 4] if tiles.bpp == 4 else [b]
    H = len(px) // W
    bank = [None] * (W * H)
    for cell in cells.cells:
        for o in cell:
            tx, ty = o['tile'] % (W // 8) * 8, o['tile'] // (W // 8) * 8
            for y in range(o['h']):
                for x in range(o['w']):
                    k = (ty + y) * W + tx + x
                    if k < len(bank):
                        bank[k] = o['pal']
    img = Image.new('RGB', (W, H))
    used = [b for b in bank if b is not None]
    default = max(set(used), key=used.count) if used else 0
    data = []
    for k, c in enumerate(px[:W * H]):
        b = bank[k] if bank[k] is not None else default
        i = (b * 16 + c) if tiles.bpp == 4 else c
        data.append(pal.colors[i] if c and i < len(pal.colors) else (40, 40, 40))
    img.putdata(data)
    return img
