"""Find ARM-mode BL/B calls to a target address.  usage: xref.py target binfile:base ..."""
import struct, sys
target = int(sys.argv[1], 0)
for spec in sys.argv[2:]:
    path, base = spec.rsplit(':', 1); base = int(base, 0)
    d = open(path, 'rb').read()
    for off in range(0, len(d) - 3, 4):
        w = struct.unpack_from('<I', d, off)[0]
        if (w >> 24) & 0x0F in (0x0A, 0x0B) and (w >> 28) != 0xF:
            imm = w & 0xFFFFFF
            if imm & 0x800000: imm -= 1 << 24
            if base + off + 8 + imm * 4 == target:
                print('%s %08x %s' % (path.rsplit('/', 1)[-1], base + off, 'bl' if (w >> 24) & 1 else 'b'))
