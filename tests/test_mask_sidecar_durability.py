"""The heathen-mask sidecars can no longer be truncated or silently replaced.

A read-only corruption audit found two ways every game could lose a village's
masks for good:

  * VV2 and VV5 wrote the real sidecar in place with CREATE_ALWAYS -- which
    truncates it before the replacement exists -- and never checked a
    WriteFile, so a crash, a full disk or an I/O error left a short file that
    the loader rejected.
  * In all five games a sidecar that was present but invalid (wrong magic,
    short, another version) loaded as an empty table that the next write
    published over it, and one that existed but could not be OPENED (a
    sharing violation, denied access) was treated exactly like a missing one.

Every game now loads and publishes through native/shared/sidecar_io.h:
temp file, every write checked, flush, then MoveFileEx over the real one; an
invalid file is moved to an unused "<name>.unreadable-<ticks>-<n>" before any
write; an unopenable one is neither read nor written until a throttled retry
opens it; only a genuinely missing file starts empty.

native/shared/sidecar_io_harness.c drives those functions against real files
in a %TEMP% folder (the deny-read case uses an ACL, which unlike an open handle
still lets the file be replaced, so it models the case the old writers would
have destroyed). Each of its guards was mutation-checked: removing any one of
them makes the harness fail. The harness needs the 32-bit MSVC toolchain and is
skipped elsewhere; the static checks below pin each game's use of the helpers.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native/shared/sidecar_io.h"
BUILD = ROOT / "scripts/build_sidecar_io_harness.ps1"
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
VV1 = ROOT / "native/vv1_origins_icons/vv1_origins_icons.c"
VV2 = ROOT / "native/vv2_origins_icons/vv2_origins_icons.c"
VV3 = ROOT / "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
VV4 = ROOT / "native/vv4_origins_icons/vv4_origins_icons.c"
VV5 = ROOT / "native/vv5_task9_origins/vv5_task9_origins.c"

# (source, writer, loader) for each game's mask sidecar.
GAMES = {
    "VV1": (VV1, "vv1_mask_sidecar_save", "vv1_mask_sidecar_load"),
    "VV2": (VV2, "vv2_mask_sidecar_save", "vv2_mask_sidecar_load"),
    "VV3": (VV3, "vv3_mask_write_sidecar_tables", "vv3_mask_read_sidecar"),
    "VV4": (VV4, "vv_write_mask_sidecar", "vv_read_mask_sidecar"),
    "VV5": (VV5, "WriteMaskSidecar", "vv5_mask_sidecar_load"),
}


def function(path: Path, name: str) -> str:
    """The body of a function DEFINITION (never a forward declaration)."""
    source = path.read_text(encoding="utf-8")
    start = re.search(
        r"^(?:static [a-z ]+|(?:__declspec\(dllexport\) )?\w+ __stdcall) \*?"
        + re.escape(name) + r"\([^;{]*\)\s*\{",
        source,
        re.M,
    )
    assert start is not None, f"{path.name}: {name}"
    return source[start.start():source.index("\n}", start.start())]


def code(text: str) -> str:
    """Strip comments, so a comment that names the old call does not count."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


class MaskSidecarDurability(unittest.TestCase):
    def test_every_game_uses_the_shared_helpers(self) -> None:
        for game, (path, _, _) in GAMES.items():
            with self.subTest(game=game):
                source = path.read_text(encoding="utf-8")
                if game == "VV2":
                    # VV2 carries VV1's source, and with it the include.
                    self.assertIn('#include "../vv1_origins_icons/vv1_origins_icons.c"', source)
                else:
                    self.assertIn('#include "../shared/sidecar_io.h"', source)

    def test_no_writer_touches_the_real_file_directly(self) -> None:
        """The in-place CREATE_ALWAYS and the unchecked WriteFile are gone."""
        for game, (path, writer, _) in GAMES.items():
            with self.subTest(game=game):
                body = code(function(path, writer))
                self.assertIn("vv_sidecar_publish(", body)
                for raw in ("CreateFileA", "CREATE_ALWAYS", "WriteFile", "MoveFileEx"):
                    self.assertNotIn(raw, body)

    def test_no_writer_runs_before_its_load_settled(self) -> None:
        """A blocked or never-loaded slot is refused before any path I/O."""
        for game, (path, writer, _) in GAMES.items():
            with self.subTest(game=game):
                body = function(path, writer)
                ready = body.index("vv_sidecar_gate_ready(")
                self.assertLess(ready, body.index("vv_sidecar_publish("))
                path_call = re.search(r"(build_mask_sidecar_path|vv\d?_?\w*sidecar_path)\(", body)
                self.assertIsNotNone(path_call)
                self.assertLess(ready, path_call.start(),
                                "the gate is checked before the path is built")

    def test_every_loader_goes_through_vv_sidecar_load(self) -> None:
        for game, (path, _, loader) in GAMES.items():
            with self.subTest(game=game):
                body = code(function(path, loader))
                self.assertIn("vv_sidecar_load(", body)
                self.assertNotIn("CreateFileA", body)
                self.assertNotIn("ReadFile", body)
                # Bound to the slot and throttled before the path is built.
                self.assertLess(body.index("vv_sidecar_gate_bind("),
                                body.index("vv_sidecar_gate_throttled("))
                self.assertIn("vv_sidecar_gate_block(", body)

    def test_a_blocked_load_never_settles(self) -> None:
        """Each game's latch stays open on a blocked file, so it is retried."""
        vv2 = function(VV2, "vv2_mask_sidecar_load")
        self.assertIn("if (status == VV_SIDECAR_LOAD_BLOCKED) return 0;", vv2)
        vv5 = function(VV5, "vv5_mask_sidecar_load")
        self.assertIn("if (status == VV_SIDECAR_LOAD_BLOCKED) {\n        return 0;", vv5)
        vv4 = function(VV4, "vv_read_mask_sidecar")
        self.assertIn("if (status == VV_SIDECAR_LOAD_BLOCKED) {\n        return 0;", vv4)
        vv3 = function(VV3, "vv3_mask_read_sidecar")
        self.assertIn("case VV_SIDECAR_LOAD_BLOCKED:\n        return;", vv3)
        self.assertLess(vv3.index("case VV_SIDECAR_LOAD_BLOCKED:"),
                        vv3.index("g_vv3_mask_loaded = 1;"))
        self.assertEqual(vv3.count("g_vv3_mask_loaded = 1;"), 1)
        # VV1 has no latch: its per-frame tick retries a slot whose load has
        # not settled, and persists nothing until it has.
        tick = function(VV1, "Vv1MaskTick")
        retry = tick.index("if (!vv_sidecar_gate_ready(&vv1_mask_gate, slot)) {")
        self.assertLess(retry, tick.index("vv1_mask_sidecar_load();"))
        self.assertLess(tick.index("vv1_mask_sidecar_load();"),
                        tick.index("vv1_mask_sweep_dead()"))
        # VV4's writer additionally honours its own latch.
        self.assertIn("if (!g_sidecar_loaded || !vv_sidecar_gate_ready(",
                      function(VV4, "vv_write_mask_sidecar"))

    def test_only_a_missing_file_is_empty(self) -> None:
        load = function(HEADER, "vv_sidecar_load")
        self.assertIn(
            "if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) {", load)
        self.assertIn("if (vv_sidecar_set_aside(path)) {", load)
        aside = code(function(HEADER, "vv_sidecar_set_aside"))
        self.assertIn("MoveFileExA(path, aside, MOVEFILE_WRITE_THROUGH)", aside)
        self.assertNotIn("REPLACE_EXISTING", aside)
        publish = function(HEADER, "vv_sidecar_publish")
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", publish)
        self.assertIn("FlushFileBuffers(h)", publish)
        self.assertIn("|| wrote != sizes[i]) {", publish)

    def test_shipped_builds_use_the_real_writer_and_clock(self) -> None:
        """The harness seams default to the real calls; no game overrides them."""
        header = HEADER.read_text(encoding="utf-8")
        self.assertIn("#define VV_SIDECAR_WRITE_FILE WriteFile", header)
        self.assertIn("#define VV_SIDECAR_TICKS() GetTickCount()", header)
        for game, (path, _, _) in GAMES.items():
            with self.subTest(game=game):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("VV_SIDECAR_WRITE_FILE", source)
                self.assertNotIn("VV_SIDECAR_TICKS", source)

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        self.assertNotIn("FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
