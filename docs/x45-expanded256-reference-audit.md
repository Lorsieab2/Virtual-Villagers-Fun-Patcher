# X45 Expanded-256 reference audit

This additive audit is STOP-only. It preserves the VV4 13-row and VV5 66-row ledgers and mechanically re-derives every rel32 stock target from its source address and signed displacement. Targets inside each game’s `.shr` move by the declared delta; external targets remain unmoved. The VV4 `0xCC02A` row has a derived moved target but lacks the expanded metadata field, so it remains an explicit ledger metadata gap/STOP rather than being silently filled.

The broad serializer evidence artifact contains stale raw file hashes for both ledger files on this specialist tip. The audit records the current raw and canonical-text pins and labels the legacy references `stale_raw_file_pin_stop`; it does not rewrite the existing artifact or either ledger. VV5’s current specialist digest is `A5DF…`; the corrected C342 integration digest is separately pinned as `14E460…` and is not claimed present here.

All native, stock-import, save/reload, offline-catch-up, failed-load, atomic rotation, stored-index, serializer, runtime-receipt, and player-receipt gates remain STOP. Checked-in evidence is empty, and publication is false.

```powershell
python scripts/validate_x45_expanded256_reference_audit.py
python -m unittest tests.test_x45_expanded256_reference_audit
```
