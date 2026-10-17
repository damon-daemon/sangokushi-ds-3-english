# render 1D-mapped NCGR OBJ cells after gfx.apply: objprev.py out.png base [base...]
import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom, gfx
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
if '--orig' not in sys.argv: gfx.apply(rom)
low={n.lower():n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
G=lambda b,e: rom.getFileByName(low[(b+e).lower()])
rows=[]
for b in [a for a in sys.argv[2:] if a != '--orig']:
  t=nitrogfx.Tiles(G(b,'.ncgr')); p=nitrogfx.Palette(G(b,'.nclr')); c=nitrogfx.Cells(G(b,'.ncer'))
  ims=[i for i in (nitrogfx.render_cell(c,t,p,i) for i in range(len(c.cells))) if i and i.width<300]
  W=sum(i.width+3 for i in ims); H=max(i.height for i in ims)
  m=Image.new('RGBA',(W,H),(60,60,60,255)); x=0
  for i in ims: m.paste(i,(x,0),i); x+=i.width+3
  rows.append(m)
M=Image.new('RGBA',(max(r.width for r in rows),sum(r.height+2 for r in rows)),(0,0,0,255)); y=0
for r in rows: M.paste(r,(0,y)); y+=r.height+2
M.resize((M.width*3,M.height*3),Image.NEAREST).save(sys.argv[1])
