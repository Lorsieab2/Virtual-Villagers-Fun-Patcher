# Duplicate purchase guards

Buying Time Warp, Island Event or Barrel of Babies more than once charged for
each purchase while only the first took effect. This records the cause, how
each game now refuses the duplicate, and the constraints that shaped it.

## The cause

Every game queues these purchases by **writing a value that may already be
there**, so the write is a no-op the player still pays for.

| Game | Island Event | Barrel of Babies |
| --- | --- | --- |
| VV1 | countdown `player + 0xA300` zeroed | flag byte in `.shr` set |
| VV2 | countdown `player + 0x2EAE0` zeroed | flag byte in `.shr` set |
| VV3 | countdown `manager + 0x12EF4` zeroed | flag byte `0x4B3C75` set |
| VV4 | countdown `world + 0x170E0` zeroed (getter `0x41FE70`) | armed flag `0x728B04`, **and the same countdown** |
| VV5 | countdown `manager + 0x17D3C` zeroed | flag bit 4 of `0x51D388`, **and the same countdown** |

In VV4 and VV5 the Barrel rides the Island Event's own trigger, so a pending
event of either kind blocks both rows.

Time Warp needs no guard: it subtracts from the clock, so a second purchase
does advance the village again.

## How each game refuses

**VV1, VV2, VV4, VV5 — the row is never clickable.** The Tech menu's state
word gains two bits, and the companion DLL draws those rows as disabled
"Unavailable" buttons. Because the click cannot happen, the charge path is
never entered, and no refusal message is needed — which is what makes this
affordable, since the executables' string blocks are effectively full.

```
STATE_ISLAND_PENDING  0x800000
STATE_BARREL_PENDING  0x1000000
```

These are **dedicated bits**, not the existing `1 << (8 + row)` "unavailable"
encoding. In a 14-row Tech menu that encoding is ambiguous: bit 9 means both
"row 9 satisfied" and "row 1 unavailable". VV4's dialog already worked around
this with an `(8 + row) >= row_count` bound. The dedicated bits sit above every
row bit (0-13), every `(8 + row)` marker (8-21) and every `STATE_*` flag
(16-22).

Computing them costs the constrained menu payload only a 5-byte `call`; the
checks live in a small cave. VV1's helper runs in the menu's own frame, reading
`[esi+0x0C]` and OR-ing straight into EDI, so the call site needs no argument
setup at all — its cave had two spare bytes.

**VV3 does the same, but computes it in the DLL.** Its payload has no cave
space left to work out the state, which is exactly what the companion DLL is
for: the DLL runs inside the game's own process, so it calls VV3's own
parameterless world-manager getter at `0x428B60`, reads the countdown and the
Barrel flag itself, and disables the rows. Nothing is asked of the executable,
and VV3's payload is byte-identical to what it was before this feature.

It uses the same probe the executable uses to tell the stock and expanded
builds apart (whether the immediate at `0x42883A` is 256), so it reads the
right field in both.

VV1 and VV2 keep a small executable-side helper for a different reason, not a
space one: their player object is reachable only as `[menu_object + 0x0C]`, and
a scan of the running process found no global holding it, so the DLL has no way
to obtain it on its own. VV3's manager has a getter; theirs does not.

VV3's older Island Event refusal message (DLL result code 10) stays as a
backstop behind the disabled row.

The executable-side guards sit **after `jb insufficient`** and **before the
deduction**. After the branch because their compares overwrite the flags it
reads — the same mistake the paused Time Warp guard made, caught as a P1 on
three games. Before the deduction because refusing afterwards still costs the
player the points, which is the reported bug.

## Finding space, and how not to

Three cave placements were chosen and each collided, because each analysis was
missing a different source of claims. A candidate window must be free against
**all** of these:

1. the stock image (non-zero bytes are real game data);
2. every optional feature manifest — a patch absent from one composition still
   owns its range when selected (VV3's Village-Wide Upgrades owns `0x7B820`);
3. spans declared as `length` beside an `after_base64` payload, not just hex
   `after` fields (the Village Statistics writer owns 512 bytes at `0x7B464`);
4. the automatic safety patches, which are generated in `data/builds.json`
   rather than declared in any feature manifest (`0x7B260-0x7B33C` for VV3);
5. fun patches also declared in `builds.json` (`vv3_nature_honey_refill`).

Checking only "zero in the stock exe and in one built exe" passes all three
bad candidates. The patcher's own overlap detector is the authority, and it is
fail-closed, so a bad placement fails the suite rather than shipping.

Final placements: VV1 `0x8BF00`, VV2 `0x9A4A0`, VV4 `0xCCC20`. VV5 inlines its
checks in `tech_menu`, which had 257 spare bytes, so no payload byte position
outside that routine moves — its validator pins several by exact position.
VV3 needs no cave at all now that its checks live in the DLL.

That is the general answer when a game runs out of room: move the logic into
the companion DLL, not into a reduced version of the feature. An earlier
attempt gave VV3 a refuse-after-the-click message on the grounds that it had no
cave space, which is the wrong trade — the space constraint decides where code
lives, never what the player gets.

## The Barrel of Babies short-spawn, and what it is NOT

Reported in play: the Barrel delivers fewer than three children -- sometimes
zero -- while skeletons lie unburied, and delivers three again once villagers
have buried some. **It charges in full either way**, in all five games. That
last part is the actual defect: paying 75,000 tech points for zero children.

Two candidate mechanisms are ruled out by evidence, and both are ruled out for
the same reason, so neither should be tried again:

**It is not the living-population count.** Both games' own counters skip any
record whose health field is `<= 0` -- VV1's at `0x41CF90`
(`cmp dword [ecx], 0 / jle` before the increment) and VV2's at `0x425860`
(`mov edx, [ecx+0x4fc] / test / jle`). The dead are already excluded there, so
unburied bodies do not inflate it.

**It is not the population cap.** VV2's cap is a stock base of 90 plus a 0-25
collection bonus. The reproduction had **31 living villagers**, so the existing
`demand + 3 > cap` gate passed with enormous room to spare -- as it should
have. A guard written against this cap would not fire in the reported scenario
at all.

So the limit lives further in, where the spawn places each individual child.

**What is known about the record pool** (VV2, from `0x425860`):

| Thing | Value |
| --- | --- |
| Pool pointer | `[gamectx + 0x305A4]` |
| First record | pool + `0x30` |
| Record stride | `0xE48C` |
| Occupied byte | record + `0` |
| Health | record + `0x4FC` |
| Slot count | 256 (four records unrolled x 64 iterations) |

With 31 living plus a handful of skeletons against 256 slots, a plain
free-slot search should not run out either -- which is why the mechanism is
still open rather than guessed at. 83 separate call sites walk this pool by
that stride, so narrowing it by static reading alone is not practical.

**What would settle it:** one reproduction with the pool read live -- occupied
count versus living count at the moment the Barrel short-spawns, and which
slots the children that DO arrive land in. That distinguishes a slot-allocation
limit from a world-space placement limit (skeletons physically blocking the
drop points), which are the two remaining candidates and want opposite fixes.

Until then the row is deliberately NOT blocked on a guessed threshold: a guard
that does not fire in the reported case would be worse than none, because it
would look like the bug was fixed.

## Known gap: capacity is checked at purchase, not at delivery

The Barrel row is refused unless three villager slots are free, and the
purchased barrel's child count is forced to three. Both decisions are made when
the player buys. The event itself is deliberately deferred -- VV1 waits 180
update ticks, VV2 90 -- so the village can change in between: a pregnancy
completing, or another event taking a record, can leave fewer than three slots
by the time the children are actually placed. The stock per-child allocation
then stops early, and the purchase has already been charged.

The arming window is now as small as it can be: the three-child override is
raised immediately before the deferred dispatch rather than at purchase, so a
natural barrel firing during the delay can no longer consume it.

Re-validating capacity at delivery is NOT implemented, and the reason is
specific rather than an oversight. The count-roll site holds only the event
object in ESI; it has no route to the villager pool. VV1's records are reached
as `[player + 0xADE8]`, and a scan of the running process found no global
holding that player pointer -- which is the same reason VV1's menu helper has
to read it from `[esi + 0x0C]` instead. Closing this properly means plumbing a
context pointer into the deferred dispatch, which is a real change to that
path rather than an addition beside it.
