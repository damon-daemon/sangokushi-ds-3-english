def decompress(d):
    """Nintendo LZ77 type 0x10."""
    if d[0] != 0x10: raise ValueError('not LZ10')
    size = d[1] | d[2] << 8 | d[3] << 16
    out = bytearray(); i = 4
    while len(out) < size:
        flags = d[i]; i += 1
        for b in range(8):
            if len(out) >= size: break
            if flags & (0x80 >> b):
                v = d[i] << 8 | d[i + 1]; i += 2
                n = (v >> 12) + 3; disp = (v & 0xFFF) + 1
                for _ in range(n): out.append(out[-disp])
            else:
                out.append(d[i]); i += 1
    return bytes(out)
