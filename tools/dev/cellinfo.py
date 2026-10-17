import sys; sys.path.insert(0,'tools')
import nitrogfx, ndspy.rom
rom=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds')
low={rom.filenames.filenameOf(i).lower():rom.filenames.filenameOf(i) for i in range(len(rom.files)) if rom.filenames.filenameOf(i)}
for b in sys.argv[1:]:
    c=nitrogfx.Cells(rom.getFileByName(low[(b+'.ncer').lower()]))
    print('==',b,len(c.cells))
    for i,cell in enumerate(c.cells):
        if not cell: continue
        xs=[o['tile']%32*8 for o in cell]; ys=[o['tile']//32*8 for o in cell]
        x1=max(o['tile']%32*8+o['w'] for o in cell); y1=max(o['tile']//32*8+o['h'] for o in cell)
        print(i,(min(xs),min(ys),x1-min(xs),y1-min(ys)),'pal',sorted({o['pal'] for o in cell}),'n',len(cell))
