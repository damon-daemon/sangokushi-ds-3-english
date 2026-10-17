import sys,os,re; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom
from PIL import Image
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
out=sys.argv[1]; pref=sys.argv[2:]
names=[rom.filenames.filenameOf(i) for i in range(len(rom.files))]
names=[n for n in names if n and any(n.startswith(p) for p in pref)]
low={n.lower():n for n in names}
def find(base,exts):
    for e in exts:
        n=low.get((base+e).lower())
        if n: return n
for n in names:
    b,e=os.path.splitext(n); el=e.lower()
    try:
        if el=='.ncbr' or (el=='.ncgr' and find(b,['.ncer'])):
            ce=find(b,['.ncer']); pl=find(b,['.nclr'])
            if not pl:
                cand=[x for x in names if x.lower().endswith('.nclr') and os.path.dirname(x)==os.path.dirname(n)]
                pl=cand[0] if cand else None
            if not pl or not ce: continue
            t=nitrogfx.Tiles(rom.getFileByName(n)); c=nitrogfx.Cells(rom.getFileByName(ce)); p=nitrogfx.Palette(rom.getFileByName(pl))
            if t.tiled:
                img=nitrogfx.sheet_with_cells(t,c,p)
            else: continue
        elif el=='.nscr':
            ch=find(b,['.ncgr']) or find(re.sub(r'\d+$','',b)+'00',['.ncgr']) or find(re.sub(r'\d+$','00',b),['.ncgr'])
            pl=find(b,['.nclr']) or (find(ch[:-5],['.nclr']) if ch else None)
            if not ch or not pl: continue
            img=nitrogfx.render(nitrogfx.Screen(rom.getFileByName(n)),nitrogfx.Tiles(rom.getFileByName(ch)),nitrogfx.Palette(rom.getFileByName(pl)))
        else: continue
        fn=os.path.join(out,n.replace('/','__')+'.png'); img.save(fn); print(fn.split('/')[-1], img.size)
    except Exception as ex:
        print('ERR',n,ex)
