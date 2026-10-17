# render BG screens after gfx.apply (in-memory): bgprev.py out.png base [base...]
import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom, gfx
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
gfx.apply(rom)
low={n.lower():n for n in (rom.filenames.filenameOf(i) for i in range(len(rom.files))) if n}
G=lambda b,e: rom.getFileByName(low[(b+e).lower()])
ims=[nitrogfx.render(nitrogfx.Screen(G(b,'.nscr')),nitrogfx.Tiles(G(b,'.ncgr')),
                     nitrogfx.Palette(G(b,'.nclr'))) for b in sys.argv[2:]]
cols=2; m=Image.new('RGB',(cols*260,((len(ims)+cols-1)//cols)*196))
for i,im in enumerate(ims): m.paste(im,(i%cols*260,i//cols*196))
m.save(sys.argv[1])
