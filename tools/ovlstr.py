"""In-place string patches in arm9 overlays (format strings the arm9 pool tool doesn't cover).

Each entry: (overlay id, offset in the decompressed overlay, original bytes, new text).
The new text plus its null must fit in the original slot (original bytes incl. padding).
"""
import os, sys
import ndspy.code
sys.path.insert(0, os.path.dirname(__file__))
import script

PATCHES = [
    (7, 0x6176C, b'%s\x82\xcc\x90\xed\x82\xa2\x00\x00\x00\x00', '%s Battle'),   # "%sの戦い" (battle name)
    (3, 0xC7A4, b'\x96\x87\x00\x00', ''),                                     # 枚 after gallery card count
    (3, 0xC7B4, b'\x96\x87\x00\x00', ''),
]

def apply(rom):
    ovs = rom.loadArm9Overlays()
    touched = set()
    for ov, off, old, text in PATCHES:
        d = ovs[ov].data
        assert bytes(d[off:off + len(old)]) == old, (ov, hex(off))
        new = script.encode(text) + b'\0'
        assert len(new) <= len(old), (ov, text)
        d[off:off + len(old)] = new.ljust(len(old), b'\0')
        touched.add(ov)
    for ov in touched:
        rom.files[ovs[ov].fileID] = ovs[ov].save(compress=True)
    rom.arm9OverlayTable = ndspy.code.saveOverlayTable(ovs)
    return len(PATCHES)
