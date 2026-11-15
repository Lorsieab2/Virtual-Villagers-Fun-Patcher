"""Write the owner's "Role Models and Good Examples — 40 New Isola Events" (RM-01..RM-40) as collection events, then
format and check them:
  RM-01..RM-40   one event per line                                 rolemodels L5-83 (rm)
The shape and the helpers are scripts/horizon_rm/hzrm_common.py's (the whole event is on one line: each page's text
is its part of that line).

THE AUTHORING RECORD (the owner's rules, the lead's brief of 2026-11-15):
- Text verbatim (four choices A-D, two outcomes each; one of the two is drawn, equally likely).  No sensitivity edits:
  nothing names a word the owner listed for change, and no modern technology appears.  No grammar fixes: none is
  glaring.
- The text names nobody: roles carry no token.  Each event casts the one villager the scene needs (cast_only), or the
  one a small skill gain lands on.
- Effects only where natural (the lead: "small effects only where natural"): the outcome's own words name the
  learning --
    RM-11 B1  "gains a little building experience"            the apprentice: small Building
    RM-25 A1  "gains a little building experience"            the apprentice: small Building
    RM-17 A1  "the apprentice learns a safer checking routine"  the healer's apprentice: small Healing
    RM-36 A2  "a parent patiently demonstrates the task again"  the parent: small Parenting
  Nothing else changes the game: no harm anywhere (every outcome is a success, a compromise, a delay or an imperfect
  resolution, as the closing note says); food gathered for a family's supper, shared or not found stays the family's
  story, not the village's stores.
- Games: every game.  No text names a chief, Heathens or conversion (RM-32's "village leader" is the text's own word).

    python scripts/horizon_rm/gen_rm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hzrm_common as c  # noqa: E402

V, GROWN = c.VILLAGER, c.GROWN
T, sk = c.T, c.sk
HOUSEHOLD = "food shared, counted, gathered or eaten in the story; the village's stores do not change"
FOOD = T('"food"', HOUSEHOLD)
FEAST = T('"celebration"', "a celebration mentioned in the story; no celebration happens in the game")

# RM-NN: ({role: spec}, description or None (the setup), opts)
DEFAULT = ({"villager": V}, None, {})
RM: dict[int, tuple] = {
    1: ({"villager": V}, None, {"to": {0: [FOOD]}}),
    7: ({"villager": V}, None, {"to": {"a2": [FOOD]}}),
    9: ({"villager": V}, None,
        {"to": {"c2": [T('"skill"', "\"skill\" in its everyday sense (what a teacher can do), not a skill gain")]}}),
    11: ({"apprentice": V}, None, {"fx": {"b1": [sk("apprentice", "Building")]}}),
    13: ({"villager": V}, None, {"to": {0: [FEAST]}}),
    16: ({"villager": V}, None, {"to": {"c1": [FOOD]}}),
    17: ({"apprentice": V}, None, {"fx": {"a1": [sk("apprentice", "Healing")]}}),
    18: ({"villager": V}, None, {"to": {"b2": [FOOD]}}),
    23: ({"villager": V}, None, {"to": {0: [FOOD, FEAST]}}),
    25: ({"apprentice": V}, None, {"fx": {"a1": [sk("apprentice", "Building")]}}),
    32: ({"villager": V},
         "A village leader proposes changing the work schedule, but several villagers worry about their family "
         "responsibilities.", {}),
    34: ({"villager": V}, None, {"to": {0: [FOOD], "a1": [FOOD]}}),
    36: ({"parent": GROWN}, None, {"fx": {"a2": [sk("parent", "Parenting")]}}),
    37: ({"villager": V}, None, {"to": {"a2": [FOOD], "d1": [FOOD]}}),
    39: ({"villager": V},
         "Several friends once agreed to keep a favorite stretch of beach clean, but their visits have become less "
         "frequent.", {}),
    40: ({"villager": V},
         "A quiet villager finds a damaged basket, scattered seeds and a loose stone beside a path after everyone has "
         "gone home.", {}),
}


def main() -> int:
    rows = c.rows(c.lib.ROLEMODELS_ID, "rm")
    assert [c.num_of(r) for r in rows] == list(range(1, 41))
    docs = []
    for r in rows:
        roles, desc, opts = RM.get(c.num_of(r), DEFAULT)
        docs.append((c.lib.ROLEMODELS_DIR / "rm" / f"{r['id']}.json", c.build_rm(r, roles, desc, opts)))
    return c.write_and_check(docs)


if __name__ == "__main__":
    sys.exit(main())
