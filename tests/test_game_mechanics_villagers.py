"""Game Mechanics' Villagers group (src/vv_game_mechanics_villagers.py; the owner, 2026-11-26: "please add heathen
info in game mechanics, as detailed as the believers. plus their current faith and time until conversion cooldown
expires" and "add villagers' faith and health too!").

Every case starts from a committed real save (tests/fixtures/rename_tribe, as test_game_mechanics_life.py) and
writes the fields under test into a copy at the offsets the module reads -- health and the sick mark in every game;
New Believers' faction, mask bytes, role, Faith and preaching wait -- so each line is checked against chosen values.
The preaching wait's code is checked in the stock exe where it is present.
"""
from __future__ import annotations

import gzip
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_game_mechanics_villagers as villagers  # noqa: E402
import vv_last_names as ln  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
SAVES = {1: "vv1-huttest-1", 2: "vv2-huttest-1", 3: "vv3-huttest-1", 4: "vv4-huttest-1", 5: "vv5-256-1"}
NOW = 1_790_000_000 + 3_000_000
GROUP = gm.VILLAGERS


def fixture(game: int) -> bytearray:
    return bytearray(gzip.decompress((FIXTURES / f"{SAVES[game]}.ldw.gz").read_bytes()))


def entries(game: int, data: bytes) -> list[int]:
    """The villagers whose name no other villager shares (a line is found by its name)."""
    ats = ln._entries(game, bytes(data))
    names = [ln._cstr(data, at, ln.FIELDS[game].name_cap) for at in ats]
    return [at for at, n in zip(ats, names) if names.count(n) == 1]


def put(data: bytearray, at: int, value: int) -> None:
    struct.pack_into("<i", data, at, value)


def name(game: int, data: bytes, at: int) -> str:
    return ln._cstr(data, at, ln.FIELDS[game].name_cap)


def page(test: unittest.TestCase, game: int, data: bytes, now: float = NOW) -> list[gm.Fact]:
    import vv_tribe_rename
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
    root = Path(tempfile.mkdtemp(prefix="gmv"))
    test.addCleanup(shutil.rmtree, root, True)
    folder = root / base
    folder.mkdir()
    (folder / f"{base}1.ldw").write_bytes(bytes(data))
    return gm.read(folder, game, 1, [], now=now)


def group(facts: list[gm.Fact]) -> list[gm.Fact]:
    return [f for f in facts if f.group == GROUP]


def line_of(facts: list[gm.Fact], who: str) -> gm.Fact:
    return next(f for f in group(facts) if not f.sub and f.text.startswith(f"{who}: "))


def subs_of(facts: list[gm.Fact], who: str) -> list[gm.Fact]:
    rows = group(facts)
    start = rows.index(line_of(facts, who))
    out = []
    for f in rows[start + 1:]:
        if not f.sub:
            break
        out.append(f)
    return out


# New Believers' Heathens, made in a copy: (faction 1, role, orange byte, red byte, Faith).
def heathen(data: bytearray, at: int, role: int = 0, orange: int = 0, red: int = 0, faith: int = -30,
            wait: int = 0) -> None:
    data[at + villagers.VV5_FACTION] = 1
    data[at + villagers.VV5_ORANGE] = orange
    data[at + villagers.VV5_RED] = red
    put(data, at + villagers.VV5_ROLE, role)
    put(data, at - 0x18, faith)
    struct.pack_into("<I", data, at + villagers.VV5_WAIT, wait)


def believer(data: bytearray, at: int, faith: int = 40) -> None:
    data[at + villagers.VV5_FACTION] = 0
    data[at + villagers.VV5_ORANGE] = 0
    data[at + villagers.VV5_RED] = 0
    put(data, at + villagers.VV5_ROLE, 0)
    put(data, at - 0x18, faith)


class EveryGame(unittest.TestCase):
    def test_one_line_per_living_villager_with_health(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                facts = page(self, game, data)
                rows = group(facts)
                self.assertTrue(rows, "the Villagers group is on every save's page")
                order = [gm.GROUPS.index(f.group) for f in facts]
                self.assertEqual(order, sorted(order))
                self.assertEqual(gm.GROUPS.index(GROUP), gm.GROUPS.index(life.VILLAGER_TIMERS) + 1)
                village = gm.Village(Path("."), game, 1, Path("x"), bytes(data), None, NOW)
                everyone = life.people(village)
                heads = [f for f in rows if not f.sub and re.search(r"; health -?\d+ of 100", f.text)]
                self.assertEqual(len(heads), len(everyone))
                for p in (q for q in everyone if sum(r.name == q.name for r in everyone) == 1):
                    line = line_of(facts, p.name)
                    self.assertIn(f"health {p.health} of 100", line.text)
                    self.assertIn(p.sex, line.text)
                    self.assertIn(f"{p.age // 20} villager year", line.text)
                    self.assertTrue(line.confirmed)

    def test_health_states(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                lay = life.LAYOUTS[game]
                ats = entries(game, data)
                ats = [at for at in ats if game != 5 or data[at + villagers.VV5_FACTION] == 0][:3]
                for at in ats:
                    if game == 5:
                        believer(data, at)
                # healthy; sick at 80; sick at 15 (near death)
                for at, health, sick in zip(ats, (100, 80, 15), (0, 1, 1)):
                    put(data, at + lay.health, health)
                    if lay.sick_byte:
                        data[at + lay.sick] = sick
                    else:
                        put(data, at + lay.sick, sick)
                facts = page(self, game, data)
                well, ill, weak = (line_of(facts, name(game, data, at)).text for at in ats)
                self.assertIn("health 100 of 100", well)
                self.assertNotIn("sick", well.split(";")[2] if well.count(";") > 1 else well)
                self.assertIn("health 80 of 100, sick (see Villager timers", ill)
                self.assertIn("health 15 of 100, sick (near death", weak)

    def test_the_general_page_has_no_villagers(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertNotIn(GROUP, {f.group for f in gm.general(game, now=NOW)})

    def test_faith_only_in_new_believers(self) -> None:
        for game in range(1, 5):
            with self.subTest(game=game):
                text = "\n".join(f.text for f in group(page(self, game, fixture(game))))
                self.assertNotIn("Faith", text)
                self.assertNotIn("Heathen", text)

    def test_plain_words(self) -> None:
        """No code labels: no hex, offsets, field or role numbers, no programmer names."""
        bad = re.compile(r"0x[0-9A-Fa-f]|\+0x|\brole \d|\bfaction\b|\bVV5_|\bentry\b|\boffset\b|\bdword\b|\bbyte\b"
                         r"|\bTrue\b|\bFalse\b|\bNone\b|\bkind byte\b")
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                if game == 5:
                    ats = entries(5, data)
                    heathen(data, ats[0], role=13, faith=-94)
                    heathen(data, ats[1], orange=1, faith=-40)
                for f in group(page(self, game, data)):
                    self.assertIsNone(bad.search(f.text), f.text)


class NewBelievers(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture(5)
        self.ats = entries(5, self.data)
        self.start = villagers.clock_start(bytes(self.data))
        self.assertIsNotNone(self.start)

    def test_believers_show_their_faith(self) -> None:
        low, high = self.ats[0], self.ats[1]
        believer(self.data, low, faith=4)
        believer(self.data, high, faith=72)
        facts = page(self, 5, self.data)
        self.assertIn("; Faith 4 (becomes a Heathen at 0 or less)", line_of(facts, name(5, self.data, low)).text)
        self.assertIn("; Faith 72.", line_of(facts, name(5, self.data, high)).text)

    def test_every_mask_and_role(self) -> None:
        cases = [  # (role, orange, red) -> (mask, role words)
            ((12, 0, 0), ("purple mask", "the Heathen Doctor (a puzzle Heathen)")),
            ((13, 0, 0), ("the Chief's mask", "the Heathen Chief (a puzzle Heathen)")),
            ((14, 0, 0), ("purple mask", "the Heathen Master Scientist (a puzzle Heathen)")),
            ((15, 0, 0), ("purple mask", "the Heathen Master Builder (a puzzle Heathen)")),
            ((16, 0, 0), ("purple mask", "the Heathen Master Farmer (a puzzle Heathen)")),
            ((17, 0, 0), ("blue mask", "the Heathen Mommy (a puzzle Heathen)")),
            ((0, 0, 0), ("blue mask", "an ordinary Heathen (blue: can be preached to)")),
            ((6, 1, 0), ("orange mask", "a heathen guard (orange: chases believers away)")),
            ((18, 0, 1), ("red mask", "a senior heathen guard (red: so scary that believers run)")),
        ]
        for n, ((role, orange, red), _) in enumerate(cases):
            heathen(self.data, self.ats[n], role, orange, red, faith=-10 - n)
        facts = page(self, 5, self.data)
        for n, (_, (mask, words)) in enumerate(cases):
            with self.subTest(role=cases[n][0]):
                text = line_of(facts, name(5, self.data, self.ats[n])).text
                self.assertIn(f"; Faith {-10 - n}; {mask}; {words}.", text)
                rows = " ".join(f.text for f in subs_of(facts, name(5, self.data, self.ats[n])))
                for part in ("Skills: ", "Likes: ", "Parents: "):
                    self.assertIn(part, rows)
                if cases[n][0][0] in villagers.PUZZLE_ROLES:
                    self.assertIn("Preaching wait: does not apply (a puzzle Heathen is never preached to)", rows)
                    self.assertIn("never reached by the Earthquake God Power", rows)

    def test_faith_on_both_sides_of_zero(self) -> None:
        heathen(self.data, self.ats[0], faith=-13)
        heathen(self.data, self.ats[1], faith=0)
        heathen(self.data, self.ats[2], faith=6)
        facts = page(self, 5, self.data)
        minus = " ".join(f.text for f in subs_of(facts, name(5, self.data, self.ats[0])))
        self.assertIn("Faith -13: 14 short of joining (a Heathen joins when Faith rises above 0): 3 to 5 sermons", minus)
        zero = " ".join(f.text for f in subs_of(facts, name(5, self.data, self.ats[1])))
        self.assertIn("Faith 0: 1 short of joining", zero)
        self.assertIn("1 sermon of +3 to +5", zero)
        above = " ".join(f.text for f in subs_of(facts, name(5, self.data, self.ats[2])))
        self.assertIn("Faith 6 is already above 0", above)
        self.assertIn("loading a save never converts anyone", above)

    def test_preaching_wait_running(self) -> None:
        clock_now = int(NOW - self.start)
        heathen(self.data, self.ats[0], wait=clock_now + 600)
        facts = page(self, 5, self.data)
        row = next(f for f in subs_of(facts, name(5, self.data, self.ats[0])) if f.text.startswith("Preaching wait"))
        self.assertEqual(row.due, float(self.start + clock_now + 600))
        self.assertEqual(row.due_kind, "ready")
        self.assertIn("tired of listening until", row.text)
        self.assertIn("10 real-life minutes left", row.text)
        self.assertIn("the same at Fast, Normal and Slow", row.text)
        self.assertIn("paused or closed", row.text)
        rendered = gm.render(facts, NOW)
        self.assertIn("(in 10 min 00 s)", rendered)
        self.assertIn(gm.DUE_NOW, gm.render(facts, NOW + 601))

    def test_preaching_wait_expired_and_unset(self) -> None:
        clock_now = int(NOW - self.start)
        heathen(self.data, self.ats[0], wait=clock_now - 60)
        heathen(self.data, self.ats[1], wait=0)
        heathen(self.data, self.ats[2], wait=clock_now + 7200, role=0, orange=1)
        facts = page(self, 5, self.data)
        rows = [next(f for f in subs_of(facts, name(5, self.data, at)) if f.text.startswith("Preaching wait"))
                for at in self.ats[:3]]
        self.assertTrue(rows[0].text.startswith("Preaching wait: ready now (the 2-hour wait ended "))
        self.assertIsNone(rows[0].due)
        self.assertEqual(rows[1].text, "Preaching wait: ready now (no wait set).")
        self.assertIn("120 real-life minutes left", rows[2].text)

    def test_heathens_never_count_and_the_page_says_so(self) -> None:
        for at in self.ats[:4]:
            heathen(self.data, at)
        facts = page(self, 5, self.data)
        header = next(f for f in group(facts) if f.text.startswith("Heathens outside the tribe: "))
        self.assertIn("never count in the patcher's Village Statistics", header.text)
        intro = group(facts)[0].text
        everyone = life.people(gm.Village(Path("."), 5, 1, Path("x"), bytes(self.data), None, NOW))
        tribe = sum(1 for p in everyone if not p.heathen)
        self.assertIn(f"({tribe} in the tribe, {len(everyone) - tribe} Heathens outside it)", intro)
        self.assertIn(f"Believers in the tribe: {tribe}.", [f.text for f in group(facts)])
        vitals = " ".join(f.text for f in facts if f.group == life.VITALS)
        self.assertIn("never counted in the patcher's Village Statistics", vitals)

    def test_a_heathen_is_as_detailed_as_a_believer(self) -> None:
        believer(self.data, self.ats[0])
        heathen(self.data, self.ats[1])
        facts = page(self, 5, self.data)

        def kinds(who: str) -> set[str]:
            return {f.text.split(":", 1)[0] for f in subs_of(facts, who)}

        self.assertLessEqual(kinds(name(5, self.data, self.ats[0])) - {"Titles"},
                             kinds(name(5, self.data, self.ats[1])))

    def test_minimal_detail_keeps_each_villager(self) -> None:
        heathen(self.data, self.ats[0], wait=int(NOW - self.start) + 300)
        short = gm.minimum(page(self, 5, self.data))
        who = name(5, self.data, self.ats[0])
        self.assertTrue(any(f.group == GROUP and f.text.startswith(f"{who}: ") for f in short))
        self.assertTrue(any(f.group == GROUP and f.text.startswith("Preaching wait: tired") for f in short))

    def test_length_stays_bounded(self) -> None:
        """At most 9 lines a villager (its line and up to 8 below it), plus 4 group lines."""
        for at in self.ats[:30]:
            heathen(self.data, at)
        facts = page(self, 5, self.data)
        people = len(life.people(gm.Village(Path("."), 5, 1, Path("x"), bytes(self.data), None, NOW)))
        self.assertLessEqual(len(group(facts)), 9 * people + 4)


class FaithGroup(unittest.TestCase):
    def test_the_wait_is_said_under_faith_and_heathens(self) -> None:
        import vv_game_mechanics_faith_vv5 as faith
        village = gm.Village(Path("."), 5, 1, Path("5.ldw"), gm.blank_save(5, 1.8e9), frozenset(), 1.8e9,
                             general=True)
        text = " ".join(f.text for f in faith.lines(village))
        self.assertIn("Each Heathen keeps their own wait in the save (Villagers shows how long is left)", text)
        self.assertIn("Every Heathen it reaches then cannot be preached to for 2 real-life hours", text)


try:
    import island_event_exe as ie
    _EXE = ie.available(5)
except Exception:  # noqa: BLE001
    _EXE = False


@unittest.skipUnless(_EXE, "the stock New Believers exe (research/stock-executables or inputs) is not here")
class StockExe(unittest.TestCase):
    """The preaching wait as the module's docstring cites it, read from the stock exe."""

    def setUp(self) -> None:
        self.exe = ie.exe(5)

    def test_the_wait_is_set_to_the_clock_plus_two_hours(self) -> None:
        for at, want in ((0x468F25, "call 0x4036e0"), (0x468F2A, "add eax, 0x1c20"),
                         (0x468F33, "mov dword ptr [esi + 0x1cf4], eax"),
                         (0x46D2D8, "add eax, 0x1c20"), (0x46D2E4, "mov dword ptr [esi + 0x1cf4], eax"),
                         (0x41F7B8, "add eax, 0x1c20"), (0x41F7BD, "mov dword ptr [esi + 0x1cf4], eax")):
            with self.subTest(at=hex(at)):
                self.assertEqual(self.exe.instruction(at), want)
        self.assertEqual(villagers.WAIT_SECONDS, 0x1C20)

    def test_the_sermon_end_tests_the_wait(self) -> None:
        for at, want in ((0x468E19, "mov ebp, dword ptr [esi + 0x1cf4]"), (0x468E26, "call 0x4036e0"),
                         (0x468E2B, "cmp ebp, eax"), (0x468E30, "jbe 0x468e8f")):
            with self.subTest(at=hex(at)):
                self.assertEqual(self.exe.instruction(at), want)

    def test_the_save_keeps_the_wait(self) -> None:
        # The writer copies +0x1CF4 to entry +0x114; the name is at entry +0x20, so the wait is name + 0xF4.
        self.assertEqual(self.exe.instruction(0x465346), "mov eax, dword ptr [edi + 0x1cf4]")
        self.assertEqual(self.exe.instruction(0x46534C), "mov dword ptr [esi + 0x114], eax")
        self.assertEqual(villagers.VV5_WAIT, 0x114 - 0x20)
        self.assertEqual(self.exe.instruction(0x466C23), "mov dword ptr [esi + 0x1cf4], eax")

    def test_the_clock_is_real_seconds_from_the_saved_stamp(self) -> None:
        self.assertEqual(self.exe.instruction(0x4036E8), "call 0x47c96a")          # _time64
        self.assertEqual(self.exe.instruction(0x403705), "call 0x47cf8a")          # difftime
        self.assertEqual(self.exe.instruction(0x40383F), "mov dword ptr [0x4c6250], ecx")   # the header's stamp
        self.assertEqual(villagers.HEADER_STAMP, 0x4C6250 - 0x4C6248)


if __name__ == "__main__":
    unittest.main()
