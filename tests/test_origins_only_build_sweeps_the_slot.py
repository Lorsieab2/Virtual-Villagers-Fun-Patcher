"""An Origins-only build must carry a working tribe-delete reset, in all five.

Origins writes the per-slot mask files, so Origins has to sweep them: without
the sweep, a new tribe started in a reused slot inherits the old one's masks.
That is why the stub and hook were moved out of the parentage log and into
Origins, and why the case worth testing is the build with Origins and NO
parentage log.

Everything here is read out of a REAL built artifact rather than a manifest.
The stub is located by searching the image for its own strings, not by reading
a declared offset, because the five games place it differently -- VV1/VV4/VV5
in a code cave carried as a patch, VV2/VV3 inside an appended page -- and a
check that trusted the declared placement would not notice bytes that never
reached the file.

Two failure shapes this is built to catch, both of which really happened:

  * The stub landing in a section without the execute characteristic. VV1's
    first placement sat in a non-executable appended section, which is a
    runtime crash rather than a build error.
  * The companion DLL not being shipped. The stub resolves it by name and
    falls through to the game's own delete on failure -- deliberately, so a
    missing DLL costs the sweep and never the save -- so a build that forgets
    it looks perfect: hook present, stub correct, every byte guard green, and
    the feature silently doing nothing. VV5 shipped exactly that, because its
    certified Task9 record substitutes its own companion list.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
IMAGE_BASE = 0x400000

DLL_NAME = b"VVFP Save Reset.dll\x00"
EXPORT_NAME = b"ResetDeletedTribe\x00"
STUB_CODE_OFFSET = 0x28

# The hook is the save-slot menu's OWN call to deleteSave, and the thunk is
# where the stub hands control back. Both measured live in all five running
# games. The game's other caller of deleteSave rotates backup generations and
# passes slot + 0x14, so hooking the handler's own call reaches the reset and
# never ordinary play.
GAMES = {
    "vv1": {
        "exe": "Virtual Villagers - A New Home.exe",
        "patch": "vv1_origins_village_wide_upgrades",
        "hook": 0x13E07,
        "thunk": 0x41BFF0,
    },
    "vv2": {
        "exe": "Virtual Villagers - The Lost Children.exe",
        "patch": "vv2_origins_village_wide_upgrades",
        "hook": 0x14E77,
        "thunk": 0x424C70,
    },
    "vv3": {
        "exe": "Virtual Villagers - The Secret City.exe",
        "patch": "vv3_origins_village_wide_upgrades",
        "hook": 0x1B5D3,
        "thunk": 0x427E00,
    },
    "vv4": {
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "patch": "vv4_origins_village_wide_upgrades",
        "hook": 0x18CD5,
        "thunk": 0x41F1D0,
    },
    "vv5": {
        "exe": "Virtual Villagers - New Believers.exe",
        "patch": "vv5_origins_village_wide_upgrades",
        "hook": 0x193F5,
        "thunk": 0x424690,
    },
}

HAVE_STOCK = all((STOCK / spec["exe"]).is_file() for spec in GAMES.values())


def _sections(data: bytes) -> list[tuple[str, int, int, int, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    head = pe + 24 + opt
    out = []
    for index in range(count):
        base = head + 40 * index
        name = data[base : base + 8].rstrip(b"\x00").decode("latin1")
        _vsz, va, rsz, ro = struct.unpack_from("<IIII", data, base + 8)
        chars = struct.unpack_from("<I", data, base + 36)[0]
        out.append((name, va, rsz, ro, chars))
    return out


def _owning_section(data: bytes, offset: int):
    for section in _sections(data):
        _name, _va, rsz, ro, _chars = section
        if ro <= offset < ro + rsz:
            return section
    return None


def _build(game: str, spec: dict) -> tuple[pathlib.Path, dict]:
    """Apply Origins WITHOUT the parentage log; return the output folder."""
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"{game}_origins_only_"))
    game_dir = work / "game"
    game_dir.mkdir()
    shutil.copy2(STOCK / spec["exe"], game_dir / spec["exe"])
    out_root = work / "out"
    out_root.mkdir()
    run = subprocess.run(
        [
            sys.executable,
            str(ROOT / "src" / "vv_fun_patcher.py"),
            "apply",
            str(game_dir / spec["exe"]),
            "--fun-patch",
            spec["patch"],
            "--output-root",
            str(out_root),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if run.returncode != 0:
        raise AssertionError(
            f"{game}: apply failed: {(run.stdout + run.stderr).strip()[-400:]}"
        )
    folders = [p for p in out_root.iterdir() if p.is_dir()]
    if not folders:
        raise AssertionError(f"{game}: no output folder produced")
    folder = folders[0]
    log = json.loads(
        next(folder.glob("*.patch-log.json")).read_text(encoding="utf-8")
    )
    return folder, log


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class OriginsOnlyBuildSweepsTheSlotTests(unittest.TestCase):
    builds: dict[str, tuple[pathlib.Path, dict]] = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.builds = {game: _build(game, spec) for game, spec in GAMES.items()}

    def test_the_builds_really_exclude_the_parentage_log(self) -> None:
        """Guard the guard: with the log selected, this proves nothing."""
        for game, (_folder, log) in sorted(self.builds.items()):
            with self.subTest(game=game):
                selected = {f.get("id") for f in log.get("selected_features", [])}
                self.assertIn(f"{game}_enable_origins_exclusive_features", selected)
                self.assertFalse(
                    [i for i in selected if str(i).endswith("_write_parentage_log")],
                    f"{game}: the parentage log is in this build, so it does not "
                    "test the Origins-only case at all",
                )

    def test_the_companion_dll_is_shipped(self) -> None:
        for game, (folder, _log) in sorted(self.builds.items()):
            with self.subTest(game=game):
                self.assertTrue(
                    (folder / "VVFP Save Reset.dll").is_file(),
                    f"{game}: the stub resolves VVFP Save Reset.dll by name, but "
                    "the build does not ship it -- the sweep is silently lost",
                )

    def test_the_stub_is_present_and_executable(self) -> None:
        for game, (folder, _log) in sorted(self.builds.items()):
            with self.subTest(game=game):
                data = next(folder.glob("*Modded.exe")).read_bytes()
                at = data.find(DLL_NAME)
                self.assertGreaterEqual(
                    at, 0, f"{game}: the stub is not in the built image"
                )
                self.assertGreaterEqual(
                    data.find(EXPORT_NAME),
                    0,
                    f"{game}: the stub's export name is not in the image",
                )
                section = _owning_section(data, at)
                self.assertIsNotNone(
                    section, f"{game}: the stub is outside every mapped section"
                )
                assert section is not None
                name, _va, _rsz, _ro, chars = section
                self.assertTrue(
                    chars & 0x20000000,
                    f"{game}: the stub sits in {name}, which has no execute "
                    "characteristic -- this is a runtime crash, not a build error",
                )
                self.assertEqual(
                    data[at + STUB_CODE_OFFSET],
                    0x60,
                    f"{game}: the stub's code does not begin with pushad",
                )

    def test_the_stub_calls_the_reset_and_returns_into_the_game(self) -> None:
        for game, (folder, _log) in sorted(self.builds.items()):
            spec = GAMES[game]
            with self.subTest(game=game):
                data = next(folder.glob("*Modded.exe")).read_bytes()
                at = data.find(DLL_NAME)
                section = _owning_section(data, at)
                assert section is not None
                _name, va, _rsz, ro, _chars = section
                code_at = at + STUB_CODE_OFFSET
                code_va = IMAGE_BASE + va + (code_at - ro)

                tail = data[code_at : code_at + 0x40]
                end = tail.find(b"\xff\xd0\x61\xe9")  # call eax; popad; jmp rel32
                self.assertGreaterEqual(
                    end, 0, f"{game}: the stub's tail was not found"
                )
                self.assertEqual(
                    tail[end - 2 : end],
                    bytes([0x6A, int(game[-1])]),
                    f"{game}: the stub does not push game id {game[-1]}",
                )
                jmp_at = code_at + end + 3
                rel = struct.unpack_from("<i", data, jmp_at + 1)[0]
                landed = IMAGE_BASE + va + (jmp_at - ro) + 5 + rel
                self.assertEqual(
                    landed,
                    spec["thunk"],
                    f"{game}: the stub falls through to {landed:#x}, not the "
                    f"game's deleteSave thunk {spec['thunk']:#x}",
                )

    def test_the_hook_reaches_the_stub(self) -> None:
        for game, (folder, _log) in sorted(self.builds.items()):
            spec = GAMES[game]
            with self.subTest(game=game):
                data = next(folder.glob("*Modded.exe")).read_bytes()
                at = data.find(DLL_NAME)
                section = _owning_section(data, at)
                assert section is not None
                _name, va, _rsz, ro, _chars = section
                code_va = IMAGE_BASE + va + (at + STUB_CODE_OFFSET - ro)

                hook = data[spec["hook"] : spec["hook"] + 5]
                self.assertEqual(
                    hook[:1],
                    b"\xe8",
                    f"{game}: the hook is not a call ({hook.hex().upper()}) -- "
                    "the stock delete call was not replaced",
                )
                hook_section = _owning_section(data, spec["hook"])
                assert hook_section is not None
                _hn, hva, _hrsz, hro, _hc = hook_section
                hook_va = IMAGE_BASE + hva + (spec["hook"] - hro)
                target = hook_va + 5 + struct.unpack("<i", hook[1:])[0]
                self.assertEqual(
                    target,
                    code_va,
                    f"{game}: the hook reaches {target:#x}, but the stub's code "
                    f"is at {code_va:#x}",
                )


if __name__ == "__main__":
    unittest.main()
