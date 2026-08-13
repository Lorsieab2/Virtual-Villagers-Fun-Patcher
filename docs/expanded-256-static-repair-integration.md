# Expanded-256 static repair integration

The real patcher applies the reviewed static serializer/reader repairs only in
Expanded-256 modes. Stock modes are unchanged. Every repair is transactional:
the complete stage parent identity and every byte preimage must match before
the in-memory executable is changed, and the exact stage result hash must match
after the PE checksum is recomputed.

The immutable `data/expanded_256.json` manifests and their row digests are not
rewritten. The active lineage and exact current-manifest parent/result hashes
are pinned in `data/expanded_256_static_repair_integration.json`.

- VV3 appends the reviewed `.vv3sv` serializer/reader/gate page after the exact
  Origins + village-wide Running Expanded composition has been relocated.
- VV4 appends the reviewed `.vv4x` serializer/reader/gate page immediately after
  its immutable Expanded manifest rows.
- VV5 applies the reviewed 16 same-width operand repairs immediately after its
  immutable 1951-row Expanded manifest and before later automatic/fun patches.

Dry-run and patch-log payloads include `expanded_static_repairs`, with the
repair ID, stage parent SHA-256, stage result SHA-256, and final rendered
SHA-256. This is emitted native patch content, but it is not runtime/player or
publication evidence. Atomic save writers, runtime verification, player
receipts, and Expanded publication remain separate gates.

The VV4 candidate's `d353_helpers.singleton.sha256` is explicitly the stock
helper hash `CFD204...BBE08`. The current immutable Expanded manifest changes
only the guarded allocation immediate at raw `0x1FE9B` from `C8710100` to
`70DD0100`, so the exact current-parent helper hash is
`C7F59E4C...35C98E5F`; its control flow and ABI are unchanged. The integration
contract binds both hashes and verifies the current-parent range before it
emits `.vv4x`; it does not mislabel the historical stock helper hash as the
active-parent hash.
