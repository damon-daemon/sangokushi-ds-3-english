# strw.py word ... : pixel width of strings in the game's VWF font
import sys; sys.path.insert(0,'tools')
import font6x12
W={}
for ch,rows in font6x12.GLYPHS.items():
    W[ch]=font6x12._trim(rows)[1] if ch not in font6x12.FIXED_WIDTH else 6
for c in font6x12.GAME_GLYPHS: W.setdefault(c,6)
for s in sys.argv[1:]: print('%3d %s'%(sum(W.get(c,6) for c in s), s))
