# VV3 Expanded-256 runtime capture harness

This is a disabled preparation harness, not a launcher or runtime
certification. It only preflights explicitly supplied paths and prints an
unsigned, observation-empty checklist. It has no code path that launches the
game, discovers save locations, opens save files, signs evidence, or changes a
runtime/player/publication gate.

The harness is bound to the authenticated static evidence contract in
`src/vv3_expanded_256_evidence.py`. The evidence bundle and its canonical
exporter manifest must pass file-bound validation first. The generated template
records the evidence digest, exporter-manifest body and file digests, exporter
run identity, exact stock SHA-256, and expanded prototype SHA-256. Declared
metadata alone is not authentication.

## Exact complete-folder preflight

The operator must explicitly provide both the game folder and a separate
canonical folder-inventory JSON. Production preflight requires the exact folder
name `Virtual Villagers - The Secret City - Modded 256` and exactly 419 files:

| Role | Exact count |
|---|---:|
| Stock executable | 1 |
| Retained game assets | 411 |
| Modded 256 entry executable | 1 |
| `VVFP Origins Icons.dll` | 1 |
| Patch log | 1 |
| Transparency log | 1 |
| Player readme | 1 |
| Runtime inventory | 1 |
| Checksum list | 1 |

The stock executable is fixed at 831,488 bytes and SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
The companion DLL is fixed at 295,936 bytes and SHA-256
`2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9`.
The declarative inventory must contain one canonical, sorted path/role/size/hash
record for every physical file. The actual folder path set must match exactly;
missing and extra files both fail. Every component is checked for symlink,
junction, or reparse behavior, and every file is hashed and re-read. A partial
folder with a correspondingly partial inventory is rejected by the fixed count
and role contract. Its declarative shape is documented by
`data/vv3_expanded_256_folder_inventory.schema.json`; schema acceptance alone
cannot prove file presence, hashes, ordering, role counts, or no-follow reads.

## Save boundary

`--modded-save-root` is mandatory and must point directly to an existing
`Virtual Villagers - The Secret City - Modded 256` directory. The harness checks
only the explicitly supplied path and its filesystem metadata. It rejects
symlink/reparse components and does not list the directory or open any save.
Vanilla, automatically discovered, current-user, and inferred save roots are
not accepted.

## Pending checklist

The generated receipt has eleven ordered pending stages:

1. loader-hang instruction, caller, return address, branch, registers, stack,
   and thread state;
2. exact stock-layout import;
3. expanded save and reload;
4. offline catch-up;
5. failed-load nonmutation;
6. save rotation and backup behavior;
7. records 149, 150, 254, and 255;
8. proof that padding indices 256-259 are unreachable;
9. all ten stored-index width/sentinel paths;
10. current `vv3_enable_origins_exclusive_features` behavior;
11. explicit player validation tied to the exact receipt and build.

Every stage starts with `status: pending`, empty observation/artifact references,
no operator notes, and `player_confirmed: false`. The integrity block is
unsigned and has no digest or signature. Runtime GO, player GO, and publication
remain false with decision `STOP`. This version intentionally rejects any
attempt to turn the template into observed evidence; a separately authorized
future receipt validator is required after genuine player/runtime capture.

## Dry-run command

```text
python scripts/prepare_vv3_expanded_runtime_capture.py --dry-run --evidence-json path\evidence.json --catalog-root path\evidence-catalog --game-folder "path\Virtual Villagers - The Secret City - Modded 256" --folder-inventory path\folder-inventory.json --modded-save-root "path\Virtual Villagers - The Secret City - Modded 256"
```

Successful preflight writes canonical JSON only to standard output. There is no
output-file, launch, save-copy, save-read, signing, or publication option.
Temporary-fixture unit tests use injected miniature folder contracts and never
require a stock executable, game folder, DLL, or real save.
