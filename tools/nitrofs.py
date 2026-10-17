import struct, sys, os
def parse(rom):
    h = rom[:0x200]
    fnt_off, fnt_sz, fat_off, fat_sz = struct.unpack_from('<IIII', h, 0x40)
    fnt = rom[fnt_off:fnt_off+fnt_sz]; fat = rom[fat_off:fat_off+fat_sz]
    files = []
    def walk(dir_id, path):
        off, first, _ = struct.unpack_from('<IHH', fnt, (dir_id & 0xfff)*8)
        fid = first
        while True:
            l = fnt[off]; off += 1
            if l == 0: break
            name = fnt[off:off+(l&0x7f)].decode('shift_jis','replace'); off += l&0x7f
            if l & 0x80:
                sub = struct.unpack_from('<H', fnt, off)[0]; off += 2
                walk(sub, path+name+'/')
            else:
                s, e = struct.unpack_from('<II', fat, fid*8)
                files.append((fid, path+name, s, e-s)); fid += 1
    walk(0xF000, '')
    return files, h
if __name__ == '__main__':
    rom = open(sys.argv[1],'rb').read()
    files, h = parse(rom)
    print('arm9 off/size', hex(struct.unpack_from('<I',h,0x20)[0]), hex(struct.unpack_from('<I',h,0x2c)[0]))
    print('arm7 size', hex(struct.unpack_from('<I',h,0x3c)[0]), 'ovt9 size', hex(struct.unpack_from('<I',h,0x54)[0]))
    for f in files: print(f[0], f[1], f[3], rom[f[2]:f[2]+4])
