# VV3 Expanded-256 capacity candidate

`scripts/build_vv3_expanded_256_capacity.py` builds the Virtual Villagers 3
Expanded-256 capacity candidate from the exact local stock executable
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.

The composition is deliberately limited to the current Expanded-256 relocation
and capacity ledger, a zero-filled non-executable reserved PE section, the
reviewed static serializer/reader page, and the guarded atomic writer. It does
not install the optional Time Warp page or its hooks.

This is a static/package candidate, not a safety claim. The source contracts
still mark native output, runtime, player, and publication as STOP. A player
must test startup, new village, stock-save import, reload, offline catch-up,
save/exit/reload, and population checkpoints through 256. Any crash report
must include the exception code, fault RVA, registers, caller return address,
stack, mode, lifecycle phase, and population count.
