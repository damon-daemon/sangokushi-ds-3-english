"""Find virtual calls through a vtable slot: ldr rX,[rY,#slot] followed (within 3 insns) by blx rX.
usage: vcalls.py slot binfile:base ..."""
import re, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
slot = int(sys.argv[1], 0)
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
for spec in sys.argv[2:]:
    path, base = spec.rsplit(':', 1); base = int(base, 0)
    d = open(path, 'rb').read()
    ins = []
    for off in range(0, len(d) - 3, 4):   # per word: capstone stops at the first undecodable word
        ins.extend(md.disasm_lite(d[off:off + 4], base + off, 1))
    for k, (a, size, m, o) in enumerate(ins):
        mm = re.fullmatch(r'(\w+), \[(\w+), #(0x[0-9a-f]+|\d+)\]', o)
        if m == 'ldr' and mm and int(mm.group(3), 0) == slot:
            reg = mm.group(1)
            for a2, _, m2, o2 in ins[k + 1:k + 4]:
                if m2 == 'blx' and o2 == reg:
                    print('%s %08x' % (path.rsplit('/', 1)[-1], a2)); break
