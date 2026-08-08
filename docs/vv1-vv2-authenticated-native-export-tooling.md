# VV1/VV2 authenticated native export tooling

These scripts are read-only preparation tools. They do not launch IDA, Ghidra, or a game; they do not read saves; and they do not accept game folders outside this repository. Before any later run, copy a complete game folder into a dedicated workspace subdirectory and obtain separate authorization.

1. Generate a dry-run plan with `python scripts/vv_native_evidence_inventory.py <workspace-game-folder> --game vv1 --dry-run`. This traverses without following links, rejects links/reparse points and non-regular files, hashes every file, carries the exact `file_count` and `dll_count` into the plan, and prints only canonical JSON to standard output.
2. Review the query plan and exact source inventory. Do not run either disassembler template without separate authorization. Both templates deliberately stop until reviewed query addresses and source bindings are supplied inside an authorized IDA/Ghidra session.
3. An automated exporter must populate every query in `data/native_evidence/vv1_vv2_native_query_manifest.json`, including function bounds, effective addresses, file offsets, raw bytes and hashes, instructions, callers/callees/xrefs, register/stack cleanup/return contracts, side effects, and the identical source binding on every record. That binding includes the executable, complete-folder inventory, canonical manifest, exporter source, and analyzer name/version.
4. Validate with `python scripts/vv_native_evidence_validate.py export.json --manifest data/native_evidence/vv1_vv2_native_query_manifest.json --inventory inventory.json`.

The validator rejects partial query coverage, manual edits, synthetic or placeholder wording, malformed addresses/hashes, duplicate queries, raw-byte hash mismatches, source-binding drift, and noncanonical artifact hashes. An `absent-proved` result is allowed only as an automated record with the same complete field set and binding; it is not permission to omit a query.

No generated inventory or export belongs in Git. Keep later evidence under an ignored/output location and bind it by SHA-256 in a separately reviewed change. This commit contains scripts, templates, fixtures, tests, and documentation only.
