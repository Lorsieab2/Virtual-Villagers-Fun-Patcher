# Virtual Villagers Fun Patcher

A small, offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

The first patch, **Modified Max Pop**, raises each game's maximum possible population to the size of its built-in villager record pool:

| Game | Stock final maximum | Villager slots | Modified final maximum |
|---|---:|---:|---:|
| A New Home | 90 | 256 | 256 |
| The Lost Children | 115 with all four collections | 256 | 256 with all four collections |
| The Secret City | 125 with all four collections and level-3 magic | 150 | 150 with all four collections and level-3 magic |
| The Tree of Life | 115 with all four collections | 150 | 150 with all four collections |
| New Believers | 105 with both collections | 150 | 150 with both collections |

Housing and collection progression are retained. Only the final maximum changes.

## Use

1. Extract the release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Choose **One Game** or **All 5 Games**.
4. For one game, select its original EXE. For all five, select one game folder in each of the five fields.
5. Validate, dry run, or create the modified EXE set.

In **All 5 Games**, there are five separate folder fields, one for each game. Select the folder containing that game's original EXE. You can also use **Find All 5 in Parent Folder...** when the five original EXEs are directly in the chosen folder or one folder below it. The patcher finds the correctly named EXE inside each selected folder and validates every source before writing any batch output.

The patcher remembers the one-game EXE path and all five game-folder paths in `patcher_local_settings.json`. It never edits, renames, replaces, or deletes an original EXE. Each modified EXE and its verification log are created beside the original in that game's folder:

- `Virtual Villagers - A New Home - Modified Max Pop.exe`
- `Virtual Villagers - The Lost Children - Modified Max Pop.exe`
- `Virtual Villagers - The Secret City - Modified Max Pop.exe`
- `Virtual Villagers - The Tree of Life - Modified Max Pop.exe`
- `Virtual Villagers - New Believers - Modified Max Pop.exe`

Each output receives a `.patch-log.json` file recording the source and output hashes and every applied byte guard.

## Supported builds and safety

Support is bound to the exact SHA-256 and size of each supplied stock executable. Unknown, previously modified, corrupt, duplicated, or incorrectly assigned EXEs are refused. Every original byte is checked before editing, file size is preserved, the PE checksum is recalculated, and each finished file is read back and hashed.

Bulk mode performs exact-build validation, guarded patch rendering, and existing-output checks for all five games before it writes anything. It stages and verifies all five generated files before placing each one in its corresponding game folder.

No game executable, save, extracted asset, or generated output is stored in this repository.

## Command line

Single game:

```text
python src/vv_fun_patcher.py identify "path\\game.exe"
python src/vv_fun_patcher.py dry-run "path\\game.exe"
python src/vv_fun_patcher.py apply "path\\game.exe"
```

All five:

```text
python src/vv_fun_patcher.py dry-run-all --vv1 "path\\vv1 folder" --vv2 "path\\vv2 folder" --vv3 "path\\vv3 folder" --vv4 "path\\vv4 folder" --vv5 "path\\vv5 folder"
python src/vv_fun_patcher.py apply-all --vv1 "path\\vv1 folder" --vv2 "path\\vv2 folder" --vv3 "path\\vv3 folder" --vv4 "path\\vv4 folder" --vv5 "path\\vv5 folder"
```

Technical evidence is in `docs/max-population-research.md`.
