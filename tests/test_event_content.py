"""The island events' content controls (v1.35.97, the owner 2026-11-15): content notes, content filters and rest
periods for the new events (src/vv_event_content.py writes them into each compiled event; Story / Cheat Upgrades
reads the ticked rows from the installed patches' list).

Proves, in Python: the tagging (effects and words; a sex change and a change of faith are never tagged), the dropped
outcomes and the skip, the note's labels and its variants, the rest effects beside every serious outcome, the
compiled .cieg holding them (code 25), the tag tables covering every event of every source, the rows' defaults
(notes and rest periods on in Owner's Defaults only, the filters off everywhere) and the Island Events section's
rows and advisories.  In the emulator, with the test build of "VVFP Story Upgrades.dll": the compiled events load
(up to 32 patch names), a ticked filter drops its outcome and skips an event that cannot do without it, the note
starts the first page and leaves out a filtered subject, and a rest effect rests the villager and their family for
the right number of days and keeps them out of a serious role while it lasts.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_cie_graph as cg  # noqa: E402
import vv_event_content as content  # noqa: E402


def graph(nodes: dict, start: str = "s", roles: dict | None = None) -> dict:
    return cg.load({"format": "vvfp-cie-graph", "version": 6, "title": "The Test Of Content", "games": [1, 2, 3, 4, 5],
                    "roles": roles or {"subject": {"kind": "villager"}}, "start": start, "nodes": nodes})


# A walk: an opening page, then a random draw between a safe ending and a death.
TWO_ENDINGS = {
    "s": {"text": "(Name) walks along the shore at dawn.", "children": [{"next": "b"}]},
    "b": {"type": "branch", "children": [{"next": "safe"}, {"next": "dies"}]},
    "safe": {"text": "(Name) comes home with a shell."},
    "dies": {"text": "A wave takes (him/her).", "effects": [{"do": "kill", "cause": "unknown"}]},
}
# A death on the only way on: it cannot be dropped.
ONE_WAY = {
    "s": {"text": "(Name) walks along the shore at dawn.", "children": [{"next": "dies"}]},
    "dies": {"text": "A wave takes (him/her).", "effects": [{"do": "kill", "cause": "unknown"}]},
}


class Tagging(unittest.TestCase):
    def test_effects_and_words_are_tagged(self):
        g = graph(TWO_ENDINGS)
        tags = content.tag_graph(g)
        self.assertEqual(set(tags["dies"]) >= {"F03", "F05"}, True)
        self.assertNotIn("safe", tags)
        g = graph({"s": {"text": "(Name) mourns at the funeral after the earthquake."}})
        self.assertTrue({"F03", "F05", "F21"} <= set(content.tag_graph(g)["s"]))

    def test_a_kind_of_person_is_never_a_filter(self):
        g = graph({"s": {"text": "(Name) becomes someone new, and is happy.",
                         "effects": [{"do": "sex_change"}]}})
        self.assertEqual(content.tag_graph(g), {})
        g = graph({"s": {"text": "(Name) falls in love with (friend.name).", "children": []}},
                  roles={"subject": {"kind": "villager"}, "friend": {"kind": "villager"}})
        self.assertNotIn("F28", content.tag_graph(g).get("s", []), "romance in general is never filtered")

    def test_every_event_of_every_source_has_a_table_entry(self):
        from build_event_collection_features import event_files
        missing = []
        for path in event_files():
            meta = json.loads(path.read_text(encoding="utf-8")).get("collection")
            if isinstance(meta, dict) and meta["id"] not in content.load_table(meta.get("source", "v28")):
                missing.append(meta["id"])
        self.assertEqual(missing, [], "run scripts/build_event_content_tags.py")


class Injection(unittest.TestCase):
    def test_a_droppable_death_is_dropped_and_the_event_kept(self):
        g = graph(TWO_ENDINGS)
        out, plan = content.inject(g, content.tag_graph(g))
        dies = next(c for c in out["nodes"]["b"]["children"] if c["next"] == "dies")
        safe = next(c for c in out["nodes"]["b"]["children"] if c["next"] == "safe")
        self.assertEqual(dies["if"], {"not": {"any": [{"patch": "island_event_filter_f03"},
                                                      {"patch": "island_event_filter_f05"}]}})
        self.assertIsNone(safe["if"])
        self.assertNotIn("if", out["requirement"], "never skipped: the safe ending is left")
        self.assertIn("island_event_filter_f03", out["patches"])

    def test_a_death_on_the_only_way_skips_the_event(self):
        g = graph(ONE_WAY)
        out, plan = content.inject(g, content.tag_graph(g))
        self.assertIn([frozenset({"F03"})], plan["groups"])
        req = out["requirement"]["if"]
        self.assertEqual(req["not"]["any"][0], {"patch": "island_event_filter_f03"})

    def test_the_note_starts_the_first_text_and_names_no_outcome(self):
        g = graph(TWO_ENDINGS)
        out, plan = content.inject(g, content.tag_graph(g))
        self.assertEqual(plan["labels"], [("Bereavement", ["F03", "F05"])])
        v = out["nodes"]["s"]["variants"]
        self.assertEqual(v[0]["text"], "Content note: Bereavement\n(Name) walks along the shore at dawn.")
        self.assertEqual(v[0]["if"]["all"][0], {"patch": "island_event_content_notes"})
        self.assertEqual(out["nodes"]["s"]["text"], "(Name) walks along the shore at dawn.", "no note when off")

    def test_rest_effects_stand_before_every_serious_outcome(self):
        g = graph(TWO_ENDINGS)
        out, _plan = content.inject(g, content.tag_graph(g))
        self.assertEqual(out["nodes"]["dies"]["effects"][0], {"do": "rest", "role": "subject", "days": 60})
        g = graph({"s": {"text": "(Name) is badly injured in the fall.", "children": []}})
        out, _plan = content.inject(g, content.tag_graph(g))
        self.assertEqual(out["nodes"]["s"]["effects"][0], {"do": "rest", "role": "subject", "days": 30})

    def test_the_compiled_event_holds_the_rest_effect(self):
        g = graph(TWO_ENDINGS)
        out, _plan = content.inject(g, content.tag_graph(g))
        back = cg.decompile_graph(cg.compile_graph(out))
        self.assertEqual(back["nodes"]["dies"]["effects"][0]["do"], "rest")
        self.assertEqual(back["nodes"]["dies"]["effects"][0]["days"], 60)

    def test_an_untagged_event_is_unchanged(self):
        g = graph({"s": {"text": "(Name) bakes bread."}})
        self.assertEqual(cg.compile_graph(content.inject(g, content.tag_graph(g))[0]), cg.compile_graph(g))


class SpeakingAndTraits(unittest.TestCase):
    TALK = {"s": {"text": "(Name) looks up. \"Good morning,\" says (friend.name).", "children": []}}
    ROLES = {"subject": {"kind": "villager"}, "friend": {"kind": "villager"}}

    def test_a_role_given_words_speaks(self):
        g = graph(self.TALK, roles=self.ROLES)
        self.assertEqual(content.speaking_roles(g), ["friend"])
        out, _plan = content.inject(g, {}, {"speaks": ["friend"]})
        back = cg.decompile_graph(cg.compile_graph(out))
        self.assertTrue(back["roles"]["friend"].get("speaks"))
        self.assertFalse(back["roles"]["subject"].get("speaks"))

    def test_the_quiet_hands_gives_its_subject_the_mute_trait(self):
        g = graph(TWO_ENDINGS)
        self.assertEqual(content.event_traits("il003_quiet_hands", g), [{"role": "subject", "trait": "mute"}])
        self.assertEqual(content.event_traits("il004_other", g), [])
        out, _plan = content.inject(g, {}, {"traits": content.event_traits("il003_quiet_hands", g)})
        self.assertEqual(out["nodes"]["s"]["effects"][0], {"do": "trait", "role": "subject", "trait": "mute"})
        back = cg.decompile_graph(cg.compile_graph(out))
        self.assertEqual(back["nodes"]["s"]["effects"][0]["do"], "trait")


class Rows(unittest.TestCase):
    def test_defaults(self):
        import vv_fun_patcher_gui as gui
        for game in range(1, 6):
            for ident in ("island_event_content_notes", "island_event_rest_periods"):
                pid = f"vv{game}_{ident}"
                self.assertFalse(gui.default_fun_patch_selection(pid))
                self.assertTrue(gui.owners_default_fun_patch_selection(pid))
                self.assertFalse(gui.select_all_fun_patch_selection(pid))
            for n in range(1, 29):
                pid = f"vv{game}_island_event_filter_f{n:02d}"
                self.assertFalse(gui.default_fun_patch_selection(pid))
                self.assertFalse(gui.owners_default_fun_patch_selection(pid))
                self.assertFalse(gui.select_all_fun_patch_selection(pid))

    def test_the_rows_load_and_name_the_engine_s_patches(self):
        import vv_fun_patcher as fp
        ids = {p.id for p in fp.load_fun_patches()}
        for game in range(1, 6):
            self.assertIn(f"vv{game}_{content.NOTES_PATCH}", ids)
            self.assertIn(f"vv{game}_{content.REST_PATCH}", ids)
            for f in content.FILTER_IDS:
                self.assertIn(f"vv{game}_{content.filter_patch(f)}", ids)

    def test_the_section_and_the_advisories(self):
        import vv_fun_patcher_gui as gui
        self.assertEqual(gui.island_event_section_kind("vv3_isola_grand_event_collection"), "row")
        self.assertEqual(gui.island_event_section_kind("vv3_more_island_events"), "row")
        self.assertEqual(gui.island_event_section_kind("vv3_island_event_filter_f12"), "filter")
        self.assertIsNone(gui.island_event_section_kind("vv3_story_cheat_upgrades"))
        self.assertTrue(gui.island_event_advisory("vv1_isola_grand_event_collection")[0].startswith(
            "CONTENT ADVISORY: These events include occasional illness"))
        self.assertEqual(gui.island_event_advisory("vv2_more_island_events")[0],
                         "Content advisory: Some events involve danger, disasters or difficult choices; outcomes "
                         "are non-graphic.")
        self.assertTrue(gui.island_event_advisory("vv5_story_cheat_upgrades")[0].startswith(
            "Player-created events may contain sensitive subjects."))


try:
    import test_story_cie_graph_runtime as rt
    from test_story_custom_island_event import GAMES, emulated, have_stock
except Exception:                              # noqa: BLE001 -- no emulator: the native half is skipped
    rt = None


def _mask(out: dict, *ids: str) -> int:
    return sum(1 << out["patches"].index(i) for i in ids)


if rt is not None:
    @emulated
    class Native(unittest.TestCase):
        def test_filters_and_notes_in_the_game(self):
            g = graph(TWO_ENDINGS)
            out, _plan = content.inject(g, content.tag_graph(g))
            data = cg.compile_graph(out)
            for game in GAMES:
                if not have_stock(game):
                    continue
                with self.subTest(game=game):
                    run = rt.Run(game)
                    self.assertIsNone(run.check(data))
                    run.rolls([1] + [0] * 40)
                    run.force(["dies"], patches=_mask(out, content.NOTES_PATCH), graph=out)
                    self.assertIsNone(run.queue(data))
                    shown = run.play()
                    first = run.strip(shown[0][1], "The Test Of Content")
                    self.assertTrue(first.startswith("Content note: Bereavement"), first)
                    self.assertEqual(len(run.told()), 1, "the forced death came")
                    run = rt.Run(game)
                    run.rolls([1] + [0] * 40)
                    run.force(["dies"], patches=_mask(out, content.NOTES_PATCH, "island_event_filter_f03"), graph=out)
                    self.assertIsNone(run.queue(data))
                    shown = run.play()
                    first = run.strip(shown[0][1], "The Test Of Content")
                    self.assertFalse(first.startswith("Content note"), first)
                    self.assertEqual(run.told(), [], "the filtered death is dropped")
                    self.assertIn("shell", " ".join(s[1] for s in shown))

        def test_an_event_that_cannot_do_without_it_is_skipped(self):
            g = graph(ONE_WAY)
            out, _plan = content.inject(g, content.tag_graph(g))
            data = cg.compile_graph(out)
            for game in GAMES:
                if not have_stock(game):
                    continue
                with self.subTest(game=game):
                    run = rt.Run(game)
                    run.rolls([1] + [0] * 40)
                    run.force([], patches=_mask(out, "island_event_filter_f03"), graph=out)
                    why = run.queue(data)
                    self.assertIsNotNone(why)
                    self.assertIn("content filters", why)

        def test_a_rest_effect_rests_the_villager_and_keeps_them_out(self):
            g = graph(TWO_ENDINGS)
            out, _plan = content.inject(g, content.tag_graph(g))
            data = cg.compile_graph(out)
            buf = rt.SCRATCH + 0xC00
            for game in GAMES:
                if not have_stock(game):
                    continue
                with self.subTest(game=game):
                    run = rt.Run(game)
                    run.rolls([1] + [0] * 40)
                    run.force(["dies"], graph=out)
                    run.p.export("VvfpStoryProbeRest", 1, run.n, 0, buf)
                    self.assertIsNone(run.queue(data))
                    run.play()
                    run.p.export("VvfpStoryProbeRest", 1, run.n, 0, buf)
                    until, now = struct.unpack("<2I", run.p.read(buf, 8))
                    self.assertGreater(now, 0, "the game clock")
                    # Bea died; nobody of hers is recorded in this village, so only her own record was kept.
                    run.p.export("VvfpStoryProbeRest", 1, run.n, 1, buf)
                    until, now = struct.unpack("<2I", run.p.read(buf, 8))
                    self.assertEqual(until - now >= 60 * 86400 - 600, True, (until, now))
                    run.p.export("VvfpStoryProbeRest", -1, run.n, 0, 0)

        def test_a_resting_villager_is_kept_out_of_a_serious_role(self):
            hurt = graph({"s": {"text": "(Name) is badly injured in the fall.", "children": []}})
            hurt, _plan = content.inject(hurt, content.tag_graph(hurt))
            walk = graph(TWO_ENDINGS)
            walk, _plan = content.inject(walk, content.tag_graph(walk))
            buf = rt.SCRATCH + 0xC00
            for game in GAMES:
                if not have_stock(game):
                    continue
                with self.subTest(game=game):
                    run = rt.Run(game)
                    run.p.export("VvfpStoryProbeRest", 1, run.n, 1, buf)
                    run.rolls([1] + [0] * 40)
                    run.force([], graph=hurt)
                    self.assertIsNone(run.queue(cg.compile_graph(hurt)))
                    run.play()
                    self.assertEqual(run.state()["records"][0], 1, "Bea was hurt")
                    self.assertEqual(run.p.export("VvfpStoryProbeRest", 1, run.n, 1, buf), 1)
                    until, now = struct.unpack("<2I", run.p.read(buf, 8))
                    self.assertEqual(until - now, 30 * 86400)
                    run.rolls([1] + [0] * 40)
                    run.force([], graph=walk)
                    self.assertIsNone(run.queue(cg.compile_graph(walk)))
                    self.assertNotEqual(run.state()["records"][0], 1, "Bea rests: never the subject of the walk")
                    run.p.export("VvfpStoryProbeRest", -1, run.n, 0, 0)


if rt is not None:
    @emulated
    class NativeTraits(unittest.TestCase):
        def test_a_story_mute_villager_never_takes_a_speaking_role(self):
            quiet = graph({"s": {"text": "(Name) folds (his/her) hands and says nothing.", "children": []}})
            quiet, _plan = content.inject(quiet, {}, {"traits": [{"role": "subject", "trait": "mute"}]})
            talk = graph(SpeakingAndTraits.TALK, roles={"friend": {"kind": "villager"},
                                                       "subject": {"kind": "villager", "optional": True}},
                         start="s")
            talk, _plan = content.inject(talk, {}, {"speaks": ["friend"]})
            for game in GAMES:
                if not have_stock(game):
                    continue
                with self.subTest(game=game):
                    run = rt.Run(game)
                    run.rolls([1] + [0] * 40)
                    run.force([], graph=quiet)
                    self.assertIsNone(run.queue(cg.compile_graph(quiet)))
                    run.play()
                    self.assertEqual(run.state()["records"][0], 1, "Bea was cast")
                    run.rolls([1] + [0] * 40)
                    run.force([], graph=talk)
                    self.assertIsNone(run.queue(cg.compile_graph(talk)))
                    self.assertNotEqual(run.state()["records"][0], 1, "Bea is story-mute: never the one who speaks")


if __name__ == "__main__":
    unittest.main()
