"""Revive keeps every detail (the owner, 2026-11-25): the snapshot holds exactly what each game's own save keeps.

native/shared/revive_snapshot.h keeps, at every death and disappearance, the bytes of the villager record that the
game's own save writes and its own loader restores -- everything that survives a save and a load, which is what
"every persistent field" means for the game itself -- and restores the persistent part of it (VV_RS_KEEP_*) onto the
revived villager.  This test proves the windows against the games, and the field table against the windows:

* the REAL per-villager loader of each stock executable (inputs/vvN-stock-copy) runs in Unicorn twice, from two
  saved entries that differ in every byte; the record bytes that come out different are exactly the ones the loader
  restores from the save, and they must be exactly VV_RS_SAVED_<game> (less the few bytes the run must hold equal
  to keep the loader on one path, named below);
* FIELDS names every field of those windows, persistent or transient, with the code that shows it (the two
  research passes of 2026-11-25, every address checked in the stock executables), with no gap and no overlap;
* VV_RS_KEEP_<game> is exactly the union of the persistent fields (The Secret City's Tribal Chief flag and New
  Believers' faction byte apart: both are restored by their own rules, story_revive.inc);
* the identity fields the matching reads (VV_RS_LAYOUT) are the Cause of Death companion's own (REC), and age is
  never restored (the owner: they come back at age 5).
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native" / "shared" / "revive_snapshot.h"
COD = ROOT / "native" / "vvfp_cause_of_death" / "vvfp_cause_of_death.c"
EXES = {
    1: ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
    2: ROOT / "inputs" / "vv2-stock-copy" / "Virtual Villagers - The Lost Children.exe",
    3: ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe",
    4: ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe",
    5: ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe",
}

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover
    HAVE_EMULATOR = False

P, T = "persistent", "transient"

# Every field of every saved window: (offset, size, what it is, P/T, the evidence).
FIELDS = {
    1: [
        (0x33C, 4, "life tick's seconds not yet turned into age", T, "creator 0x43C6EB = 0; tick 0x42EA58"),
        (0x340, 4, "elapsed-time mark the record last saw", T, "0x43C6FF; tick 0x42E988"),
        (0x344, 4, "health", T, "creator 0x43C70C = 0x5A"),
        (0x348, 4, "age", T, "0x43C73C"),
        (0x34C, 4, "processed age (the life tick's cursor)", T, "0x43C742; 0x42EF27"),
        (0x350, 4, "sex (1 male, 2 female)", P, "0x43C5E9"),
        (0x354, 4, "sick", T, "creator 0x43C716 = 0"),
        (0x358, 4, "pregnancy stamp", T, "conception 0x43BBFA; cleared 0x42F0B2"),
        (0x35C, 4, "litter", T, "0x43BC4E / 0x43BC8C; cleared 0x42F0C7"),
        (0x360, 4, "head", P, "0x43C647"),
        (0x364, 4, "body", P, "0x43C633"),
        (0x368, 4, "personal number (name pick, skeleton frame, voice)", P, "0x43C657..0x43C675; 0x43B9BC"),
        (0x36C, 4, "family (last name; 0xC7 the Golden Child)", P, "0x43C67B; delivery 0x42EFC7"),
        (0x370, 0x1C, "name, last name included", P, "0x43C696"),
        (0x38C, 4, "conception: the baby's inherited-skill selector", T, "0x43BC0A"),
        (0x390, 4, "conception: the inherited-skill value", T, "0x43BC10"),
        (0x394, 4, "conception: the father's family copy", T, "0x43BC04; 0x42EF39"),
        (0x398, 0x10, "likes (4)", P, "0x43C420"),
        (0x3A8, 0x10, "dislikes (4)", P, "0x43C427"),
        (0x3B8, 4, "current work spot / task", T, "creator 0x43C728 = 0; 0x4241E2"),
        (0x3BC, 0x14, "skills: Parenting, Building, Farming, Healing, Research", P, "creator 0x43C3D8"),
        (0x3D0, 4, "job preference (the Details checkmark)", P, "creator 0x43C3F6; UI 0x4496E9"),
    ],
    2: [
        (0x524, 4, "life tick's seconds", T, "creator 0x44CD8E = 0"),
        (0x528, 4, "elapsed-time mark (the write stamp)", T, "0x44CDA2; tick 0x43B752"),
        (0x52C, 4, "health", T, "0x44CDB2 = 0x5A"),
        (0x530, 4, "age", T, "0x44CDE2"),
        (0x534, 4, "processed age", T, "0x44CDF1"),
        (0x538, 4, "sex (1 male, 2 female)", P, "0x44CB7E"),
        (0x53C, 4, "sick", T, "0x44CDBC"),
        (0x540, 4, "pregnancy stamp", T, "0x44BA06"),
        (0x544, 4, "litter", T, "0x44BA82; cleared 0x43BF85"),
        (0x548, 4, "head", P, "0x44CC00"),
        (0x54C, 4, "body", P, "0x44CC3C"),
        (0x550, 4, "personal number (name pick, skeleton and totem frame)", P, "0x44CD00; 0x44B77C"),
        (0x554, 4, "family (last name)", P, "0x44CD0F; delivery 0x43BE85"),
        (0x558, 1, "is a totem statue", T, "set only by 0x44D485"),
        (0x559, 3, "(never referenced)", T, "scan"),
        (0x55C, 4, "totem's home x", T, "0x44D277; loader 0x44B6D1"),
        (0x560, 4, "totem's home y", T, "0x44D28B"),
        (0x564, 0x19, "name", P, "0x44CD42"),
        (0x57D, 0x19, "father's name", P, "0x44CE0B"),
        (0x596, 0x19, "mother's name", P, "0x44CE17"),
        (0x5AF, 1, "(padding)", P, "scan"),
        (0x5B0, 0x10, "father's head and body, mother's head and body", P, "0x44CE3C..0x44CE5A"),
        (0x5C0, 0x19, "expected father's name", T, "conception 0x44BA35"),
        (0x5D9, 3, "(never referenced)", T, "scan"),
        (0x5DC, 4, "expected father's body", T, "0x44BA24"),
        (0x5E0, 4, "expected father's head", T, "0x44BA43"),
        (0x5E4, 4, "conception: inherited-skill selector", T, "0x44BA10"),
        (0x5E8, 4, "conception: inherited-skill value", T, "0x44BA2A"),
        (0x5EC, 4, "conception: the father's family", T, "0x44BA1A"),
        (0x5F0, 0xF8, "likes (62)", P, "0x44CAB7"),
        (0x6E8, 0xF8, "dislikes (62)", P, "0x44C998"),
        (0x7E0, 4, "current work task", T, "creator 0x44CDCE = 0"),
        (0x7E4, 0x14, "skills: Parenting, Building, Farming, Healing, Research", P, "0x44C95B"),
        (0x7F8, 4, "job preference", P, "0x44C979; UI 0x465BC4"),
        (0x7FC, 1, "Esteemed Elder", P, "totem maker 0x44D4A2; Details 0x429C1D"),
        (0x7FD, 3, "(never referenced)", T, "scan"),
    ],
    3: [
        (0xDC4, 4, "age", T, "parentage_export.c"),
        (0xDC8, 4, "sex (0 male, 1 female)", P, "0x4564A1"),
        (0xDCC, 4, "personal number (name pick)", P, "0x45C67B"),
        (0xDD0, 4, "family (last name)", P, "0x45C69E"),
        (0xDD4, 0x19, "name", P, "parentage_export.c"),
        (0xDED, 3, "(padding)", P, "scan"),
        (0xDF0, 4, "head", P, "0x4564C0"),
        (0xDF4, 4, "body (the Chief's robe is 29)", P, "0x456527; 0x45FBDE"),
        (0xDF8, 0x19, "father's name", P, "0x456629"),
        (0xE11, 0x19, "mother's name", P, "0x456637"),
        (0xE2A, 2, "(padding)", P, "scan"),
        (0xE2C, 0x10, "father's head and body, mother's head and body", P, "0x45665C..0x456676"),
        (0xE3C, 4, "conception: inherited-skill selector", T, "0x455B39"),
        (0xE40, 4, "conception: inherited-skill value", T, "0x455B55"),
        (0xE44, 4, "conception: the father's family", T, "0x455B43"),
        (0xE48, 0x18, "expected father's name", T, "0x455B6D"),
        (0xE60, 4, "(after the expected father's name)", T, "scan"),
        (0xE64, 4, "expected father's body", T, "0x455B4F"),
        (0xE68, 4, "expected father's head", T, "0x455B67"),
        (0xE6C, 4, "health block: the pending age slice", T, "block setup 0x4625D6"),
        (0xE70, 4, "health block: the clock mark", T, "0x4625E4"),
        (0xE74, 4, "processed age", T, "0x46260C"),
        (0xE78, 4, "health", T, "0x46260F; setter 0x462670"),
        (0xE7C, 4, "cause of death", T, "0x462616"),
        (0xE80, 1, "Tribal Chief", P, "set 0x45FBD0; restored only with no other Chief"),
        (0xE81, 3, "(padding)", T, "scan"),
        (0xE84, 4, "the processed age when made / made Chief (an achievement's clock)", T, "0x45FBCA; 0x462630"),
        (0xE88, 1, "robe-ceremony variant", T, "0x4219A8"),
        (0xE89, 1, "sick", T, "0x4625F4"),
        (0xE8A, 2, "(padding)", T, "scan"),
        (0xE8C, 4, "pregnancy stamp", T, "0x455B2F"),
        (0xE90, 4, "litter", T, "0x455B7C"),
        (0xE94, 1, "totem / stand-in marker", T, "0x455993; loader 0x4568A3"),
        (0xE95, 3, "(padding)", T, "scan"),
        (0xE98, 4, "totem's saved x", T, "0x4559C4"),
        (0xE9C, 4, "totem's saved y", T, "0x4559C4"),
        (0xEA0, 4, "current action", T, "0x462603"),
        (0xEA4, 1, "(set 0 by the block setup)", T, "0x462609"),
        (0xEA5, 3, "(padding)", T, "scan"),
        (0xEA8, 4, "default movement speed (30)", T, "0x46261D"),
        (0xEAC, 0x14, "skills: Farming, Parenting, Healing, Research, Building", P, "parentage_export.c"),
        (0xEC0, 4, "job preference", P, "0x456769"),
        (0xFB4, 0x0C, "likes (3)", P, "loader 0x45686B"),
        (0xFC0, 0x0C, "dislikes (3)", P, "loader 0x456887"),
    ],
}
_TREE = [
    (0x1B8C, 4, "age", T, "parentage_export.c"),
    (0x1B90, 4, "sex (0 male, 1 female)", P, "0x460990"),
    (0x1B94, 4, "personal number (name pick, skeleton frame)", P, "0x465DB5"),
    (0x1B98, 4, "family (last name)", P, "0x465DE7"),
    (0x1B9C, 0x19, "name", P, "0x45D4B2"),
    (0x1BB5, 3, "(padding)", P, "scan"),
    (0x1BB8, 4, "head", P, "0x460A10"),
    (0x1BBC, 4, "body", P, "0x460A09"),
    (0x1BC0, 0x19, "father's name", P, "parentage_export.c"),
    (0x1BD9, 0x19, "mother's name", P, "parentage_export.c"),
    (0x1BF2, 2, "(padding)", P, "scan"),
    (0x1BF4, 0x10, "father's head and body, mother's head and body", P, "parentage_export.c"),
    (0x1C04, 4, "conception: inherited-skill selector", T, "0x45E83A"),
    (0x1C08, 4, "conception: inherited-skill value", T, "0x45E856"),
    (0x1C0C, 4, "conception: the father's family", T, "0x45E844"),
    (0x1C10, 0x18, "expected father's name", T, "0x45E86E"),
    (0x1C28, 4, "(after the expected father's name)", T, "scan"),
    (0x1C2C, 4, "expected father's body", T, "0x45E850"),
    (0x1C30, 4, "expected father's head", T, "0x45E868"),
    (0x1C34, 4, "health block: the pending age slice", T, "0x46AEB6"),
    (0x1C38, 4, "health block: the clock mark", T, "0x46AEC4"),
    (0x1C3C, 4, "processed age", T, "0x46AED7"),
    (0x1C40, 4, "health", T, "0x46AEDA"),
    (0x1C44, 4, "cause of death", T, "0x46AEE1"),
    (0x1C48, 1, "sick", T, "0x46AECB"),
    (0x1C49, 3, "(padding)", T, "scan"),
    (0x1C4C, 4, "pregnancy stamp", T, "0x45E830"),
    (0x1C50, 4, "litter", T, "0x45E87D"),
    (0x1C54, 4, "the player's work assignment", T, "0x46AED4"),
    (0x1C58, 4, "default movement speed (30)", T, "0x46AEE8"),
]
FIELDS[4] = _TREE + [
    (0x1C5C, 0x14, "skills: Farming, Parenting, Healing, Research, Building (floats)", P, "parentage_export.c"),
    (0x1C70, 4, "job preference", P, "0x45DA28"),
    (0x1E60, 0x0C, "likes (3)", P, "loader 0x45DC28"),
    (0x1E6C, 0x0C, "dislikes (3)", P, "loader 0x45DC4E"),
]
FIELDS[5] = _TREE + [
    (0x1C5C, 0x18, "skills: Farming, Parenting, Healing, Research, Building, Devotion (floats)", P, "parentage_export.c"),
    (0x1C74, 4, "job preference", P, "0x46886C"),
    (0x1CEC, 1, "faction (1 Heathen): made by the game's own creator, never written raw", P, "setter 0x466880"),
    (0x1CED, 1, "orange mask selector", P, "loader 0x466BF2"),
    (0x1CEE, 1, "red mask selector", P, "loader 0x466BFB"),
    (0x1CEF, 1, "(saved; no reader but the save)", P, "0x466C05; 0x46532A"),
    (0x1CF0, 4, "Faith", P, "0x466C17"),
    (0x1CF4, 4, "Heathen cooldown deadline (clock + 7200)", T, "0x468F33"),
    (0x1CF8, 4, "(not saved: the sparkle counter)", None, "0x4729F5"),
    (0x1CFC, 4, "role: Doctor, Heathen Chief / Retired Chief, Masters, Mommy", P, "0x466C0E"),
    (0x1F5C, 0x0C, "likes (3)", P, "loader 0x466B9B"),
    (0x1F68, 0x0C, "dislikes (3)", P, "loader 0x466BC5"),
]
# Restored by their own rules, not by VV_RS_KEEP (story_revive.inc / vv_rs_apply).
OWN_RULES = {3: {0xE80}, 5: {0x1CEC}}


def _spans(name: str) -> list[tuple[int, int]]:
    text = HEADER.read_text(encoding="utf-8")
    body = re.search(r"static const vv_rs_span %s\[\] = \{(.*?)\};" % name, text, re.S).group(1)
    return [(int(a, 16), int(b, 16)) for a, b in re.findall(r"\{ (0x[0-9A-F]+), (0x[0-9A-F]+) \}", body)]


def _bytes(spans) -> set[int]:
    return {o + k for o, n in spans for k in range(n)}


def saved(game: int) -> set[int]:
    return _bytes(_spans(f"VV_RS_SAVED_{game}"))


def keep(game: int) -> set[int]:
    return _bytes(_spans(f"VV_RS_KEEP_{game}"))


class FieldTable(unittest.TestCase):
    def test_every_saved_byte_is_one_named_field(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                covered: list[int] = []
                for offset, size, _what, kind, _evidence in FIELDS[game]:
                    if kind is None:
                        continue
                    covered += range(offset, offset + size)
                self.assertEqual(len(covered), len(set(covered)), "fields overlap")
                self.assertEqual(set(covered), saved(game))

    def test_the_restored_bytes_are_exactly_the_persistent_fields(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                persistent = _bytes((o, n) for o, n, _w, kind, _e in FIELDS[game] if kind == P)
                own = {o + k for o, n, _w, kind, _e in FIELDS[game] if o in OWN_RULES.get(game, ()) for k in range(n)}
                self.assertEqual(keep(game), persistent - own)
                self.assertTrue(keep(game) <= saved(game))

    def test_each_restored_span_lies_in_one_saved_window(self):
        # vv_rs_at finds a span only inside one window of the snapshot's data.
        for game in range(1, 6):
            windows = _spans(f"VV_RS_SAVED_{game}")
            for offset, size in _spans(f"VV_RS_KEEP_{game}"):
                with self.subTest(game=game, span=hex(offset)):
                    self.assertTrue(any(o <= offset and offset + size <= o + n for o, n in windows))

    def test_age_and_health_are_never_restored(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                restored = keep(game)
                for offset, size, what, kind, _e in FIELDS[game]:
                    if what in ("age", "health", "sick", "litter", "pregnancy stamp", "processed age"):
                        self.assertEqual(kind, T)
                        self.assertFalse(set(range(offset, offset + size)) & restored, what)

    def test_the_matching_reads_the_cause_of_death_layout(self):
        text = re.sub(r"/\*.*?\*/", "", COD.read_text(encoding="utf-8"), flags=re.S)
        body = text[text.index("static struct game_records REC[6] = {"):]
        rows = re.findall(r"\{([^{}]*)\}", body[body.index("{") + 1:body.index("};")])
        header = re.sub(r"/\*.*?\*/", "", HEADER.read_text(encoding="utf-8"), flags=re.S)
        lay = header[header.index("VV_RS_LAYOUT[6] = {"):]
        lay_rows = re.findall(r"\{([^{}]*)\}", lay[lay.index("{") + 1:lay.index("};")])
        for game in range(1, 6):
            rec = [int(v.strip().rstrip("u"), 0) for v in rows[game].split(",") if v.strip()]
            ours = [int(v.strip().rstrip("u"), 0) for v in lay_rows[game].split(",") if v.strip()]
            stride, age, sex, name, name_bytes, head, body_ = ours[:7]
            with self.subTest(game=game):
                self.assertEqual((stride, age, name, sex, head, body_), (rec[3], rec[7], rec[8], rec[10], rec[16], rec[17]))
                self.assertTrue({sex, head, body_} | set(range(name, name + name_bytes)) <= keep(game))
                self.assertFalse(set(range(age, age + 4)) & keep(game))


def _image(game: int) -> bytes:
    pe = pefile.PE(str(EXES[game]))
    return pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.SizeOfImage


STACK = 0x70000000
RETURN = 0x0BAD0000
RECORD = 0x20000000
ENTRY = 0x30000000


class Loader:
    """One stock executable with its villager loader run on a record."""

    def __init__(self, game: int):
        image, size = _image(game)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (max(len(image), size) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(RETURN, 0x1000)
        self.game = game
        self.stubs = {}
        mu.hook_add(UC_HOOK_CODE, self._code)

    def _code(self, mu, address, size, user):
        stub = self.stubs.get(address)
        if stub is not None:
            stub(mu)

    def ret(self, pop: int):
        mu = self.mu
        esp = mu.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", mu.mem_read(esp, 4))[0]
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, back)

    def thiscall(self, entry: int, this: int, *args: int):
        mu = self.mu
        esp = STACK
        for arg in reversed(args):
            esp -= 4
            mu.mem_write(esp, struct.pack("<I", arg))
        esp -= 4
        mu.mem_write(esp, struct.pack("<I", RETURN))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, this)
        mu.emu_start(entry, RETURN, count=2_000_000)


def _pattern(seed: int, n: int) -> bytearray:
    return bytearray(((k * 37 + seed * 101 + 11) ^ (k >> 3) ^ seed) & 0xFF or 1 for k in range(n))


def loaded_bytes(game: int, held: dict[int, int]) -> set[int]:
    """The record bytes the game's own loader takes from a saved entry: two runs whose entries differ in every byte
    (but `held`, entry offset -> the byte both runs keep there), compared."""
    records = []
    for seed in (1, 2):
        m = Loader(game)
        mu = m.mu
        if game in (3, 4, 5):
            stride = {3: 0x1F8C, 4: 0x2E3C, 5: 0x2F44}[game]
            entry_size = {3: 0x11C, 4: 0x104, 5: 0x118}[game]
            loader = {3: 0x456830, 4: 0x45DBE0, 5: 0x466B60}[game]
            mu.mem_map(RECORD, 0x10000)
            mu.mem_map(ENTRY, 0x1000)
            entry = _pattern(seed, entry_size)
            for at, value in held.items():
                entry[at] = value
            mu.mem_write(ENTRY, bytes(entry))
            if game == 5:
                # The faction setter (0x466888..0x4668A0) stores its byte at +0x1CEC and derives two fields of its
                # own; only the faction itself is the saved entry's, so the setter is stood in for by that store.
                def setter(mu):
                    esp = mu.reg_read(UC_X86_REG_ESP)
                    value = struct.unpack("<I", mu.mem_read(esp + 4, 4))[0] & 0xFF
                    mu.mem_write(mu.reg_read(UC_X86_REG_ECX) + 0x1CEC, bytes([value]))
                    m.ret(4)
                m.stubs[0x466880] = setter
            m.thiscall(loader, RECORD, ENTRY)
            records.append(bytes(mu.mem_read(RECORD, stride)))
        elif game == 1:
            manager, state = RECORD, ENTRY
            mu.mem_map(manager, 0x40000)
            mu.mem_map(state, 0x1000)
            mu.mem_write(manager + 0x3E010, struct.pack("<I", state))
            entry = _pattern(seed, 0x98)
            mu.mem_write(state + 0x180, bytes(entry))
            mu.mem_write(state + 0x218, b"\1")
            mu.mem_write(state + 0x9C + 0x218, b"\0")
            m.thiscall(0x43B8C0, manager)
            records.append(bytes(mu.mem_read(manager, 0x3D8)))
        else:
            world, obj = RECORD, ENTRY
            mu.mem_map(world, 0xE58000)
            mu.mem_map(obj, 0x2000)
            mu.mem_write(world + 0xE574D4, struct.pack("<I", obj))
            entry = _pattern(seed, 0x2DC)
            for at, value in held.items():
                entry[at] = value
            mu.mem_write(obj + 0x218, bytes(entry[:0x2C0]))
            mu.mem_write(obj + 0x4D8, bytes(entry[0x2C0:]))
            mu.mem_write(obj + 0x4F4, b"\1")
            mu.mem_write(obj + 0x2E0 + 0x4F4, b"\0")
            m.thiscall(0x44B640, world)
            records.append(bytes(mu.mem_read(world, 0xE48C)))
    a, b = records
    return {k for k in range(len(a)) if a[k] != b[k]}


@unittest.skipUnless(HAVE_EMULATOR and all(p.is_file() for p in EXES.values()),
                     "needs unicorn, pefile and the stock executables in inputs/")
class TheGamesOwnLoaders(unittest.TestCase):
    """The windows are what each stock loader restores: no more, no less."""

    # Entry bytes both runs hold, to keep each loader on one path, and the record bytes they are (which the
    # comparison therefore cannot see and are checked by the table instead):
    #   The Lost Children: the name's last byte (its strcpy needs an end; record +0x57B) and the totem byte (+0x558:
    #   a totem's home is copied to its position);
    #   The Secret City: the totem marker (+0xE94: its position is copied the same way);
    #   The Tree of Life: health (+0x1C40: a dead body's place is worked out from it).
    HELD = {1: {}, 2: {0x57B - 0x524: 0, 0x558 - 0x524: 0}, 3: {0xD4: 0},
            4: {0xB8: 50, 0xB9: 0, 0xBA: 0, 0xBB: 0}, 5: {}}
    HELD_RECORD = {1: set(), 2: {0x57B, 0x558}, 3: {0xE94}, 4: {0x1C40, 0x1C41, 0x1C42, 0x1C43}, 5: set()}

    def test_each_loader_restores_exactly_the_saved_windows(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                got = loaded_bytes(game, self.HELD[game])
                self.assertEqual(got, saved(game) - self.HELD_RECORD[game],
                                 f"loaded but not kept: {sorted(hex(x) for x in got - saved(game))[:12]}; "
                                 f"kept but not loaded: {sorted(hex(x) for x in saved(game) - got)[:12]}")

    def test_new_believers_faction_comes_from_the_save(self):
        for value in (0, 1):
            m = Loader(5)
            mu = m.mu
            mu.mem_map(RECORD, 0x10000)
            mu.mem_map(ENTRY, 0x1000)
            entry = _pattern(3, 0x118)
            entry[1] = value
            mu.mem_write(ENTRY, bytes(entry))
            seen = []
            m.stubs[0x466880] = lambda mu: (seen.append(
                struct.unpack("<I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP) + 4, 4))[0] & 0xFF), m.ret(4))
            m.thiscall(0x466B60, RECORD, ENTRY)
            self.assertEqual(seen, [value])


if __name__ == "__main__":
    unittest.main()
