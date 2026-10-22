"""Both Factions: Nature and Magic (The Secret City).

The owner: buy BOTH the Faction of Nature and the Faction of Magic, both
working at once, without crashing or breaking saves; the save keeps a stock
single faction (the one bought first) and the second one lives in a per-save
file (docs/vv3-both-factions.md).

Everything here runs the shipped bytes: The Secret City as the patcher renders
it (the whole public catalog, all three population modes, and the 256
Villagers build), with the shipped "VVFP VV3 Both Factions.dll" mapped beside
it in an emulator (tests/story_emulator.py) and a small in-memory file system
for its per-save file.  The game's own routines run for real -- the Tech
screen's purchase, the save routine, the loader, the herb draw and the Tech
screen draw -- with only their display, sound and disk calls replaced by stubs.

* why the owner's cheated save broke: the stock loader refuses a save whose
  Nature and Magic are both above 0, and the whole village load fails;
* the other faction is bought on the Tech screen at its stock price, and the
  stock game (no companion) still refuses it;
* every save is stock-valid: the second faction is written as 0 and kept in
  the file; the stock game loads that save with the first faction only;
* save -> load gives both factions back, every level of each;
* both herbs are drawn; both factions get the Tech screen's sunbeam;
* the companion installs only over the stock bytes, all or nothing.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import HEAP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    HEAP = 0

ID = "vv3_both_factions"
DLL_LEAF = "VVFP VV3 Both Factions.dll"
DLL = ROOT / "assets" / "both_factions" / DLL_LEAF
ROW = ROOT / "data" / "vv3_both_factions_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

TECH = 0x582618
POINTS = 0x582644
NATURE, MAGIC = 5, 6
STRING_ALREADY_CHOSEN = 0x419
COST_TABLE = 0x4A818C
SIDE = "C:\\Docs\\LDW\\Game\\Virtual Villagers Fun Patcher\\Save {s}\\Data\\Factions\\Virtual Villagers 3 Second Faction - Save {s}.dat"
SAVE_BYTES = 0x12F1C
SAVE_TECH = 0x6CC0
SAVE_POINTS = 0x6CDC

SITES = {
    0x427D1F: "B918265800E837F2FFFF",
    0x428A08: "B918265800E84EE6FFFF",
    0x4657D5: "56B918265800E8F017FCFF",
    0x464AE4: "8B87D400000083F8FF",
    0x420BD5: "C3",
    0x4656FE: "7F36",
    0x465734: "7ECA",
    0x465583: "83BED4000000FF0F8494000000",
}


def stock_exe() -> Path:
    build = {b.id: b for b in patcher.load_builds()}["vv3"]
    return ROOT / "inputs" / "vv3-stock-copy" / build.input_name


def have_stock() -> bool:
    try:
        return stock_exe().is_file()
    except Exception:  # pragma: no cover
        return False


@functools.lru_cache(maxsize=None)
def render(mode: str, expanded: bool = False) -> bytes:
    """The whole public catalog for The Secret City (and, with `expanded`,
    the experimental 256 Villagers build)."""
    build = {b.id: b for b in patcher.load_builds()}["vv3"]
    ids = [p.id for p in patcher.load_public_fun_patches()
           if p.game_id == "vv3" and (expanded or p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS)]
    data, _ = patcher.render_patched_bytes(stock_exe(), build, mode, ids)
    return bytes(data)


@functools.lru_cache(maxsize=None)
def stock_image() -> bytes:
    import pefile as _pe
    return _pe.PE(str(stock_exe()), fast_load=True).get_memory_mapped_image()


def stock_cost(level: int, tech: int) -> int:
    """The stock price of the next level (0x427020): dword [0x4A818C + 4*(level + 1 + 3*tech)]."""
    return struct.unpack_from("<I", stock_image(), COST_TABLE + 4 * (level + 1 + 3 * tech) - 0x400000)[0]


class Files:
    """A small file system for the companion's per-save file (kernel32's
    file calls, by name, as the companion makes them)."""

    def __init__(self, proc):
        self.proc = proc
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.handles: dict[int, list] = {}
        self.next_handle = 0x100
        self.error = 0
        self.locked: set[str] = set()
        for name in ("SHGetSpecialFolderPathA", "CreateDirectoryA", "CreateFileA", "ReadFile", "WriteFile",
                     "FlushFileBuffers", "CloseHandle", "MoveFileExA", "DeleteFileA", "GetLastError",
                     "GetSystemTimeAsFileTime"):
            proc.api_handlers[name] = getattr(self, "_" + name)

    @staticmethod
    def key(path: str) -> str:
        return path.lower()

    def _SHGetSpecialFolderPathA(self, p):
        p.write(p.arg(1), b"C:\\Docs\0")
        return 1, 16

    def _CreateDirectoryA(self, p):
        self.dirs.add(self.key(p.cstring(p.arg(0))))
        return 1, 8

    def _CreateFileA(self, p):
        path = p.cstring(p.arg(0))
        access, disposition = p.arg(1), p.arg(4)
        k = self.key(path)
        if k in self.locked:
            self.error = 32                        # ERROR_SHARING_VIOLATION
            return 0xFFFFFFFF, 28
        if disposition == 3:                       # OPEN_EXISTING
            if k not in self.files:
                self.error = 2                     # ERROR_FILE_NOT_FOUND
                return 0xFFFFFFFF, 28
            data = bytearray(self.files[k])
        else:                                      # CREATE_ALWAYS
            data = bytearray()
        h = self.next_handle
        self.next_handle += 4
        self.handles[h] = [k, data, 0, bool(access & 0x40000000)]
        return h, 28

    def _ReadFile(self, p):
        h, buf, n, got = p.arg(0), p.arg(1), p.arg(2), p.arg(3)
        k, data, pos, _ = self.handles[h]
        chunk = bytes(data[pos:pos + n])
        p.write(buf, chunk)
        self.handles[h][2] = pos + len(chunk)
        p.put32(got, len(chunk))
        return 1, 20

    def _WriteFile(self, p):
        h, buf, n, wrote = p.arg(0), p.arg(1), p.arg(2), p.arg(3)
        entry = self.handles[h]
        entry[1] += p.read(buf, n)
        p.put32(wrote, n)
        return 1, 20

    def _FlushFileBuffers(self, p):
        return 1, 4

    def _CloseHandle(self, p):
        k, data, _, writing = self.handles.pop(p.arg(0))
        if writing:
            self.files[k] = bytes(data)
        return 1, 4

    def _MoveFileExA(self, p):
        src, dst = self.key(p.cstring(p.arg(0))), self.key(p.cstring(p.arg(1)))
        if dst in self.files and not (p.arg(2) & 1):
            self.error = 183
            return 0, 12
        self.files[dst] = self.files.pop(src)
        return 1, 12

    def _DeleteFileA(self, p):
        return int(self.files.pop(self.key(p.cstring(p.arg(0))), None) is not None), 4

    def _GetLastError(self, p):
        return self.error, 0

    def _GetSystemTimeAsFileTime(self, p):
        p.write(p.arg(0), struct.pack("<II", 0x11111111, 0x01D00000))
        return 0, 4

    def side(self, slot: int) -> bytes | None:
        return self.files.get(self.key(SIDE.format(s=slot)))


class Game:
    """The rendered executable with (or without) the companion, the
    technology manager and the stubs its display, sound and disk calls need."""

    def __init__(self, mode: str = "stock", *, companion: bool = True, expanded: bool = False,
                 install: bool = True, unpatched: bool = False):
        # `unpatched`: the stock executable itself, as the player's untouched install has it.
        exe = stock_exe().read_bytes() if unpatched else render(mode, expanded)
        self.proc = Process(exe, DLL if companion else None)
        p = self.proc
        if not companion:
            self._bind_game_imports()
        self.files = Files(p)
        self.messages: list[int] = []
        self.sounds: list[int] = []
        self.draws: list[tuple] = []
        self.images: list[tuple] = []
        self.parts: list[tuple] = []
        # Display, sound and text: recorded, never run.
        p.stub(0x42E0F0, lambda q: (self.messages.append(q.arg(0)) or 0, 8))   # message (text id, -1)
        p.stub(0x424110, lambda q: (self.sounds.append(q.arg(0)) or 0, 4))     # sound
        p.stub(0x42E0B0, lambda q: (0, 0))
        p.stub(0x42F740, lambda q: (0x0E00F000, 0))
        p.stub(0x42F190, lambda q: (0x0E00F100, 12))
        p.stub(0x41C7A0, lambda q: (0, 4))
        p.stub(0x41C2F0, lambda q: (0, 0))
        p.stub(0x401AF0, lambda q: (1, 8))                                     # the faction confirm: OK
        self.levels(1, 1, 1, 1, 1, 0, 0)
        if companion and install:
            p.export("VvfpStartup", 3, 0)

    def _bind_game_imports(self):
        """No companion: the game's own imports still reach stubs."""
        from story_emulator import API_STUBS
        p = self.proc
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in getattr(p._exe_pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = imp.name.decode()
                p.mu.mem_write(imp.address, struct.pack("<I", stub))

    # ---- state ---------------------------------------------------------
    def levels(self, *values: int) -> None:
        for i, v in enumerate(values):
            self.proc.put32(TECH + 4 * i, v)

    def level(self, tech: int) -> int:
        return self.proc.u32(TECH + 4 * tech)

    def points(self, value: int | None = None) -> int:
        if value is not None:
            self.proc.put32(POINTS, value)
        return self.proc.u32(POINTS)

    # ---- the Tech screen -----------------------------------------------
    def buy(self, tech: int) -> int:
        """Click technology `tech` on the Tech screen (message 8, button tech+1)."""
        p = self.proc
        screen = p.alloc(0x200)
        p.write(screen, struct.pack("<I", 0x49E87C))
        return p.call(0x465640, [8, tech + 1], ecx=screen) & 0xFF

    def draw_tech_screen(self) -> list[tuple]:
        """The Tech screen's draw 0x4649C0; returns the images it drew."""
        p = self.proc
        screen = p.alloc(0x200)
        drawn: list[tuple] = []
        mgr = p.alloc(0x40)
        p.stub(0x42E9D0, lambda q: (mgr, 0))
        p.stub(0x42EB90, lambda q: (drawn.append(("image", q.arg(0), q.arg(1), q.arg(2), q.arg(3))) or 0, 0x14))
        p.stub(0x42ECA0, lambda q: (drawn.append(("pip", q.arg(0), q.arg(1), q.arg(2))) or 0, 0x18))
        p.stub(0x408940, lambda q: (mgr, 0))
        p.stub(0x408A10, lambda q: (drawn.append(("shade",)) or 0, 0x14))
        for va, pop in ((0x42E250, 12), (0x429A00, 0), (0x42E2A0, 0), (0x42E230, 0), (0x40D1A0, 4)):
            p.stub(va, lambda q, pop=pop: (0, pop))
        p.call(0x464920, [1], ecx=screen)       # the screen opens (stock: picks the chosen faction)
        p.call(0x4649C0, [], ecx=screen)
        return drawn

    def tech_screen_frame(self, chosen: int, rolls) -> list[tuple]:
        """The Tech screen's frame 0x465530 with [screen+0xD4] = `chosen` and the
        game's rand(n) answering from `rolls`; returns the particles spawned
        (type, x, y, petal flag)."""
        p = self.proc
        screen = p.alloc(0x200)
        p.put32(screen + 0xD4, chosen & 0xFFFFFFFF)
        flag = p.alloc(0x10)
        p.write(flag, b"\1")
        spawned: list[tuple] = []
        answers = iter(rolls)
        p.stub(0x42E0C0, lambda q: (0, 0))
        p.stub(0x436E60, lambda q: (0, 12))
        p.stub(0x4377F0, lambda q: (0, 8))
        p.stub(0x42E230, lambda q: (flag, 0))
        p.stub(0x4032D0, lambda q: (next(answers), 0))
        p.stub(0x429400, lambda q: (spawned.append((q.arg(0), q.arg(1), q.arg(2), q.arg(5))) or 0, 0x20))
        p.stub(0x429710, lambda q: (0, 0))
        p.call(0x465530, [], ecx=screen)
        return spawned

    # ---- the world -----------------------------------------------------
    def draw_world(self) -> list[int]:
        """The world object's draw 0x420B30; returns the parts it listed."""
        p = self.proc
        parts: list[int] = []
        p.stub(0x42E440, lambda q: (parts.append((q.arg(0), q.arg(1))) or 0, 0x10))
        p.stub(0x4358D0, lambda q: (0, 4))
        p.call(0x420B30, [], ecx=0x5607D8)
        return [part for layer, part in parts if layer == 3]

    # ---- save and load -------------------------------------------------
    def new_game_object(self) -> int:
        p = self.proc
        game = p.alloc(0x13000 + 0x8000)
        p.write(game, struct.pack("<I", 0x4808E0))
        # Systems saved before the technologies: recognisable bytes, so the
        # fingerprint covers real content.
        p.write(game + 8, bytes((i * 7 + 3) & 0xFF for i in range(0x40)))
        return game

    def save(self, game: int, slot: int) -> bytes:
        """The game's save of `slot` (0x427C60), as written to disk."""
        p = self.proc
        written: list[bytes] = []
        # The systems' own savers write into the buffer; only the levels
        # (0x426F60) and the tech points (0x427110) run for real.
        for va in (0x412C50, 0x42D460, 0x454930, 0x4264A0, 0x426540, 0x436DD0, 0x45EF80):
            p.stub(va, lambda q: (1, 4))
        p.stub(0x435790, lambda q: (1, 8))

        def writer(q):
            written.append(q.read(q.arg(0), q.arg(1)))
            return 1, 12
        p.stub(0x403530, writer)
        p.call(0x427C60, [slot], ecx=game)
        assert written, "nothing was written"
        return written[0]

    def load(self, game: int, slot: int, data: bytes) -> int:
        """The game's load of `slot` (0x428880) from `data` (the file's buffer)."""
        p = self.proc

        def read(q):
            out, n = q.arg(0), q.arg(1)
            q.write(out, data[:n].ljust(n, b"\0"))
            return 1, 12
        p.stub(0x4033A0, read)
        p.stub(0x428810, lambda q: (0, 0))
        for va in (0x412BD0, 0x42D3E0, 0x426480, 0x426520, 0x435710, 0x437290, 0x45C860, 0x454CB0):
            p.stub(va, lambda q: (1, 4))
        # The levels (0x427060) and the tech points (0x4270F0) load for real.
        p.stub(0x45C990, lambda q: (0, 0))
        return p.call(0x428880, [slot], ecx=game) & 0xFF

    def reset(self) -> None:
        """What the game does before every load and every new village (0x426F40)."""
        self.levels(1, 1, 1, 1, 1, 0, 0)


def emulated(cls):
    cls = unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(cls)
    return unittest.skipUnless(have_stock(), "stock The Secret City is not in inputs/")(cls)


def factions(buffer: bytes) -> tuple[int, int]:
    return struct.unpack_from("<II", buffer, SAVE_TECH + 4 * NATURE)


def with_factions(buffer: bytes, nature: int, magic: int) -> bytes:
    out = bytearray(buffer)
    struct.pack_into("<II", out, SAVE_TECH + 4 * NATURE, nature, magic)
    return bytes(out)


def bought(mode: str = "stock", *, first: int = NATURE, second_levels: int = 1, first_levels: int = 1,
           expanded: bool = False) -> Game:
    """A village that bought `first` then the other faction, on the Tech screen."""
    g = Game(mode, expanded=expanded)
    g.points(10_000_000)
    for _ in range(first_levels):
        g.buy(first)
    for _ in range(second_levels):
        g.buy(NATURE + MAGIC - first)
    return g


# ---- the row, the guide and the files ----------------------------------------

class BothFactionsRow(unittest.TestCase):

    def row(self) -> dict:
        return json.loads(ROW.read_text(encoding="utf-8"))

    def test_the_row_is_present_for_vv3_and_enabled(self):
        row = self.row()
        self.assertEqual(row["id"], ID)
        self.assertEqual(row["game_id"], "vv3")
        self.assertTrue(row["enabled"])
        self.assertTrue(row["catalog_enabled"])
        self.assertFalse(row["catalog_hidden"])
        self.assertEqual(row["dependencies"], [])
        self.assertEqual(row["patches"], [])

    def test_default_on_for_vv3_only(self):
        self.assertEqual([p.name for p in patcher.BOTH_FACTIONS_FEATURE_PATHS], [ROW.name])
        games = {p.game_id for p in patcher.load_fun_patches() if p.id == ID}
        self.assertEqual(games, {"vv3"})

    def test_the_declared_detours_are_the_companions_sites(self):
        detours = {int(d["va"], 16): d for d in self.row()["runtime_detours"]}
        self.assertEqual(set(detours), set(SITES))
        for va, stock in SITES.items():
            with self.subTest(va=hex(va)):
                self.assertEqual(detours[va]["stock_bytes"], stock)
                self.assertEqual(len(detours[va]["written_bytes"]) // 2, len(stock) // 2)

    def test_the_companion_is_shipped_and_hash_pinned(self):
        [item] = self.row()["companion_files"]
        self.assertEqual(item["destination"], DLL_LEAF)
        self.assertEqual(item["source"], f"assets/both_factions/{DLL_LEAF}")
        self.assertEqual(hashlib.sha256(DLL.read_bytes()).hexdigest().upper(), item["sha256"])

    def test_the_loader_knows_the_companion_in_its_appended_place(self):
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS[-1], DLL_LEAF)
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(re.findall(r'"([^"]+)"', body), list(patcher.STARTUP_LOADER_COMPANIONS))
        self.assertLess(len(patcher.STARTUP_LOADER_COMPANIONS), 30)
        self.assertIn(DLL_LEAF.encode(), (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes())

    def test_the_dll_exports_only_vvfpstartup(self):
        import pefile as _pe
        pe = _pe.PE(str(DLL))
        names = {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertEqual({n for n in names if n.startswith(b"Vvfp")}, {b"VvfpStartup"})

    def test_start_over_deletes_the_file(self):
        import vv_save_layout as layout
        reset = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        vv3 = reset[reset.index("/* VV3 */"):reset.index("/* VV4 */")]
        self.assertIn("BOTH_FACTIONS_FORMAT", vv3)
        self.assertIn('#define BOTH_FACTIONS_FORMAT DATA_FORMAT("Factions", "Virtual Villagers 3 Second Faction")',
                      reset)
        self.assertIn(b"Factions\\Virtual Villagers 3 Second Faction - Save %d.dat",
                      (ROOT / "assets" / "save_reset" / "VVFP Save Reset.dll").read_bytes())
        # Start Over deletes the older-layout name AND its place in the save's own folder
        # (vv_ps_new_path_w), which is exactly where the companion writes.
        for slot in range(1, 6):
            older = f"Virtual Villagers Fun Patcher Data\\Factions\\Virtual Villagers 3 Second Faction - Save {slot}.dat"
            found_slot, own, kind = layout.per_save_place(older)
            self.assertEqual((found_slot, kind), (slot, "file"))
            self.assertEqual("C:\\Docs\\LDW\\Game\\" + own, SIDE.format(s=slot))

    def test_the_guide_and_the_readme(self):
        guide = (ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8")
        self.assertIn(f'"{ID}"', guide)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"`{ID}`", readme)
        self.assertIn("**Both Factions: Nature and Magic**", readme)
        self.assertTrue((ROOT / "docs" / "vv3-both-factions.md").is_file())


# ---- the stock executable: every reader of the two factions -------------------

@unittest.skipUnless(have_stock(), "stock The Secret City is not in inputs/")
class EveryFactionReader(unittest.TestCase):
    """The gate list: every place the stock game reads Nature (5) or Magic
    (6) is one the design handles.  A reader that is not in this list fails
    the test (docs/vv3-both-factions.md, "Every reader")."""

    # call site of 0x426FC0 -> technology
    READERS = {
        0x415517: NATURE,   # Ghostly Dream (nature or healing), island event 16
        0x415657: MAGIC,    # Ghostly Dream (research or architecture), island event 17
        0x420BB9: NATURE,   # the world draw: the Nature herb (level 2)
        0x420BDD: MAGIC,    # the world draw: the Magic herb (level 2) -- reached with both (0x420BD5)
        0x4347C3: NATURE,   # Nature 1: fruit refill
        0x4593DC: MAGIC,    # Magic 1: +1 tech point per research
        0x45FE9D: MAGIC,    # Magic 3: +10 population maximum
        0x4601C4: NATURE,   # Nature 3: longevity
        0x464942: NATURE,   # the Tech screen opens: the chosen faction
        0x464969: MAGIC,
        0x464DBB: NATURE,   # the Tech screen hover: preview while neither is chosen
        0x464DCB: MAGIC,
        0x464EB6: NATURE,
        0x464EC6: MAGIC,
        0x4656F7: NATURE,   # the purchase: "already chosen" (removed at 0x4656FE)
        0x46572D: MAGIC,    # (removed at 0x465734)
        0x46575F: NATURE,   # the purchase: the confirmation while neither is chosen
        0x46576F: MAGIC,
    }
    # calls of 0x426FC0 with a computed technology: every technology alike
    COMPUTED = {0x4325E2, 0x464A0C, 0x464AB0, 0x464C65}

    def test_every_reader_is_in_the_gate_list(self):
        import capstone
        import pefile as _pe
        pe = _pe.PE(str(stock_exe()))
        text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
        code = text.get_data()
        base = pe.OPTIONAL_HEADER.ImageBase + text.VirtualAddress
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        found: dict[int, object] = {}
        window: list = []
        for ins in md.disasm(code, base):
            if ins.mnemonic == "call" and ins.op_str == "0x426fc0":
                push = next((w for w in reversed(window) if w.mnemonic == "push"), None)
                ecx = next((w for w in reversed(window) if w.mnemonic == "mov" and w.op_str.startswith("ecx,")), None)
                self.assertIsNotNone(ecx, hex(ins.address))
                self.assertEqual(ecx.op_str, "ecx, 0x582618", hex(ins.address))
                value = push.op_str if push is not None else None
                found[ins.address] = int(value) if value is not None and value.isdigit() else value
            if ins.mnemonic in ("int3",) or (ins.mnemonic == "ret"):
                window = []
            else:
                window = (window + [ins])[-8:]
        faction_calls = {va: t for va, t in found.items() if t in (NATURE, MAGIC)}
        computed = {va for va, t in found.items() if not isinstance(t, int)}
        self.assertEqual(faction_calls, self.READERS)
        self.assertEqual(computed, self.COMPUTED)
        # No other code names the two levels directly (0x58262C, 0x582630).
        for ins in md.disasm(code, base):
            self.assertNotIn("0x58262c", ins.op_str)
            self.assertNotIn("0x582630", ins.op_str)

    def test_the_loader_refuses_both_and_the_writer_copies_both(self):
        image = stock_image()

        def at(va, n):
            return image[va - 0x400000:va - 0x400000 + n]
        # 0x427060: [in+0x14] (Nature) and [in+0x18] (Magic) both nonzero -> refused.
        self.assertEqual(at(0x427067, 3), bytes.fromhex("8B4714"))
        self.assertEqual(at(0x427074, 3), bytes.fromhex("8B4718"))
        self.assertEqual(at(0x427079, 2), bytes.fromhex("7559"))       # jne 0x4270D4 (al = 0)
        self.assertEqual(at(0x4270D5, 2), bytes.fromhex("32C0"))
        # 0x426F60 copies all seven levels, the factions at +0x14 and +0x18.
        self.assertEqual(at(0x426F80, 6), bytes.fromhex("8B5114895014"))
        self.assertEqual(at(0x426F86, 6), bytes.fromhex("8B4918894818"))
        # The save routine calls it on the buffer at game + 0x6CC8 (= buffer + 0x6CC0).
        self.assertEqual(at(0x427D18, 6), bytes.fromhex("8D8EC86C0000"))

    def test_the_two_herbs_are_separate_items_and_places(self):
        image = stock_image()

        def at(va, n):
            return image[va - 0x400000:va - 0x400000 + n]
        # Drop handlers registered for map regions 30 (Herb6) and 31 (Herb7).
        self.assertIn(bytes.fromhex("6A06684013420" + "06A1E"), image)
        self.assertIn(bytes.fromhex("6A0668D013420" + "06A1F"), image)
        # Each gives "Gathering herbs" (task 0x73) its own carried item, 0x24 and 0x25.
        self.assertEqual(at(0x4213B6, 10), bytes.fromhex("6A73C744240824000000"))
        self.assertEqual(at(0x421446, 10), bytes.fromhex("6A73C744240825000000"))
        # The draw: herb_nature.png (image 0x99) and herb_magic.png (0x98) at their own places.
        self.assertEqual(at(0x420D63, 5), bytes.fromhex("B950050000"))   # the Magic herb's place (0x32, 0x550)
        self.assertEqual(at(0x420D83, 5), bytes.fromhex("B9B5040000"))   # the Nature herb's place (0x78, 0x4B5)
        # Part 5 draws [obj+0x18], loaded from image 0x98 (herb_magic.png); part 6 draws
        # [obj+0x1C], image 0x99 (herb_nature.png).
        self.assertEqual(at(0x420AE3, 5), bytes.fromhex("6898000000"))
        self.assertEqual(at(0x420AF9, 3), bytes.fromhex("894618"))
        self.assertEqual(at(0x420AF2, 5), bytes.fromhex("6899000000"))
        self.assertEqual(at(0x420B08, 3), bytes.fromhex("89461C"))
        self.assertEqual(at(0x420D5B, 3), bytes.fromhex("8B5618"))       # part 5 draws [esi+0x18]
        self.assertEqual(at(0x420D8F, 3), bytes.fromhex("8B461C"))       # part 6 draws [esi+0x1C]

    def test_the_sites_hold_the_stock_bytes(self):
        image = stock_image()
        for va, stock in SITES.items():
            with self.subTest(va=hex(va)):
                self.assertEqual(image[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock)
        self.assertEqual(image[0x420BD6 - 0x400000:0x420BD8 - 0x400000], bytes.fromhex("6A06"))


# ---- emulated: the shipped bytes ---------------------------------------------

@emulated
class WhyTheCheatedSaveBroke(unittest.TestCase):
    """The owner set both factions with a cheat and the save broke."""

    def test_the_stock_loader_refuses_a_save_with_both_factions(self):
        g = Game(unpatched=True, companion=False)
        game = g.new_game_object()
        good = g.save(game, 1)
        self.assertEqual(factions(good), (0, 0))
        for nature, magic in ((1, 0), (0, 3), (3, 0)):
            g.reset()
            self.assertEqual(g.load(game, 1, with_factions(good, nature, magic)), 1)
            self.assertEqual((g.level(NATURE), g.level(MAGIC)), (nature, magic))
        for nature, magic in ((1, 1), (3, 3), (2, 1)):
            with self.subTest(nature=nature, magic=magic):
                g.reset()
                self.assertEqual(g.load(game, 1, with_factions(good, nature, magic)), 0,
                                 "the whole village load fails")

    def test_the_companion_never_lets_such_a_save_be_written(self):
        g = bought("stock", second_levels=3, first_levels=3)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (3, 3))
        for slot in (1, 2, 5, 21):
            with self.subTest(slot=slot):
                data = g.save(g.new_game_object(), slot)
                self.assertEqual(factions(data), (3, 0))


@emulated
class ThePurchase(unittest.TestCase):

    def test_the_stock_game_refuses_the_other_faction(self):
        for unpatched in (True, False):
            g = Game(unpatched=unpatched, companion=False)
            g.points(1_000_000)
            g.buy(NATURE)
            g.buy(MAGIC)
            self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 0))
            self.assertIn(STRING_ALREADY_CHOSEN, g.messages)

    def test_the_other_faction_is_bought_at_its_stock_price_in_every_mode(self):
        for mode in MODES:
            for first in (NATURE, MAGIC):
                with self.subTest(mode=mode, first=first):
                    g = Game(mode)
                    second = NATURE + MAGIC - first
                    start = 1_000_000
                    g.points(start)
                    g.buy(first)
                    after_first = g.points()
                    self.assertEqual(start - after_first, stock_cost(0, first))
                    self.assertEqual(g.buy(second), 0)
                    self.assertEqual((g.level(first), g.level(second)), (1, 1))
                    self.assertEqual(after_first - g.points(), stock_cost(0, second))
                    self.assertNotIn(STRING_ALREADY_CHOSEN, g.messages)
                    for lvl in (1, 2):
                        before = g.points()
                        g.buy(second)
                        self.assertEqual(before - g.points(), stock_cost(lvl, second))
                    self.assertEqual(g.level(second), 3)
                    g.buy(second)                                   # fully researched: nothing
                    self.assertEqual(g.level(second), 3)

    def test_not_enough_points_buys_nothing(self):
        g = Game()
        g.points(stock_cost(0, NATURE))
        g.buy(NATURE)
        g.points(stock_cost(0, MAGIC) - 1)
        g.buy(MAGIC)
        self.assertEqual(g.level(MAGIC), 0)
        self.assertEqual(g.points(), stock_cost(0, MAGIC) - 1)


@emulated
class SaveAndLoad(unittest.TestCase):

    def round_trip(self, mode, *, first, first_levels, second_levels, expanded=False, slot=2):
        g = bought(mode, first=first, first_levels=first_levels, second_levels=second_levels,
                   expanded=expanded)
        game = g.new_game_object()
        data = g.save(game, slot)
        second = NATURE + MAGIC - first
        expect = {first: first_levels, second: 0}
        self.assertEqual(factions(data), (expect[NATURE], expect[MAGIC]), "the save holds the first only")
        self.assertIsNotNone(g.files.side(slot))
        g.reset()
        self.assertEqual(g.load(game, slot, data), 1)
        self.assertEqual((g.level(first), g.level(second)), (first_levels, second_levels))
        return g, game, data

    def test_save_load_gives_both_factions_back_every_level_every_mode(self):
        for mode in MODES:
            for first in (NATURE, MAGIC):
                for second_levels in (1, 2, 3):
                    with self.subTest(mode=mode, first=first, second_levels=second_levels):
                        self.round_trip(mode, first=first, first_levels=3 - (second_levels == 3),
                                        second_levels=second_levels)

    def test_the_256_villagers_build(self):
        g, game, data = self.round_trip("immediate_fixed", first=NATURE, first_levels=2, second_levels=3,
                                        expanded=True)
        self.assertEqual(len(data), 0x1A4B4)

    def test_save_load_save_load_keeps_both(self):
        g, game, data = self.round_trip("stock", first=MAGIC, first_levels=1, second_levels=1)
        g.buy(NATURE)                                   # the second faction goes on after a load
        data = g.save(game, 2)
        self.assertEqual(factions(data), (0, 1))
        g.reset()
        self.assertEqual(g.load(game, 2, data), 1)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (2, 1))

    def test_the_save_loads_in_the_stock_game_with_the_first_faction_only(self):
        g, game, data = self.round_trip("collection_progression", first=NATURE, first_levels=2, second_levels=3)
        for unpatched in (True, False):
            s = Game(unpatched=unpatched, companion=False)
            s.files.files.update(g.files.files)         # the file is there: the stock game ignores it
            self.assertEqual(s.load(s.new_game_object(), 2, data), 1)
            self.assertEqual((s.level(NATURE), s.level(MAGIC)), (2, 0))

    def test_another_save_of_the_slot_gets_nothing(self):
        g, game, data = self.round_trip("stock", first=NATURE, first_levels=1, second_levels=2)
        other = bytearray(data)
        struct.pack_into("<I", other, SAVE_POINTS, struct.unpack_from("<I", data, SAVE_POINTS)[0] + 1)
        g.reset()
        self.assertEqual(g.load(game, 2, bytes(other)), 1)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 0))
        g.reset()
        self.assertEqual(g.load(game, 3, data), 1, "another slot")
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 0))

    def test_an_older_save_still_finds_its_entry(self):
        g, game, first_save = self.round_trip("stock", first=NATURE, first_levels=1, second_levels=1)
        g.buy(MAGIC)
        g.points(g.points() - 7)
        second_save = g.save(game, 2)
        g.reset()
        self.assertEqual(g.load(game, 2, first_save), 1)       # a restored backup of the earlier save
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 1))
        g.reset()
        self.assertEqual(g.load(game, 2, second_save), 1)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 2))

    def test_the_backup_generation_loads_with_its_slots_file(self):
        g = bought("stock", first=MAGIC, second_levels=2)
        game = g.new_game_object()
        data = g.save(game, 4)
        backup = g.save(game, 24)
        self.assertEqual(backup, data)
        g.reset()
        self.assertEqual(g.load(game, 24, backup), 1)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (2, 1))

    def test_one_faction_writes_no_file(self):
        g = Game()
        g.points(1_000_000)
        g.buy(NATURE)
        data = g.save(g.new_game_object(), 1)
        self.assertEqual(factions(data), (1, 0))
        self.assertEqual(g.files.files, {})

    def test_an_unreadable_file_is_never_replaced_and_the_save_stays_stock(self):
        g = bought("stock", second_levels=1)
        g.files.locked.add(Files.key(SIDE.format(s=1)))
        data = g.save(g.new_game_object(), 1)
        self.assertEqual(factions(data), (1, 0))
        self.assertIsNone(g.files.side(1))

    def test_a_damaged_file_is_set_aside_not_trusted(self):
        g, game, data = self.round_trip("stock", first=NATURE, first_levels=1, second_levels=2)
        key = Files.key(SIDE.format(s=2))
        damaged = bytearray(g.files.files[key])
        damaged[0] ^= 0xFF
        g.files.files[key] = bytes(damaged)
        g.reset()
        self.assertEqual(g.load(game, 2, data), 1)
        self.assertEqual((g.level(NATURE), g.level(MAGIC)), (1, 0))
        self.assertTrue(any(".unreadable-" in k for k in g.files.files), "kept aside, never deleted")

    def test_a_new_village_starts_with_no_second_faction(self):
        g = bought("stock", first=NATURE, second_levels=1)
        g.reset()                                     # Start Over / a new tribe (0x427F70 -> 0x426F40)
        g.buy(MAGIC)                                  # Magic first in the new village
        g.buy(NATURE)
        data = g.save(g.new_game_object(), 3)
        self.assertEqual(factions(data), (0, 1), "the new village's first faction is Magic")


@emulated
class BothFactionsWork(unittest.TestCase):

    def test_both_herbs_are_drawn(self):
        for companion, both in ((True, [6, 5]), (False, [6])):
            g = Game(companion=companion)
            g.levels(1, 1, 1, 1, 1, 2, 2)
            herbs = [part for part in g.draw_world() if part in (5, 6)]
            self.assertEqual(herbs, both)
            for nature, magic, herbs_alone in ((2, 0, [6]), (0, 2, [5]), (1, 1, []), (3, 3, [6, 5] if companion else [6])):
                g.levels(1, 1, 1, 1, 1, nature, magic)
                self.assertEqual([part for part in g.draw_world() if part in (5, 6)], herbs_alone)

    def test_both_factions_are_lit_on_the_tech_screen(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                g = Game(mode)
                g.levels(1, 1, 1, 1, 1, 2, 3)
                drawn = g.draw_tech_screen()
                sunbeams = sorted(x[2] for x in drawn if x[0] == "image" and x[1] == 0x90)
                self.assertEqual(sunbeams, [0x16F - 0x28, 0x283 - 0x28])
                self.assertNotIn(("shade",), drawn)
                self.assertEqual(len([x for x in drawn if x[0] == "pip"]), 5 + 2 + 3, "every level filled in")

    def test_one_faction_draws_as_the_stock_game(self):
        for companion in (True, False):
            g = Game(companion=companion)
            g.levels(1, 1, 1, 1, 1, 2, 0)
            drawn = g.draw_tech_screen()
            self.assertEqual(sorted(x[2] for x in drawn if x[0] == "image" and x[1] == 0x90), [0x16F - 0x28])
            self.assertIn(("shade",), drawn)

    def test_both_factions_float_their_own_particles_on_the_tech_screen(self):
        nature = (0xA, 0x16F + 3, 0x92 + 4, 1)          # petals in Nature's column
        magic = (2, 0x283 + 5, 0x92 + 6, 0)             # sparkles in Magic's column
        for mode in MODES:
            with self.subTest(mode=mode):
                g = Game(mode)
                g.levels(1, 1, 1, 1, 1, 1, 2)
                # Each column rolls its own chance (rand(100) < 10), then x, then y.
                self.assertEqual(g.tech_screen_frame(NATURE, [0, 3, 4, 0, 5, 6]), [nature, magic])
                self.assertEqual(g.tech_screen_frame(NATURE, [50, 9, 5, 6]), [magic])
                self.assertEqual(g.tech_screen_frame(MAGIC, [9, 3, 4, 10]), [nature])
                self.assertEqual(g.tech_screen_frame(NATURE, [10, 99]), [])

    def test_one_faction_or_none_floats_as_the_stock_game(self):
        for companion in (True, False):
            with self.subTest(companion=companion):
                g = Game(companion=companion)
                g.levels(1, 1, 1, 1, 1, 0, 2)
                self.assertEqual(g.tech_screen_frame(MAGIC, [0, 5, 6]), [(2, 0x283 + 5, 0x92 + 6, 0)])
                g.levels(1, 1, 1, 1, 1, 0, 0)
                self.assertEqual(g.tech_screen_frame(-1, []), [])
                # Neither bought: the stock preview of the faction under the pointer.
                self.assertEqual(g.tech_screen_frame(NATURE, [0, 3, 4]), [(0xA, 0x16F + 3, 0x92 + 4, 1)])

    def test_every_level_reader_sees_both(self):
        g = bought("stock", first=NATURE, first_levels=3, second_levels=3)
        p = g.proc
        # The Ghostly Dream predicates (island events 16 and 17).
        self.assertEqual(p.call(0x415510) & 0xFF, 1)
        self.assertEqual(p.call(0x415650) & 0xFF, 1)
        # Every other reader asks the getter for its own technology.
        for tech in (NATURE, MAGIC):
            self.assertEqual(p.call(0x426FC0, [tech], ecx=TECH), 3)


@emulated
class Installing(unittest.TestCase):

    def test_installs_every_site_in_every_build(self):
        for mode, expanded in [(m, False) for m in MODES] + [("immediate_fixed", True)]:
            with self.subTest(mode=mode, expanded=expanded):
                g = Game(mode, expanded=expanded)
                for va, stock in SITES.items():
                    self.assertNotEqual(g.proc.read(va, len(stock) // 2).hex().upper(), stock, hex(va))
                self.assertEqual(g.proc.read(0x4656FE, 2), b"\x90\x90")
                self.assertEqual(g.proc.read(0x465734, 2), bytes.fromhex("EBCA"))
                self.assertEqual(g.proc.read(0x420BD5, 1), b"\x90")

    def test_other_games_install_nothing(self):
        g = Game(install=False)
        for game in (1, 2, 4, 5):
            g.proc.export("VvfpStartup", game, 0)
        for va, stock in SITES.items():
            self.assertEqual(g.proc.read(va, len(stock) // 2).hex().upper(), stock)

    def test_a_changed_site_installs_nothing(self):
        for va in SITES:
            with self.subTest(va=hex(va)):
                g = Game(install=False)
                g.proc.write(va, b"\xCC")
                g.proc.export("VvfpStartup", 3, 0)
                # Nothing written: in particular the purchase still refuses the other faction.
                for other, stock in SITES.items():
                    if other != va:
                        self.assertEqual(g.proc.read(other, len(stock) // 2).hex().upper(), stock, hex(other))


if __name__ == "__main__":
    unittest.main()
