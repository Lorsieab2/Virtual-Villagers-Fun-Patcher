"""New Believers' More Respectful Flower Hovel Cover: the owner's cover, its bottom-left on the completed hovel's.

The owner (2026-11-08): "a patch that overrides the normal one: "More Respectful Flower Hovel Cover" - overrides the
normal graphics and fix vanilla bugs vv5 graphic", and "its bottom and left edges should be aligned to the bottom and
left edges of the original completed hovel".

0x4370E0, the only drawer of image 0x1B, calls 0x44F320(sprite, x, y, 1.0f) once The Last Heathen (project 25) is
done; 0x44F320 draws at once from the top-left corner (tests/test_vv5_hovel_cover.py has the stock trace).  The
completed hovel is Fix Vanilla Bugs' 634 x 286 picture at (1702, 1465), bottom-left (1702, 1751); the owner's
picture (its height read from the PNG; the first, placeholder art is 800 x 500 with its hovel layers at (0, 214),
flush with its bottom and left edges) is drawn at (1702, 1751 - height) = (1702, 1251) for 500, with Fix Vanilla
Bugs on or off.  New art is the one file plus the builder re-run; nothing here needs changing.  The row writes none of Fix Vanilla Bugs' bytes
(scripts/build_vv5_respectful_hovel_cover.py has the design).

Everything here runs the stock and the patcher's rendered draw routine in unicorn.
"""
from __future__ import annotations

import functools
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv5_respectful_hovel_cover as builder  # noqa: E402
from vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
ART = ROOT / "assets" / "vv5_respectful_hovel_cover" / "vvfp_respectful_hovel.png"
FEATURE = "vv5_respectful_hovel_cover"
FIX = "vv5_fix_vanilla_bugs"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE = 0x400000
OBJECT, STK, RETURN = 0x10000000, 0x20000000, 0x0BAD0000
SPRITE = 0x13572468
DRAW, SOLVED, QUEUE = 0x44F320, 0x43AE80, 0x521078
ONE = struct.unpack("<I", struct.pack("<f", 1.0))[0]
NO_STOCK = "stock executables are not available"


def _row() -> dict:
    data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return next(p for p in data["fun_patches"] if p["id"] == FEATURE)


@functools.lru_cache(maxsize=None)
def _render(mode: str, ids: tuple) -> bytes:
    build = next(b for b in load_builds() if b.id == "vv5")
    data, _ = render_patched_bytes(STOCK, build, mode, list(ids))
    return bytes(data)


@functools.lru_cache(maxsize=None)
def _image(data: bytes) -> bytes:
    return pefile.PE(data=data, fast_load=True).get_memory_mapped_image()


def _draws(data: bytes, solved: bool) -> list[tuple]:
    """Run 0x4370E0 on <data>'s image: every call of 0x44F320 as (ecx, sprite, x, y, scale bits), and esp checks."""
    image = _image(data)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(BASE, image)
    for area in (OBJECT, STK, RETURN):
        mu.mem_map(area, 0x100000)
    mu.mem_write(OBJECT + 0x10, struct.pack("<I", SPRITE))
    top = STK + 0x80000
    mu.mem_write(top, struct.pack("<I", RETURN))
    calls = []

    def ret(n: int) -> None:
        esp = mu.reg_read(UC_X86_REG_ESP)
        mu.reg_write(UC_X86_REG_EIP, struct.unpack("<I", mu.mem_read(esp, 4))[0])
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + n)

    def code(uc, address, size, _):
        if address == SOLVED:
            esp = uc.reg_read(UC_X86_REG_ESP)
            assert struct.unpack("<I", uc.mem_read(esp + 4, 4))[0] == 25 and uc.reg_read(UC_X86_REG_ECX) == 0x51E008
            uc.reg_write(UC_X86_REG_EAX, 1 if solved else 0)
            ret(4)
        elif address == DRAW:
            esp = uc.reg_read(UC_X86_REG_ESP)
            calls.append((uc.reg_read(UC_X86_REG_ECX),) + struct.unpack("<IiiI", uc.mem_read(esp + 4, 16)))
            ret(16)
        elif address == RETURN:
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, code)
    mu.reg_write(UC_X86_REG_ESP, top)
    mu.reg_write(UC_X86_REG_ECX, OBJECT)
    mu.emu_start(0x4370E0, RETURN, count=200)
    assert mu.reg_read(UC_X86_REG_ESP) == top + 4, "the routine left the stack unbalanced"
    return calls


def _name(data: bytes) -> str:
    image = _image(data)
    pointer = struct.unpack_from("<I", image, 0x4CF76C - BASE)[0]
    return image[pointer - BASE:image.index(b"\0", pointer - BASE)].decode("ascii")


class Manifest(unittest.TestCase):
    def test_the_row_is_what_the_builder_makes(self) -> None:
        self.assertEqual(_row(), builder.row())

    def test_the_owners_art_is_shipped_as_given(self) -> None:
        row = _row()
        (art,) = row["companion_files"]
        self.assertEqual((art["source"], art["destination"]),
                         ("assets/vv5_respectful_hovel_cover/vvfp_respectful_hovel.png",
                          "Images/vvfp_respectful_hovel.png"))
        data = ART.read_bytes()
        self.assertEqual(art["size"], len(data))
        self.assertEqual(art["sha256"], hashlib.sha256(data).hexdigest().upper())
        self.assertEqual(struct.unpack(">II", data[16:24]), (builder.ART_WIDTH, builder.ART_HEIGHT))
        self.assertEqual((data[24], data[25]), (8, 6))                        # 8-bit RGBA, as vvfp_hovel.png
        from patcher_files import stays_in_place
        self.assertTrue(stays_in_place("Images/vvfp_respectful_hovel.png"))

    def test_the_alignment(self) -> None:
        """Bottom-left on the completed hovel's: x the same, y + height = 1465 + 286."""
        self.assertEqual(builder.DRAW_X, 1702)
        self.assertEqual(builder.DRAW_Y + builder.ART_HEIGHT, 1465 + 286)
        self.assertTrue(0 <= builder.DRAW_Y and builder.DRAW_X + builder.ART_WIDTH <= 2560)   # on the 2560 map

    def test_the_art_touches_its_bottom_and_left_edges(self) -> None:
        """The picture's bottom and left edges are the ones laid on the completed hovel's, so something is drawn
        on each (an empty margin there would move the art up or right of the hovel's edges)."""
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            self.skipTest("Pillow is not available")
        box = Image.open(ART).getchannel("A").getbbox()
        self.assertIsNotNone(box)
        self.assertEqual((box[0], box[3]), (0, builder.ART_HEIGHT))

    def test_defaults(self) -> None:
        """The owner (2026-11-08): off in the normal defaults, on in Owner's Defaults and Select All."""
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertFalse(default_fun_patch_selection(FEATURE))
        self.assertTrue(owners_default_fun_patch_selection(FEATURE))
        self.assertTrue(select_all_fun_patch_selection(FEATURE))

    def test_no_byte_is_shared_with_fix_vanilla_bugs(self) -> None:
        data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        fix = next(p for p in data["fun_patches"] if p["id"] == FIX)

        def spans(row):
            for p in row["patches"]:
                start = int(p["offset"], 16)
                yield start, start + len(p["after"]) // 2

        for a, b in spans(_row()):
            for c, d in spans(fix):
                self.assertFalse(a < d and c < b, (hex(a), hex(c)))


@unittest.skipUnless(pefile is not None and STOCK.is_file(), NO_STOCK)
class Draw(unittest.TestCase):
    def test_stock(self) -> None:
        stock = STOCK.read_bytes()
        for offset, before in ((int(p["offset"], 16), bytes.fromhex(p["before"])) for p in _row()["patches"]):
            self.assertEqual(stock[offset:offset + len(before)], before)
        self.assertEqual(_draws(stock, True), [(QUEUE, SPRITE, 1705, 1459, ONE)])
        self.assertEqual(_draws(stock, False), [])
        self.assertEqual(_name(stock), "hovel_cover.png")

    def test_fix_vanilla_bugs_alone(self) -> None:
        data = _render("collection_progression", (FIX,))
        self.assertEqual(_draws(data, True), [(QUEUE, SPRITE, 1702, 1465, ONE)])
        self.assertEqual(_name(data), "vvfp_hovel.png")

    def test_the_new_cover_alone_and_with_fix_vanilla_bugs(self) -> None:
        for mode in MODES:
            for ids in ((FEATURE,), (FIX, FEATURE)):
                with self.subTest(mode=mode, ids=ids):
                    data = _render(mode, ids)
                    self.assertEqual(_draws(data, True), [(QUEUE, SPRITE, 1702, 1751 - builder.ART_HEIGHT, ONE)])
                    self.assertEqual(_draws(data, False), [])
                    self.assertEqual(_name(data), "vvfp_respectful_hovel.png")

    def test_nothing_else_reads_the_new_bytes(self) -> None:
        """The padding the draw grows into is not a jump or call target, and the pointer's one reader is the
        image table entry itself (its getter reads the entry)."""
        image = _image(STOCK.read_bytes())
        text = image[0x1000:0x94339]
        outside = []
        for i in range(len(text) - 5):                  # every byte as a call / jmp rel32 or a short jump
            va = BASE + 0x1000 + i
            if 0x4370E0 <= va < 0x437120:
                continue
            if text[i] in (0xE8, 0xE9):
                target = va + 5 + struct.unpack_from("<i", text, i + 1)[0]
            elif text[i] == 0xEB or 0x70 <= text[i] <= 0x7F:
                target = va + 2 + struct.unpack_from("<b", text, i + 1)[0]
            else:
                continue
            if 0x437113 <= target < 0x437120:
                outside.append(hex(va))
        self.assertEqual(outside, [])
        self.assertEqual(image[0x4C5FD0 - BASE:0x4C5FF0 - BASE], bytes(0x20))   # the stock tail is zero


if __name__ == "__main__":
    unittest.main()
