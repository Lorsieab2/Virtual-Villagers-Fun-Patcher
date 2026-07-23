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

This detours to guarded padding at file offset `0x94400`. The detour first preserves the original `[villager+0x1CFC] == 0x0D` Retired Chief predicate. If that predicate is false, it uses the scheduler's invariant `EBX = 0` to compare the nonnegative IEEE-754 Devotion field against zero. A Retired Chief or a villager with positive Devotion continues to the original timing chance; every other villager skips the branch.

At file offset `0x6F1F5`, the seven guarded bytes that begin the stock second random choice detour to a second guarded block at file offset `0x94440`. That block checks the Retired Chief state again:

- A Retired Chief returns to the original random choice and can still select either Honoring or Spreading the Word.
- A newly eligible ordinary devotee goes directly to stock behavior `0xA0` Honoring.

The displaced random-number call is reproduced only on the Retired Chief route and returns to the exact original continuation at virtual address `0x46F1FC`.

## Preserved behavior

- No skill points are written directly by the patch.
- The original Honoring action queue and its stock Devotion gain remain responsible for training.
- The original autonomous scheduler timing remains intact.
- Conversion behavior, statue upgrades, manual statue assignment, and skill thresholds are untouched.
- Spreading the Word is not assigned to ordinary devotees by this patch.
- The Retired Chief retains the stock random Honoring-or-Spreading behavior.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
