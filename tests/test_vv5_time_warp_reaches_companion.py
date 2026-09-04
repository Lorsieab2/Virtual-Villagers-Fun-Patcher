"""VV5's Time Warp must reach the companion in the RENDERED image.

VV5 carries two copies of the Tech-menu handler. The Origins base payload lives
at 0x7B2xxx and is also embedded verbatim in the Task9 record's 0xDB000 patch;
the Task9 stock menu page at 0x7C9000 REPLACES it at load. Only the second one
runs.

That cost a shipped release. Time Warp was fixed in the Origins payload, every
manifest-level check agreed it was fixed, and the game kept running the old
`194400 / speed` clock write from the Task9 page -- which the engine's clamp
then cut, producing exactly the bug the fix was for. A search for the old
constant "proved" it was gone because the search used 0x2F7E0 (194,528) rather
than 0x2F760 (194,400).

So this test renders the executable and asserts on the bytes a player runs.
Nothing here reads a manifest.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"

# `mov eax, 194400` -- the superseded clock-only advance. Written out rather
# than computed so a typo cannot silently make this test vacuous again.
OLD_DELTA_IMM = bytes.fromhex("b860f70200")   # 0x0002F760 == 194400
EXPORT = b"ShowVv5TimeWarp\x00"


def _sections(data: bytes):
    pe = int.from_bytes(data[0x3C:0x40], "little")
    count = int.from_bytes(data[pe + 6 : pe + 8], "little")
    opt = int.from_bytes(data[pe + 20 : pe + 22], "little")
    base = int.from_bytes(data[pe + 52 : pe + 56], "little")
    out = []
    for i in range(count):
        h = pe + 24 + opt + i * 40
        va = base + int.from_bytes(data[h + 12 : h + 16], "little")
        raw = int.from_bytes(data[h + 20 : h + 24], "little")
        size = int.from_bytes(data[h + 16 : h + 20], "little")
        out.append((va, data[raw : raw + size]))
    return out


def _find_all(data: bytes, needle: bytes) -> list[int]:
    hits = []
    for va, blob in _sections(data):
        for m in re.finditer(re.escape(needle), blob):
            hits.append(va + m.start())
    return hits


@unittest.skipUnless(STOCK.is_file(), "VV5 stock executable not present")
class VV5TimeWarpReachesCompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build = next(b for b in vv_fun_patcher.load_builds() if b.id == "vv5")
        cls.rendered, _ = vv_fun_patcher.render_patched_bytes(
            STOCK, build, "immediate_fixed",
            ["vv5_enable_origins_exclusive_features"],
        )

    def test_the_export_name_is_reachable_from_the_task9_page(self) -> None:
        """The LIVE handler must push the export, not just some copy of it.

        The Origins page also references it, and that reference is inert. What
        matters is a push from the 0x7C9xxx/0x7CAxxx range the menu dispatches
        into.
        """
        strings = _find_all(self.rendered, EXPORT)
        self.assertTrue(strings, "ShowVv5TimeWarp is not in the rendered image")

        pushes = []
        for va in strings:
            pushes += _find_all(self.rendered, b"\x68" + va.to_bytes(4, "little"))
        self.assertTrue(pushes, "nothing pushes the export name")

        live = [p for p in pushes if 0x7C9000 <= p < 0x7D0000]
        self.assertTrue(
            live,
            "the export is referenced only from the replaced Origins page "
            f"(pushes at {[hex(p) for p in pushes]}); the Task9 page at "
            "0x7C9000 is what actually runs",
        )

    def test_the_superseded_clock_write_is_not_what_row_zero_reaches(self) -> None:
        """If the old constant is still executed, the clamp bug is still live.

        It may remain present as unreachable tail code, but the companion
        dispatch has to come first in the handler.
        """
        old = _find_all(self.rendered, OLD_DELTA_IMM)
        if not old:
            return                      # removed outright: also fine

        strings = _find_all(self.rendered, EXPORT)
        pushes = []
        for va in strings:
            pushes += _find_all(self.rendered, b"\x68" + va.to_bytes(4, "little"))
        live = [p for p in pushes if 0x7C9000 <= p < 0x7D0000]
        self.assertTrue(live, "no live dispatch to compare against")

        for site in old:
            if 0x7C9000 <= site < 0x7D0000:
                self.assertLess(
                    min(live), site,
                    f"the 194400 clock write at {site:#x} precedes the companion "
                    f"dispatch at {min(live):#x}, so row 0 still reaches it",
                )


if __name__ == "__main__":
    unittest.main()
