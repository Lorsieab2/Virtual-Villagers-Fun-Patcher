"""Write the owner's "Isola - Beyond the Horizon" companion anthology (EVENT 001-080) as collection events, then
format and check them:
  EVENT 001-040  The World We Imagine (PARTs I-V)                   horizon L23-524  (hz_world)
  EVENT 041-080  Expansion Volume II: The Constructs, the Cities...  horizon L587-1065 (hz_vol2)
The shape and the helpers are scripts/horizon_rm/hzrm_common.py's.

THE AUTHORING RECORD (the owner's rules, the lead's brief of 2026-11-15):
- Text verbatim.  No sensitivity edits (the owner, 2026-11-15: the newest sources, Beyond the Horizon among them,
  "need NO wording edits"; "broadcast" in event 036 stays).  No grammar fixes: none is glaring.
- Every statement about distant peoples stays the villagers' speculation, as written; nothing confirms an outside
  world, and no event spawns anyone.
- The text names nobody: roles carry no token.  Each event casts the one villager the scene needs (cast_only); the
  two outcomes with a reward cast a villager skilled in it.
- Effects only where the text gives one (the source: "Rewards, where given, should be small"): 009 A1 "small Building
  experience" and 018 A1 "modest Research experience" (a small skill gain, the words cut as an instruction).  No
  harm anywhere: every outcome is talk, imagination or a small harmless trial.  The effect-table words that change
  nothing (food imagined, an imagined injury, a feeling of dislike, a celebration discussed) get text_only reasons.
- Games: every game.  The VV3 note on event 026 (the Tribal Chief only observes) holds by itself: no event casts or
  changes the Chief.  No VV5 text names Heathens or conversion (the flavor note about the two communities is a notes
  row), so no Guardians of Isola form is needed.
- Series: each PART of volume I is one series, and Expansion Volume II is one (collection_manifest.HORIZON_SERIES).

    python scripts/horizon_rm/gen_hz.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hzrm_common as c  # noqa: E402

V = c.VILLAGER
BUILDER = c.skilled(V, "Building")
SCHOLAR = c.skilled(V, "Research")
T, sk = c.T, c.sk
IMAGINED = "imagined or discussed only: nothing in the village changes"

# EVENT NNN: ({role: spec}, description or None (the setup or its first sentence), opts)
DEFAULT = ({"villager": V}, None, {})
HZ: dict[int, tuple] = {
    9: ({"builder": BUILDER},
        "A builder asks whether distant people might live in dwellings built above one another.",
        {"fx": {"a1": [sk("builder", "Building")]}, "instr": {"a1": "; small Building experience"}}),
    18: ({"scholar": SCHOLAR}, None,
         {"fx": {"a1": [sk("scholar", "Research")]}, "instr": {"a1": "; modest Research experience"}}),
}
# Pick Island Event's sentence where the setup is longer than one plain sentence of 130 characters: the setup's own
# words, shortened.
DESCRIPTIONS = {
    4: "After two neighbors dispute a borrowed basket, a mediator asks whether faraway people quarrel over ordinary "
       "things.",
    5: "A young villager wonders whether distant peoples remember their dead with songs, silence, flowers or stories.",
    7: "Watching an elder mend a net, an apprentice asks whether people in distant lands also grow old.",
    8: "A musician wonders what distant people celebrate and whether their festivals also go wrong.",
    12: "A fisher wonders whether distant people might spend their days doing work that produces nothing visible.",
    15: "A sanitation worker asks how an imagined city of thousands could keep its water and streets clean.",
    19: "A healer asks whether distant physicians might have tools for observing things too small for the naked eye.",
    25: "Watching the moon rise, a child asks whether distant peoples might someday send travelers beyond the sky.",
    28: "After a respected craftsperson breaks a village rule, a child asks whether powerful people obey their own "
        "laws.",
    30: "An elder asks whether people beyond the sea might look every imaginable way, or resemble Isolans closely.",
    31: "A teenager wonders whether a distant city might offer opportunities unavailable on Isola.",
    37: "A drummer asks whether distant people make unimagined music, and whether they still sing to children at "
        "bedtime.",
    39: "A researcher asks whether distant inventions make life easier while creating problems no one expected.",
    40: "As the sun sets, a child asks whether someone on a distant shore might be wondering about the islanders.",
    41: "A carver wonders whether distant craftspeople could assemble a figure that walks and obeys without a living "
        "body.",
    42: "A storyteller proposes that a distant people might build a speaking figure and claim a spirit lives within it.",
    71: "A gardener wonders whether distant societies could change forests, air and seas so much that the weather "
        "changes.",
    75: "A parent wonders whether distant people raise children in households of many shapes.",
    80: "After every theory of towers and machines, a child asks whether an unknown family might simply be cooking "
        "supper.",
}


def main() -> int:
    docs = []
    for section, first, last in (("hz_world", 1, 40), ("hz_vol2", 41, 80)):
        rows = c.rows(c.lib.HORIZON_ID, section)
        assert [c.num_of(r) for r in rows] == list(range(first, last + 1)), section
        for r in rows:
            roles, desc, opts = HZ.get(c.num_of(r), DEFAULT)
            desc = desc or DESCRIPTIONS.get(c.num_of(r))
            docs.append((c.lib.HORIZON_DIR / section / f"{r['id']}.json", c.build_hz(r, roles, desc, opts)))
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
