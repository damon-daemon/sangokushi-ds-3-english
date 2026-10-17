"""Redraw text baked into BG screens (NSCR + NCGR + NCLR).

The screen is flattened to one indexed bitmap (palette bank * 16 + index for 4bpp),
edited, and written back into the tiles it uses. Edited tiles must be used by one
screen cell only (true of the full-screen 8bpp startup art); anything else raises.

Ops:
  ('erase', (x, y, w, h), dx[, dy])  copy the background from (x + dx, y + dy)
  ('inpaint', (x, y, w, h), pred, grow)  rebuild the pixels matching pred ('dark',
                                      'bright', 'yellow'), grown by grow px, from
                                      their surroundings
  ('text', (x, y, w, h), text, style[, align])  draw text centred vertically,
                                      aligned 'left' (default), 'center' or 'right'
Styles give RGB colours, mapped to the nearest palette entry:
  font 'plain' (font6x12) or 'bold' (gfxtext bold caps / emboldened lowercase),
  fill = top-to-bottom gradient, outline = 1px ring around the glyphs.
"""
import os, sys
import ndspy.lz10
sys.path.insert(0, os.path.dirname(__file__))
import nitrogfx, gfxtext

class BG:
    def __init__(self, scr, chr_, pal):
        self.scr, self.t, self.pal = nitrogfx.Screen(scr), nitrogfx.Tiles(chr_), nitrogfx.Palette(pal)
        s = self.scr
        self.w, self.h = s.w, s.h
        self.px = [0] * (self.w * self.h)
        self.banks = [0] * (self.w * self.h)
        tw = self.w // 8
        for n in range(tw * (self.h // 8)):
            e = s.map[n]
            ti, hf, vf, pn = e & 0x3FF, e >> 10 & 1, e >> 11 & 1, e >> 12
            t = self.t.tile(ti)
            for y in range(8):
                for x in range(8):
                    c = t[(7 - y if vf else y) * 8 + (7 - x if hf else x)]
                    i = (n // tw * 8 + y) * self.w + n % tw * 8 + x
                    self.px[i] = c
                    self.banks[i] = pn
        self.orig = list(self.px)

    @classmethod
    def from_pixels(cls, px, w, h, colors, bpp=8, bank=0):
        """Wrap a plain indexed bitmap (e.g. an OBJ cell) so the inpaint/text ops work on it."""
        bg = object.__new__(cls)
        bg.w, bg.h, bg.px, bg.orig = w, h, list(px), list(px)
        bg.banks = [bank] * (w * h)
        bg.t = type('T', (), {'bpp': bpp})()
        bg.pal = type('P', (), {'colors': colors})()
        return bg

    def color(self, rgb, at):
        """Nearest palette index to rgb within the bank used at pixel index at."""
        if self.t.bpp == 8:
            cand = range(1, min(256, len(self.pal.colors)))
            base = 0
        else:
            base = self.banks[at] * 16
            cand = range(base + 1, base + 16)
        c = min(cand, key=lambda k: sum((a - b) ** 2 for a, b in zip(self.pal.colors[k], rgb)))
        return c - base

    def fill(self, box, rgb=None):
        """Fill box with the colour nearest rgb, or index 0 (transparent) when rgb is None."""
        x0, y0, w, h = box
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                i = y * self.w + x
                self.px[i] = 0 if rgb is None else self.color(rgb, i)

    def rect(self, box, rgb, t=1):
        """Outline a box with a t px border."""
        x0, y0, w, h = box
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                if x < x0 + t or x >= x0 + w - t or y < y0 + t or y >= y0 + h - t:
                    i = y * self.w + x
                    self.px[i] = self.color(rgb, i)

    def erase(self, box, dx, dy=0):
        x0, y0, w, h = box
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                self.px[y * self.w + x] = self.orig[(y + dy) * self.w + x + dx]

    PRED = {'dark': lambda r, g, b: r + g + b < 120,
            'bright': lambda r, g, b: r + g + b > 480,
            'gold': lambda r, g, b: r > 150 and g > 120 and r > b + 30,
            'light': lambda r, g, b: r + g + b > 300,
            'notlight': lambda r, g, b: r + g + b < 480,
            'yellow': lambda r, g, b: r > 150 and r > b + 60,
            'blue': lambda r, g, b: b > 200 and b > r + 30,
            'pink': lambda r, g, b: r > 200 and r > g + 25}

    def rgb(self, i):
        base = 0 if self.t.bpp == 8 else self.banks[i] * 16
        return self.pal.colors[base + self.orig[i]]

    def inpaint(self, box, pred, grow=1):
        x0, y0, w, h = box
        p = self.PRED[pred]
        mask = {(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w) if p(*self.rgb(y * self.w + x))}
        inside = lambda q: x0 <= q[0] < x0 + w and y0 <= q[1] < y0 + h
        for _ in range(grow):
            mask |= {(x + dx, y + dy) for x, y in mask for dx in (-1, 0, 1) for dy in (-1, 0, 1) if inside((x + dx, y + dy))}
        val = {}
        todo = set(mask)
        known = lambda q: q not in todo and inside(q)      # only sample from inside the box
        get = lambda q: val[q] if q in val else self.rgb(q[1] * self.w + q[0])
        while todo:                        # onion peel: average known neighbours
            layer = {}
            for x, y in todo:
                nb = [get(q) for q in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
                                       (x - 1, y - 1), (x + 1, y + 1), (x - 1, y + 1), (x + 1, y - 1)) if known(q)]
                if len(nb) >= 2 or (nb and len(todo) < 50):
                    layer[(x, y)] = tuple(sum(c[k] for c in nb) / len(nb) for k in range(3))
            if not layer:
                layer = {q: (0, 0, 0) for q in todo}
            val.update(layer)
            todo -= set(layer)
        for _ in range(3):                 # smooth the filled area
            val = {(x, y): tuple(sum(c[k] for c in nb) / len(nb) for k in range(3))
                   for (x, y) in val for nb in [[get(q) for q in ((x, y), (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                                               if inside(q)]]}
        for (x, y), c in val.items():
            i = y * self.w + x
            self.px[i] = self.color(c, i)

    def text(self, box, text, style, align='left'):
        bx, by, bw, bh = box
        m = gfxtext.render(text.upper(), stretch=style.get('stretch', ())) if style['font'] == 'bold' else gfxtext.render_plain(text)
        if style.get('xscale', 1) > 1:
            m = [[v for v in r for _ in range(style['xscale'])] for r in m]
        if style.get('yscale', 1) > 1:
            m = [r for r in m for _ in range(style['yscale'])]
        m = gfxtext.pad(m, 1)
        ink = [y for y in range(len(m)) if any(m[y])]
        m = m[ink[0] - 1:ink[-1] + 2]
        ring = gfxtext.dilate(m)
        h, w = len(m), len(m[0])
        if w > bw or h > bh:
            raise ValueError('%r is %dx%d, box %dx%d' % (text, w, h, bw, bh))
        ox = bx + {'center': (bw - w) // 2, 'right': bw - w}.get(align, 0)
        oy = by + (bh - h) // 2
        fill = style['fill']
        for y in range(h):
            for x in range(w):
                if m[y][x]:
                    rgb = fill[min(len(fill) - 1, (y - 1) * len(fill) // max(1, h - 2))]
                elif ring[y][x]:
                    rgb = style['outline']
                else:
                    continue
                i = (oy + y) * self.w + ox + x
                self.px[i] = self.color(rgb, i)

    def save(self):
        from collections import Counter
        s, tw = self.scr, self.w // 8
        use = Counter(e & 0x3FF for e in s.map)
        for n in range(tw * (self.h // 8)):
            cells = [(n // tw * 8 + y) * self.w + n % tw * 8 + x for y in range(8) for x in range(8)]
            if all(self.px[i] == self.orig[i] for i in cells):
                continue
            e = s.map[n]
            if use[e & 0x3FF] > 1 or e & 0xC00:
                raise ValueError('cell %d,%d uses a shared or flipped tile' % (n % tw, n // tw))
            self.t.set_tile(e & 0x3FF, [self.px[i] for i in cells])
        return self.t.save()

def apply(rom, edits):
    def get(n):
        fid = rom.filenames.idOf(n)
        if fid is None:
            raise KeyError(n)
        return fid, bytes(rom.files[fid])
    low = {n.lower(): n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
    for base, ops in edits:
        bases = base if isinstance(base, tuple) else (base,) * 3     # (screen, chars, palette)
        sf, scr = get(low[bases[0].lower() + '.nscr'])
        cf, chr_ = get(low[bases[1].lower() + '.ncgr'])
        pf, pal = get(low[bases[2].lower() + '.nclr'])
        bg = BG(scr, chr_, pal)
        for op in ops:
            getattr(bg, op[0])(*op[1:])
        out = bg.save()
        rom.files[cf] = ndspy.lz10.compress(out) if chr_[:1] == b'\x10' else out
    return len(edits)
