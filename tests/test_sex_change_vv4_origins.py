"""A villager's sex changed (native/shared/sex_change.h): The Tree of Life's masks ("VVFP VV4 Origins Icons.dll",
native/vv4_origins_icons) stay theirs, through the DLL's own export VvfpVillagerSexChanged and through the save's
"Sex Changes" log.

Each case runs the real DLL in tests/story_emulator.py on the stock executable, with an emulated disk
(tests/head_look_emulation.py's Disk) and a village in the game's own record table.  The mask is the one the DLL
answers through VvfpMaskOf (the store the Story companion and the log exporters read); the follow runs through
Vv4MaskCacheSurface, the per-frame export the game's present hook calls.
  * the change in play: the record's sex flipped as sex_change.h writes it and the export told: the mask stays, and
    the file written now names the villager by the new identity -- a reload with the new sex finds it;
  * the save not saved after the change: with the slot's log naming the villager the mask is found; without it, it
    is not; a name two living villagers share is never guessed.

THE BUTTON.  Change Appearance's "Change sex..." (native/shared/sex_change_ui.h) is driven in the companion's real
dialog procedure and chooser export by native/vv4_origins_icons/sex_change_ui_harness.c
(scripts/build_sex_change_ui_harness.ps1): Yes changes the sex at once, No nothing; a villager carrying or nursing a
baby is asked with the carrying sentence and keeps the pregnancy fields; the story villagers are refused; Undo changes does not change it back; an OK with only the sex changed is no change
for the executable.  The window and the warning box on screen: the harness's shot mode (-Shots <folder>).
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

try:
    import pefile  # noqa: F401
    import unicorn  # noqa: F401

    from head_look_emulation import DOCS, GAMES, Disk
    from story_emulator import Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK = {
    3: ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe",
    4: ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe",
    5: ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe",
}
DLLS = {
    3: ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll",
    4: ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll",
    5: ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll",
}
MALE, FEMALE = 0, 1
NAMES = ("Kai", "Lani", "Moku", "Nalu")
SEXES = (MALE, FEMALE, MALE, FEMALE)
FATHER, MOTHER = 0x1BC0, 0x1BD9          # VV4 / VV5: the parents' names
BLUE, RED = 1, 3


def have(game: int) -> bool:
    return HAVE_EMULATOR and STOCK[game].is_file() and DLLS[game].is_file()


BUTTON_HARNESS = ROOT / "scripts" / "build_sex_change_ui_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")


def have_compiler() -> bool:
    return sys.platform == "win32" and CL.is_file() and shutil.which("powershell") is not None


# Every check the harness makes, by game (The Secret City's chief and stand-in; New Believers' roles 12 and 17,
# a Heathen's and a believer's faith fields; the Gender presentation checkbox and its row, a story villager told why).
BUTTON_CHECKS = {3: 27, 4: 24, 5: 31}


def run_button_harness(test: unittest.TestCase, game: int) -> None:
    """The "Change sex..." button in the game's real dialog procedure and chooser export (test mode)."""
    run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUTTON_HARNESS),
                          "-Games", str(game)], capture_output=True, text=True, timeout=900)
    out = run.stdout + run.stderr
    test.assertEqual(run.returncode, 0, out)
    test.assertIn(f"game {game}: {BUTTON_CHECKS[game]} checks, 0 failures", out)
    test.assertNotIn("FAIL", out)


def fnv(h: int, data: bytes) -> int:
    for b in data:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def text(raw: bytes, n: int = 25) -> bytes:
    return raw[:n].split(b"\0", 1)[0]


def log_file(slot: int = 1) -> str:
    return (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {slot}\\Data\\"
            f"Sex Changes\\Sex Changes - Save {slot}.txt").lower()


class OriginsGame:
    """One game in the emulator with its Origins DLL, a village and the save slot (1)."""

    def __init__(self, game: int, disk_from: "OriginsGame | None" = None):
        self.game = game
        self.g = dict(GAMES[game])
        self.p = Process(STOCK[game].read_bytes(), DLLS[game])
        self.disk = Disk(self.p)
        self.opened: list[str] = []
        opener = self.disk._open

        def tracked(path: str):
            self.opened.append(path.lower())
            return opener(path)

        self.disk._open = tracked
        self.p.api_handlers["CreateFileA"] = lambda p: tracked(p.cstring(p.arg(0)))
        self.p.api_handlers["CreateFileW"] = lambda p: tracked(p.wstring(p.arg(0)))
        self.p.api_handlers["SHGetFolderPathA"] = self._folder_a
        self.p.api_handlers["SHGetFolderPathW"] = self._folder_w
        self.p.api_handlers["wsprintfW"] = self._wsprintf_w
        self.p.api_handlers["VirtualAlloc"] = lambda p: (p.alloc(max(p.arg(1), 1)), 16)
        self.p.tick = 1_000_000
        if disk_from is not None:
            self.disk.files = dict(disk_from.disk.files)
            self.disk.folders = set(disk_from.disk.folders)
        for va, size in self.extra_pages():
            if not self.p.mapped(va, size):
                self.p.mu.mem_map(va & ~0xFFF, ((va + size + 0xFFF) & ~0xFFF) - (va & ~0xFFF))
        manager = self.p.alloc(self.g["slot_field"] + 0x100)
        self.p.put32(self.g["manager"], manager)
        self.p.put32(manager + self.g["slot_field"], 1)

    @staticmethod
    def _folder_a(p):
        p.write(p.arg(4), DOCS.encode() + b"\0")
        return 0, 20

    @staticmethod
    def _wsprintf_w(p):
        """wsprintfW (cdecl): %ls / %s wide strings, %d / %u / %x numbers, %c, %%."""
        fmt, out, k, i = p.wstring(p.arg(1)), [], 2, 0
        while i < len(fmt):
            c = fmt[i]
            if c != "%":
                out.append(c)
                i += 1
                continue
            j = i + 1
            while j < len(fmt) and fmt[j] in "-0123456789.l":
                j += 1
            kind = fmt[j]
            if kind == "%":
                out.append("%")
            elif kind == "s":
                out.append(p.wstring(p.arg(k)))
                k += 1
            elif kind in "du":
                v = p.arg(k)
                out.append(str(v - (1 << 32) if kind == "d" and v & 0x80000000 else v))
                k += 1
            elif kind in "xX":
                out.append(format(p.arg(k), kind))
                k += 1
            elif kind == "c":
                out.append(chr(p.arg(k)))
                k += 1
            i = j + 1
        text_out = "".join(out)
        p.write(p.arg(0), text_out.encode("utf-16-le") + b"\0\0")
        return len(text_out), 0

    @staticmethod
    def _folder_w(p):
        p.write(p.arg(4), DOCS.encode("utf-16-le") + b"\0\0")
        return 0, 20

    def extra_pages(self):
        return []

    def record(self, i: int) -> int:
        return self.g["records"] + i * self.g["stride"]

    def villager(self, i: int, name: str, sex: int, *, father: str = "", mother: str = "") -> int:
        r = self.record(i)
        self.p.write(r + self.g["present"], b"\x01")
        self.p.write(r + self.g["name"], name.encode().ljust(25, b"\0"))
        self.p.put32(r + self.g["sex"], sex)
        self.p.put32(r + self.g["age"], 600)
        if self.game in (4, 5):
            self.p.write(r + FATHER, father.encode().ljust(25, b"\0"))
            self.p.write(r + MOTHER, mother.encode().ljust(25, b"\0"))
        self.live(r)
        return r

    def live(self, r: int) -> None:
        """What the game holds on a living villager beyond the identity (overridden per game)."""

    def village(self, names=NAMES, sexes=SEXES) -> "OriginsGame":
        for i, (name, sex) in enumerate(zip(names, sexes)):
            self.villager(i, name, sex)
        return self

    def later(self) -> None:
        self.p.tick += 1000

    def change(self, i: int, slot: int = 1) -> int:
        """The sex field flipped as sex_change.h's vv_sex_change_apply writes it, and the DLL told."""
        r = self.record(i)
        before = self.p.alloc(self.g["stride"])
        self.p.write(before, self.p.read(r, self.g["stride"]))
        now = self.p.u32(r + self.g["sex"])
        self.p.put32(r + self.g["sex"], MALE if now == FEMALE else FEMALE)
        return self.p.export("VvfpVillagerSexChanged", self.game, slot, r, before)

    def mask(self, i: int) -> int:
        self.later()
        return self.p.export("VvfpMaskOf", self.record(i))

    def masks_file(self) -> str | None:
        for path in reversed(self.opened):
            if "village masks - save 1.dat" in path and not path.endswith(".tmp"):
                return path
        return None

    def log(self, lines: bytes) -> None:
        self.disk.files[log_file()] = lines
        self.disk.folders.add(log_file().rsplit("\\", 1)[0])


class Vv4Game(OriginsGame):
    def __init__(self, disk_from=None):
        super().__init__(4, disk_from)

    def identity(self, i: int) -> int:
        r = self.record(i)
        h = fnv(2166136261, self.p.read(r + self.g["sex"], 4))
        h = fnv(h, text(self.p.read(r + self.g["name"], 25)) + b"\xff")
        h = fnv(h, text(self.p.read(r + FATHER, 25)) + b"\xfe")
        h = fnv(h, text(self.p.read(r + MOTHER, 25)) + b"\xfd")
        return h or 1

    def frame(self) -> None:
        """The present hook's per-frame export: the sweep, and the follow once the records have been seen."""
        self.later()
        self.p.export("Vv4MaskCacheSurface", 0)

    def settle(self) -> None:
        for _ in range(3):
            self.frame()

    def write_masks(self, masks: dict[int, int], ids: dict[int, int] | None = None) -> str:
        """A version-3 file as the DLL writes it: masks, their identities, the roster."""
        count = 150
        roster = [self.identity(i) if self.p.read(self.record(i) + self.g["present"], 1) != b"\0" else 0
                  for i in range(count)]
        ids = ids or {}
        body = bytes(masks.get(i, 0) for i in range(count))
        fps = b"".join(struct.pack("<I", ids.get(i, roster[i]) if masks.get(i) else 0) for i in range(count))
        data = b"VVMK" + struct.pack("<II", 3, count) + body + fps + b"".join(struct.pack("<I", r) for r in roster)
        path = (f"{DOCS}\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Village Masks\\"
                f"Village Masks - Save 1.dat").lower()
        folder = path
        while "\\" in folder:
            folder = folder.rsplit("\\", 1)[0]
            self.disk.folders.add(folder)
        self.disk.files[path] = data
        return path

    def file_ids(self, path: str) -> list[int]:
        data = self.disk.files[path]
        count = struct.unpack_from("<I", data, 8)[0]
        return list(struct.unpack_from(f"<{count}I", data, 12 + count))


@unittest.skipUnless(have(4), "unicorn/pefile, the stock VV4 or the DLL is missing")
class Vv4MasksFollowASexChange(unittest.TestCase):
    def masked(self) -> Vv4Game:
        g = Vv4Game().village()
        g.write_masks({1: RED})
        g.settle()
        self.assertEqual(g.mask(1), RED)
        return g

    def test_the_mask_follows_a_sex_change_in_play(self):
        g = self.masked()
        self.assertEqual(g.change(1), 1)
        self.assertEqual(g.mask(1), RED)
        g.settle()
        self.assertEqual(g.mask(1), RED, "the next frames' follow keeps it")
        path = g.masks_file()
        self.assertIsNotNone(path)
        self.assertEqual(g.file_ids(path)[1], g.identity(1), "the file names the new identity")
        # A reload with the new sex (the save saved after the change) finds it.
        later = Vv4Game(disk_from=g).village(sexes=(MALE, MALE, MALE, FEMALE))
        later.settle()
        self.assertEqual(later.mask(1), RED)

    def test_the_log_finds_them_when_the_save_was_not_saved(self):
        g = self.masked()
        g.change(1)
        g.settle()
        lost = Vv4Game(disk_from=g).village()          # the save still holds the old sex
        lost.settle()
        self.assertEqual(lost.mask(1), 0, "without the log the mask is not found")
        g.log(b"F\tM\tLani\r\n")
        found = Vv4Game(disk_from=g).village()
        found.settle()
        self.assertEqual(found.mask(1), RED, "the log naming Lani finds it")
        path = found.masks_file()
        self.assertEqual(found.file_ids(path)[1], found.identity(1), "and the file is written so")

    def test_a_name_two_living_villagers_share_is_never_guessed(self):
        g = self.masked()
        g.change(1)
        g.settle()
        g.log(b"F\tM\tLani\r\n")
        twin = Vv4Game(disk_from=g).village(names=NAMES + ("Lani",), sexes=SEXES + (FEMALE,))
        twin.settle()
        self.assertEqual(twin.mask(1), 0)
        self.assertEqual(twin.mask(4), 0)

    def test_a_later_rename_is_still_one(self):
        g = self.masked()
        g.change(1)
        g.settle()
        g.p.write(g.record(1) + g.g["name"], b"Leilani".ljust(25, b"\0"))
        g.settle()
        self.assertEqual(g.mask(1), RED)

    def test_another_game_or_nothing_kept_is_not_carried(self):
        g = Vv4Game().village()
        g.settle()
        r = g.record(0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 5, 1, r, r), 0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 4, 1, 0, r), 0)


@unittest.skipUnless(have_compiler(), "the MSVC x86 compiler or PowerShell is missing")
class Vv4ChangeSexButton(unittest.TestCase):
    def test_the_button_in_the_real_dialog(self):
        run_button_harness(self, 4)


if __name__ == "__main__":
    unittest.main()
