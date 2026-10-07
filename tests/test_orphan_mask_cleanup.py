"""The first-load cross-check clears ORPHAN Village Masks entries (v1.35.59, all five games).

An orphan is a mask entry whose stored villager identity no villager in the village carries --
living, or a body still in its record -- on a record nobody holds (The Secret City finds masks by
identity, so there the record does not matter).  The Repair / Not now prompt lists them; Repair
backs the mask file up as "<file>.before-v1.35.59-repair", removes exactly them and lists each in
the Repairs log; an entry some villager carries (one, or several alike) is never touched.

native/shared/orphan_masks_game_harness.c compiles each game's own Origins companion source with
the game's memory stood in for at its own addresses and drives the companion's load, the scan and
the repair against real files.  Built with the toolchain the DLL build scripts use; skipped where
it is not installed.  The wiring is checked from the sources.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = "Virtual Villagers Fun Patcher Data"
SHARED = ROOT / "native" / "shared"
BUILD = (ROOT / "scripts" / "build_vv1_parentage_dll.ps1").read_text(encoding="utf-8")

COMPANIONS = {
    1: "native/vv1_origins_icons/vv1_origins_icons.c",
    2: "native/vv2_origins_icons/vv2_origins_icons.c",
    3: "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    4: "native/vv4_origins_icons/vv4_origins_icons.c",
    5: "native/vv5_task9_origins/vv5_task9_origins.c",
}
BUILD_SCRIPTS = {
    1: "scripts/build_vv1_origins_icons.ps1",
    2: "scripts/build_vv2_origins_icons.ps1",
    3: "scripts/build_vv3_full_mastery_candidate_dll.ps1",
    4: "scripts/build_vv4_origins_icons.ps1",
    5: "scripts/build_vv5_task9_origins_dll.ps1",
}

CASES = (
    "ok   it is in the Village Masks folder (the #519 resolver)",
    "ok   the load keeps every entry where it was (nobody moved)",
    "ok   two orphans: Dee's mask and the one with no identity (scan says 2)",
    "ok   the file is byte for byte as it was",
    "ok   no backup",
    "ok   no Repairs log",
    "ok   nothing changed, no backup, no log",
    "ok   this repair's backup is gone again",
    "ok   the entries are back in the table",
    "ok   no backup left, nothing listed",
    "ok   when the file cannot be written back either, the backup is kept: it alone holds them",
    "ok   ... both entries",
    "ok   exactly the two orphans are gone from the table",
    "ok   and from the file",
    "ok   Bo's, the alike pair's and the body's are kept in the file",
    "ok   the backup is the file as it was: ",
    "ok   two removals are listed",
    "ok   and the backup's name",
    "ok   the next scan finds nothing",
    "ok   a Repair then changes nothing more",
    "ok   nor does the next load's",
    "ok   which keeps the alike pair's mask (and the body's)",
    "ok   load after load",
    "ok   only the entry that is still an orphan is removed",
    "ok   backed up again, beside the first backup: ",
)
WEAK_CASES = (
    "ok   one orphan: the name no villager has",
    "ok   the name both Cys carry is kept",
    "ok   and still kept at the next load",
)


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class OrphanMaskHarnessTests(unittest.TestCase):
    """Each game's companion, run."""

    @classmethod
    def setUpClass(cls):
        vs, sdk, ver = _toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        cls.work = Path(tempfile.mkdtemp())
        cls.results = {}
        for game in COMPANIONS:
            out = cls.work / f"g{game}"
            out.mkdir()
            exe = out / f"vvfp_orphan_masks_harness_vv{game}.exe"
            cmd = [str(cl), "/nologo", "/O2", "/MT", "/W3", "/D_CRT_SECURE_NO_WARNINGS", f"/DOM_GAME={game}",
                   "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
                   "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
                   str(SHARED / "orphan_masks_game_harness.c"), f"/Fe{exe}", f"/Fo{out}\\",
                   "/link", "/FIXED", "/DYNAMICBASE:NO", "/BASE:0x400000",
                   f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
                   f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
                   "user32.lib", "gdi32.lib", "shell32.lib", "advapi32.lib", "gdiplus.lib", "ole32.lib"]
            build = subprocess.run(cmd, capture_output=True, text=True, cwd=out)
            if build.returncode != 0:
                raise AssertionError(f"game {game}: " + build.stdout[-3000:] + build.stderr[-3000:])
            cls.results[game] = subprocess.run([str(exe)], capture_output=True, text=True, timeout=600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes_in_every_game(self):
        for game, result in self.results.items():
            with self.subTest(game=game):
                self.assertIn("== 0 failure(s) ==", result.stdout, result.stdout)
                self.assertNotIn("FAIL", result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_every_case_is_run_in_every_game(self):
        for game, result in self.results.items():
            extra = (WEAK_CASES if game in (2, 5) else ()) + (
                ("ok   before the follow has run, the scan cannot tell yet",) if game == 4 else ())
            for case in CASES + extra:
                with self.subTest(game=game, case=case):
                    self.assertIn(case, result.stdout)


    def test_the_checker_computes_each_companions_identities(self):
        """scripts/vvfp_consistency_check.py reads identities from the SAVE; each must be the one the
        companion computes from the record (the harness prints them)."""
        for game, result in self.results.items():
            lines = [ln.split() for ln in result.stdout.splitlines() if ln.startswith("IDENT ")]
            self.assertEqual(len(lines), 5 if game >= 3 else 4, result.stdout[:2000])
            people = [PEOPLE[int(ln[1])] for ln in lines]
            roster = roster_for(game, people)
            for ln, v in zip(lines, roster):
                with self.subTest(game=game, villager=ln[2], record=ln[1]):
                    self.assertEqual(v.name, ln[2])
                    self.assertEqual(f"{v.ident:08X}", ln[3])
                    if game in (2, 5):
                        self.assertEqual(f"{v.name_hash:08X}", ln[5])
                    if game == 4:
                        self.assertEqual(f"{v.ident_v2:08X}", ln[5])


# ---- the read-only checker on the same village, from a save ------------------------------------

spec = importlib.util.spec_from_file_location("vvfp_consistency_check", ROOT / "scripts" / "vvfp_consistency_check.py")
checker = importlib.util.module_from_spec(spec)
sys.modules.setdefault(spec.name, checker)
spec.loader.exec_module(checker)

# The harness's village: (name, male, family) -- family: A New Home's family scalar 1, the later
# games' parents "Pa" and "Ma" (The Secret City: Likes 3, 4, 5).  Fay is a body awaiting burial.
PEOPLE = [("Ana", False, 0), ("Bo", True, 0), ("Cy", True, 1), ("Cy", True, 1), ("Fay", False, 0)]
DEE = ("Dee", False, 0)
SAVE_NAMES = {1: "Virtual Villagers{slot}.ldw", 2: "Virtual Villagers - The Lost Children{slot}.ldw",
              3: "Virtual Villagers - The Secret City{slot}.ldw", 4: "Virtual Villagers - The Tree of Life{slot}.ldw",
              5: "Virtual Villagers - New Believers{slot}.ldw"}
STRIDE = {2: 0x2E0, 3: 0x11C, 4: 0x104, 5: 0x118}
FIRST = 0x2000


def save_for(game: int, people) -> bytes:
    if game == 1:
        data = bytearray(0x184 + 256 * 0x9C)
        for i, (name, male, family) in enumerate(people):
            base = 0x184 + i * 0x9C - 0x33C
            struct.pack_into("<i", data, base + 0x350, 1 if male else 2)
            struct.pack_into("<i", data, base + 0x348, 500)
            struct.pack_into("<i", data, base + 0x36C, family)
            struct.pack_into("<i", data, base + 0x3D4, 1)
            data[base + 0x370:base + 0x370 + len(name)] = name.encode()
        return bytes(data)
    lay = checker.LAYOUTS[game]
    data = bytearray(FIRST + 150 * STRIDE[game] + 64)
    for i, (name, male, family) in enumerate(people):
        p = FIRST + i * STRIDE[game] + 0x40
        data[p:p + len(name)] = name.encode()
        if game in checker.PRESENT:                     # the writer's flag on every villager it packs
            off, width = checker.PRESENT[game]
            data[p + off:p + off + width] = (1).to_bytes(width, "little")
        struct.pack_into("<i", data, p + lay.age, 500)
        struct.pack_into("<i", data, p + lay.head, 3)
        struct.pack_into("<i", data, p + lay.body, 4)
        sex = {2: (1, 2), 3: (0, 1), 4: (1, 0), 5: (0, 1)}[game][0 if male else 1]
        struct.pack_into("<i", data, p + lay.gender, sex)
        if game == 3:
            struct.pack_into("<3i", data, p + 0xF0, *((3, 4, 5) if family else (-1, -1, -1)))
            struct.pack_into("<3i", data, p + 0xFC, -1, -1, -1)
        elif family:
            data[p + lay.father:p + lay.father + 2] = b"Pa"
            data[p + lay.mother:p + lay.mother + 2] = b"Ma"
    return bytes(data)


def roster_for(game: int, people):
    data = save_for(game, people)
    return checker.vv1_roster(data) if game == 1 else checker.vv25_roster(game, data, [])


def mask_file(game: int, value: dict, stored: dict, roster: dict, magic: bytes | None = None) -> bytes:
    n = 256 if game in (1, 2, 3) else 150
    v = [value.get(i, 0) for i in range(n)]
    s = [stored.get(i, 0) for i in range(n)]
    r = [roster.get(i, 0) for i in range(n)]

    def nib(vals):
        out = bytearray(len(vals) // 2)
        for i, x in enumerate(vals):
            out[i >> 1] |= (x << 4) if i & 1 else x
        return bytes(out)
    if game == 1:
        return b"VM02" + nib(v) + struct.pack(f"<{n}I", *r)
    if game == 2:
        return (magic or b"VM06") + struct.pack(f"<{n}I", *r) + bytes(v)
    if game == 3:
        return b"MSK4" + bytes(v) + struct.pack(f"<{n}I", *s)
    if game == 4:
        return b"VVMK" + struct.pack("<II", 3, n) + bytes(v) + struct.pack(f"<{n}I", *s) + struct.pack(f"<{n}I", *r)
    return (magic or b"VM06") + struct.pack(f"<{n}I", *r) + nib(v)


class CheckerFixtures(unittest.TestCase):
    """scripts/vvfp_consistency_check.py reports orphans WRONG (repairable), per game, read-only."""

    def village(self, game: int, file: bytes) -> list[tuple[str, str, str]]:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory())) / "g"
        (folder / DATA / "Village Masks").mkdir(parents=True)
        people = PEOPLE if game >= 3 else PEOPLE[:4]
        (folder / SAVE_NAMES[game].format(slot=1)).write_bytes(save_for(game, people))
        name = checker.VV_MASK_FILES.get(game, "Village Masks - Save {slot}.dat").format(slot=1)
        (folder / DATA / "Village Masks" / name).write_bytes(file)
        before = (folder / DATA / "Village Masks" / name).read_bytes()
        rep = checker.check(folder, 1, game)
        self.assertEqual((folder / DATA / "Village Masks" / name).read_bytes(), before, "read-only")
        return [line for line in rep.lines if "Village Masks" in line[0]]

    def scenario(self, game: int) -> bytes:
        roster = roster_for(game, PEOPLE if game >= 3 else PEOPLE[:4])
        ids = {v.rank: v.ident for v in roster}
        dee = roster_for(game, [DEE])[0].ident
        value = {1: 1, 5: 3, 6: 4, 7: 2}
        stored = {1: ids[1], 5: dee, 7: ids[2]}
        if game >= 3:
            value[8] = 5
            stored[8] = ids[4]
        held = dict(ids)
        held.update({5: dee, 7: ids[2]})
        if game >= 3:
            held[8] = ids[4]
        return mask_file(game, value, stored, held)

    def test_orphans_are_wrong_and_the_rest_kept_in_every_game(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                lines = self.village(game, self.scenario(game))
                wrong = [text for _, verdict, text in lines if verdict == "WRONG"]
                where = "entry" if game == 3 else "record"
                self.assertEqual(len(wrong), 2, lines)
                self.assertTrue(wrong[0].startswith(f"{where} 6: Red Mask -- kept for a villager who is no longer"))
                self.assertTrue(wrong[1].startswith(f"{where} 7: Purple Mask -- kept with no villager's identity"))
                self.assertTrue(all("(repairable: the first-load check removes it, after asking)" in t for t in wrong))
                note = [text for _, verdict, text in lines if verdict == "NOTE"]
                self.assertTrue(note and note[0].startswith(f"{3 if game >= 3 else 2} other mask entries kept"), lines)

    def test_a_clean_file_is_ok(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                roster = roster_for(game, PEOPLE[:4])
                ids = {v.rank: v.ident for v in roster}
                lines = self.village(game, mask_file(game, {1: 1}, {1: ids[1]}, ids))
                self.assertEqual([v for _, v, _ in lines], ["OK"], lines)

    def test_another_villages_file_is_not_judged(self):
        for game in (2, 5):
            with self.subTest(game=game):
                lines = self.village(game, mask_file(game, {1: 1, 5: 2}, {}, {0: 11, 1: 12, 2: 13, 5: 14}))
                self.assertEqual([v for _, v, _ in lines], ["NOTE"], lines)
                self.assertIn("another village's mask file", lines[0][2])

    def test_an_older_name_only_file_is_matched_by_name(self):
        for game in (2, 5):
            with self.subTest(game=game):
                roster = roster_for(game, PEOPLE[:4])
                names = {v.rank: v.name_hash for v in roster}
                dee = roster_for(game, [DEE])[0].name_hash
                held = dict(names)
                held.update({5: dee, 9: names[2]})
                lines = self.village(game, mask_file(game, {5: 3, 9: 2}, {}, held, b"VM04" if game == 2 else b"VM05"))
                wrong = [text for _, verdict, text in lines if verdict == "WRONG"]
                self.assertEqual(len(wrong), 1, lines)
                self.assertTrue(wrong[0].startswith("record 6: Red Mask"), lines)


class OrphanMaskWiringTests(unittest.TestCase):
    """The sources: every companion defines the pair, the prompt asks, the builds link the Repairs log."""

    def test_every_companion_defines_the_scan_and_the_repair(self):
        for game, rel in COMPANIONS.items():
            src = _source(rel)
            with self.subTest(game=game):
                # The Lost Children's companion is A New Home's source with its own parts added.
                included = _source(COMPANIONS[1]) if game == 2 else src
                self.assertIn('#include "../shared/orphan_masks.h"', included)
                self.assertRegex(src, r"static int vvfp_xc_masks_scan\(int game, int slot\) \{\n"
                                      rf"    return game == {game} \?")
                self.assertIn("static int vvfp_xc_masks_repair(int game, int slot) {", src)
                self.assertIn(f"vv_om_commit({game}, slot, path, &gone, &table));", src)
                # Only what the prompt listed AND is still an orphan at the answer is removed.
                self.assertIn("vv_om_still(&", src)

    def test_the_prompt_asks_and_acts_on_the_answer(self):
        bridge = _source("native/shared/crosscheck_bridge.h")
        self.assertIn("masks = vvfp_xc_masks_scan(game, slot);", bridge)
        self.assertIn("|| stats < 0 || masks < 0) {", bridge)
        self.assertIn("|| vvfp_xc.stats > 0 || vvfp_xc.masks > 0;", bridge)
        self.assertIn("vv_om_describe(vvfp_xc.masks, ", bridge)
        # Approved by Repair Saves & Logs: removed at load, without asking; at the quit after an answered Repair.
        self.assertIn("(void)vvfp_xc_masks_repair(game, slot);", bridge)
        self.assertIn("ok &= vvfp_xc_masks_repair(game, slot) != 0;", bridge)
        om = _source("native/shared/orphan_masks.h")
        self.assertIn('"- %d mask entries for villagers who are no longer in the village. "', om)
        self.assertIn('"- 1 mask entry for a villager who is no longer in the village. "', om)
        self.assertIn('#define VV_OM_BACKUP_SUFFIX L".before-v1.35.59-repair"', om)

    def test_every_origins_build_links_the_save_folder_resolver(self):
        for game, rel in BUILD_SCRIPTS.items():
            with self.subTest(game=game):
                self.assertIn('(Join-Path $projectRoot "native\\shared\\save_folder.c")', _source(rel))

    def test_no_marker_is_needed(self):
        # A repaired village's scan finds nothing, so nothing is added to the Repair Saves & Logs re-arm list.
        tools = _source("src/vv_log_tools.py")
        block = tools.split("REARM_MARKERS: tuple", 1)[1].split("\n)\n", 1)[0]
        self.assertIn("Graves Logged", block)
        self.assertNotIn("Village Masks", block)


if __name__ == "__main__":
    unittest.main()
