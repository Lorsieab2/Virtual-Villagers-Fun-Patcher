# VV3 Heathen-Mask Cosmetic Overlay — Status & Handoff

Branch: `claude/vv3-heathen-mask-patch`. Feature: an optional, per-villager cosmetic
Heathen-mask overlay in VV3's **Change Appearance** window (options: (None), Blue,
Orange, Red, Purple, Tribal Chief). Purely cosmetic; per-villager; renders on the
**Details/portrait** screen; persists across save/reload.

## TL;DR — DONE and playtest-verified end-to-end (2026-08-23)

Render, storage, persistence, atlas self-deploy, and no-interference are all
built and live-tested. Only the **Chief** atlas row and an optional reuse-guard
upgrade remain.

| Piece | State |
|---|---|
| Detail render (Blue/Orange/Red/Purple) | ✅ renders on every villager, seated on the head |
| Storage | ✅ DLL-owned table, immune to the sim (see below) |
| Chooser (mask cycler in Change Appearance) | ✅ writes the table on OK-after-charge |
| Persistence (survives quit/reload) | ✅ sidecar, live round-trip proven |
| Atlas ships without a manifest step | ✅ embedded in the DLL, self-extracts |
| No interference with other features | ✅ manifest diff + full suite green |
| **Chief** atlas row | ⛔ art staggered — needs re-stacking (below) |
| Village-view masks | ⛔ separate pipeline (below) — Details-only by design |

## Architecture

**Storage — DLL-owned table, NOT a record byte.** VV3's record byte `+0xED0` reads
0 in every static and live read, but the **running sim zeroes it every frame** (the
same trap as VV2's `+0x480`) — a written mask vanishes within a frame. *Lesson: a
free-byte proof MUST write a value and confirm it PERSISTS with the sim running,
not just read 0.* So the mask lives in the companion DLL: `g_vv3_mask[256]` +
`g_vv3_mask_fp[256]`, keyed by slot index `(record-0x59E124)/0x1F8C`. Exports
`VV3_Get/SetMaskForRecord`. The villager record and the save file are **never**
written. Slot-reuse is guarded by an FNV fingerprint over gender (`+0xDC8`) + 3
Likes (`+0xFB4`) + 3 Dislikes (`+0xFC0`) so a newborn reusing a dead villager's
slot can't inherit the mask.

**Render — DLL-side draw, tiny exe cave.** The exe hooks the Detail head-draw call
site `0x456B24` (covers *every* villager once storage is stable). The cave draws
the head, then calls `VV3DrawMaskOnHead(record, [record+0x1F7C], &args)` once. The
DLL reads the table, gets the atlas (`VV3GetMaskAtlas` → game allocator `0x46EC93`
+ loader `0x40AF10`), and draws the mask cell on top via the game's own draw fn
`0x4093A0` — row = mask-1, y lifted by `(scaledY * VV3_MASK_LIFT_MUL) >> 7` with
`VV3_MASK_LIFT_MUL = 34` (live-tuned: 54 too high, 16 too low). Keeping the draw in
the DLL keeps the exe cave ~110 B (fits the Origins payload gap `PAYLOAD_VA+0xAD8`)
— **no appended PE section needed**. Cached DLL fn ptr in `.data 0x6C7A00`.

**Chooser.** `ShowVV3AppearanceChooser` (dialog 213, still `@20`) takes the record
pointer and reads/commits via the table. The Change Appearance cave passes the
record and no longer touches `+0xED0`. Head (`+0xDF0`) / body (`+0xDF4`) writes are
unchanged (legitimate paid changes).

**Persistence.** Sidecar `<Documents>\LDW\<exe-basename>\vvfp_masks.dat`
(`SHGetSpecialFolderPathA(CSIDL_PERSONAL)` — follows OneDrive redirection).
Write-through in `VV3_SetMaskForRecord`, read-once on the first table access.
Magic `MSK3` + the two arrays. All file I/O in normal functions (never `DllMain`).
Live-tested: set Red on a villager → sidecar written → relaunch → mask restored.

**Atlas self-deploy.** `Images/heathen_masks.png` is embedded in the DLL as RCDATA
5000; `VV3GetMaskAtlas` extracts it to `<game>\Images\` if missing (respects an
existing file). Ships with only the DLL — `companion_files` stays `[the DLL]`, no
shared cross-game patcher core touched. Atlas: 8 cols × 5 rows, cell 40×128, built
by `scripts/build_vv3_mask_atlas_separate.py` from the user's port canvases.

**No interference (verified).** The composed-build manifest differs from the pinned
baseline by exactly one thing: the **removal** of the 4 head-atlas row-count
patches (`0xAAE6C/9C/F2C/F5C`) — the abandoned append-rows artifact. Nothing added;
every other feature hook (doublers, EDL, barrel, collections, village-wide,
appearance) is byte-identical. The mod no longer modifies the shared head atlases
at all. Golden pins updated; VV3 suite green.

## Remaining

1. **Chief atlas row (blocked on art).** `mask_chief.png`'s 8 frames are staggered
   in a 2-row layout with horizontal overlap (the chief head sprite sits
   differently per facing), so the uniform `(CANVAS_DX,CANVAS_DY)` composite that
   builds the other four masks misaligns it, and the frames can't be reliably
   auto-separated. Needs the chief re-stacked to a single origin like the other
   masks (all 8 frames aligned to the head), then add `"chief"` to `STRAIGHT` in
   the atlas builder. VV4 tip: subtract the known head from a head+mask mockup for
   pixel-exact isolation.
2. **Reuse-guard upgrade (optional).** The chats converged on clear-on-birth /
   VV4's free-slot sweep (clear `table[idx]` when the active flag `record+0xF10`
   says the slot is dead) as cleaner than the fingerprint. VV3 has no per-frame DLL
   entry during the village sim, so it needs a new village-loop hook (`0x45F670`
   iterates 150 records) — deferred; the fingerprint works.
3. **Sidecar co-location (minor).** On OneDrive-redirected systems the sidecar
   lands in `OneDrive\Documents\LDW` while the game's `.ldw` saves are in plain
   `Documents\LDW`. Persistence is self-consistent so it works; matching the game's
   exact save path would co-locate them.

## Not built: map / village-view masks

VV3's village compositor does **not** route through the Detail head-draw thunk — it
uses a separate texture-index animation system (`0x42E440`, per-villager texture
table `[edi+0x127C44]`, layer dispatcher `0x45F7E0` reading `record+0xF20`, animObj
`record+0xDD0`). So masks are Details-only for now; a village overlay is a separate,
larger effort (per-frame render code in a 150-iteration hot loop — do it with live
iteration, not blind).
