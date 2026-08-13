# VV4 Expanded-256 composite candidate

The source-bound renderer `scripts/build_vv4_expanded_256_candidate.py` adds
the reviewed 256-record serializer and hard-bounded deserializer to the
latest VV4 Expanded progression render:

`AC430442DE23406236903CAA6FC9A992D52DCF3269A95ED345A9EF6F18B9C30A`

The renderer preserves the existing expanded storage, initialization, tail
relocations, stock-save conversion, record walkers, and current feature bytes.
It appends the authenticated `.vv4x` page at raw `0xE3000`, updates the unused
section header slot, raises `SizeOfImage` from `0x471000` to `0x472000`, and
hooks the save serializer call at raw `0x1F125` and deserializer call at raw
`0x1FD34`.

This is a static candidate, not a safe-release claim. The atomic writer,
checked failure handling, runtime save/load/reload receipts, and player
confirmation remain STOP gates. The public Expanded-256 publication guard
therefore remains disabled.

```powershell
$env:PYTHONPATH = "src"
python scripts/build_vv4_expanded_256_candidate.py `
  outputs/expanded-256-audit/vv4-renders/vv4-experimental_expanded_256_progression-all-current.exe `
  outputs/vv4-expanded-256-candidate/VV4-Expanded-256-Candidate.exe
python -m unittest tests.test_vv4_expanded_256_candidate
```
