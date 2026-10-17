# Find unedited files that still contain art from edited graphics files (duplicate sheets).
import sys; sys.path.insert(0,'tools')
import ndspy.rom, ndspy.lz10
a=ndspy.rom.NintendoDSRom.fromFile('sangokushi_ds_3.nds'); b=ndspy.rom.NintendoDSRom.fromFile('build/sangokushi_ds_3_en.nds')
def un(d):
    d=bytes(d)
    if d[:1]==b'\x10':
        try: return ndspy.lz10.decompress(d)
        except Exception: pass
    return d
gfx=lambda n: n and n.lower().rsplit('.',1)[-1] in ('ncgr','ncbr')
A={i:un(a.files[i]) for i in range(len(a.files)) if gfx(a.filenames.filenameOf(i))}
changed=[i for i in A if bytes(a.files[i])!=bytes(b.files[i])]
unchanged=[i for i in A if i not in changed]
for i in changed:
    oa, ob = A[i], un(b.files[i])
    # sample changed 64-byte chunks of the original
    chunks=[oa[k:k+64] for k in range(0,min(len(oa),len(ob))-64,64) if oa[k:k+64]!=ob[k:k+64] and oa[k:k+64].count(0)<40][:40]
    hits={}
    for j in unchanged:
        n=sum(1 for c in chunks if c in A[j])
        if n>=3: hits[a.filenames.filenameOf(j)]=n
    if hits: print(a.filenames.filenameOf(i),'->',hits)
