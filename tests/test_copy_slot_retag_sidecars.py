"""Copy Player Slot and Move Player Slot: every binary sidecar that keeps its slot number gets the target's.

A companion reads its slot's file only when the slot number inside it is that slot's (the readers named below).
A copy or move that left the old number in a file the companions then never read it: the data was lost in the
new slot.  These are the formats added to src/vv_copy_slot.py `_SLOT_FIELD` / `_story_graph`:

    'VFN1'  New Believers' Faith Notice waiting popup   vvfp_faith_notice.c valid_file: u[3] == the slot
    'VFK1'  New Believers' Faith Loss believers kept     vvfp_faith_loss.c valid_file: u[3] == the slot
    'VCG1'  the Story Purchases Graph (a bought run)     story_graph.inc cg_village_seen: cg_head.slot == the slot,
                                                         and cg_flush_file writes only while cg.slot is the slot

Each test copies (and moves) a slot 1 village to slot 3 and checks that the file changed only in its slot
field(s) and that the reader's own checks accept it for slot 3.  Cause of Death's Graves Logged is 'VCG1' too;
its count must never be taken for a slot.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_copy_slot as tc  # noqa: E402
import vv_copy_slot as cs  # noqa: E402
import vv_move_slot as ms  # noqa: E402

OWN = tc.OWN
GAME = 5                                  # Faith Notice and Faith Loss are New Believers' only

NOTICE = f"{OWN}\\Save {{s}}\\Data\\Faith Notice\\Waiting Popup - Save {{s}}.dat"
LOSS = f"{OWN}\\Save {{s}}\\Data\\Faith Loss\\Believers Kept - Save {{s}}.dat"
GRAPH = f"{OWN}\\Save {{s}}\\Data\\Paid Purchases\\Virtual Villagers {GAME} Story Purchases Graph - Save {{s}}.dat"
LOGGED = f"{OWN}\\Save {{s}}\\Data\\Deaths\\Virtual Villagers {GAME} Graves Logged - Save {{s}}.dat"


# ---- The files, as the companions write them -----------------------------------------------------------------

def faith_notice(slot: int) -> bytes:
    """vvfp_faith_notice.c: magic, version 2, game 5, slot, total, five reasons, n, n x (name[28], before, after)."""
    head = b"VFN1" + struct.pack("<10I", 2, 5, slot, 3, 1, 1, 1, 0, 0, 1)
    return head + b"Ana".ljust(28, b"\0") + struct.pack("<ii", 40, 0)


def faith_loss(slot: int) -> bytes:
    """vvfp_faith_loss.c: magic, version 2, game 5, slot, count, count x 6 u32."""
    return b"VFK1" + struct.pack("<4I", 2, 5, slot, 2) + struct.pack("<12I", *range(1, 13))


def story_graph(slot: int) -> bytes:
    """story_graph.inc: cg_file_head (magic, version 6, game, slot, state bytes, graph bytes, roster[256]), the
    run's state (phase, game, slot, ...), the graph."""
    state = struct.pack("<3i", 2, GAME, slot) + bytes(range(52))
    graph = b"CIEG" + bytes(range(12))
    roster = struct.pack("<256I", *range(100, 356))
    return b"VCG1" + struct.pack("<5I", 6, GAME, slot, len(state), len(graph)) + roster + state + graph


def graves_logged(count: int) -> bytes:
    """cod_backfill.inc: magic 'VCG1', version 1, game, count, count x (u16 place, u16 0, u32 fingerprint)."""
    return b"VCG1" + struct.pack("<3I", 1, GAME, count) + b"".join(
        struct.pack("<HHI", k, 0, 0xABC0 + k) for k in range(count))


# ---- The readers' checks, as the companions make them ----------------------------------------------------------

def notice_reads(data: bytes, slot: int) -> bool:
    u = struct.unpack_from(f"<{len(data) // 4}I", data[:len(data) // 4 * 4])
    return (len(data) >= 44 and data[:4] == b"VFN1" and u[1] in (1, 2) and u[2] == 5 and u[3] == slot
            and 0 < u[4] <= 0xFFFF and sum(u[5:10]) == u[4] and len(data) == 44 + 36 * u[10])


def loss_reads(data: bytes, slot: int) -> bool:
    u = struct.unpack_from("<5I", data)
    return (data[:4] == b"VFK1" and u[1] in (1, 2) and u[2] == 5 and u[3] == slot and u[4] <= 256
            and len(data) == 20 + 24 * u[4])


def graph_reads(data: bytes, slot: int) -> bool:
    version, game, head_slot, state, graph = struct.unpack_from("<5I", data, 4)
    phase, state_game, state_slot = struct.unpack_from("<3i", data, cs._GRAPH_HEAD)
    return (data[:4] == b"VCG1" and game == GAME and head_slot == slot and state_game == GAME and phase != 0
            and len(data) == cs._GRAPH_HEAD + state + graph
            and state_slot == slot)            # cg_flush_file: the run is written back only for its own slot


def changed_offsets(before: bytes, after: bytes) -> list[int]:
    assert len(before) == len(after)
    return [k for k in range(len(before)) if before[k] != after[k]]


FORMATS = [
    ("Faith Notice", NOTICE, faith_notice, notice_reads, [12]),
    ("Faith Loss", LOSS, faith_loss, loss_reads, [12]),
    ("Story Purchases Graph", GRAPH, story_graph, graph_reads, [12, cs._GRAPH_STATE_SLOT]),
]


class TransformTests(unittest.TestCase):
    def test_each_format_gets_only_its_slot_fields_changed(self) -> None:
        for name, _path, make, reads, fields in FORMATS:
            with self.subTest(format=name):
                source = make(1)
                self.assertTrue(reads(source, 1))
                out = cs.transform_binary(source, 1, 3, {}, "A", "B")
                self.assertTrue(reads(out, 3), name)
                self.assertFalse(reads(out, 1), name)
                self.assertEqual(changed_offsets(source, out), fields)
                for at in fields:
                    self.assertEqual(struct.unpack_from("<I", out, at)[0], 3)
                self.assertEqual(out, make(3))

    def test_another_slots_file_is_left_as_it_is(self) -> None:
        for name, _path, make, _reads, _fields in FORMATS:
            with self.subTest(format=name):
                data = make(2)
                self.assertEqual(cs.transform_binary(data, 1, 3, {}, "A", "B"), data)

    def test_a_graph_whose_two_slots_disagree_or_that_is_not_whole_is_left_as_it_is(self) -> None:
        data = bytearray(story_graph(1))
        struct.pack_into("<I", data, cs._GRAPH_STATE_SLOT, 2)
        self.assertEqual(cs.transform_binary(bytes(data), 1, 3, {}, "A", "B"), bytes(data))
        whole = story_graph(1)
        for cut in (whole[:-1], whole + b"\0", whole[:cs._GRAPH_HEAD]):
            self.assertEqual(cs.transform_binary(cut, 1, 3, {}, "A", "B"), cut)

    def test_graves_logged_shares_the_magic_and_its_count_is_never_a_slot(self) -> None:
        for count in range(0, 6):
            with self.subTest(count=count):
                data = graves_logged(count)
                self.assertEqual(cs.transform_binary(data, 1, 3, {}, "A", "B"), data)
                self.assertEqual(cs.transform_binary(data, count or 1, 3, {}, "A", "B"), data)


class CopyAndMoveTests(tc.Base):
    def _place(self, folder: Path, slot: int) -> dict[str, bytes]:
        files = {path.format(s=slot): make(slot) for _n, path, make, _r, _f in FORMATS}
        files[LOGGED.format(s=slot)] = graves_logged(slot)          # its count is the slot's number
        for rel, data in files.items():
            self.put(folder, rel, data)
        return files

    def _check(self, folder: Path) -> None:
        for name, path, make, reads, fields in FORMATS:
            with self.subTest(format=name):
                copied = (folder / path.format(s=3)).read_bytes()
                self.assertTrue(reads(copied, 3), name)
                self.assertEqual(changed_offsets(make(1), copied), fields)
        self.assertEqual((folder / LOGGED.format(s=3)).read_bytes(), graves_logged(1))

    def test_copy_player_slot(self) -> None:
        game, folder, _old = self.make("huttest", GAME, "Modded")
        before = self._place(folder, 1)
        cs.copy_slot(game, folder, 1, 3, "Copied Tribe", processes=tc.FakeProcesses(), now=tc.NOW)
        self._check(folder)
        for rel, data in before.items():
            self.assertEqual((folder / rel).read_bytes(), data, rel)       # the source's files untouched

    def test_move_player_slot(self) -> None:
        game, folder, _old = self.make("huttest", GAME, "Modded")
        self._place(folder, 1)
        ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=tc.NOW)
        self._check(folder)
        for _n, path, _m, _r, _f in FORMATS:
            self.assertFalse((folder / path.format(s=1)).exists())


if __name__ == "__main__":
    unittest.main()
