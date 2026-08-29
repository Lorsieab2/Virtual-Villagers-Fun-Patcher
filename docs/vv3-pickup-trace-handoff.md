# VV3 pickup, fishing, and water — static result and player handoff

Scope: exact stock `Virtual Villagers - The Secret City.exe`, SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
The ownership route is statically/source proven; no game launch or visual
acceptance is claimed in this audit.

## Confirmed stock paths

- `sub_4605F0` is the normal per-villager render handler. It receives a villager
  index, derives the record with the `0x1F8C` stride from the `0x59E124` base,
  and reads the record's render fields.
- `0x42E3F5` is the sole direct caller of `sub_4605F0` in the stock executable.
- `sub_4605F0` resolves the head atlas and calls the whole-head draw `0x42E570`
  at `0x460A60`. The candidate stashes that exact stock head tuple and replays
  it once at the final world-mask wrapper.
- The action/full-body overlay is `sub_45F7E0`, reached at both `0x460B48` and
  `0x460D10`. Both calls use the same `__thiscall(record,x,y) / ret 0x0C`
  ABI and are routed through one `.vv3mc` wrapper. Its post-stock export is
  stash-only; the final world wrapper owns the one mask blit.
- Stock drag sets `record+0xF12 = 1` while held. The matching head tuple is the
  held owner, and release is handled by the next final wrapper after that field
  clears. A fresh head tuple resets an action stash for the same record.
- The ordinary `record+0xF20` value is `-1`; an `+0xE8C` nonzero route can set
  it to exactly `3`. The direct setter found in the exact build is task 163,
  Carrying vial to ocean. Generic task-1 swimming on terrain 5 remains
  head-owned. Fishing task 11 frames `8` and `9` are action-owned.
- Action anchors are supported only for `record+0xF20` values `0..50`.
  Unsupported values, including `51` and `>=52`, fail closed without a head
  fallback. Held head ownership takes precedence over any action stash.

## Deliberately untouched effect sites

The only other direct `0x42E570` call is `0x434357`, and `0x4344B3` is a second
generic cell blit in the same `0x4341A0..0x434758` three-style timed
sprite/particle object. Its selector is `0..2`, entries are 24 bytes, elapsed
limits include `0x12C` and `0x7080`, and fixed anchors are `(110,160)`,
`(114,212)`, `(75,176)` at `0x5947B8..0x5947CC`. Neither call carries a
villager record or proven cursor-held identity, so both remain byte-identical
to stock. `0x5947D0` is a four-bit initialization latch, not pickup state.

## Player acceptance handoff

Static/source evidence establishes ownership and fail-closed transitions, but
the player still decides whether the placement is visually acceptable. Trace
one successful mouse-down, several held frames, fishing frames 8/9, a terrain-5
swim, and release. Record:

1. the earliest successful-grab callback, record pointer/index, and any
   drag-object pointer;
2. cursor x/y and record fields `+0xF1C`, `+0xF12`, `+0xF14`, `+0xF18`, and
   `+0xF20` at grab, held, action, swim, fish, and release;
3. every `0x42E510`/`0x42E570` entry, including return address, atlas/cell,
   x/y, facing, scale, and whether the draw came from head or action stash;
4. the first release frame where `+0xF12` clears and no stale stash paints.

This trace must distinguish the normal villager head/action calls from the
timed effect calls. Player visual acceptance remains pending for facing,
age/scale, Details, swimming, fishing, held motion, and release.
