"""The Living Event Engine's mixer (src/vv_living_mixer.py) and its pack (docs/event-collection/living-pack.md).

  * the build is deterministic, and the shipped packs and manifest rows are what it makes;
  * VLEP v1: the header, the tables and the blobs read back; every blob decompiles; the outcome map's node indexes
    are the decompiled graph's;
  * the variants: K per active seed, variant 0 of a MIX seed flagged, the games of each;
  * the run-time twin lv_order: weights 1000 / (1 + uses), at most 12 tries, no roll when the weights sum to 1 or
    less, the history's recency window;
  * the fixture packs under tests/data/living_fixture are what the mixer makes now.
"""
from __future__ import annotations

import struct
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
import vv_living_mixer as mx  # noqa: E402

BANK = mx.Bank()
VARIANTS, PACKS = mx.build(BANK)


class Determinism(unittest.TestCase):
    def test_a_second_build_is_identical(self) -> None:
        variants = mx.generate(BANK)
        self.assertEqual([(v.manifest_id, v.k, v.graph) for v in variants],
                         [(v.manifest_id, v.k, v.graph) for v in VARIANTS])

    def test_the_shipped_packs_are_what_the_build_makes(self) -> None:
        for game in mx.GAMES:
            with self.subTest(game=game):
                shipped = (ROOT / "assets" / "event_collection" / f"vv{game}" / "living.pak").read_bytes()
                self.assertEqual(shipped, PACKS[game])

    def test_the_shipped_manifest_rows_are_the_build_rows(self) -> None:
        import build_event_collection_features as build
        for game in mx.GAMES:
            with self.subTest(game=game):
                text = (ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt").read_text(encoding="utf-8")
                shipped = [r for r in text.splitlines() if r.startswith("living_")]
                self.assertEqual(shipped, [build.living_line(r) for r in mx.manifest_rows(game, VARIANTS, BANK)])

    def test_the_fixture_is_what_the_mixer_makes(self) -> None:
        for name, data in mx.fixture_files(VARIANTS, BANK).items():
            with self.subTest(name=name):
                self.assertEqual((mx.FIXTURE / name).read_bytes(), data)


class ThePack(unittest.TestCase):
    def test_header_and_crc(self) -> None:
        for game, data in PACKS.items():
            with self.subTest(game=game):
                self.assertEqual(data[:4], b"VLEP")
                version, hbytes, total, crc = struct.unpack_from("<HHII", data, 4)
                self.assertEqual((version, hbytes, total), (1, 64, len(data)))
                self.assertEqual(zlib.crc32(data[:12] + b"\0" * 4 + data[16:]) & 0xFFFFFFFF, crc)
                self.assertEqual(data[16], game)
                p = mx.read_pack(data)
                self.assertEqual((p["roles"], p["archetypes"], p["lenses"]), (30, 38, 15))
                blobs = struct.unpack_from("<I", data, 48)[0]
                self.assertEqual(blobs % 4, 0)

    def test_tables_and_blobs(self) -> None:
        for game, data in PACKS.items():
            p = mx.read_pack(data)
            mine = [v for v in VARIANTS if game in v.games]
            self.assertEqual(len(p["variants"]), len(mine))
            for rec, v in zip(p["variants"], mine):
                self.assertEqual(rec["blob"], v.cieg)
                self.assertEqual(rec["k"], v.k)
                self.assertEqual(p["seeds"][rec["seed"]]["id"], v.manifest_id)
                self.assertEqual(rec["games"], sum(1 << (g - 1) for g in v.games))
            for s in p["seeds"]:
                self.assertRegex(s["id"], r"^living_(le|mc)_[a-z]{3}_\d\d$")
                self.assertLessEqual(len(s["id"]), 22)
                self.assertEqual(s["series"], s["id"][:-3])
                ks = [p["variants"][i]["k"] for i in range(s["first"], s["first"] + s["count"])]
                self.assertEqual(ks, sorted(set(ks)))

    def test_outcome_map_node_indexes(self) -> None:
        p = mx.read_pack(PACKS[5])
        for rec in p["variants"][::17]:
            d = cg.decompile_graph(rec["blob"])
            order = list(d["nodes"])
            for node, grp, arc in rec["outcomes"]:
                n = d["nodes"][order[node]]
                self.assertEqual(n["children"], [])
                if arc != mx.NONE8:
                    self.assertEqual(n["text"], mx.plain(BANK.archetypes[arc]["text"]))
                    self.assertEqual(grp, mx.GROUP_CODE[BANK.archetypes[arc]["group"]])


class TheVariants(unittest.TestCase):
    def test_k_per_active_seed(self) -> None:
        by: dict[str, list[int]] = {}
        for v in VARIANTS:
            by.setdefault(v.manifest_id, []).append(v.k)
        self.assertEqual(len(by), 120 + 95)
        for sid, ks in by.items():
            self.assertEqual(ks, list(range(mx.MC_K if sid.startswith("living_mc_") else mx.K)), sid)

    def test_mix_is_variant_zero(self) -> None:
        mixed = [v for v in VARIANTS if v.flags & mx.FLAG_MIX]
        self.assertEqual(len(mixed), 60)
        self.assertTrue(all(v.k == 0 for v in mixed))
        self.assertEqual({v.seed for v in mixed}, {m["seed"] for m in BANK.mix})

    def test_one_game_roles_only_in_their_game(self) -> None:
        for v in VARIANTS:
            for rid in v.plan.get("roles") or []:
                self.assertTrue(set(v.games) <= set(BANK.role[rid]["games"]), (v.manifest_id, v.k, rid))

    def test_every_game_has_most_variants(self) -> None:
        """At most two of a seed's ten variants use a role only one game has (the VV3 chief, the VV5 practitioners)."""
        for seed in BANK.seeds:
            mine = [v for v in VARIANTS if v.seed == seed["id"]]
            for game in seed["games"]:
                self.assertGreaterEqual(sum(game in v.games for v in mine), mx.K - 2, (seed["id"], game))

    def test_no_mj(self) -> None:
        self.assertFalse(any(v.seed.startswith("mj_") for v in VARIANTS))

    def test_mc_ships_its_source_order_alone(self) -> None:
        """MC K = 1 (lead, 2026-11-14): its other orders were near duplicates (about 2 MB a pack)."""
        self.assertEqual(mx.MC_K, 1)
        for sit in BANK.mc_sits:
            orders = [v.plan["order"] for v in VARIANTS if v.seed == sit["id"]]
            self.assertEqual(orders, [(0, 1, 2, 3)])

    def test_mc_orders_are_distinct_when_asked_for(self) -> None:
        for sit in BANK.mc_sits[:5]:
            orders = mx.mc_orders(sit, mx.K)
            self.assertEqual(orders[0], (0, 1, 2, 3))
            self.assertEqual(len(set(orders)), mx.K)

    def test_packs_stay_small(self) -> None:
        for game, data in PACKS.items():
            self.assertLess(len(data), 4_000_000, game)

    def test_manifest_rows(self) -> None:
        for game in mx.GAMES:
            rows = mx.manifest_rows(game, VARIANTS, BANK)
            p = mx.read_pack(PACKS[game])
            self.assertEqual([r["id"] for r in rows], [s["id"] for s in p["seeds"]])
            series = {r["series"] for r in rows}
            self.assertEqual(len(series), 18)          # 12 Living Engine categories + 6 MC
            for r in rows:
                self.assertRegex(r["description"], r"^[A-Z][A-Za-z0-9 .,!?:;'-]*[.!?]$")
                self.assertLessEqual(len(r["description"]), 130)
                if game != 3:
                    self.assertNotIn("chief", r["description"].lower())
                self.assertEqual(r["credit"], BANK.credit)


class Ordering(unittest.TestCase):
    def setUp(self) -> None:
        self.p = mx.read_pack(PACKS[1])
        self.seed = self.p["seeds"][0]
        self.vs = self.p["variants"][self.seed["first"]:self.seed["first"] + self.seed["count"]]

    def hist(self) -> mx.History:
        return mx.History(30, 38, 15, len(self.p["variants"]))

    def test_fresh_history_takes_the_rolls_in_pack_order(self) -> None:
        rolls = []

        def below(n):
            rolls.append(n)
            return 0
        order = mx.lv_order(self.vs, self.seed["first"], self.hist(), below)
        self.assertEqual(order, list(range(self.seed["first"], self.seed["first"] + len(self.vs))))
        # One roll a pick (the last too: its weight, 1000, is more than 1).
        self.assertEqual(rolls, [1000 * n for n in range(len(self.vs), 0, -1)])

    def test_no_roll_when_the_weights_sum_to_one(self) -> None:
        h = self.hist()
        v = dict(self.vs[0])
        for _ in range(1000):
            h.armed(0, v, 7)
        rolls = []
        self.assertEqual(mx.lv_order([v], 7, h, lambda n: rolls.append(n) or 0), [7])
        self.assertEqual(rolls, [])                  # weight max(1, 1000 // 4001) = 1: no roll

    def test_at_most_twelve(self) -> None:
        many = self.vs * 2
        order = mx.lv_order(many, 0, mx.History(30, 38, 15, 100), lambda n: n - 1)
        self.assertEqual(len(order), 12)

    def test_used_variants_weigh_less(self) -> None:
        h = self.hist()
        first = self.seed["first"]
        h.armed(0, self.vs[0], first)          # pair, lens, family set and variant uses of variant 0 go up
        uses = h.uses(self.vs[0], first)
        self.assertGreaterEqual(uses, 2)
        seen = []
        mx.lv_order(self.vs, first, h, lambda n: seen.append(n) or 0)
        self.assertEqual(seen[0], 1000 // (1 + uses) + sum(1000 // (1 + h.uses(v, first + i))
                                                           for i, v in enumerate(self.vs) if i))

    def test_recency_window(self) -> None:
        h = self.hist()
        for i in range(100):
            h.armed(i, self.vs[0], self.seed["first"])
        self.assertEqual(len(h.ring), 64)
        self.assertEqual(h.recent(213), set(range(100 - 64, 100)))
        self.assertEqual(h.recent(30), set(range(90, 100)))
        self.assertEqual(h.recent(2), set())

    def test_finish_counts_the_archetype(self) -> None:
        h = self.hist()
        h.finished(5)
        h.finished(mx.NONE8)
        self.assertEqual(dict(h.arc), {5: 1})


class Moods(unittest.TestCase):
    """The owner's Global Editorial Override (item 10): about one third warm, social and serious."""

    TABLE = {"le_cat_per": "warm", "le_cat_fam": "social", "le_cat_cel": "warm", "le_cat_art": "social",
             "le_cat_ani": "social", "le_cat_bel": "serious", "le_cat_gov": "serious", "le_cat_oth": "social",
             "le_cat_foo": "warm", "le_cat_emo": "serious", "le_cat_res": "serious", "le_cat_odd": "warm",
             "mc_cat_isl": "social", "mc_cat_dis": "serious", "mc_cat_aft": "serious", "mc_cat_los": "serious",
             "mc_cat_tra": "serious", "mc_cat_bel": "social"}

    def test_the_table(self) -> None:
        got = {c["id"]: c["mood"] for c in BANK.categories + BANK.mc_cats}
        self.assertEqual(got, self.TABLE)
        self.assertEqual(BANK.raw["moods"]["order"], list(mx.MOODS))

    def test_living_engine_is_a_third_each(self) -> None:
        moods = [c["mood"] for c in BANK.categories]
        self.assertEqual({m: moods.count(m) for m in mx.MOODS}, {"warm": 4, "social": 4, "serious": 4})

    def test_each_seed_record_holds_its_categorys_mood(self) -> None:
        for game, data in PACKS.items():
            p = mx.read_pack(data)
            for s in p["seeds"]:
                v = next(x for x in VARIANTS if x.manifest_id == s["id"])
                cat = BANK.cat[BANK.seed[v.seed]["category"]] if v.bank == 0 else BANK.mc_cats[v.cat_index]
                self.assertEqual(mx.MOODS[s["mood"]], cat["mood"], (game, s["id"]))

    def test_mood_weights(self) -> None:
        h = mx.History(30, 38, 15, 10)
        moods = [0, 0, 1, 2]                          # seed -> mood
        self.assertEqual(h.mood_weights(moods), [1, 1, 1])           # nothing seen: no bias
        h.ring = [0, 2]
        self.assertEqual(h.mood_weights(moods), [1, 1, mx.MOOD_BOOST])   # serious seen least
        h.ring = [0, 3]
        self.assertEqual(h.mood_weights(moods), [1, mx.MOOD_BOOST, 1])
        h.ring = [0]
        self.assertEqual(h.mood_weights(moods), [1, mx.MOOD_BOOST, mx.MOOD_BOOST])
        h.ring = [0, 2, 3]
        self.assertEqual(h.mood_weights(moods), [1, 1, 1])           # one each: no bias


class TheLenses(unittest.TestCase):
    def test_fifteen_plain_lenses(self) -> None:
        texts = [l["text"] for l in BANK.lenses]
        self.assertEqual(len(texts), 15)
        self.assertEqual(texts[-1], "uncertainty")
        self.assertTrue(all("." not in x and " seed " not in x for x in texts), texts)
        self.assertEqual([l["id"] for l in BANK.lenses], ["le_lens_" + x for x in texts])


if __name__ == "__main__":
    unittest.main()
