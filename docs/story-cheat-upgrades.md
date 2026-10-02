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
game's own code, with its own choices, random outcomes and amounts -- except
the outcomes the player sets (below), which are the game's own rolls answered
with the chosen value.

### Events not offered (developer-dead)

Since v1.35.46 a developer-dead event is offered when it was **proven to work**:
its event object (or case), its title, description and choice strings exist, and
its popup and apply run completely in emulation with nothing half-finished. It is
listed as "(never happens in the original game)" and delivered past its
always-false condition for that one pick. The rest stay excluded:

| Game | Offered as never happening in the original game | Still excluded, and why |
| --- | --- | --- |
| A New Home | A Mighty Storm (island case 1), The Furry Food (encounter 5) | -- |
| The Lost Children | The Mosquito Swarm, The Dragonfly Migration, Science Awareness Day | case 4: no event body, title or text |
| The Secret City | -- | The Swarm of Bees, The Drought: strings only, no event object (The Drought is also unfinished) |
| The Tree of Life | The Canoe from the Other Side (needs room) | The Tsunami: half-finished (its text destroys structures, its apply never touches one and skips the drowning's death step); The Medical Emergency, The Return of Biggles: the condition never picks the villager, so no popup opens and the apply reads a null villager; The Salty Air: strings only |
| New Believers | The Stinging Wasps, The Abandoned Infants (needs room) | The Return of Biggles and slots 48-54: no villager is ever picked, the apply reads a null villager; the strings-only group |

Offered: A New Home 40, The Lost Children 56, The Secret City 57, The Tree of
Life 45, New Believers 47 (the full lists, with descriptions, are in
`scripts/story_island_events.py` and each row's `island_events`).

## Pick Island Event: outcomes, strength and unlocks (v1.35.46)

The owner: "In general I want all possible outcomes for events that have them to
be possible." Every offered event that has anything to decide gets settings in the
Pick Island Event dialog (the event list on the left; the event's settings on the
right, one row each, with the selected row's dropdown, a number box for an amount
with a wide range, and a villager list with Ctrl/Shift extended selection for
"Choose who"). Every setting starts at **Random (original game)**. The full list,
per game and event, is `docs/story-island-outcomes.md` (generated); the evidence
for each (the code it was traced in) is in `scripts/story_outcomes_vv1.py` ...
`story_outcomes_vv5.py`.

| Game | Events with settings | Settings | Result options | Amounts | Each-villager | Which-villager | Strength events |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A New Home | 26 | 89 | 73 | 39 | 4 | 24 | 8 |
| The Lost Children | 28 | 79 | 92 | 31 | 7 | 21 | 3 |
| The Secret City | 42 | 117 | 79 | 55 | 7 | 32 | -- |
| The Tree of Life | 34 | 72 | 29 | 27 | 8 | 27 | -- |
| New Believers | 29 | 69 | 91 | 21 | -- | 24 | -- |

What can be set, where the event's own code rolls for it:

* **The result** -- one of the event's own results. A two-choice event's popup
  still appears and the player still clicks; the setting decides the result of
  the choice it is labelled with.
* **Every amount** the event can roll (food, tech points, health, skill gains,
  faith, ages, weather lengths), over its whole range: every value is listed, or
  typed when the range is wide (it must be a value the game itself can roll).
* **Each villager** -- a roll the game makes for every villager in turn (who falls
  sick, is stung, is swept away, learns): nobody, everyone, or the villagers
  chosen. "Everyone" where it could end the tribe (The Secret City's tsunami and
  low-tide wave) asks for confirmation first.
* **Which villager** the event is about, where the game picks one with a roll
  among candidates; a villager the game itself would not pick leaves the choice
  to the game.
* **Each baby's** sex, skill, level, age and looks, where rolled.
* **Strength** (A New Home, The Lost Children): the magnitude the game normally
  takes from the population (a third of it, 1 to 10), only for the events whose
  code uses it -- every value where it is linear, 1-4 / 5-7 / 8-10 for the Barrel
  O` Babies (one, two or three babies; the count still stops at the village's
  room).

A setting whose condition fails right now (a newcomer or a copy needs room; the
Gong's rarer results need its tiers open) says so and can not be bought.

### How a roll is answered

Each setting names the game's own `call rand` instructions that decide it (the
generator checks every one is an `E8 rel32` call to that game's rand, holding the
stock bytes in every render). The companion points each at one stub that hands
the call's registers to the outcome engine (`story_outcomes.inc`), which returns
the chosen value only when **all** of these hold, and the game's own rand
otherwise:

* the armed pick has a setting for that roll;
* the roll's **phase** is current: "select" (before the event is shown -- the
  condition method the selector asks on every pass, A New Home's crate and The
  Lost Children's sack set-up before the variant roll) answers from the moment
  the pick is armed; "build" (the popup's text methods, which the popup calls at
  build time and again at the click) answers once the pick is delivered;
  "apply" answers only while that very event's apply runs;
* for a routine other code reaches too (the weather setter, a skill helper, a
  villager picker, a per-villager loop), only **inside the event's own call to
  it**: that call runs bracketed by a second stub;
* for a setting of one choice, only when **that choice was clicked**;
* for a baby, only at **that baby's** call of the creator's roll (the creator
  calls belong to the Origins rows, which patch them to count births, so babies
  are told apart by their order in the apply).

The armed outcome ends when the event's apply returns (The Secret City, The Tree
of Life, New Believers: the popup's OK handler, 0x419A29/0x419A41,
0x417EC9/0x417EE5, 0x418749/0x418765, whose apply calls the companion
replaces; A New Home / The Lost Children: the resolve calls 0x41A444, 0x42D0C4,
0x422364, 0x439DB4, 0x43483D, and A New Home's island chooser call 0x428777,
inside which its single-result events run), when the pick is refused or
lapses, and when the game starts choosing another island event while an old
delivered outcome is still held. A forced value therefore never reaches a
natural event, nor another event sharing the routine. The apply calls are
matched to the delivered event object, so the Origins Barrel or a custom event
shown by the same popup is never forced.

Strength: A New Home substitutes the magnitude in the island chooser call
0x428777 (only for an armed island pick whose condition holds, never for the
Origins Barrel's call); The Lost Children in the case body call 0x43483D, after
the case roll.

### Unlocked picks

For each offered event with a condition, the condition was classified: a timing
or story condition (already happened, a level, a season, a puzzle state, a
population floor the code does not need) is passed for one delivery once the
event's popup and apply were run in emulation with the condition false and
completed coherently; a condition the event's code needs (a villager of some
kind, crops, a chief) keeps it locked with the reason, and room for new
villagers is never overridden. An unlocked event is listed as "(normally not
possible right now)".

| Game | Unlocked | Locked with the reason | Developer-dead offered | Still excluded |
| --- | --- | --- | --- | --- |
| A New Home | 2 | 6 | 2 | 0 |
| The Lost Children | 5 | 13 | 3 | 1 |
| The Secret City | 18 | 24 | 0 | 2 |
| The Tree of Life | 9 | 23 | 1 | 4 |
| New Believers | 5 | 26 | 2 | 9 |

A New Home and The Lost Children pass the check right after the event roll, once
(0x4284EC, 0x418941; 0x434617, 0x41F5A5). The other three deliver the picked
object although its condition method returns false -- after that method has run
(it picks the villager the event is about before the failing check), only if it
picked the villager the event needs **this time** (the field is cleared first),
and, for an event that makes villagers, only while the game's own room test
passes.

The Secret City's Tsunami and Low Tide are unlocked below their population
floors: in a very small village their sweep can, as in stock, take every villager.

## Pick Gong of Wonder Outcome (The Lost Children)

A separate upgrade in The Lost Children's Tech menu (0 tech points; not an island
event, so not under the Island Event lock). The player picks what the **next**
ring of the Gong of Wonder does: any of its 23 results (tier A and B results only
once a tier-C result has opened them, as in the game), the amounts of tech and
food, who falls sick, which skill "grants wisdom" raises, and one baby, twins or
triplets for "grants life" (twins and triplets need breeding mastered, as in the
game). A gong use is the call 0x461B8E into its outcome routine 0x44E8A0 (its
only caller); the settings are answered only inside it and end when it returns,
so they are used for one ring. An armed choice also ends after ten minutes
without a ring and when the save slot changes. The Gong rests about a day after
each ring; a choice waits for the next real ring. It works with the Gong of Wonder
Coconuts Fix ticked or not (none of its sites overlap the fix's bytes; with the
fix, the coconut results add 30 instead of setting 30).

## Stock behaviour found in passing (reported, not changed)

The owner's rule: no original-game behaviour is changed without being reported
first. These are offered exactly as the game produces them:

* The Secret City's Royal Jelly: the clear vial's text says the jelly spoiled, yet it is the clear vial
  that cures and raises Healing; the dark vial's text says it worked, yet it
  changes nothing.
* The Lost Children's Gong "Takes youth" / "Grants youth" write fixed villager
  slots 6 and 15, not the villager who rang it.
* Several health losses have no floor (A New Home's old-fruit crate finder and
  rotting-crate finder, The Lost Children's fire ants and mice finder), and A New
  Home's Mysterious Face stranger's farming can reach 106.
* The Secret City's quartz vial: at age exactly 280 the text promises one result
  and the apply takes the other; its body-change branch can never run.
* The Lost Children's Prettiest Girl: the selector asks for an adult woman, the
  pick accepts a girl of any age.
* The Tree of Life's healer events do not require the healer to be sick.
* New Believers' Abandoned Infants (never in stock) does not filter by faction.
* The part-1 condition texts for A New Home's whale and visitor, The Lost
  Children's gold coin and spyglass, The Secret City's Daredevil and Low Tide and
  The Tree of Life's Pretty Shell were wrong and are corrected (patcher text only).

## Not verified (outcomes)

* Nothing here has run in a live game yet: the dialog, every setting's effect in
  play, the unlocked and dead events, and the Gong.
* The weather lengths are in the game's own clock units; their real-time length
  was not established.
* A setting's label describes the code it was traced in; the in-game text is the
  game's own.

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

### Two choices (v1.35.47)

The owner: "I want the player to be able to choose the outcomes. Some buttons
should have a chance of multiple outcomes too."

Tick **Ask a question with two choices** in the Custom Island Event dialog and
the description becomes the **question**; **Choices...** opens a dialog with
the two **button labels** and, for each button, a list of one to four
**outcomes** (Add / Edit / Remove, double-click to edit) and the **chance** of
the chosen outcome (1-100). The note under each list shows every outcome's
share: its chance out of the button's total (chances 3 and 1 are 75% and
25%); a button with one outcome always gets it. **Edit** opens the Custom
Island Event dialog again for that outcome: the title is the event's (greyed),
the text box is the outcome's **Result text**, and every change the Maker
offers -- food and tech, refill, village changes, new villagers, villager
changes, food sources, puzzles, revivals -- is that outcome's own. With the box
ticked the event itself holds no changes (its village controls are off; changes
added before ticking must be removed). The word / character / line counter
counts the question against the question popup and a result text against the
result popup.

When the event happens the game shows the question with the two buttons; the
click rolls one of that button's outcomes (weighted by the chances, through the
game's own random routine where the hook names it), makes exactly that
outcome's changes as a plain custom event makes its own, and shows its result
text with the usual food / tech and "no room" lines. Nothing changes before the
click. Queueing is the plain event's: the same lock, the same ten-minute lapse,
bound to the save slot and the Start Over / delete generation; an answer in a
village other than the one the question was asked in changes nothing.

Every value is checked when OK is pressed and again when the event is bought:
both labels non-empty and within the game's label width (letters, numbers,
spaces and . , ! ? : - ' only), one to four outcomes per button, each chance
1-100, each result text non-empty and fitting the result popup, and the usual
room checks for each outcome's new villagers and babies. The engine is
`ce_choice_*` in `native/vvfp_story_upgrades/story_custom.inc`; the data is
`ce_choice` / `ce_outcome` in `story_custom.h`.

**Each game's own two-button popup is hooked separately** (the
`CAP_CHOICE` capability in each `story_c*.inc` adapter, with the popup's
question / result widths and line counts, the label width and the game's
random routine). A game without the hook keeps the box disabled and refuses a
question ("This game can not ask a question with two choices yet"). Evidence
level: the engine is tested in emulation (`tests/test_story_two_choice.py`:
the layout, every roll of every chance split and the real generator's
shares, every refusal, the lock / lapse / village binding, applying exactly
the rolled outcome, mutation-checked); **the dialogs and the in-game popups are
not yet confirmed in a running game**.

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
