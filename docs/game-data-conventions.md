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
