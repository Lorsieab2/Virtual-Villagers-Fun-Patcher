# Authorized analyzer workflow (disabled, read-only)

This additive workflow binds the VV3-VV5 ten-query export plans to the exact
no-follow inventories under `inputs/`. It records the available VV2 manifest
without fabricating the two rows required by a separate 50-query manifest.

The repository currently contains `data/native_evidence/vv1_vv2_native_query_manifest.json`
with 48 query IDs. The dedicated 50-query VV2 manifest, its path/hash, and the
two additional query IDs are absent, so the reconciliation remains STOP with
`unresolved_query_count: 2` and `unresolved_query_ids: null`.

VV3, VV4, and VV5 inventory and dry-run plan preparation is complete with zero
writes and ten query families per game. Actual IDA/Ghidra export remains
pending an authorized session bound to the exact executable hash, an automated
unedited EA map/export, and source-binding hashes. Historical research IDA
databases and static audit JSONs are not treated as certified exports here.

## Expected export artifact names

The generic VV3-VV5 exporter validation command names these source-bound JSON
artifacts explicitly:

| Game | Expected artifact | Current state |
| --- | --- | --- |
| VV2 | **Not defined yet** | STOP: the authoritative dedicated 50-query manifest is missing, so its export path cannot be inferred. |
| VV3 | `inputs/vv3-export.json` | Absent; no authorized machine export has been written. |
| VV4 | `inputs/vv4-export.json` | Absent; no authorized machine export has been written. |
| VV5 | `inputs/vv5-export.json` | Absent; no authorized machine export has been written. |

For VV2, `export.json` and `inventory.json` in the legacy validator example
are command-line placeholders, not canonical filenames. Do not create or
rename an export until the missing 50-query manifest supplies its authoritative
path and query IDs.

No game is launched, no save is accessed, and no native output or route
enablement is produced. All workflow, catalog, runtime, player, and publication
gates remain disabled/fail-closed.

## Read-only query discovery

The repository also provides a metadata-only discovery helper:

```powershell
python scripts\discover_vv345_native_evidence.py
```

It prints the ordered ten-query metadata for VV3, VV4, and VV5 together with
their current source-binding records. It does not open a game folder, IDA
database, save, or executable, and it never writes an export. Unresolved EA,
file-offset, raw-byte, register, stack-cleanup, and calling-convention fields
are emitted as `null`. The report remains `STOP` when the workflow has no
reviewed artifact; a future workflow declaration without independently
validated packet rows is reported as `DECLARED_BUT_UNVERIFIED` and also
remains `STOP`.
