import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from nitrofs import parse
rom = open(sys.argv[1],'rb').read(); out = sys.argv[2]
files, _ = parse(rom)
for fid, p, s, n in files:
    d = os.path.join(out, p); os.makedirs(os.path.dirname(d), exist_ok=True)
    open(d,'wb').write(rom[s:s+n])
print(len(files))
