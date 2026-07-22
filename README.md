# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

Its max-population patch uses every built-in villager slot: 256 slots in A New Home and The Lost Children, and 150 slots in The Secret City, The Tree of Life, and New Believers.

## Two patch styles

Choose the style in the patcher; the choice and all paths are remembered.

| Style | Collection behavior | Output suffix |
|---|---|---|
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `- Modified Max Pop.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `- Fixed Max Pop.exe` |

A New Home has no collection population bonus, so both styles use the same 256 limit but still create separately named outputs.

## VV2: Easier Healing Mastery

Enable the optional **Easier Healing Mastery (VV2)** checkbox to change the Healing job fallback in The Lost Children. When a healer or a villager who prefers Healing has no sick villager to treat, the stock job scheduler now enters its existing persistent plant-study state instead of returning "no work." The same stock state is processed during ordinary play and time catch-up.

The patch does not change healing gains, illness, food, skill thresholds, plant availability, or manual plant study. If the option is combined with Collection Progression, the output is named `Virtual Villagers - The Lost Children - Modified Max Pop + Easier Healing.exe`; Immediate Fixed uses the matching `Fixed Max Pop + Easier Healing.exe` name. Max-pop-only names remain unchanged.

| Game | Stock final maximum | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|
| A New Home | 90 | 256 | 256 |
| The Lost Children | 115 | 231 to 256 | 256 |
| The Secret City | 125 | 115 to 150 | 150 |
| The Tree of Life | 115 | 125 to 150 | 150 |
| New Believers | 105 | 135 to 150 | 150 |

Housing gates remain in place.

## Safe twins and triplets at the ceiling

All five stock games test the population limit once before choosing a singleton, twins, or triplets. Without an additional guard, a multiple birth at maximum minus one can report maximum plus one or maximum plus two, even though no corresponding villager records remain.

Both patch styles add a slot-saturation guard:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a patch style.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Validate, dry run, or create the modified EXE set.

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The original EXEs are never edited, renamed, replaced, or deleted. Outputs and their `.patch-log.json` verification logs are placed beside the originals in their respective game folders. Both styles can coexist.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, file size is preserved, the PE checksum is recalculated, and each result is read back and hashed.

Bulk mode validates and renders all five inputs before writing, then stages and verifies all five outputs before placing them into the game folders.

No game executable, save, extracted asset, or generated output is committed to this repository.

## Command line

Pass `--patch-mode collection_progression` or `--patch-mode immediate_fixed` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. Add `--fun-patch vv2_easier_healing_mastery` for the VV2 option.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed
python src/vv_fun_patcher.py apply "path\game.exe" --patch-mode collection_progression
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed
```

Technical evidence is in `docs/max-population-research.md` and `docs/vv2-easier-healing-research.md`.
