"""Isola Grand Event Collection: the frozen source, the manifest and every collection file (design E4 a-h).

Pinned here:
  * the source in the repo is the frozen V28 copy (SHA-256 in data/event_collection/SOURCE.sha256), line count fixed;
  * data/event_collection/manifest.json is current (scripts/collection_manifest.py --check), covers every
    non-blank line of the source with no overlap, and lists its disagreements with the inventories;
  * every data/event_collection/<section>/<id>.json passes scripts/collection_check.py (a SCHEMA and g ROUND are
    SKIPPED, never passed, until src/vv_cie_graph.py reads version 6);
  * each check refuses what it should: a changed word, a dropped bank item, an unconsumed source line, an unlisted
    grammar fix, an unprefixed pronoun, "Chief" outside VV3, a missing effect, unequal weights, a harmed special
    villager, an unreachable node;
  * grammar fixes used by any file are in docs/event-collection/grammar-fixes.md.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import collection_manifest as cm  # noqa: E402

GARDENING = ROOT / "data" / "event_collection" / "v6" / "vv3_gardening_contest.json"


def check_doc(doc: dict, name: str = "vv3_gardening_contest", section: str = "v6") -> cc.Report:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / section / f"{name}.json"
        p.parent.mkdir()
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        return cc.check_file(p)


def problems(rep: cc.Report, check: str) -> list[str]:
    return [p for p in rep.problems if p.startswith(check)]


class FrozenSource(unittest.TestCase):
    def test_sha256_matches_the_record(self):
        self.assertEqual(lib.recorded_sha256(),
                         "319712596bccd325f47df13b10dc895071f0306f7105b17cc8f3ed73bae44c3e")
        self.assertEqual(lib.source_sha256(), lib.recorded_sha256(),
                         "the frozen source changed (or was checked out with CRLF: see .gitattributes)")

    def test_record_names_the_source(self):
        rel = lib.SOURCE_HASH_FILE.read_text(encoding="ascii").split(None, 1)[1].strip()
        self.assertEqual(ROOT / rel, lib.SOURCE)

    def test_line_count_is_stable(self):
        raw = lib.SOURCE.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(len(lib.source_lines()), lib.SOURCE_LINES)


class FrozenCompanion(unittest.TestCase):
    """The second source: the owner's Companion Anthology, frozen byte for byte (2026-11-14)."""

    def test_sha256_matches_the_record(self):
        self.assertEqual(lib.recorded_sha256(lib.COMPANION_ID),
                         "d39d14da81b04225308452425069db3186a62065a3ee634f5c6afd074e64ff16")
        self.assertEqual(lib.source_sha256(lib.COMPANION_ID), lib.recorded_sha256(lib.COMPANION_ID))

    def test_record_names_the_source(self):
        rel = lib.COMPANION_HASH_FILE.read_text(encoding="ascii").split(None, 1)[1].strip()
        self.assertEqual(ROOT / rel, lib.COMPANION)

    def test_line_count_and_active_source(self):
        self.assertNotIn(b"\r", lib.COMPANION.read_bytes())
        self.assertEqual(len(lib.source_lines(lib.COMPANION_ID)), lib.COMPANION_LINES)
        self.assertEqual(lib.active_source(), lib.SOURCE_ID)
        with lib.use_source(lib.COMPANION_ID):
            self.assertTrue(lib.line(92).startswith("EVENT 001"))
            self.assertEqual(lib.src_lines("L8961"), [8961])
            with self.assertRaises(ValueError):
                lib.src_lines("L8962")
        self.assertEqual(lib.active_source(), lib.SOURCE_ID)
        self.assertNotEqual(lib.line(92)[:9], "EVENT 001")

    def test_companion_markers_only_for_the_companion(self):
        self.assertEqual(lib.strip_structural("RANDOM OUTCOME 1 - A jar."), "RANDOM OUTCOME 1 - A jar.")
        with lib.use_source(lib.COMPANION_ID):
            self.assertEqual(lib.strip_structural("RANDOM OUTCOME 1 - A jar."), "A jar.")
            self.assertEqual(lib.strip_structural("  • A jar."), "A jar.")


class FrozenLiving(unittest.TestCase):
    """The third source: the owner's all-in-one Living Event Engine file, frozen byte for byte (2026-11-14)."""

    def test_sha256_matches_the_record(self):
        self.assertEqual(lib.recorded_sha256(lib.LIVING_ID),
                         "cbb46fcbbdb594f54b69da9297ca21242b51d15ee7b41080c795e8555addf31c")
        self.assertEqual(lib.source_sha256(lib.LIVING_ID), lib.recorded_sha256(lib.LIVING_ID))
        rel = lib.LIVING_HASH_FILE.read_text(encoding="ascii").split(None, 1)[1].strip()
        self.assertEqual(ROOT / rel, lib.LIVING)

    def test_line_count(self):
        self.assertNotIn(b"\r", lib.LIVING.read_bytes())
        self.assertEqual(len(lib.source_lines(lib.LIVING_ID)), lib.LIVING_LINES)
        with lib.use_source(lib.LIVING_ID):
            self.assertTrue(lib.line(20219).startswith("MED-01"))

    def test_living_rows(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data["living"]["uncovered_lines"], [])
        self.assertEqual(data["living"]["overlaps"], [])
        rows = [r for r in data["rows"] if r["source"] == lib.LIVING_ID and r["kind"] == "event"]
        by = {}
        for r in rows:
            by[r["section"]] = by.get(r["section"], 0) + 1
            self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
        # v20: Two Lives, One Decision reads this file's copy of D1 (the owner's added outcomes, 2026-11-15); its file
        # stays in data/event_collection/v20/
        self.assertEqual(by, {"lv_med": 31, "lv_life": 45, "lv_circle": 31, "lv_peoples": 37, "lv_unseen": 39,
                              "lv_ways": 38, "lv_auth": 30, "v20": 1})
        files = [p for p in cc.collection_files() if lib.LIVING_DIR in p.parents]
        self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows if r["section"] != "v20"))


class FrozenHorizonAndRoleModels(unittest.TestCase):
    """The fourth and fifth sources (2026-11-15): Beyond the Horizon and Role Models and Good Examples, frozen byte
    for byte (the Role Models file keeps the owner's CRLF line ends)."""

    SOURCES = ((lib.HORIZON_ID, lib.HORIZON, lib.HORIZON_HASH_FILE, lib.HORIZON_DIR,
                "8ebae8de40a13179ac908777e4d02f43d2dcb4f397d77a367c3a75878a266f1c",
                {"hz_world": 40, "hz_vol2": 40}),
               (lib.ROLEMODELS_ID, lib.ROLEMODELS, lib.ROLEMODELS_HASH_FILE, lib.ROLEMODELS_DIR,
                "688010b259dda145cb9b7e3afb78658be5fc960ce323da9c0bb9c241b26a14ad", {"rm": 40}))

    def test_sha256_and_lines(self):
        for sid, path, hash_file, _d, digest, _by in self.SOURCES:
            with self.subTest(sid):
                self.assertEqual(lib.recorded_sha256(sid), digest)
                self.assertEqual(lib.source_sha256(sid), digest)
                rel = hash_file.read_text(encoding="ascii").split(None, 1)[1].strip()
                self.assertEqual(ROOT / rel, path)
                self.assertEqual(len(lib.source_lines(sid)), lib.SOURCES[sid][2])
        with lib.use_source(lib.HORIZON_ID):
            self.assertTrue(lib.line(23).startswith("EVENT 001"))
        with lib.use_source(lib.ROLEMODELS_ID):
            self.assertTrue(lib.line(5).startswith("EVENT RM-01"))

    def test_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        for sid, _p, _h, folder, _d, want in self.SOURCES:
            with self.subTest(sid):
                self.assertEqual(data[sid]["uncovered_lines"], [])
                self.assertEqual(data[sid]["overlaps"], [])
                rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
                by = {}
                for r in rows:
                    by[r["section"]] = by.get(r["section"], 0) + 1
                    self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
                self.assertEqual(by, want)
                files = [p for p in cc.collection_files() if folder in p.parents]
                self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))
        # the owner (2026-11-15): choice options always title case -- these sources' files say so and show it
        self.assertEqual(lib.title_case_label("Divide the remaining food into equal portions."),
                         "Divide the Remaining Food into Equal Portions.")
        self.assertEqual(lib.title_case_label("Invite the child to help with an age-appropriate part of the chore."),
                         "Invite the Child to Help with an Age-Appropriate Part of the Chore.")
        self.assertEqual(lib.title_case_label("Leave the reef alone for the day."), "Leave the Reef Alone for the Day.")
        self.assertEqual(lib.title_case_label("Ask what it is for."), "Ask What It Is For.")
        for folder in (lib.HORIZON_DIR, lib.ROLEMODELS_DIR):
            for p in folder.glob("*/*.json"):
                doc = json.loads(p.read_text(encoding="utf-8"))
                self.assertEqual(doc["collection"]["label_case"], "title", p.name)
                for c in doc["nodes"]["setup"]["choices"]:
                    self.assertEqual(c["label"], lib.title_case_label(c["label"]), p.name)
        # one series per PART of volume I, and Expansion Volume II as one (each counts as one in the rare roll)
        self.assertEqual(data["horizon"]["counts"]["series"], {"hz_part1": 8, "hz_part2": 8, "hz_part3": 9,
                                                               "hz_part4": 7, "hz_part5": 8, "hz_vol2": 40})


class FrozenDraftsA(unittest.TestCase):
    """The owner-approved drafts of 2026-11-15, set A: twelve frozen sources, one series each."""

    EVENTS = {"da_il01": 10, "da_il02": 30, "da_il03": 20, "da_il04": 20, "da_il05": 20, "da_il06": 20,
              "da_il07": 20, "da_il08": 20, "da_il09": 20, "da_il10": 20, "da_wd": 50, "da_lo": 50}

    def test_sha256_and_lines(self):
        self.assertEqual(set(lib.DRAFTS_A), set(self.EVENTS))
        for sid in lib.DRAFTS_A:
            with self.subTest(sid):
                self.assertEqual(lib.source_sha256(sid), lib.recorded_sha256(sid))
                rel = lib.SOURCES[sid][1].read_text(encoding="ascii").split(None, 1)[1].strip()
                self.assertEqual(ROOT / rel, lib.SOURCES[sid][0])
                self.assertEqual(len(lib.source_lines(sid)), lib.SOURCES[sid][2])

    def test_rows_files_and_series(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        for sid, want in self.EVENTS.items():
            with self.subTest(sid):
                block = data["drafts_a"][sid]
                self.assertEqual(block["uncovered_lines"], [])
                self.assertEqual(block["overlaps"], [])
                self.assertEqual(block["counts"]["series"], {sid: want})
                rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
                self.assertEqual(len(rows), want)
                for r in rows:
                    self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
                files = [p for p in cc.collection_files() if (lib.DRAFTS_A_DIR / sid) in p.parents]
                self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))


class FrozenDraftsB(unittest.TestCase):
    """The owner-approved draft event files, group B (2026-11-15): eight files, each its own frozen source (byte for
    byte), 50 events each, one series per file, built by scripts/drafts_b/gen_drafts_b.py."""

    def test_sha256_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(lib.DRAFTS_B), 8)
        for sid, (topic, n, section, prefix) in lib.DRAFTS_B.items():
            with self.subTest(sid):
                self.assertEqual(lib.recorded_sha256(sid), lib.source_sha256(sid))
                path = lib.SOURCES[sid][0]
                rel = lib.SOURCES[sid][1].read_text(encoding="ascii").split(None, 1)[1].strip()
                self.assertEqual(ROOT / rel, path)
                self.assertEqual(path.read_bytes().count(b"\n"), n)
                with lib.use_source(sid):
                    self.assertTrue(lib.line(1).startswith("NEW EVENTS"))
                self.assertEqual(data[sid]["uncovered_lines"], [])
                self.assertEqual(data[sid]["overlaps"], [])
                self.assertEqual(data[sid]["counts"]["series"], {section: 50})
                rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
                self.assertEqual(len(rows), 50)
                for r in rows:
                    self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
                    self.assertTrue(r["id"].startswith(prefix.lower()), r["id"])
                    self.assertEqual(r["games"], [1, 2, 3, 4, 5])
                files = [p for p in cc.collection_files() if lib.DRAFTS_B_DIR / section in p.parents]
                self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))
                for p in files:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    self.assertEqual(doc["collection"]["label_case"], "title", p.name)
                    for c in doc["nodes"]["setup"].get("choices", []):
                        self.assertEqual(c["label"], lib.title_case_label(c["label"]), p.name)


class FrozenDraftsC(unittest.TestCase):
    """The owner-approved draft event files, group C (2026-11-15), wired as group B: eight files, 50 events each, one
    series per file; BLF-26/27 New Believers only; built by scripts/drafts_c/gen_drafts_c.py."""

    def test_sha256_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(len(lib.DRAFTS_C), 8)
        vv5_only = set()
        for sid, (topic, n, section, prefix) in lib.DRAFTS_C.items():
            with self.subTest(sid):
                self.assertEqual(lib.recorded_sha256(sid), lib.source_sha256(sid))
                path = lib.SOURCES[sid][0]
                self.assertEqual(path.read_bytes().count(b"\n"), n)
                self.assertEqual(data[sid]["uncovered_lines"], [])
                self.assertEqual(data[sid]["overlaps"], [])
                self.assertEqual(data[sid]["counts"]["series"], {section: 50})
                rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
                self.assertEqual(len(rows), 50)
                for r in rows:
                    self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
                    if r["games"] != [1, 2, 3, 4, 5]:
                        self.assertEqual(r["games"], [5], r["id"])
                        vv5_only.add(r["id"][:5])
                files = [p for p in cc.collection_files() if lib.DRAFTS_C_DIR / section in p.parents]
                self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))
                for p in files:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    self.assertEqual(doc["collection"]["label_case"], "title", p.name)
                    for nd in doc["nodes"].values():      # BLF-36: setup_m / setup_f (the same-sex couple)
                        for c in nd.get("choices", []):
                            self.assertEqual(c["label"], lib.title_case_label(c["label"]), p.name)
        self.assertEqual(vv5_only, {"blf26", "blf27"})


class FrozenDraftsD(unittest.TestCase):
    """The owner-approved files, group D (2026-11-15): eight files, each one series; moments are a branch of equally
    likely endings; no effects; Fathers 01-08 a male nursing parent; built by scripts/drafts_d/gen_drafts_d.py."""

    WANT = {"draft_rm2": 50, "draft_hz2": 50, "moments500": 125, "draft_tim2": 50, "openq97": 35, "armor45": 45,
            "draft_arm2": 50, "fathers30": 30}

    def test_sha256_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(set(lib.DRAFTS_D), set(self.WANT))
        owner = lib.owner_titles()
        for sid, (_name, n, section, _topic) in lib.DRAFTS_D.items():
            with self.subTest(sid):
                self.assertEqual(lib.recorded_sha256(sid), lib.source_sha256(sid))
                self.assertEqual(lib.SOURCES[sid][0].read_bytes().count(b"\n"), n)
                self.assertEqual(data[sid]["uncovered_lines"], [])
                self.assertEqual(data[sid]["overlaps"], [])
                self.assertEqual(data[sid]["counts"]["series"], {section: self.WANT[sid]})
                rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
                self.assertEqual(len(rows), self.WANT[sid])
                files = [p for p in cc.collection_files() if lib.DRAFTS_D_DIR / section in p.parents]
                self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))
                for p in files:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    self.assertEqual(doc["games"], [1, 2, 3, 4, 5], p.name)
                    self.assertFalse(any(nd.get("effects") for nd in doc["nodes"].values()), p.name)
                    for c in doc["nodes"]["setup"].get("choices", []):
                        self.assertEqual(c["label"], lib.title_case_label(c["label"]), p.name)
                    if sid in ("moments500", "draft_tim2"):
                        kids = doc["nodes"]["setup"]["children"]
                        self.assertEqual(len(kids), 4, p.name)
                        self.assertFalse(any("weight" in k for k in kids), p.name)
                    if sid == "moments500":
                        self.assertIn(doc["collection"]["id"], owner)
                    if sid == "fathers30":
                        nursing = doc["roles"]["subject"].get("special") == "nursing_parent"
                        num = int(p.stem[3:5])
                        self.assertEqual(nursing, num <= 8 and num not in (5, 6, 7), p.name)
                        if num in (5, 6, 7):   # after the birth: a man who is a recorded parent of the young child
                            self.assertEqual(doc["roles"]["subject"]["relation"], {"parent_of": "friend"}, p.name)
                            self.assertEqual(doc["roles"]["subject"]["sex"], "male")
                        if nursing:
                            self.assertEqual(doc["roles"]["subject"]["sex"], "male")


class FrozenAnthology(unittest.TestCase):
    """The owner's all-in-one Animals anthology (2026-11-15), frozen byte for byte: only its newest volumes are rows,
    one series each, built by scripts/anthology_new/gen_anthology.py."""

    WANT = {"an_mom": 8, "an_rel": 36, "an_child": 47, "an_fam": 24, "an_joy": 38, "an_hs": 42, "an_age": 36,
            "an_jus": 32, "an_expr": 74, "an_fauna": 24}

    def test_sha256_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        sid = lib.ANTHOLOGY_ID
        self.assertEqual(lib.recorded_sha256(sid), "95172b7948bc94afe35013d3ceb28092fc78790b8ba3bf67e5ac228aacbe4de2")
        self.assertEqual(lib.source_sha256(sid), lib.recorded_sha256(sid))
        rel = lib.ANTHOLOGY_HASH_FILE.read_text(encoding="ascii").split(None, 1)[1].strip()
        self.assertEqual(ROOT / rel, lib.ANTHOLOGY)
        self.assertEqual(lib.ANTHOLOGY.read_bytes().count(b"\n"), lib.ANTHOLOGY_LINES)
        with lib.use_source(sid):
            self.assertTrue(lib.line(59).startswith("[MOM-01]"))
        self.assertEqual(data[sid]["uncovered_lines"], [])
        self.assertEqual(data[sid]["overlaps"], [])
        self.assertEqual(data[sid]["counts"]["series"], self.WANT)
        rows = [r for r in data["rows"] if r["source"] == sid and r["kind"] == "event"]
        self.assertEqual(len(rows), sum(self.WANT.values()))
        for r in rows:
            self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])
            self.assertEqual(r["games"], [1, 2, 3, 4, 5])
            self.assertEqual(r["series"], r["section"])
        files = [p for p in cc.collection_files() if lib.ANTHOLOGY_DIR in p.parents]
        self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows))
        effects = {}
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(doc["collection"]["label_case"], "title", p.name)
            for c in (c for nd in doc["nodes"].values() for c in nd.get("choices", [])):   # REL-04/26: two copies
                self.assertEqual(c["label"], lib.title_case_label(c["label"].replace("{@Chief}", "Chief")).replace(
                    "Chief", "{@Chief}"), p.name)
            for nd in doc["nodes"].values():
                for e in nd.get("effects", []):
                    effects[e["do"]] = effects.get(e["do"], 0) + 1
            for r in doc["roles"].values():
                if r.get("special") == "nursing_parent":     # a carrying or nursing parent: an adult woman
                    self.assertEqual((r["sex"], r["min_age"] >= 18), ("female", True), p.name)
        # nothing harmful: hair dye (the random head look), REL-15's sex change, two couples' celebrations
        self.assertEqual(effects, {"appearance": 5, "sex_change": 1, "celebrate": 4})


class FrozenCritic(unittest.TestCase):
    """The owner's "(Name1)'s Harshest Critic" (2026-11-16, Expanded v3), frozen byte for byte: one event in six files
    (its route families), one series, the setup and shared pools as add-on rows (authoring-rules.md 15i)."""

    def test_sha256_rows_and_files(self):
        data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))
        sid = lib.CRITIC_ID
        self.assertEqual(lib.recorded_sha256(sid), "a4445778c71f7e23c01c476258e6d002f785ef7d37d058e2b9d34f0018993149")
        self.assertEqual(lib.source_sha256(sid), lib.recorded_sha256(sid))
        self.assertEqual(lib.source_sha256(lib.CRITIC_CREDIT_ID), lib.recorded_sha256(lib.CRITIC_CREDIT_ID))
        self.assertEqual(lib.CRITIC.read_bytes().count(b"\n"), lib.CRITIC_LINES)
        self.assertEqual(lib.CRITIC_CREDIT.read_text(encoding="utf-8"), "Created by Lorsieab2, Claude and ChatGPT.\n")
        self.assertEqual(data[sid]["uncovered_lines"], [])
        self.assertEqual(data[sid]["overlaps"], [])
        rows = [r for r in data["rows"] if r["source"] == sid]
        self.assertEqual(sum(r["kind"] == "event" for r in rows), 6)
        self.assertEqual(sum(r["kind"] == "addon" for r in rows), 6)
        self.assertEqual({r["series"] for r in rows}, {"hc_critic"})
        files = [p for p in cc.collection_files() if lib.CRITIC_DIR in p.parents]
        self.assertEqual(sorted(p.stem for p in files), sorted(r["id"] for r in rows if r["kind"] == "event"))
        routes = 0
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(doc["games"], [1, 2, 3, 4, 5], p.name)
            self.assertEqual(doc["title"], "(Name1)'s Harshest Critic")
            self.assertEqual(doc["collection"]["credit"], "Created by Lorsieab2, Claude and ChatGPT.")
            self.assertIn("hc_setup", doc["collection"]["addons"])
            self.assertIn("hc_variant2", doc["collection"]["addons"])
            for c in (c for nd in doc["nodes"].values() for c in nd.get("choices", [])):
                self.assertEqual(lib.title_case_label(c["label"]), c["label"], p.name)
            routes += len(doc["nodes"]["routes"]["children"])
            # Variant 2: the mentor's kind word after a fail or a stumble
            self.assertTrue(any(n.get("text") == "{V2}" for n in doc["nodes"].values()), p.name)
            # every group's question copies: four each, labels from the owner's lists
            self.assertEqual(sum(1 for n in doc["nodes"].values() if n.get("type") == "question"), 24)
        self.assertEqual(routes, 112)


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_current(self):
        self.assertEqual(lib.MANIFEST.read_text(encoding="utf-8"), cm.dumps(cm.build()),
                         "run python scripts/collection_manifest.py")

    def test_every_line_belongs_to_one_row(self):
        self.assertEqual(self.data["uncovered_lines"], [])
        self.assertEqual(self.data["overlaps"], [])
        self.assertEqual(self.data["companion"]["uncovered_lines"], [])
        self.assertEqual(self.data["companion"]["overlaps"], [])

    def test_companion_counts(self):
        # The anthology's contents (L7-14): 318 + 120 + 60 + 97 + 154 = 749 events; its Living Catalogue templates are
        # seven series (the owner, 2026-11-14: a series still counts as one).
        c = self.data["companion"]["counts"]
        self.assertEqual(c["events"], 749)
        self.assertEqual(c["notes"], 23)
        self.assertEqual(c["series"], {"cat_bodies": 28, "cat_fins": 28, "cat_foliage": 23, "cat_flowers": 37,
                                       "cat_magic_fish": 7, "cat_magic_plants": 6, "cat_creatures": 5})
        self.assertEqual(self.data["companion"]["source_sha256"],
                         "d39d14da81b04225308452425069db3186a62065a3ee634f5c6afd074e64ff16")
        rows = [r for r in self.data["rows"] if r["source"] == lib.COMPANION_ID and r["kind"] == "event"]
        by = {}
        for r in rows:
            by[r["section"]] = by.get(r["section"], 0) + 1
            self.assertLessEqual(len(r["id"]), cm.VV1_ID_MAX, r["id"])     # every companion event is in A New Home
        self.assertEqual(by, {"c5": 318, "lbl": 120, "fwk": 60, "sss": 97, "cat": 154})

    def test_counts(self):
        c = self.data["counts"]
        # 22 + 29 + 124 events, 4 add-ons (two Cooking Contest add-ons, V13-A, V13-B): the source has 34 V17
        # contests where inventory part 3 counted 33 (listed in inventory_disagreements).  The V28 source adds V27's
        # 57 short events (and removes the V26 materials bank).  D1 (Two Lives, One Decision) reads the owner's newer
        # copy in the Living Engine file (2026-11-15: its added outcomes), so it is a living row; its V28 lines a notes
        # row.
        self.assertEqual(c["events"], 175 + 57 - 1)
        self.assertEqual(c["banks"], 7)
        self.assertEqual(c["addons"], 4)
        self.assertEqual(c["series"], {"v14_golden_child": 25, "v17_contests": 34, "v18_trials": 12,
                                       "v20_crises": 11})
        d1 = next(r for r in self.data["rows"] if r["id"] == "all_v20_d1_two_lives")
        self.assertEqual((d1["source"], d1["lines"], d1["series"]), (lib.LIVING_ID, [8957, 9056], "v20_crises"))
        self.assertTrue(any("V17-E has 7 contests" in d["what"] for d in self.data["inventory_disagreements"]))

    def test_rows_are_verified_against_the_source(self):
        for r in self.data["rows"]:
            self.assertEqual(r["source_check"]["boundary"], [], r["id"])
            self.assertNotEqual(r["source_check"]["title_found"], False, r["id"])
            if r["kind"] in ("event", "addon"):
                self.assertEqual(r["source_check"]["choices"], "verified", r["id"])
        self.assertEqual(self.data["disagreements"], [])

    def test_ids_unique_and_credit_verbatim(self):
        ids = [r["id"] for r in self.data["rows"]]
        self.assertEqual(len(ids), len(set(ids)))
        for r in self.data["rows"]:
            with lib.use_source(r["credit"].get("source", r["source"])):   # a credit file of its own (critic)
                text = "\n".join(lib.line(n) for spec in r["credit"]["lines"] for n in lib.src_lines(spec))
            self.assertEqual(r["credit"]["text"], text, r["id"])

    def test_known_counts(self):
        rows = {r["id"]: r for r in self.data["rows"]}
        self.assertEqual(rows["vv3_gardening_contest"]["pools"], {"A": 6, "(1)": 4, "(2)": 4, "(3)": 5})
        self.assertEqual(rows["vv2_cooking_contest"]["pools"]["Q"], 27)
        self.assertEqual(rows["vv1_child_of_legend"]["pools"]["(4)"], 11)
        self.assertEqual(rows["vv5_meaning_of_faith"]["choices"], 6)
        self.assertEqual(rows["all_v20_between_life"]["choices"], 7)
        self.assertEqual(rows["all_v22_4_parents"]["choices"], 7)


# Format gaps Track A / B must close (each pinned so the test flips when the gap closes): a file listed here may fail
# ONLY with problems matching its pattern.  None is open:
#   GAP-FIT7 and GAP-ANSWER-SENTENCE (an answer page too short for one sentence without Scrolling Popups) closed when the
#   collection's rows came to require Scrolling Popups (lead's decision, 2026-11-14): its popups are checked scrolling.
#   GAP-LABEL-NAME and GAP-LABELFIT closed with the engine's label name-to-pronoun fallback (decision 14).
#   GAP-VISITOR closed with the named stranger ({"kind": "stranger", "named": true}).
KNOWN_GAPS: dict[str, str] = {}


class CollectionFiles(unittest.TestCase):
    def test_every_file_passes(self):
        import re
        files = cc.collection_files()
        self.assertGreaterEqual(len(files), 10)
        rows = cc.manifest_rows()
        for p in files:
            with self.subTest(file=p.name):
                rep = cc.check_file(p, rows)
                gap = KNOWN_GAPS.get(p.name)
                if gap:
                    self.assertTrue(rep.problems, f"{p.name}: the gap is closed; remove it from KNOWN_GAPS")
                    self.assertEqual([x for x in rep.problems if not re.match(gap, x)], [])
                else:
                    self.assertEqual(rep.problems, [])
                if cc.engine() is None:
                    self.assertTrue(rep.skipped, "a and g must say SKIPPED while the v6 format is missing")

    def test_cli_runs(self):
        # The command line on a handful of files: every file is already checked by the subtests above, and the whole
        # collection again in a subprocess outran CI's 10-minute timeout.
        files = [str(p) for p in cc.collection_files() if p.name not in KNOWN_GAPS][:5]
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collection_check.py"), *files],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"{len(files)} of {len(files)} files pass", r.stdout)

    def test_v27_weights_follow_the_global_rule(self):
        # The lead's decisions (2026-11-14, the V27 global rule): a death is very rare (2 against 20), a minor setback
        # occasional (10), a disappearance or serious harm rare (5).
        seen = {"kill": 0, "minor": 0}
        for p in sorted((lib.COLLECTION_DIR / "v27").glob("*.json")):
            doc = json.loads(p.read_text(encoding="utf-8"))
            for nid, n in doc["nodes"].items():
                for k in n.get("children") or []:
                    target = doc["nodes"][k["next"]]
                    effs = target.get("effects") or []
                    with self.subTest(file=p.name, node=k["next"]):
                        if any(e["do"] == "kill" for e in effs):
                            seen["kill"] += 1
                            self.assertEqual((k.get("weight"), k.get("rarity")), (2, "very_rare"))
                        elif effs and all(e["do"] == "damage" or (e["do"] == "health_change" and e["min"] == -30)
                                          for e in effs):
                            seen["minor"] += 1
                            self.assertEqual((k.get("weight"), k.get("rarity")), (10, "occasional"))
                        elif any(e["do"] == "vanish" for e in effs):
                            self.assertEqual(k.get("weight"), 5)
        self.assertGreaterEqual(seen["kill"], 3)
        self.assertGreaterEqual(seen["minor"], 6)

    def test_shared_pools(self):
        self.assertEqual(cc.check_shared_pools(), [])

    def test_every_listed_grammar_fix_is_on_its_line(self):
        self.assertGreaterEqual(len(cc.grammar_doc_fixes()), 30)
        for source in lib.SOURCES:
            with lib.use_source(source):
                for n, before, after in cc.grammar_doc_fixes(source):
                    self.assertIn(before, lib.normalize_source_text(lib.line(n)), f"{source} L{n}")
                    self.assertNotEqual(before, after)

    def test_grammar_fixes_used_are_listed(self):
        rows = cc.manifest_rows()
        for p in cc.collection_files():
            doc = json.loads(p.read_text(encoding="utf-8"))
            source = cc.file_source(doc, rows)
            listed = cc.grammar_doc_fixes(source)
            with lib.use_source(source):
                for f in doc.get("grammar_fixes", []):
                    (n,) = lib.src_lines(f["src"])
                    self.assertIn((n, f["before"], f["after"]), listed, p.name)

    def test_companion_files_live_by_volume(self):
        rows = cc.manifest_rows()
        files = [p for p in cc.collection_files() if lib.COMPANION_DIR in p.parents]
        self.assertGreaterEqual(len(files), 78)                       # wave 1 chunk 1: Part 1 and Part 3 001-030
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(doc["collection"]["source"], lib.COMPANION_ID, p.name)
            self.assertEqual(rows[doc["collection"]["id"]]["source"], lib.COMPANION_ID, p.name)
            self.assertEqual(p.parent.parent, lib.COMPANION_DIR, p.name)

    def test_a_file_is_checked_against_its_own_source(self):
        """A companion file's src tags mean the companion's lines: under the Grand source they would not match."""
        p = lib.COMPANION_DIR / "c5" / "c5a001_kiln_secret.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(cc.check_file(p).problems, [])
        bad = copy.deepcopy(doc)
        bad["collection"]["source"] = lib.SOURCE_ID
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "c5" / p.name
            q.parent.mkdir()
            q.write_text(cc.canonical(bad), encoding="utf-8", newline="\n")
            self.assertTrue(problems(cc.check_file(q), "a SCHEMA"))

    def test_authoring_keys_never_reach_the_engine(self):
        for p in cc.collection_files():
            g = cc.graph_for_engine(json.loads(p.read_text(encoding="utf-8")))
            blob = json.dumps(g)
            for key in ('"src"', '"text_only"', '"rarity"', '"ledger"', '"title_src"',
                        '"inline_sets"'):
                self.assertNotIn(key, blob, p.name)
            for part in list(g["nodes"].values()) + list(g.get("pools", {}).values()):
                self.assertNotIn("set", part, p.name)   # a bank label ("set" on an effect is skill_set)


class ChecksRefuse(unittest.TestCase):
    """Each check bites: mutate the passing Gardening Contest and expect that check's problem."""

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(GARDENING.read_text(encoding="utf-8"))

    def doc(self):
        return copy.deepcopy(self.base)

    def test_base_passes(self):
        self.assertEqual(check_doc(self.doc()).problems, [])

    def test_changed_word(self):
        d = self.doc()
        d["nodes"]["s2"]["text"] = d["nodes"]["s2"]["text"].replace("curved path", "winding path")
        self.assertTrue(problems(check_doc(d), "b FIDELITY"))

    def test_added_word(self):
        d = self.doc()
        d["pools"]["A"]["items"][0]["text"] += " and bees"
        self.assertTrue(problems(check_doc(d), "b FIDELITY"))

    def test_dropped_word_is_unconsumed(self):
        d = self.doc()
        d["nodes"]["s4"]["text"] = d["nodes"]["s4"]["text"].replace(" They simplify it rather than overpromise.", "")
        rep = check_doc(d)
        self.assertTrue(any("L3077" in p for p in problems(rep, "c COVERAGE")), rep.problems)

    def test_dropped_item_changes_the_bank_size(self):
        d = self.doc()
        del d["pools"]["A"]["items"][5]
        rep = check_doc(d)
        self.assertTrue(problems(rep, "d TOKENS"))
        self.assertTrue(problems(rep, "c COVERAGE"))

    def test_unconsumed_line(self):
        d = self.doc()
        d["collection"]["ledger"] = [e for e in d["collection"]["ledger"] if e["src"] != "L3046"]
        self.assertTrue(any("L3046" in p for p in problems(check_doc(d), "c COVERAGE")))

    def test_unlisted_grammar_fix(self):
        d = self.doc()
        d["grammar_fixes"] = [{"src": "L3072", "before": "path's", "after": "paths'"}]
        d["nodes"]["s2"]["text"] = d["nodes"]["s2"]["text"].replace("path's", "paths'")
        self.assertTrue(any("grammar-fixes.md" in p for p in problems(check_doc(d), "b FIDELITY")))

    def test_unprefixed_pronoun(self):
        d = self.doc()
        d["pools"]["END"]["items"][4]["text"] = "(he/she) agrees"
        self.assertTrue(any("role-prefixed" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_chief_outside_vv3(self):
        d = self.doc()
        d["games"] = [3, 4]
        d["nodes"]["s2"]["text"] = "the Chief suggests"
        self.assertTrue(any("Chief" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_gloriously_offensive(self):
        d = self.doc()
        d["nodes"]["s3"]["text"] = "GLORIOUSLY OFFENSIVE"
        self.assertTrue(any("GLORIOUSLY" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_missing_effect(self):
        d = self.doc()
        d["nodes"]["s1"]["effects"] = []
        self.assertTrue(any("experience" in p for p in problems(check_doc(d), "e EFFECTS")))

    def test_food_needs_a_size(self):
        d = self.doc()
        d["nodes"]["p2"]["effects"] = [{"do": "food", "amount": 50, "scaled": True}]
        self.assertTrue(problems(check_doc(d), "e EFFECTS"))

    def test_skill_amount_off_table(self):
        d = self.doc()
        d["nodes"]["s1"]["effects"][0]["max"] = 25
        self.assertTrue(problems(check_doc(d), "e EFFECTS"))

    def test_unequal_weights_without_odds(self):
        d = self.doc()
        d["nodes"]["shared"]["children"][0]["weight"] = 3
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_rarity_weights(self):
        d = self.doc()
        kids = d["nodes"]["shared"]["children"]
        for k in kids:
            k["weight"] = 20
        kids[3]["rarity"], kids[3]["weight"] = "rare", 5
        self.assertEqual(problems(check_doc(d), "h CHANCES"), [])
        kids[3]["weight"] = 4
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_unreachable_node(self):
        d = self.doc()
        d["nodes"]["orphan"] = {"text": "{END}"}
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_harmed_special_role(self):
        d = self.doc()
        d["roles"]["gardener1"]["special"] = "tribal_chief"
        d["nodes"]["s1"]["effects"][0] = {"do": "kill", "role": "gardener1", "cause": "unknown", "src": "L3071"}
        self.assertTrue(problems(check_doc(d), "f SAFETY"))

    def test_die_unrecovered_is_always_unknown_causes(self):
        # The owner's rule: a death with no body is always "Unknown causes"; the checker refuses an author's cause.
        d = self.doc()
        d["nodes"]["s1"]["effects"][0] = {"do": "die_unrecovered", "role": "gardener1", "cause": "Drowned",
                                          "src": "L3071"}
        self.assertTrue(any("always \"Unknown causes\"" in p for p in problems(check_doc(d), "e EFFECTS")))
        d["nodes"]["s1"]["effects"][0]["cause"] = "unknown"
        self.assertFalse(any("always \"Unknown causes\"" in p for p in problems(check_doc(d), "e EFFECTS")))

    def test_harmed_role_allowing_protected(self):
        # The owner's model (2026-11-14, cie-v6-binary.md 7): "allow" on a harmed role is the author's choice, listed
        # by --allow-report for review; a harmed special role without it is refused.
        d = self.doc()
        d["roles"]["gardener1"]["protected"] = "allow"
        d["nodes"]["s1"]["effects"][0] = {"do": "health_change", "role": "gardener1", "min": -20, "max": -10,
                                          "src": "L3071"}
        self.assertFalse(problems(check_doc(d), "f SAFETY"))
        self.assertEqual([x[0] for x in cc.allow_on_harm(d)], ["gardener1"])
        d["roles"]["gardener1"]["protected"] = "auto"
        d["roles"]["gardener1"]["special"] = "tribal_chief"
        self.assertTrue(problems(check_doc(d), "f SAFETY"))

    def test_wrong_credit(self):
        d = self.doc()
        d["collection"]["credit"] = "someone else"
        self.assertTrue(problems(check_doc(d), "a SCHEMA"))

    def test_engine_seam_strips_authoring_keys(self):
        g = cc.graph_for_engine(self.doc())
        self.assertEqual(g["pools"]["A"]["items"][0], "neat rows with carefully labeled plants")
        self.assertNotIn("ledger", g["collection"])
        self.assertNotIn("text_only", g["nodes"]["p2"])
        self.assertNotIn("description", g["collection"])

    def test_missing_or_unplain_description(self):
        for bad in (None, "", "Two gardeners plan a garden", "(Gardener1) plans a garden.", "x" * 40 + ".",
                    "A gardener plans {A}.", "A" + " long" * 30 + "."):
            with self.subTest(bad=bad):
                d = self.doc()
                if bad is None:
                    del d["collection"]["description"]
                else:
                    d["collection"]["description"] = bad
                self.assertTrue(problems(check_doc(d), "i PICK"))

    def test_an_owner_title_must_be_the_new_title(self):
        rows = cc.manifest_rows()
        path = ROOT / "data" / "event_collection" / "exclusive" / "vv3_weather_dance_that_went.json"
        d = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(cc.check_file(path, rows).problems, [])
        self.assertEqual(d["title"], "The Wacky Weather Dance")
        d["title"] = "The Weather Dance That Went Wrong"           # the source heading: the owner renamed it
        self.assertTrue(problems(check_doc(d, "vv3_weather_dance_that_went", "exclusive"), "b FIDELITY"))

    def test_guardians_wording_is_required_in_new_believers(self):
        """j: blind to ids -- a New Believers text saying Heathen or convert needs its Guardians form."""
        path = ROOT / "data" / "event_collection" / "exclusive" / "vv5_convert_who_missed_home.json"
        base = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(check_doc(base, "vv5_convert_who_missed_home", "exclusive").problems, [])
        cases = {
            "title variant": lambda d: d.pop("title_variants"),
            "page variant": lambda d: d["nodes"]["question"].pop("variants"),
            "description variant": lambda d: d["collection"].pop("description_variants"),
            "wrong form": lambda d: d["nodes"]["question"]["variants"][0].update(text="A newcomer sits alone."),
        }
        for what, change in cases.items():
            with self.subTest(what=what):
                d = copy.deepcopy(base)
                change(d)
                self.assertTrue(problems(check_doc(d, "vv5_convert_who_missed_home", "exclusive"), "j GUARDIANS"))
        # a heathen word in a game-5 list item, which the format cannot vary by patch here
        d = copy.deepcopy(self.doc())
        d["games"] = [3, 5]
        d["pools"]["END"]["items"][0]["text"] = "A Heathen neighbour visits."
        self.assertTrue(problems(check_doc(d), "j GUARDIANS"))


class TextRegex(unittest.TestCase):
    def test_tokens(self):
        import re
        src = 'Then (he/she) (L) the (K) into a (J, different from the first J) (into/onto) (the Chief/a child).'
        words = {"chief": {"3": "the Chief", "*": "the village leader"}}
        for data in ['Then (cook.he/she) {L} the {K} into a {J.2} {into|onto} {{@chief}|a child}.']:
            self.assertRegex(src, cc.text_regex(data, words))
        self.assertIsNone(re.search(cc.text_regex("Then (x.he/she) {L} a {K}", {}), src))


if __name__ == "__main__":
    unittest.main()
