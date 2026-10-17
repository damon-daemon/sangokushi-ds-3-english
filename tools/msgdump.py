import sys, struct
def entries(d):
    if len(d) < 2: return []
    n = struct.unpack_from('<H', d, 0)[0]
    offs = list(struct.unpack_from('<%dH' % n, d, 2)) + [len(d)]
    return [d[offs[i]:offs[i+1]] for i in range(len(offs)-1)]
def show(b):
    out=[]; i=0
    while i < len(b):
        c=b[i]
        if (0x81<=c<=0x9f or 0xe0<=c<=0xfc) and i+1<len(b):
            try: out.append(b[i:i+2].decode('cp932')); i+=2; continue
            except: pass
        if 0xa1<=c<=0xdf: out.append(bytes([c]).decode('cp932')); i+=1; continue
        if 0x20<=c<0x7f: out.append(chr(c)); i+=1; continue
        out.append('{%02X}'%c); i+=1
    return ''.join(out)
if __name__=='__main__':
    d=open(sys.argv[1],'rb').read()
    for n,e in enumerate(entries(d)): print(n, show(e))
