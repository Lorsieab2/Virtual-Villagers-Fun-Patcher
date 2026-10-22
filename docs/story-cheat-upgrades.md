# Story / Cheat Upgrades

The owner's patch for custom stories, experiments, sandbox play and cheats,
in all five games, **off by default**; Owner's Defaults ticks it. It
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
| The Lost Children | The Mosquito Swarm, The Dragonfly Migration, Science Awareness Day (with Restore Missing Island Events ticked these are ordinary events: that row puts them in the game's own roll) | case 4: no event body, title or text (Restore Missing Island Events gives it the three lore pages, offered as The Tattered Diary, The Doctrine of Magicians and The Doctrine of Naturalists only with that row) |
| The Secret City | -- | The Swarm of Bees, The Drought: strings only, no event object (The Drought is also unfinished) |
| The Tree of Life | The Canoe from the Other Side (needs room) | The Tsunami: half-finished (its text destroys structures, its apply never touches one and skips the drowning's death step); The Medical Emergency, The Return of Biggles: the condition never picks the villager, so no popup opens and the apply reads a null villager; The Salty Air: strings only |
| New Believers | The Stinging Wasps, The Abandoned Infants (needs room) | The Return of Biggles and slots 48-54: no villager is ever picked, the apply reads a null villager; the strings-only group |

Offered: A New Home 40, The Lost Children 59 (56 without Restore Missing Island Events), The Secret City 57, The Tree of
Life 45, New Believers 47 (the full lists, with descriptions, are in
`scripts/story_island_events.py` and each row's `island_events`).

## Pick Island Event: outcomes, strength and unlocks (v1.35.46)

The owner: "In general I want all possible outcomes for events that have them to
be possible." Every offered event that has anything to decide gets settings in the
Pick Island Event dialog (the event list on the left; the event's settings on the
right, one row each, with the selected row's dropdown, a number box for an amount
with a wide range, and a villager list with Ctrl/Shift extended selection for
"Choose who"). Every setting starts at **Random (original game)**.

Since v1.35.80 (the owner: "make sure all these windows are expandable"): the
dialog -- like every dialog of the Story Upgrades and every game's Origins menu
companion (the VV1 / VV2 / VV4 Origins Icons, VV3 Safe Upgrades, VV5 Task9 Origins
Icons, which VV4 also uses in the Expanded modes) -- has a sizing frame and minimise / maximise boxes
(`native/shared/vvfp_dialog_kit.h`). Its smallest size is its own; larger, every
control keeps its share of the window (lists, text and drop-downs grow; buttons
and art keep their size); minimised it has a taskbar button of its own and the
game behind it is left as it is. The lists' entries wrap, so no entry is cut
off, every drop-down opens as wide as its widest entry, and every description and
note fits at the smallest size (`tests/test_resizable_pickers.py` measures them).
A villager list or drop-down has a **sort selector**: the game's own order, **Age
(oldest at top)** (ties by name) or **Alphabetical (first name, then last name)**
(case-insensitive, numbered names in numeral order: Kenobi I, II, III, ...),
kept per game for the session; the chosen villagers stay chosen. The same
selector is on the Custom Island Event's villager lists (Villager changes and its
father, Parents, Revive -- made oldest first, so Age or Alphabetical -- and the
question's picture). The full list,
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

A setting whose condition fails right now (a newcomer or a copy needs room) says
so and can not be bought. Twins and triplets the game rolls only once the village
has mastered them (The Lost Children's [world+0x2EA8C] == 3, The Tree of Life's
Parenting mastery 3) can be chosen before that: the gate is lifted for the chosen
conception call only (the dword set to 3 and put back when the call returns; the
mastery call 0x41E1C0 answered 3 inside the event's apply).

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
ring of the Gong of Wonder does: any of its 23 results, the amounts of tech and
food, who falls sick, which skill "grants wisdom" raises, one baby, twins or
triplets for "grants life" (also before breeding is mastered), and the villager
the ringer's results act on. A gong use is the call
0x461B8E into its outcome routine 0x44E8A0 (its only caller); the settings are
answered only inside it and end when it returns, so they are used for one ring.
An armed choice also ends after ten minutes without a ring and when the save
slot changes. It works with the Gong of Wonder Coconuts Fix ticked or not (none
of its sites overlap the fix's bytes; with the fix, the coconut results add 30
instead of setting 30).

The picker has the Pick Island Event dialog's format (the owner, v1.35.80: "I
like the format of the 'Pick Island Events' better"): the list on the left is
**What the Gong does** -- "Random (original game)" first, then all 23 results in
the game's own words under the headings Tier A (6), Tier B (9) and Tier C (8) --
and choosing one lists on the right only that result's own settings (its amount,
who falls sick, the skill, the babies, the villager who rang it; Random lists them
all). While the result is left Random with any other setting made, the window
and the purchase's confirmation say "The effect itself is still random - pick it
in 'What the Gong does'": the effect is then the game's own roll, as designed
(the owner's v1.35.80 preview report of a random effect was this case). OK keeps
only the chosen result's own settings.

Every outcome (the owner, 2026-10-20: "I want ALL of them"):

* Tier A and B results. The game gives them only once a tier-C result has set
  village byte +0x2E910 (0x44EFDB), so a village's first ring is always tier C.
  A chosen tier A or B result sets that byte to 1 (the game's own value) for its
  ring only when it is 0, and 0 is put back when the routine returns.
* The villager who rang it. "Takes life", the loss of 90 health and "Grants
  wisdom" act on the record the game's search 0x44B440 answers (the first adult
  whose task is ringing the Gong). Its four calls whose answer is used
  (0x44EB9E, 0x44EE06, 0x44F34C, 0x44F3BD) are scope calls: the game's search
  runs, then the chosen villager's index replaces its answer -- only while the
  Gong's use runs, and only when that record is still the villager chosen (its
  identity taken at the purchase) and passes the search's own test (present,
  living, adult, not a totem statue). Otherwise the game's answer stands.
* "Takes youth" / "Grants youth" call the same search (0x44EF36, 0x44EFA9) only
  to see that a ringer exists, then write the age of the FIXED records 6 and 15
  through ESI (stock defect). With a villager chosen (valid as above and not
  carrying a baby) the search answers that villager and ESI is moved by the
  distance from the fixed record to the chosen one, so the game's own stores
  write the chosen villager; ESI is popped right after. Random, or a chosen
  villager no longer valid: records 6 and 15, as the game does.
* Who falls sick: a "choose who" whose villagers are all gone at the ring goes
  back to the game's own rolls for that ring.
* Not offered, with the reason (also in `docs/story-island-outcomes.md`): which
  women "Grants life" makes pregnant (no roll: every eligible woman), and the
  "Grants life" rand(50) stored at +0x5EC (nothing reads it).

Buying it makes the Gong ready to ring at once (the owner, 2026-10-20). The Gong
rests about a day after each ring (0x461B5D: +0x2EAC8 = the clock + 86400); the
game marks it ready by writing 1 there when its fourth piece completes
(0x4639F6). The purchase writes that same 1 when the Gong is whole and resting;
while the Gong is not whole (+0x2E7F0) it is refused and nothing is written or
spent. The ring afterwards rests the Gong again as the game does.

## Recharge Chief Powers (The Secret City)

The owner (2026-10-20): "add an equivalent 'Recharge Chief Powers' in the
Upgrades menu that makes the chief's powers available immediately after
purchase, with the same tech point cost." The equivalent is Pick Gong of Wonder
Outcome, which makes the Gong ready to ring at once: a separate button in the
Tech menu, not an island event (no Island Event lock), charged through the same
path at the same price -- the Island Event upgrade's, so 0, or 30,000 with
Story / Cheat Upgrades cost Tech Points, taken only when the powers are
recharged.

The Tribal Chief's three once-a-day powers each keep the clock time they can
next be used in the world object (0x428B60()), on the game's clock 0x403330:

| Power | Next use | Use | Leadership |
| --- | --- | --- | --- |
| Granting food | +0x12F00 | 0x421A30, hotspot 15: action 0x87 | 1 (the tech text) |
| Educating the children | +0x12EFC | 0x466828, the chief dropped on a child: 0x45D460, action 0x39 | 2 |
| Pointing out a rare collectible | +0x12EF8 | 0x421BE0, hotspot 0x25: action 0x89 | 3 |

Each use tests `stamp > clock` (then the chief says "The chief can only do this
once every 24 hours", say 0x2A through action 0x72, and nothing else happens);
otherwise the power runs and the stamp becomes clock + 0x14370 (23 hours). A new
village sets all three to its clock (0x4280C6-0x4280E0); the robe's success
0x431FE0 writes 0 to all three when a villager becomes the chief (0x432013,
0x432022, 0x432038). The purchase writes that same 0 to each stamp still ahead
of the clock and nothing else, so the next use rests the power again exactly
as the game does.

Refused with a message, nothing written and nothing charged: no living chief
(the game's own chief test 0x45FC00, as the Custom Island Event's Tribal Chief
status uses it); Leadership level 0 ([0x582618 + 4*4] through 0x426FC0(4): the
first power comes at level 1); every power ready already. Emulated in all three
population modes (tests/test_vv3_recharge_chief_powers.py), including the
game's own food, lesson and collectible routines afterwards; not yet run in the
game.

## Stock behaviour found in passing (reported, not changed)

The owner's rule: no original-game behaviour is changed without being reported
first. These are offered exactly as the game produces them:

* The Secret City's Royal Jelly: the clear vial's text says the jelly spoiled, yet it is the clear vial
  that cures and raises Healing; the dark vial's text says it worked, yet it
  changes nothing. The owner has since approved a fix: with The Secret City's
  "Fix Vanilla Bugs" (default on) the dark vial cures and the clear vial does
  nothing. The Healing setting is tied to no button, so it applies to
  whichever vial cures in the game being played. "Fix Vanilla Bugs" also
  makes The Lost Children's Crystal Ball need a second living villager, and
  Pick Island Event follows that condition when the fix is in the game.
* The Lost Children's Gong "Takes youth" / "Grants youth" write fixed villager
  slots 6 and 15, not the villager who rang it.
* Several health losses have no floor (A New Home's old-fruit crate finder and
  rotting-crate finder, The Lost Children's fire ants and mice finder), and A New
  Home's Mysterious Face stranger's farming can reach 106.
* The Secret City's quartz vial: at age exactly 280 the text promises one result
  and the apply takes the other; its body-change branch can never run. The
  text is fixed by "Fix Vanilla Bugs" (a 14-year-old reads the elder text);
  the body-change branch is left as it is.
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
  once counts once; changes added for a villager twice are combined into one entry:
  every like and dislike change is kept (two entries that each add a like both add it, in order,
  up to 64 changes per villager), any other field set twice takes the later entry's value, and
  a villager who dies or disappears gets nothing else (the count line under the list says so as you
  choose a villager who is already in the event). Edit shows the last like, remove-a-like, dislike and
  remove-a-dislike change of a combined entry and keeps the entry's others. New Believers adds seven
  more toggles: **All Heathens**, **All Blue Heathens**, **All Red Heathens**,
  **All Orange Heathens**, **All Purple Heathens**, **All Chief Heathens** and
  **All Heathen Mommies** (the type the game's mask draw 0x4728C6 shows).
  Each villager's row names the role the game keeps for them, read live as the
  list opens: Golden Child (A New Home), Esteemed Elder and their totem (The
  Lost Children), Tribal Chief (The Secret City), Believer, Retired Chief or
  Heathen type (New Believers). The Tree of Life keeps no such role.
  The **action** list offers every action the game's own code can start for
  one villager (island events', puzzles', the Golden Child's, the Tribal
  Chief's and the Heathens' included), for any villager, labelled with the
  text the Details screen then shows, grouped and sorted; an action that may
  harm the game or the save ends "(Unsafe)" and its reason is shown, with the
  advice to back up the save, before it is confirmed. The full list per game
  is `docs/custom-island-event-villager-actions.md`
  (scripts/build_cie_actions_doc.py).
* **New villagers**: how many, sex, age, name, head and body, likes and
  dislikes, skills, custom title, mask.
* **Parents**: the parentage data of the chosen villagers.

Every value is checked when a dialog closes and a value the game does not
accept is refused with its valid range. Buying the event (0 tech points)
makes the island event due **exactly as the Island Event purchase does** -- the
same lock as Pick Island Event: one island event, pick or custom event at a
time, refused while one is queued. An undelivered Custom Island Event never
lapses with time (the owner, 2026-10-06); it is dropped only when the village
changes.

### Delivery

**Within seconds.** Once the countdown is due, every game's event trigger runs
every 2 seconds and draws one random villager, firing only when that villager's
age equals its processed age; a miss just waits for the next draw, so in a
village with many rejuvenated villagers an event could wait minutes. The drawn
villager is never used afterwards. While a Custom Island Event is armed, the
trigger's draw (VV1 0x4237DD, VV2 0x42EEED, VV3 0x468757, VV4 0x43FA70, VV5
0x44272F) goes through a wrapper that asks the game's own picker again, with
the same arguments, up to 64 times until it draws a villager the trigger
accepts (native/vvfp_story_upgrades/story_fast_delivery.inc). With nothing
armed it is the stock call; a village where nobody matches waits exactly as the
stock game does. Natural island events, Pick Island Event and Pick Gong of
Wonder Outcome are unchanged.

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

**A new tribe's two opening island events (v1.35.73).** The owner: "ALL VV
GAMES WILL ALWAYS SHOW TWO ISLAND EVENTS WHEN STARTING A NEW TRIBE GAME!!!
THIS IS BASE-GAME". Each game's village start sets the trigger's island-event
counter (Island Events Seen) to 0 and makes the first event due 900 s later;
the trigger makes the second one due 30 minutes after the first only while
that counter is 0, and every later one hours apart:

| Game | Counter | Village start: counter 0 / first event due | 30-minute second event |
| --- | --- | --- | --- |
| A New Home | world+0x9E40 | 0x41C000: 0x41C3EB (ebx 0 from 0x41C009) / 0x41C4AE | 0x423A37 |
| The Lost Children | world+0x2E51C | 0x424C80: 0x4251D5 (ebx 0 from 0x424CA1) / 0x4252A2 | 0x42F147 |
| The Secret City | 0x5824C4 (statistics 0x5824A0 +0x24) | 0x427F70: reset 0x426450 at 0x427FD8 / 0x4280B9 | 0x468899 |
| The Tree of Life | 0x4D6E04 (statistics 0x4D6DE0 +0x24) | 0x41F1E0: reset 0x41D9D0 at 0x41F248 / 0x41F322 | 0x43FB9D |
| New Believers | 0x51D37C (statistics 0x51D358 +0x24) | 0x4246A0: reset 0x41EBF0 at 0x42473D / 0x42485B | 0x442801 |

(The three statistics blocks are 0x98 bytes, zeroed whole by the reset and
copied to and from the save by 0x4264A0 / 0x426480, 0x41DA20 / 0x41DA00 and
0x41EC40 / 0x41EC20.) While that counter says fewer than two island events
have been made, a player's custom event is never delivered: the family rolls
and the quicker villager draw (before the trigger counts the event) and each
delivery point above (after it) leave the event to the game, and the custom
event stays queued with the same lock. Bought then, the purchase does not make
the island event due (that would bring the first opening event forward); once
the game has made both, the companion's per-frame tick makes it due exactly as
the Island Event upgrade does, so the custom event is the third
(story_custom.inc `ce_held`, story_custom_ui.inc `ce_opening_tick`). Choose
Time Skip Amount's closing notice is not an island event (its count is taken
back) and is not held. tests/test_story_opening_events.py runs each game's
real trigger three times in a new village.

**A village where everyone has died (v1.35.80).** The owner (2026-10-21):
"allow Custom Island Events to be bought and triggered when everyone is dead
(so the player can add new villagers)". None of the five games ends a village
whose last villager dies: there is no game-over state, no return to the title
and no change to the save. The village keeps running (clock, food, menus); the
game shows "Your tribe has been lost! Game over." (eSayGameOver) on its status
line every 2 s while its population count is 0 (VV1 0x421B40(0x1F) from the
main update 0x42373C, VV2 0x42EE49, VV3 0x4686AF, VV4 0x43F9B7, VV5 0x442676,
each a 5-second status label), and A New Home, The Lost Children and The Tree
of Life queue their "all of your villagers died" tip once and mark their
tutorial tips shown (stock, left as it is). What stopped a Custom Island Event:

| Game | Trigger's count call | Skip | Routine between draw and age check | Resume |
| --- | --- | --- | --- | --- |
| A New Home | 0x4237CB call 0x41CF90 (world) | 0x423ABE | 0x41D110 -> edi | 0x423816 |
| The Lost Children | 0x42EEDB call 0x425860 (world) | 0x42F1D4 | 0x426110 -> edi | 0x42EF26 |
| The Secret City | 0x468743 call 0x45E8F0 (manager) | 0x4688DF | 0x402200 -> ebp | 0x468798 |
| The Tree of Life | 0x43FA4E call 0x467610 (manager) | 0x43FC0E | 0x416EB0 -> ebp | 0x43FA9B |
| New Believers | 0x4426FB call 0x4713F0 (manager; believers only) | 0x44285F | 0x417650 -> ebp | 0x44275A |

(the trigger does nothing, not even reschedule, while the count is 0), New
Believers' selector returning before its delivery site when no stock event is
possible (0x4188E5 `test edi, edi; je 0x4189C5`), and the companion's own
purchase refusing a village with no living adult. Each count call is now a
call to a stub (native/vvfp_story_upgrades/story_empty_village.inc) that runs
the count unchanged; only when it answers 0 and a plain Custom Island Event is
queued for this village does it drop its return and resume after the villager
draw and age check with the register the stock code has there. The drawn
villager is never used after that check in any game, and nothing from there to
the popup reads a villager record for a custom event (its object shows no
villager), so the game reschedules, plays its sound, counts the event, builds
it, and the usual delivery point puts the custom event in it. New Believers'
selector exit, with no stock event possible and a plain custom event due, makes
the stock path's two trophy calls (0x413450 on 0x4DB358 with 0x2F and 0x30) and
goes to 0x41895B with esi 1. The `mov ecx` before each count call is left as it
is, so 256 Villagers (Experimental), which moves the manager to 0x800000, keeps
working. The creators (0x43C350, 0x44F580 via 0x44C600, 0x45FF50, 0x467D10,
0x471E20) take the first free record and read no other villager; the room
predicates pass at population 0; bodies keep their records and can be revived.
Nothing else needs resetting: once the count is above 0 the game's own next tick
treats it as a normal village. The purchase now allows an empty village; a
question with two choices is refused (it needs a living villager to show), an
empty village does not wait for its two opening island events (its trigger can
never make them), and A New Home's and The Lost Children's first island event
stays the game's own visitor. Villager Changes says there is nobody to change
when no villager or body is left. Tests: tests/test_story_empty_village.py (each
game's real trigger in all three population modes and with 256 Villagers, the
selector exit, the purchase, arrivals and skeletons). **Not yet seen in a
running game.**

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
| Faction / status | -- | Esteemed Elder (0x44D190, with its totem); totem art 1-8 | -- (Tribal Chief omitted) | -- | believer / Heathen (the game's conversions, not counted; puzzle Heathens refused) |
| Behaviours | stop, dance, swim, relax, recover | stop, enjoy the pond, relax at the beach, honor the dead, sneeze, recover | stop, recover | stop, recover | stop, recover |
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

New Believers' faction changes are the Maker's, not the player's, so they
count nowhere (owner, 2026-10-02). "Becomes a believer" runs the game's own
conversion 0x4668B0, which adds to the trophies A Heathen's Prerogative (0x13,
3 conversions) and If You Can't Beat 'Em... (0x14, 10) in the trophy table
0x4DB358 -- earning one also queues its popup and adds to Over-Achiever and
Unachievable -- and to the patcher's Heathens Converted (0x51D3A4). The
companion copies the whole trophy table and that total before the call and
puts them back straight after, on the game thread, before any frame can draw
the popup or any save or export can read them. "Becomes a Heathen" (0x4669E0)
and a new Heathen (0x46FD20) write no counter at all (emulated on the stock
code and the full catalog). A conversion in play still counts as it always did.

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
click. Queueing is the plain event's: the same lock, no lapse with time,
bound to the save slot and the Start Over / delete generation; an answer in a
village other than the one the question was asked in changes nothing.

The picture (v1.35.48): **Villager in the picture** in the Choices dialog is
**Random (a living villager)** or one of the village's villagers (name, sex,
age; in New Believers believers only). The pick is kept with the villager's
record and identity -- name, sex, head, body, likes and dislikes, as a
villager change is -- taken when the event is bought; when the question is
asked, that villager is shown only if the record still holds the same living
villager (in New Believers, still a believer); otherwise, and for Random, a
random living villager is shown (the game's own random routine). Every game
shows the villager: A New Home's and The Lost Children's encounter popups draw
the villager's portrait under the title (the dialog's own villager field,
+0x5098 / +0x50A0, which their draw routines 0x4187E0 / 0x41F430 read) and
select that villager as their own setup does (0x43A160 / 0x44B2D0); the text
then leaves five empty lines under the title, as every stock encounter does,
in the question and the result. The Secret City, The Tree of Life and New
Believers must show one (their two-button popup is not drawn without it).

Every value is checked when OK is pressed and again when the event is bought:
both labels non-empty and within the game's label width (letters, numbers,
spaces and . , ! ? : - ' only), one to four outcomes per button, each chance
1-100, each result text non-empty and fitting the result popup, and the usual
room checks for each outcome's new villagers and babies. The engine is
`ce_choice_*` in `native/vvfp_story_upgrades/story_custom.inc`; the data is
`ce_choice` / `ce_outcome` in `story_custom.h`.

**Each game's own two-button popup asks the question** (the `CAP_CHOICE`
capability in each `story_c*.inc` adapter, with the popup's question / result
widths and line counts, the label width and the game's own rand). In every
game the question and its result share one dialog: a click removes the two
buttons, the result replaces the question and OK closes it.

| Game | The popup | Where | Text (characters x lines), label |
| --- | --- | --- | --- |
| A New Home | the villager encounters' (0x41A460) | the family rolls send a question there; the setup call 0x41A51F is replaced: question +0x74, labels +0x4E92 / +0x4F92, the villager in the picture +0x5098 (selected as the stock setup does), a variant past the stock jump table; the resolve call 0x41A444 (an outcomes scope call) is handed to the answer for that dialog only | 49 x 13 (15 with the picture's two lines), 34 |
| The Lost Children | family A's (0x422380) | the same at 0x42244A (question +0x7C, labels +0x4E9A / +0x4F9A, villager +0x50A0) and 0x422364 | 46 x 16 (18 with the picture), 30 |
| The Secret City | the event dialog 0x4192F0 | the pick site hands it a copy of the two-choice vtable 0x47EA40: title / question / labels / result through the custom ids, the villager in the picture (pose 5), the answer on the click (+0x34), nothing more on OK | 48 x 11, 32 |
| The Tree of Life | 0x417790 | the same, vtable 0x48CB64 | 48 x 11, 34 |
| New Believers | 0x418020 | the same, vtable 0x497D34; the villager shown is a believer, never a Heathen | 48 x 11 (results 17), 38 |

The limits are each game's longest and tallest stock two-choice texts and
labels. A New Home and The Lost Children size the popup once, from the
question, so the question is padded with empty lines to the tallest result
either button can show (its text plus every outcome line its changes could
print); The Secret City, The Tree of Life and New Believers size it from the
question and both buttons' tallest results. In A New Home and The Lost
Children the result repeats the title (the result replaces the whole text);
in the other three the title stays above it. Their two-choice popup is never
shown without a villager, so a question waits while nobody living
can be shown (A New Home and The Lost Children then show it without a
picture). A New Home's and The Lost Children's first island event is always their
two-choice family, so a question may be that event (a plain one may not).

Evidence level: emulation of each game's rendered executable in all three
population modes (`tests/test_story_two_choice_hooks.py`: the question,
labels and fields in each game's own dialog, the game's own click handler
reaching the answer, the rolled outcome applied once and its text shown, a
natural encounter and another dialog left to the game, the remembered dialog
forgotten, a missed dispatch writing nothing; 16 mutations of the hooks, each
caught), and **live in all five games** (v1.35.47 test build, 2026-10-02): the
question in each game's own popup, a click, the outcome's result and its food
change in memory (both outcomes of a 50/50 button seen), nothing more on OK.
The picked villager (v1.35.48): emulated in all three population modes (the
pick shown, a pick whose record changed, died or was reused falls back to a
random living villager, a Heathen never shown in New Believers, no picture
when nobody living can be shown; 11 mutations of the pick, each caught), and
live in all five games (v1.35.48 test build, 2026-10-02): the picked villager
in each game's own popup (A New Home and The Lost Children: the portrait under
the title and that villager selected -- named in A New Home's villager panel,
read back from The Lost Children's memory; The
Secret City and The Tree of Life: two picks in a row, each shown; New
Believers: only the three living believers offered, the only male believer
shown), the result, and the food change.

### Custom titles

A villager's title can be replaced by the player's text (1-31 letters,
numbers, spaces and . , ! ? : - '). It is kept per save slot in

    <save folder>\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save N.dat

(`native/shared/custom_titles.h`), never in the save, and shown in the
villager panel (VV1 0x41FD75, VV2 0x429DE3, VV3 0x468FC8, VV4 0x4404D9, VV5
0x44319E) and as "Custom title:" in the Village Population roster and the
Village History. No game's Details screen shows a title. A title belongs to
its record only while the record holds the villager it was set for (the name,
likes and dislikes, checked on every look); it is dropped when that villager
is seen to die, and a reused record never inherits it. After a load (the
games pack their records) every title goes to the one villager who has its
whole identity: the name, likes, dislikes, head, body and sex, and an age and
skills no lower than stored (version 3 of the file keeps them). When two
villagers could be them, or a namesake who is not them is all there is, the
title is kept PENDING -- shown on nobody, never dropped (v1.35.70) -- and
bound again as soon as exactly one villager has that identity and no other
title claims them -- unless two or more could be them at once while it waited
(CONTESTED): then the one left after the others die or leave is never taken
for them, and it waits for the player; Check Saves & Logs asks about every
pending title. Start
Over deletes the slot's file, and a table that sees its file gone forgets the
old village instead of writing it back.

### Not offered, and why

* A New Home: the Golden Child (only its puzzle makes one; the creator's
  family 0xC7 forces sex, age and looks); puzzle completion (no callable
  completion routine). The 47th like word ("sleeping") IS offered: the game's
  own creator never rolls it, and the Details screen's reader that overran on
  it is fixed by Fix Vanilla Bugs.
* The Lost Children: puzzle states; fish and soil refills.
* The Secret City: Tribal Chief (only the robe puzzle; a second chief is a
  known defect); the beehive refill (tied to its puzzle); puzzle states.
* The Tree of Life: fruit-tree and fishing refills (no game routine); weather
  types other than rain and clear (not identified); puzzle states.
* New Believers: puzzle states (prerequisites unproven); the puzzles' own
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
