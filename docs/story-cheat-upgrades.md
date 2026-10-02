# Story / Cheat Upgrades

The owner's patch for custom stories, experiments, sandbox play and cheats,
in all five games, **off by default** and left off by Owner's Defaults. It
requires the Origins upgrades row (Enable Origins Tech, Details, and
Village-Wide Upgrades). Part 1: every Origins upgrade costs 0 tech points,
and a new Origins upgrade, **Pick Island Event**. Part 2: **Custom Island
Event** and custom villager titles (below).

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
into a village loaded much later), and the next chooser says so.  A pick (or a
custom event) belongs to the village it was queued in: loading another save
slot, Start Over or deleting a tribe discards it ("VVFP Save Reset.dll" tells
the story companion through VvfpStoryVillageReset), so it can never replace
another village's event or change its villagers.

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

## Custom Island Event (part 2)

The owner: "Custom Island Event -- Allows the player to create and trigger a
custom Island Event for storytelling, testing, sandbox play, or cheats ...
available options must be determined separately for VV1, VV2, VV3, VV4, and
VV5 from each game's actual executable/data structures ... Unsupported
properties should be omitted or disabled rather than approximated."

Evidence level: static analysis of the exact executables (five per-game
traces), and emulation of the rendered executables with the companion mapped
beside them (`tests/test_story_custom_island_event.py`), plus native
harnesses on real files for the .dat (`tests/test_custom_titles_persistence.py`).
**Not yet confirmed in a running game**: the dialogs, the popup's look, the
pose of a male carrier, and the in-game timing all need a live check (Time
Warp forces the event quickly).

### How it is used

A **Custom Island Event (0 tech points)...** button sits beside Pick Island
Event on the Origins Tech menu. Its plain Windows dialogs:

* **Custom Island Event**: the event's title (one line) and description, the
  village changes (food and tech points: add, subtract or set to 0; refill the
  food sources; the game's village and puzzle changes), the new villagers, and
  the villager changes. **Not in this game...** lists what the game does not
  offer and why.
* **Villager changes**: the villagers in a list with standard extended
  selection (Ctrl+click toggles one, Shift+click selects a range) and five
  group toggles named exactly **All Adult Women**, **All Adult Men**, **All
  Females**, **All Males**, **All Children** ("adult" is each game's own
  boundary, 14 years). Toggles and picks combine; a villager matched more than
  once counts once; changes added for a villager twice are merged (the later
  value wins), so changes can be set per villager.
* **New villagers**: how many, sex, age, name, head and body, likes and
  dislikes, skills, custom title, mask.
* **Parents**: the parentage data of the chosen villagers.

Every value is checked when a dialog closes and a value the game does not
accept is refused with its valid range. Buying the event (0 tech points)
makes the island event due **exactly as the Island Event purchase does** -- the
same lock as Pick Island Event: one island event, pick or custom event at a
time, refused while one is queued. An undelivered event lapses after ten
minutes.

### Delivery

When the game's own scheduler fires the island event (it has already
rescheduled the next one, played its sound and counted it), the changes are
made and the game's own island-event popup shows the custom title and
description, followed by the food / tech lines in the game's own wording and a
line for anything the village had no room for.

| Game | Where | How |
| --- | --- | --- |
| A New Home | 0x428777, the island event's chooser call | the replacement writes the text into the event's own buffer (+0x277F) and makes the changes; the trigger's family rolls send it to the island family |
| The Lost Children | 0x4349B2, the single-result event's chooser call | the same (+0x277F); the family rolls send it to family C |
| The Secret City | 0x419BDB (the Pick Island Event site) | the presenter gets a custom event object: The Fog's vtable with the title / body ids 0x4CB / 0x4CC (string-table slots the game leaves empty) |
| The Tree of Life | 0x4180F7 | the event base vtable, ids 0x32A / 0x32B (The Salty Air's, no event object) |
| New Believers | 0x41895B | Blessings Day's vtable, ids 0x3AD / 0x3AE (empty slots) |

The Origins Barrel always reaches the game's own code. A New Home's and The
Lost Children's first island event of a village is always the other family,
so a custom event is refused until it has happened.

### What each game offers

| Option | A New Home | The Lost Children | The Secret City | The Tree of Life | New Believers |
| --- | --- | --- | --- | --- | --- |
| Title and description (live word / character / panel-line counter) | yes | yes | yes | yes | yes |
| Food / tech points | yes | yes | yes | yes | yes |
| Refill food sources | berries; crops once the farm produces | coconut trees; crops while planted (not fish / soil: puzzle-gated) | fruit trees (0x4340A0) | berry bushes | noni bushes; crops once built |
| New villagers | creator 0x43C350 | 0x44F580 | 0x45FF50 | 0x467D10 | believers, 0x471E20 |
| Dies (skeleton) | health 0 | health 0 | 0x462670(0, -1) | stop + 0x46AF00(0, -1) | stop + SetHealth(0, 2) |
| Disappears (no skeleton) | as "a closer look" (0x41979D) | as A Dangerous Mission | as the Tsunami (0x45D990) | as The Sealed Box | presence byte +0x1CD4 cleared, after the stop (0x473440) and the manager release (0x470800) |
| Falls sick | yes | yes | yes | yes | believers only (Heathens are cured every moment) |
| Pregnant (baby / twins / triplets, either sex) | adults 18+ | adults 18+ | adults 18+ | adults 18+ (0x45E7B0, forced) | adult believers (0x465E00, forced; Heathens never deliver) |
| Likes / dislikes | 46 of 47 words | 62 words | 79 words | 79 words | 79 words |
| Appearance | heads / bodies 0-19 | 0-29 | 0-29 | 0-29 | 0-29 |
| Skills | 5 | 5 | 5 | 5 | 6 |
| Parents | with Show Parents (its sidecar) | on the record | on the record | on the record | on the record |
| Custom title | yes | yes | yes | yes | yes |
| Mask | yes | yes | yes | yes | yes |
| Faction / status | -- | Esteemed Elder (0x44D190, with its totem); totem art 1-8 | -- (Tribal Chief omitted) | -- | believer / Heathen (the game's conversions; puzzle Heathens refused) |
| Behaviours | stop, dance, swim, relax, recover | stop, swim, celebrate, visit graves, sneeze, recover | stop, recover | stop, recover | stop, recover |
| Village / puzzle | Isola Day, Blessings Day, the dirty beach (as The Big Wave) | -- | -- | rain, clear weather | -- |

The editor counts as you type: the title's characters against the one line the panel
gives it, and the description's words, characters and panel lines, laid out by
the same word-wrap the popup uses, so "too long" there is exactly what OK refuses.

Each is the game's own routine or the fields its own code writes for the same
effect (the per-game files `native/vvfp_story_upgrades/story_c1.inc` ..
`story_c5.inc` cite the sites). A villager is changed only while its record
still holds the same living villager as when the event was queued: same name,
sex, head, body, likes and dislikes (names repeat, so a name alone is not enough),
decided once before the event changes anything. Each new
villager and each baby is made only while the game's own room predicate says
the village has room (and a record is free), so the population cap of the
installed mode is never passed -- run in all three modes in the tests.

A pregnancy writes what each game's conception writes (and counts Babies
Made, twins and triplets as the game does); with **Write Births and
Conceptions Log to Text File** ticked it is logged through the same
`WriteParentageRecordWithFather` call the game's own conceptions use. No
game's conception or delivery checks the carrier's sex, so a man can carry
(the Heathen Mommy works the same way); an unknown father is "Unknown" with
the carrier's own looks. How a male carrier's pose looks is not verified.

### Custom titles

A villager's title can be replaced by the player's text (1-31 letters,
numbers, spaces and . , ! ? : - '). It is kept per save slot in

    <save folder>\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save N.dat

(`native/shared/custom_titles.h`), never in the save, and shown in the
villager panel (VV1 0x41FD75, VV2 0x429DE3, VV3 0x468FC8, VV4 0x4404D9, VV5
0x44319E) and as "Custom title:" in the Village Population roster and the
Village History. No game's Details screen shows a title. A title belongs to
its record only while the record holds the villager whose name it was set
for; it is dropped when the villager dies or the record is reused. Start Over
deletes the slot's file, and a table that sees its file gone forgets the old
village instead of writing it back.

### Not offered, and why

* A New Home: the Golden Child (only its puzzle makes one; the creator's
  family 0xC7 forces sex, age and looks); puzzle completion (no callable
  completion routine); the 47th like word (the game never uses it and its
  list reader can overrun on it).
* The Lost Children: puzzle states; fish and soil refills.
* The Secret City: Tribal Chief (only the robe puzzle; a second chief is a
  known defect); the beehive refill (tied to its puzzle); puzzle states.
* The Tree of Life: fruit-tree and fishing refills (no game routine); weather
  types other than rain and clear (not identified); puzzle states.
* New Believers: new Heathens (the creator's arguments are not
  all understood); puzzle states (prerequisites unproven); the puzzles' own
  Heathens keep their faction.

### Found in passing (not changed here)

* A New Home: 0x43A200 returns the first corpse, not a free record (the
  emulation of the population-cap test showed it); the companion scans for a
  free record itself.
* Static only: VV1's twin/triplet slot guards in builds.json compare lifetime
  Babies Made with 256; VV1's like list has no comma after its last word;
  VV1's "Read the book" removal leaves a stale selection; VV2's Equal
  Division labels the job codes differently from the game's title table;
  VV2's renders' clamped slot scan can reuse record 255; VV3's physical guard
  ignores pending litters; `vv4_origins_icons.c` describes its sex values in
  reverse; `settle_vv5_identity_chain.py` can leave
  `VV5_TASK9_ACTIVE_SOURCE_TEXT_SHA256` behind (set by hand here).
