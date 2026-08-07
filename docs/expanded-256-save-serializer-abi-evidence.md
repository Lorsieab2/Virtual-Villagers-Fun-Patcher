# VV4/VV5 Expanded-256 save and serializer ABI evidence gate

This additive gate is disabled and fail-closed. Its checked-in evidence matrix is empty, both games are STOP at zero of fourteen required evidence classes, and publication remains false. Static descriptions, candidate offsets, inferred behavior, synthetic fixtures, and manually injected fields cannot satisfy it.

The fourteen requirements are exact save sizes/layouts; loader ABI; stock-import conversion; writer record-count source and tail; serializer bounds; deserializer bounds; padding non-saveability; checksum, encryption, or compression behavior; slot rotation/temp/atomic replacement; failed-load nonmutation; offline-catch-up ordering; manager/pool identity after reload; current Origins behavior; and complete-folder/runtime/player receipts.

Each completed requirement needs an exact row count and canonical row-ledger digest. Every native row must authenticate the function name and EA, instruction EA, file offset, preimage, calling convention, return and failure semantics, xrefs, exact source artifact, and both runtime and player receipt references. Completion also requires exact stock and expanded save byte sizes and layout digests, a complete authenticated folder inventory, and authenticated player observations. Unknown checksum/encryption/compression behavior remains STOP; “none” must itself be proved.

Bindings are exact: VV4 stock SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220, VV5 stock SHA-256 92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D, the 13-row VV4 and 66-row VV5 relocation ledgers, stored-index canonical digest C606ACF950ED6C193F921D06F738CE0854AD7A3F390524E5C0B333600788E275, runtime contract digest C70F0BD0CDDFF921B215FA178D725A57EC2AEE380C575FFD1D56D8F282562B60, and capture-harness file digest 719DAD95AC6AB2D2E1CC9F64DECF1BB894CC4A98B5B7662A3A84402B2C5CA321.

The gate does not emit native changes and cannot set GO. No game was launched, no save was accessed, no package was produced, and no shared relocation, runtime, or publication file was changed while establishing this contract.
