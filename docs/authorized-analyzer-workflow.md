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

No game is launched, no save is accessed, and no native output or route
enablement is produced. All workflow, catalog, runtime, player, and publication
gates remain disabled/fail-closed.
