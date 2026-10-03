"""New Believers: the Custom Island Event Maker's faction changes never count.

The owner (2026-10-02): "Becomes a believer", "Becomes a Heathen" and the new
Heathens the Maker makes must not change the game's own statistics or
trophies; "if the player converts them the normal way I want it to count."

What the game's routines write outside the villager's record (emulated on
the stock code and on the full public catalog, every byte of every writable
section compared):

* to a believer, 0x4668B0: trophy progress "A Heathen's Prerogative" (0x13,
  earned at 3) and "If You Can't Beat 'Em..." (0x14, earned at 10) in the
  trophy table 0x4DB358 (entry i at +i*12: earned byte, progress, stamp);
  earning one also queues its popup (+0x318) and adds to Over-Achiever (0x40)
  and Unachievable (0x41).  With the statistics row, the patcher's Heathens
  Converted total 0x51D3A4 (its detour on 0x4668B0's entry).
* to a Heathen, 0x4669E0, and the Heathen creator 0x46FD20: nothing.

Everything here runs the REAL conversion code; only the routines that need
the renderer (sound, sparkles, the status line, the tip, the action start
and stop) are stubbed, and recorded.
"""
from __future__ import annotations

import re
import struct
import unittest

from test_story_custom_island_event import (
    MODES,
    ROOT,
    Story,
    emulated,
    have_stock,
)
from story_custom_fixtures import Change, Event, Spawn

import build_statistics_features as stats_features

TROPHIES = 0x4DB358
TROPHY_BYTES = 0x428
HEATHENS_CONVERTED = 0x51D3A4
PREROGATIVE, CANT_BEAT_EM, OVER_ACHIEVER, UNACHIEVABLE = 0x13, 0x14, 0x40, 0x41
SOURCE = ROOT / "native" / "vvfp_story_upgrades" / "story_c5.inc"

# The routines that need the renderer: (address, bytes popped).
UI = {0x44EF60: 8, 0x44C440: 4, 0x476D00: 0x14, 0x470810: 0xC, 0x44E730: 0xC,
      0x465580: 8, 0x473440: 0}


def trophy(proc, i):
    raw = proc.read(TROPHIES + 12 * i, 12)
    return raw[0], struct.unpack_from("<i", raw, 4)[0]


def setup(mode="collection_progression"):
    story = Story("vv5", mode, full=True)
    p = story.proc
    v = story.village
    ui = []
    def screen(va, pop):
        def fn(q):
            ui.append(va)
            return 0, pop
        return fn
    for va, pop in UI.items():
        p.stub(va, screen(va, pop))
    p.stub(0x41ED40, lambda q: (777, 0))                 # the trophy's time stamp
    p.write(v.world + 0x17E39, b"\1")                    # in play (SetFaith converts)
    p.stub(0x425950, lambda q: (v.world, 0))
    # The creator's random numbers, CRT data, clock and name pick.
    state = [12345]

    def rand(q):
        state[0] = (state[0] * 1103515245 + 12345) & 0x7FFFFFFF
        bound = q.arg(0)
        return ((state[0] >> 8) % bound if bound else 0), 0
    p.stub(0x403660, rand)
    ptd = p.alloc(0x400)
    p.stub(0x48173E, lambda q: (ptd, 0))
    p.stub(0x4036E0, lambda q: (100000, 0))

    def name(q):
        q.put32(q.reg("ecx") + 8, 1)
        q.put32(q.reg("ecx") + 0xC, q.arg(0))
        q.write(q.reg("ecx") + 0x10, b"Nm\0")
        return 0, 4
    p.stub(0x46F680, name)
    for i in range(150):
        p.put32(v.record(i) + 0x1B80, v.record(i))
    v.put(0, sex="m", years=40, name="Elder")             # an adult believer (arming)
    v.put(1, sex="f", years=30, name="Believer")
    p.put32(v.record(1) + 0x1CF0, 20)
    v.put(2, sex="m", years=30, name="Heathen", faction=1)
    p.put32(v.record(2) + 0x1CF0, (-5) & 0xFFFFFFFF)
    v.put(3, sex="f", years=30, name="Another", faction=1)   # a Heathen remains
    p.put32(v.record(3) + 0x1CF0, (-30) & 0xFFFFFFFF)
    # Trophy progress the player has already earned towards, and the popup
    # queue empty (-1 each, as 0x413360 clears it).
    p.write(TROPHIES + 0x318, b"\xff" * (0x42 * 4))
    for i, progress in ((PREROGATIVE, 1), (CANT_BEAT_EM, 7), (OVER_ACHIEVER, 4),
                        (UNACHIEVABLE, 4)):
        p.put32(TROPHIES + 12 * i + 4, progress)
    p.put32(HEATHENS_CONVERTED, 9)
    return story, ui


def counters(proc):
    return proc.read(TROPHIES, TROPHY_BYTES), proc.u32(HEATHENS_CONVERTED)


def outside_records(proc):
    """Every writable byte of the executable except the villager records."""
    pe = proc._exe_pe
    base = pe.OPTIONAL_HEADER.ImageBase
    records = (0x554190, 0x554190 + 150 * 0x2F44)
    out = {}
    for s in pe.sections:
        if s.Characteristics & 0x80000000:
            va = base + s.VirtualAddress
            data = bytearray(proc.read(va, (s.Misc_VirtualSize + 0xFFF) & ~0xFFF))
            lo, hi = max(records[0], va), min(records[1], va + len(data))
            if lo < hi:
                data[lo - va:hi - va] = bytes(hi - lo)
            out[va] = bytes(data)
    return out


def changed(before, after):
    return [hex(va + k) for va in before for k in range(len(before[va]))
            if before[va][k] != after[va][k]][:16]


@emulated
class MakerConversionsDoNotCountTests(unittest.TestCase):
    def setUp(self):
        if not have_stock("vv5"):
            self.skipTest("no stock executable")

    def test_becomes_a_believer_converts_through_the_game_and_counts_nothing(self):
        for mode in MODES:
            story, ui = setup(mode)
            p, v = story.proc, story.village
            before, memory = counters(p), outside_records(p)
            ok, r, _ = story.apply(Event(changes=[story.change(2, status=0)]))
            with self.subTest(mode=mode):
                self.assertEqual(r["refused"], 0)
                self.assertEqual((v.byte(2, 0x1CEC), v.i32(2, 0x2F40), v.i32(2, 0x1CF0)),
                                 (0, 0, 55), "converted by the game's own routine")
                self.assertIn(0x44C440, ui, "the game's conversion ran (its sound)")
                self.assertEqual(counters(p), before,
                                 "no trophy, popup or Heathens Converted moved")
                self.assertEqual(changed(memory, outside_records(p)), [],
                                 "nothing outside the villager records changed")

    def test_an_earning_conversion_earns_nothing_and_queues_no_popup(self):
        story, ui = setup()
        p = story.proc
        p.put32(TROPHIES + 12 * PREROGATIVE + 4, 2)        # the next conversion earns it
        before = counters(p)
        story.apply(Event(changes=[story.change(2, status=0)]))
        self.assertEqual(story.village.byte(2, 0x1CEC), 0)
        self.assertEqual(trophy(p, PREROGATIVE), (0, 2))
        self.assertEqual(p.read(TROPHIES + 0x318, 4), b"\xff" * 4, "no popup queued")
        self.assertEqual(trophy(p, OVER_ACHIEVER), (0, 4))
        self.assertEqual(counters(p), before)

    def test_becomes_a_heathen_and_new_heathens_count_nothing(self):
        for mode in MODES:
            story, ui = setup(mode)
            p, v = story.proc, story.village
            before, memory = counters(p), outside_records(p)
            ok, r, _ = story.apply(Event(changes=[story.change(1, status=1)],
                                         spawns=[Spawn(count=1, sex=1, age=400, faction=1)]))
            with self.subTest(mode=mode):
                self.assertEqual((v.byte(1, 0x1CEC), v.i32(1, 0x2F40), v.i32(1, 0x1CF0)),
                                 (1, 2, -10))
                made = [i for i in range(4, 150) if v.byte(i, 0x1CD4)]
                self.assertEqual(len(made), 1, "one new Heathen through 0x46FD20")
                self.assertEqual((v.byte(made[0], 0x1CEC), v.i32(made[0], 0x1CF0)), (1, -55))
                self.assertEqual(counters(p), before)
                self.assertEqual(changed(memory, outside_records(p)), [])

    def test_a_conversion_in_play_still_counts(self):
        """The game's own route (faith rising above 0, SetFaith 0x467F90, as
        preaching drives it) is untouched: both trophies and Heathens
        Converted move, and an earning conversion earns."""
        for mode in MODES:
            story, ui = setup(mode)
            p, v = story.proc, story.village
            p.put32(TROPHIES + 12 * PREROGATIVE + 4, 2)
            p.call(0x467F90, [10, 1], ecx=v.record(2))
            with self.subTest(mode=mode):
                self.assertEqual(v.byte(2, 0x1CEC), 0)
                self.assertEqual(trophy(p, PREROGATIVE), (1, 3), "earned at 3")
                self.assertEqual(trophy(p, CANT_BEAT_EM), (0, 8))
                self.assertEqual(trophy(p, OVER_ACHIEVER)[1], 5, "earning adds to Over-Achiever")
                self.assertEqual(p.read(TROPHIES + 0x318, 4), struct.pack("<i", PREROGATIVE),
                                 "the popup is queued")
                self.assertEqual(p.u32(HEATHENS_CONVERTED), 10)


class TheAddressesAreTheGamesAndTheStatisticsRows(unittest.TestCase):
    def test_constants_match(self):
        text = SOURCE.read_text(encoding="utf-8")
        value = lambda name: int(re.search(rf"#define {name} (0x[0-9A-F]+)u?", text).group(1), 16)
        self.assertEqual(value("C5_TROPHIES"), TROPHIES)
        self.assertEqual(value("C5_TROPHY_BYTES"), TROPHY_BYTES)
        config = stats_features.GAMES["vv5"]
        self.assertEqual(value("C5_HEATHENS_CONVERTED"), config["conversion_stat_va"])
        self.assertEqual(HEATHENS_CONVERTED, config["conversion_stat_va"])
        self.assertEqual(config["conversion_hook_va"], 0x4668B0)


if __name__ == "__main__":
    unittest.main()
