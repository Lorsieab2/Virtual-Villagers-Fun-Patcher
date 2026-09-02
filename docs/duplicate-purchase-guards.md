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

**VV3 refuses at the click instead**, showing "An Island Event is already on
its way." (DLL result code 10) or "A Barrel of Babies is already on its way."
(code 11), charging nothing. Its Island Event already worked this way. The
Barrel joins it rather than getting the nicer disabled-row treatment because
VV3 has no code cave to compute the state in: every window in its `.text`
padding is claimed (see below), and the guard fits inline only because the
Barrel flag is a plain global needing no manager lookup.

Both refusals sit **after `jb insufficient`** and **before the deduction**.
After the branch because their compares overwrite the flags it reads — the
same mistake the paused Time Warp guard made, caught as a P1 on three games.
Before the deduction because refusing afterwards still costs the player the
points, which is the reported bug.

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
VV3's guard pushed `tech_menu` 13 bytes past its slot, so `detail_menu` and
`tech_increment` each moved `0x10` later; both had room, and nothing outside
the generator pins those offsets.
