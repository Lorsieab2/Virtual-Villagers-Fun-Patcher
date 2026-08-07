# VV4/VV5 Expanded-256 save and serializer ABI evidence gate

This additive gate is disabled and fail-closed. Its checked-in evidence matrix is empty, both games are STOP at zero of fourteen required evidence classes, and publication remains false. Static descriptions, candidate offsets, inferred behavior, synthetic fixtures, and manually injected fields cannot satisfy it.

The fourteen requirements are exact save sizes/layouts; loader ABI; stock-import conversion; writer record-count source and tail; serializer bounds; deserializer bounds; padding non-saveability; checksum, encryption, or compression behavior; slot rotation/temp/atomic replacement; failed-load nonmutation; offline-catch-up ordering; manager/pool identity after reload; current Origins behavior; and complete-folder/runtime/player receipts.

Each completed requirement needs an exact row count and canonical row-ledger digest. Every native row must authenticate the function name and EA, instruction EA, file offset, preimage, calling convention, return and failure semantics, xrefs, exact source artifact, and both runtime and player receipt references. Completion also requires exact stock and expanded save byte sizes and layout digests, a complete authenticated folder inventory, and authenticated player observations. Unknown checksum/encryption/compression behavior remains STOP; “none” must itself be proved.

Bindings are exact: VV4 stock SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220, VV5 stock SHA-256 92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D, the 13-row VV4 and 66-row VV5 relocation ledgers, stored-index canonical digest 4A8C0554B495651ABF951E71D6DC481382929CBF8FA9A0EF9182CEA5C165B54D, runtime contract digest 44006789E82B4C92C9940B8B33ED3AFDFCA45EB25DF774F22156AEF9FF7392E8, and capture-harness source-text digest 719DAD95AC6AB2D2E1CC9F64DECF1BB894CC4A98B5B7662A3A84402B2C5CA321.

The gate does not emit native changes and cannot set GO. No game was launched, no save was accessed, no package was produced, and no shared relocation, runtime, or publication file was changed while establishing this contract.
