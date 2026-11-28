# When the Isola Grand Event Collection's events come

How the new island events come into a game, in all five games (v1.35.97). The code is
`native/vvfp_story_upgrades/story_collection.inc` (in "VVFP Story Upgrades.dll"); the tests are
`tests/test_collection_trigger.py`, `tests/test_more_island_events_stock_odds.py` and
`tests/test_event_collection_package.py`.

## The owner's rules

- The stock island events' chances among themselves never change (the game's own draw is never widened).
- Since 2026-11-15 (the owner) a new event takes a natural event's place; the game's own event does not come that
  time. This replaced the separate rare roll of 2026-11-14. Since 2026-11-27 (the owner: "additional events should
  replace vanilla ones 50% of the time") that is a flat 50% (it was a chance rolled in 30-50% each time).
- Since 2026-11-27 (the owner: "all events at any size; below 61 population a max of 1-2 villagers can die or
  disappear to prevent mass casualties") every new event may come at any population; below 61 villagers one that can
  take more than 2 villagers in one of its endings stays out of the draw (the casualty limit below).
- They never replace a rescue event or the two opening events.
- Off by default; Owner's Defaults, Select All and Classic VV Difficulty (The Tree of Life, New Believers) tick both.

## Never a share of the game's own draw

The nine events of More Island Events (`native/vvfp_more_island_events`) used to be drawn with
the game's own events: one more encounter in A New Home, family A's draw widened to `rand(23)` in
The Lost Children, one more list entry each in the later three games, and one more case each for
The Remembrance Ceremony and The Rumblings. That shrank every stock event's chance. All of it is
gone. Each game's draw now runs on the stock bytes, with the stock bound, and the companion only
steps in when one of its events is **due**:

| Game | The draw with nothing due | When an event is due |
|---|---|---|
| A New Home | the stock roller 0x418920 | the due event instead of the roller's draw |
| The Lost Children | `rand(22)` at 0x41F59D, a stock 21 drawn again | the draw's call is pointed into the companion for that one chooser run; its first answer is the event's own number (21 or 22), then put back |
| The Secret City, The Tree of Life, New Believers | the selector's own list and `rand(count)` | no entry is added; the due event's object is put in slot 0 and Story / Cheat Upgrades' pick presents it |
| Single-result choosers (A New Home, The Lost Children) | the stock chooser | the chooser's first draw answers the due event's case |

An event is due when Pick Island Event picked it, or when the natural-event replacement below drew it.
`tests/test_more_island_events_stock_odds.py` runs each game's selection 10,000 times with the
companion installed: every stock event keeps its 1/c share, the draw's call in The Lost Children
is never written while nothing is due, and A New Home's and The Lost Children's choosers give the
same draws, draw for draw, as the stock code.

## When a new event comes (the owner, 2026-11-15)

The separate rare roll between natural events is gone. Instead:

1. **At each natural island event** the game is about to deliver -- 3 seconds before its island timer is due, once
   for that natural time, with nothing else armed or on its way (and in New Believers no God Power armed) -- the game's
   own random routine passes 50 in 100 (`SC_REPLACE_PERCENT`), one roll, at any population.
2. **On a pass**, one new event (More Island Events' or the collection's, the draw below) is armed **instead**: the
   game's own event does not happen that time. When no new event can be cast, the game's own event comes as always.
3. **Never replaced:** the village's two opening events (`CE_OPENING_EVENTS`), a rescue event (the trouble guard holds
   the game's own rescue rule), and nothing while the village is in trouble.
4. **The casualty limit:** every new event may come at any population, when its own requirements hold. While the
   village has fewer than **61** villagers (`SC_MIN_POPULATION`: the living villagers the game lists and the babies
   being carried, as the game's own rescue rule counts its population; New Believers' believers only; `sc_gate` in
   `sc_apply`), an event that can take **more than 2** villagers (`SC_MAX_GONE`) in one of its endings is left out of
   the draw -- before it is chosen, so what an event shows always happens. **The count** (`sc_graph_gone`; its Python
   twin `vv_cie_graph.gone`, kept equal by `tests/test_casualty_limit.py`): one ending is one path through the event
   from its first page to an end, every page's effects on it; it counts the distinct villager roles killed, made to
   disappear, dead with the body never found, or dead after giving birth (`kill`, `vanish`, `die_unrecovered`,
   `birth_then_die`), plus each villager the event made itself (every time), plus a group's size (N of a random N;
   "every villager" and the like more than any limit). A lost pregnancy (`baby_lost`) counts as no one. The event's
   count is its worst ending. A Living Event Engine variant is counted the same way (`lv_excluded`); a procedural
   event's ending is its setup, one approach and ONE outcome, so an outcome is left out when it alone takes more than
   2 and any other piece when it takes anyone (`pc_too_deadly`). More Island Events' counts are `SC_MORE_GONE`
   (story_more_filters.h, from `GONE` in scripts/build_story_more_filters.py, read from each event's own effects): The
   Aspiring Adventurer 1, The Cave Explorers 2, The Climb 1, The Troubling Signs 5, Diving for Treasure 1, The
   Mysterious Mask 9 (five volunteers, and up to four children in a capture); so below 61 villagers only The Troubling
   Signs and The Mysterious Mask stay out (each also needs 61 villagers of its own).
5. **The schedule goes on:** the new event is armed as a purchase arms one; once the island timer's keeper has the
   arm, its kept time is set to a new natural time after this one, drawn as the game's own trigger draws one (A New
   Home 12-23 hours, The Lost Children 10-19, the later three 8-15). The delivery counts as one island event.
6. **The trouble guard** (unchanged): the stock rescue predicate in all five games, food stored below 10 a villager or
   none, half the villagers or more sick, fewer than 6 villagers of 14 or more.
7. **The choice** (unchanged): every event equally likely whichever source it comes from; a series counts as one
   event; strict casting; a candidate that cannot be cast is left out and the draw made again.

Pick Island Event and Custom Island Events (player-chosen) ignore the casualty limit and the 50%. No Safeguards for
Island Events (and Additional Events too) lifts the casualty limit too.

## Pick Island Event and the library

- Pick Island Event lists the collection's events of the game after More Island Events' (when the
  collection's patch is installed), each "possible now" by the strict cast, or with what it needs.
- The in-game Custom Island Event library ("From the library...") has an "Isola Grand Event
  Collection" group. Bought there, an event is cast as every library purchase is: a requirement
  nobody meets is dropped, the protected villagers' safety never.

## The files

`scripts/build_event_collection_features.py` compiles every event under `data/event_collection/`
and writes, for each game, `Virtual Villagers Fun Patcher Files\Events\` with the
game's `.cieg` files, `manifest.txt` (`id<TAB>title<TAB>games<TAB>draw weight<TAB>series<TAB>credit`)
and `Credits.txt` (the source's credit ledger, lines 1-91, and every
section's credit block, verbatim; then each event's own credit).

Both patches, More Island Events and Isola Grand Event Collection, need Story / Cheat Upgrades,
which runs the roll and Pick Island Event.

## The content controls (v1.35.97, the owner 2026-11-15)

Each game's patcher page has an **Island Events** section: More Island Events, the Isola Grand Event Collection (with
the owner's red content advisories), **Content Notes for Island Events** (on in
Owner's Defaults, off elsewhere) and the 28 **content filters** (off everywhere). They are names in "VVFP Installed
Patches.txt" only; the collection's compiled events carry what each does (cie-v6-binary.md 31), and More Island
Events' events are kept out whole by `SC_MORE_FILTERS` (story_more_filters.h, generated from content_tags/mie.json by
scripts/build_story_more_filters.py on every Story Upgrades build). The game's own events never change.
