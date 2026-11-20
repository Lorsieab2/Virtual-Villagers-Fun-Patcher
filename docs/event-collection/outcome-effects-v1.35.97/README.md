# Outcome effects pass (v1.35.97)

This pass gives the patcher's added island events the game effects their own outcome text suggests. It follows the
owner's request to "go look at the vanilla island events and emulate how those work", and the owner's follow-ups of
2026-11-18:

- Add an effect wherever the text even suggests one.
- Each added effect happens half the time.
- The popup ends with a plain line saying what happened, with the amount.

No event text, title or choice changed.

## How the stock island events behave

Sources: `src/vv_game_mechanics_events_vv1.py` ... `vv5.py`, `docs/story-island-outcomes.md`.

- **Food and tech from found things.** VV1/VV2 crates give +500/+1,000/+1,500 food or tech points by strength, and
  vials give tech. VV3 fog gives or takes 300 food. VV4/VV5 finds give +500 to +3,000 tech. A celebration costs 10
  food per villager. A plague takes 80 x n from each food store. These are the ranges behind the collection's size
  words (`vv_cie_graph.SIZE_TABLE`): `small` is half the stock range, `normal` is the stock range, and `large` is
  double it.
- **Skills.** Stock events give +20 to +65 to one villager.
- **Sickness and cures.** A stock event makes one villager sick, or every villager sick at 15-80 percent each. A
  cure event cures everyone. Health changes run 10-60.

## Sizes in this pass (the owner, 2026-11-19: the stock island events' scale)

Each amount is picked by how big the outcome's own words sound. "Small" words are a few, a little, scraps or a
handful. "Big" words are huge, a great, a feast, overflowing, the best in years, a lot, badly or fully. Everything
else is the normal size.

| Effect | Small words | Normal | Big words |
|---|---|---|---|
| Food / tech | `small` (half the stock range) | `normal` (the stock range, e.g. VV1/VV2 500-1,500) | `large` (double) |
| Skill gain or loss | 10-20 | 20-40 | 30-60 |
| Health gain | +10-20 | +15-30 | +30-50 |
| Health loss | -10-20 | -15-30 | -25-50 |

A health loss on a child or a special villager always takes the small size (-10-20). Effects that existed before this
pass are unchanged.
- **Hut damage** (The Rumblings and similar): a percentage of a building.
- **Tech levels**: one level up (The Trapped Whale, The Visitor, The Ancient Gold Coin).
- **Celebrations**: the whole village celebrates (Isola Day, Blessings Day, The Mushroom Celebration).
- **Likes and dislikes**: one villager's like or dislike slots change.
- **New villagers**: The Barrel O' Babies, The Mysterious Face.
- **Who is affected**: usually the one villager the event is about. Sickness, cures and celebrations reach the whole
  village.

## How the 50% works

The CIE v6 format has no per-effect chance, so the pass uses the format's own silent random branch.

- An outcome page X that gets an effect becomes `{"type": "branch", "children": [X__fx, X__text]}`, equally weighted.
  - `X__fx` is X plus the added effects.
  - `X__text` is X as it was.
- Everything that led to X still leads to X, and "visited X" still holds.
- Effects X already had stay on both copies, so they still happen every time.
- The chances table shows the split as 1/2 and 1/2.

## The result line

Every page of an added event that makes a change ends with the engine's result lines (`auto_text`). The rule is
always: the line shows whenever an effect happens, old or new, and only then. Examples:

- "The village gains 40 food."
- "Kai gains 5 Building skill."
- "Ana loses 10 health."
- "Everyone celebrates."
- "Kai shakes his head."

The full table is `vv_cie_graph.AUTO_LINES` (pinned equal to `story_graph.inc` `CG_AUTO_LINES`). The new strings are
in `data/translations/patcher_strings.json`.

A death or a disappearance takes its wording from the page's own words, through the `"line"` key, which is flag 16 of
the effect record:

- "<R> suffers fatal injuries." where the text tells of a fall, a wound or an accident.
- "<R> leaves the village." where the villager goes of their own accord.

The cases are listed in `wording-cases.txt`.

## Counts

Outcomes are every outcome page of the source. Candidates read are the pages the keyword screen passed. Each one was
read and judged.

| Source | Outcomes | Candidates read | Effect lines | Applied now | Waiting for a merge | By type |
|---|---|---|---|---|---|---|
| Isola Grand Event Collection (all draft batches; feat/v1.35.97) | 14,766 | 6,353 | 2,701 | 2,662 | 39 | celebrates (mood good) 1571, tech gain 503, skill gain 159, shakes head (mood bad) 141, health up 119, food gain 81, health loss 39, food loss 35, cure 21, celebrate 9, repair 5, group dance 3, group song 3, group play 2, group sick 2, tech loss 1, damage 1, likes 1, appearance 1, sick 1, group stories 1, group cure 1, village 1 |
| GO events and rewrites (#774) | 6,685 | 3,394 | 1,053 | 0 | 1,053 | celebrates (mood good) 474, shakes head (mood bad) 168, skill gain 85, health loss 63, health up 53, tech gain 50, celebrate 27, food gain 25, damage 18, food loss 17, cure 14, group song 10, likes 10, group cure 9, dislikes 8, repair 7, group dance 6, group stories 3, group relax 1, group pray 1, young_look 1, sick 1, pregnant 1, new_villager 1 |
| Living Culture (#811) | 1,002 | 700 | 310 | 0 | 310 | celebrates (mood good) 182, shakes head (mood bad) 63, group song 16, repair 7, food loss 7, health up 6, skill gain 6, celebrate 5, damage 4, health loss 4, tech gain 4, food gain 2, group stories 1, group cure 1, sick 1, dislikes 1 |
| The Harshest Critic (#803) | 198 | 90 | 14 | 0 | 14 | celebrates (mood good) 7, tech gain 4, shakes head (mood bad) 2, health up 1 |
| Island Traders, Village Moments, VV4 Supplies (#813 on #806) | 145 | 83 | 25 | 0 | 25 | skill gain 12, celebrates (mood good) 9, health up 1, shakes head (mood bad) 1, tech gain 1, food gain 1 |

The Cooking Contest (`original/vv2_cooking_contest.json`, 39 lines) is the one file without the 50% chance. Its many
pools make more than 200,000 histories once the pages are split. Any split doubles the histories through the page,
wherever the coin flip sits, so the owner's fallback applies (2026-11-19): its effects always happen
(`outcome_effects.NO_SPLIT`).

The owner's answers of 2026-11-19 are added (50%):

- the cures for natural recoveries;
- food given to outsiders, as a food loss;
- likes and dislikes the text names, in the games that have the word. A game without the word keeps the text
  alone (the split's first child is limited to the games that have it).

The two pregnancies (b142, b260) stay story-only: neither text names a cast villager as the mother. "Go missing"
keeps "disappears from the village".

The renames in anrel17, anrel28, anrel31, anrel34 and blf40 are not made. The new name is a drawn stranger name
(`(Chosen)`), not a fixed word, and `change_name` takes only a fixed name. Making the rename would need a new effect
field ("the name of role X").

## The lists

- The `<source> (50 percent).txt` files in this folder use the owner's format:
  `<event> | <outcome> | <effect> | "<words that justify it>"`.
- The script-readable lists are in `data/event_collection/outcome_effects/`. They are applied by
  `scripts/outcome_effects.py` and by every generator as it writes a file. `collection_check` fails a file that lacks
  a listed effect, its result lines or its wording.
- `data/event_collection/outcome_effects/pending/` holds lines that cannot be applied on feat/v1.35.97 yet. Their
  events or effect kinds are on unmerged branches:
  - GO events (#774), Living Culture (#811), The Harshest Critic (#803), Traders and Supplies (#813).
  - The cure, repair, new villager and pregnancy effects (#774).
  - The group effects and weather (#813).

  After a branch merges, move its file up one folder, then run `python scripts/outcome_effects.py` and
  `collection_check`.
