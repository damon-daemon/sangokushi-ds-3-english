"""Rebuild the ROM with translated script and produce a patch.

usage: .venv/bin/python tools/build.py [clean.nds] [out.nds]
"""
import os, subprocess, sys
import ndspy.rom

sys.path.insert(0, os.path.dirname(__file__))
import script, patch_arm9, names, arm9str, gfx, ovlstr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLEAN_HEADER_CRC = 0x7753

def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

def match_header_crc(path):
    """Give the patched ROM the clean ROM's header CRC16 by setting two reserved header
    bytes (0x15-0x16, unused and zero in the original). Loaders such as TWiLight Menu++ /
    nds-bootstrap identify a game by game code + header CRC to apply their own
    compatibility and anti-piracy fixes; the rebuilt header (new offsets and sizes) would
    otherwise not be recognised. The patch itself contains no such fix."""
    import struct
    with open(path, 'r+b') as f:
        h = bytearray(f.read(0x160))
        for v in range(0x10000):
            h[0x15], h[0x16] = v & 0xFF, v >> 8
            if crc16(h[:0x15E]) == CLEAN_HEADER_CRC:
                break
        else:
            raise RuntimeError('no reserved-byte value gives the clean header CRC')
        struct.pack_into('<H', h, 0x15E, CLEAN_HEADER_CRC)
        f.seek(0); f.write(h)

def main():
    clean = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sangokushi_ds_3.nds')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'sangokushi_ds_3_en.nds')
    rom = ndspy.rom.NintendoDSRom.fromFile(clean)
    changed = 0
    sdir = os.environ.get('SCRIPT_DIR', os.path.join(ROOT, 'script'))
    for n in range(68):
        name = 'msgsec%02d.dat' % n
        fid = rom.filenames.idOf('Message/' + name)
        data = script.build(sdir, name)
        if len(rom.files[fid]) < 2:
            continue
        if data != rom.files[fid]:
            rom.files[fid] = data; changed += 1
    for fx in ('Scenario/FixData.bin', 'Scenario/ChallengeFixData.bin'):
        fid = rom.filenames.idOf(fx)
        rom.files[fid] = names.apply(rom.files[fid], sdir)
    fid = rom.filenames.idOf('Challenge/ChallengeStage.bin')
    rom.files[fid] = names.apply_stages(rom.files[fid], sdir)
    print('graphics: %d sheets edited' % gfx.apply(rom))
    print('overlay strings: %d' % ovlstr.apply(rom))
    arm9 = rom.loadArm9()
    table = patch_arm9.apply(arm9)
    n_in, n_moved = arm9str.apply(arm9)
    print('arm9 UI strings: %d in place, %d relocated' % (n_in, n_moved))
    rom.arm9 = arm9.save(compress=True)
    print('arm9 patched (ASCII font table at %#x)' % table)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rom.saveToFile(out)
    match_header_crc(out)
    print('rebuilt %s (%d message files changed)' % (out, changed))
    patch = os.path.splitext(out)[0] + '.xdelta'
    try:
        subprocess.run(['xdelta3', '-e', '-f', '-9', '-S', 'djw', '-s', clean, out, patch], check=True)
        print('patch', patch)
    except FileNotFoundError:
        print('xdelta3 not installed; skipped patch')

if __name__ == '__main__':
    main()
