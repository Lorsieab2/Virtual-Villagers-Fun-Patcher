# VV3 Nature Level 1 Honey Refill Research

## Supported executable

| Size | SHA-256 |
|---:|---|
| 831,488 bytes | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |

## Stock mechanics

The Secret City's Nature technology is technology index 5. The technology-level getter is `0x00426FC0`, using the technology manager at `0x00582618`.

The fruit-tree refill loop begins at `0x00434760`. Once at least `0x2A30` seconds (10,800 seconds) have elapsed, it calculates a refill from elapsed time with factor 37 at Nature level 0 and factor 42 at Nature level 1 or higher. The resulting proportional improvement is exactly `42 / 37`. Nature does not change the fruit-tree update threshold in this routine.

The honey resource object begins at `0x005945D0`; its current amount is the field at `+0x10`, also visible as global address `0x005945E0`. Its update routine begins at `0x004319B0`. Stock honey waits for at least `0xE10` seconds (3,600 seconds), adds `floor(elapsed_seconds * 2 / 3600)` units, records the current timestamp, and caps the resource at `0xBB8` (3,000). That stock routine contains no Nature-technology check.

## Patch

The patch replaces the 16-byte stock honey refill calculation at file offset `0x319F9` with a guarded detour into unused mapped `.text` padding at file offset `0x7B2A0`.

The detour:

1. Calculates the elapsed seconds exactly as the stock routine does.
2. Reads Nature technology level through the stock technology getter.
3. At Nature level 0, executes the original multiply-and-shift arithmetic.
4. At Nature level 1 or higher, calculates `floor(elapsed_seconds * 84 / 133200)`, which is the stock honey rate multiplied by the fruit trees' exact `42 / 37` improvement.
5. Returns to the untouched stock amount addition, timestamp update, and 3,000-unit cap.

The one-hour honey update threshold is unchanged. No honey is granted immediately when the patch is applied; the improvement is evaluated by the game's existing refill update.

## Boundaries

- Nature level 0 retains the stock honey refill rate.
- Nature levels 1, 2, and 3 share the same improved rate, matching the fruit-tree threshold behavior.
- The patch does not change honey harvesting, initial honey, the honey display, fruit-tree behavior, technology costs, or Nature technology progression.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
