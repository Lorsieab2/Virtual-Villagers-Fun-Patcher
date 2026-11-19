"""Game Mechanics, all five games: "Village Solidarity" (scripts/build_village_solidarity_feature.py,
native/vvfp_village_solidarity, the story engine's native/vvfp_story_upgrades/story_solidarity.inc).

The score is read from the save's own Village Scores file (src/vv_village_scores.py), the rules from the companion's
code (the step, the clamp and the factor, pinned by tests/test_village_solidarity.py).  The stock games have no such
score: without the patch nothing is shown.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_village_scores as scores

FEATURE = {game: f"vv{game}{scores.SOLIDARITY_ROW_SUFFIX}" for game in range(1, 6)}

RULES = (f"{scores.SOLIDARITY_NAME}: 0 to 100, 50 at the start. A new event's page marked to raise it adds "
         f"{scores.STEP}, one marked to lower it takes {scores.STEP} away, a quiet page leaves it. It only changes "
         "odds: above 50 the new cooperative and celebration events and the cooperative endings are more likely, "
         "below 50 the new repair, peace and apology events and the tense endings (at the normal strength 2% more "
         "of their own chance for each point away from 50, so double at 0 or 100). The game's own island events, "
         "work, skills and health never change")


def lines(village: gm.Village) -> list[tuple[str, object]]:
    """The Village Solidarity lines for the Other group, only when the patch may be in."""
    if village.has(FEATURE[village.game]) is False:
        return []
    out: list[tuple[str, object]] = [(gm.patch_words(village, FEATURE[village.game], RULES), gm.CODE)]
    if not village.general:
        values = scores.read_scores(village.folder, village.slot)
        score = (values or {}).get(scores.SOLIDARITY_NAME)
        out.append((f"{scores.SOLIDARITY_NAME} now: {score} / 100." if score is not None else
                    f"{scores.SOLIDARITY_NAME} now: 50 / 100 (no change has been saved for this village yet).",
                    gm.SAVE))
    return out
