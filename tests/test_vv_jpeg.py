"""src/vv_jpeg.py decodes the games' JPEGs exactly as the games do.

The games load JPEGs with SDL2_image (IMG_LoadJPG_RW), which hands them to libjpeg-9.dll at its defaults
(only RGB output and no colour quantizing are set: SDL2_image.dll 0x1000360D-0x10003658).  Here that DLL runs in
Unicorn (tests/jpeg_oracle.py), driven the same way, on every JPEG the five games ship, and every pixel must
equal vv_jpeg's.

Needs Unicorn and pefile, the game's libjpeg-9.dll in research/game-dlls and the games' Images folders in
research/game-images (none of them are in the repository): skipped without them (CI).
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import hashlib
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_jpeg  # noqa: E402

DLL = ROOT / "research" / "game-dlls" / "libjpeg-9.dll"
IMAGES = ROOT / "research" / "game-images"
try:
    import pefile  # noqa: F401
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False


def game_jpegs() -> list[Path]:
    """Every JPEG of every game's Images folder, one per distinct file."""
    seen, out = set(), []
    for path in sorted(IMAGES.glob("*/Images/*")):
        if path.suffix.casefold() not in (".jpg", ".jpeg") or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            out.append(path)
    return out


_LIB = None


def _compare(path: str) -> tuple[str, int, str]:
    """(name, differing bytes, a note) for one file: the DLL's rows against vv_jpeg's."""
    global _LIB
    import jpeg_oracle
    if _LIB is None:
        _LIB = jpeg_oracle.LibJpeg(DLL)
    data = Path(path).read_bytes()
    w, h, ref = _LIB.decode(data)
    image = vv_jpeg.decode_jpeg(data)
    if (image.width, image.height) != (w, h):
        return path, -1, f"size {image.width}x{image.height}, the game's {w}x{h}"
    mine = bytearray(w * h * 3)
    mine[0::3], mine[1::3], mine[2::3] = image.data[0::4], image.data[1::4], image.data[2::4]
    if any(image.data[3::4][i] != 255 for i in range(0, w * h, max(1, w * h // 997))):
        return path, -1, "not opaque"
    return path, sum(1 for a, b in zip(ref, mine) if a != b), ""


class Rules(unittest.TestCase):
    """Without the games' files."""

    def test_size_from_the_frame_header(self) -> None:
        sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, 600, 800, 3) + bytes(9)
        self.assertEqual(vv_jpeg.jpeg_size(b"\xff\xd8" + sof), (800, 600))
        with self.assertRaises(vv_jpeg.JpegError):
            vv_jpeg.jpeg_size(b"\x89PNG")

    def test_flat_blocks(self) -> None:
        """A block with only its DC term: every sample is the range-limited DC (both IDCTs agree)."""
        q = [1] * 64
        for dc in (-1024, -300, -2, 0, 5, 200, 1016, 2000):
            block = [dc] + [0] * 63
            want = vv_jpeg.LIMIT[((dc * 4 + vv_jpeg.PASS2_OFFSET) >> vv_jpeg.PASS2_BITS) & vv_jpeg.RANGE_MASK]
            self.assertEqual(set(vv_jpeg.idct_8x8(block, q)), {want}, dc)
            self.assertEqual(set(vv_jpeg.idct_16x16(block, q)), {want}, dc)

    def test_ycc_tables(self) -> None:
        self.assertEqual((vv_jpeg.CR_R[128], vv_jpeg.CB_B[128]), (0, 0))
        self.assertEqual((vv_jpeg.CR_R[255], vv_jpeg.CB_B[0]), (178, -227))

    def test_scaled_sizes(self) -> None:
        """jdmaster.c: a 2 x 2 subsampled component gets the 16 x 16 IDCT; the full-size ones the 8 x 8."""
        self.assertEqual(vv_jpeg._scaled(2, 1), 16)
        self.assertEqual(vv_jpeg._scaled(2, 2), 8)
        self.assertEqual(vv_jpeg._scaled(1, 1), 8)


@unittest.skipUnless(HAVE_UNICORN and DLL.is_file() and IMAGES.is_dir(),
                     "the game's libjpeg-9.dll, Unicorn and the games' pictures are needed")
class EveryGameJpegIsTheGames(unittest.TestCase):
    def test_every_jpeg_of_the_five_games(self) -> None:
        files = game_jpegs()
        self.assertGreater(len(files), 100)
        with ProcessPoolExecutor(max_workers=max(1, min(24, os.cpu_count() or 1))) as pool:
            results = list(pool.map(_compare, [str(f) for f in files], chunksize=2))
        bad = [r for r in results if r[1] != 0]
        self.assertEqual(bad, [], f"{len(bad)} of {len(results)} JPEGs differ from the game's decode")
        print(f"\n{len(results)} distinct JPEGs of the five games: every pixel is libjpeg 9's")


if __name__ == "__main__":
    unittest.main()
