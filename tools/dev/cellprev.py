# render NCBR (2D linear) cells after gfx.apply: cellprev.py out.png base first last [--orig]
import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom, gfx
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
if '--orig' not in sys.argv: gfx.apply(rom)
low={n.lower():n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
b=sys.argv[2]; G=lambda e: rom.getFileByName(low[(b+e).lower()])
c=nitrogfx.Cells(G('.ncer')); t=nitrogfx.Tiles(G('.ncbr'))
import os
pl=low.get((b+'.nclr').lower()) or [v for k,v in low.items() if k.endswith('.nclr') and os.path.dirname(k)==os.path.dirname(b.lower())][0]
p=nitrogfx.Palette(rom.getFileByName(pl))
px=[]
for q in t.data: px+=[q&15,q>>4]
ims=[]
for i in range(int(sys.argv[3]),int(sys.argv[4])+1):
  oams=c.cells[i]
  if not oams: continue
  x0=min(o['x'] for o in oams); y0=min(o['y'] for o in oams)
  W=max(o['x']+o['w'] for o in oams)-x0; H=max(o['y']+o['h'] for o in oams)-y0
  im=Image.new('RGB',(W,H),(30,30,60))
  for o in reversed(oams):
    tx,ty=o['tile']%32*8,o['tile']//32*8
    for y in range(o['h']):
      for x in range(o['w']):
        v=px[(ty+y)*256+tx+x]
        if v: im.putpixel((o['x']-x0+(o['w']-1-x if o['hf'] else x),o['y']-y0+(o['h']-1-y if o['vf'] else y)),p.colors[o['pal']*16+v])
  ims.append(im)
cols=6; cw=max(i.width for i in ims)+4; ch=max(i.height for i in ims)+4
M=Image.new('RGB',(cols*cw,((len(ims)+cols-1)//cols)*ch))
for k,im in enumerate(ims): M.paste(im,(k%cols*cw,k//cols*ch))
M.resize((M.width*2,M.height*2),Image.NEAREST).save(sys.argv[1])
