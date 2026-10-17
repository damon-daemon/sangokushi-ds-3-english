"""Draw English labels into 4bpp linear sheets (NCBR) in the game's embossed style.

Glyphs come from font6x12 (original drawings), emboldened by one column and
optionally stretched vertically. A label is filled with a vertical gradient of
palette indices, then given an inner and an outer outline, and centred in its
box (which is cleared to transparent first).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import font6x12, boldfont

# Digits and punctuation for graphics (font6x12 takes these from the ROM at build time);
# original drawings, 5 columns, caps height rows 1-9.
_D = {
    '0': ['.###.', '#...#', '#..##', '#.#.#', '#.#.#', '#.#.#', '##..#', '#...#', '.###.'],
    '1': ['..#..', '.##..', '#.#..', '..#..', '..#..', '..#..', '..#..', '..#..', '#####'],
    '2': ['.###.', '#...#', '....#', '....#', '...#.', '..#..', '.#...', '#....', '#####'],
    '3': ['.###.', '#...#', '....#', '....#', '..##.', '....#', '....#', '#...#', '.###.'],
    '4': ['...#.', '..##.', '.#.#.', '.#.#.', '#..#.', '#####', '...#.', '...#.', '...#.'],
    '5': ['#####', '#....', '#....', '####.', '....#', '....#', '....#', '#...#', '.###.'],
    '6': ['..##.', '.#...', '#....', '####.', '#...#', '#...#', '#...#', '#...#', '.###.'],
    '7': ['#####', '....#', '...#.', '...#.', '..#..', '..#..', '..#..', '.#...', '.#...'],
    '8': ['.###.', '#...#', '#...#', '#...#', '.###.', '#...#', '#...#', '#...#', '.###.'],
    '9': ['.###.', '#...#', '#...#', '#...#', '.####', '....#', '....#', '...#.', '.##..'],
    '-': ['.....', '.....', '.....', '.....', '#####', '.....', '.....', '.....', '.....'],
    '+': ['.....', '.....', '..#..', '..#..', '#####', '..#..', '..#..', '.....', '.....'],
    '/': ['....#', '....#', '...#.', '...#.', '..#..', '.#...', '.#...', '#....', '#....'],
    '(': ['...#.', '..#..', '.#...', '.#...', '.#...', '.#...', '.#...', '..#..', '...#.'],
    ')': ['.#...', '..#..', '...#.', '...#.', '...#.', '...#.', '...#.', '..#..', '.#...'],
    ',': ['.....', '.....', '.....', '.....', '.....', '.....', '.....', '..##.', '..#..', '.#...'],
    '.': ['.....', '.....', '.....', '.....', '.....', '.....', '.....', '.##..', '.##..'],
    ':': ['.....', '.....', '.##..', '.##..', '.....', '.....', '.##..', '.##..', '.....'],
}
PLAIN = {ch: (['.....'] + rows + ['.....'] * 11)[:12] for ch, rows in _D.items()}

def plain_glyph(ch):
    return PLAIN.get(ch) or font6x12.GLYPHS[ch]

def glyph(ch, bold=True, stretch=()):
    if ch in boldfont.GLYPHS:
        return [list(r) for r in boldfont.GLYPHS[ch]]
    rows = plain_glyph(ch)[1:10] if ch.isupper() or ch in "0123456789'.-&" else plain_glyph(ch)[1:12]
    g = [[c == '#' for c in r] + [False] for r in rows]
    if bold:
        g = [[r[x] or (x > 0 and r[x - 1]) for x in range(len(r))] for r in g]
    out = []
    for i, r in enumerate(g):
        out.append(r)
        if i in stretch:
            out.append(list(r))
    # trim empty columns on both sides
    cols = [x for x in range(len(out[0])) if any(r[x] for r in out)]
    if not cols:
        return [[False] * 3 for _ in out]
    return [r[cols[0]:cols[-1] + 1] for r in out]

def render(text, gap=1, stretch=(1, 4, 7)):
    gs = [glyph(c, stretch=stretch) for c in text]
    h = max(len(g) for g in gs)
    w = sum(len(g[0]) for g in gs) + gap * (len(gs) - 1)
    img = [[False] * w for _ in range(h)]
    x = 0
    for g in gs:
        off = h - len(g)
        for y, r in enumerate(g):
            for i, v in enumerate(r):
                if v:
                    img[y + off][x + i] = True
        x += len(g[0]) + gap
    return img

def dilate(mask):
    h, w = len(mask), len(mask[0])
    return [[mask[y][x] or any(0 <= y + dy < h and 0 <= x + dx < w and mask[y + dy][x + dx]
             for dy in (-1, 0, 1) for dx in (-1, 0, 1)) for x in range(w)] for y in range(h)]

def pad(mask, n):
    w = len(mask[0])
    return [[False] * (w + 2 * n) for _ in range(n)] + [[False] * n + r + [False] * n for r in mask] + \
           [[False] * (w + 2 * n) for _ in range(n)]

def draw(sheet, sheet_w, box, text, fill, inner, outer, stretch=(1, 4, 7)):
    """sheet: list of palette indices (row-major, sheet_w wide). box = (x, y, w, h)."""
    bx, by, bw, bh = box
    m = pad(render(text, stretch=stretch), 2)
    m1 = dilate(m)
    m2 = dilate(m1)
    h, w = len(m), len(m[0])
    if w > bw or h > bh:
        raise ValueError('%r is %dx%d, box %dx%d' % (text, w, h, bw, bh))
    for y in range(bh):
        for x in range(bw):
            sheet[(by + y) * sheet_w + bx + x] = 0
    ox, oy = bx + (bw - w) // 2, by + (bh - h) // 2
    ink = [y for y in range(h) if any(m[y])]
    top, bot = ink[0], ink[-1]
    for y in range(h):
        for x in range(w):
            if m[y][x]:
                t = (y - top) / max(1, bot - top)
                c = fill[min(len(fill) - 1, int(t * len(fill)))]
            elif m1[y][x]:
                c = inner
            elif m2[y][x]:
                c = outer
            else:
                continue
            sheet[(oy + y) * sheet_w + ox + x] = c

def render_plain(text):
    """Regular font6x12 glyphs (proportional), rows 1-11."""
    cols = []
    for ch in text:
        if ch == ' ':
            cols += [[False] * 11] * 3
            continue
        rows = plain_glyph(ch)[1:12]
        g = [[c == '#' for c in r] for r in rows]
        used = [x for x in range(5) if any(r[x] for r in g)] or [0]
        for x in range(used[0], used[-1] + 1):
            cols.append([r[x] for r in g])
        cols.append([False] * 11)
    cols = cols[:-1]
    h = 11
    # drop rows unused by every glyph (keeps caps-only text compact)
    m = [[cols[x][y] for x in range(len(cols))] for y in range(h)]
    return m

def draw_plate(sheet, sheet_w, box, text, fill, outline, wood, src=None, outline2=None, bold=False):
    """Repaint box with texture tiled from wood=(x, y, w) (a clean strip, bh rows tall,
    read from src, the unmodified sheet), then draw text centred with a 1px outline.
    bold uses the boldfont capitals (text is upper-cased)."""
    bx, by, bw, bh = box
    src = src or sheet
    if callable(wood):                     # wood(x, y) -> clean background index
        for y in range(bh):
            for x in range(bw):
                sheet[(by + y) * sheet_w + bx + x] = wood(x, y)
    else:
        wx, wy, ww = wood
        for y in range(bh):
            for x in range(bw):
                sheet[(by + y) * sheet_w + bx + x] = src[(wy + y) * sheet_w + wx + (x % ww)]
    m = pad(render(text.upper(), stretch=()) if bold else render_plain(text), 1)
    ink = [y for y in range(len(m)) if any(m[y])]
    m = m[ink[0] - 1:ink[-1] + 2]
    if outline2 is not None:
        m = pad(m, 1)
    m1 = dilate(m)
    m2 = dilate(m1) if outline2 is not None else m1
    h, w = len(m), len(m[0])
    if w > bw:
        raise ValueError('%r is %dpx wide, plate %dpx' % (text, w, bw))
    ox, oy = bx + (bw - w) // 2, by + (bh - h) // 2
    for y in range(h):
        for x in range(w):
            if m[y][x]:
                c = fill[min(len(fill) - 1, (y - 1) * len(fill) // max(1, h - 2))]
            elif m1[y][x]:
                c = outline
            elif m2[y][x]:
                c = outline2
            else:
                continue
            sheet[(oy + y) * sheet_w + ox + x] = c

def clean_from(sheet, sheet_w, origins, w, h):
    """Per-pixel majority over identically-drawn cells (text differs, art does not).
    Returns (clean, diffbox) with clean[y][x] and the box (x0,y0,x1,y1) where any cell differs."""
    from collections import Counter
    clean = [[0] * w for _ in range(h)]
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            vals = [sheet[(oy + y) * sheet_w + ox + x] for ox, oy in origins]
            v, n = Counter(vals).most_common(1)[0]
            clean[y][x] = v
            if n < len(vals):
                xs.append(x); ys.append(y)
    return clean, (min(xs), min(ys), max(xs) + 1, max(ys) + 1)

def clean_by_extent(sheet, sheet_w, origins, w, h, text_vals, text_rows, margin=3, fallback=None, cols=None, mirror=True):
    """Clean background for cells sharing art but with centred text: each cell's text extent is
    the columns (in text_rows) holding text_vals, widened by margin; a pixel is taken from any
    cell whose text does not cover that column, else fallback(x, y)."""
    from collections import Counter
    mode = [[Counter(sheet[(oy + y) * sheet_w + ox + x] for ox, oy in origins).most_common(1)[0][0]
             for x in range(w)] for y in range(h)]
    ext = []
    for ox, oy in origins:
        central = set(cols or ())
        cs = [x for x in range(w) if any(
            sheet[(oy + y) * sheet_w + ox + x] in text_vals and
            (x in central or sheet[(oy + y) * sheet_w + ox + x] != mode[y][x])
            for y in text_rows)]
        ext.append((min(cs) - margin, max(cs) + margin) if cs else (w, -1))
    clean = [[0] * w for _ in range(h)]
    known = [any(not a <= x <= b for a, b in ext) for x in range(w)]
    for y in range(h):
        for x in range(w):
            mx = w - 1 - x
            if known[x]:
                src = [o for o, (a, b) in zip(origins, ext) if not a <= x <= b][0]
                clean[y][x] = sheet[(src[1] + y) * sheet_w + src[0] + x]
            elif mirror and known[mx]:
                src = [o for o, (a, b) in zip(origins, ext) if not a <= mx <= b][0]
                clean[y][x] = sheet[(src[1] + y) * sheet_w + src[0] + mx]
            else:
                clean[y][x] = fallback(x, y) if fallback else 0
    lo = min(a for a, b in ext); hi = max(b for a, b in ext)
    if mirror:
        lo = max(0, min(lo, w - 1 - hi)); hi = w - 1 - lo
    return clean, (max(0, lo), 0, min(w, hi + 1), h)

def fill_gaps(clean, lo=0, hi=None):
    """Fill columns left as None by tiling the known columns in [lo, hi) to their left
    (or right, if none), so textures continue without pulling in frame edges."""
    w = len(clean[0])
    hi = w if hi is None else hi
    x = 0
    while x < w:
        if clean[0][x] is not None:
            x += 1
            continue
        e = x
        while e < w and clean[0][e] is None:
            e += 1
        cand = [j for j in range(lo, x) if clean[0][j] is not None] or \
               [j for j in range(e, hi) if clean[0][j] is not None] or \
               [j for j in range(w) if clean[0][j] is not None and not lo - 3 <= j <= hi + 3] or \
               [j for j in range(w) if clean[0][j] is not None]
        for y in range(len(clean)):
            for i in range(x, e):
                clean[y][i] = clean[y][cand[(i - x) % len(cand)]]
        x = e

def rowfill(sheet, sheet_w, box, text_vals, grow=0):
    """Clean background for box on a horizontally banded fill: pixels with a value in
    text_vals (grown by grow px within the box) take the nearest other pixel of the same
    row inside the box. Rows with no such pixel are left as they are. Returns bg(x, y)."""
    bx, by, bw, bh = box
    get = lambda x, y: sheet[(by + y) * sheet_w + bx + x]
    mask = {(x, y) for y in range(bh) for x in range(bw) if get(x, y) in text_vals}
    for _ in range(grow):
        mask |= {(x + dx, y) for x, y in mask for dx in (-1, 1) if 0 <= x + dx < bw}
    clean = [[get(x, y) for x in range(bw)] for y in range(bh)]
    for y in range(bh):
        good = [x for x in range(bw) if (x, y) not in mask]
        if not good:
            continue
        for x in range(bw):
            if (x, y) in mask:
                clean[y][x] = get(min(good, key=lambda g: (abs(g - x), g > x)), y)
    return lambda x, y: clean[y][x]

def draw_cell(img, text, fill, outline, bold=False, stretch=(), outer=None, clip=False):
    """Clear img (list of rows of indices) and draw text centred: fill gradient, 1px
    outline ring, optional second ring outer. clip lets the rings run off the edges."""
    h, w = len(img), len(img[0])
    for row in img:
        row[:] = [0] * w
    if not text.strip():
        return
    m = render(text.upper(), stretch=stretch) if bold else render_plain(text)
    rings = 2 if outer is not None else 1
    m = pad(m, rings)
    ink = [y for y in range(len(m)) if any(m[y])]
    m = m[ink[0] - rings:ink[-1] + rings + 1]
    m1 = dilate(m)
    m2 = dilate(m1) if outer is not None else m1
    mh, mw = len(m), len(m[0])
    if (mw > w or mh > h) and not (clip and mw - 2 * rings <= w and mh - 2 * rings <= h):
        raise ValueError('%r is %dx%d, cell %dx%d' % (text, mw, mh, w, h))
    ox, oy = (w - mw) // 2, (h - mh) // 2
    for y in range(mh):
        for x in range(mw):
            if not (0 <= oy + y < h and 0 <= ox + x < w):
                continue
            if m[y][x]:
                c = fill[min(len(fill) - 1, (y - rings) * len(fill) // max(1, mh - 2 * rings))]
            elif m1[y][x]:
                c = outline
            elif m2[y][x]:
                c = outer
            else:
                continue
            img[oy + y][ox + x] = c
