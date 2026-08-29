# VV3 pickup truth — static result and player trace handoff

Scope: exact stock `Virtual Villagers - The Secret City.exe`, SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
No game launch or runtime acceptance is claimed in this audit.

## Confirmed

- `sub_4605F0` is the normal per-villager render handler. It receives a villager index,
  derives the record with the `0x1F8C` stride from the `0x59E124` record base/context, and
  reads the record's render fields.
- `0x42E3F5` is the sole direct caller of `sub_4605F0` in the stock executable.
- `sub_4605F0` resolves the head atlas and calls the whole-head draw `0x42E570` at
  `0x460A60`. The call has the handler's live record context and stock head x/y/scale
  arguments. The current world mask path stashes those arguments and the wrapper preserves
  the post-handler draw ordering.
- The action/full-body overlay is `sub_45F7E0`, reached from the normal handler at
  `0x460B48`. The current action mask hook remains there.
- The only other direct `0x42E570` call is `0x434357`, but that site belongs to the separate
  `0x4341A0..0x434758` three-style timed sprite/particle effect object. Its selector is
  `0..2`, its entries are 24 bytes, its elapsed-time limits include `0x12C` and `0x7080`,
  and its fixed anchors are `(110,160)`, `(114,212)`, `(75,176)` at `0x5947B8..0x5947CC`.
- `0x4344B3` is a second generic cell blit in that same effect object. Neither effect call
  carries a villager record or proven cursor-held identity.
- `0x5947D0` is a four-bit initialization latch. It is written by test/skip/OR initialization
  idioms and is not a selection, pickup, or villager-state flag.
- SDL mouse/input evidence reaches generic event/UI code: `SDL_GetMouseState` is imported at
  `0x47C24C` (thunk `0x46E6F4`); generic mouse dispatch is in the `0x404220` family. The
  `SetCapture`/`ReleaseCapture` calls at `0x438B91`/`0x438BA1` operate on a UI object and do
  not statically expose a villager record.

## Likely, but not proven

The simplest hypothesis remains possible: a grabbed villager may stay in the normal
`sub_4605F0` path and receive cursor-relative coordinates in the same head call at
`0x460A60`. The direct caller and head call are the only statically proven villager render
family. The branch on `record+0xF1C == 6` and the use of `record+0xF12` show render-state
conditions, but their pickup meanings are not proven. `+0xF12` is also used by stock carried-
baby scaling/offset logic, so it cannot be promoted to a player-drag flag from this evidence.

## Unknown

Static analysis does not identify:

- the first callback that returns a successful player grab;
- the live villager record/index at grab time;
- whether the normal handler runs for the grabbed villager on every held frame;
- whether `0x460A60` x/y/scale are ground-relative or cursor-relative while held;
- any separate held/cursor renderer and its active flag/lifetime;
- the release callback and the first frame where the held identity clears.

Consequently no hook is installed at `0x434357` or `0x4344B3`, and no grab-time record capture
or clear-on-release is implemented.

## Minimal player trace

Trace one successful mouse-down, several held frames, and release. At each event, record:

1. the earliest successful-grab callback, record pointer/index, and any drag-object pointer;
2. cursor x/y and record fields `+0xF1C`, `+0xF12`, `+0xF14`, `+0xF18`, `+0xF20`;
3. every entry to `0x42E510`/`0x42E570`, including return address, atlas/sprite pointer,
   cell/frame, x/y, facing, and scale;
4. the release callback and the first frame in which record identity and held coordinates
   clear.

The trace must distinguish the normal handler/head call from the timed effect calls. If the
trace proves the normal handler's head args follow the cursor, the safest implementation is
to keep the mask inside that replayed head call and capture only the proven record identity.
If it proves a separate held renderer, hook that renderer only after its exact preimage and
ABI are recorded. In either case, code goes in `.vv3mc` R-X and state in `.vv3md` R/W; the
player makes the final visual interpretation.
