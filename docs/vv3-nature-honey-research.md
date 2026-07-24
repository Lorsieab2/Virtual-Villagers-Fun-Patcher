# VV3 Nature Level 1 Actually Replenishes Food Sources Faster

## Supported executable

| Size | SHA-256 |
|---:|---|
| 831,488 bytes | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |

## Stock mechanics

The Secret City's Nature technology is technology index 5. The technology-level getter is `0x00426FC0`, using the technology manager at `0x00582618`.

The fruit-tree refill loop begins at `0x00434760`. Once at least `0x2A30` seconds (10,800 seconds) have elapsed, it calculates a refill from elapsed time with factor 37 at Nature level 0 and factor 42 at Nature level 1 or higher. The resulting proportional improvement is exactly `42 / 37`. Nature does not change the fruit-tree update threshold in this routine.

The honey resource object begins at `0x005945D0`; its current amount is the field at `+0x10`, also visible as global address `0x005945E0`. Its update routine begins at `0x004319B0`. Stock honey waits for at least `0xE10` seconds (3,600 seconds), adds `floor(elapsed_seconds * 2 / 3600)` units, records the current timestamp, and caps the resource at `0xBB8` (3,000). That stock routine contains no Nature-technology check.

## Patch

The patch gives Nature level 1 or higher a 75%-time eligibility threshold for both renewable food sources:

- fruit trees: 10,800 seconds becomes 8,100 seconds, or 2 hours 15 minutes;
- honey: 3,600 seconds becomes 2,700 seconds, or 45 minutes.

Nature level 0 follows the original thresholds and calculation. At Nature level 1 or higher, the tree calculation uses effective factor 56 over the new 8,100-second interval. This produces the same amount as factor 42 over the stock 10,800-second interval: `8100 × 56 = 10800 × 42`. The shorter timer therefore does not turn the refill into a smaller partial award.

The patch also retains the guarded honey-amount detour at file offset `0x319F9` into unused mapped `.text` padding at file offset `0x7B2A0`.

The detour:

1. Calculates the elapsed seconds exactly as the stock routine does.
2. Reads Nature technology level through the stock technology getter.
3. At Nature level 0, executes the original multiply-and-shift arithmetic.
4. At Nature level 1 or higher, calculates `floor(elapsed_seconds * 84 / 99900)`. The denominator is `37 × 2700`, so the honey quantity retains the fruit trees' exact `42 / 37` improvement while being normalized to the new 45-minute interval.
5. Returns to the untouched stock amount addition, timestamp update, and 3,000-unit cap.

No fruit or honey is granted immediately when the patch is applied. The shorter thresholds and improved honey amount are evaluated by the game's existing refill updates.

## Boundaries

- Nature level 0 retains stock fruit-tree and honey timing and amounts.
- Nature levels 1, 2, and 3 share the same faster thresholds and improved rates.
- The stock Nature fruit-tree amount per normal refill is preserved at the shorter interval.
- The patch does not change honey harvesting, initial honey, the honey display, resource caps, technology costs, or Nature technology progression.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
