# When the Isola Grand Event Collection's events come

How the new island events come into a game, in all five games (v1.35.97). The code is
`native/vvfp_story_upgrades/story_collection.inc` (in "VVFP Story Upgrades.dll"); the tests are
`tests/test_collection_trigger.py`, `tests/test_more_island_events_stock_odds.py` and
`tests/test_event_collection_package.py`.

## The owner's rules

- The stock island events' chances never change.
- The new events are rare, but a seven-day playthrough sees some.
- They never replace a rescue event.
- Default ON in Owner's Defaults, OFF everywhere else.

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

An event is due when Pick Island Event picked it, or when the rare roll below drew it.
`tests/test_more_island_events_stock_odds.py` runs each game's selection 10,000 times with the
companion installed: every stock event keeps its 1/c share, the draw's call in The Lost Children
is never written while nothing is due, and A New Home's and The Lost Children's choosers give the
same draws, draw for draw, as the stock code.

## When a new event comes (the owner, 2026-11-15)

The separate rare roll between natural events is gone. Instead:

1. **At each natural island event** the game is about to deliver -- 3 seconds before its island timer is due, once
   for that natural time, with nothing else armed or on its way (and in New Believers no God Power armed) -- the game's
   own random routine rolls 50 of 100 (`SC_REPLACE_PERCENT`).
2. **On a pass**, one new event (More Island Events' or the collection's, the draw below) is armed **instead**: the
   game's own event does not happen that time. When no new event can be cast, the game's own event comes as always.
3. **Never replaced:** the village's two opening events (`CE_OPENING_EVENTS`), a rescue event (the trouble guard holds
   the game's own rescue rule), and nothing while the village is in trouble.
4. **Population:** only when the village has **61 or more** villagers (`SC_MIN_POPULATION`: the living villagers the
   game lists and the babies being carried, as the game's own rescue rule counts its population; New Believers'
   believers only). Below 61 nothing is replaced.
5. **The schedule goes on:** the new event is armed as a purchase arms one; once the island timer's keeper has the
   arm, its kept time is set to a new natural time after this one, drawn as the game's own trigger draws one (A New
   Home 12-23 hours, The Lost Children 10-19, the later three 8-15). The delivery counts as one island event.
6. **The trouble guard** (unchanged): the stock rescue predicate in all five games, food stored below 10 a villager or
   none, half the villagers or more sick, fewer than 6 villagers of 14 or more.
7. **The choice** (unchanged): every event equally likely whichever source it comes from; a series counts as one
   event; strict casting; a candidate that cannot be cast is left out and the draw made again.

Pick Island Event and Custom Island Events (player-chosen) ignore the 61 and the 50%.

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
Events' events are kept out whole by `SC_MORE_FILTERS` (story_collection.inc). The game's own events never change.
