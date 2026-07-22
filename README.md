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
3. Choose one original game EXE and an output folder.
4. Use **Validate** or **Dry Run**, then **Create Modified EXE**.

The patcher remembers both paths in `patcher_local_settings.json`. It never edits the original EXE. It creates exactly one of these names:

- `Virtual Villagers - A New Home - Modified Max Pop.exe`
- `Virtual Villagers - The Lost Children - Modified Max Pop.exe`
- `Virtual Villagers - The Secret City - Modified Max Pop.exe`
- `Virtual Villagers - The Tree of Life - Modified Max Pop.exe`
- `Virtual Villagers - New Believers - Modified Max Pop.exe`

A `.patch-log.json` file records the source and output hashes and every applied byte guard.

## Supported builds and safety

Support is bound to the exact SHA-256 and size of each supplied stock executable. Unknown, previously modified, or corrupt EXEs are refused. Every original byte is checked before editing, outputs are written atomically, file size is preserved, the PE checksum is recalculated, and the finished file is read back and hashed.

No game executable, save, extracted asset, or generated output is stored in this repository.

## Command line

```text
python src/vv_fun_patcher.py identify "path\\game.exe"
python src/vv_fun_patcher.py dry-run "path\\game.exe"
python src/vv_fun_patcher.py apply "path\\game.exe" "output folder"
```

Technical evidence is in `docs/max-population-research.md`.
