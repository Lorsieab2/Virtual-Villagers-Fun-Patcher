# Story / Cheat Upgrades (part 1)

The owner's patch for custom stories, experiments, sandbox play and cheats,
in all five games, **off by default** and left off by Owner's Defaults. It
requires the Origins upgrades row (Enable Origins Tech, Details, and
Village-Wide Upgrades). Part 1 is: every Origins upgrade costs 0 tech points,
and a new Origins upgrade, **Pick Island Event**. (Custom Island Event is part
2 and is not in this build.)

Evidence level: static analysis of the exact executables, and emulation of
the rendered executables with the companion mapped beside them
(`tests/test_story_cheat_upgrades.py`). **Not yet confirmed in a running
game.**

## How it is built

The row patches no executable byte. Its companion, `VVFP Story Upgrades.dll`
(`native/vvfp_story_upgrades`), is loaded by each game's Origins companion
(`native/shared/story_bridge.h`) from its per-frame tick and before every
Origins menu, and asked to install for that game. The install verifies every
site it lists against the exact bytes the Origins payload put there and writes
nothing unless all of them match; only then does it report itself active,
and only then does the Origins companion show and charge 0 and add the Pick
Island Event button. A build whose bytes differ changes nothing.

`scripts/build_story_cheat_upgrades_features.py` generates the five rows and
`story_tables.h` from the lists in that script and in
`scripts/story_island_events.py`. It checks every listed byte against the
executable the patcher renders in all three population modes (with only this
row and with the whole public catalog), and **fails if any byte an Origins
row writes still holds a price** the list does not zero, so a new Origins row
cannot ship with a price this row misses.

## Free Origins upgrades: what changes

Every place the Origins payload compares the balance with a price, deducts a
price, refunds a price, passes a price to its companion, or prints a price in
its own prompt:

| Game | Sites | What |
| --- | --- | --- |
| A New Home | 12 | price table 0x485FC0 (Tech rows 0-5, Details rows 0-4), 11 immediates (1,000,000 rows 6-10 check/deduct, 30,000 Full Heal deduction, 5,000 Change Appearance, 450,000/1,000,000 prompt prices) |
| The Lost Children | 5 | price table 0x494F90, 1,000,000 check/deduct (rows 6-12), 30,000 Full Heal check/deduct |
| The Secret City | 10 | price table 0x4A3F60, 1,000,000 check/deduct and no-change refund, Collections check/deduct, Full Heal refund, 5,000 Change Appearance |
| The Tree of Life | 9 | price table 0x489EE7, 1,000,000 checks/deductions and Collections refund, Full Heal refund, 5,000 Change Appearance check/deduct |
| New Believers | 76 | every check, deduction and read-back in the Task9 page (64), the base payload's tables behind its trampolines, and the 9 Task9 prompts that print a price |

Refunds are zeroed too: with only the price zeroed, a no-change Full Heal or
Collections purchase would refund the old price and mint tech points.

The companions' own prices go through `vvfp_story_price` (Change Appearance
for All in all five, The Lost Children's per-villager Change Appearance, The
Secret City's Equal Division), and every price a dialog or prompt prints reads
0. Every existing refusal stays: one pending Island Event / Barrel at a time,
room for the Barrel's children, and every "nothing to change" check.

## Pick Island Event

A plain Windows list (the owner's choice, not game art) of the game's island
events by their official titles from the game's own English strings, each with
a one-line description. Duplicate titles carry a short variant. An event whose
own condition does not hold right now is listed as "not possible right now"
with what it needs, and cannot be chosen.

Buying it (0 tech points) makes the island event due **exactly as the Origins
Island Event purchase does** -- the same fields, so the Island Event row's own
pending lock covers it, and it is refused while an island event (in New
Believers, also a Barrel) is already queued. When the game's own scheduler
fires the event, the companion replaces only the game's choice of WHICH event:

* **A New Home / The Lost Children** choose a family and then an event with
  `rand()` calls; the pick answers exactly those calls, once each (VV1
  0x423818, 0x42383A, 0x4284DB, 0x418932, 0x42B03E; VV2 0x42EF28, 0x42EF4A,
  0x434607, 0x41F59D, 0x437B0E). The game's own trigger, magnitude
  (clamp(population/3, 1, 10)), condition table, text, sound, event counter
  and rescheduling run as stock. Forced once, not on every call: both games'
  choosers re-roll an event whose condition fails, so a value forced on every
  call would hang on an impossible event.
* **The Secret City, The Tree of Life, New Believers** keep a table of event
  objects; at the point the selector has chosen (VV3 0x419BDB, VV4 0x4180F7,
  VV5 0x41895B -- after the stock rescue overrides) the picked index replaces
  the choice **only if the event's own condition holds** (asked through the
  event object's own vtable, as the selector does). Otherwise the game's own
  choice runs and the next chooser says why the pick could not happen. The
  Secret City's Origins Barrel calls the same selector with every slot
  pointing at the barrel; a pick is never spent there.

A pick not delivered within ten minutes lapses (so it can never carry over
into a village loaded much later), and the next chooser says so.

No event is emulated; the picked event is created, shown and resolved by the
game's own code, with its own choices, random outcomes and amounts.

### Events not offered (developer-dead)

| Game | Excluded | Why |
| --- | --- | --- |
| A New Home | A Mighty Storm | island case 1: its condition class (0x4286A1 = 5) always re-rolls |
| A New Home | The Furry Food | encounter variant 5: its class (0x4189A9 = 4) always re-rolls |
| The Lost Children | case 4 (no body), The Mosquito Swarm, The Dragonfly Migration, Science Awareness Day | the selector's condition table maps them to the never-valid entry 0x434824 |
| The Secret City | The Swarm of Bees, The Drought | strings only; no event object |
| The Tree of Life | The Tsunami, The Canoe from the Other Side, The Medical Emergency, The Return of Biggles | condition 0x4146E0 is `xor al,al; ret` |
| The Tree of Life | The Salty Air | strings only (slot 19 is empty) |
| New Believers | The Stinging Wasps, The Return of Biggles, The Abandoned Infants, The Smelly/Floral/Invisible Vial, Innovation in Farming, Tough Lessons, The Pretty Shell, The Legendary Stranger | condition 0x415B10 is `xor al,al; ret` |
| New Believers | The Tsunami, The Canoe..., The Rainy Season, The Festival of the Banyan, Daredevil Barrel, The State of the Tree, A Closer Look | strings only; no event class |

Offered: A New Home 38, The Lost Children 53, The Secret City 57, The Tree of
Life 44, New Believers 45 (the full lists, with descriptions, are in
`scripts/story_island_events.py` and each row's `island_events`).

## Found in passing (fixed in v1.35.45)

* A New Home and The Lost Children: the Origins Barrel's three-child flag was
  consumed by the next Mysterious Crate / Sack roll, not by the barrel (whose
  count comes from its magnitude 10), so the next crate after a purchased
  barrel was forced to its strongest outcome. The flag and its detours are
  removed; the barrel still gets three children from its magnitude.
* A New Home: the deferred barrel helper destroyed its heap event with the
  plain destructor and never freed the block. It now calls the class's
  deleting destructor (0x427A00, flag 1).
* `docs/duplicate-purchase-guards.md` said the Island Event purchase zeroes the
  countdown in VV1, VV2 and VV4; it writes clock + 5. Corrected.
* New Believers: the stock Chutes Without Ladders override (0x41893D) ran
  after the Origins barrel stub, so a purchased Barrel could come out as
  Chutes in a very small village. A purchased Barrel now goes straight to the
  presenter; natural events keep the override.

## Not verified

* Nothing here has run in a live game yet: the dialog, the button placement,
  the delivery in play, and the in-game timing of the lock all need a live
  check (Time Warp to force events quickly).
* Some event conditions' meanings (which a "not possible right now" line
  names) were read from code and are described generically where unverified.
