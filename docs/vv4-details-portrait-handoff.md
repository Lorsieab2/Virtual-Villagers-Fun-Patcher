# VV4 Details portrait mask — current static handoff

Status as of 2026-08-29. Static and player evidence are kept separate.

## Preserved player-approved path

The player-approved village/action/pickup renderer remains unchanged. Its hook
is the call at `0x468263` inside `FUN_00467DA0`; it reissues the world head blit
through `FUN_0044C790`. The world cave bytes and its five-byte vertical-offset
table are pinned by `tests/test_vv4_heathen_mask.py`.

No new map, pickup, or held-villager hook is claimed by the Details repair.

## Confirmed Details path and first divergence

The Villager Detail screen uses this exact stock chain:

`0x447D30` -> `0x460BF0(record, 0)` -> `0x45F550`

- `0x45F653` draws the body from `record+0x1BBC`.
- `0x45F702` draws the head from `record+0x1BB8` through the seven-argument
  `0x409A70` draw thunk.

The preceding Details mask replay diverged from that renderer in two concrete
ways:

1. It treated `record+0x1CD4 & 7` as a facing. `+0x1CD4` is the occupied/active
   byte, so this normally selected one constant/wrong mask frame.
2. It enlarged neither the art nor the scale: it reused the eight-facing
   village atlas at the native head scale, producing the tiny mask shown by the
   player.

The historical `0x45F965` route is not the Details portrait and remains stock.

## Current VV5-style Details repair

The hook remains limited to the confirmed `0x45F702` head draw and first replays
the stock head with its untouched seven-argument tuple. The mask replay then:

- uses the live native X and Y values;
- reads VV4's portrait turn from `record+0x2E38 mod 3`, the structural
  counterpart of VV5's `record+0x2F3C mod 3`;
- maps the three portrait turns through `[0, 1, 2]` into a dedicated 3-column by
  5-row Details atlas;
- uses row `mask-1` for Blue, Orange, Red, Purple, and Chief;
- uses the native head scale multiplied by 1.5;
- retains VV5's per-facing X offsets `[19, 3, -16]`, base Y lift `50`, per-row Y
  offsets `[0, 2, 0, 2, 0]`, and the young-villager correction for Orange,
  Purple, and Chief;
- preserves the draw-manager wrapper in ECX and pushes exactly seven arguments
  for the second draw.

The DLL constructs and publishes a separate ldwImageGrid object for this path.
`assets/vv4_masks/vvfp_bighead_mask_atlas.png` is deterministically generated
from the same recipe as VV5's approved `bigheads_masks.png`; the two files are
byte-identical (162x405 RGBA, SHA-256
`8E10BE75CBED771DA9F63E8C7DF7A1CA91658A9A4069862D9E4EE53D04FDCB47`).
The VV4 companion installs it as
`Images/vvfp_bighead_mask_atlas00.png`, matching the game's multi-file grid
loader naming rule.

## Evidence boundary

The exact hook, cave bounds, ABI, field use, atlas identity, companion path,
unchanged world bytes, and deterministic rebuild are statically tested. This
does not prove the player-visible result. The player must reopen Villager Detail
with masked adults and children, let the portrait turn through all three
facings, and confirm final seating and tracking. Recheck the already-approved
village/action/pickup behavior only as a regression gate.
