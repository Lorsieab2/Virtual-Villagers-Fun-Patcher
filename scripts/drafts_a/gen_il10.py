"""Write the owner-approved draft "New Events - Inner Life Part X" (events 181-200) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit, no grammar fix.  191's "old
now, or gone" is a plain, gentle mention of death (the draft's note).  Effects as the draft's brackets: 192 A (name1)
celebrates.  Nothing else changes in the game.

Casting:
  181  "the oldest villager, an elder": cast an elder; the text ("now the oldest person in the village") is kept as
       written (the caller's ruling; the draft's note allows any elder).
  182  the child says "(he/she) is six": cast a child aged exactly 6 so the text holds (casting only, text unchanged).
  185, 190, 195  two elders: (name2) cast as an elder (the casting line's parse gave an adult).
  196  "an elder couple, partners as the game records them": (name2) an elder recorded as (name1)'s spouse
       (spouse_of), so the child's "But you're married" holds; text kept as written.
The owner's naming rule (2026-11-15), "cast" edits: a single person present in the scene, named only by role, is a
cast villager named at the first mention: 184 the watching child, 186 the child who calls, 187 "another elder", 189
the child with the bowl, 195 "another elder", 196 the visiting child, 198 the passing child.  Left alone: 189 B's
"a child who is now a grandparent" (only remembered through a toy, not present), 198 B's friend who helped (a
memory), groups (the children, the grown-ups, the elders).
Flag (no edit): 187 and 193 say the elder has known / believed something "for sixty years", and 185/190 speak of
fifty years; an elder is cast 55+, so a young elder makes these a little generous.  Kept as story.

    python scripts/drafts_a/gen_il10.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il10"
TABLE: dict[int, dict] = {
    181: {"note": "cast an elder; the text's \"the oldest person in the village\" kept as written",
          "desc": "An elder realizes over breakfast that they are now the oldest person in the village."},
    182: {"roles": {"subject": c.ELDER, "friend": c.ages(6, 6)},
          "note": "the child is cast aged 6 (the text: \"though (he/she) is six\")",
          "pron": {"a": {0: "subject"}},
          "desc": "A child asks an elder how old they are, and the elder realizes they do not know: let the child guess, or pick one."},
    183: {"pron": {"a_label": "friend", "a": {0: "subject"}},
          "desc": "The best napper in the village finds a very small child already asleep in the shade: lie down too, or admit defeat."},
    184: {"roles": {"subject": c.ELDER, "child": c.CHILD},
          "cast": [(50, "A watching child laughs", "(child), a watching child, laughs")],
          "desc": "An elder thinks about the little things they never got round to: do one of them today, or let some stay undone."},
    185: {"roles": {"subject": c.ELDER, "friend": c.ELDER},
          "desc": "Two elders have competed for fifty years to grow the biggest melon, and this year one melon is enormous."},
    186: {"roles": {"subject": c.ELDER, "child": c.CHILD},
          "cast": [(71, "Then a child calls", "Then (child), a child, calls")],
          "pron": {"setup": {3: "subject"}},
          "desc": "An elder sitting in the sun looks down at their own old hands, and thinks of everything they have done."},
    187: {"roles": {"subject": c.ELDER, "friend": c.YOUNG_ADULT, "elder": c.ELDER},
          "cast": [(83, "asking another elder", "asking (elder), another elder,")],
          "pron": {"setup": {0: "friend"}},
          "desc": "An elder gives a young villager advice about a fishing line with total confidence, and it goes very wrong."},
    188: {"pron": {"setup": {1: "subject"}},
          "desc": "An elder wakes up grumpy for no reason, and a cheerful villager arrives with a flower, a joke and some fruit."},
    189: {"roles": {"subject": c.ELDER, "child": c.CHILD},
          "cast": [(104, "sees a child walking", "sees (child), a child, walking")],
          "desc": "An elder's hut is so full of things that it is time for a change: give some away, or tidy and keep everything."},
    190: {"roles": {"subject": c.ELDER, "friend": c.ELDER},
          "desc": "Two elders who have barely ever talked wait out a rain shower together and find they share a sense of humor."},
    191: {"desc": "An elder who cannot sleep looks up at the stars, the same stars they watched as a child."},
    192: {"desc": "An elder who used to swim every day watches the children in the shallows: wade in, or just dip their feet."},
    193: {"desc": "An elder learns that two kinds of bird they have talked about for sixty years are really one kind."},
    194: {"pron": {"setup": {0: "subject", 1: "friend"}},
          "desc": "A villager thanks an elder for something wise they said years ago, and the elder does not remember saying it."},
    195: {"roles": {"subject": c.ELDER, "friend": c.ELDER, "elder": c.ELDER},
          "cast": [(167, "another elder.", "(elder), another elder.")],
          "desc": "An elder who wakes before dawn finds other elders by the embers, and a little early club begins."},
    196: {"roles": {"subject": c.ELDER, "friend": c.related(c.ELDER, "spouse_of", "subject"), "child": c.CHILD},
          "cast": [(179, "Today a visiting child watches", "Today (child), a visiting child, watches")],
          "pron": {"a": {0: "child"}},
          "note": "an elder couple as the game records them (spouse_of); text kept as written",
          "desc": "An elder couple have argued for years about how to fold the sleeping blanket, and a child asks why."},
    197: {"desc": "An elder who still feels thirty-five catches their reflection in the stream and does not recognize it."},
    198: {"roles": {"subject": c.ELDER, "child": c.CHILD},
          "cast": [(206, "tells a passing child", "tells (child), a passing child")],
          "desc": "An elder stops beside the garden wall they helped build forty years ago and finds it is still standing."},
    199: {"desc": "An elder has started collecting fallen feathers late in life: show a friend the collection, or keep it private."},
    200: {"desc": "An elder sits outside at sunset and looks back over the whole of their life, without needing a verdict."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
