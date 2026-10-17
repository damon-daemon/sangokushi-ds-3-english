# render edited sheets after gfx.apply (in-memory)
import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom, gfx
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
gfx.apply(rom)
out=sys.argv[1]; names=sys.argv[2:]
low={rom.filenames.filenameOf(i).lower():rom.filenames.filenameOf(i) for i in range(len(rom.files)) if rom.filenames.filenameOf(i)}
ims=[]
for n in names:
    b=n.rsplit('.',1)[0]
    t=nitrogfx.Tiles(rom.getFileByName(low[n.lower()])); c=nitrogfx.Cells(rom.getFileByName(low[(b+'.ncer').lower()]))
    pl=low.get((b+'.nclr').lower()) or [v for k,v in low.items() if k.endswith('.nclr') and k.rsplit('/',1)[0]==b.lower().rsplit('/',1)[0]][0]
    ims.append(nitrogfx.sheet_with_cells(t,c,nitrogfx.Palette(rom.getFileByName(pl))))
H=max(i.height for i in ims); m=Image.new('RGB',(sum(i.width+4 for i in ims),H))
x=0
for i in ims: m.paste(i,(x,0)); x+=i.width+4
crop=int(sys.argv[0+0] and 0) 
m.save(out)
