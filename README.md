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
4. Select the original EXE or EXEs and an output folder.
5. Validate, dry run, or create the modified EXE set.

In **All 5 Games**, you can choose each EXE separately or use **Find All 5 in Parent Folder...** when the five original EXEs are directly in the chosen folder or one folder below it. The patcher validates every source before writing any batch output.

The patcher remembers the one-game path, all five bulk paths, and the output folder in `patcher_local_settings.json`. It never edits an original EXE. It creates:

- `Virtual Villagers - A New Home - Modified Max Pop.exe`
- `Virtual Villagers - The Lost Children - Modified Max Pop.exe`
- `Virtual Villagers - The Secret City - Modified Max Pop.exe`
- `Virtual Villagers - The Tree of Life - Modified Max Pop.exe`
- `Virtual Villagers - New Believers - Modified Max Pop.exe`

Each output receives a `.patch-log.json` file recording the source and output hashes and every applied byte guard.

## Supported builds and safety

Support is bound to the exact SHA-256 and size of each supplied stock executable. Unknown, previously modified, corrupt, duplicated, or incorrectly assigned EXEs are refused. Every original byte is checked before editing, file size is preserved, the PE checksum is recalculated, and each finished file is read back and hashed.

Bulk mode performs exact-build validation, guarded patch rendering, and existing-output checks for all five games before it creates or replaces any final EXE. It stages and verifies all five generated files before committing them to the selected output folder.

No game executable, save, extracted asset, or generated output is stored in this repository.

## Command line

Single game:

```text
python src/vv_fun_patcher.py identify "path\\game.exe"
python src/vv_fun_patcher.py dry-run "path\\game.exe"
python src/vv_fun_patcher.py apply "path\\game.exe" "output folder"
```

All five:

```text
python src/vv_fun_patcher.py dry-run-all --vv1 "path\\vv1.exe" --vv2 "path\\vv2.exe" --vv3 "path\\vv3.exe" --vv4 "path\\vv4.exe" --vv5 "path\\vv5.exe"
python src/vv_fun_patcher.py apply-all "output folder" --vv1 "path\\vv1.exe" --vv2 "path\\vv2.exe" --vv3 "path\\vv3.exe" --vv4 "path\\vv4.exe" --vv5 "path\\vv5.exe"
```

Technical evidence is in `docs/max-population-research.md`.
