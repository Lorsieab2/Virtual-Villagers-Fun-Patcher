# VV3 Heathen-Mask Cosmetic Overlay — Status & Handoff

Branch: the VV3 Origins mask candidate plus the local slot-persistence commit. Feature:
an optional, per-villager cosmetic Heathen-mask overlay in VV3's
**Change Appearance** window (options: (None), Blue, Orange, Red, Purple, Tribal
Chief). Purely cosmetic; per-villager; the current candidate has separate Details,
village, and action-pose render paths; player runtime acceptance remains open. The held/
cursor path is intentionally unimplemented pending an exact player trace.

## TL;DR — static candidate status (runtime acceptance open)

The implementation, deployment artifact, and per-save sidecar selector are built
and statically tested. No runtime or player acceptance is claimed here. The
**Chief** atlas row and unowned native preference changes remain separate
art/runtime questions.

| Piece | State |
|---|---|
| Detail render (Blue/Orange/Red/Purple) | ✅ exact hook/cave is built; player render proof pending |
| Village/action-pose render paths | ✅ exact candidate hooks are built; player pose proof pending |
| Held/cursor path | ⛔ no hook; `0x434357`/`0x4344B3` are a timed effect renderer; player trace required |
| Storage | ✅ DLL-owned table, immune to the sim (see below) |
| Chooser (mask cycler in Change Appearance) | ✅ writes the table on OK-after-charge |
| Persistence (survives quit/reload) | ✅ per-save sidecar selector built; player round-trip pending |
| Atlas ships without a manifest step | ✅ embedded in the DLL, self-extracts |
| No interference with other features | ✅ guarded manifest/test composition; player regression pending |
| **Chief** atlas row | ⛔ art staggered — needs re-stacking (below) |
| Village-view masks | ✅ separate candidate path is emitted; player positioning proof pending |

## Architecture

**Storage — DLL-owned table, NOT a record byte.** VV3's record byte `+0xED0` reads
0 in every static and live read, but the **running sim zeroes it every frame** (the
same trap as VV2's `+0x480`) — a written mask vanishes within a frame. *Lesson: a
free-byte proof MUST write a value and confirm it PERSISTS with the sim running,
not just read 0.* So the mask lives in the companion DLL: `g_vv3_mask[256]` +
`g_vv3_mask_fp[256]`, keyed by slot index `(record-0x59E124)/0x1F8C`. Exports
`VV3_Get/SetMaskForRecord`. The villager record and the save file are **never**
written. Every loaded sidecar mask value is sanitized to the supported `0..5`
range before it enters the table, so malformed or hand-edited bytes fail closed.
Slot-reuse is guarded by an FNV fingerprint over gender (`+0xDC8`) + 3 Likes
(`+0xFB4`) + 3 Dislikes (`+0xFC0`). Before either the same-slot fast path or the
slot-shift fallback may return a mask, the getter requires exactly one active,
living record and exactly one nonzero stored entry with that fingerprint. Two
simultaneous live matches or two stored matches therefore fail closed to no mask;
unique-fingerprint reload/slot-shift recovery remains available. A nonzero setter
commit also requires that unique live owner; it clears any older shifted stored copy
before rebinding the current slot, while an explicit None may still clear an exact
stale slot. The individual chooser aborts before its staged writes and native charge
if that nonzero bind is ambiguous. The whole-village transaction preflights every
requested mask that can be nonzero before any head/body or mask mutation; an
ambiguous target aborts the whole batch with no 450,000-point deduction. Random is
checked conservatively because it can select a nonzero mask. This fingerprint
is still not a stable identity: if one villager disappears and a replacement/newborn
with the exact same fingerprint occupies the population later, there is no overlap
from which uniqueness can distinguish them. No proven stable name, identity, or
allocation-generation field has been established in the current exact-build
evidence, so that sequential replacement boundary needs a player trace or new
native evidence, not an invented record offset. The owned Grant Running detail and
village-wide writers bracket their exact preference stores through
`VV3RunningMaskBoundary`; it snapshots both live and stored preimages and retags
only a fingerprint with one owner in each snapshot after the `-1`/`38` transforms.
This keeps unique slot-reuse and slot-shift recovery without cross-tagging an
ambiguous preimage or assuming Likes/Dislikes are immutable. The active
save number is captured from the stock save-builder argument at `0x403290` into
`.vv3md+0x44`; slots outside 1..5 fail closed.

**Render — DLL-side draw, separated exe caves.** The Detail head-draw call site
`0x456B24` calls `VV3DrawMaskOnHead(record, [record+0x1F7C], &args)`. The DLL
reads the table, gets the atlas (`VV3GetMaskAtlas` → game allocator `0x46EC93`
+ loader `0x40AF10`), and draws the mask cell on top via the game's own draw fn
`0x4093A0` — row = mask-1, y lifted by `(scaledY * VV3_MASK_LIFT_MUL) >> 7` with
`VV3_MASK_LIFT_MUL = 34`. Village and action-pose paths use the appended `.vv3mc`
R-X caves and `.vv3md` R/W function-pointer slots. The world handler is `sub_4605F0`
(`0x42E3F5` sole direct caller), and its stock head call is `0x460A60`; the action
overlay is wrapped at `0x460B48`. These paths still require player verification for every
pose, facing, age/scale, and Details transition. No held/cursor draw is claimed.

**Chooser.** `ShowVV3AppearanceChooser` (dialog 213, still `@20`) takes the record
pointer and reads/commits via the table. The Change Appearance cave passes the
record and no longer touches `+0xED0`. Head (`+0xDF0`) / body (`+0xDF4`) writes are
unchanged (legitimate paid changes). A head/body-only edit does not call the mask
setter: if identity ambiguity made the getter fail closed to None, that unchanged
zero therefore cannot clear an existing stored mask. A changed mask still binds
before the staged head/body writes and before the native charge.

**Persistence.** Each positive active slot uses its own sidecar
`<Documents>\LDW\<exe-basename>\vvfp_masks_<slot>.dat`
(`SHGetSpecialFolderPathA(CSIDL_PERSONAL)` — follows OneDrive redirection).
`VV3_SetMaskForRecord` writes through to the selected file; a slot change clears
the table and loads only the new file. Magic `MSK3` + the two arrays. A missing or
short file clears the table, and there is no legacy unsuffixed-file migration.
All file I/O is in normal functions (never `DllMain`). Static round-trip structure
is tested; live save-switch and relaunch behavior remain player gates.

**Atlas self-deploy.** `Images/heathen_masks.png` is embedded in the DLL as RCDATA
5000; `VV3GetMaskAtlas` extracts it to `<game>\Images\` if missing (respects an
existing file). Ships with only the DLL — `companion_files` stays `[the DLL]`, no
shared cross-game patcher core touched. Atlas: 8 cols × 5 rows, cell 40×128, built
by `scripts/build_vv3_mask_atlas_separate.py` from the user's port canvases.

**No interference (static status).** The composed-build manifest removes the 4
head-atlas row-count patches (`0xAAE6C/9C/F2C/F5C`) from the abandoned append-rows
artifact, adds the separated `.vv3mc`/`.vv3md` mask sections, and adds only the
exact save-builder slot-capture patch at `0x403290` for sidecar selection.
Other audited feature hooks remain guarded by the manifest and the VV3 suite is
green; player regression testing is still required.

## Remaining

1. **Chief atlas row (blocked on art).** `mask_chief.png`'s 8 frames are staggered
   in a 2-row layout with horizontal overlap (the chief head sprite sits
   differently per facing), so the uniform `(CANVAS_DX,CANVAS_DY)` composite that
   builds the other four masks misaligns it, and the frames can't be reliably
   auto-separated. Needs the chief re-stacked to a single origin like the other
   masks (all 8 frames aligned to the head), then add `"chief"` to `STRAIGHT` in
   the atlas builder. VV4 tip: subtract the known head from a head+mask mockup for
   pixel-exact isolation.
2. **Sequential same-fingerprint replacement / unowned preference changes remain
   outside this fix.** Simultaneous duplicate live or stored fingerprints now fail
   closed, including the same-slot fast path, and Grant Running retags only unique
   live/stored preimages. Nonzero setter commits likewise require one live owner and
   cannot be seeded through an inactive/stale record. Whole-village mask batches
   preflight that condition before any mutation or charge. A deceased/removed
   villager followed later by a newborn or replacement with the exact same
   gender+Likes+Dislikes fingerprint cannot be
   distinguished without a proven stable identity or allocation-generation field.
   The exact detail and village-wide Grant Running writers owned by this composition
   are bracketed by `VV3RunningMaskBoundary`; other native preference mutations are
   not wrapped and remain outside the current mask identity guarantee. No unproved
   name or record ID field is substituted.
3. **Sidecar co-location (minor).** On OneDrive-redirected systems the sidecar
   lands in `OneDrive\Documents\LDW` while the game's `.ldw` saves are in plain
   `Documents\LDW`. Persistence is self-consistent so it works; matching the game's
    exact save path would co-locate them.
4. **Held/cursor render (blocked on evidence).** Static disassembly proves that
   `0x434357` (`call 0x42E570`) and `0x4344B3` (`call 0x42E510`) are two draws in the
   same three-style timed sprite/effect object. They have no villager record identity and
   must remain stock. The true successful-grab boundary, held record lifetime, release
   clear, and visible held draw caller/arguments remain unknown. Do not add a hook until a
   player trace captures those values.

## Village / action-pose candidate path

VV3's village compositor does **not** route through the Detail head-draw thunk — it
uses a separate texture-index animation system (`0x42E440`, per-villager texture
table `[edi+0x127C44]`, layer dispatcher `0x45F7E0` reading `record+0xF20`, animObj
`record+0xDD0`). The current candidate wraps the proven village handler/head and
action-overlay call sites in the appended `.vv3mc` section and resolves its DLL
functions through `.vv3md`. The handler record identity and head arguments are proven for
the normal world path. The mask is intentionally not hooked into `0x434357`/`0x4344B3`:
those are timed UI/effect calls, not held-villager draws. Static coverage is not player
proof: runtime must still verify every action pose, facing, age/scale, and Details
transition, and must trace pickup before any held implementation is attempted.
