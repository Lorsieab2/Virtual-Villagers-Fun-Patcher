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
