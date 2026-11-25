"""Pick Island Event: the override toggle (the owner, 2026-11-25, all five games).

"would be nice to have an override toggle. all 5 games" -- "just put a warning message for the override
toggle/button" -- "it safely uses the available people in the village/game etc" -- "none of the usual requirements
should apply, unless it's literally technically impossible".

native/vvfp_story_upgrades/story_override.inc, its table scripts/story_island_outcomes.py OVERRIDE.  Everything here
runs the shipped bytes in the emulator (tests/story_emulator.py), the test build of "VVFP Story Upgrades.dll"
installed beside each game's executable as the patcher renders it:

* the compiled table is the data;
* The Secret City, The Tree of Life, New Believers: every listed event, its own condition FALSE (it picks nobody),
  is delivered by the game's own selector only when bought with the override; the villager(s) its popup and apply
  read are cast from the living villagers of the kind its condition picks (never a Heathen outside a Heathen's part,
  never a puzzle's or a sick Heathen, never twice the same villager); then the event's OWN popup methods and its
  OWN apply (every choice) run for real on that object -- complete, no invalid access;
* what stays impossible: no villager of a kind the event needs, no free villager record, a chief the code looks up;
* A New Home / The Lost Children: the event's own condition is passed for its roll only when bought with the
  override;
* the picker: off when it opens, the rows it opens, and back.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import story_island_events  # noqa: E402
import story_island_outcomes as outcomes  # noqa: E402
from test_story_outcomes import (  # noqa: E402
    GAMES, PICK_SITES, SCRATCH, STACK, TABLES, Game, _position, _script, emulated, have_stock, stock_target)

KIND_IDS = outcomes.OV_KINDS
ADULT = 0x118
BUILDERS = {"vv3": 0x418630, "vv4": 0x416FF0, "vv5": 0x417790}
NEW = {"vv3": 0x46EC93, "vv4": 0x470C5C, "vv5": 0x47BBDC}    # each game's operator new (its getters call it)
HEATHEN_FACTION, HEATHEN_ROLE, HEATHEN_SICK = 0x1CEC, 0x1CFC, 0x1C48


def builder_slots(g: Game) -> dict[int, tuple[int, int]]:
    """slot -> (object size, vtable), read from the game's own event-table builder (push size; call new;
    mov [eax], vtable; mov [table + 4 * slot], eax)."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    table, start = TABLES[g.game], BUILDERS[g.game]
    code = g.proc.read(start, 0x2000)
    out, size, vt, pushed = {}, None, None, None
    for ins in md.disasm(code, start):
        if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
            pushed = int(ins.op_str, 16)
        elif ins.mnemonic == "call":
            size = pushed
        elif ins.mnemonic == "mov" and ins.op_str.startswith("dword ptr [eax], 0x"):
            vt = int(ins.op_str.split(", ")[1], 16)
        elif ins.mnemonic == "mov" and ins.op_str.startswith("dword ptr [0x") and ins.op_str.endswith("], eax"):
            at = int(ins.op_str[len("dword ptr ["):].split("]")[0], 16)
            if table <= at < table + 4 * 64:
                out[(at - table) // 4] = (size, vt)
        elif ins.mnemonic == "ret":
            break
    return out


# The village every cast runs in, by kind: (name, sex, years, heathen, role, sick).
PEOPLE = {
    "man": ("Mano", "m", 30, 0, 0, 0), "woman": ("Wana", "f", 28, 0, 0, 0),
    "boy": ("Boyo", "m", 8, 0, 0, 0), "girl": ("Gila", "f", 7, 0, 0, 0),
    "hman": ("Hemo", "m", 30, 1, 0, 0), "hkid": ("Heki", "m", 8, 1, 0, 0),
    "puzzle": ("Pozo", "f", 30, 1, 13, 0), "sickh": ("Siko", "m", 9, 1, 0, 1),
}


def village(g: Game, who: tuple[str, ...]) -> dict[int, str]:
    """Only `who` live in the village: record -> key."""
    v = g.village
    for i in range(v.L["count"] if g.game != "vv1" else 0):
        g.proc.write(v.record(i) + v.L["active"], b"\0")
    for i in range(6):
        g.proc.write(v.record(i) + v.L["active"], b"\0")
    out = {}
    for i, key in enumerate(who):
        name, sex, years, heathen, role, sick = PEOPLE[key]
        if heathen and g.game != "vv5":
            continue
        r = v.put(i, sex=sex, years=years, name=name, faction=heathen)
        if g.game in ("vv4", "vv5"):
            g.proc.put32(r + 0x1B80, r)    # the record's own pointer to itself, as the game keeps it
        if g.game == "vv5":
            g.proc.put32(r + HEATHEN_ROLE, role)
            g.proc.write(r + HEATHEN_SICK, bytes([sick]))
        out[r] = key
    return out


def kind_ok(key: str, kind: str) -> bool:
    _, sex, years, heathen, role, sick = PEOPLE[key]
    adult = years * 20 >= ADULT
    if kind.startswith("heathen"):
        return bool(heathen) and not (12 <= role <= 17) and not sick
    if heathen:
        return False
    return {"any": True, "adult": adult, "child": not adult, "woman": adult and sex == "f",
            "man": adult and sex == "m", "female": sex == "f", "male": sex == "m"}[kind]


FALLBACK = {"child": ("child", "any"), "heathen_child": ("heathen_child", "heathen"),
            "heathen_man": ("heathen_man", "heathen")}

EVERYONE = ("man", "woman", "boy", "girl", "hman", "hkid", "puzzle", "sickh")


class Delivery:
    """One VV3-VV5 event's object with its real vtable in the game's table, its condition stubbed false."""

    def __init__(self, game: str, slot: int, who=EVERYONE, override: int = 1, cond_picks: dict | None = None):
        self.g = g = Game(game)
        # What some applies reach outside the game's own code, answered as on a machine with no settings file:
        # the C runtime's clock (time()), and the Origins payload's settings (its default; no file opens).
        g.proc.api_handlers["GetSystemTimeAsFileTime"] = lambda p: (p.write(p.arg(0), bytes(8)) or 0, 4)
        g.proc.api_handlers["GetPrivateProfileIntA"] = lambda p: (p.arg(2), 16)
        g.proc.api_handlers["CreateFileA"] = lambda p: (0xFFFFFFFF, 28)
        # The game's operator new (cdecl, the size): the emulator has no C runtime heap, so from the test's.
        g.proc.stub(NEW[game], lambda p: (p.alloc(max(p.arg(0), 4)), 0))
        if game == "vv4":
            # The Tree of Life's group behaviour (thiscall on the villager manager, 5 arguments): every villager of
            # an age starts a behaviour, with pathing the test's world does not have -- the village's, not the
            # cast villager's
            g.proc.stub(0x4671A0, lambda p: (0, 0x14))
        if game == "vv5":
            # New Believers' Divine Energy gain (thiscall, 1 argument) and the effects manager's animation start
            # (0x41D460 on 0x4DE000, 9 arguments): the world's, not the villager's -- as
            # tests/test_heathens_in_existing_events.py Stock.apply
            g.proc.stub(0x424F80, lambda p: (0, 4))
            g.proc.stub(0x41D460, lambda p: (0, 0x24))
        self.people = village(g, who)
        self.size, self.vt = builder_slots(g)[slot]
        self.obj = g.proc.alloc(0x40)
        g.proc.put32(self.obj, self.vt)
        for off in (4, 8, 0xC, 0x10):
            g.proc.put32(self.obj + off, 0)
        for other in range(1, 58):
            if other != slot:
                g.proc.put32(TABLES[game] + 4 * other, g.proc.alloc(0x40))
        g.proc.put32(TABLES[game] + 4 * slot, self.obj)
        self.cond_calls = 0

        def condition(p, picks=cond_picks or {}):
            self.cond_calls += 1
            for off, record in picks.items():
                p.put32(p.reg("ecx") + off, record)
            return 0, 0
        g.proc.stub(g.proc.u32(self.vt + 4), condition)
        g.proc.export("VvfpStoryProbeSetTick", 0)
        g.proc.export("VvfpStoryProbeSetPick", g.n, _position(game, slot), 0)
        g.proc.export("VvfpStoryProbeSetOverride", override)
        self.slot = slot

    def deliver(self) -> bool:
        g = self.g
        site, resume = PICK_SITES[g.game]
        other = 2 if self.slot != 2 else 3
        g.proc.set_reg("esi", other)
        g.proc.set_reg("esp", STACK)
        g.proc.run(site, resume)
        return g.proc.reg("esi") == self.slot

    def field(self, off: int) -> int:
        return self.g.proc.u32(self.obj + off)

    def run_event(self) -> None:
        """The event's own popup methods, then its own apply for every choice, from the delivered object."""
        p = self.g.proc
        method = lambda i: p.u32(self.vt + 4 * i)  # noqa: E731
        for i in ((2, 3, 10, 13) if self.size == 0xC else (2, 3, 5, 6, 7, 8, 10, 13)):
            p.call(method(i), [], ecx=self.obj)
        snapshot = p.read(self.obj, 0x14)
        for choice in ((None,) if self.size == 0xC else (0, 1)):
            p.write(self.obj, snapshot)
            if choice is None:
                p.call(method(12), [], ecx=self.obj)
            else:
                p.call(method(11), [choice], ecx=self.obj)


def cast_entries(game: str):
    for slot, e in sorted(outcomes.OVERRIDE[game].items()):
        if not e.get("refuse") and not e.get("room"):
            yield slot, e


@emulated
class TableTests(unittest.TestCase):
    def test_the_compiled_table_is_the_data(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                g = Game(game)
                order = [e["slot"] for e in story_island_events.EVENTS[game]]
                want = [s for s in order if s in outcomes.OVERRIDE[game]]
                got, i = [], 0
                while g.proc.export("VvfpStoryProbeOverrideEntry", g.n, i, SCRATCH) == 1:
                    got.append(struct.unpack("<8i", g.proc.read(SCRATCH, 32)))
                    i += 1
                self.assertEqual([row[0] for row in got], want)
                for row in got:
                    e = outcomes.OVERRIDE[game][row[0]]
                    cast = e.get("cast", {})
                    self.assertEqual(row[1:], (
                        1 if e.get("pass") else 0, KIND_IDS.get(cast.get(4), 0), KIND_IDS.get(cast.get(0xC), 0),
                        *e.get("flag", (0, 0)), e.get("room", 0), 1 if e.get("refuse") else 0), row[0])

    def test_every_entry_is_an_event_of_its_game_and_says_how_it_was_proven(self):
        for game in GAMES:
            slots = {e["slot"] for e in story_island_events.EVENTS[game]}
            for slot, e in outcomes.OVERRIDE[game].items():
                with self.subTest(game=game, slot=slot):
                    self.assertIn(slot, slots)
                    self.assertTrue(set(e) <= {"pass", "cast", "flag", "room", "refuse"}, e)
                    if game in ("vv1", "vv2"):
                        self.assertTrue(e.get("pass"), "A New Home / The Lost Children pass the condition")
                    else:
                        self.assertNotIn("pass", e)


@emulated
class CastTests(unittest.TestCase):
    """Every cast event: its condition false, it is delivered with the override, cast from the living villagers of
    its kind, and its own popup and apply run to the end."""

    def test_every_cast_event_is_delivered_cast_and_runs(self):
        ran = 0
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            for slot, e in cast_entries(game):
                with self.subTest(game=game, slot=slot):
                    d = Delivery(game, slot)
                    food_before = None
                    self.assertTrue(d.deliver(), "delivered with the override")
                    self.assertGreaterEqual(d.cond_calls, 1, "its own condition was asked first")
                    cast = e.get("cast", {})
                    picked = {}
                    for off, kind in cast.items():
                        record = d.field(off)
                        self.assertIn(record, d.people, f"+0x{off:X} is a living villager of the village")
                        self.assertTrue(kind_ok(d.people[record], kind), (off, kind, d.people[record]))
                        picked[off] = record
                    if len(picked) == 2:
                        self.assertNotEqual(picked[4], picked[0xC], "never the same villager twice")
                    if "flag" in e:
                        count, base = e["flag"]
                        self.assertIn(d.field(0x10), range(base, base + count))
                    d.run_event()
                    ran += 1
        if not ran:
            self.skipTest("needs the stock executables")

    def test_without_the_override_the_same_pick_is_refused_and_the_object_is_left_alone(self):
        for game in ("vv3", "vv4", "vv5"):
            if not have_stock(game):
                continue
            slot = next(s for s, e in cast_entries(game) if e.get("cast"))
            with self.subTest(game=game):
                d = Delivery(game, slot, override=0)
                self.assertFalse(d.deliver())
                self.assertEqual((d.field(4), d.field(0xC)), (0, 0))

    def test_a_villager_its_own_condition_picked_is_kept(self):
        for game, slot in (("vv3", 34), ("vv5", 13)):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                probe = Delivery(game, slot)
                chosen = next(r for r, k in probe.people.items() if k == ("woman" if game == "vv3" else "girl"))
                d = Delivery(game, slot, cond_picks={4: chosen})
                self.assertTrue(d.deliver())
                self.assertEqual(d.field(4), chosen)
                self.assertNotEqual(d.field(0xC), chosen)

    def test_a_childs_part_falls_back_to_anyone_a_sexed_or_adults_part_never_does(self):
        if not have_stock("vv3"):
            self.skipTest("needs The Secret City")
        d = Delivery("vv3", 24, who=("man", "woman"))          # The Ants and the Granary: a child
        self.assertTrue(d.deliver())
        self.assertIn(d.people[d.field(4)], ("man", "woman"))
        d.run_event()
        for slot, who, missing in ((34, ("woman", "boy", "girl"), "an adult man"),   # The Lovers
                                   (18, ("boy", "girl"), "an adult")):               # an adult's part
            with self.subTest(slot=slot):
                d = Delivery("vv3", slot, who=who)
                self.assertFalse(d.deliver())
                self.assertEqual((d.field(4), d.field(0xC)), (0, 0), "put back as it was")
                why = d.g.proc.alloc(400)
                self.assertEqual(d.g.proc.export("VvfpStoryProbeOverridePossible", 3, _position("vv3", slot), why), 0)
                self.assertEqual(d.g.proc.cstring(why), missing)

    def test_new_believers_never_casts_a_heathen_outside_a_heathens_part(self):
        if not have_stock("vv5"):
            self.skipTest("needs New Believers")
        # only Heathens: a believer's part has nobody
        d = Delivery("vv5", 11, who=("hman", "hkid"))
        self.assertFalse(d.deliver())
        # a Heathen's part: never a puzzle's or a sick Heathen
        d = Delivery("vv5", 44, who=("man", "puzzle", "sickh"))     # The Defector
        self.assertFalse(d.deliver())
        why = d.g.proc.alloc(400)
        self.assertEqual(d.g.proc.export("VvfpStoryProbeOverridePossible", 5, _position("vv5", 44), why), 0)
        self.assertIn("Heathen", d.g.proc.cstring(why))
        d = Delivery("vv5", 44, who=("man", "puzzle", "sickh", "hman"))
        self.assertTrue(d.deliver())
        self.assertEqual(d.people[d.field(4)], "hman")
        # a Heathen child's part takes another ordinary Heathen when there is no Heathen child
        d = Delivery("vv5", 13, who=("girl", "hman", "puzzle"))
        self.assertTrue(d.deliver())
        self.assertEqual((d.people[d.field(4)], d.people[d.field(0xC)]), ("girl", "hman"))
        d.run_event()

    def test_two_parts_need_two_villagers(self):
        if not have_stock("vv5"):
            self.skipTest("needs New Believers")
        d = Delivery("vv5", 14, who=("girl",))                      # The Daredevil Jump: a female and a male
        self.assertFalse(d.deliver())

    def test_trick_or_trade_never_takes_the_food_below_zero(self):
        if not have_stock("vv5"):
            self.skipTest("needs New Believers")
        d = Delivery("vv5", 41)
        food = 0x51D34C
        d.g.proc.put32(food, 0)
        self.assertTrue(d.deliver())
        d.run_event()
        self.assertGreaterEqual(struct.unpack("<i", d.g.proc.read(food, 4))[0], 0)

    def test_what_stays_refused(self):
        for game, slot, words in (("vv3", 47, "tribal chief"), ("vv4", 34, "mother with a baby")):
            if not have_stock(game):
                continue
            with self.subTest(game=game, slot=slot):
                d = Delivery(game, slot)
                self.assertFalse(d.deliver())
                why = d.g.proc.alloc(400)
                self.assertEqual(d.g.proc.export("VvfpStoryProbeOverridePossible", d.g.n, _position(game, slot),
                                                 why), 0)
                self.assertIn(words, d.g.proc.cstring(why))
                self.assertIn("can not be forced safely", d.g.proc.cstring(why))


@emulated
class RoomTests(unittest.TestCase):
    """The game's room test is not asked; the free villager records are."""

    def test_room_events_need_free_records_only(self):
        for game, slot in (("vv3", 7), ("vv3", 57), ("vv5", 26)):
            if not have_stock(game):
                continue
            need = outcomes.OVERRIDE[game][slot]["room"]
            for free, delivered in ((need, True), (need - 1, False)):
                with self.subTest(game=game, slot=slot, free=free):
                    d = Delivery(game, slot)
                    v = d.g.village
                    count = v.L["count"]
                    for i in range(count - free):
                        d.g.proc.write(v.record(i) + v.L["active"], b"\1")
                    self.assertEqual(d.deliver(), delivered)


@emulated
class PassTests(unittest.TestCase):
    """A New Home / The Lost Children: the event's own condition is passed for its roll only with the override."""

    def test_vv1_island_events(self):
        if not have_stock("vv1"):
            self.skipTest("needs A New Home")
        for slot in (3, 12):                     # Locusts (no crops), the Barrel (room: the game's own says no)
            for override in (1, 0):
                with self.subTest(slot=slot, override=override):
                    g = Game("vv1")
                    g.proc.stub(0x402F10, _script((13,)))
                    g.proc.stub(0x43A1A0, lambda p: (0, 0))      # the game's room test: full
                    g.proc.export("VvfpStoryProbeSetTick", 0)
                    g.proc.export("VvfpStoryProbeSetPick", 1, _position("vv1", slot), 0)
                    g.proc.export("VvfpStoryProbeSetOverride", override)
                    event = g.proc.alloc(0x6000)
                    g.proc.put32(event + 0x50A4, g.village.world)
                    g.proc.put32(event + 0x50A8, g.village.base)
                    seen = []
                    g.proc.stub(0x427CA0, lambda p: (seen.append(p.arg(0)) or 0, 8))
                    g.proc.call(0x428470, [2, 6], ecx=event)
                    self.assertEqual(seen, [slot if override else 13])

    def test_vv1_encounters(self):
        if not have_stock("vv1"):
            self.skipTest("needs A New Home")
        slot = (1 << 6) | 0                      # The Trapped Whale with spirituality at its highest
        for override in (1, 0):
            with self.subTest(override=override):
                g = Game("vv1")
                g.proc.stub(0x402F10, _script((2,)))
                g.proc.export("VvfpStoryProbeSetTick", 0)
                g.proc.export("VvfpStoryProbeSetPick", 1, _position("vv1", slot), 0)
                g.proc.export("VvfpStoryProbeSetOverride", override)
                g.proc.put32(g.village.world + 0xA2BC, 3)
                event = g.proc.alloc(0x6000)
                g.proc.put32(event + 0x50A4, g.village.world)
                g.proc.put32(event + 0x50A8, g.village.base)
                self.assertEqual(g.proc.call(0x418920, [], ecx=event), 0 if override else 2)

    def test_vv2_single_result_events(self):
        if not have_stock("vv2"):
            self.skipTest("needs The Lost Children")
        for slot in (16, 21, 25):                # a population of six; the game's room test full
            # (A Dangerous Mission's own population count reads the whole village: without the override it runs
            # only in the game, as tests/test_story_outcomes.py UnlockTests says of the checks that read it)
            for override in ((1,) if slot == 16 else (1, 0)):
                with self.subTest(slot=slot, override=override):
                    g = Game("vv2")
                    g.proc.stub(0x4031A0, _script((22,)))
                    g.proc.stub(0x44B310, lambda p: (0, 0))
                    g.proc.export("VvfpStoryProbeSetTick", 0)
                    g.proc.export("VvfpStoryProbeSetPick", 2, _position("vv2", slot), 0)
                    g.proc.export("VvfpStoryProbeSetOverride", override)
                    seen = []
                    g.proc.stub(stock_target("vv2", 0x43483D), lambda p: (seen.append(p.arg(0)) or 0, 8))
                    event = g.proc.alloc(0x6000)
                    g.proc.call(0x434570, [2, 7], ecx=event)
                    self.assertEqual(seen, [slot if override else 22])

    def test_vv2_the_mother_is_still_needed(self):
        if not have_stock("vv2"):
            self.skipTest("needs The Lost Children")
        g = Game("vv2")
        why = g.proc.alloc(400)
        self.assertEqual(g.proc.export("VvfpStoryProbeOverridePossible", 2, _position("vv2", 15), why), 0)
        self.assertEqual(g.proc.export("VvfpStoryProbeOverridePossible", 2, _position("vv2", 16), why), 1)


@emulated
class PickerTests(unittest.TestCase):
    """The picker: the override is off when it opens; ticked, the events it reaches are offered and marked."""

    def _open(self, game, failing):
        g = Game(game)
        for slot in range(1, 58):
            obj = g.proc.alloc(0x40)
            vt = g.proc.alloc(0x40)
            code = g.proc.alloc(0x40)
            g.proc.write(code, b"\xC3" * 0x20)
            g.proc.put32(obj, vt)
            for i in range(16):
                g.proc.put32(vt + 4 * i, code + i)
            g.proc.stub(code + 1, lambda p, ok=(slot not in failing): (1 if ok else 0, 0))
            g.proc.put32(TABLES[game] + 4 * slot, obj)
        g.proc.export("VvfpStoryProbeChooserOpen", g.n, 0)
        return g

    def _row(self, g, index):
        out = SCRATCH + 0x3000
        possible = g.proc.export("VvfpStoryProbeChooserText", index, 0, out, 1200)
        g.proc.export("VvfpStoryProbeChooserText", index, 0xFFFFFFFF, out, 1200)
        label = g.proc.cstring(out)
        g.proc.export("VvfpStoryProbeChooserWords", index, 0, 0, out, 1200)
        return possible, label, g.proc.cstring(out)

    def test_the_rows_with_and_without_the_override(self):
        if not have_stock("vv3"):
            self.skipTest("needs The Secret City")
        g = self._open("vv3", {18, 47, 7})
        crystal, chief = _position("vv3", 18), _position("vv3", 47)
        self.assertEqual(self._row(g, crystal)[0], 0, "off when the picker opens")
        g.proc.export("VvfpStoryProbeChooserOverride", 1)
        possible, label, words = self._row(g, crystal)
        self.assertEqual(possible, 3)
        self.assertTrue(label.endswith(" (only with the override)"), label)
        self.assertIn("With the override it happens anyway", words)
        why = g.proc.alloc(400)
        self.assertEqual(g.proc.export("VvfpStoryProbeChooserWhy", crystal, why, 400), 1, "bought with it")
        possible, label, words = self._row(g, chief)
        self.assertEqual(possible, 0)
        self.assertIn("Not possible even with the override", words)
        self.assertIn("tribal chief", words)
        self.assertEqual(self._row(g, _position("vv3", 2))[0], 1, "a possible event is as it was")
        g.proc.export("VvfpStoryProbeChooserOverride", 0)
        self.assertEqual(self._row(g, crystal)[0], 0)
        self.assertEqual(g.proc.export("VvfpStoryProbeChooserWhy", crystal, why, 400), 0)

    def test_the_checkbox_warns_first_and_the_gong_has_none(self):
        rc = (ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.rc").read_text(encoding="utf-8")
        self.assertIn('CONTROL     "", 3015, "Button", BS_AUTOCHECKBOX', rc)   # its words: chooser_dialog.s7, by key
        ui = (ROOT / "native" / "vvfp_story_upgrades" / "story_outcomes_ui.inc").read_text(encoding="utf-8")
        self.assertIn("MB_OKCANCEL | MB_ICONWARNING | MB_DEFBUTTON2", ui[ui.index("IDC_PICK_OVERRIDE && code"):])
        self.assertIn("ShowWindow(GetDlgItem(window, IDC_PICK_OVERRIDE), SW_HIDE)", ui)
        self.assertIn("CheckDlgButton(window, IDC_PICK_OVERRIDE, BST_UNCHECKED);\n        chooser_set_text(window, "
                      "IDC_PICK_OVERRIDE,", ui)


if __name__ == "__main__":
    unittest.main()
