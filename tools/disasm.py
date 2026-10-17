"""usage: dis.py binfile base start end   (ARM mode, resolves pc-relative literals)"""
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
d = open(sys.argv[1], 'rb').read(); base = int(sys.argv[2], 0)
start, end = int(sys.argv[3], 0), int(sys.argv[4], 0)
md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
for ins in md.disasm(d[start - base:end - base], start):
    extra = ''
    if ins.mnemonic.startswith('ldr') and '[pc, #' in ins.op_str:
        a = ins.address + 8 + int(ins.op_str.split('#')[-1].rstrip(']'), 0)
        extra = '   ; =0x%08x' % int.from_bytes(d[a - base:a - base + 4], 'little')
    print('%08x  %-8s %s%s' % (ins.address, ins.mnemonic, ins.op_str, extra))
