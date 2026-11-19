"""Every Island Event Can Happen (A New Home, The Lost Children, The Secret City, New Believers).

The owner (2026-11-17, final): the only requirements dropped are the technology-level gates -- every event that
needs a technology level can happen at any level, everything researched included -- and every event that raises a
technology raises it by 1 up to the top (3) instead of setting it.  Everything else stays stock.
scripts/build_every_island_event_can_happen_features.py has the stock code read for each site.

These tests pin the manifests to the stock bytes, render each row alone and with every other public patch of its
game in all three patch modes (only the row's bytes change), and run the REAL changed conditions and raises of the
rendered executables in an emulator at every technology level: each dropped gate lets its event qualify at every
level with the row and only at the stock levels without it; each raise is +1 up to 3; the requirements kept in the
same conditions (the villagers they cast, the room / record check) still block.  The Story / Cheat Upgrades
companion's Pick Island Event copy of the A New Home and The Lost Children conditions recognises the row by its
bytes.  The Tree of Life needs nothing.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import capstone
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_fun_patcher as patcher  # noqa: E402

GAMES = (1, 2, 3, 5)
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE = 0x400000
STACK, THIS, WORLD, SCRATCH, RETURN = 0x70000000, 0x20000000, 0x30000000, 0x40000000, 0x0BAD0000
LEVELS = (0, 1, 2, 3)


def fid(game: int) -> str:
    return f"vv{game}_every_island_event_can_happen"


def manifest(game: int) -> dict:
    return json.loads((ROOT / "data" / f"{fid(game)}_feature.json").read_text(encoding="utf-8"))


def stock_bytes(game: int) -> bytes | None:
    import build_every_island_event_can_happen_features as gen
    path = ROOT / "research" / "stock-executables" / gen.STOCK[game]
    return path.read_bytes() if path.is_file() else None


def _builds():
    return {b.id: b for b in patcher.load_builds()}


def input_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _builds()[f"vv{game}"].input_name


_RENDERS: dict = {}


def render(game: int, mode: str, ids: tuple) -> bytes:
    key = (game, mode, ids)
    if key not in _RENDERS:
        data, _ = patcher.render_patched_bytes(input_path(game), _builds()[f"vv{game}"], mode, list(ids))
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


def other_public_ids(game: int) -> tuple:
    return tuple(p.id for p in patcher.load_public_fun_patches()
                 if p.game_id == f"vv{game}" and p.id != fid(game)
                 and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS)


def have_inputs() -> bool:
    return all(input_path(g).is_file() for g in GAMES)


class Manifests(unittest.TestCase):
    def test_generator_reproduces_every_manifest(self) -> None:
        if any(stock_bytes(g) is None for g in GAMES):
            self.skipTest("stock executables not present")
        import build_every_island_event_can_happen_features as gen
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(gen.build(game), manifest(game))

    def test_rows(self) -> None:
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            raw = manifest(game)
            with self.subTest(game=game):
                self.assertEqual(raw["id"], fid(game))
                self.assertEqual(raw["game_id"], f"vv{game}")
                self.assertEqual(raw["name"], "Every Island Event Can Happen")
                self.assertTrue(raw["description"].endswith("**Needs no other patch.**"))
                self.assertEqual(raw["companion_files"], [])
                self.assertIn(fid(game), public)
                for patch in raw["patches"]:
                    self.assertEqual(len(patch["before"]), len(patch["after"]))
        self.assertFalse((ROOT / "data" / "vv4_every_island_event_can_happen_feature.json").exists())

    def test_stock_bytes_and_whole_instructions(self) -> None:
        if any(stock_bytes(g) is None for g in GAMES):
            self.skipTest("stock executables not present")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32) if HAVE_EMULATOR else None
        for game in GAMES:
            data = stock_bytes(game)
            for patch in manifest(game)["patches"]:
                off = int(patch["offset"], 16)
                before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
                with self.subTest(game=game, offset=patch["offset"]):
                    self.assertEqual(data[off:off + len(before)], before)
                    if md is not None:
                        for code in (before, after):
                            self.assertEqual(sum(i.size for i in md.disasm(code, BASE + off)), len(code))

    def test_off_by_default_on_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import default_fun_patch_selection, owners_default_fun_patch_selection
        for game in GAMES:
            with self.subTest(game=game):
                self.assertFalse(default_fun_patch_selection(fid(game)))
                self.assertTrue(owners_default_fun_patch_selection(fid(game)))

    def test_shipped_documented_and_explained(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        guided = {i for entry in howto["patches"] for i in entry["ids"]}
        for game in GAMES:
            with self.subTest(game=game):
                self.assertIn(f'"data/{fid(game)}_feature.json"', release)
                self.assertIn(f"- Patch ID: `{fid(game)}`", readme)
                self.assertIn(fid(game), guided)

    def test_game_mechanics_marks_the_changed_events(self) -> None:
        import importlib
        titles = {1: {"The Trapped Whale", "The Visitor"}, 2: {"The Ancient Gold Coin", "The Spyglass"},
                  3: {"The Bitter Brown Beans (taste or dye)", "The Bitter Brown Beans (brew or fertilizer)",
                      "The Ancient Tablet (laundry or decoration)", "The Ancient Tablet (research or display)",
                      "The Medical Emergency"},
                  5: {"You're Doing It Wrong!", "The Advanced Artifacts", "The Migrating Fruit Bats"}}
        for game in GAMES:
            module = importlib.import_module(f"vv_game_mechanics_events_vv{game}")
            marked = {e.title for e in module.EVENTS if any(f == fid(game) for f, _ in e.patched)}
            with self.subTest(game=game):
                self.assertEqual(marked, titles[game])


@unittest.skipUnless(HAVE_EMULATOR, "capstone / unicorn / pefile not installed")
class Renders(unittest.TestCase):
    def setUp(self) -> None:
        if not have_inputs():
            self.skipTest("stock executables not present (inputs/)")

    def _only_row_bytes(self, game: int, without: bytes, with_row: bytes) -> None:
        field = pefile.PE(data=with_row, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
        ranges = [(int(p["offset"], 16), len(p["after"]) // 2) for p in manifest(game)["patches"]]
        self.assertEqual(len(without), len(with_row))
        diff = [i for i in range(len(without)) if without[i] != with_row[i] and not field <= i < field + 4]
        self.assertTrue(diff)
        self.assertTrue(all(any(o <= i < o + n for o, n in ranges) for i in diff), [hex(i) for i in diff[:6]])
        for p in manifest(game)["patches"]:
            o, n = int(p["offset"], 16), len(p["after"]) // 2
            self.assertEqual(with_row[o:o + n], bytes.fromhex(p["after"]))

    def test_alone_in_every_mode(self) -> None:
        for game in GAMES:
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self._only_row_bytes(game, render(game, mode, ()), render(game, mode, (fid(game),)))

    def test_with_every_other_public_patch_in_every_mode(self) -> None:
        for game in GAMES:
            others = other_public_ids(game)
            self.assertGreater(len(others), 20)
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self._only_row_bytes(game, render(game, mode, others), render(game, mode, others + (fid(game),)))

    def test_story_companion_recognises_the_row(self) -> None:
        """Pick Island Event's own copy of the A New Home / The Lost Children conditions asks the row's bytes."""
        src = {g: (ROOT / "native" / "vvfp_story_upgrades" / f"story_vv{g}.inc").read_text(encoding="utf-8")
               for g in (1, 2)}

        def array(text: str, name: str) -> bytes:
            body = re.search(r"%s\[\d+\] = \{([^}]*)\}" % name, text).group(1)
            return bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", body))

        for game, name, sites in ((1, "VV1_EVERY_EVENT_NOPS", (0x41895B, 0x41896F)),
                                  (2, "VV2_EVERY_EVENT_PASS", (0x41F5C5, 0x41F659))):
            want = array(src[game], name)
            for site in sites:
                self.assertIn("vv%d_every_event(0x%Xu)" % (game, site), src[game])
                for mode in MODES:
                    with self.subTest(game=game, site=hex(site), mode=mode):
                        row = render(game, mode, (fid(game),))
                        self.assertEqual(row[site - BASE:site - BASE + len(want)], want)
                        self.assertNotEqual(render(game, mode, ())[site - BASE:site - BASE + len(want)], want)

    def test_no_safeguards_sites_stay_apart(self) -> None:
        """No Safeguards for Island Events (native/vvfp_no_safeguards, once merged) checks its own sites' stock
        bytes at start: none of them may share a byte with this row, so both install in either order."""
        native = ROOT / "native" / "vvfp_no_safeguards"
        if not native.is_dir():
            self.skipTest("No Safeguards is not in this tree")
        site = re.compile(r"\{\s*0x([0-9A-Fa-f]+)u,\s*(\d+),")
        for game in GAMES:
            text = (native / f"ns_vv{game}.inc").read_text(encoding="utf-8")
            body = text[text.index(f"NS_VV{game}_SITES[] = {{"):]
            theirs = [(int(a, 16), int(n)) for a, n in site.findall(body)]
            for p in manifest(game)["patches"]:
                va, n = BASE + int(p["offset"], 16), len(p["after"]) // 2
                for at, length in theirs:
                    with self.subTest(game=game, mine=hex(va), theirs=hex(at)):
                        self.assertTrue(va + n <= at or at + length <= va)


class Machine:
    """One rendered executable in an emulator.  `hooks`: address -> (return value or callable, bytes the callee
    pops); a callable gets the machine and returns the value."""

    def __init__(self, exe: bytes) -> None:
        image = pefile.PE(data=exe).get_memory_mapped_image()
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        for at, size in ((STACK - 0x40000, 0x50000), (THIS, 0x10000), (WORLD, 0x40000), (SCRATCH, 0x20000),
                         (RETURN, 0x1000)):
            mu.mem_map(at, size)
        self.hooks: dict = {}
        self.calls: dict = {}
        mu.hook_add(UC_HOOK_CODE, self._dispatch)

    def put(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<i", value))

    def get(self, va: int) -> int:
        return struct.unpack("<i", self.mu.mem_read(va, 4))[0]

    def arg(self, n: int) -> int:
        return self.get(self.mu.reg_read(UC_X86_REG_ESP) + 4 * n)

    def _dispatch(self, mu, address, size, _user) -> None:
        hook = self.hooks.get(address)
        if hook is None:
            return
        value, pop = hook
        self.calls[address] = self.calls.get(address, 0) + 1
        if callable(value):
            value = value(self)
        esp = mu.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", mu.mem_read(esp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, back)

    def run(self, entry: int, stack: list, ecx: int = THIS, esi: int = THIS) -> int:
        """Run from `entry` with `stack` (dwords from esp up; RETURN where the code returns) until RETURN."""
        esp = STACK - 0x8000
        self.mu.mem_write(esp, b"".join(struct.pack("<I", w & 0xFFFFFFFF) for w in stack))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.reg_write(UC_X86_REG_ESI, esi)
        self.mu.emu_start(entry, RETURN, count=200000)
        self.esp_after = self.mu.reg_read(UC_X86_REG_ESP)
        self.expected_esp = esp + 4 * stack.index(RETURN) + 4
        return self.mu.reg_read(UC_X86_REG_EAX)


def epilogue(pops: int, pad: int) -> list:
    """`pops` saved registers, a frame of `pad` bytes, then the return address."""
    return [0] * pops + [0] * (pad // 4) + [RETURN]


@unittest.skipUnless(HAVE_EMULATOR, "capstone / unicorn / pefile not installed")
class Emulated(unittest.TestCase):
    """The real changed code of every build, at every technology level (0 to 3)."""

    def setUp(self) -> None:
        if not have_inputs():
            self.skipTest("stock executables not present (inputs/)")

    def builds(self, game: int):
        for mode in MODES:
            yield mode, False, render(game, mode, ())
            yield mode, True, render(game, mode, (fid(game),))

    # -- A New Home ------------------------------------------------------------------------------------------
    def vv1_variant(self, exe: bytes, variant: int, field: int, level: int, child: int = 0) -> tuple:
        m = Machine(exe)
        rolls = [variant]
        m.hooks[0x402F10] = (lambda mm: rolls.pop(0) if rolls else 1, 0)       # rand(16): then variant 1 (class 1)
        m.hooks[0x43BE70] = (child, 0)                                           # the child picker
        m.put(THIS + 0x50A4, WORLD)
        m.put(THIS + 0x50A8, SCRATCH)
        m.put(WORLD + field, level)
        chosen = m.run(0x418920, [RETURN])
        return chosen, m.calls[0x402F10]

    def test_vv1_whale_and_visitor_at_every_level(self) -> None:
        for mode, row, exe in self.builds(1):
            for variant, field in ((0, 0xA2BC), (4, 0xA2D4)):
                for level in LEVELS:
                    with self.subTest(mode=mode, row=row, variant=variant, level=level):
                        accepted = row or level < 3
                        self.assertEqual(self.vv1_variant(exe, variant, field, level),
                                         (variant, 1) if accepted else (1, 2))

    def test_vv1_kept_child_requirement(self) -> None:
        for mode, row, exe in self.builds(1):
            with self.subTest(mode=mode, row=row):
                self.assertEqual(self.vv1_variant(exe, 7, 0xA2BC, 3, child=-1), (1, 2))   # The Troubled Child
                self.assertEqual(self.vv1_variant(exe, 7, 0xA2BC, 3, child=0), (7, 1))

    def test_vv1_raises_are_plus_one_up_to_three(self) -> None:
        for mode, row, exe in self.builds(1):
            for entry, field in ((0x4193E8, 0xA2BC), (0x41980F, 0xA2D4)):
                for level in LEVELS:
                    with self.subTest(mode=mode, row=row, entry=hex(entry), level=level):
                        m = Machine(exe)
                        m.put(THIS + 0x50A4, WORLD)
                        m.put(WORLD + field, level)
                        m.run(entry, epilogue(4, 0x2710))
                        self.assertEqual(m.esp_after, m.expected_esp)
                        self.assertEqual(m.get(WORLD + field), min(level + 1, 3))

    # -- The Lost Children -----------------------------------------------------------------------------------
    def vv2_case(self, exe: bytes, case: int, field: int, level: int, food: int = 0) -> tuple:
        m = Machine(exe)
        rolls = [case]
        m.hooks[0x4031A0] = (lambda mm: rolls.pop(0) if rolls else 21, 0)      # rand(22); 21 is always refused
        m.put(THIS + 0x50AC, WORLD)
        m.put(WORLD + field, level)
        m.put(WORLD + 0x2EAA4, food)
        chosen = m.run(0x41F570, [RETURN])
        return chosen, m.calls[0x4031A0]

    def test_vv2_gold_coin_and_spyglass_at_every_level(self) -> None:
        for mode, row, exe in self.builds(2):
            for case, field in ((0, 0x2EA74), (18, 0x2EA94)):
                for level in LEVELS:
                    with self.subTest(mode=mode, row=row, case=case, level=level):
                        accepted = row or level < 2
                        self.assertEqual(self.vv2_case(exe, case, field, level),
                                         (case, 1) if accepted else (5, 10))

    def test_vv2_kept_food_requirement(self) -> None:
        for mode, row, exe in self.builds(2):
            with self.subTest(mode=mode, row=row):
                self.assertEqual(self.vv2_case(exe, 1, 0x2EA74, 3, food=249), (5, 10))     # The Cursed Idol
                self.assertEqual(self.vv2_case(exe, 1, 0x2EA74, 3, food=250), (1, 1))

    def test_vv2_raises(self) -> None:
        for mode, row, exe in self.builds(2):
            for name, entry, field in (("gold coin", 0x420518, 0x2EA74), ("spyglass", 0x421E74, 0x2EA94)):
                for level in LEVELS:
                    with self.subTest(mode=mode, row=row, event=name, level=level):
                        m = Machine(exe)
                        m.put(THIS + 0x50AC, WORLD)
                        m.put(WORLD + field, level)
                        m.put(WORLD + field + 4, 0x55555555)
                        m.put(WORLD + field - 4, 0x55555555)
                        m.run(entry, epilogue(4, 0x2C2C))
                        self.assertEqual(m.esp_after, m.expected_esp)
                        if row:
                            want = min(level + 1, 3)
                        elif name == "gold coin":
                            want = level + 1 if level < 2 else level
                        else:
                            want = 2
                        self.assertEqual(m.get(WORLD + field), want)
                        self.assertEqual(m.get(WORLD + field + 4), 0x55555555)
                        self.assertEqual(m.get(WORLD + field - 4), 0x55555555)

    # -- The Secret City -------------------------------------------------------------------------------------
    TECH3 = 0x582618

    def vv3_condition(self, exe: bytes, entry: int, levels: dict, found: int = 7, records: int = 10) -> int:
        m = Machine(exe)
        m.hooks[0x45D460] = (found, 0x10)                                        # the villager picker
        # The always-applied safety patch's cave behind 0x41580C (Beans / Tablet): its record count.
        jump = exe[0x41580C - BASE:0x41580C - BASE + 5]
        if jump[0] == 0xE9:
            cave = 0x41580C + 5 + struct.unpack("<i", jump[1:])[0]
            image = pefile.PE(data=exe).get_memory_mapped_image()
            md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            for ins in md.disasm(image[cave - BASE:cave - BASE + 32], cave):
                if ins.mnemonic == "call":
                    m.hooks[int(ins.op_str, 16)] = (records, 0)
                    break
        for index in range(7):
            m.put(self.TECH3 + 4 * index, levels.get(index, 1))
        return m.run(entry, [RETURN]) & 0xFF

    def test_vv3_conditions_at_every_level(self) -> None:
        # (event, condition, the technologies it reads: 0 Science, 1 Medicine, 2 Alchemy, stock rule)
        cases = (
            ("beans taste / tablet laundry", 0x4157E0, (0,), lambda lv: lv[0] < 2),
            ("beans brew", 0x4159B0, (0,), lambda lv: lv[0] >= 2),
            ("tablet research", 0x415C40, (0, 2), lambda lv: lv[0] >= 2 and lv[2] < 3),
            ("medical emergency", 0x4171D0, (1,), lambda lv: lv[1] >= 2),
        )
        import itertools
        for mode, row, exe in self.builds(3):
            for name, entry, techs, stock_rule in cases:
                for values in itertools.product(LEVELS, repeat=len(techs)):
                    levels = {0: 1, 1: 1, 2: 1, **dict(zip(techs, values))}
                    with self.subTest(mode=mode, row=row, event=name, levels=levels):
                        self.assertEqual(self.vv3_condition(exe, entry, levels),
                                         1 if row or stock_rule(levels) else 0)

    def test_vv3_kept_requirements(self) -> None:
        for mode, row, exe in self.builds(3):
            for entry in (0x4157E0, 0x4159B0, 0x415C40, 0x4171D0):
                with self.subTest(mode=mode, row=row, entry=hex(entry)):
                    self.assertEqual(self.vv3_condition(exe, entry, {0: 0, 1: 3, 2: 0}, found=0), 0)
            with self.subTest(mode=mode, row=row, check="records"):
                # Beans / Tablet: the safety patch's record check still refuses when no record is left.
                self.assertEqual(self.vv3_condition(exe, 0x4157E0, {0: 0}, records=0x100), 0)
                self.assertEqual(self.vv3_condition(exe, 0x4157E0, {0: 0}, records=10), 1)

    def test_vv3_tablet_raise_is_plus_one_up_to_three(self) -> None:
        for mode, row, exe in self.builds(3):
            for level in LEVELS:
                with self.subTest(mode=mode, row=row, level=level):
                    m = Machine(exe)
                    m.put(0x582614, 0)                                           # no listeners
                    m.put(self.TECH3 + 8, level)
                    m.run(0x426FD0, [RETURN, 2], ecx=self.TECH3)
                    self.assertEqual(m.esp_after, m.expected_esp + 4)
                    self.assertEqual(m.get(self.TECH3 + 8), min(level + 1, 3))
        # "Focus research on tablet" calls it for Alchemy: push 2; mov ecx, 0x582618; call 0x426FD0.
        exe = render(3, "stock", (fid(3),))
        self.assertEqual(exe[0x415D29 - BASE:0x415D35 - BASE], bytes.fromhex("6A02B918265800E89B120100"))

    # -- New Believers ---------------------------------------------------------------------------------------
    TECH5 = 0x51D5CC

    def vv5_machine(self, exe: bytes, science: int, food_mastery: int, found: int = 7) -> "Machine":
        m = Machine(exe)
        m.hooks[0x471870] = (found, 0x38)                                        # the villager picker
        m.hooks[0x403660] = (0, 0)                                               # rand
        m.hooks[0x413450] = (0, 8)                                               # the level-up notice
        m.hooks[0x425950] = (SCRATCH, 0)
        m.put(0x51D5C4, 0)                                                       # no listeners
        for index in range(6):
            m.put(self.TECH5 + 4 * index, 1)
        m.put(self.TECH5, science)
        m.put(self.TECH5 + 16, food_mastery)
        return m

    def test_vv5_conditions_at_every_level(self) -> None:
        cases = (
            ("you're doing it wrong", 0x415F60, lambda s, f: s < 2),
            ("advanced artifacts", 0x416430, lambda s, f: s == 2),
            ("fruit bats", 0x4166F0, lambda s, f: f < 2),
        )
        for mode, row, exe in self.builds(5):
            for name, entry, stock_rule in cases:
                for science in LEVELS:
                    for food in LEVELS:
                        with self.subTest(mode=mode, row=row, event=name, science=science, food_mastery=food):
                            m = self.vv5_machine(exe, science, food)
                            self.assertEqual(m.run(entry, [RETURN]) & 0xFF,
                                             1 if row or stock_rule(science, food) else 0)

    def test_vv5_kept_villager_requirements(self) -> None:
        for mode, row, exe in self.builds(5):
            for entry in (0x415F60, 0x416430, 0x4166F0):
                with self.subTest(mode=mode, row=row, entry=hex(entry)):
                    m = self.vv5_machine(exe, 1, 1, found=0)
                    self.assertEqual(m.run(entry, [RETURN]) & 0xFF, 0)

    def test_vv5_raises_are_plus_one_up_to_three(self) -> None:
        raises = (("teach them", 0x416081, 0), ("independent report", 0x416518, 0), ("observe them", 0x416778, 4))
        for mode, row, exe in self.builds(5):
            for name, entry, index in raises:
                for level in LEVELS:
                    with self.subTest(mode=mode, row=row, result=name, level=level):
                        m = self.vv5_machine(exe, 1, 1)
                        m.put(self.TECH5 + 4 * index, level)
                        m.run(entry, [0, RETURN, 0])
                        self.assertEqual(m.esp_after, m.expected_esp + 4)
                        if name == "teach them" and not row:
                            want = level + 1 if level < 2 else level         # stock: only below 2
                        else:
                            want = min(level + 1, 3)
                        self.assertEqual(m.get(self.TECH5 + 4 * index), want)


@unittest.skipUnless(HAVE_EMULATOR, "capstone / unicorn / pefile not installed")
class TreeOfLifeNeedsNothing(unittest.TestCase):
    def test_no_condition_reads_a_level_and_every_raise_stops_at_three(self) -> None:
        path = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
        if not path.is_file():
            self.skipTest("stock executables not present")
        data = path.read_bytes()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        # The event code (conditions and results, 0x414900..0x418000): the level getter 0x41E1C0 is called once,
        # in a result, right before a raise that it guards with "below 3"; every raise is 0x41E1D0.
        getters, raises = [], []
        for ins in md.disasm(data[0x14900:0x18000], 0x414900):
            if ins.mnemonic == "call" and ins.op_str == "0x41e1c0":
                getters.append(ins.address)
            if ins.mnemonic == "call" and ins.op_str == "0x41e1d0":
                raises.append(ins.address)
        self.assertEqual(getters, [0x415303])
        self.assertEqual(raises, [0x415314, 0x41591D, 0x416DB2, 0x416DBF])
        # 0x41E1D0: cmp eax, 3 / jge out before the add.
        self.assertEqual(data[0x1E1DC:0x1E1E4], bytes.fromhex("83F8037D3483C001"))


if __name__ == "__main__":
    unittest.main()
