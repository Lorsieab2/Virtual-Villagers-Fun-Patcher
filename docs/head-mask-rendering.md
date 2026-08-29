# Head positioning and Heathen-mask rendering

This is the cross-game rendering contract for the VV mask patches. VV2 and VV5 are the
behavioral references. Static/source checks do not constitute player acceptance; every
game still requires a runtime trace and a player confirmation.

## Part 1 — The head is the positioning authority

The mask must be emitted from the same draw family as the visible head, reusing the head
draw's x/y, facing/frame selection, and scale. Do not reconstruct a head position from a
villager's world coordinates when the engine already supplied the final head arguments.
That reconstruction drops pose, facing, camera, and pickup offsets and produces a detached
mask.

The low-level VV draw functions consume pre-camera world coordinates and apply the camera
and scroll internally. A mask that is reissued through the same draw manager must therefore
pass the same coordinate space and scale convention as the stock head.

## Part 2 — Mask rules

1. Replay the stock head call and change only the mask atlas and cell/frame.
2. Enumerate every head or full-body pose caller. A walking-only hook is not coverage for
   bend, sit, fish, swim, work, or other action frames.
3. Select the mask column from the proven facing source; never reuse an age-offset head
   frame as though it were a mask column.
4. Select the color row from the mask side table; it is independent of head frame.
5. Scale the mask using the same head scale. The art's face anchor and vertical lift are
   measured values and must be validated by rendering the actual cells over the actual head.
6. Selection is not pickup. Do not gate a render path on a selection bit.
7. A pickup overlay is not proven until a live trace identifies the successful grab, the
   held record, the held renderer, and release lifetime. Do not guess from an unrelated
   global or effect object.

## Part 3 — Game-specific evidence

### VV1 — A New Home

VV1's mask path follows its proven head callers. Runtime acceptance must still verify every
pose, facing, scale, Details transition, and pickup behavior against the reference builds.

### VV2 — The Lost Children

VV2 is the reference from-scratch implementation: the mask is emitted inside the head draw,
and the call-site audit must cover the walking and action/pose caller band. Its behavior is
the standard for inherited position, facing, scale, and pickup handling.

### VV3 — The Secret City

Confirmed in the exact stock executable (`Virtual Villagers - The Secret City.exe`, SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`):

- The normal villager handler is `sub_4605F0`. `0x42E3F5` is its sole direct caller.
- The handler derives a villager record from its index using stride `0x1F8C` and issues the
  stock head draw at `0x460A60` through `0x42E570`.
- The action overlay is `sub_45F7E0`, reached at the proven action call site `0x460B48`.
- The mask patch's world/action/Details hooks use these proven families and owned `.vv3mc`
  (R-X) / `.vv3md` (R/W) sections.
- `0x4341A0..0x434758` is one three-style timed sprite/particle effect object. It iterates
  24-byte entries, compares elapsed time to `0x12C`/`0x7080`, and uses three fixed anchors
  `(110,160)`, `(114,212)`, `(75,176)` from `0x5947B8..0x5947CC`.
- `0x434357` calls the generic scaled-sprite draw `0x42E570` with a sprite selected from a
  three-entry effect table. `0x4344B3` calls the generic cell blit `0x42E510` in the same
  effect object. Neither call has a villager record or held identity.
- `0x5947D0` is a four-bit initialization latch, not selection, pickup, or villager state.
  It is written by test/skip/OR initialization idioms and must never gate mask rendering.

Therefore `0x434357` and `0x4344B3` remain byte-identical to stock. No VV3 held/cursor hook
is installed. Static analysis does not prove whether a grabbed villager remains in the
normal handler or which callback owns the visible held copy.

### VV4 — The Tree of Life

VV4's proven central villager renderer and head draw are the positioning authority. A Details
panel may reuse the village renderer with a different draw manager; a runtime caller/draw-
manager trace is required before treating it as a separate portrait path.

### VV5 — New Believers

VV5 supplies the native mask behavior and remains the latest reference for facing, pose,
scale, Details, and pickup semantics. Its native state does not transfer backward to VV1–VV4.

## Part 4 — Field-finding and trace rules

For an unknown game, enumerate all direct and indirect callers of the actual head draw and
record the arguments at the low-level blit. A filename, table, or generic sprite call is not
enough to establish identity. For pickup, trace mouse-down through the first successful grab
callback, then through held frames and release. Capture record pointer/index, drag object,
cursor x/y, atlas/sprite, cell/frame, facing, scale, and active/release fields.

If a candidate global is only tested and ORed during one-time initialization and is never
cleared, classify it as a latch—not a state flag. If a function receives only generic sprite
arguments and no record or stable owner, classify its identity as unknown.

## Part 5 — Verification gates

Before calling a patch complete:

1. Verify the patcher apply succeeded and the final executable/DLL/atlas hashes match the
   intended source artifacts.
2. Confirm the final build was regenerated after the last source change and that its section
   table contains the patch-owned code/data sections.
3. Enumerate every relevant head/action caller and verify no pose is outside the hook gate.
4. Trace first-frame load, per-slot persistence, Details, all poses, facing, scale, selection,
   pickup, and release in the running game.
5. Require the player to make the final interpretation of visual correctness.

## Part 6 — Acceptance standard

The reference behavior requires: mask on the visible head, inherited x/y/facing/scale,
complete action coverage, no selection displacement, pickup following the held head, correct
Details scale/facing, immediate per-slot restore, and no regression in unrelated features.
No static claim can substitute for the player's runtime result.

## Part 7 — Owned patch storage

New code belongs in a patch-owned executable section and new mutable state belongs in a
patch-owned writable section. VV3 uses `.vv3mc` R-X for trampolines and `.vv3md` R/W for
function pointers, diagnostics, and sidecar state. Do not place new hooks in borrowed slack.

For VV3 specifically, the held path is intentionally absent until the player trace proves
the real boundary. The two timed-effect calls `0x434357` and `0x4344B3` are not safe hook
points and must remain stock.
