"""The Lost Children, Origins masks: the mask is drawn once, on the head, in every pose (fixed in v1.35.86).

THE BUG.  The mask stubs ("Enable Origins-Exclusive Features and Heathen Masks", scripts/
build_vv2_mask_stage2.py) detour the game's two cell draws (adult 0x4095B0, child 0x409600) and draw the
mask after any village draw whose sheet is a head atlas -- the adult stub also asks that the row be the
villager's head value.  Their list of head atlases held 0xE574A0, which is female_actions (the women's and
girls' bending / sitting / arms-out / in-the-air / resting bodies), not a head atlas.  So a woman whose body
value equals her head value got a second mask drawn over her action-pose body, and every girl bending or
sitting got one (the child stub has no row check).  Men and boys were never hit: male_actions (0xE574A4)
was not listed.

THE PROOF.  The executable the patcher builds with that patch runs the game's own village compositor
0x445B50 in Unicorn (tests/test_pictures_vv2.py's harness), with the patch's mask atlas built by the
game's own constructor and a mask in the patch's own table.  For every mask, both sexes, children and
adults, every pose, and a body value equal to the head value or not: exactly one mask blit, straight
after the head blit, and none after a body.

It needs the stock executable, the game's pictures (research/game-images), the shipped Origins DLL and
Unicorn/pefile; without them it skips.  The build-script check below runs everywhere.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import test_pictures_vv2 as pv2
    import vv_pictures_vv2 as v2
    HAVE = pv2.EMULATE and v2.ORIGINS_DLL.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE = False


@unittest.skipUnless(HAVE, "the stock The Lost Children, its pictures, the Origins DLL and Unicorn are needed")
class OneMaskOnTheHead(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            exe = pv2._patched_exe()
        except Exception as exc:  # noqa: BLE001 -- the patcher could not build it here
            raise unittest.SkipTest(f"the patched executable could not be built ({exc})")
        cls.table = pv2._section_va(exe, b".mtab")
        cls.emu = pv2.VillageEmulator(exe)
        cls.emu.p.put32(cls.table + 0xF08, cls.emu.build_atlas(v2.MASK_FILE, 8, 5))

    def test_every_pose(self) -> None:
        n = 0
        for mask in range(1, 6):
            self.emu.p.write(self.table, bytes((mask,)))
            for male in (False, True):
                for age in (60, 200, 279, 280, 700, 1100, 2000):
                    for state in (0, 1, 2, 3, 8, 9, 10):
                        for frame in range(4):
                            for same in (True, False):
                                head = 11
                                st = v2.State(male=male, age=age, head=head, body=head if same else 4,
                                              state=state, frame=frame, direction=frame, facing=frame + 2,
                                              height=4, variant=1, mask=mask)
                                with self.subTest(st=st):
                                    blits = self.emu.draw(st)
                                    sheets = [b[0] for b in blits]
                                    masks = [i for i, s in enumerate(sheets) if s == v2.MASK_FILE]
                                    self.assertEqual(len(masks), 1, sheets)
                                    self.assertIn("_heads", sheets[masks[0] - 1], sheets)
                                    n += 1
        self.assertGreater(n, 2000)


class TheHeadAtlasesAreTheFourHeadSheets(unittest.TestCase):
    """Runs everywhere: the stubs' list is exactly the asset loader's four head atlases."""

    def test_the_list(self) -> None:
        tree = ast.parse((ROOT / "scripts" / "build_vv2_mask_stage2.py").read_text(encoding="utf-8"))
        value = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                     and any(getattr(t, "id", None) == "HEAD_ATLASES" for t in node.targets))
        self.assertEqual(ast.literal_eval(value), (0xE574A8, 0xE574AC, 0xE574B0, 0xE574B4))


if __name__ == "__main__":
    unittest.main()
