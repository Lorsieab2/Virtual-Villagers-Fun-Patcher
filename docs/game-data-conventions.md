# Game data conventions

Facts about how the Virtual Villagers games store their data that apply
across the series, rather than to one feature. They are recorded here
because each one has already been got wrong at least once, and because a
mistake in any of them produces output that looks reasonable instead of
output that obviously fails.

## Indexing starts at zero

Where a game stores an index into a list, the first entry of that list is
value **0**, not value 1. This holds generally: preference lists,
spritesheet rows, and the other enumerated tables the games index into.

There is no adjustment to apply when reading such a value. Adding one to
"convert" it shifts every result by a single entry, which is the worst
possible size of error — a villager who likes ants is reported as liking
crowds, and nothing about the output looks malformed.

## Twenty age units make one year

Ages are stored in age units. **20 age units = 1 year.**

Deriving this ratio from a single observed villager does not work, because
a villager's displayed age is rounded and a lone sample is consistent with
several nearby ratios. The figure above is the game's, and should be used
directly rather than re-measured.

## Likes and dislikes are arrays in all five games

A villager's likes and their dislikes are each an **array** of consecutive
`i32` indices into that game's preference list — not a single field. This
is true in all five games.

A slot is empty when it holds `-1` **or** when it holds an index at or
past the end of the list. Both markers occur in real villages and both
mean the same thing. Code that treats an out-of-range index as a sign it
is reading the wrong offset will reject the correct offset; that has
happened.

The game's Details panel displays the **first filled** entry of each
array, not slot 0. Two real villagers show why the distinction matters:
one whose first dislike slot is empty while the second holds the value the
panel displays, and one whose slots are all empty and whose panel line is
consequently blank. Reading slot 0 reports the first as having no dislike
and the second as disliking whatever `-1` decodes to.

The list itself grew across the series — 47 entries in VV1, 62 in VV2, 79
in VV3, VV4 and VV5 — so each game must index its own list. The lists
share a prefix, so indexing the wrong one yields correct-looking words for
low indices and silently wrong words for high ones.

## Zero is a real appearance value

`0` is a valid head value and a valid body value. It cannot be used as an
"absent" or "unset" sentinel for appearance fields, and a head or body of
zero must be printed rather than suppressed.

## Saved and in-memory layouts are different address spaces

A villager record's offsets in a save file bear no relation to its offsets
in the running game's villager array. In VV5 the record stride is `0x118`
on disk and `0x2F44` in memory. An offset measured in one must never be
carried into the other; it has to be measured again.

## A correlation identifies a value, never its meaning

When a field in a save file changes in lockstep with a field in memory
across every villager, that establishes the two hold the **same value**.
It says nothing about what that value *means*.

This is not hypothetical. Two fields once correlated 45 of 45 with a pair
believed to be likes and dislikes. Changing a villager's clothes in-game
moved one of them, proving the pair were head and body. Meaning is settled
by perturbing the game state and watching what moves, or by reading the
game's own display — never by correlation strength alone.

## Pregnant and nursing are one state

The games do not expose a pregnancy readout distinct from nursing: a
carrying villager's Details panel reads `Nursing for: N min`. The owner
treats the two as **the same state**, and these logs record it as one.

A candidate field must therefore not be rejected because its holders turn
out to be nursing rather than visibly pregnant. That rejection cost a long
detour on VV2, where `+0x540` — the correct field — was discarded twice on
exactly that reasoning before the game's own panel confirmed a holder.

## A litter is one, two or three babies

In **all five games** a villager carries 1, 2 or 3 babies, never more. Any
candidate litter field whose live values fall outside that set is
misidentified, whatever else fits.

This is a cheap falsification test and it works: VV2's `+0x5E4` is
female-only, which fits a pregnancy field, and was briefly shipped as the
litter. Its values are 1, 3 and **5**, and 5 is not a possible litter, so
the field is something else. "Female-only and small positive" is not
sufficient evidence; the value set must be a subset of {1, 2, 3}.

Nursing adds 1–3 to the population count, matching the litter range, and
those babies have no villager records of their own.

## The games are alike; an empty result indicts the search

The five games store the same villager concepts in the same shapes. When a
field is found in one game, the corresponding field exists in the others.

So a search that comes back empty is evidence that **the search** is
wrong, not that the game is unusual. The correct response is to find which
assumption excluded the answer — a threshold, a unit, a gender filter, a
stale anchor — rather than to conclude that this game differs.

Concretely: VV2's pregnancy field went unfound through several passes
because the search imposed a `value >= 200` floor carried over from VV1's
scale, and because it required a conception stamp to sit *below* the
mother's age in a way that ignored the 20-units-per-year conversion. The
field was at `age + 0x10`, exactly where VV1 puts it.

## Displayed values are converted; compare in the same units

The number a panel shows is frequently not the number in memory. Age is
the standing example — 20 units to the year, so a villager displaying 41
holds 836 — and a raw read will never equal the displayed figure.

Treating that mismatch as proof the offset is wrong is a mistake that has
been made repeatedly. Convert before comparing, and when a measured value
is off from the display by a suspiciously round factor, suspect units
before suspecting the address.

## Villagers are children or adults — use those words

There are exactly two kinds of villager: **children** and **adults**. Those
are the terms this project uses, in code, in comments, in logs and in
conversation.

"Newborn" is not one of them. The owner has corrected it repeatedly, and it is
not merely a style preference — the word implies a third category that does not
exist and invites treating the youngest villagers as a special case to be
filtered, reported on, or excluded. They are not special. A child is a villager
and is logged like any other.

The underlying rule, which is what makes the distinction load-bearing:

* An adult can gain **nursing** status. That adds 1–3 to the population count.
* The babies being nursed are **not separate villagers**. They have **no
  record of their own** — nothing in the villager array represents them.
* A villager becomes a separate villager, a child, at **age 2** (40 age units),
  which is when a record first exists for it.

So an age floor added to "filter out the very young" filters out nothing that
was ever there, while wrongly dropping real two-year-olds who are genuine
separate villagers. That mistake has been made here before.

## The games store both parents on the child, for life

**The games always save the parents' names, head values and body values in the
child's own villager data.** This is the owner's statement of how the series
works, and it is the fact any parentage feature should be built on.

It holds for **VV2, VV3, VV4 and VV5**, and it holds permanently — an adult
villager still carries its own parents' details, not just a child. So a villager's
ancestry can be read at any moment from its own record. Nothing has to be
captured at a birth, and no companion has to watch for one.

Measured live, VV2 keeps the father's name at `+0x57D` and the mother's at
`+0x596`, with their appearance at `+0x5B0`/`+0x5B4` (father) and
`+0x5B8`/`+0x5BC` (mother). The two agree with each other: across 159 stored
parent names, 141 had the named villager's current head and body equal to the
stored pair. The 18 that differed are villagers whose looks changed after the
birth — the Origins upgrades restyle a whole village — which is exactly what a
birth-time snapshot should look like.

Do not confuse this with the **pregnancy father** field (VV2 `+0x5C0`). That
one is the father of the child a woman is currently carrying, copied onto her
at conception and present only while she is pregnant. The owner's definition:
"the father of the child this woman is carrying". The two are different fields
answering different questions, and only the pair above is the villager's own
ancestry.

**VV1 is the exception.** A New Home stores no parent fields at all, which is
why it needs a sidecar that reconstructs parentage and binds it to the living
roster. Its logs get the same Parents block by that route instead.

**VV2 to VV5 show the parents on the Details screen**, so the game itself is
the reference: open a villager and read the father and mother off the panel,
then confirm the record holds those names. That is the check to reach for
first, ahead of any statistical argument.

Where a screen is not available, a wrong offset still fails visibly. Three
independent tests:

* **Gender purity.** A father field resolves only to male villagers and a
  mother field only to female ones. VV2's scored 74 male / 0 female and 0 male
  / 85 female — a coincidence cannot be that clean.
* **Sibling grouping.** Villagers sharing all four appearance values are
  siblings, so real fields cluster into family groups. A wrong offset yields
  one constant shared by everyone, or values shifted by a field.
* **A control field.** An unrelated pair of dwords matches a living villager's
  appearance 0% of the time, against 45–87% for the real ones.

## The games simulate villagers before the player's tribe exists

Records can reach the conception hook for villagers who are **not** in the
tribe the player then plays. The owner's first v1.35.27 VV3 tribe logged seven
conceptions between fourteen villagers who appear in neither of that tribe's
saves, before its first save. Only the two hooked callers reach VV3's
conception routine (`0x45833E`, `0x45B8C9`), so those villagers were live
records in the game's table when it ran. VV5's own `ldwLog.txt` from the same
session names two villagers (Upuro, Sanda) who never joined the tribe either.
The owner confirmed no earlier tribe had been started in that VV3 session.

So "a record exists for a villager nobody has" is not by itself a logging
defect or a duplicate. It is the window before the village's first save. The
parentage companion holds records written in that window until the village is
known, then keeps only those whose villager still occupies the same slot as the
same villager (`native/parentage_export/parentage_export.c`, `emit_record`).
Where the pre-tribe simulation comes from (for example the scene behind the
menus) is **UNVERIFIED**; the fix does not depend on it.

## A villager can be born without a father on purpose

VV2's Gong ("grants life", caller `0x44EB3E`) starts a pregnancy whose father
name is the game's own `"?"` placeholder at `0x476290` in `.rdata`. It is not
inside any villager record, so no father record exists to report, and the log
must say so rather than invent one. Every other VV2 caller passes the father's
name as `father + 0x564`, a pointer inside his record, which is how the hook
finds him (see `scripts/build_vv2_parentage_feature.py`).

## Shared names and shared looks are normal

Names, heads, bodies, likes and dislikes come from fixed pools, so two
villagers sharing a name, or siblings sharing an appearance, is expected game
behaviour (issues #434, #436, #443). Neither is evidence of a duplicate record.
Identify a villager by reading its record directly, or, where that is
impossible, by the full eight-field key in #436 -- never by a subset.

## VV1's `0x48B614` is the villager manager, not the Golden Child

The stock getter at `0x43DA30` allocates `0x3E034` bytes (`new`) and
constructs it with `sub_43BFF0`, whose fields sit at `+0x3DFE0` and beyond, past
256 records of stride `0x3D8`. Several VV1 Origins upgrades read
`[0x48B614]` as "the current Golden Child's record" and skip that villager
(`native/vv1_origins_icons/vv1_origins_icons.c`, `VV_GOLDEN_CHILD_PTR`). In the
owner's v1.35.27 VV1 tribe, Time Warp aged every villager by exactly 120 units
(6 years at normal speed) except Sef, listed first -- consistent with the
pointer landing on record 0. Fixed by testing the record flag everywhere; see
issue #448.

## Every conception goes through one routine per game

A villager can conceive by autonomously embracing, by the player dropping one
villager on another, during time catch-up, or through an island event (VV2's
Gong of Wonder and Love Note among them). In every game all of these start the
pregnancy in ONE conception routine: it is the only code that writes the
pregnancy fields (due, father, the father's head/body copies, litter). Every
writer of those offsets in each stock executable was enumerated; the others
only clear or shift an existing pregnancy, initialise a new villager, or (VV1's
Golden Child event) create a child directly.

| game | routine | callers | parentage hook |
|---|---|---|---|
| VV1 | `0x43BBC0` | 6 | success tails + a father stub at each of the 6 callers |
| VV2 | `0x44B980` | 6 (incl. Love Note `0x422006`, Gong `0x44EB3E`) | success join; father = arg 5 − `0x564` |
| VV3 | `0x455AB0` | 2 | success tail; father by caller-B gender branch |
| VV4 | `0x45E7B0` | 4 (resolver, 2 embrace branches, seeding) | success exit `0x45E8E4`; father = arg 4 − `0x1B9C` |
| VV5 | `0x465E00` | 4 (resolver, 2 embrace branches, seeding) | success exit `0x465F34`; father = arg 4 − `0x1B9C` |

So a parentage hook belongs at the routine's success exit, not at a call site:
a call-site hook logs only that caller (VV4 and VV5 missed autonomous embracing
until v1.35.28). **Village seeding** (VV4 `0x467C15`, VV5 `0x471B6D`) calls the
routine with its suppression argument set and a made-up father ("Joey", head 2,
body 2); it is deliberately not logged, but the resulting births are -- which
is why a new tribe can show a Birth with no Conception, or a pregnant villager
whose father is "Unknown".
