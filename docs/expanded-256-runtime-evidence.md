# VV4/VV5 Expanded-256 runtime-evidence boundary

This is a fail-closed evidence contract, not a runtime certification. The
canonical record is
`data/expanded_256_runtime_evidence.json`, validated by
`scripts/validate_expanded_runtime_evidence.py`. Its publication, runtime-GO,
player-GO, and eligibility flags are all `false`.

## Exact static identities

The contract binds the exact stock image and the two static candidate-render
fingerprints for each game. Static render hashes are candidate evidence only;
they are not launch, save, or player receipts.

| Game | Stock size / SHA-256 | Expanded immediate SHA-256 | Expanded progression SHA-256 |
|---|---:|---|---|
| VV4 The Tree of Life | 929,792 / `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` | `602824F514BFAB80883805B16C01D1E572752261A155262778CF8D535C41D887` | `AC430442DE23406236903CAA6FC9A992D52DCF3269A95ED345A9EF6F18B9C30A` |
| VV5 New Believers | 991,232 / `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` | `44042572653782B20A200799785F437D4D76B46F20384D597B8093F27CC88C89` | `6BF9E0EB9BC7D3C373E32C3A7377C9A7EA35C1FA889EEDBF9B2819A25BC43E86` |

The static current-Origins relocation ledgers are independently pinned:

- VV4: exactly 13 rows, ledger SHA-256
  `CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D`.
- VV5: exactly 66 rows, ledger SHA-256
  `14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7`.

The validator recomputes each ledger digest from canonical sorted JSON rows and
checks the source-file SHA-256 before accepting the static contract.

## Required runtime evidence

For either game and either expanded mode, a future observed record must include
a complete folder inventory with one stock executable, immediate and
progression expanded executables, the required `VVFP Origins Icons.dll`,
runtime inventory, checksum list, patch log, transparency log, and player
readme. Every record requires a relative no-follow path, role, size, SHA-256,
identical re-read SHA-256, and authenticated runtime-artifact provenance.

The runtime receipt must separately cover all of these gates:

- exact stock-save import and conversion;
- expanded save, reload, and offline catch-up;
- failed-load nonmutation and save rotation/backup behavior;
- late records 149, 150, 254, and 255;
- padding/unreachable-record behavior where applicable (VV4/VV5 explicitly
  record this as not applicable because their static layouts have no VV3-style
  four-record padding reservation);
- current Origins behavior after relocation;
- every 13 VV4 or 66 VV5 relocation row;
- explicit player runtime receipts.

Observed evidence is accepted only from an exact-build player-runtime producer
with a full source commit, capture tool, operator, capture time, provenance,
stable artifact inventory, and canonical receipt digest. Synthetic fixtures,
static renders, inferred behavior, and developer-only observations are rejected
as runtime evidence and can never establish publication GO.

No saves are present in this repository contract. No executable is launched by
the validator. A future receipt must be supplied separately by an authorized
player/runtime evidence workflow; until then both games remain ON HOLD.
