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

## Closed: capacity is now checked at delivery as well as at purchase

The Barrel row is refused unless three villager slots are free, and the
purchased barrel's child count is forced to three. Both decisions are made when
the player buys. The event itself is deliberately deferred -- VV1 waits 180
update ticks, VV2 90 -- so the village can change in between: a pregnancy
completing, or another event taking a record, can leave fewer than three slots
by the time the children are actually placed. The stock per-child allocation
then stops early, and the purchase has already been charged.

The arming window is as small as it can be: the three-child override is raised
immediately before the deferred dispatch rather than at purchase, so a natural
barrel firing during the delay cannot consume it.

**This section previously recorded delivery-time revalidation as unimplemented,
and gave a specific reason: that the dispatch site holds only the event object
and has no route to the villager pool, so closing it would mean plumbing a
context pointer into the deferred path. That reason was wrong**, and the
correction is kept visible here because it blocked the fix for a while.

The village needs no plumbing and no captured pointer. It is live at the splice
in both games, in a register the enclosing update owner is already using:

* **VV1** -- `0x42402D  mov eax, [esi + 0x10]` sits two instructions before the
  `call 0x448600` that is spliced, in the same basic block. That `[esi+0x10]`
  is exactly what the population getter takes, proved by a stock call site in
  the same function: `0x423739  mov ecx, [esi + 0x10]` feeding
  `0x42373C  call 0x41cf90`. No inter-function padding separates that site from
  the splice -- the run from `0x42373C` to the epilogue at `0x424064` contains
  no alignment fill at all, so both share one `esi`. The
  helper already recovers that register, because `mov esi, [esp + 4]` after
  `pushad` reads the enclosing frame's ESI back.
* **VV2** -- `0x42E9EB  mov edi, [esi + 0x10]` immediately precedes the splice
  at `0x42E9EE`, and EDI is untouched until the helper's own resume. The
  surrounding code drives that object through `+0x2EAC4`, `+0x2EB08`,
  `+0x30460` and `+0x305A0`, the last adjacent to the `+0x305A4` record-pool
  field the purchase preflight validates.

Both now re-run the purchase-time capacity rule against that live pointer at
delivery. **A refusal holds the paid event rather than spending it**: the
pending token stays set and a later tick retries, so the barrel arrives once a
slot frees. VV2 asks the companion DLL's `GateVV2BarrelSilent`, which shares
`vv2_barrel_has_room` with the noisy purchase gate so the two cannot drift; it
is separate from `GateVV2Barrel` only because that one raises the "close to
maximum" dialog, which a retry loop must not do.

### What this does NOT fix

This closes the **queue-window** case: capacity that was present at purchase
and gone by delivery. It does not explain or fix the reproduced short-spawn
described above, where a village with 31 living villagers and ample record
capacity still delivered fewer than three children. That mechanism -- slot
allocation versus world-space placement -- remains unresolved, and a barrel can
still be consumed short through it. The delivery recheck is not a guarantee
that every paid barrel yields three children.

## Record occupancy is not population: `+0x1CD4` in VV5

A villager record's in-use byte means **"this record slot is taken"**, not
"a villager is alive in it". Skeletons keep their records. In VV5 that byte is
`+0x1CD4`, and a survey of a village showing **Population 0** on the HUD counted
**134 occupied records**.

The two counts answer different questions, so code that iterates records has to
decide which it is asking:

- *Is there room?* -> count occupied slots.
- *How many villagers are there?* -> count living records, and say so.

The free-slot gate counts occupancy, because occupancy is what a spawn needs: a
skeleton still holds the slot a child would go into.

### What this does NOT explain

Two things were previously attributed to this distinction here, wrongly.

**It does not identify the mechanism behind the reproduced VV2 short-spawn.**
The investigation above records that the reproduced village had ample free
records, and deliberately leaves slot allocation versus world-space placement
unresolved pending a live pool capture. A VV5 occupancy survey says nothing
about which of those two caused it. Treating occupancy as the answer would aim
the eventual delivery-time fix at the wrong subsystem.

**A reading of 15 occupied against a HUD population of 18 is not reconciled by
this distinction — it is impossible under it.** Every living villager occupies a
record, and skeletons only make the occupied count *larger* than the living
count, so occupied can never be less than population. That measurement
therefore indicates a mismatched scan, a timing skew, the wrong pool, or a
different HUD definition, and it remains unexplained. It is recorded here as an
open measurement question, not as a solved one.

## Delivery-time capacity, and one window it leaves open

The purchase-time capacity gate is not the whole story, because neither game
dispatches the Barrel immediately. VV1 waits 180 ticks of the main-village
update owner; VV2 waits 90 frames of the same loop. A pregnancy or another
event can take a slot inside that window, and the stock per-child allocation
then stops after one or two children while the player has paid the full 75,000.

Both games now recheck at delivery, against the live village rather than a
pointer captured at purchase:

* VV1 reads it as `[esi + 0x10]` at the splice, and reruns the purchase ladder
  (the 12/22/47 tiers, the three housing flags, and the shared
  `POPULATION_FINAL_TIER` helper for whichever cap is installed).
* VV2 reads the same field — already in EDI at its splice — and asks the
  companion DLL's `GateVV2BarrelSilent`, which shares `vv2_barrel_has_room`
  with the noisy purchase gate so the two cannot drift.

With no room the paid event is **held**, not consumed: the pending token stays
set and a later tick retries, so the barrel arrives once a slot frees. That is
deliberately preferred over refunding or dropping it, both of which are worse
for the player than the short count being fixed.

### The window this left open, and how it was closed

The three-child override is a one-shot flag armed immediately before dispatch.
In VV1 the event construction *after* it can still fail (`call 0x44AF03`
returning zero), which left the flag armed with no dispatch. That predated the
delivery recheck; what the recheck changed is that the retry path could re-arm
it on a later tick, so a persistent construction failure became a repeating
target rather than a one-shot one.

It was **recorded rather than fixed** for v1.34.31, on the grounds that the
consequence favours the player and the trigger is an allocation failure: a
stale armed flag is consumed by the *next* barrel, natural or purchased, which
then delivers three children instead of the stock random count. Nobody is
charged for it and nobody loses a child.

**It is now fixed.** The stated reason for deferring — that a disarm "does not
fit the helper's remaining bytes and would have to route through the
patch-owned `.vv1mc` tail" — was only half right. Routing through `.vv1mc` is
exactly what it does, but that cave did not need to wait for some later
opening: the room check's `0x100` reservation already had 182 free bytes and
the disarm is 12.

The construction-failure branch targets a stub at `0x8EB80`, inside that same
reservation (room check at `+0x00`, disarm at `+0x80`). The stub clears the
flag and jumps back to the `popad` both refusal paths already shared. That
resume address is *measured* from the assembled helper rather than restated, so
the two cannot drift apart.

The **no-room** path deliberately does not disarm: nothing was armed on it, and
clearing there would mask a future ordering mistake rather than fix one. A test
pins that asymmetry so a later tidy-up cannot quietly collapse the two paths.

All three caves involved now carry generator bounds derived from the
neighbouring offsets rather than restated as literals — the main helper against
`EQUAL_DIVISION_CORE_FILE_OFFSET`, the room check against the disarm stub, and
the disarm stub against the end of the reservation, which is where
`vv1_birth_control`'s composition overlay begins at `0x8EC00`. Before that, each
could have grown into its neighbour with the build still reporting success.
