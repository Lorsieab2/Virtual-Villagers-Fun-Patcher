# VV3 Nature level 3 mortality research

Supported executable: `Virtual Villagers - The Secret City.exe`

- Size: `831,488` bytes
- SHA-256: `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`

## Stock behavior

VV3's shared villager aging loop begins at virtual address `0x45FFE0`. It is
called by the elapsed-state updater at `0x428C60` and advances the saved age
state until it reaches the current simulation state.

The loop reads Medicine with technology ID `1` and Nature with technology ID
`5` at `0x4601B1`. The accessor at `0x426FC0` simply returns the requested
technology level. In stock code, both return values at this first location are
discarded immediately; the Nature result does not participate in a comparison,
write, or calculation.

The actual old-age threshold at `0x4602C1` reads Medicine again and calculates:

`threshold = 1100 + 160 * (Medicine level - 1)`

VV3 uses 20 internal age units per displayed year. The stock Medicine
thresholds are therefore 55, 63, and 71 displayed years at levels 1, 2, and 3.
At each birthday strictly above the threshold, the old-age death chance rises
by 10 percentage points.

No stock Nature level changes that threshold.

## Patch behavior

The patch detours the final Medicine-based threshold construction at file
offset `0x602ED` into unused mapped `.text` padding at file offset `0x7B400`.
The cave:

1. reconstructs the exact stock Medicine threshold;
2. reads Nature technology ID `5`;
3. adds 140 internal age units only when the returned level is at least 3;
4. restores the stock age comparison and return path.

140 internal units equal seven displayed years. Nature levels 0 through 2
preserve the original bytes' effective result. Because this changes the
threshold inside the shared aging loop, it applies during ordinary simulation
and elapsed-time catch-up. It does not change displayed age, health, sickness,
or Medicine technology.
