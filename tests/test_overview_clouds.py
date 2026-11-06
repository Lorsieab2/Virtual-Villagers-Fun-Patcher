"""The overview map's clouds (the owner, 2026-11-06): "Disable Clouds on the Overview Map" (vv3, vv4, vv5) and "Push
Clouds Away on the Overview Map" (vv3), both on by default (scripts/build_overview_clouds_features.py).

THE STOCK CODE: each game's overview screen (the Map button) -- its vtable, its draw slot and the five-cloud loop in
it, its event slot, update and activate -- read from the stock executables.  A New Home and The Lost Children have
no clouds on their overview map; The Tree of Life and New Believers push them away from the mouse, The Secret City
does not.

THE MAP, EMULATED: each game's own cloud loop (the real machine code, the sprite draw replaced by a recorder) draws
its five clouds in the stock executable and none in the patched one; every byte the row changes is inside the
overview screen's draw routine, so the village view and every other screen are the stock code.

THE PUSH, EMULATED: "VVFP Push Clouds.dll" is started in The Secret City as VVFP Startup.dll starts it; the same
mouse moves are given to The Tree of Life's own event slot (0x444B70) and to The Secret City's (replaced), and the
same frames to The Tree of Life's own cloud step (0x444AD4..0x444B25) and to The Secret City's update (replaced,
then the stock cloud step 0x46C29F..0x46C2E3): every cloud's position, push and fade agree frame for frame, and The
Secret City's own cloud loop draws each cloud at The Tree of Life's alpha.  All or none: the companion's sites are
covered by tests/test_companion_installs_all_or_none.py.
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

STOCK_DIR = ROOT / "research" / "stock-executables"
EXES = {g: b.input_name for b in patcher.load_builds() for g in (b.id,)}
HAVE_STOCK = all((STOCK_DIR / EXES[f"vv{n}"]).is_file() for n in range(1, 6))
try:
    import capstone
    import pefile
    import unicorn  # noqa: F401

    from story_emulator import HEAP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

DLL_NAME = "VVFP Push Clouds.dll"
DLL = ROOT / "assets" / "push_clouds" / DLL_NAME
DISABLE, PUSH = "Disable Clouds on the Overview Map", "Push Clouds Away on the Overview Map"
CLOUD_GAMES = ("vv3", "vv4", "vv5")

# game: (vtable, draw slot, loop start, loop end, sprite draw, cloud stride, sprite ids (None: one fixed id))
SCREENS = {
    "vv3": (0x49EA04, 0x46C2F0, 0x46C3BD, 0x46C3E3, 0x42EB90, 12, (0x27,)),
    "vv4": (0x48EEAC, 0x4453C0, 0x4454A1, 0x4454D9, 0x44CDB0, 0x18, (0xAE, 0xAF, 0xB0, 0xB1)),
    "vv5": (0x49A448, 0x448510, 0x448623, 0x44865B, 0x44FEF0, 0x18, (0x99, 0x9A, 0x9B, 0x9C)),
}
# The overview screen's draw routine, the range the Disable row may touch (its draw slot to its `ret`).
DRAW_END = {"vv3": 0x46C414, "vv4": 0x44551C, "vv5": 0x44869F}
SLOTS = ((1, 0x46B980), (8, 0x46C070), (9, 0x46B930))
DRAW_CALL = 0x46C3D8
VV4_EVENTS, VV4_STEP, VV4_STEP_END = 0x444B70, 0x444AD4, 0x444B25
VV3_STEP, VV3_STEP_END = 0x46C29F, 0x46C2E3


def _manifest(name: str) -> dict:
    return json.loads((ROOT / "data" / f"{name}_feature.json").read_text(encoding="utf-8"))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=None)
def _stock(game: str) -> bytes:
    return (STOCK_DIR / EXES[game]).read_bytes()


@functools.lru_cache(maxsize=None)
def _rendered(game: str, ids: tuple[str, ...]) -> bytes:
    build = next(b for b in patcher.load_builds() if b.id == game)
    data, _ = patcher.render_patched_bytes(STOCK_DIR / EXES[game], build, "stock", list(ids))
    return bytes(data)


def _image(data: bytes) -> bytes:
    return pefile.PE(data=data).get_memory_mapped_image()


class TheRows(unittest.TestCase):
    def test_the_rows(self):
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in CLOUD_GAMES:
            with self.subTest(game=game):
                row = _manifest(f"{game}_disable_overview_clouds")
                self.assertEqual((row["id"], row["name"], row["game_id"]), (f"{game}_disable_overview_clouds",
                                                                             DISABLE, game))
                self.assertIn(row["id"], public)
                self.assertTrue(row["enabled"])
                self.assertEqual(row["companion_files"], [])
                self.assertEqual(len(row["patches"]), 1)
                self.assertNotIn("dependencies", row)
                for words in ("**On by default.**", "**Needs no other patch.**", "**With this on, the clouds are "
                              "hidden, so", "has no visible effect until this is unticked.**"):
                    self.assertIn(words, row["description"])
        self.assertIn(f"so {PUSH} has no visible effect", _manifest("vv3_disable_overview_clouds")["description"])
        row = _manifest("vv3_push_overview_clouds")
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        self.assertEqual((row["name"], row["game_id"], row["patches"]), (PUSH, "vv3", []))
        self.assertIn(row["id"], public)
        self.assertEqual(row["companion_files"], [{"source": f"assets/push_clouds/{DLL_NAME}",
                                                   "destination": DLL_NAME, "sha256": sha}])
        for words in ("**On by default.**", "**Needs no other patch.**",
                      f"**While {DISABLE} is ticked the clouds are hidden, so this has no visible effect until "
                      f"{DISABLE} is unticked.**", "The Tree of Life"):
            self.assertIn(words, row["description"])

    def test_only_the_games_with_overview_clouds(self):
        ids = {p.id for p in patcher.load_fun_patches() if "overview_clouds" in p.id}
        self.assertEqual(ids, {"vv3_disable_overview_clouds", "vv4_disable_overview_clouds",
                               "vv5_disable_overview_clouds", "vv3_push_overview_clouds"})

    def test_the_generator_reproduces_the_rows(self):
        module = _load_script("build_overview_clouds_features")
        for game in (3, 4, 5):
            self.assertEqual(module.disable_row(game), _manifest(f"vv{game}_disable_overview_clouds"))
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        self.assertEqual(module.push_row(sha), _manifest("vv3_push_overview_clouds"))

    def test_on_by_default_in_select_all_and_owners_defaults(self):
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for row in ("vv3_disable_overview_clouds", "vv4_disable_overview_clouds", "vv5_disable_overview_clouds",
                    "vv3_push_overview_clouds"):
            self.assertTrue(default_fun_patch_selection(row))
            self.assertTrue(owners_default_fun_patch_selection(row))
            self.assertTrue(select_all_fun_patch_selection(row))

    def test_started_by_the_startup_loader_second_word(self):
        names = list(patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertEqual(names.index(DLL_NAME), 12)                 # its bit (append only: never moves)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn(f'    "{DLL_NAME}",\n', header)
        loader = (ROOT / "assets" / "startup" / "VVFP Startup.dll").read_bytes()
        self.assertIn(DLL_NAME.encode(), loader)
        self.assertEqual(hashlib.sha256(loader).hexdigest().upper(), patcher.STARTUP_LOADER_COMPANION["sha256"])

    def test_registered_bundled_documented(self):
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        how_to = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        log = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        guided = {i for entry in guide["patches"] for i in entry.get("ids", [])}
        self.assertIn(f'"assets/push_clouds/{DLL_NAME}"', release)
        self.assertIn("CLOUDS ON THE OVERVIEW MAP", how_to)
        for name in ("vv3_disable_overview_clouds", "vv4_disable_overview_clouds", "vv5_disable_overview_clouds",
                     "vv3_push_overview_clouds"):
            self.assertIn(f'"data/{name}_feature.json"', release)
            self.assertIn(f"- Patch ID: `{name}`", readme)
            self.assertIn(_manifest(name)["description"], readme)
            self.assertIn(name, guided)
        self.assertIn(DISABLE, log)
        self.assertIn(PUSH, log)

    @unittest.skipUnless(HAVE_EMULATOR, "pefile is not installed")
    def test_the_dll_exports_imports_and_shows_no_text(self):
        pe = pefile.PE(str(DLL))
        names = sorted(e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
        self.assertEqual(names, ["VvfpPushCloudsInstalled", "VvfpStartup"])
        imports = {i.name.decode() for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports & {"LoadLibraryA", "LoadLibraryW", "OutputDebugStringA", "OutputDebugStringW",
                                    "MessageBoxA", "MessageBoxW", "DeleteFileW", "CreateFileA", "MoveFileW",
                                    "RegSetValueExW", "Sleep", "CreateThread"}, set())
        for section in pe.sections:
            self.assertFalse(section.Characteristics & 0x20000000 and section.Characteristics & 0x80000000)
        source = (ROOT / "native" / "vvfp_push_clouds" / "vvfp_push_clouds.c").read_text(encoding="utf-8")
        self.assertNotIn("vvfp_tr", source)         # no text of its own: nothing to translate


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "needs the stock executables and capstone/pefile/unicorn")
class TheStockCode(unittest.TestCase):
    """Every address the rows and the companion use is what each stock executable has there."""

    md = None

    @classmethod
    def setUpClass(cls):
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        cls.images = {g: _image(_stock(g)) for g in EXES}

    def _u32(self, game, va):
        return struct.unpack_from("<I", self.images[game], va - 0x400000)[0]

    def _dis(self, game, va, end):
        img = self.images[game]
        return [f"{i.mnemonic} {i.op_str}".strip()
                for i in self.md.disasm(img[va - 0x400000:end - 0x400000], va)]

    def test_the_draw_slot_and_its_cloud_loop(self):
        for game, (vtable, draw, start, end, sprite_draw, stride, sprites) in SCREENS.items():
            with self.subTest(game=game):
                self.assertEqual(self._u32(game, vtable + 4 * 6), draw)
                loop = " ; ".join(self._dis(game, start, end))
                self.assertIn(f"call 0x{sprite_draw:x}", loop)
                self.assertIn(f"add edi, 0x{stride:x}", loop)
                self.assertTrue(self._dis(game, end - 2, end)[0].startswith("jne"))

    def test_the_vv4_and_vv5_cloud_pictures_are_picked_at_activate(self):
        for game, init in (("vv4", 0x4447A0), ("vv5", 0x4478F0)):
            vtable = SCREENS[game][0]
            self.assertEqual(self._u32(game, vtable + 4 * 9), init)
            body = " ; ".join(self._dis(game, init, init + 0x60))
            for sprite in SCREENS[game][6]:
                self.assertIn(f"mov dword ptr [esi], 0x{sprite:x}", body)

    def test_the_vv3_overview_screen(self):
        for slot, stock in SLOTS:
            self.assertEqual(self._u32("vv3", 0x49EA04 + 4 * slot), stock)
        # the cloud loop draws sprite 0x27 at alpha 1.0 through the call 0x46C3D8
        loop = self._dis("vv3", 0x46C3BD, 0x46C3E3)
        self.assertIn("push 0x3f800000", loop)
        self.assertIn("push 0x27", loop)
        self.assertEqual(self.images["vv3"][DRAW_CALL - 0x400000:DRAW_CALL - 0x400000 + 5].hex(), "e8b327fcff")
        # the event slot handles only clicks (message 2): a mouse move does nothing
        self.assertEqual(self._dis("vv3", 0x46B980, 0x46B98A)[:3],
                         ["mov eax, dword ptr [esp + 4]", "sub eax, 2", "push esi"])
        # the update: the leave branch (bytes +0x60 / +0x61, count +0x68 += 5, > 200 returns before the clouds)
        update = " ; ".join(self._dis("vv3", 0x46C0BC, 0x46C101))
        for words in ("cmp byte ptr [esi + 0x61], bl", "cmp byte ptr [esi + 0x60], bl", "add eax, 5",
                      "cmp ecx, 0xc8", "jle 0x46c1aa"):
            self.assertIn(words, update)
        step = " ; ".join(self._dis("vv3", VV3_STEP, VV3_STEP_END))
        for words in ("mov edx, dword ptr [esi + 8]", "sub ecx, edx", "cmp eax, 0xffffff38", "add esi, 0xc"):
            self.assertIn(words, step)

    def test_the_vv4_push_numbers(self):
        handler = " ; ".join(self._dis("vv4", 0x444C8F, 0x444D71))
        # (100 - distance) / 20: the magic 0x66666667 with `sar edx, 3`
        for words in ("add ecx, 0x32", "add eax, 0x5a", "mov ecx, 0x64", "call 0x474330", "lea eax, [ecx + ecx]",
                      "fsub qword ptr [0x48eed8]", "mov eax, 0x66666667 ; imul ecx ; sar edx, 3"):
            self.assertIn(words, handler)
        self.assertEqual(struct.unpack("<d", self.images["vv4"][0x48EED8 - 0x400000:0x48EEE0 - 0x400000])[0],
                         0.009999999776482582)
        # New Believers has the same push (its own copy)
        handler5 = " ; ".join(self._dis("vv5", 0x447DE5, 0x447EC6))
        for words in ("add ecx, 0x32", "add eax, 0x5a", "mov ecx, 0x64", "lea eax, [ecx + ecx]",
                      "mov eax, 0x66666667 ; imul ecx ; sar edx, 3"):
            self.assertIn(words, handler5)

    def test_a_new_home_and_the_lost_children_have_no_overview_clouds(self):
        # A New Home's overview draw (0x42A5A0): its background, the island's objects (0x415ED0) and villagers
        # (0x4388E0) at a quarter -- no cloud.  The Lost Children ships no cloud picture at all.
        body = " ; ".join(self._dis("vv1", 0x42A5A0, 0x42A600))
        self.assertIn("call 0x415ed0", body)
        self.assertIn("call 0x4388e0", body)
        self.assertNotIn(b"cloud", _stock("vv2").lower().replace(b"clouds, dirt", b""))


class _Recorder:
    """The sprite draw replaced: every call's (sprite, x, y, alpha bits) recorded."""

    def __init__(self, proc, va):
        self.calls = []

        def draw(p):
            self.calls.append((p.arg(0), p.arg(1), p.arg(2), p.arg(3)))
            return 0, 0x14
        proc.stub(va, draw)


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "needs the stock executables and capstone/pefile/unicorn")
class TheMapDrawsNoCloud(unittest.TestCase):
    CLOUDS = ((100, 80, 1), (300, 120, 2), (500, 200, 1), (650, 300, 2), (-150, 250, 1))

    def _screen(self, proc, game):
        stride = SCREENS[game][5]
        screen = proc.alloc(0x200)
        proc.write(screen, b"\0" * 0x200)
        proc.put32(screen, SCREENS[game][0])
        for i, (x, y, drift) in enumerate(self.CLOUDS):
            base = screen + 8 + stride * i
            proc.put32(base, x & 0xFFFFFFFF)
            proc.put32(base + 4, y)
            proc.put32(base + 8, drift)
            if stride == 0x18:
                proc.write(base + 0x14, struct.pack("<f", 1.0))
                proc.put32(screen + 0xAC + 4 * i, SCREENS[game][6][i % 4])
        return screen

    def _draw_loop(self, game, data):
        proc = Process(data)
        _vt, _draw, start, end, sprite_draw, _stride, _sprites = SCREENS[game]
        recorder = _Recorder(proc, sprite_draw)
        screen = self._screen(proc, game)
        proc.set_reg("esp", 0x0FF00000 - 0x2000)
        proc.set_reg("esi", screen)
        proc.set_reg("ebx", 0x12345678)
        proc.run(start, end)
        return recorder.calls, proc

    def test_stock_draws_five_clouds_patched_none(self):
        for game in CLOUD_GAMES:
            with self.subTest(game=game):
                stock, _ = self._draw_loop(game, _stock(game))
                self.assertEqual([(x, y) for _s, x, y, _a in stock],
                                 [(x & 0xFFFFFFFF, y) for x, y, _d in self.CLOUDS])
                self.assertTrue(all(s in SCREENS[game][6] for s, *_ in stock))
                patched, proc = self._draw_loop(game, _rendered(game, (f"{game}_disable_overview_clouds",)))
                self.assertEqual(patched, [])
                if game == "vv5":
                    self.assertEqual(proc.reg("ebx") & 0xFF, 0)          # the code after the loop compares bl

    def test_only_the_overview_draw_routine_changes(self):
        for game in CLOUD_GAMES:
            with self.subTest(game=game):
                stock = _image(_stock(game))
                patched = _image(_rendered(game, (f"{game}_disable_overview_clouds",)))
                base_stock = _image(_rendered(game, ()))
                # the PE header's checksum aside (it follows every change), only the code of the draw routine
                changed = [0x400000 + i for i in range(0x1000, min(len(base_stock), len(patched)))
                           if base_stock[i] != patched[i]]
                self.assertTrue(changed)
                self.assertTrue(all(SCREENS[game][1] <= va < DRAW_END[game] for va in changed),
                                [hex(v) for v in changed])
                self.assertEqual(len(stock), len(base_stock))


@unittest.skipUnless(HAVE_STOCK and HAVE_EMULATOR, "needs the stock executables and capstone/pefile/unicorn")
class ThePushIsTheTreeOfLifes(unittest.TestCase):
    """The Secret City with the companion against The Tree of Life's own code, the same clouds, moves and frames."""

    CLOUDS = ((300, 200, 1), (420, 260, 2), (100, 100, 1), (600, 400, 2), (-180, 150, 1))
    MOVES = ((395, 255), (400, 250), (410, 258), (530, 330), (700, 500), (200, 160), (130, 140), (128, 141),
             (420, 300), (0, 0))

    def setUp(self):
        exe3 = _rendered("vv3", ("vv3_push_overview_clouds",))
        self.p3 = Process(exe3, DLL)
        self.p3.export("VvfpStartup", 3, 0)
        self.assertEqual(self.p3.export("VvfpPushCloudsInstalled"), 1)
        self.p4 = Process(_stock("vv4"))
        self.s3 = self.p3.alloc(0x200)
        self.s4 = self.p4.alloc(0x200)
        self.p3.write(self.s3, b"\0" * 0x200)
        self.p4.write(self.s4, b"\0" * 0x200)
        self.p3.put32(self.s3, 0x49EA04)
        self.p4.put32(self.s4, 0x48EEAC)
        for i, (x, y, drift) in enumerate(self.CLOUDS):
            self.p3.write(self.s3 + 8 + 12 * i, struct.pack("<3i", x, y, drift))
            self.p4.write(self.s4 + 8 + 0x18 * i, struct.pack("<5if", x, y, drift, 0, 0, 1.0))
        # The Secret City's stock update and activate: only what matters here (the update's other work -- the
        # clock, the map's markers -- needs a whole game); the cloud step is run as the stock code below.
        self.p3.stub(0x46C070, lambda p: (0, 0))
        self.p3.stub(0x46B930, lambda p: (0, 4))
        # Each game's rand(n) (0x4032D0, 0x4036D0) gives the same pick in both, so a cloud that wraps at the
        # left edge comes back at the same height and drift in both games.
        self.p3.stub(0x4032D0, lambda p: (p.arg(0) // 2, 0))
        self.p4.stub(0x4036D0, lambda p: (p.arg(0) // 2, 0))

    def _vtable_slot(self, slot):
        return self.p3.u32(0x49EA04 + 4 * slot)

    def clouds3(self):
        return [struct.unpack("<3i", self.p3.read(self.s3 + 8 + 12 * i, 12))[:2] for i in range(5)]

    def clouds4(self):
        return [struct.unpack("<5if", self.p4.read(self.s4 + 8 + 0x18 * i, 24)) for i in range(5)]

    def move(self, x, y):
        self.p4.call(VV4_EVENTS, [1, x, y], ecx=self.s4)
        self.p3.call(self._vtable_slot(1), [1, x, y], ecx=self.s3)

    def frame(self):
        self.p4.set_reg("esp", 0x0FF00000 - 0x2000)
        self.p4.set_reg("esi", self.s4)
        self.p4.run(VV4_STEP, VV4_STEP_END)
        self.p3.call(self._vtable_slot(8), [], ecx=self.s3)
        self.p3.set_reg("esp", 0x0FF00000 - 0x2000)
        self.p3.set_reg("esi", self.s3)
        self.p3.run(VV3_STEP, VV3_STEP_END)

    def alphas3(self):
        """The Secret City's own cloud loop, its sprite draw recorded: each cloud's alpha."""
        recorder = _Recorder(self.p3, 0x42EB90)
        self.p3.set_reg("esp", 0x0FF00000 - 0x2000)
        self.p3.set_reg("esi", self.s3)
        self.p3.run(0x46C3BD, 0x46C3E3)
        self.assertEqual([(x, y) for _s, x, y, _a in recorder.calls],
                         [(x & 0xFFFFFFFF, y & 0xFFFFFFFF) for x, y in self.clouds3()])
        return [struct.unpack("<f", struct.pack("<I", a))[0] for _s, _x, _y, a in recorder.calls]

    def assert_same(self):
        four = self.clouds4()
        self.assertEqual(self.clouds3(), [(c[0], c[1]) for c in four])
        self.assertEqual(self.alphas3(), [c[5] for c in four])

    def test_the_slots_and_the_draw_call_are_the_companions(self):
        dll = self.p3.dll_base, self.p3.dll_base + self.p3.dll_size
        for slot, stock in SLOTS:
            self.assertNotEqual(self._vtable_slot(slot), stock)
            self.assertTrue(dll[0] <= self._vtable_slot(slot) < dll[1])
        code = self.p3.read(DRAW_CALL, 5)
        target = DRAW_CALL + 5 + struct.unpack("<i", code[1:])[0]
        self.assertEqual(code[0], 0xE8)
        self.assertTrue(dll[0] <= target & 0xFFFFFFFF < dll[1])

    def test_with_disable_clouds_too_it_installs_and_nothing_is_drawn(self):
        proc = Process(_rendered("vv3", ("vv3_disable_overview_clouds", "vv3_push_overview_clouds")), DLL)
        proc.export("VvfpStartup", 3, 0)
        self.assertEqual(proc.export("VvfpPushCloudsInstalled"), 1)
        recorder = _Recorder(proc, 0x42EB90)
        proc.set_reg("esp", 0x0FF00000 - 0x2000)
        proc.set_reg("esi", proc.alloc(0x100))
        proc.run(0x46C3BD, 0x46C3E3)
        self.assertEqual(recorder.calls, [])

    def test_a_cursor_near_a_cloud_pushes_it_away(self):
        before = self.clouds3()[0]                       # (300, 200): its middle (390, 250)
        self.move(395, 255)                              # just right of and below the middle
        self.frame()
        after = self.clouds3()[0]
        self.assertLess(after[0], before[0] - 1)         # pushed left (with the drift) ...
        self.assertLess(after[1], before[1])             # ... and up: away from the cursor
        self.assertLess(self.alphas3()[0], 1.0)          # and a little faded
        far = self.clouds3()[3]
        self.move(395, 255)
        self.frame()
        self.assertEqual(self.clouds3()[3], (far[0] - 2, far[1]))   # a far cloud only drifts

    def test_frame_by_frame_as_the_tree_of_life(self):
        self.assert_same()
        for x, y in self.MOVES:
            self.move(x, y)
            self.assert_same()
            for _ in range(3):
                self.frame()
                self.assert_same()
        four = self.clouds4()
        self.assertTrue(any(c[3] or c[4] for c in four) or any(c[5] < 1.0 for c in four))

    def test_the_push_lasts_until_the_mouse_moves_again(self):
        self.move(395, 255)
        start = self.clouds3()[0]
        for _ in range(5):
            self.frame()
        self.assert_same()
        moved = self.clouds3()[0]
        self.assertLess(moved[1], start[1] - 5)          # still going up after five frames
        self.move(0, 599)                                # far from every cloud: the push stops
        self.frame()
        self.assert_same()

    def test_showing_the_map_again_restores_the_fade(self):
        for _ in range(20):
            self.move(395, 255)
        self.assertLess(self.alphas3()[0], 0.9)
        self.p3.call(self._vtable_slot(9), [1], ecx=self.s3)
        self.assertEqual(self.alphas3(), [1.0] * 5)

    def test_leaving_the_map_keeps_the_clouds_where_the_stock_update_does(self):
        self.move(395, 255)
        self.p3.write(self.s3 + 0x60, b"\x01")
        self.p3.put32(self.s3 + 0x68, 200)               # this frame ends the leave: the stock update returns early
        before = self.clouds3()
        self.p3.call(self._vtable_slot(8), [], ecx=self.s3)
        self.assertEqual(self.clouds3(), before)
        self.p3.put32(self.s3 + 0x68, 100)               # mid-leave: the clouds still move
        self.p3.call(self._vtable_slot(8), [], ecx=self.s3)
        self.assertNotEqual(self.clouds3(), before)


if __name__ == "__main__":
    unittest.main()
