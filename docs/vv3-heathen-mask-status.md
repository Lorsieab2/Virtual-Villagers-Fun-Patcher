# VV3 Heathen-Mask Cosmetic Overlay — Status & Handoff

Branch: `claude/vv3-heathen-mask-patch`. Feature: an optional, per-villager cosmetic
Heathen-mask overlay in VV3's **Change Appearance** window (options: (None), Blue Mask,
Orange Mask, Red Mask, Purple Mask, Tribal Chief Mask). Purely cosmetic; per-villager;
must persist across save/reload; masks are tall (extend above the head).

## TL;DR — where it stands

- **Full-exe Detail-screen integration: DONE and building green.** Origins + village-wide +
  mask compose in all modes (63 patches) with no overlap and valid PE checksums; the VV3
  origins tests pass.
- **Detail-screen render: solved and proven** (standalone probe + integrated payload hook).
- **DLL chooser UI: built** (mask cycler in the Change Appearance dialog; export `@20`
  writes `record + 0xED0` on OK).
- **Per-villager persistence byte: found and verified** (`record + 0xED0`, unused).
- **Map/village-view render: still not built** (separate name-based animation system).
- **Remaining before ship:** one **live playtest** (open Change Appearance, pick a mask,
  confirm it renders on the Detail portrait and rides save/reload) and the **atlas deploy
  step** (`build_vv3_mask_atlas.py` must append rows 30..34 to the game's `Images/` head
  atlases — the row-count bump reads out-of-bounds without it).

## How the code-cave blocker was solved

The VV3 `.text`/extended-`.rdata` padding is fully reserved by other features (statistics
alone reserves a 512-byte cave at `0x7B464..0x7B664`, village-wide `0x7B820..0x7BD40`, etc.),
so there is no free standalone `.text` cave for the ~108-byte mask render routine. The first
attempt (commit `5983a77`) placed the cave at `0x7B465` — **inside** statistics' reservation —
which collided. The fix: emit the cave **inside the always-present Origins payload**, in the
free gap between `detail_menu` (ends `+0xAD4`) and `village_preflight` (`+0xB80`), at
`PAYLOAD_VA + 0xAD8` (`0x4A3C58`). It is written with the payload's `put()` helper, whose
occupied-check guards against any payload-layout collision, and the payload region is already
executable via the Origins `0x24C` section-flags patch. The head-draw hook at `0x456B24`
(`jmp 0x4A3C58` + 6 NOPs) reaches it, and the relative `call 0x409FB0` / `jmp 0x456B2F`
re-resolve correctly from the new location (capstone-verified).

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

## Not built: map / village-view masks (RE mapped; needs live iteration)

The village map uses a **separate, texture-index animation system** — a completely different
pipeline from Detail. The Detail-screen hook does nothing there. RE findings (2026-08-22,
capstone on the stock exe):

- **Map render loop** (~`0x45F670`): iterates all 150 villager records (stride `0x1F8C`,
  loop counter `cmp 0x96`), drawing each villager.
- **Map draw primitives**: `0x42E440` / `0x42E510` — thiscall, `this = global 0x58F6F8`.
  These are the map's sprite draws; they do **not** use Detail's `0x409FB0` or the head-atlas
  globals. Frame/sprite indices are small ints (e.g. `2/4/9` by walking/action state) and a
  per-villager texture table at `[edi+0x127C44]` / `[edi+0x127C48]`.
- **Per-villager layer dispatcher** (`0x45F7E0`): reads `record+0xF20` (anim/sprite selector,
  `cmp -1`, `cmp 0x34`), then draws up to three layers gated on animObj **state `+0xE90`**
  (`>1`, `==3`) via `0x42E510`.
- **animObj** = `record+0xDD0`. Anim-setup `0x455AB0` writes head→`+0xE3C`, body→`+0xE40`,
  anim name→`+0xE48` (`strncpy 0x18`), state→`+0xE90`. Setup is driven by `FUN_004582A0`
  (`0x4582A0`, reads head `+0xDF0`/body `+0xDF4`), called 4x (the 4 villager layers) from the
  `0x416F80` layer fn. The player reads these fields through a **shifted pointer** (small
  offsets), which is why `+0xE3C/+0xE40/+0xE48` never appear as disp32 reads.

**Why this is a separate, larger effort than Detail:** the map does not composite from the
head PNG atlas, so the mask-rows-30..34 trick does not apply. A map mask needs (a) the exact
head-layer blit pinpointed as the injection point, (b) a mask texture *registered in the map's
texture system* (`0x58F6F8` / the `[0x4B8700]` table), and (c) a per-frame draw positioned on
the head. All of that is **per-frame render code in a 150-iteration hot loop** — injecting it
blind (no launch) risks crashes/corruption. Recommendation: implement the map masks with live
playtest iteration, not blind. The Detail masks (the primary, interactive surface) are done.

## Superseded: earlier finish options
The three options below were written when the cave placement was still blocked; they are kept
only for history. The blocker is now solved (see "How the code-cave blocker was solved").
