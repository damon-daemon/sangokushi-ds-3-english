# render VTA frames after gfx.apply: vtaprev.py out.png base [--orig]
import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom, gfx
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
if '--orig' not in sys.argv: gfx.apply(rom)
low={n.lower():n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
b=sys.argv[2]
G=lambda e: rom.getFileByName(low[(b+e).lower()])
t=nitrogfx.Tiles(G('.ncbr')); c=nitrogfx.Cells(G('.ncer')); p=nitrogfx.Palette(G('.nclr'))
frames=gfx.vta_frames(t,c); nf=len(frames)
W=max(f[0] for f in frames); H=max(f[1] for f in frames)
cols=max(1,512//(W+4)); M=Image.new('RGB',(cols*(W+4),((nf+cols-1)//cols)*(H+4)))
for f in range(nf):
  w,h,read,_=frames[f]; img=read(); pal=c.cells[min(f,len(c.cells)-1)][0]['pal']
  im=Image.new('RGB',(W,H))
  for y in range(h):
    for x in range(w): im.putpixel((x,y),p.colors[(0 if t.bpp==8 else pal*16)+img[y][x]])
  M.paste(im,(f%cols*(W+4),f//cols*(H+4)))
M.resize((M.width*2,M.height*2),Image.NEAREST).save(sys.argv[1])
