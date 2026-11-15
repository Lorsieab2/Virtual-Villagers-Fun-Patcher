"""The Living Event Engine's packs say only the owner's words (scripts/living_check.py), exhaustively.

  * every variant of every game's shipped pack decompiled; every text, label, pool item and game word expanded for
    that game; each must be an indexed owner line or the frame (living-events.md section 1);
  * the MIX anchor: each of the 60 MIX examples, read from the frozen source, becomes its seed's variant 0 with
    exactly the changes documented in living-events.md section 7 (the frame fix, the swaps, the sensitivity edits);
  * the documented changes are the mixer's; the credits keep the Living Engine's credit line verbatim.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import living_check as lc  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
import vv_living_mixer as mx  # noqa: E402

BANK = mx.Bank()
PACKS = {g: lc.pack_path(g).read_bytes() for g in mx.GAMES}
SETUP_RE = re.compile(r"^SETUP: (?P<seed>.+?) (A|An) (?P<pa>[a-z]+) (?P<ra>an? .+?) and (a|an) (?P<pb>[a-z]+) "
                      r"(?P<rb>an? .+?) disagree about what should happen next\. Their status alone does not settle "
                      r"the matter\.$")


def documented_changes() -> list[dict]:
    text = mx.DOC.read_text(encoding="utf-8")
    block = text[text.index(mx.DOC_BEGIN):text.index(mx.DOC_END)]
    rows = []
    for line in block.splitlines():
        m = re.match(r"^\| (MIX-\d{3}) \| (.+?) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if m:
            rows.append({"mix": m[1], "what": m[2], "before": m[3], "after": m[4], "rule": m[5]})
    return rows


def article(word: str) -> str:
    return "an" if word[0] in "aeiou" else "a"


class Exhaustive(unittest.TestCase):
    def test_every_variant_in_every_game(self) -> None:
        problems, stats = lc.check_packs(PACKS, BANK)
        self.assertEqual(problems, [])
        self.assertEqual(sum(stats["variants"].values()), sum(len(mx.read_pack(p)["variants"]) for p in PACKS.values()))

    def test_bank_texts_are_on_their_source_lines(self) -> None:
        lines = lc.source_lines()
        items = [(s["text"], s["src"]) for s in BANK.seeds] + [(a["text"], a["src"]) for a in BANK.archetypes] \
            + [(a["text"], a["src"]) for a in BANK.approaches] + [(c["text"], c["src"]) for c in BANK.choice.values()]
        for sit in BANK.mc_sits:
            items.append((sit["text"], sit["src"]))
            for ap in sit["approaches"]:
                items.append((ap["text"], ap["src"]))
                items += [(o["text"], o["src"]) for o in ap["outcomes"]]
        for text, src in items:
            with self.subTest(src=src):
                n = int(src[1:].split("-")[0].split(",")[0])
                self.assertIn(text, lines[n - 1])

    def test_credit_kept(self) -> None:
        credits = (ROOT / "assets" / "event_collection" / "Credits.txt").read_text(encoding="utf-8")
        self.assertEqual(lc.source_lines()[23814].rstrip("\r"), "CREDITS: " + BANK.credit)
        self.assertIn("CREDITS: " + BANK.credit + "\n", credits)
        for game in mx.GAMES:
            manifest = (ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt").read_text(encoding="utf-8")
            rows = [r.split("\t") for r in manifest.splitlines() if r.startswith("living_")]
            self.assertTrue(rows)
            self.assertTrue(all(r[5] == BANK.credit for r in rows))


class MixAnchor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.changes = documented_changes()
        cls.variant0 = {}
        for game, data in PACKS.items():
            p = mx.read_pack(data)
            for s in p["seeds"]:
                for vi in range(s["first"], s["first"] + s["count"]):
                    v = p["variants"][vi]
                    if v["flags"] & mx.FLAG_MIX and s["id"] not in cls.variant0:
                        cls.variant0[s["id"]] = (game, cg.decompile_graph(v["blob"]))

    def test_documented_changes_are_the_mixers(self) -> None:
        mx.generate(BANK)
        self.assertIn(mx.changes_markdown(), mx.DOC.read_text(encoding="utf-8"))
        self.assertEqual(len(self.changes), len(mx.MIX_CHANGES))
        conflicts = {BANK.raw["mix"][i]["code"] for i, m in enumerate(BANK.raw["mix"]) if m["id"] in BANK.conflicts}
        self.assertTrue(conflicts <= {c["mix"] for c in self.changes})      # every conflicting MIX is changed

    def test_each_mix_reproduced_with_exactly_the_documented_changes(self) -> None:
        lines = lc.source_lines()
        self.assertEqual(len(self.variant0), 60)
        for mix in BANK.mix:
            with self.subTest(mix=mix["code"]):
                n = int(mix["setup_src"][1:])
                m = SETUP_RE.match(mx.plain(lines[n - 1].strip()))
                self.assertIsNotNone(m)
                pa, pb = m["pa"], m["pb"]
                ra, rb = m["ra"], m["rb"]
                labels = [mx.plain(lines[n + 3 * i].strip())[3:] for i in range(4)]
                outs = [[mx.plain(lines[n + 3 * i + j].strip())[4:] for j in (1, 2)] for i in range(4)]
                drop = {"first": False, "second": False}
                for c in self.changes:
                    if c["mix"] != mix["code"]:
                        continue
                    slot = "first" if c["what"].startswith("first") else "second"
                    if "role" in c["what"]:
                        if slot == "first":
                            self.assertEqual(ra, c["before"])
                            ra = c["after"]
                        else:
                            self.assertEqual(rb, c["before"])
                            rb = c["after"]
                    elif "doubled word" in c["what"]:
                        drop[slot] = True
                    elif "personality" in c["what"]:
                        if slot == "first":
                            self.assertEqual(pa, c["before"])
                            pa = c["after"]
                        else:
                            self.assertEqual(pb, c["before"])
                            pb = c["after"]
                    else:
                        cm = re.match(r"choice ([ABCD]) outcome ([12])", c["what"])
                        i, j = "ABCD".index(cm[1]), int(cm[2]) - 1
                        self.assertEqual(outs[i][j], c["before"])
                        outs[i][j] = c["after"]
                game, d = self.variant0["living_" + mix["seed"]]
                words = d.get("words") or {}

                def part(p, r, dropped):
                    word = r.split(" ", 1)[1]
                    return r if dropped else f"{article(p)} {p} {word}"
                want = (f"{lc.chief_form(m['seed'], game)} (first), {part(pa, ra, drop['first'])}, and (second), "
                        f"{part(pb, rb, drop['second'])}, {mx.FRAME_TAIL}")
                start = d["nodes"][d["start"]]
                self.assertEqual(lc.expand_words(start["text"], words, game), want)
                self.assertEqual([lc.expand_words(c["label"], words, game) for c in start["choices"]], labels)
                for c, (good, bad) in zip(start["choices"], outs):
                    kids = d["nodes"][c["next"]]["children"]
                    self.assertEqual([d["nodes"][k["next"]]["text"] for k in kids[:2]], [good, bad])
                    self.assertEqual([k["weight"] for k in kids[:2]], [mx.W_GOOD, mx.W_ADVERSE])


if __name__ == "__main__":
    unittest.main()
