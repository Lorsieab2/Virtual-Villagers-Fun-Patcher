# C342 Expanded-256 export preflight

This is a read-only, fail-closed preflight for the repository-contained `inputs/vv4-stock-copy` and `inputs/vv5-stock-copy` folders. It requires exactly 556 and 639 physical files, rejects symlinks/reparse-like entries, verifies the exact stock executable hashes, checks C342’s VV4 13-row and VV5 66-row ledger/source-text rebinding, and requires a separately produced authenticated machine-export packet for each game.

The current specialist branch is pre-C342, so its local VV5 digest is not accepted as the C342 binding. The C342 target is VV4 `CEE01F4A…` / 13 and VV5 `14E46077…` / 66, with source-text pins recorded in the contract. Missing folders, stale pins, missing export packets, synthetic/manual fields, or changed re-read hashes are STOP.

The validator never launches executables, opens saves, writes inventories, emits native bytes, or changes publication state. It only consumes pre-existing inputs and export packets. The export packet’s `re_read_sha256` is the canonical digest of the packet with that field removed, allowing stable re-read authentication without a self-referential hash.

```powershell
python scripts/validate_c342_export_preflight.py `
  --vv4-folder inputs/vv4-stock-copy `
  --vv5-folder inputs/vv5-stock-copy `
  --vv4-export inputs/vv4-stock-copy/c342-native-export.json `
  --vv5-export inputs/vv5-stock-copy/c342-native-export.json
```
