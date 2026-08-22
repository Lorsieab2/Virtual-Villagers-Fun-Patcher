# VV3 Heathen-Mask Cosmetic Overlay — Status & Handoff

Branch: `claude/vv3-heathen-mask-patch`. Feature: an optional, per-villager cosmetic
Heathen-mask overlay in VV3's **Change Appearance** window (options: (None), Blue Mask,
Orange Mask, Red Mask, Purple Mask, Tribal Chief Mask). Purely cosmetic; per-villager;
must persist across save/reload; masks are tall (extend above the head).

## TL;DR — where it stands

- **Detail-screen render: solved and proven** (standalone probe on the stock exe).
- **DLL chooser UI: designed and built** (in git history, commit `5983a77`).
- **Per-villager persistence byte: found and verified** (`record + 0xED0`, unused).
- **Map/village-view render: not built** (separate name-based animation system).
- **BLOCKER — full-exe integration:** the VV3 `.text`/`.rdata` code-cave padding is
  **fully allocated** by existing features. The ~108-byte mask render cave has nowhere to
  live without invasive, launch-only-verifiable changes. The branch tip has been **reverted
  to a clean, building state** (58 patches, valid checksum) rather than left broken. The
  integration attempt is preserved in commit `5983a77` for reference.

## What works (proven / built)

### 1. Detail-screen render hook — `scripts/build_vv3_mask_stage1_probe.py`
Standalone patch on the stock exe. Hooks the head-draw call site and, per villager, draws
the head then (if masked) draws the mask on top.
- Hook: `HOOK_VA=0x456B24` (the `mov ecx,[esi+0x1F7C]; call 0x409FB0` head draw inside
  `FUN_004568e0`). 11 bytes replaced with `jmp` to a cave.
- Cave logic: copy the 7 stack args, draw head, read `[esi+0xED0]`, if nonzero draw the
  mask at atlas row `29 + maskbyte`, else skip; return to `0x456B2F`.
- Draw fn `0x409FB0` (7 stack args, `ret 0x1C`); sprite object at `[esi+0x1F7C]`.
- Also bumps the head-atlas row-count fields `0x1E -> 0x23` (adds rows 30..34) and fixes
  the PE checksum.

### 2. Mask atlas art — `scripts/build_vv3_mask_atlas.py`
Appends the 5 masks as **native-size, no-crop, face-centroid-aligned** rows 30..34 into the
four head atlases (`male_heads.png`, `male_heads_old.png`, `female_heads.png`,
`female_heads_old.png`; each 320x1950, 8 dir frames x 30 rows of 40x65). Source art:
`C:/Users/Owner/Downloads/vv5_heathenheads.png` (520x725, 5 masks x 8 frames, 1:1 with the
8 head views). Backs up originals to `*.mask-bak.png`. `MASK_LIFT=0` (user-confirmed "1.0
sizing, no lift change" was the correct look). **This atlas augmentation is a required
deploy step** — the row-count bump reads out-of-bounds if the atlas isn't augmented first.

### 3. Per-villager mask byte — `record + 0xED0`
Runtime-verified all-zero across 85+ live villagers and never referenced in `.text`, so it
is free to repurpose. Values: `0`=None, `1..5`=Blue/Orange/Red/Purple/Chief; atlas row =
`29 + byte`. It rides the save file (persists across save/reload) and is per-villager, so
masked and unmasked villagers coexist in one game.

### 4. DLL chooser UI (commit `5983a77`, currently reverted out of the tree)
`native/vv3_full_mastery_candidate/` — added a Heathen-Mask cycler (`< (None) >`) to the
existing **Change Appearance** dialog (id 213). Names: (None), Blue Mask, Orange Mask, Red
Mask, Purple Mask, Tribal Chief Mask. `ShowVV3AppearanceChooser` was extended to `@20`
(takes the `record` pointer) and writes the chosen index directly to `record + 0xED0` on
OK. See `git show 5983a77` for the exact `.c`/`.rc`/`.def` diffs.

## The blocker — code-cave space is exhausted

The mask render cave (~78–108 bytes; two draws per head require duplicating the 7 draw args
before the first `call`, since `0x409FB0` pops them via `ret 0x1C`) needs an executable
code cave. There is no free one:

- A composed VV3 exe (all 58 features) has **no unreserved executable padding**. Every
  zero-run in the `.text`/extended-`.rdata` padding is inside a feature's cave reservation:
  - `vv3_write_village_statistics` reserves a **512-byte** cave at `0x7B464..0x7B664`
    (uses ~178 B; the rest is zero-padding). The 512 is hardcoded in the patcher core at
    `src/vv_fun_patcher.py:6536` and in `scripts/build_statistics_features.py:58`
    (`cave_size: 0x200`), and VV4/VV5 use the same size.
  - `vv3_origins_...village_wide` reserves `0x7B820..0x7BD40` (1312 B).
  - `vv3_nature_honey_refill` occupies `0x7B340`.
  - Origins barrel caves at `0x7B3B1`, `0x7B3E0`; heal cave `0x7B664`.
- The Origins payload block (`0xA3180`, 3652 B, in the Origins-mapped executable `.rdata`
  tail) has only **60 free bytes** after it (`0xA3FC4..0xA4000`); `.rdata` raw ends at
  `0xA4000`. Too small for the ~78-byte two-draw cave, and growing past `0xA4000` means
  shifting the next section (PE surgery).

**Note for future debugging:** `render_patched_bytes(source, build, mode, ids)` re-loads
fun-patches from the on-disk manifest — filtering an in-memory `fp.raw['patches']` list has
**no effect** on the render. Edit the manifest / build script and regenerate to test.

## Options to finish (all require live playtest verification — hence not shipped blind)

1. **Shrink the statistics over-reservation.** Reduce its cave from `0x200` to `0x100`
   (content is ~178 B, so 256 B is safe) in both `scripts/build_statistics_features.py:58`
   and the `0x200` guards in `src/vv_fun_patcher.py:6536-6537`, regenerate statistics +
   Origins, then place the mask cave at ~`0x7B570` (freed `0x7B564..0x7B664`). Touches
   shared core; re-pin statistics tests. Lowest new-code risk, but a core edit.
2. **Move the double-draw into the DLL.** Add a `DrawHeadAndMask(...)` export that calls the
   exe draw fn `0x409FB0` twice; the exe hook becomes a tiny trampoline (fits the 60-byte
   payload tail) calling the resolved export pointer. Cleanest for space, but adds a
   per-frame exe->DLL call in the render hot path — must be perf/crash tested live.
3. **Grow a section** (extend `.rdata` raw + shift subsequent sections) to add cave space.
   Most invasive PE surgery.

Recommended: **Option 1** (smallest, most contained), verified with a playtest.

## Not built: map / village-view masks
The village map uses a **separate, name-based animation system** (`FUN_004582A0` @0x4582A0
-> `FUN_00455AB0` strncpy's an animation *name* into `animObj+0xE48`, head -> `+0xE3C`;
villager record `+0xDD0` = ptr to the anim object; a per-frame player draws it). It does
**not** use the head-atlas global or `0x409FB0`, so the Detail-screen hook does nothing
there. Map masks are a separate, unstarted effort.
