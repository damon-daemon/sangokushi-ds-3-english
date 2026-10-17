import struct
def decompress(data):
    data = bytes(data)
    inc = struct.unpack_from('<I', data, len(data)-4)[0]
    if inc == 0: return data
    hdr = data[-5]; enc = struct.unpack_from('<I', data, len(data)-8)[0] & 0xFFFFFF
    dec = len(data) - enc
    out = bytearray(len(data) + inc); out[:dec] = data[:dec]
    pak = len(data) - hdr; raw = len(out)
    while raw > dec and pak > dec:
        pak -= 1; flags = data[pak]
        for _ in range(8):
            if raw <= dec or pak <= dec: break
            if flags & 0x80:
                pak -= 2; v = data[pak] | (data[pak+1] << 8)
                n = (v >> 12) + 3; d = (v & 0xFFF) + 3
                for _ in range(n):
                    raw -= 1; out[raw] = out[raw + d]
                    if raw <= dec: break
            else:
                pak -= 1; raw -= 1; out[raw] = data[pak]
            flags <<= 1
    return bytes(out)
