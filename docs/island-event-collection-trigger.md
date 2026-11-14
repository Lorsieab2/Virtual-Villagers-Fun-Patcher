# The Isola Grand Event Collection's rare roll

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

## The roll

1. **The edge.** Every frame, the game's Island Events Seen count is read. When it went up while,
   in the frame before, nothing was armed or on its way (no Pick Island Event, no Custom Island
   Event, no bought island event, no branching event running, nothing of the roll's own), the
   event that just came was the game's own natural one.
2. **The roll.** Once the village's two opening events are past, and when the village is not in
   trouble (below), the game's own random routine rolls once:

   | Game | Probability after each natural event | Natural events a week (game time) | Expected collection events a week |
   |---|---|---|---|
   | A New Home | 30% | about 9.6 | about 2.9 |
   | The Lost Children | 25% | about 11.6 | about 2.9 |
   | The Secret City, The Tree of Life, New Believers | 20% | about 14.6 | about 2.9 |

   The table is one constant, `SC_P_PERCENT`.
3. **The due time** is `now + (natural - now) x U[0.30, 0.70]`: the natural time is the one the
   game's trigger has just written into its island timer, so the rare event always falls between
   two natural events. It is kept beside the save (`Virtual Villagers N Island Event Collection
   Roll - Save S.dat`, in the save's own patcher folder), with the village's roster, used only
   for the same village (a strict majority of its villagers), and deleted once delivered or
   cancelled. A lost file loses one rare event, nothing else.
4. **At due** it waits, a frame at a time, while anything else is armed or on its way, while a
   branching event runs, while the game's next natural event is 60 seconds away or less, and in
   New Believers while a God Power is armed. If a natural event comes first, or its natural time
   passes, the roll is gone.
5. **The trouble guard** cancels the roll (it never delays it), and it is asked at the roll too:
   - the stock rescue predicate, in all five games: (men > women and women <= 2) or (men <= women
     and men <= 2) or the population with the babies being carried below 3 (living villagers of
     every age; New Believers' believers only);
   - food stored below 10 a villager, or none;
   - half the villagers or more sick;
   - fewer than 6 villagers of 14 or more.

   A rescue can only come at a natural trigger. Natural triggers keep their time (the island
   timer's keeper, `native/shared/island_timer_keep.h`), and the roll never arms near one or while
   the rescue predicate holds, so a rescue is never displaced.
6. **The choice.** More Island Events' events that can happen now (when that patch is installed)
   and the collection's events for this game (when its patch is installed) are drawn 1:1 when both
   have candidates. Within More Island Events each event is equally likely; within the collection
   each event has its draw weight (`manifest.txt`, default 1), and a series (the Golden Child
   scenes, the contests, the trials, the crises) counts as one event's weight, its members equally
   likely. A collection event is cast strictly: every requirement must hold, and the protected
   villagers are never harmed. One that cannot be cast is left out and the draw is made again.
7. **The arm.** A More Island Events event is armed as Pick Island Event arms it, with no message
   and no charge (a natural arm never leaves a "could not happen" notice for the player). A
   collection event is queued by the branching engine (`cg_queue_origin`, natural origin, strict
   cast). Both make the island event due the way a purchase does, so the island timer's keeper
   puts the game's natural next time back after the delivery. The delivery counts as one island
   event.

## Pick Island Event and the library

- Pick Island Event lists the collection's events of the game after More Island Events' (when the
  collection's patch is installed), each "possible now" by the strict cast, or with what it needs.
- The in-game Custom Island Event library ("From the library...") has an "Isola Grand Event
  Collection" group. Bought there, an event is cast as every library purchase is: a requirement
  nobody meets is dropped, the protected villagers' safety never.

## The files

`scripts/build_event_collection_features.py` compiles every event under `data/event_collection/`
and writes, for each game, `Virtual Villagers Fun Patcher Files\Island Event Collection\` with the
game's `.cieg` files, `manifest.txt` (`id<TAB>title<TAB>games<TAB>draw weight<TAB>series<TAB>credit`)
and `Credits.txt` (the source's credit ledger, lines 1-91, and every
section's credit block, verbatim; then each event's own credit).

Both patches, More Island Events and Isola Grand Event Collection, need Story / Cheat Upgrades,
which runs the roll and Pick Island Event.
