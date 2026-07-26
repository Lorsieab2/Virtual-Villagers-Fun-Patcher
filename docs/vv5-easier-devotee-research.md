# VV5 Easier Devotee Training Research

## Supported executable

- Game: Virtual Villagers 5: New Believers
- Size: 991,232 bytes
- SHA-256: `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`

All file offsets and virtual addresses below refer only to this exact executable.

## Stock behavior

The villager's six skill values are contiguous single-precision fields at offsets `0x1C5C` through `0x1C70`. The villager-details renderer reads the sixth field, `[villager+0x1C70]`, and draws it with skill icon `0x0B`; other Devotion gameplay routines also read this same field.

The autonomous scheduler begins at virtual address `0x46F070`. It establishes `EBX = 0` at `0x46F07D`. Its relevant branch:

1. Loads the villager at `0x46F1D7`.
2. Tests `[villager+0x1CFC] == 0x0D` at `0x46F1DD`. This is a job-state field, not the Devotion skill. Player-confirmed behavior identifies this as the Retired Chief state.
3. Keeps an existing 50-percent scheduler chance at `0x46F1E6`.
4. Randomly chooses behavior `0xA0` (Honoring) or `0xA1` (Spreading the Word) at `0x46F1F5`.

Behavior `0xA0` is the retained stock Honoring routine at virtual address `0x45CB70`. Behavior `0xA1` is the retained Spreading the Word routine at `0x45CD80`; in observed game behavior, only the villager whose job is Retired Chief uses Spreading the Word. Ordinary devotees do not. The patch deliberately routes newly eligible ordinary devotees into `0xA0` instead of reproducing or directly altering its skill award.

## Patch

At file offset `0x6F1DD`, the nine guarded bytes:

`83 B9 FC 1C 00 00 0D 75 54`

become:

`E9 1E 52 02 00 90 90 90 90`

This detours to guarded padding at file offset `0x94400`. The detour first
preserves the original `[villager+0x1CFC] == 0x0D` Retired Chief predicate. If
that predicate is false, it checks both of the stock villager fields used by the
details screen:

- `[villager+0x1C74] == 5`, meaning Devotion is the selected preferred job.
- `[villager+0x1C70] > 0`, meaning the villager has positive Devotion skill.

A Retired Chief jumps directly back to the original timing and
Honoring-or-Spreading code at `0x46F1E6`. The patch does not replace or
intercept the stock random choice at `0x46F1F5`.

An ordinary villager with positive Devotion skill enters a separate block at
file offset `0x94900`. The selected-job check is deliberately not required;
the relocation keeps the block clear of the expanded VV5 save-loader cave:
Devotion skill alone makes the villager eligible, while a zero-skill villager
returns to the ordinary scheduler. The block reproduces the stock 50-percent
timing chance and, on success, queues stock behavior `0xA0` Honoring. A failed
chance returns to the ordinary scheduler at `0x46F23A`.

## Preserved behavior

- No skill points are written directly by the patch.
- The original Honoring action queue and its stock Devotion gain remain responsible for training.
- The original autonomous scheduler timing remains intact.
- Conversion behavior, statue upgrades, manual statue assignment, and skill thresholds are untouched.
- Manual statue Honoring can still train a beginner with no Devotion skill.
- A villager with no Devotion skill is not diverted into autonomous Honoring.
- Spreading the Word is not assigned to ordinary devotees by this patch.
- The Retired Chief uses the original stock eligibility, timing, and random
  Honoring-or-Spreading code. No custom Retired Chief discriminator remains.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
