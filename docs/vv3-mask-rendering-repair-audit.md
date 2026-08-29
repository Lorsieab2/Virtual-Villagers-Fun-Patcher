# VV3 mask rendering repair audit

Scope: the exact stock `Virtual Villagers - The Secret City.exe` build,
SHA-256 `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`
(831,488 bytes). This is a static/native audit. It does not claim player
acceptance, save behavior, or a successful pickup/fishing trace.

## Confirmed stock render paths

- Details head rendering converges at `0x456B24`. The stock call pushes
  `x=0x78`, `y=0xD4`, `scaledY=0xC8`, the head frame, and flag `1` to the
  seven-argument head draw `0x409FB0`. The VV3 Details mask cave is therefore
  bound to a real head tuple, not a guessed portrait position.
- The normal village handler is `sub_4605F0`; `0x42E3F5` is its sole direct
  caller. Its stock head draw is the call at `0x460A60` to `0x42E570`.
  The candidate stashes that call's exact x/y/scale and requires a matching
  record before drawing the mask. A missing head call produces no mask.
- The stock action overlay is `sub_45F7E0`, reached at `0x460B48`. It reads
  `record+0xF20`, returns for `-1`, and selects its first or second action
  atlas at the `0x34` split before calling `0x42E510`. The same stock call is
  also reached at `0x460D10`; F14 routes `{0,3,4}` to `0x460B48` and
  `{1,2,5,6,7}` to `0x460D10`. The current mask registration has measured
  head anchors only for action values `0..50`.

## Implemented, bounded repairs

1. Details now uses `18` in `y - ((scaledY * multiplier) >> 7)`. For the stock
   Details `scaledY=200`, this candidate is 25px lower than multiplier `34`
   (`200*18>>7 == 28`; `200*34>>7 == 53`). No atlas identity is assigned to
   the prior `34` candidate. Visual placement remains pending player acceptance.
2. The world path uses the captured stock head X unchanged and restores the
   measured per-colour Y seats `{41,40,37,35,32}` scale-relative to the stock
   head. The negative `g_vv3_facing_dx` values are neutralized and never added
   at runtime, so no synthetic facing-X correction can reintroduce the known
   horizontal shift.
3. `VV3WorldMaskDrawAt` captures the head-time `[mgr+0x3010]` term. The final
   head-owned draw rounds that term by the captured head scale, calls `0x42E510`
   with `1.0`, and restores the manager immediately. The captured scale is not
   passed directly as the `0x42E510` draw argument.
4. The action export is stash-only after the stock action draw. The final
   wrapper draws exactly once: held `+0xF12 != 0` selects the matching head
   stash and suppresses action; otherwise a matching action stash selects only
   supported frames `0..50`; unsupported frames (including `51` and `>=52`)
   fail closed without a head fallback; otherwise the matching head stash owns
   the world draw. Both stashes are cleared on every exit.

The existing action gate and stash requirement remain fail-closed. No new
hook address or record field was inferred from a screenshot.

## Pickup, fishing, and water boundary

The stock drag trace establishes `record+0xF12 = 1` while a villager is held;
the matching stock head tuple is therefore the held owner. The normal `+0xF20`
value is `-1`; an `+0xE8C` nonzero route can set it to exactly `3`. The direct
setter is the task-163 Carrying-vial-to-ocean path; `42` is only a stock
renderer water exception, not a claim that generic task-1 swimming assigns
that action. Generic task-1 swimming on terrain 5 remains head-owned. Fishing
task 11 frames `8` and `9` are the proven action-owned cases and use the
post-stock action tuple. The action wrapper now covers both stock call sites
(`0x460B48` and `0x460D10`) with the same `.vv3mc` ABI wrapper.

The other `0x42E570` call at `0x434357` and the `0x42E510` call at `0x4344B3`
remain byte-identical to stock: they are inside `0x4341A0..0x434758`, a
three-entry timed UI/effect object whose arguments are effect sprites and fixed
anchors, not a villager record. The `0x5947D0` references are initialization
latch bits, not pickup state.

### Required player acceptance trace

For one successful mouse-down, several held frames, and release, capture the
earliest successful-grab callback, record/index and drag-object pointer;
cursor coordinates and record fields `+0xF1C`, `+0xF12`, `+0xF14`, `+0xF18`,
`+0xF20`; every `0x42E510`/`0x42E570` entry with return address, atlas/cell,
x/y/facing/scale; and the first release frame where the identity clears.
This must distinguish the normal villager head call from the timed effect
calls. The ownership implementation is statically/trace proven; the player
still makes the final interpretation of on-screen placement.

## Status classification

| Finding | Classification |
|---|---|
| Details hook reaches a stock head tuple | Confirmed static |
| Previous world X/Y offsets caused the reported registration divergence | Confirmed by source arithmetic and player symptom |
| Captured head-time manager sizing with a `1.0` draw is the bounded delayed-draw repair | Confirmed ABI/path; visual acceptance pending player |
| Action hook covers measured frames `0..50` at both stock call sites | Confirmed static/source; visual acceptance pending player |
| Generic task-1 swimming on terrain 5 uses the head tuple | Confirmed trace/source; visual acceptance pending player |
| Task-11 fishing frames `8/9` use the action tuple | Confirmed trace/source; visual acceptance pending player |
| Pickup/held `+0xF12` ownership and release clearing | Confirmed trace/source; visual acceptance pending player |
