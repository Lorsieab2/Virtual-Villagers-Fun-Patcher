"""VV4 memorial repair: saves damaged by the old Village Statistics seed load again.

The defect.  Released builds up to v1.35.40 shipped a Village Statistics DLL
whose seed_vv4_elder_flags wrote grave+0x37 = 1 on every grave whose stock
flag +0x31 was set.  +0x37 is not a free byte: it is the top byte of the stock
dword grave+0x34, which the burial writer 0x45D524 fills from villager
+0x1C44 and which the memorial loader requires to lie in -1..4.  A seeded
grave therefore held 0x0100000N, and the stock memorial loader 0x45D6E0
returned 0; its only caller, the save loader at 0x41FD57, then jumps to the
load-failure exit 0x41FB8F.  The village would not load.

Where graves come from.  The save loader 0x41FB50 reads the .ldw through
0x4037E0 (an 0x18-byte "ldwg" header, or the legacy 0xC-byte one, then
0x1710C data bytes), copies the data to state+8, and hands state+0x8F8 to
0x45D6E0.  The memorial is 500 records of 0x5C bytes, so graves sit at data
offset 0x8F0 (file offset 0x908 behind the current header).  The loader walks
records until +0x1C == 0 and, for each, requires the 25-byte name at +0x00 to
end in a NUL before any control byte, +0x1C >= 0, +0x28 in -1..4 and +0x34 in
-1..4, then copies the record into the live memorial at 0x5025C8.

The repair.  An always-on VV4 safety patch rewrites that loop (0x45D700..
0x45D770, same entry, same exits, same register and stack contract) so that,
before +0x34 is validated, a value whose top byte is exactly 0x01 and whose
low 24 bits sign-extend to -1..4 has that byte restored to its sign (0x00, or
0xFF for -1) -- the exact inverse of the seed, which only ever set that one
byte.  Nothing else is written.  Any other +0x34 takes the stock path.

Pinned here, by RUNNING the loader in an emulator over the real executable:
the stock loader rejects a seeded grave and accepts a clean one; the patched
loader, rendered by the patcher in every public mode with and without every
public VV4 feature, repairs and loads seeded graves, leaves stock-valid graves
byte-identical, and still rejects every invalid grave that is not the seed's
footprint -- differentially against stock over a randomised corpus.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from functools import lru_cache
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
LOADER = 0x45D6E0
MEMORIAL = 0x5025C8
STRIDE = 0x5C
CAPACITY = 500
SRC = 0x20000000
RET = 0x60000000
STACK = 0x70000000
PATCH_OFFSET = 0x5D700
MODES = ("stock", "collection_progression", "immediate_fixed")


def _grave(name: bytes = b"Kora", v1c: int = 400, v28: int = 2, v34: int = 2, flags: bytes = b"\x01\x00\x01") -> bytes:
    rec = bytearray(STRIDE)
    rec[: len(name)] = name
    struct.pack_into("<iiiI", rec, 0x1C, v1c, 7, 9, v28 & 0xFFFFFFFF)
    rec[0x2C] = 0x11
    rec[0x31:0x34] = flags
    struct.pack_into("<I", rec, 0x34, v34 & 0xFFFFFFFF)
    for i in range(0x38, STRIDE):
        rec[i] = (i * 37) & 0xFF
    return bytes(rec)


def _memorial(graves: list[bytes], tail: bytes = b"") -> bytes:
    buf = bytearray(STRIDE * CAPACITY)
    for i, g in enumerate(graves):
        buf[i * STRIDE:(i + 1) * STRIDE] = g
    buf[len(graves) * STRIDE:len(graves) * STRIDE + len(tail)] = tail
    return bytes(buf)


def _seeded(v34: int) -> bool:
    v = v34 & 0xFFFFFFFF
    return v >> 24 == 1 and -1 <= ((v & 0xFFFFFF) ^ 0x800000) - 0x800000 <= 4


@lru_cache(maxsize=None)
def _stock() -> bytes:
    return EXE.read_bytes()


@lru_cache(maxsize=None)
def _render(mode: str, with_features: bool) -> tuple[bytes, tuple]:
    build = next(b for b in vfp.load_builds() if b.id == "vv4")
    rows = [f.id for f in vfp.load_public_fun_patches() if f.game_id == "vv4"] if with_features else []
    rendered, applied = vfp.render_patched_bytes(EXE, build, mode, rows)
    return bytes(rendered), tuple((r["offset"], r["owner"]) for r in applied)


def _run(image: bytes, memorial: bytes) -> tuple[int, bytes, bytes]:
    """Run 0x45D6E0(state+0x8F8) with ecx = the live memorial.  Returns
    (al, source buffer afterwards, live memorial afterwards)."""
    pe = pefile.PE(data=image, fast_load=True)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
    mu.mem_map(0x400000, size)
    for s in pe.sections:
        raw = image[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]
        mu.mem_write(0x400000 + s.VirtualAddress, raw[: max(0, size - s.VirtualAddress)])
    mu.mem_map(SRC, 0x10000 * 3)
    mu.mem_write(SRC, memorial)
    mu.mem_map(RET, 0x1000)
    mu.mem_write(RET, b"\xF4")
    mu.mem_map(STACK - 0x10000, 0x20000)
    esp = STACK - 0x100
    mu.mem_write(esp, struct.pack("<II", RET, SRC))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, MEMORIAL)
    mu.reg_write(UC_X86_REG_EAX, 0xDEADBEEF)
    mu.emu_start(LOADER, RET, count=2_000_000)
    assert mu.reg_read(UC_X86_REG_ESP) == esp + 8, "ret 4 must pop the one argument"
    al = mu.reg_read(UC_X86_REG_EAX) & 0xFF
    return al, bytes(mu.mem_read(SRC, len(memorial))), bytes(mu.mem_read(MEMORIAL, len(memorial)))


def _images():
    for mode in MODES:
        for with_features in (False, True):
            yield f"{mode}/{'all-public' if with_features else 'no-features'}", _render(mode, with_features)[0]


@unittest.skipUnless(EXE.exists(), "stock VV4 executable fixture not present")
class SeededGraveRepairTests(unittest.TestCase):
    def test_stock_loader_rejects_a_seeded_grave_and_accepts_a_clean_one(self):
        ok, _, _ = _run(_stock(), _memorial([_grave(v34=0x00000002)]))
        self.assertEqual(ok, 1)
        bad, _, _ = _run(_stock(), _memorial([_grave(v34=0x01000002)]))
        self.assertEqual(bad, 0, "the defect: stock refuses the seeded save")

    def test_the_repair_is_installed_as_safety_in_every_mode_and_selection(self):
        build = next(b for b in vfp.load_builds() if b.id == "vv4")
        patch = next(p for p in build.safety_patches if int(p["offset"], 0) == PATCH_OFFSET)
        before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
        self.assertEqual(_stock()[PATCH_OFFSET:PATCH_OFFSET + len(before)], before)
        for mode in MODES:
            for with_features in (False, True):
                image, applied = _render(mode, with_features)
                with self.subTest(mode=mode, features=with_features):
                    self.assertEqual(image[PATCH_OFFSET:PATCH_OFFSET + len(after)], after)
                    self.assertIn((hex(PATCH_OFFSET).upper().replace("0X", "0x"), "automatic:safety"),
                                  {(o.upper().replace("0X", "0x"), w) for o, w in applied})

    def test_seeded_graves_are_repaired_and_the_save_loads(self):
        values = [0x01000000, 0x01000001, 0x01000002, 0x01000003, 0x01000004, 0x01FFFFFF]
        graves = [_grave(name=b"G%d" % i, v34=v) for i, v in enumerate(values)]
        graves.insert(2, _grave(name=b"Clean", v34=2))
        memorial = _memorial(graves)
        expected = bytearray(memorial)
        for i, g in enumerate(graves):
            v = struct.unpack_from("<I", g, 0x34)[0]
            if _seeded(v):
                expected[i * STRIDE + 0x37] = 0xFF if v == 0x01FFFFFF else 0x00
        for label, image in _images():
            with self.subTest(image=label):
                al, src, live = _run(image, memorial)
                self.assertEqual(al, 1)
                self.assertEqual(src, bytes(expected), "only byte +0x37 of each seeded grave may change")
                self.assertEqual(live[: len(graves) * STRIDE], bytes(expected[: len(graves) * STRIDE]))

    def test_stock_valid_graves_are_byte_identical_and_load_as_stock(self):
        graves = [_grave(name=b"V%d" % i, v28=v28, v34=v34, flags=bytes([f, 1 - f, f]))
                  for i, (v28, v34, f) in enumerate(
                      [(a, b, (a + b) & 1) for a in range(-1, 5) for b in range(-1, 5)])]
        memorial = _memorial(graves, tail=_grave(v1c=0, v34=0x01000002))
        s_al, s_src, s_live = _run(_stock(), memorial)
        self.assertEqual(s_al, 1)
        for label, image in _images():
            with self.subTest(image=label):
                al, src, live = _run(image, memorial)
                self.assertEqual(al, 1)
                self.assertEqual(src, memorial, "a stock-valid memorial is never written")
                self.assertEqual(live, s_live)

    def test_invalid_graves_outside_the_seed_footprint_are_still_rejected(self):
        for v34 in (5, -2, 0x01000005, 0x01FFFFFE, 0x02000002, 0x01010002, 0x01000102,
                    0x00000100, 0x00010002, 0x80000000, 0x7FFFFFFF, 0x01800000, 0xFF000002):
            memorial = _memorial([_grave(name=b"Ok"), _grave(v34=v34)])
            s_al, s_src, _ = _run(_stock(), memorial)
            self.assertEqual(s_al, 0, hex(v34))
            for label, image in _images():
                with self.subTest(v34=hex(v34 & 0xFFFFFFFF), image=label):
                    al, src, _ = _run(image, memorial)
                    self.assertEqual(al, 0)
                    self.assertEqual(src, memorial, "a rejected grave is not modified")

    def test_other_invalid_fields_are_still_rejected_even_beside_a_seeded_value(self):
        # The repair belongs to +0x34 alone: +0x28 keeps the stock -1..4 rule
        # (including the seed-like 0x01000002), as do the name and +0x1C.
        cases = [dict(v28=v28) for v28 in (5, -2, 0x01000002, 0x00000100)]
        cases += [dict(name=b"Bad\x07"), dict(name=b"X" * 25), dict(v1c=-1)]
        for fields in cases:
            memorial = _memorial([_grave(name=b"Ok"), _grave(**{"v34": 0x01000002, **fields})])
            self.assertEqual(_run(_stock(), memorial)[0], 0, fields)
            for label, image in _images():
                with self.subTest(fields=repr(fields), image=label):
                    al, src, _ = _run(image, memorial)
                    self.assertEqual(al, 0)
                    self.assertEqual(src, memorial)

    def test_records_after_the_first_empty_slot_are_not_touched(self):
        memorial = _memorial([_grave(v34=0x01000001), _grave(v1c=0, v34=0x01000003), _grave(v34=0x01000004)])
        expected = bytearray(memorial)
        expected[0x37] = 0
        for label, image in _images():
            with self.subTest(image=label):
                al, src, _ = _run(image, memorial)
                self.assertEqual(al, 1)
                self.assertEqual(src, bytes(expected))

    def test_randomised_corpus_matches_stock_except_the_seed_footprint(self):
        rng = random.Random(0x45D6E0)
        interesting = [-2, -1, 0, 1, 2, 3, 4, 5, 0x01000000, 0x01000002, 0x01000004, 0x01000005, 0x01FFFFFF,
                       0x01FFFFFE, 0x02000001, 0x00FFFFFF, 0xFF000001, 0x7FFFFFFF, 0x80000000]
        images = list(_images())
        for trial in range(60):
            count = rng.choice([1, 2, 5, 40, CAPACITY])
            graves = []
            for _ in range(count):
                # Each malformed field is rare so that a memorial usually
                # reaches later records instead of failing on the first.
                name = rng.choice([b"Bad\x07", b"X" * 25]) if rng.random() < 0.01 else rng.choice([b"Ana", b"\xe9lise"])
                graves.append(_grave(
                    name=name,
                    v1c=(rng.choice([-5, 0]) if rng.random() < 0.01 else rng.choice([1, 400, 900])),
                    v28=rng.choice(interesting) if rng.random() < 0.03 else rng.randint(-1, 4),
                    v34=rng.choice(interesting) if rng.random() < 0.3 else rng.randint(-1, 4),
                ))
            memorial = _memorial(graves[:CAPACITY])
            s_al, s_src, s_live = _run(_stock(), memorial)
            repaired = bytearray(memorial)
            for i in range(min(count, CAPACITY)):
                base = i * STRIDE
                if struct.unpack_from("<i", memorial, base + 0x1C)[0] == 0:
                    break
                v = struct.unpack_from("<I", memorial, base + 0x34)[0]
                if _seeded(v):
                    repaired[base + 0x37] = 0xFF if v == 0x01FFFFFF else 0x00
            r_al, _, r_live = _run(_stock(), bytes(repaired))
            for label, image in images[:2] if trial % 3 else images:
                with self.subTest(trial=trial, image=label):
                    al, src, live = _run(image, memorial)
                    # Patched == stock run over the memorial with only the seed
                    # footprint undone, for the records the loader reaches.
                    self.assertEqual(al, r_al)
                    self.assertEqual(live, r_live)
                    if s_al == 1:
                        self.assertEqual(src, memorial)
                        self.assertEqual(live, s_live)
                    for i in range(CAPACITY):
                        a, b = i * STRIDE, (i + 1) * STRIDE
                        if src[a:b] != memorial[a:b]:
                            diff = [k for k in range(STRIDE) if src[a + k] != memorial[a + k]]
                            self.assertEqual(diff, [0x37])
                            self.assertEqual(src[a:b], bytes(repaired[a:b]))


if __name__ == "__main__":
    unittest.main()
