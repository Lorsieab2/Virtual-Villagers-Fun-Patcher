"""Repair Saves & Logs makes revival snapshots afterwards (the owner, 2026-11-26), all five games.

src/vv_revive_backfill.py turns a villager's saved entry -- a stale copy still in the slot's save, or their entry in
an older save of the village -- into the snapshot "VVFP Cause of Death.dll" would have kept (native/shared/
revive_snapshot.h).  Proven here:

* the map from a saved entry to the snapshot's data is each game's OWN loader's: the real loader of each stock
  executable (inputs/, Unicorn) turns an entry into a record, and the record's saved windows are exactly what
  entry_to_data gives;
* the file the module writes is the one the DLLs read (the same layout and checksum, read back by parse);
* who is who: the departed of the logs matched by name, sex, looks, likes and dislikes and an age no older than at
  death; a record slot reused by someone else is never taken for them; two different entries that could be the
  same person make none; a person with a snapshot (a capture or an earlier backfill) gets no other; the newest
  source (the oldest age) is taken, exact for the later fields only when it is a body's copy;
* idempotent: a second run changes nothing; a file the DLL would not read is never written over.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_revive_backfill as rb  # noqa: E402
from test_revive_snapshot_windows import (  # noqa: E402
    ENTRY as EMU_ENTRY, EXES, HAVE_EMULATOR, RECORD, Loader, _pattern,
)

STRIDE = {1: 0x3D8, 2: 0xE48C, 3: 0x1F8C, 4: 0x2E3C, 5: 0x2F44}


def load_entry(game: int, entry: bytes) -> bytes:
    """The record the game's own loader makes of one saved entry."""
    m = Loader(game)
    mu = m.mu
    if game in (3, 4, 5):
        loader = {3: 0x456830, 4: 0x45DBE0, 5: 0x466B60}[game]
        mu.mem_map(RECORD, 0x10000)
        mu.mem_map(EMU_ENTRY, 0x1000)
        mu.mem_write(EMU_ENTRY, entry)
        if game == 5:
            def setter(mu):
                esp = mu.reg_read(m_esp())
                value = struct.unpack("<I", mu.mem_read(esp + 4, 4))[0] & 0xFF
                mu.mem_write(mu.reg_read(m_ecx()) + 0x1CEC, bytes([value]))
                m.ret(4)
            m.stubs[0x466880] = setter
        m.thiscall(loader, RECORD, EMU_ENTRY)
        return bytes(mu.mem_read(RECORD, STRIDE[game]))
    if game == 1:
        mu.mem_map(RECORD, 0x40000)
        mu.mem_map(EMU_ENTRY, 0x1000)
        mu.mem_write(RECORD + 0x3E010, struct.pack("<I", EMU_ENTRY))
        mu.mem_write(EMU_ENTRY + 0x180, entry[:0x98])
        mu.mem_write(EMU_ENTRY + 0x218, b"\1")
        m.thiscall(0x43B8C0, RECORD)
        return bytes(mu.mem_read(RECORD, 0x3D8))
    mu.mem_map(RECORD, 0xE58000)
    mu.mem_map(EMU_ENTRY, 0x2000)
    mu.mem_write(RECORD + 0xE574D4, struct.pack("<I", EMU_ENTRY))
    mu.mem_write(EMU_ENTRY + 0x218, entry[:0x2C0])
    mu.mem_write(EMU_ENTRY + 0x4D8, entry[0x2C0:0x2DC])
    mu.mem_write(EMU_ENTRY + 0x4F4, b"\1")
    m.thiscall(0x44B640, RECORD)
    return bytes(mu.mem_read(RECORD, 0xE48C))


def m_esp():
    from unicorn.x86_const import UC_X86_REG_ESP
    return UC_X86_REG_ESP


def m_ecx():
    from unicorn.x86_const import UC_X86_REG_ECX
    return UC_X86_REG_ECX


def windows(game: int, record: bytes) -> bytes:
    return b"".join(record[o:o + n] for o, n in rb.SAVED[game])


@unittest.skipUnless(HAVE_EMULATOR and all(p.is_file() for p in EXES.values()),
                     "needs unicorn, pefile and the stock executables in inputs/")
class TheGamesOwnLoaderIsTheMap(unittest.TestCase):
    def test_a_saved_entry_becomes_exactly_the_record_windows(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                entry = _pattern(game + 5, rb.ENTRY_BYTES[game])
                if game == 2:
                    entry[0x57B - 0x524] = 0          # the name's end (the loader's strcpy)
                    entry[0x558 - 0x524] = 0          # not a totem statue
                if game == 3:
                    entry[0xD4] = 0                   # not a totem marker
                if game == 4:
                    entry[0xB8:0xBC] = struct.pack("<i", 50)   # alive (a body's place is worked out)
                record = load_entry(game, bytes(entry))
                self.assertEqual(rb.entry_to_data(game, bytes(entry)), windows(game, record))


# ---- the rules, over made-up sources and logs -----------------------------------------------------------

def record_for(game, name, sex, head, body, likes, dislikes, age, seed=1, father="", mother=""):
    """A record whose every saved byte is set, with these identity fields (the snapshot's data of it)."""
    age_at, sex_at, name_at, cap, head_at, body_at, likes_at, dislikes_at, slots, father_at, mother_at = rb.LAYOUT[game]
    r = bytearray(((k * 29 + seed * 53) & 0x7F) | 1 for k in range(STRIDE[game]))
    r[name_at:name_at + cap] = name.encode().ljust(cap, b"\0")
    struct.pack_into("<i", r, sex_at, sex)
    struct.pack_into("<i", r, head_at, head)
    struct.pack_into("<i", r, body_at, body)
    struct.pack_into("<i", r, age_at, age)
    struct.pack_into(f"<{slots}i", r, likes_at, *(list(likes) + [-1] * (slots - len(likes))))
    struct.pack_into(f"<{slots}i", r, dislikes_at, *(list(dislikes) + [-1] * (slots - len(dislikes))))
    if father_at:
        r[father_at:father_at + 0x19] = father.encode().ljust(0x19, b"\0")
        r[mother_at:mother_at + 0x19] = mother.encode().ljust(0x19, b"\0")
    return windows(game, bytes(r))


def death_block(name, sex, age, head, body, likes, dislikes, heading="Death 1", father="", mother=""):
    values = {"Sex": sex, "Age at death": str(age), "Likes": likes, "Dislikes": dislikes}
    sub = {"Father": father, "Mother": mother}
    return SimpleNamespace(identity=(name, head, body), heading=heading,
                           value=lambda key, indent="  ": (sub if indent == "    " else values).get(key))


class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_backfill(self, game, blocks, srcs):
        target = self.folder / f"Revive Snapshots - {game}.dat"
        with mock.patch("vv_log_additions.person_blocks", return_value=blocks), \
                mock.patch("vv_revive_backfill.sources", return_value=srcs), \
                mock.patch("vv_revive_backfill.path", return_value=target):
            return rb.backfill(self.folder, game, 1), target

    def test_each_game(self):
        for game in range(1, 6):
            male, female = rb.SEX_VALUES[game]
            with self.subTest(game=game):
                # Ana died at 1300; the save still holds her body's copy (age 1300).  Kai vanished at 500; only a
                # backup (age 400) holds him.  Their record slot was reused by Mira (alive, other looks).
                ana = record_for(game, "Ana Rua", female, 5, 6, (0, 5), (17,), 1300, seed=1, father="Tano Rua")
                kai_old = record_for(game, "Kai Moana", male, 11, 12, (), (1,), 400, seed=2)
                kai_older = record_for(game, "Kai Moana", male, 11, 12, (), (1,), 200, seed=3)
                mira = record_for(game, "Mira Tane", female, 7, 8, (2,), (), 900, seed=4)
                namesake = record_for(game, "Ana Rua", female, 5, 6, (3,), (17,), 1000, seed=5)   # other likes
                srcs = [rb.Source(rb.FROM_SAVE, 133_000_000_000_000_000, "the save", [mira, ana, namesake]),
                        rb.Source(rb.FROM_BACKUP, 132_000_000_000_000_000, "backup A", [kai_old, mira]),
                        rb.Source(rb.FROM_BACKUP, 131_000_000_000_000_000, "backup B", [kai_older])]
                from vv_lost_titles import PREFERENCES
                w = PREFERENCES[game]
                blocks = [death_block("Ana Rua", "Female", 1300, 5, 6, f"{w[0]}, {w[5]}", w[17], father="Tano Rua"),
                          death_block("Kai Moana", "Male", 500, 11, 12, "(none)", w[1], heading="Disappeared")]
                result, target = self.run_backfill(game, blocks, srcs)
                self.assertTrue(result.written)
                self.assertEqual(sorted(result.made), ["Ana Rua: the save", "Kai Moana: backup A"])
                raw = target.read_bytes()
                snaps = rb.parse(raw, game)
                self.assertIsNotNone(snaps)
                by = {s.identity()[0]: s for s in snaps}
                self.assertEqual(by["Ana Rua"].data, ana)                 # byte for byte, not the namesake
                self.assertEqual((by["Ana Rua"].source, by["Ana Rua"].exact),
                                 (rb.FROM_SAVE, rb.EXACT_IDENTITY | rb.EXACT_LATER))   # her body's copy
                self.assertEqual(by["Kai Moana"].data, kai_old)           # the newest source, not the older one
                self.assertEqual((by["Kai Moana"].source, by["Kai Moana"].exact), (rb.FROM_BACKUP, rb.EXACT_IDENTITY))
                self.assertEqual(len(snaps), 2)                           # Mira (alive) is nobody's
                # idempotent: nothing more, the file as it was
                again, _ = self.run_backfill(game, blocks, srcs)
                self.assertFalse(again.written)
                self.assertEqual(target.read_bytes(), raw)

    def test_two_different_entries_that_could_be_them_make_none(self):
        for game in range(1, 6):
            male, _female = rb.SEX_VALUES[game]
            with self.subTest(game=game):
                one = record_for(game, "Kai Moana", male, 11, 12, (), (), 400, seed=2)
                two = record_for(game, "Kai Moana", male, 11, 12, (), (), 400, seed=7)
                srcs = [rb.Source(rb.FROM_BACKUP, 1, "backup", [one, two])]
                result, target = self.run_backfill(
                    game, [death_block("Kai Moana", "Male", 500, 11, 12, "(none)", "(none)")], srcs)
                self.assertEqual((result.made, result.unsure, target.exists()), ([], ["Kai Moana"], False))

    def test_a_captured_snapshot_is_never_backfilled_over(self):
        for game in range(1, 6):
            _male, female = rb.SEX_VALUES[game]
            with self.subTest(game=game):
                ana = record_for(game, "Ana Rua", female, 5, 6, (), (), 1300, seed=1)
                target = self.folder / f"Revive Snapshots - {game}.dat"
                target.write_bytes(rb.build(game, [rb.Snapshot(game, ana)]))   # a capture at her death
                before = target.read_bytes()
                older = record_for(game, "Ana Rua", female, 5, 6, (), (), 1000, seed=9)
                result, _ = self.run_backfill(
                    game, [death_block("Ana Rua", "Female", 1300, 5, 6, "(none)", "(none)")],
                    [rb.Source(rb.FROM_BACKUP, 1, "backup", [older])])
                self.assertFalse(result.written)
                self.assertEqual(target.read_bytes(), before)

    def test_a_file_the_dll_would_not_read_is_never_written_over(self):
        game = 3
        target = self.folder / f"Revive Snapshots - {game}.dat"
        target.write_bytes(b"not a snapshot file")
        ana = record_for(game, "Ana Rua", 1, 5, 6, (), (), 1300)
        result, _ = self.run_backfill(game, [death_block("Ana Rua", "Female", 1300, 5, 6, "(none)", "(none)")],
                                      [rb.Source(rb.FROM_SAVE, 1, "the save", [ana])])
        self.assertFalse(result.written)
        self.assertIn("not one this version reads", result.note)
        self.assertEqual(target.read_bytes(), b"not a snapshot file")

    def test_head_0_body_0_and_age_0_are_valid_values(self):
        # Codex, PR #880: `x or -1` read a valid 0 as missing and dropped the entry.  The owner's rule: zero appearance
        # (and dead parents) are valid.  In every game's plausibility test, in a stale entry read from a save, and in a
        # backup the backfill matches.
        import vv_log_tools as tools
        for game in range(1, 6):
            male, female = rb.SEX_VALUES[game]
            with self.subTest(game=game):
                zero = record_for(game, "Zero Looks", female, 0, 0, (), (), 0, seed=3)
                self.assertTrue(rb._plausible(game, zero))
                result, target = self.run_backfill(
                    game, [death_block("Zero Looks", "Female", 0, 0, 0, "(none)", "(none)")],
                    [rb.Source(rb.FROM_BACKUP, 1, "backup", [zero])])
                self.assertEqual(result.made, ["Zero Looks: backup"])
                snaps = rb.parse(target.read_bytes(), game)
                self.assertEqual(snaps[0].data, zero)
                self.assertEqual(snaps[0].identity()[2:4], (0, 0))
        # A New Home's save, read as the game lays it out: entry i at VV1_BLOCK0 + i * VV1_STRIDE, the entry the
        # snapshot's data byte for byte; a stale copy (its flag not 1) with head 0, body 0 and age 0 is kept.
        checker = tools.load_checker()
        save = bytearray(checker.VV1_BLOCK0 + 256 * checker.VV1_STRIDE)
        zero = record_for(1, "Zero Looks", 2, 0, 0, (), (), 0, seed=3)
        at = checker.VV1_BLOCK0 + 3 * checker.VV1_STRIDE
        save[at:at + 0x98] = zero
        self.assertIn(zero, rb.save_entries(1, bytes(save)))
    def test_the_file_layout_is_the_dlls(self):
        header = (ROOT / "native" / "shared" / "revive_snapshot.h").read_text(encoding="utf-8")
        self.assertIn("#define VV_RS_MAGIC 0x31535256u", header)
        self.assertIn("#define VV_RS_MAX 2048", header)
        self.assertIn("#define VV_RS_DATA_MAX 0x300u", header)
        self.assertEqual(rb.ENTRY, 908)
        self.assertIn("approve_repair", (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8"))
        self.assertIn("vv_revive_backfill.backfill(folder, game, slot)",
                      (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
