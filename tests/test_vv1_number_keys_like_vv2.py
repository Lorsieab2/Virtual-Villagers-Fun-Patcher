"""A New Home's number keys behave exactly like The Lost Children's.

Everything here is EMULATED machine code: A New Home as the patcher renders
it with Numeric Keys selected, its companion's TEST build loaded and armed the
way VVFP Startup.dll arms it (VvfpStartup), and The Lost Children's STOCK
executable beside it.  Each scenario drives both games through their own
code -- the village screen's text-character handler, the village update from
the glide's spot onward, the map drag, the mouse-up branch, the screen
buttons -- with the same screen margins and the same start, and requires the
two views to follow the same path, update for update.

The Lost Children's code (stock):
  0x429E70  text-character handler: '1'..'9' set the target at +0x230/+0x234
  0x42F814  the glide in the village update, through its clamp, to 0x42F9ED
  0x431758  the map drag: moves the view, leaves the target alone
  0x4308F2  mouse-up: clears the target
  0x42A78F / 0x42AA35 / 0x42AABA / 0x42AB9C  screen buttons 3/5/6/7 clear it
A New Home's (patched): 0x41FDF0 (detoured at 0x41FE04), the update from the
Origins hook at 0x423F89 to 0x42402D, the drag at 0x4259DE, mouse-up at
0x424F12, buttons 0x4208CC / 0x420932 / 0x420998, constructor 0x422555.
"""
from __future__ import annotations

import gc
import glob
import json
import struct
import unittest
from pathlib import Path

import pefile
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI

import test_builders_decision_roll as rig
from test_builders_decision_roll import HALT, OBJ, STATE, STOCK, STOCK_ABSENT, STOCK_PRESENT, Leaf, Machine

ROOT = Path(__file__).resolve().parents[1]
KEYS_TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP VV1 Number Keys.test.dll"
rig.TEST_DLLS.setdefault("number_keys", KEYS_TEST_DLL)
rig.MODULE_FILE.setdefault("number_keys", "VVFP VV1 Number Keys.dll")
rig.BASES.setdefault("number_keys", 0x13000000)
KEYS_PRESENT = KEYS_TEST_DLL.is_file()
KEYS_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"

ROWS = ("vv1_enable_origins_exclusive_features", "vv1_number_keys")
SCREEN = OBJ                      # the village screen object
VV1_STATE_GLOBAL = 0x48AEDC       # what 0x41D500 returns
NUMBER_KEYS_UPDATE_DLL_FN = 0x491210   # the Origins hook's cached export (.vv1md + 0x210)

# per game: screen field offsets
FIELDS = {
    "vv1": dict(edge=0x2D8, margins=0x298, held=0x294, drag=0x290, last=0x3C),
    "vv2": dict(edge=0x228, margins=0x1E8, held=0x1E4, drag=0x1E0, last=0x44, target=0x230),
}
CARRY = {"vv1": 0x439410, "vv2": 0x449220}

# The six A New Home sites: (va, stock bytes, resume).
SITES = [
    (0x41FE04, bytes.fromhex("8B44242483C0E0"), 0x41FE0B),
    (0x424F12, bytes.fromhex("8B8EF0020000"), 0x424F18),
    (0x4208CC, bytes.fromhex("899ED8020000899EDC020000"), 0x4208D8),
    (0x420932, bytes.fromhex("899ED8020000899EDC020000"), 0x42093E),
    (0x420998, bytes.fromhex("899EDC020000899ED8020000"), 0x4209A4),
    (0x422555, bytes.fromhex("899ED8020000899EDC020000"), 0x422561),
]
VV2_BUTTON_CLEARS = [(0x42A78F, 0x42A7A7), (0x42AA35, 0x42AA4D), (0x42AABA, 0x42AAD2), (0x42AB9C, 0x42ABB4)]

# The VV1 clamp extrema -205..885 / -5..1205 as screen margins (left, top,
# right, bottom): x in [-left, 1680 - right], y in [-top, top - bottom + 1680].
MARGINS = (205, 5, 795, 480)


class Game:
    """One emulated game with its village screen and state."""

    def __init__(self, game: str, *, tamper: int | None = None, margins=MARGINS, protect_fails: int | None = None):
        self.game = game
        if game == "vv1":
            exe = rig.rendered("vv1", ROWS)
            if tamper is not None:
                exe = bytearray(exe)
                off = pefile.PE(data=bytes(exe)).get_offset_from_rva(tamper - 0x400000)
                exe[off] ^= 0xFF
                exe = bytes(exe)
            self.m = Machine("vv1", exe, modules=("number_keys",))
            self._model_protection(protect_fails)
            self.m.w32(VV1_STATE_GLOBAL, STATE)
            self.m.w32(NUMBER_KEYS_UPDATE_DLL_FN, self.m.exports["number_keys"]["Vv1NumberKeysUpdate"])
            self.m.call_export("number_keys", "VvfpStartup", 1, 0)
        else:
            self.m = Machine("vv2", STOCK["vv2"].read_bytes(), modules=())
        self.f = FIELDS[game]
        self.m.w32(SCREEN + 0x10, STATE)
        self.m.w32(SCREEN + self.f["held"], 0xFFFFFFFF)
        self.carried: list = []
        self.m.leaves[CARRY[game]] = Leaf(3, lambda m, a, c, r: self.carried.append(a) or 0, name="carry refresh")
        for k, v in enumerate(margins):
            self.m.w32(SCREEN + self.f["margins"] + 4 * k, v)
        self.at(123, 456)

    # -- page protection --------------------------------------------------------
    def _model_protection(self, fails: int | None) -> None:
        """VirtualProtect with real per-page state (code pages start
        PAGE_EXECUTE_READ, 0x20); a call for the site at `fails` fails
        while self.protect_fails is set."""
        self.protect = {}
        self.protect_calls: list[tuple[int, int]] = []
        self.protect_fails = fails
        base_import = self.m._import

        def _import(name: str) -> None:
            if name != "VirtualProtect":
                base_import(name)
                return
            mu = self.m.mu
            sp = mu.reg_read(rig.UC_X86_REG_ESP)
            addr, size, new, old_out = struct.unpack("<4I", mu.mem_read(sp + 4, 16))
            self.protect_calls.append((addr, new))
            if addr == self.protect_fails:
                mu.reg_write(UC_X86_REG_EAX, 0)
                return
            pages = range(addr & ~0xFFF, addr + size, 0x1000)
            mu.mem_write(old_out, struct.pack("<I", self.protect.get(addr & ~0xFFF, 0x20)))
            for page in pages:
                self.protect[page] = new
            mu.reg_write(UC_X86_REG_EAX, 1)

        self.m._import = _import

    def loosened(self) -> list[int]:
        return sorted(page for page, value in self.protect.items() if value != 0x20)

    # -- the view ------------------------------------------------------------
    def at(self, x: int, y: int) -> None:
        self.m.w32(STATE + 8, x)
        self.m.w32(STATE + 0xC, y)

    def view(self) -> tuple[int, int]:
        return (struct.unpack("<i", self.m.mu.mem_read(STATE + 8, 4))[0],
                struct.unpack("<i", self.m.mu.mem_read(STATE + 0xC, 4))[0])

    def edge(self) -> tuple[int, int]:
        return tuple(struct.unpack("<ii", self.m.mu.mem_read(SCREEN + self.f["edge"], 8)))

    def set_edge(self, vx: int, vy: int) -> None:
        self.m.w32(SCREEN + self.f["edge"], vx)
        self.m.w32(SCREEN + self.f["edge"] + 4, vy)

    def target(self) -> tuple[int, int]:
        if self.game == "vv2":
            return tuple(struct.unpack("<ii", self.m.mu.mem_read(SCREEN + self.f["target"], 8)))
        out = 0x0F000000 - 0x20000
        self.m.call_export("number_keys", "Vv1NumberKeysProbeTarget", out, out + 4)
        return tuple(struct.unpack("<ii", self.m.mu.mem_read(out, 8)))

    # -- the game's own code -------------------------------------------------
    def key(self, ch: str) -> int:
        start = 0x41FDF0 if self.game == "vv1" else 0x429E70
        self.m.run(start, HALT, {UC_X86_REG_ECX: SCREEN}, stack=(HALT, 5, 0, ord(ch)))
        return self.m.mu.reg_read(UC_X86_REG_EAX) & 0xFF

    def update(self) -> tuple[int, int]:
        if self.game == "vv1":
            self.m.run(0x423F89, 0x42402D, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBX: 0, UC_X86_REG_EDX: STATE})
        else:
            self.m.run(0x42F814, 0x42F9ED, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBX: 0, UC_X86_REG_ECX: STATE})
        return self.view()

    def press(self, x: int, y: int) -> None:
        """What the mouse-down on empty ground leaves behind: the drag flag
        and the pointer (VV1 0x425441, VV2 0x4310EB)."""
        self.m.w8(SCREEN + self.f["drag"], 1)
        self.m.w32(SCREEN + self.f["last"], x)
        self.m.w32(SCREEN + self.f["last"] + 4, y)

    def drag(self, x: int, y: int) -> None:
        stack = (0,) * 9 + (y,)                    # [esp+0x24] = pointer y
        if self.game == "vv1":
            self.m.run(0x4259DE, 0x425A67, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBP: x}, stack=stack)
        else:
            self.m.run(0x431758, 0x4317DD, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBX: x}, stack=stack)

    def release(self) -> None:
        if self.game == "vv1":
            self.m.run(0x424F12, 0x424F2C, {UC_X86_REG_ESI: SCREEN})
        else:
            self.m.run(0x4308F2, 0x430918, {UC_X86_REG_ESI: SCREEN})
        self.m.w8(SCREEN + self.f["drag"], 0)


def both(**kw) -> tuple[Game, Game]:
    return Game("vv1", **kw), Game("vv2", **kw)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(KEYS_PRESENT, KEYS_ABSENT)
class SameAsTheLostChildren(unittest.TestCase):
    def tearDown(self) -> None:
        # Each Game holds a unicorn engine whose code hook refers back to its
        # Machine; collect the cycles so engines do not pile up.
        gc.collect()

    def assertSamePath(self, a: Game, b: Game, steps) -> list:
        path = []
        for step in steps:
            pa, pb = step(a), step(b)
            self.assertEqual(pa, pb, f"step {len(path)}: A New Home {pa} vs The Lost Children {pb}")
            path.append(pa)
        return path

    def test_the_six_sites_hold_the_stock_bytes_the_companion_checks(self):
        stock = pefile.PE(str(STOCK["vv1"]))
        rendered = pefile.PE(data=rig.rendered("vv1", ROWS))
        g = Game("vv1")
        buf = 0x0F000000 - 0x20000
        for index, (va, want, resume) in enumerate(SITES):
            n = g.m.call_export("number_keys", "Vv1NumberKeysProbeSite", index, buf, buf + 4, buf + 0x20)
            self.assertEqual(n, len(want))
            self.assertEqual(g.m.u32(buf), va)
            self.assertEqual(bytes(g.m.mu.mem_read(buf + 4, n)), want)
            self.assertEqual(stock.get_data(va - 0x400000, n), want, hex(va))
            self.assertEqual(rendered.get_data(va - 0x400000, n), want, f"{va:#x}: the patcher leaves it stock")
            live = bytes(g.m.mu.mem_read(va, n))
            self.assertEqual(live[0], 0xE9, f"{va:#x} detoured once armed")
            self.assertEqual(live[5:], b"\x90" * (n - 5))
            self.assertEqual(live, bytes(g.m.mu.mem_read(buf + 0x20, n)))

    def test_no_patch_writes_any_of_the_six_sites(self):
        for path in glob.glob(str(ROOT / "data" / "*.json")):
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            except ValueError:
                continue
            stack = [data]
            while stack:
                node = stack.pop()
                if isinstance(node, list):
                    stack.extend(node)
                elif isinstance(node, dict):
                    stack.extend(node.values())
                    if node.get("game_id") not in (None, "vv1"):
                        continue
                    if "offset" in node and "after" in node and isinstance(node["offset"], str):
                        off, n = int(node["offset"], 16), len(node["after"]) // 2
                        for va, want, _ in SITES:
                            site = va - 0x400000           # .text: file offset == RVA in A New Home
                            self.assertFalse(off < site + len(want) and site < off + n,
                                             f"{Path(path).name} writes {off:#x}, over the {va:#x} site")

    def test_a_key_glides_the_same_path(self):
        a, b = both()
        self.assertEqual((a.key("3"), b.key("3")), (0, 0), "both handlers return 0 for a digit")
        self.assertEqual(a.target(), (850, 1200))
        self.assertEqual(a.target(), b.target())
        self.assertEqual(a.view(), (123, 456), "the key itself moves nothing")
        path = self.assertSamePath(a, b, [Game.update] * 80)
        self.assertEqual(path[0], (123 + (850 - 123) // 10, 456 + (1200 - 456) // 10))
        self.assertEqual(path[-1], (841, 1191), "stops short, no snap: the remaining delta / 10 is 0")
        self.assertEqual(a.target(), (0, 0))
        self.assertEqual(b.target(), (0, 0))

    def test_every_key_targets_the_same_spot(self):
        for ch in "123456789":
            a, b = both()
            a.key(ch), b.key(ch)
            self.assertEqual(a.target(), b.target(), ch)
            self.assertSamePath(a, b, [Game.update] * 60)

    def test_other_characters_set_nothing(self):
        a = Game("vv1")
        for ch in "0q ":
            if ch == " ":
                continue                        # space pauses: a real handler path, not a target
            self.assertEqual(a.key(ch), 0)
            self.assertEqual(a.target(), (0, 0), ch)
        a.update()
        self.assertEqual(a.view(), (123, 456))

    def test_a_drag_wins_the_same_way(self):
        """The glide pulls while the button is held; releasing ends it."""
        a, b = both()
        a.key("3"), b.key("3")
        steps = [Game.update] * 3
        steps += [lambda g: (g.press(400, 300), g.view())[1]]
        steps += [lambda g, p=p: (g.drag(*p), g.view())[1] for p in ((450, 330), (520, 380), (600, 420))]
        steps += [Game.update] * 2                    # button still held: the glide still pulls
        steps += [lambda g: (g.drag(650, 450), g.view())[1]]
        steps += [lambda g: (g.release(), g.view())[1]]
        steps += [Game.update] * 10                   # released: the view stays where the drag left it
        path = self.assertSamePath(a, b, steps)
        self.assertEqual(a.target(), (0, 0))
        self.assertEqual(b.target(), (0, 0))
        released = path[-11]
        self.assertTrue(all(p == released for p in path[-10:]), "nothing moves after the release")
        self.assertNotEqual(released, (841, 1191), "the drag won: the glide never finished")
        self.assertLess(path[4][0], path[2][0], "the drag pulled the view back against the glide")
        self.assertGreater(path[8][0], path[7][0], "while held, the glide kept pulling")

    def test_a_click_ends_a_glide_the_same_way(self):
        a, b = both()
        a.key("9"), b.key("9")
        self.assertSamePath(a, b, [Game.update] * 4 + [lambda g: (g.release(), g.view())[1]] + [Game.update] * 5)
        self.assertEqual(a.target(), (0, 0))

    def test_a_second_key_retargets_from_where_the_view_is(self):
        a, b = both()
        a.key("1"), b.key("1")
        steps = [Game.update] * 4 + [lambda g: (g.key("9"), g.view())[1]] + [Game.update] * 70
        path = self.assertSamePath(a, b, steps)
        self.assertEqual(a.target(), (0, 0))
        self.assertTrue(abs(path[-1][0] - 850) < 10 and abs(path[-1][1] - 0) < 10, path[-1])

    def test_the_map_edge_clamp_and_its_quirk_are_the_same(self):
        """A margin that puts 850 beyond the clamp: the clamped axis's target
        is zeroed (0x42F8C5), so that axis then heads for 0, as in the stock
        Lost Children."""
        tight = (205, 5, 1680 - 800, 480)              # x at most 800
        a, b = both(margins=tight)
        a.key("3"), b.key("3")
        a.at(790, 456), b.at(790, 456)
        path = self.assertSamePath(a, b, [Game.update] * 80)
        self.assertEqual(path[0][0], 796)
        self.assertEqual(path[1][0], 800, "clamped at the edge (796 + 5 = 801 > 800)")
        self.assertLess(path[2][0], 800, "then the zeroed target pulls x toward 0")
        self.assertLess(path[-1][0], 100)
        y_edge = (205, 5, 795, 1680 + 5 - 1000)       # y at most 1000
        a, b = both(margins=y_edge)
        a.key("2"), b.key("2")
        self.assertSamePath(a, b, [Game.update] * 80)
        self.assertEqual(a.target(), b.target())

    def test_carrying_a_villager_the_same_way(self):
        a, b = both()
        for g in (a, b):
            g.m.w32(SCREEN + g.f["held"], 4)          # a villager in hand
            g.key("6")

        def tick(g):
            g.set_edge(2, -2)                         # what the carry / follow code sets each frame
            g.update()
            return g.view() + g.edge()

        path = self.assertSamePath(a, b, [tick] * 6)
        self.assertTrue(all(p[2:] == (0, 0) for p in path), "the glide zeroes the edge velocities")
        self.assertEqual(len(a.carried), 6, "the carried villager is refreshed every glide update")
        self.assertEqual(len(a.carried), len(b.carried))
        self.assertSamePath(a, b, [lambda g: (g.release(), g.view())[1], Game.update])
        self.assertEqual(a.target(), (0, 0))

    def test_without_a_glide_the_edge_scroll_is_native(self):
        a, b = both()
        for g in (a, b):
            g.set_edge(2, -2)
        self.assertSamePath(a, b, [Game.update] * 3)
        self.assertEqual(a.view(), (129, 450))

    def test_the_screen_buttons_end_a_glide_the_same_way(self):
        for start, stop in VV2_BUTTON_CLEARS:
            b = Game("vv2")
            b.key("5")
            b.m.run(start, stop, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBX: 0})
            self.assertEqual(b.target(), (0, 0), hex(start))
        for va, _, resume in SITES[2:]:
            a = Game("vv1")
            a.key("5")
            a.set_edge(3, 3)
            a.m.run(va, resume, {UC_X86_REG_ESI: SCREEN, UC_X86_REG_EBX: 0})
            self.assertEqual(a.target(), (0, 0), hex(va))
            self.assertEqual(a.edge(), (0, 0), f"{va:#x}: the stock clears still run")
            a.update()
            self.assertEqual(a.view(), (123, 456))

    def test_the_mouse_up_branch_still_runs_its_own_code(self):
        a = Game("vv1")
        a.set_edge(3, 3)
        a.m.w8(SCREEN + 0x281, 1)
        a.release()
        self.assertEqual(a.edge(), (0, 0))
        self.assertEqual(a.m.mu.mem_read(SCREEN + 0x281, 1), b"\0")

    def test_one_changed_site_installs_nothing(self):
        a = Game("vv1", tamper=0x424F12)
        self.assertEqual(a.m.mu.mem_read(0x41FE04, 1)[0], 0x8B, "the key site stays stock")
        a.key("3")
        self.assertEqual(a.target(), (0, 0))
        a.update()
        self.assertEqual(a.view(), (123, 456))

    def test_one_site_that_cannot_be_made_writable_installs_nothing_and_retries(self):
        """VirtualProtect fails for the 4th site (0x420932): no site is
        written, every protection already loosened is put back, the install
        reports 0 (not installed) -- and a later tick installs all six."""
        a = Game("vv1", protect_fails=SITES[3][0])
        for va, want, _ in SITES:
            self.assertEqual(bytes(a.m.mu.mem_read(va, len(want))), want, f"{va:#x} untouched")
        self.assertEqual(a.loosened(), [], "every protection changed was restored")
        self.assertEqual([c[0] for c in a.protect_calls[:4]], [s[0] for s in SITES[:4]],
                         "all four acquisitions were tried before anything was written")
        self.assertEqual(a.m.call_export("number_keys", "Vv1NumberKeysInstall"), 0)
        a.key("3")
        self.assertEqual(a.target(), (0, 0), "no key detour")
        a.update()
        self.assertEqual(a.view(), (123, 456))

        a.protect_fails = None                    # a later tick, when it works
        self.assertEqual(a.m.call_export("number_keys", "Vv1NumberKeysTick"), 1)
        for va, want, _ in SITES:
            self.assertEqual(a.m.mu.mem_read(va, 1)[0], 0xE9, f"{va:#x} detoured on the retry")
        self.assertEqual(a.loosened(), [], "the original protections are back after writing")
        a.key("3")
        self.assertEqual(a.target(), (850, 1200))

    def test_a_normal_install_restores_every_protection(self):
        a = Game("vv1", protect_fails=0)
        self.assertEqual(a.m.mu.mem_read(SITES[1][0], 1)[0], 0xE9)
        self.assertEqual(a.loosened(), [])

    def test_no_village_nothing_moves(self):
        a = Game("vv1")
        a.key("3")
        a.m.w32(VV1_STATE_GLOBAL, 0)
        a.update()
        self.assertEqual(a.view(), (123, 456))


if __name__ == "__main__":
    unittest.main()
