"""Game Mechanics, all five games: "Village Solidarity" (scripts/build_village_solidarity_feature.py,
native/vvfp_village_solidarity, the story engine's native/vvfp_story_upgrades/story_solidarity.inc).

The score is read from the save's own Village Scores file (src/vv_village_scores.py), the rules from the companion's
code (the step, the clamp and the factor, pinned by tests/test_village_solidarity.py).  The stock games have no such
score: without the patch nothing is shown.
"""
from __future__ import annotations

import vv_game_mechanics as gm
import vv_stock_event_solidarity as stock
import vv_village_scores as scores

FEATURE = {game: f"vv{game}{scores.SOLIDARITY_ROW_SUFFIX}" for game in range(1, 6)}

RULES = (f"{scores.SOLIDARITY_NAME}: 0 to 100, 50 at the start. A new event's page marked to raise it adds "
         f"{scores.STEP}, one marked to lower it takes {scores.STEP} away, a quiet page leaves it. It only changes "
         "chance weights: above 50 the new cooperative and celebration events and the cooperative endings, below 50 "
         "the new repair, peace and apology events and the tense endings, each get 2% more of their own chance "
         "weight for each point away from 50 at the normal strength (double at 0 or 100); no other weight changes. "
         "The game's own island events, work, skills and health never change")


def stock_rule(game: int) -> str:
    """The game's own island events move the score too (the owner, 2026-11-20): each result by its tag."""
    count = stock.counts()[game]
    total = sum(count.values())
    return (f"The game's own island events move it too, once for each result shown, by the owner's tag for that "
            f"result: of this game's {total} results, {count['RAISE']} raise it by {scores.STEP} (gains, healing, "
            f"newcomers, celebrations), {count['LOWER']} lower it by {scores.STEP} (losses, sickness, deaths, "
            f"disasters) and {count['NEUTRAL']} leave it. This only moves the score: those events and their chances "
            "stay exactly the game's own")


def lines(village: gm.Village) -> list[tuple[str, object]]:
    """The Village Solidarity lines for the Other group, only when the patch may be in."""
    if village.has(FEATURE[village.game]) is False:
        return []
    out: list[tuple[str, object]] = [(gm.patch_words(village, FEATURE[village.game], RULES), gm.CODE),
                                     (gm.patch_words(village, FEATURE[village.game], stock_rule(village.game)),
                                      gm.CODE)]
    if not village.general:
        values = scores.read_scores(village.folder, village.slot)
        score = (values or {}).get(scores.SOLIDARITY_NAME)
        out.append((f"{scores.SOLIDARITY_NAME} now: {score} / 100." if score is not None else
                    f"{scores.SOLIDARITY_NAME} now: 50 / 100 (no change has been saved for this village yet).",
                    gm.SAVE))
    return out
