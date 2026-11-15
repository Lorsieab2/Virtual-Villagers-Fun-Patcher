"""The Living Event Engine at run time (native/vvfp_story_upgrades/story_living.inc) against its contract
docs/event-collection/living-pack.md.

EMULATED (unicorn, each game's executable as the patcher renders it, the TEST build of "VVFP Story Upgrades.dll";
tests/story_emulator.py), in all five games, with the fixture packs tests/data/living_fixture/vvN.pak:

  * THE ORDER: lv_order gives the same variants in the same order as its Python twin vv_living_mixer.lv_order, for
    every seed of every fixture pack, fresh and with a history read from a VLEH file, under the same rolls;
  * THE DRAW: a living row armed by the rare roll is a variant of its seed queued through cg_queue_origin (STRICT);
    a variant that cannot be cast is passed over for the next (STRICT CASTING FALLBACK); a seed none of whose
    variants casts is not possible now;
  * RECENCY: a seed among the last W armed (W = living rows / 3) is left out of the draw;
  * MOODS: the least-seen mood's series weigh LV_MOOD_BOOST, as History.mood_weights says;
  * THE HISTORY FILE: written at each arm (VLEH v1, its crc, the pack's crc), read back after a restart, a damaged,
    foreign-pack or other-village file is a fresh history, Start Over (VvfpStoryVillageReset) deletes it;
  * THE FINISH: a living event played to its end counts the archetype of its last page (the pack's outcome
    records), and nothing else;
  * PICK ISLAND EVENT AND THE LIBRARY: a living row is possible when any variant casts (STRICT); the library's own
    cast (PREFER) chooses and records a variant.

The live game is NOT exercised here.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_living_mixer as mx  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime import DONE, IDLE
    from test_story_cie_graph_runtime_v6 import V6 as Run
    from unicorn import UC_HOOK_CODE

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
ORIGIN_PURCHASE, ORIGIN_PICK, ORIGIN_NATURAL = 0, 1, 2
CAST_STRICT, CAST_PREFER = 0, 1
FAMILIES = 128
HEAD = 48
COUNTS_AT = HEAD + 2 * mx.RING
VV3_MANAGER_GLOBAL, VV3_QUEUE_ARM_ISLAND = 0x4B309C, 0x6DF340    # story_tables.h


def pack_bytes(game: int) -> bytes:
    return (mx.FIXTURE / f"vv{game}.pak").read_bytes()


def manifest_text(game: int) -> str:
    return (mx.FIXTURE / f"vv{game}_manifest.txt").read_text(encoding="ascii")


# ---- VLEH v1 in Python (the tests' reading and writing of the engine's file) ------------------------------------


def vleh_read(data: bytes, pack: dict) -> dict:
    """The file's fields and counts (living-pack.md 3)."""
    (magic, version, head, total, crc, pack_crc, sig, used, at, s, v, r, a, l, _z, armed,
     _z2) = struct.unpack_from("<4sHHIIIIHHHHHHHHII", data, 0)
    assert magic == b"VLEH" and version == 1 and head == HEAD and total == len(data)
    assert zlib.crc32(data[:12] + b"\0\0\0\0" + data[16:]) & 0xFFFFFFFF == crc
    ring = list(struct.unpack_from(f"<{mx.RING}H", data, HEAD))
    n = r * r + l + FAMILIES + a + v
    counts = list(struct.unpack_from(f"<{n}H", data, COUNTS_AT))
    assert total == COUNTS_AT + 2 * n
    newest_last = [ring[(at - 1 - k) % mx.RING] for k in range(used - 1, -1, -1)]
    return {"pack_crc": pack_crc, "sig": sig, "used": used, "head": at, "armed": armed, "ring": newest_last,
            "pair": counts[:r * r], "lens": counts[r * r:r * r + l],
            "family": counts[r * r + l:r * r + l + FAMILIES],
            "arc": counts[r * r + l + FAMILIES:r * r + l + FAMILIES + a],
            "var": counts[r * r + l + FAMILIES + a:], "seeds": s, "variants": v}


def vleh_write(h: mx.History, pack: dict, sig: int, pack_crc: int | None = None) -> bytes:
    """A VLEH v1 file holding the twin's history `h` for `pack` (the ring newest last)."""
    r, a, l, v = pack["roles"], pack["archetypes"], pack["lenses"], len(pack["variants"])
    ring = [mx.NONE16] * mx.RING
    for k, s in enumerate(h.ring[-mx.RING:]):
        ring[k] = s
    used = len(h.ring[-mx.RING:])
    counts = [0] * (r * r + l + FAMILIES + a + v)
    for key, n in h.pair.items():
        counts[key] = n
    for i, n in h.lens.items():
        counts[r * r + i] = n
    for i, n in h.family.items():
        counts[r * r + l + i] = n
    for i, n in h.arc.items():
        counts[r * r + l + FAMILIES + i] = n
    for i, n in h.var.items():
        counts[r * r + l + FAMILIES + a + i] = n
    total = COUNTS_AT + 2 * len(counts)
    body = (struct.pack("<4sHHIIIIHHHHHHHHII", b"VLEH", 1, HEAD, total, 0,
                        pack["crc"] if pack_crc is None else pack_crc, sig, used, used % mx.RING,
                        len(pack["seeds"]), v, r, a, l, 0, used, 0)
            + struct.pack(f"<{mx.RING}H", *ring) + struct.pack(f"<{len(counts)}H", *counts))
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return body[:12] + struct.pack("<I", crc) + body[16:]


if HAVE_EMULATOR:
    class Living(Run):
        """One game's process with a village of four adults (Run's), the fixture pack and the probes."""

        def __init__(self, game: str, people=None):
            super().__init__(game) if people is None else super().__init__(game, people)
            self.data = pack_bytes(self.n)
            self.pack = mx.read_pack(self.data)
            self.at = self.p.alloc(len(self.data) + 16)
            self.p.write(self.at, self.data)
            self.buf = self.p.alloc(0x40000)
            self.ids = {s["id"]: i for i, s in enumerate(self.pack["seeds"])}
            self.p.export("VvfpStoryProbeLivingPack", self.at, len(self.data))
            # Casting draws many rolls: after the given ones every roll is 0 (never the game's own routine, whose
            # C runtime this emulation does not run).
            self.p.export("VvfpStoryProbeSetRollTail", 0)
            if game == "vv3" and self.p.u32(VV3_MANAGER_GLOBAL) == 0:
                # The Secret City makes an island event due through its manager's own helper (vv3_arm): a manager
                # stands in, and the helper is stubbed (fastcall, nothing on the stack).
                self.p.put32(VV3_MANAGER_GLOBAL, self.p.alloc(0x20000))
                self.p.stub(VV3_QUEUE_ARM_ISLAND, lambda q: (0, 0))
                self.p.mu.hook_add(UC_HOOK_CODE, self.p._on_code, begin=VV3_QUEUE_ARM_ISLAND,
                                   end=VV3_QUEUE_ARM_ISLAND)

        def big(self, name: str, *args: int) -> int:
            """An export whose casting tries many villagers and variants: past the emulator's default cap."""
            return self.p.call(self.p.exports[name], list(args), limit=200_000_000)

        def text(self, s: str) -> int:
            at = self.p.alloc(len(s) + 1)
            self.p.write(at, s.encode("ascii") + b"\0")
            return at

        def order(self, seed: int) -> list[int]:
            n = self.big("VvfpStoryProbeLivingOrder", self.n, seed, self.buf, 64)
            assert n >= 0
            return [self.p.u32(self.buf + 4 * k) for k in range(n)]

        def arm(self, sid: str, origin: int = ORIGIN_NATURAL, cast: int = CAST_STRICT) -> int:
            got = self.big("VvfpStoryProbeLivingArm", self.n, self.text(sid), origin, cast)
            return got - (1 << 32) if got >> 31 else got

        def file(self) -> bytes:
            size = self.p.export("VvfpStoryProbeLivingFile", 0, 0)
            if size <= 0:
                return b""
            self.p.export("VvfpStoryProbeLivingFile", self.buf, size)
            return self.p.read(self.buf, size)

        def set_file(self, data: bytes) -> None:
            self.p.write(self.buf, data)
            self.p.export("VvfpStoryProbeLivingSetFile", self.buf, len(data))

        def living_state(self) -> dict:
            assert self.big("VvfpStoryProbeLivingState", self.n, self.buf) == 0
            v = struct.unpack("<8i", self.p.read(self.buf, 32))
            return {"used": v[0], "head": v[1], "armed": v[2], "sig": v[3] & 0xFFFFFFFF, "moods": list(v[4:7]),
                    "left_out": v[7]}

        def manifest(self) -> None:
            text = manifest_text(self.n)
            at = self.p.alloc(len(text) + 1)
            self.p.write(at, text.encode("ascii") + b"\0")
            self.p.export("VvfpStoryProbeCollectionManifest", at, 0, 0)

        def choose(self) -> tuple[bool, list[int]]:
            got = self.big("VvfpStoryProbeCollectionChoose", self.n, self.buf, 64)
            return bool(got & 0x100), [self.p.u32(self.buf + 4 * k) & 0xFFFF for k in range(got & 0xFF)]

        def idle(self) -> None:
            """The run queued by an arm undone (the next arm needs an idle engine), as a fresh session."""
            self.p.export("VvfpStoryProbeGraphSession", 0, 0)


class Rolls:
    """The rolls the test gives the engine (VvfpStoryProbeSetRolls), as the twin's random_below draws them."""

    def __init__(self, values: list[int]):
        self.values = list(values)
        self.next = 0

    def __call__(self, n: int) -> int:
        r = self.values[self.next] % n
        self.next += 1
        return r


def each_game():
    for game in GAMES:
        if have_stock(game):
            yield game


@emulated
class TheOrderMatchesItsTwin(unittest.TestCase):
    def test_fresh_and_read_histories(self) -> None:
        rng = random.Random(97)
        for game in each_game():
            run = Living(game)
            sig = run.living_state()["sig"]
            pack = run.pack
            moods = [s["mood"] for s in pack["seeds"]]
            self.assertTrue(all(m in (0, 1, 2) for m in moods))
            for trial in range(4):
                h = mx.History(pack["roles"], pack["archetypes"], pack["lenses"], len(pack["variants"]))
                for _ in range(trial * 3):                 # trial 0: a fresh history
                    vi = rng.randrange(len(pack["variants"]))
                    h.armed(pack["variants"][vi]["seed"], pack["variants"][vi], vi)
                if trial:
                    run.set_file(vleh_write(h, pack, sig))
                else:
                    run.set_file(b"")
                for si, seed in enumerate(pack["seeds"]):
                    values = [rng.randrange(1 << 20) for _ in range(16)]
                    run.rolls(values)
                    native = run.order(si)
                    vs = pack["variants"][seed["first"]:seed["first"] + seed["count"]]
                    twin = mx.lv_order(vs, seed["first"], h, Rolls(values))
                    with self.subTest(game=game, trial=trial, seed=seed["id"]):
                        self.assertEqual(native, twin)


@emulated
class TheDraw(unittest.TestCase):
    def test_strict_casting_falls_back_to_the_next_variant(self) -> None:
        """Personal Expression's first variant needs Healing 50 and Research 50 (nobody has them): the next is
        queued."""
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                seed = run.ids["living_le_per_01"]
                first = run.pack["seeds"][seed]["first"]
                run.rolls([0] * 64)                         # the order: pack order
                order = run.order(seed)
                self.assertEqual(order[0], first)
                run.rolls([0] * 64)
                got = run.arm("living_le_per_01")
                self.assertNotEqual(got, first)            # k = 0 cannot be cast ...
                self.assertIn(got, order[1:])              # ... a later one in the order is queued
                self.assertNotIn(run.state()["phase"], (IDLE, DONE))
                h = vleh_read(run.file(), run.pack)
                self.assertEqual(h["ring"], [seed])
                self.assertEqual(h["var"][got], 1)
                self.assertEqual(sum(h["var"]), 1)

    def test_a_seed_none_of_whose_variants_casts(self) -> None:
        """Art, Knowledge, and Craft's variants here need a skill, the chief or Devotion: four adults (no skills)
        have none of them."""
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                self.assertEqual(run.arm("living_le_art_05"), -1)
                self.assertEqual(run.file(), b"")          # nothing recorded
                self.assertIn(run.state()["phase"], (IDLE, DONE))

    def test_the_rare_roll_arms_a_living_row(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                run.manifest()
                # The series (per, cel, art, odd, tra): roll 0 the first, Personal Expression; then its order.
                run.rolls([0] * 64)
                armed, trace = run.choose()
                self.assertTrue(armed)
                self.assertEqual(trace, [0])
                h = vleh_read(run.file(), run.pack)
                self.assertEqual(h["ring"], [run.ids["living_le_per_01"]])


@emulated
class Recency(unittest.TestCase):
    def test_the_last_w_seeds_are_left_out(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                run.manifest()
                self.assertEqual(run.living_state()["left_out"], 0)
                run.rolls([0] * 64)
                self.assertGreaterEqual(run.arm("living_le_per_01"), 0)
                run.idle()
                st = run.living_state()                  # six living rows: W = 2
                self.assertEqual((st["used"], st["armed"], st["left_out"]), (1, 1, 1))
                # The draw: Personal Expression (row 0) is out; roll 0 is now Celebration and Play's series (row
                # 1, which nobody can cast here), then the next draw's roll 0 the Art row.
                run.rolls([0] * 64)
                armed, trace = run.choose()
                self.assertTrue(armed)
                self.assertNotIn(0, trace)
                self.assertEqual(trace[:2], [1, 2])

    def test_the_window_moves_on(self) -> None:
        run = Living("vv4")
        run.manifest()
        for sid in ("living_le_per_01", "living_mc_tra_08", "living_mc_tra_13"):
            run.rolls([0] * 64)
            self.assertGreaterEqual(run.arm(sid), 0, sid)
            run.idle()
        st = run.living_state()
        self.assertEqual(st["used"], 3)
        self.assertEqual(st["left_out"], 2)              # W = 2: the two TRA rows; Personal Expression is back


@emulated
class Moods(unittest.TestCase):
    def test_the_least_seen_mood_weighs_more(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                run.manifest()
                self.assertEqual(run.living_state()["moods"], [1, 1, 1])
                run.rolls([0] * 64)
                self.assertGreaterEqual(run.arm("living_le_per_01"), 0)   # warm
                run.idle()
                self.assertEqual(run.living_state()["moods"], [1, mx.MOOD_BOOST, mx.MOOD_BOOST])
                run.rolls([0] * 64)
                self.assertGreaterEqual(run.arm("living_mc_tra_13"), 0)   # serious
                run.idle()
                self.assertEqual(run.living_state()["moods"], [1, mx.MOOD_BOOST, 1])
                # The twin agrees on the same ring.
                h = mx.History(30, 38, 15, len(run.pack["variants"]))
                h.ring = vleh_read(run.file(), run.pack)["ring"]
                self.assertEqual(h.mood_weights([s["mood"] for s in run.pack["seeds"]]), [1, mx.MOOD_BOOST, 1])

    def test_the_boost_steers_the_draw(self) -> None:
        """After a warm and a serious arm (both left out: W = 2), the series left are Celebration (warm, 1), Art
        (social, 2), Oddities (warm, 1) and the TRA series (serious, 1 -- one of its rows is out): rolls 1 and 2 are
        both Art, roll 3 Oddities, roll 4 the TRA row left."""
        run = Living("vv4")
        run.manifest()
        for sid in ("living_le_per_01", "living_mc_tra_13"):
            run.rolls([0] * 64)
            self.assertGreaterEqual(run.arm(sid), 0)
            run.idle()
        for roll in (1, 2):
            run.rolls([roll] + [0] * 63)
            armed, trace = run.choose()
            self.assertEqual(trace[0], 2, roll)          # living_le_art_05
            run.idle()
        run.rolls([3] + [0] * 63)
        armed, trace = run.choose()
        self.assertEqual(trace[0], 3)                    # living_le_odd_03
        run.idle()
        run.rolls([4] + [0] * 63)
        armed, trace = run.choose()
        self.assertEqual(trace[0], 4)                    # the TRA series: its row left (tra_08)


@emulated
class TheHistoryFile(unittest.TestCase):
    def armed(self, game: str = "vv4") -> Living:
        run = Living(game)
        run.manifest()
        run.rolls([0] * 64)
        self.assertGreaterEqual(run.arm("living_le_per_01"), 0)
        run.idle()
        return run

    def test_written_at_each_arm(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = self.armed(game)
                h = vleh_read(run.file(), run.pack)
                self.assertEqual(h["pack_crc"], run.pack["crc"])
                self.assertEqual(h["sig"], run.living_state()["sig"])
                self.assertNotEqual(h["sig"], 0)
                self.assertEqual((h["used"], h["head"], h["armed"]), (1, 1, 1))
                self.assertEqual((h["seeds"], h["variants"]), (len(run.pack["seeds"]), len(run.pack["variants"])))

    def test_read_back_after_a_restart(self) -> None:
        run = self.armed()
        run.p.export("VvfpStoryProbeLivingForget")
        self.assertEqual(run.living_state()["used"], 1)

    def test_a_damaged_file_is_a_fresh_history(self) -> None:
        run = self.armed()
        data = bytearray(run.file())
        data[HEAD] ^= 1                                   # the ring's first entry: the crc no longer holds
        run.set_file(bytes(data))
        self.assertEqual(run.living_state()["used"], 0)
        run.set_file(run.file()[:100])                    # short
        self.assertEqual(run.living_state()["used"], 0)

    def test_another_packs_file_is_a_fresh_history(self) -> None:
        run = self.armed()
        h = mx.History(30, 38, 15, len(run.pack["variants"]))
        h.ring = [0]
        sig = run.living_state()["sig"]
        run.set_file(vleh_write(h, run.pack, sig))
        self.assertEqual(run.living_state()["used"], 1)   # the twin's file, this pack: read
        run.set_file(vleh_write(h, run.pack, sig, pack_crc=run.pack["crc"] ^ 1))
        self.assertEqual(run.living_state()["used"], 0)

    def test_another_villages_file_is_a_fresh_history(self) -> None:
        run = self.armed()
        data = run.file()
        run.reset([(0, "f", 33, "Ona"), (1, "m", 34, "Pim"), (2, "f", 45, "Qua"), (3, "m", 29, "Rex")])
        run.set_file(data)
        self.assertEqual(run.living_state()["used"], 0)

    def test_start_over_deletes_it(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = self.armed(game)
                self.assertNotEqual(run.file(), b"")
                run.p.export("VvfpStoryVillageReset", run.n, 1)
                self.assertEqual(run.file(), b"")
                self.assertEqual(run.living_state()["used"], 0)


@emulated
class TheFinish(unittest.TestCase):
    def test_the_archetype_reached_is_counted(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                run.rolls([0] * 64)
                vi = run.arm("living_le_per_01")
                self.assertGreaterEqual(vi, 0)
                run.play(button=0)
                self.assertIn(run.state()["phase"], (IDLE, DONE))
                path = [run.p.u32(run.buf + 4 * k)
                        for k in range(run.p.export("VvfpStoryProbeGraphPath", 0, run.buf, 64))]
                outs = {node: arc for node, _grp, arc in run.pack["variants"][vi]["outcomes"]}
                self.assertIn(path[-1], outs)
                h = vleh_read(run.file(), run.pack)
                expected = [0] * run.pack["archetypes"]
                expected[outs[path[-1]]] = 1
                self.assertEqual(h["arc"], expected)

    def test_another_event_counts_nothing(self) -> None:
        from test_story_cie_graph_runtime import CIEG
        run = Living("vv4")
        run.rolls([0] * 64)
        self.assertGreaterEqual(run.arm("living_le_per_01"), 0)
        run.idle()
        before = run.file()
        self.assertIsNone(run.queue(CIEG))
        run.rolls([1, 1, 1, 7, 2, 5] + [0] * 40)
        run.play(button=0)
        self.assertEqual(run.file(), before)


@emulated
class PickAndLibrary(unittest.TestCase):
    def entries(self, run: Living) -> dict[str, tuple[int, str]]:
        out = {}
        title, needs, refusal = run.p.alloc(512), run.p.alloc(512), run.p.alloc(1024)
        m = 0
        while True:
            k = run.big("VvfpStoryProbeMoreEntry", run.n, m, title, needs, refusal, 400)
            if k == 0xFFFFFFFF:
                break
            run.p.export("VvfpStoryProbeMoreDescription", m, run.buf, 400)
            out[run.p.cstring(run.buf)] = (k, run.p.cstring(needs))
            m += 1
        return out

    def test_possible_when_any_variant_casts(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                run.manifest()
                rows = {line.split("\t")[0]: line.split("\t")[6] for line in manifest_text(run.n).splitlines()}
                got = self.entries(run)
                self.assertEqual(got[rows["living_le_per_01"]][1], "")     # its fifth variant casts
                self.assertNotEqual(got[rows["living_le_art_05"]][1], "")  # none casts: what it needs

    def test_the_library_casts_its_own_way_and_records(self) -> None:
        for game in each_game():
            with self.subTest(game=game):
                run = Living(game)
                # Art, Knowledge, and Craft: STRICT casts none; the library drops a requirement nobody meets.
                vi = run.big("VvfpStoryProbeLivingLibrary", run.n, run.text("living_le_art_05"), 1)
                self.assertNotEqual(vi, 0xFFFFFFFF)
                seed = run.ids["living_le_art_05"]
                self.assertEqual(run.pack["variants"][vi]["seed"], seed)
                h = vleh_read(run.file(), run.pack)
                self.assertEqual((h["ring"], h["var"][vi]), ([seed], 1))


@emulated
class GuardiansOfIsola(unittest.TestCase):
    """New Believers with and without Guardians of Isola Rewrite: no living text says "Heathen" or "convert" (so its
    manifest rows carry no Guardians wording and its blobs no Guardians variants); the same seed arms the same
    variant, and every page and title of the event is the same, with the patch on and off."""

    WORDS = r"heathen|convert"

    def test_new_believers_with_and_without_the_patch(self) -> None:
        import re
        from test_story_cie_graph_runtime_v6 import installed
        if not have_stock("vv5"):
            self.skipTest("needs New Believers' stock executable")
        seen = {}
        for guardians in (False, True):
            run = Living("vv5")
            if guardians:
                installed(run, ["guardians_of_isola"])
            run.rolls([0] * 64)
            vi = run.arm("living_le_per_01")
            self.assertGreaterEqual(vi, 0)
            run.walk_through([0] * 4)
            shown = run.displays() + run.titles()
            for text in shown:
                self.assertIsNone(re.search(self.WORDS, text, re.I), text)
            seen[guardians] = (vi, shown)
        self.assertEqual(seen[False], seen[True])

    def test_no_living_text_needs_guardians_wording(self) -> None:
        import re
        for game in mx.GAMES:
            p = mx.read_pack((ROOT / "assets" / "event_collection" / f"vv{game}" / "living.pak").read_bytes())
            for v in p["variants"]:
                self.assertIsNone(re.search(rb"(?i)heathen|convert", v["blob"]), (game, p["seeds"][v["seed"]]["id"]))
            rows = [r.split("\t") for r in (ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt")
                    .read_text(encoding="utf-8").splitlines() if r.startswith("living_")]
            self.assertTrue(rows)
            self.assertTrue(all(r[7] == "" and r[8] == "" for r in rows))
            self.assertTrue(all(re.search(self.WORDS, r[1] + r[6], re.I) is None for r in rows))


if __name__ == "__main__":
    unittest.main()
