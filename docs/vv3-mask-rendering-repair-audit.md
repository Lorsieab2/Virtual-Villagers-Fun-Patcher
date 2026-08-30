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
  caller and remains stock. The old `0x460A60 -> 0x42E570` candidate hook is
  wrong: that generic draw uses a fixed context resource, omits the record's
  `+0xDF0/+0xF18` appearance tuple, and halves scale when `+0xF12` is held.
  The authoritative head draw is `0x460C7F -> 0x42E5E0`; stock loads the
  head atlas/facing and supplies six arguments `(atlas, x, y, head-row,
  facing, scale)`.
- The stock action overlay is `sub_45F7E0`, reached at `0x460B48`. It reads
  `record+0xF20`, returns for `-1`, and selects its first or second action
  atlas at the `0x34` split before calling `0x42E510`. The same stock call is
  also reached at `0x460D10`; F14 routes `{0,3,4}` to `0x460B48` and
  `{1,2,5,6,7}` to `0x460D10`. The mask candidate does not hook either action
  call site. Stock action rendering remains the owner for sit/lie/swim/fish/work
  poses; exact mask seating there remains unproved and receives no reconstruction.

## Implemented, bounded repairs

1. Details now uses `18` in `y - ((scaledY * multiplier) >> 7)`. For the stock
   Details `scaledY=200`, this candidate is 25px lower than multiplier `34`
   (`200*18>>7 == 28`; `200*34>>7 == 53`). No atlas identity is assigned to
   the prior `34` candidate. Visual placement remains pending player acceptance.
2. The world cave at `0x460C7F` replays the exact six stock arguments through
   `0x42E5E0`, then calls `VV3WorldMaskDrawAt` synchronously while those original
   arguments are untouched. The callback changes only the atlas and head-row,
   preserving stock x/y/facing/scale and manager state. No synthetic offsets,
   manager reconstruction, or deferred stash is used.
3. The stock carried branch (`+0xF12 != 0`) rejoins the same body/head sequence
   and reaches `0x460C7F`; the candidate therefore reuses its exact six-argument
   tuple while held as well. This removes the old half-scale ground ghost without
   inventing offsets. Cursor coordinate ownership and final visual follow remain
   player-trace gates. The action overlay remains stock and can naturally cover
   the inline head layer.
4. The old action wrappers, deferred world draw, `0x460A60` hook, and all
   synthetic action/head positioning are removed. No new hook address or record
   field was inferred from a screenshot.

## Pickup, fishing, and water boundary

The stock drag trace establishes `record+0xF12 = 1` while a villager is held; the
held branch still reaches the authoritative inline head tuple, so the mask follows
that exact stock draw arguments. The
normal `+0xF20` value is `-1`; an `+0xE8C` nonzero route can set it to exactly
`3`. The direct setter is the task-163 Carrying-vial-to-ocean path; `42` is
only a stock renderer water exception, not a claim that generic task-1 swimming
assigns that action. Generic task-1 swimming on terrain 5 and task-11 fishing
frames `8`/`9` remain stock action/head ownership paths with no guessed mask
seating.

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
| Inline mask reuses the six-argument `0x460C7F -> 0x42E5E0` head tuple | Confirmed ABI/path; visual acceptance pending player |
| Action call sites remain stock; no unproved pose mask is painted | Confirmed static/source; visual acceptance pending player |
| Generic task-1 swimming on terrain 5 uses the head tuple | Confirmed trace/source; visual acceptance pending player |
| Task-11 fishing frames `8/9` use the action tuple | Confirmed trace/source; visual acceptance pending player |
| Pickup/held `+0xF12` reaches the authoritative head tuple | Confirmed trace/source; cursor ownership and visual acceptance pending player |
