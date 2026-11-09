"""Memorial Actions Can Also Occur at the Heathen Hovel (New Believers).

The traces and the owner's rules are in scripts/build_vv5_hovel_memorial_actions.py.  These tests run the game's
own code in unicorn (tests/farmers_emulation_vv5.py, on the real map) with the manifest's bytes poked in:

  * "Reflecting" (behaviour 29) and the everyday "Honoring the dead" (behaviour 17 from its chooser 0x46B0F0),
    before the memorial (The Last Heathen not solved) and after it, the hovel chosen and not chosen;
  * permanence: once solved, a Heathen in the village changes nothing;
  * the Day of Honor island event's start of the same behaviour stays as stock;
  * the patch off: the stock walks;
  * every hovel point is walkable, with walkable neighbours, joined to the village.
"""
from __future__ import annotations

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
from vv_fun_patcher_gui import (  # noqa: E402
    UNTICKING_CONFLICT_IDS,
    default_fun_patch_selection,
    owners_default_fun_patch_selection,
    select_all_fun_patch_selection,
)

try:
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

_spec = importlib.util.spec_from_file_location("build_vv5_hovel_memorial_actions",
                                               ROOT / "scripts" / "build_vv5_hovel_memorial_actions.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

MANIFEST = ROOT / "data" / "vv5_hovel_memorial_actions_feature.json"
STOCK = gen.STOCK
REGISTER = 0x463F80                      # the behaviour table's registrations (the static initialiser 0x494030)
TABLE = 0x5475C8                         # behaviour id -> routine (8 bytes each)
DISPATCHER = 0x547D44
REFLECT_BOX = (1530, 1803, 1606, 1805)   # stock: 0x5FA + rand(0x112), 0x646 + rand(0xC8)
HOVEL_BOX = (2176, 2272, 1576, 1600)


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def emulation():
    try:
        import farmers_emulation_vv5 as fe
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("unicorn not installed")
    if not fe.available():
        raise unittest.SkipTest("New Believers' exe and map (research/game-data/vv5) not present")
    return fe


def rand_calls(code: bytes, va: int) -> list[int]:
    """The return addresses of a piece's calls of the game's rand 0x403660."""
    out = []
    for i in range(len(code) - 4):
        if code[i] == 0xE8 and va + i + 5 + struct.unpack_from("<i", code, i + 1)[0] == gen.RAND:
            out.append(va + i + 5)
    return out


def decide_rand() -> int:
    code_a, _, at = gen.caves()
    calls = rand_calls(code_a, gen.CAVE_A[0])
    mine = [c for c in calls if at["decide"] < c < at["reflect"]]
    assert len(mine) == 1
    return mine[0]


def village(fe, *, memorial: bool, patched: bool, hovel: bool | None = None, seed: int = 5):
    """A village (The Last Heathen solved or not), the manifest poked in and the behaviour table registered again
    from the patched bytes, as the game does at start-up; `hovel` forces the wrapper's rand(100) (True: < 25)."""
    projects = (fe.GRANARY, fe.HUNGRY_TOTEM, fe.HYDRO_FARM, fe.LAKE) + ((gen.LAST_HEATHEN,) if memorial else ())
    v = fe.Village(seed=seed, projects=projects)
    if patched:
        for p in manifest()["patches"]:
            at, data = int(p["offset"], 16) + 0x400000, bytes.fromhex(p["after"])
            v.uc.mem_write(at, data)
            v.uc.ctl_remove_cache(at, at + len(data))
        v.call(REGISTER, DISPATCHER)
    if hovel is not None:
        v.by_caller[decide_rand()] = 10 if hovel else 90
    v.villager(age=400, health=90)
    return v


class Recorder:
    """The go-tos (0x4745A0: x, y) and area walks (0x4744C0: area) a behaviour queues."""

    def __init__(self, v):
        self.v, self.targets, self.areas = v, [], []
        uc = v.uc
        self.hooks = [
            uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: self.targets.append(struct.unpack(
                "<ii", bytes(u.mem_read(u.reg_read(UC_X86_REG_ESP) + 4, 8)))), begin=gen.WALK_TO, end=gen.WALK_TO),
            uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: self.areas.append(struct.unpack(
                "<i", bytes(u.mem_read(u.reg_read(UC_X86_REG_ESP) + 4, 4)))[0]), begin=gen.WALK_AREA,
                end=gen.WALK_AREA)]

    def close(self):
        for h in self.hooks:
            self.v.uc.hook_del(h)


def in_box(points, box) -> bool:
    x0, x1, y0, y1 = box
    return bool(points) and all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in points)


def run_to_end(test, v) -> list[tuple[int, int]]:
    """Frames until the villager's queue is empty; the feet at the end of each go-to step."""
    ends, last, frames = [], v.step_type(), 0
    while v.step_type() != 0:
        v.step_frame()
        frames += 1
        if last == 4 and v.step_type() != 4:
            ends.append(v.feet())
        last = v.step_type()
        test.assertLess(frames, 30000, "the action ends")
    return ends


@unittest.skipUnless(HAVE_EMULATOR, "unicorn not installed")
class Emulated(unittest.TestCase):
    def assertArrivesAtTheHovel(self, v, targets):
        """Each go-to ends with the villager at the hovel: its record point is its feet's point 12 left and 35 up,
        and the game ends a walk within a step of the target (measured: up to 20 pixels short)."""
        ends = run_to_end(self, v)
        at_hovel = [(x, y) for x, y in ends
                    if min(max(abs(x + 12 - tx), abs(y + 35 - ty)) for tx, ty in targets) <= 24]
        self.assertGreaterEqual(len(at_hovel), len(set(targets)) - 1, (targets, ends))

    def reflect(self, fe, **kw):
        v = village(fe, **kw)
        rec = Recorder(v)
        v.start(gen.REFLECTING)
        rec.close()
        return v, rec

    def honor_from_chooser(self, fe, **kw):
        """The everyday chooser 0x46B0F0 with its rolls passing (rand(100) > 70, rand(3) = 0, a grave, < 50)."""
        v = village(fe, **kw)
        v.by_caller.update({0x46B0FB: 80, 0x46B10F: 0, 0x46B12B: 0})
        graves = v.uc.hook_add(UC_HOOK_CODE, lambda u, *_: (u.reg_write(UC_X86_REG_EAX, 1), u.reg_write(
            UC_X86_REG_EIP, struct.unpack("<I", bytes(u.mem_read(u.reg_read(UC_X86_REG_ESP), 4)))[0]),
            u.reg_write(UC_X86_REG_ESP, u.reg_read(UC_X86_REG_ESP) + 4)), begin=0x464E90, end=0x464E90)
        rec = Recorder(v)
        started = v.call(0x46B0F0, fe.V0) & 0xFF
        rec.close()
        v.uc.hook_del(graves)
        self.assertEqual((started, v.r32(fe.V0 + fe.BEHAVIOUR)), (1, gen.HONORING))
        return v, rec

    def test_reflecting_before_and_after_the_memorial(self):
        fe = emulation()
        hovel = {gen.hovel_point(rx, ry) for rx in range(gen.HOVEL_X_SPAN) for ry in range(gen.HOVEL_Y_SPAN)}
        for patched, memorial, chosen, at_hovel in ((False, True, None, False), (True, False, True, False),
                                                    (True, True, False, False), (True, True, True, True)):
            with self.subTest(patched=patched, memorial=memorial, chosen=chosen):
                v, rec = self.reflect(fe, memorial=memorial, patched=patched, hovel=chosen)
                self.assertEqual((len(rec.targets), rec.areas), (5, []))
                if at_hovel:
                    self.assertTrue(set(rec.targets) <= hovel, rec.targets)
                    self.assertGreater(len(set(rec.targets)), 1)
                    self.assertArrivesAtTheHovel(v, rec.targets)
                else:
                    self.assertTrue(in_box(rec.targets, REFLECT_BOX), rec.targets)

    def test_everyday_honoring_before_and_after_the_memorial(self):
        fe = emulation()
        for patched, memorial, chosen, at_hovel in ((False, True, None, False), (True, False, True, False),
                                                    (True, True, False, False), (True, True, True, True)):
            with self.subTest(patched=patched, memorial=memorial, chosen=chosen):
                v, rec = self.honor_from_chooser(fe, memorial=memorial, patched=patched, hovel=chosen)
                if at_hovel:
                    self.assertEqual(rec.areas, [0x7A], "the flowers first, as stock")
                    self.assertEqual(len(rec.targets), 3)
                    self.assertTrue(in_box(rec.targets, HOVEL_BOX), rec.targets)
                    self.assertArrivesAtTheHovel(v, rec.targets)
                else:
                    self.assertEqual((rec.areas, rec.targets), ([0x7A, 0x7B, 0x7B, 0x7B], []))

    def test_the_hovel_is_chosen_a_quarter_of_the_time(self):
        """The owner (2026-11-08): 25%, the wrapper's rand(100) < 25."""
        fe = emulation()
        self.assertEqual(gen.CHANCE, 25)
        for roll, at_hovel in ((0, True), (24, True), (25, False), (99, False)):
            with self.subTest(roll=roll):
                v = village(fe, memorial=True, patched=True)
                v.by_caller[decide_rand()] = roll
                rec = Recorder(v)
                v.start(gen.REFLECTING)
                rec.close()
                self.assertTrue(in_box(rec.targets, HOVEL_BOX if at_hovel else REFLECT_BOX), (roll, rec.targets))

    def test_honoring_the_dead_another_way_never_uses_the_hovel(self):
        """The owner (2026-11-08): the Custom Island Event's "Honoring the dead (another way)" (behaviour 46,
        0x4567C0) must not use the hovel: its one go-to stays in its own strip, 1454..1839 by 1705..1742."""
        fe = emulation()
        v = village(fe, memorial=True, patched=True, hovel=True)
        rec = Recorder(v)
        v.start(46)
        rec.close()
        self.assertEqual(len(rec.targets), 1)
        self.assertTrue(in_box(rec.targets, (1454, 1839, 1705, 1742)), rec.targets)
        code = bytes.fromhex(next(p for p in manifest()["patches"] if p["offset"] == "0x6409E")["after"])
        self.assertEqual(len(code), 5)
        offsets = {int(p["offset"], 16) + 0x400000 for p in manifest()["patches"]}
        self.assertFalse(offsets & set(range(0x4567C0, 0x456936)), "nothing in behaviour 46's routine")

    def test_the_memorial_is_for_good_and_needs_no_other_state(self):
        """Once The Last Heathen is solved a Heathen in the village changes nothing, and the game's own check never
        un-solves it; a village where it is not solved (a new one, Start Over too) has no memorial."""
        fe = emulation()
        v = village(fe, memorial=True, patched=True, hovel=True)
        v.w8(fe.V0 + fe.HEATHEN, 1)
        v.call(0x437120)                                    # the game's no-Heathens-left check: nothing to do
        progress = v.r32(fe.PROGRESS + 8 * gen.LAST_HEATHEN)
        self.assertGreaterEqual(progress, v.r32(fe.THRESHOLD + 4 * gen.LAST_HEATHEN))
        rec = Recorder(v)
        v.start(gen.REFLECTING)
        rec.close()
        self.assertTrue(in_box(rec.targets, HOVEL_BOX))
        at = gen.caves()[2]
        self.assertEqual(v.call(at["decide"]) & 0xFF, 1)
        fresh = village(fe, memorial=False, patched=True, hovel=True)
        self.assertEqual(fresh.call(at["decide"]) & 0xFF, 0)

    def test_the_day_of_honor_and_other_starts_stay_stock(self):
        """The Day of Honor island event starts behaviour 17 for everyone (0x414DDA -> 0x470C60); like the Custom
        Island Event's start (0x465580 directly) it never goes through the chooser's wrapper."""
        fe = emulation()
        for how in ("day_of_honor", "direct"):
            with self.subTest(how=how):
                v = village(fe, memorial=True, patched=True, hovel=True)
                rec = Recorder(v)
                if how == "day_of_honor":
                    v.call(0x470C60, fe.VILLAGERS, gen.HONORING, -1, -1, -1, 0, 0)
                else:
                    v.start(gen.HONORING)
                rec.close()
                self.assertEqual(v.r32(fe.V0 + fe.BEHAVIOUR), gen.HONORING)
                self.assertEqual((rec.areas, rec.targets), ([0x7A, 0x7B, 0x7B, 0x7B], []))

    def test_every_hovel_point_is_walkable_and_joined_to_the_village(self):
        fe = emulation()
        cells = struct.unpack("<102400I", (fe.DATA / "lcmap.dat").read_bytes())

        def free(cx, cy):
            cell = cells[cy * 320 + cx]
            return not cell & 1 and (cell >> 4) & 0x7FF not in (0x69, 0x6A)
        start = (2000 // 8, 1580 // 8)                      # the flower patch west of the hovel
        seen, todo = {start}, [start]
        while todo:
            x, y = todo.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < 320 and 0 <= ny < 320 and (nx, ny) not in seen and free(nx, ny):
                    seen.add((nx, ny))
                    todo.append((nx, ny))
        for rx in range(gen.HOVEL_X_SPAN):
            for ry in range(gen.HOVEL_Y_SPAN):
                x, y = gen.hovel_point(rx, ry)
                self.assertIn((x // 8, y // 8), seen, (x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        self.assertTrue(free(x // 8 + dx, y // 8 + dy), (x, y))
        # Right at the hovel: its rocks are the blocked cells just north of the points.
        self.assertFalse(free(2216 // 8, 1544 // 8))
        self.assertEqual((gen.hovel_point(0, 0), gen.hovel_point(96, 24)), ((2176, 1576), (2272, 1600)))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Manifest(unittest.TestCase):
    def test_the_manifest_is_the_generators(self):
        self.assertEqual(manifest(), gen.feature())

    def test_the_stock_sites(self):
        """The bytes the patch replaces are what the trace says they are."""
        data = STOCK.read_bytes()
        call = lambda site, target: b"\xE8" + struct.pack("<i", target - site - 5)   # noqa: E731
        for site in gen.REFLECTING_WALKS:
            self.assertEqual(data[site - 0x400000:site - 0x400000 + 5], call(site, gen.WALK_TO))
        for site in gen.HONORING_GRAVE_WALKS:
            off = site - 0x400000
            self.assertEqual(data[off:off + 5], call(site, gen.WALK_AREA))
            self.assertEqual(data[off - 4:off], b"\x6A\x7B\x8B\xCE")         # push 0x7B (the graves' area); mov ecx,esi
        off = gen.HONORING_CHOOSER_START - 0x400000
        self.assertEqual(data[off:off + 5], call(gen.HONORING_CHOOSER_START, gen.STARTER))
        self.assertEqual(data[off - 7:off - 5], b"\x6A\x11")                 # push 0x11 (behaviour 17)
        off = gen.REFLECTING_REGISTRATION - 0x400000
        self.assertEqual(data[off:off + 7], b"\x68" + struct.pack("<I", gen.REFLECTING_ROUTINE) + b"\x6A\x1D")
        off = gen.DAY_OF_HONOR_START - 0x400000
        self.assertEqual(data[off:off + 2], b"\x6A\x11")
        # The memorial check: project 25 on the project table (0x4370E0, the hovel cover, asks the same).
        self.assertEqual(data[0x370E3:0x370EF], bytes.fromhex("6A19B908E05100") + call(0x4370EA, gen.PROJECT_DONE))

    def test_selection_and_text(self):
        pid = gen.ID
        self.assertFalse(default_fun_patch_selection(pid))
        self.assertTrue(select_all_fun_patch_selection(pid))           # the owner (2026-11-08): Select All ticks it
        self.assertTrue(owners_default_fun_patch_selection(pid))
        self.assertNotIn(pid, UNTICKING_CONFLICT_IDS)
        m = manifest()
        self.assertTrue(m["description"].startswith(
            "Best paired with \"Shrine to the Ancestors\". Villagers will sometimes come here to pay "
            "their respects to those that passed on, and others that guide their fate. **Needs no other patch.**"))
        public = patcher.load_public_fun_patches()
        row = next(p for p in public if p.id == pid)
        # Respecting the Legacy of Isola needs it (it ticks it with the other four respectful patches).
        self.assertEqual(patcher.patch_requirement_text(row, public),
                         "Requires no other patch to be ticked. Needed by Respecting the Legacy of Isola: unticking "
                         "this unticks it.")

    def test_registered_and_documented(self):
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('HOVEL_MEMORIAL_ACTIONS_FEATURE_PATHS = (ROOT / "data" / "vv5_hovel_memorial_actions_feature.json",)',
                      source)
        self.assertIn('"data/vv5_hovel_memorial_actions_feature.json"',
                      (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8"))
        self.assertIn(f"- Patch ID: `{gen.ID}`", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"`{gen.ID}`", (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8"))
        self.assertIn("MEMORIAL ACTIONS CAN ALSO OCCUR AT THE HEATHEN HOVEL (NEW BELIEVERS)",
                      (ROOT / "How to Use.txt").read_text(encoding="utf-8"))
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn(gen.ID, {i for entry in howto["patches"] for i in entry.get("ids", [])})

    def test_no_other_patch_claims_the_bytes(self):
        mine = set()
        for p in manifest()["patches"]:
            off = int(p["offset"], 16)
            mine.update(range(off, off + len(p["after"]) // 2))
        for record in patcher._load_fun_patch_records(include_expanded_time_warp=True):
            raw = record.raw if hasattr(record, "raw") else record
            if raw.get("id") == gen.ID or raw.get("game_id") != "vv5":
                continue
            for p in raw.get("patches", []) or []:
                try:
                    off, n = int(str(p.get("offset")), 16), len(p.get("before", "")) // 2
                except (TypeError, ValueError):
                    continue
                self.assertFalse(mine & set(range(off, off + n)), (raw.get("id"), p.get("offset")))

    def test_the_patcher_renders_it(self):
        build = next(b for b in patcher.load_builds() if b.id == "vv5")
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                image, _ = patcher.render_patched_bytes(STOCK, build, mode, [gen.ID])
                image = bytes(image)
                for p in manifest()["patches"]:
                    off = int(p["offset"], 16)
                    self.assertEqual(image[off:off + len(p["after"]) // 2].hex().upper(), p["after"])


if __name__ == "__main__":
    unittest.main()
