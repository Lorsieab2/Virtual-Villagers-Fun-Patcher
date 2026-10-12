"""What the patcher costs a frame at 256 villagers, in all five games (v1.35.70).

The owner, playing A New Home with 256 villagers, asked for every patcher-made
slowdown to be found and fixed in every game without changing what the games
do.  Measured with the harnesses below (a warm cache, 256 villagers, New
Believers with 150 Heathens), before and after:

  - The Cause of Death tick ran once per villager HEAD DRAWN in The Secret
    City and New Believers (their companions have no once-a-frame call):
    about 1.35 ms and 4.4 ms a frame.  It now runs its passes once a draw
    pass: about 17 us and 29 us.  Paced or not, a village's play leaves the
    tick's tables identical after every frame.
  - The Secret City's mask lookup fingerprinted every record for every
    villager drawn, masked or not (about 1.1 ms a frame).  A villager with
    no mask stored under their identity now answers at once (about 18 us a
    frame for an unmasked village); the answer is the same.  With every
    villager masked it still hashed every record per villager drawn (about
    1.4 ms); v1.35.71 re-reads them and hashes only a record whose identity
    bytes changed (about 0.43 ms), every answer the full scan's.
  - The Lost Children's route descent translated the whole 168 x 168 field
    on every waypoint (about 6 us a call); it now translates the few cells
    it reads (about 0.1 us), with every waypoint the same.
  - Every Births, Conceptions or Deaths record read every file of its log,
    in every folder, three times, and looked the save folder up again per
    file: a record of the sixth 256-record round read 2.3 MB.  The scans'
    results are kept per file until the file changes; such a record now
    reads about 0.2 MB (the file it goes into), and every file written is
    byte-for-byte the same.

Each harness builds with the MSVC toolchain the DLL build scripts name, and is
skipped where it is not installed.  Nothing here touches the real
Documents\\LDW: every harness redirects Documents to a throwaway folder.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
BUILD = (ROOT / "scripts" / "build_vv1_parentage_dll.ps1").read_text(encoding="utf-8")


def _toolchain():
    vs = re.search(r'\$vsTools = "([^"]+)"', BUILD).group(1)
    sdk = re.search(r'\$sdkRoot = "([^"]+)"', BUILD).group(1)
    ver = re.search(r'\$sdkVersion = "([^"]+)"', BUILD).group(1)
    return Path(vs), Path(sdk), ver


def _compile(source: Path, exe: Path, work: Path, defines=(), fixed=False, includes=()):
    vs, sdk, ver = _toolchain()
    cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
    if not cl.exists():
        raise unittest.SkipTest("MSVC x86 toolchain not installed")
    cmd = [str(cl), "/nologo", "/O2", "/MT", "/W3", "/D_CRT_SECURE_NO_WARNINGS"]
    cmd += [f"/D{d}" for d in defines]
    cmd += ["/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
            "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt")]
    for inc in includes:
        cmd += ["/I", str(inc)]
    cmd += [str(source), f"/Fe{exe}", f"/Fo{work}\\", "/link"]
    if fixed:
        cmd += ["/FIXED", "/DYNAMICBASE:NO", "/BASE:0x400000"]
    cmd += [f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
            f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}",
            "kernel32.lib", "user32.lib", "gdi32.lib", "shell32.lib", "advapi32.lib", "gdiplus.lib",
            "ole32.lib"]
    build = subprocess.run(cmd, capture_output=True, text=True, cwd=work)
    if build.returncode != 0:
        raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])


class _Work(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix="vvfc_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def docs(self, name: str) -> Path:
        folder = self.work / name
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        return folder


class OriginsCompanionFrameCostTests(_Work):
    """Each game's Origins companion, a frame of play at 256 villagers."""

    def test_every_game_frame_costs_little_and_opens_no_file(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                out = self.work / f"fc{game}"
                out.mkdir()
                exe = out / f"frame_cost_vv{game}.exe"
                _compile(NATIVE / "shared" / "frame_cost_harness.c", exe, out, (f"FC_GAME={game}",), fixed=True)
                run = subprocess.run([str(exe), str(self.docs(f"docs_fc{game}"))], capture_output=True,
                                     text=True, timeout=600)
                self.assertIn("== 0 failure(s) ==", run.stdout, run.stdout)
                self.assertEqual(run.returncode, 0, run.stdout)
                self.assertIn("no file is opened or probed in 200 frames without masks (0)", run.stdout)
                self.assertIn("no file is opened or probed in 200 frames with masks (0)", run.stdout)
                if game == 3:
                    # v1.35.71: every villager masked was about 1.4 ms a frame.
                    self.assertIn("ok   The Secret City, every villager masked, costs under 1 ms", run.stdout)
                    self.assertIn("ok   a masked frame with no change hashes no record again (0)", run.stdout)
                    self.assertIn("ok   a rename hashes that one record again (1)", run.stdout)
                    self.assertIn("ok   every mask answer is the full scan's over births, deaths, reloads, "
                                  "renames and twins (0 differ)", run.stdout)
                    self.assertIn("ok   the story reaches masked villagers and twin groups", run.stdout)

    def test_the_secret_city_answers_an_unmasked_villager_without_the_live_scan(self):
        source = (NATIVE / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c").read_text(
            encoding="utf-8", errors="replace")
        getter = source[source.index("int __stdcall VV3_GetMaskForRecord(void *record)"):]
        getter = getter[:getter.index("\n}\n")]
        self.assertLess(getter.index("vv3_mask_has_stored_fingerprint(fpv)"),
                        getter.index("vv3_mask_live_refresh()"))

    def test_the_secret_city_masked_lookup_hashes_only_a_changed_record(self):
        """v1.35.71: the getter's live scan no longer hashes every record per villager drawn."""
        source = (NATIVE / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c").read_text(
            encoding="utf-8", errors="replace")
        getter = source[source.index("int __stdcall VV3_GetMaskForRecord(void *record)"):]
        getter = getter[:getter.index("\n}\n")]
        self.assertNotIn("vv3_mask_unique_live_index(fpv)", getter)
        self.assertNotIn("vv3_mask_live_fingerprint_count(fpv)", getter)
        self.assertLess(getter.index("slots = vv3_mask_live_refresh();"),
                        getter.index("vv3_mask_unique_live_index_in(fpv, slots)"))
        refresh = source[source.index("static int vv3_mask_live_refresh(void) {"):]
        refresh = refresh[:refresh.index("\n}\n")]
        # Every record, every call; every byte the fingerprint reads is compared.
        self.assertIn("for (i = 0; i < slots; ++i, rec += VV3_STRIDE) {", refresh)
        self.assertIn("memcmp(c->name, rec + VV3_NAME, VV3_NAME_LEN)", refresh)
        self.assertIn("c->gender != rec[VV3_GENDER]", refresh)
        for k in range(6):
            self.assertIn(f"c->prefs[{k}] != prefs[{k}]", refresh)
        self.assertIn("if (slots != g_vv3_live_slots || base != g_vv3_live_base) {", refresh)


class CauseTickCostTests(_Work):
    """The Cause of Death tick: once a draw pass, and the same records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.exe = cls.work / "cause_tick_cost_harness.exe"
        _compile(NATIVE / "vvfp_cause_of_death" / "cause_tick_cost_harness.c", cls.exe, cls.work,
                 includes=(NATIVE / "shared", NATIVE / "vvfp_cause_of_death"))

    def test_the_passes_run_once_a_frame_in_every_game(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                run = subprocess.run([str(self.exe), "cost", str(self.docs(f"docs_cost{game}")), str(game)],
                                     capture_output=True, text=True, timeout=600)
                self.assertIn("== 0 failure(s) ==", run.stdout, run.stdout)
                self.assertIn("the passes run once a frame (50 in 50 frames)", run.stdout, run.stdout)
                self.assertEqual(run.returncode, 0, run.stdout)

    def test_pacing_changes_nothing_the_tick_records(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                runs = []
                for pace in ("0", "1"):
                    run = subprocess.run([str(self.exe), "story", str(self.docs(f"docs_story{game}_{pace}")),
                                          str(game), pace], capture_output=True, text=True, timeout=600)
                    self.assertEqual(run.returncode, 0, run.stdout)
                    runs.append(run.stdout)
                frames = [line for line in runs[1].splitlines() if line.startswith("FRAME ")]
                self.assertEqual(len(frames), 40, runs[1])
                self.assertGreater(len({line.split()[-1] for line in frames}), 2,
                                   "the story changes the tick's tables")
                self.assertEqual(runs[0], runs[1])

    def test_only_the_draw_driven_games_are_paced(self):
        source = (NATIVE / "vvfp_cause_of_death" / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        pace = source[source.index("static int cod_pass_starts(int game)"):]
        pace = pace[:pace.index("\n}\n")]
        self.assertIn("if (game != 3 && game != 5) {\n        return 1;", pace)
        tick = source[source.index("__declspec(dllexport) void __stdcall VvfpCauseTick(int game)"):]
        tick = tick[:tick.index("\n}\n")]
        # The cheap part (the stand-in's mark, the temporary records) still runs on every call.
        self.assertLess(tick.index("standin_pending = 0;"), tick.index("cod_pass_starts(g_game)"))
        self.assertLess(tick.index("temporary_name[i] = 0;"), tick.index("cod_pass_starts(g_game)"))


class RouteDescentCostTests(_Work):
    def test_the_lost_childrens_descent_is_the_same_and_cheap(self):
        exe = self.work / "descent_cost_harness.exe"
        _compile(NATIVE / "vvfp_pathfinding" / "descent_cost_harness.c", exe, self.work)
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=600)
        self.assertIn("== 0 failure(s) ==", run.stdout, run.stdout)
        self.assertIn("is the same as the whole-field descent's (60000 calls)", run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)


class LogScanCostTests(_Work):
    """The shipped Parentage Export: a record reads its own file, not the history."""

    def test_a_record_reads_the_file_it_goes_into_not_every_file(self):
        exe = self.work / "log_scan_cost_harness.exe"
        _compile(NATIVE / "parentage_export" / "log_scan_cost_harness.c", exe, self.work)
        dll = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
        run = subprocess.run([str(exe), str(dll), "6"], capture_output=True, text=True, timeout=900)
        self.assertIn("== 0 failure(s) ==", run.stdout, run.stdout)
        self.assertEqual(run.returncode, 0, run.stdout)
        files = [line for line in run.stdout.splitlines() if line.startswith("FILE ")]
        logs = [line for line in files if "Births and Conceptions Log" in line]
        self.assertEqual(len(logs), 6, run.stdout)
        rounds = [int(m.group(1)) for m in re.finditer(r"round \d+: (\d+) bytes read per record", run.stdout)]
        self.assertEqual(len(rounds), 6)
        # Flat, not growing with the history: the last round reads at most twice the first.
        self.assertLess(rounds[-1], rounds[0] * 2, rounds)

    def test_the_scan_memo_forgets_a_file_that_changed(self):
        source = (NATIVE / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        same = source[source.index("static int scan_same_stat("):]
        same = same[:same.index("\n}\n")]
        for field in ("nFileSizeHigh", "nFileSizeLow", "ftLastWriteTime", "ftCreationTime"):
            self.assertIn(field, same)
        # Never kept from a read that failed.
        self.assertIn("if (have_stat && read) {", source)
        self.assertIn("if (have_stat && !ferror(file)) {", source)


if __name__ == "__main__":
    unittest.main()
