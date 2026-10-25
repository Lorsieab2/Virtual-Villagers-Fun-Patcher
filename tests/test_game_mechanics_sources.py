"""Where the Game Mechanics window reads which patches are in the game (vv_game_mechanics.patch_source): the game's
exe as it is now, through the patcher's log of the run that made it when that log's hash is the exe's, else the
exe's own bytes -- never the save (the owner, 2026-10-23).  Disagreements are shown, not resolved."""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402
from test_game_mechanics import BASE, EPOCH, make_save  # noqa: E402

FILES = "Virtual Villagers Fun Patcher Files"


class Sources(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="gms"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.saves = self.root / "LDW" / BASE
        self.saves.mkdir(parents=True)
        (self.saves / f"{BASE}1.ldw").write_bytes(make_save(trees=[(0, 1, 1, 0)]))

    def game(self, where: str = "g", exe: bytes = b"MZ") -> Path:
        folder = self.root / where / BASE
        (folder / FILES).mkdir(parents=True)
        (folder / f"{BASE}.exe").write_bytes(exe)
        return folder

    def patch_log(self, folder: Path, ids: list[str], exe: bytes | None = None, when="2026-10-23T01:02:03Z") -> None:
        digest = hashlib.sha256((folder / f"{BASE}.exe").read_bytes() if exe is None else exe).hexdigest()
        (folder / FILES / f"{BASE}.patch-log.json").write_text(json.dumps(
            {"patcher": gm.PATCHER_SIGNATURE, "fun_patches": ids, "output_sha256": digest, "created_utc": when}),
            encoding="utf-8")

    def read(self, folders):
        return gm.read(self.saves, 3, 1, folders, now=EPOCH + 100_000)

    def sources(self, facts) -> list[str]:
        return [f.text for f in facts if f.group == gm.SOURCES]

    def test_patch_on_and_off_from_the_patchers_log(self) -> None:
        folder = self.game()
        self.patch_log(folder, [vv3.NATURE_PATCH])
        on = self.read([folder])
        self.assertIn(f"The patcher's \"{gm.feature_name(vv3.NATURE_PATCH)}\" is in the game", gm.render(on))
        self.assertTrue(any("as listed by the patcher's log of the run that made it (2026-10-23T01:02:03Z UTC)" in s
                            for s in self.sources(on)))
        self.patch_log(folder, [])
        off = gm.render(self.read([folder]))
        self.assertIn(f"The patcher's \"{gm.feature_name(vv3.NATURE_PATCH)}\" is not in the game", off)

    def test_a_log_for_another_exe_is_not_used(self) -> None:
        folder = self.game()
        self.patch_log(folder, [vv3.NATURE_PATCH], exe=b"an older build")
        facts = self.read([folder])
        text = gm.render(facts)
        self.assertNotIn("is in the game", text.split("Food sources")[1])
        self.assertTrue(any("is for a different" in s and "patched again or replaced" in s for s in self.sources(facts)))
        self.assertTrue(any("read from its own bytes" in s for s in self.sources(facts)))
        # Not seen in the bytes is "not known", never "not in the game".
        self.assertIn("could not be told", text)

    def test_from_the_exes_own_bytes(self) -> None:
        import vv_fun_patcher as fp
        feature = next(p for p in fp.load_fun_patches() if p.id == vv3.NATURE_PATCH)
        edits = feature.raw["patches"]
        size = max(int(e["offset"], 0) + len(fp._patch_bytes(e, "after")) for e in edits) + 16
        exe = bytearray(size)
        for e in edits:
            after = fp._patch_bytes(e, "after")
            at = int(e["offset"], 0)
            exe[at:at + len(after)] = after
        folder = self.game(exe=bytes(exe))
        facts = self.read([folder])
        self.assertIn(f"The patcher's \"{gm.feature_name(vv3.NATURE_PATCH)}\" is in the game", gm.render(facts))

    def test_no_exe_and_several_exes(self) -> None:
        none = self.sources(self.read([self.root / "nowhere" / BASE]))
        self.assertIn(f"Could not tell which patches this game has: no game folder holding {BASE}.exe was found.", none)
        a, b = self.game("a", b"MZ1"), self.game("b", b"MZ2")
        several = self.sources(self.read([a, b]))
        self.assertTrue(any(s.startswith("Could not tell which patches this game has: several different") for s in several))
        self.assertIn("could not be told", gm.render(self.read([a, b])))

    def test_the_save_does_not_decide_but_its_disagreement_is_shown(self) -> None:
        folder = self.game()
        self.patch_log(folder, [])                     # the exe has neither fruit-tree patch now
        data = make_save(clock=(6, 0, 100_000, 50_000), trees=[(1, 51_000, 51_000, 300)])
        (self.saves / f"{BASE}1.ldw").write_bytes(data)
        fp = vv3._trees_fingerprint(data[12:])
        body = bytearray(vv3.TIMER_ENTRIES * vv3.TIMER_ENTRY)
        struct.pack_into("<IIBBBBI3I3I", body, 0, fp & 0xFFFFFFFF, fp >> 32, 2, 1, 0, 0, 10_800,
                         51_000, 0, 0, 61_800, 0, 0)
        place = self.saves / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
        place.mkdir(parents=True)
        (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(
            struct.pack("<5I", vv3.TIMER_MAGIC, 1, 3, 1, 1) + bytes(body))
        sources = self.sources(self.read([folder]))
        self.assertTrue(any(s.startswith("Read: ") and s.endswith("Fruit Tree Timers - Save 1.dat.") for s in sources))
        self.assertTrue(any(s.startswith("They disagree: this save's fruit-tree timers file holds a \"Fruit Trees Take "
                                         "Turns Refilling\" schedule") for s in sources))

    def test_the_save_is_named_with_its_time(self) -> None:
        sources = self.sources(self.read([]))
        self.assertTrue(sources[0].startswith(f"The save: {self.saves / (BASE + '1.ldw')}, last written "))
        # Every game autosaves (the owner, 2026-10-25: "Games autosave").
        self.assertIn("when it is closed normally and every 10 real-life minutes by its autosave", sources[0])
        self.assertNotIn("only when", sources[0])


if __name__ == "__main__":
    unittest.main()
