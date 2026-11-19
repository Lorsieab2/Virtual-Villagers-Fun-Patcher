# Outcome effects pass (v1.35.97)

This pass gives the patcher's added island events the game effects their own outcome text already implies. It
follows the owner's request to "go look at the vanilla island events and emulate how those work". No event text,
title or choice changed. Most outcomes keep no effect.

## How the stock island events behave

Sources: `src/vv_game_mechanics_events_vv1.py` ... `vv5.py`, `docs/story-island-outcomes.md`.

- **Food and tech from found things.** VV1/VV2 crates give +500/+1,000/+1,500 food or tech points by strength, and
  vials give tech. VV3 fog gives or takes 300 food. VV4/VV5 finds give +500 to +3,000 tech. A celebration costs 10
  food per villager. A plague takes 80 x n from each food store. These are the ranges behind the collection's size
  words (`vv_cie_graph.SIZE_TABLE`): `small` is half the normal stock range, and `normal` is the stock range.
- **Skills.** Stock events give +20 to +65 to one villager (a dream, a mushroom, a vial). A full mastery (100) is the
  rare top. This pass uses small steps: a little (5-10), some (10-20), a lot (20-40).
- **Sickness and cures.** A stock event makes one villager sick, or every villager sick at 15-80 percent each. A
  cure event cures everyone and sets health to 100. Health losses run 10-60.
- **Hut damage** (The Rumblings and similar): a percentage of a building, up to unbuilt.
- **Tech levels**: one level up (The Trapped Whale, The Visitor, The Ancient Gold Coin).
- **Celebrations**: the whole village celebrates (Isola Day, Blessings Day, The Mushroom Celebration).
- **Likes and dislikes**: one villager's first like or dislike slots change (running, crowds, work, fish, the ocean).
- **New villagers**: The Barrel O' Babies (1-3 children), The Mysterious Face (an adult stranger joins).
- **Who is affected**: usually the one villager the event is about. Sickness, cures and celebrations reach the whole
  village.

## Counts

Reviewed means every outcome page was keyword-screened, and the candidates were read one by one.

| Source | Outcomes | Candidates read | Effects kept | Applied now | Pending |
|---|---|---|---|---|---|
| Grand Event Collection (all draft batches, feat/v1.35.97) | 14,766 | 3,198 | 68 | 44: skill 18, food 12, health 7, tech 2, mood, look, sick, celebrate, like | 24: cure 20 (#774); song 2, dance 1, rain 1 (#813) |
| GO events and rewrites (#774) | 6,685 new or changed | 1,405 | 62 | 0 | 62: celebrate 12, health 11, food 9, cure 8, dance 4, song 3, stories 2, pray 1, hut damage 3, skill 3, likes 2, sick, unhappy, new villager, pregnant |
| Living Culture (#811) | 1,002 | 332 | 21 | 0 | 21: song 12 (#813), huts repaired 6 (#774), food 2, dislike 1 |
| The Harshest Critic (#803) | 198 | 58 | 0 | 0 | 0 |
| Island Traders, Village Moments, VV4 Supplies (#813/#806) | 145 | 21 | 0 (their effects are already built in) | 0 | 0 |
| Procedural/mixer seeds | built from the GO events (`go_seeds.json`) | | follow #774's lines when the seeds are rebuilt | | |
| More Island Events (native) | coded in the companion DLL; the effects are already part of each event | | 0 | | |

## The lists

- `<source>.txt` in this folder uses the owner's format: `<event> | <outcome> | <effect> | "<words that justify it>"`.
- The script-readable lists are in `data/event_collection/outcome_effects/`. They are applied by
  `scripts/outcome_effects.py` and by every generator as it writes a file. `collection_check` fails a file that lacks
  a listed effect.
- `data/event_collection/outcome_effects/pending/` holds lines whose events or effect kinds are not on
  feat/v1.35.97 yet: GO events (#774), Living Culture (#811), and the cure/repair (#774) and group/weather (#813)
  effects. After the branch merges, move the file up one folder, then run `python scripts/outcome_effects.py` and
  `collection_check`.
