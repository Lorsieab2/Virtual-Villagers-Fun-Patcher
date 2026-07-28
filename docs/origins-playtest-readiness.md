# Origins static playtest-readiness gate

This document records the patcher's five-game composition matrix for the
current Origins catalog. For each supported game, the test selects every
enabled game-scoped optional patch, resolves prerequisites in dependency-first
order, and renders all four population modes against the exact stock
executable. It verifies every byte guard, feature owner, PE checksum, and
shared Origins companion hash while proving that the stock executable remains
byte-identical.

This is static composition/readiness only. It does not prove player-visible
runtime behavior, and runtime/player confirmation remains pending. The test
never launches a game and does not authorize packaging by itself.

## Village-wide Origins containment

All five `vvN_origins_village_wide_upgrades` records are disabled and absent
from the catalog. Their commands 6/7/8 are bundled in one atomic payload, so
Running, Full Mastery, and Age 18 remain unavailable together until each
game's complete payload receives a GO gate. VV4 audit
`628e0d9217b92b9cd695655842b09d74689a0238` proves the direct Full Mastery
stores bypass eight native mutations. VV5 audit
`02581c8f518e27ebd5fc7d2972db5597ab08ed35` records unresolved counter,
eligibility, no-change, inheritance, and expanded-layout requirements. VV3 is
ON HOLD under audit `089957227c0db6a4c3128045519ffa27b201a00e`:
its five signed DWORD skills are `+0xEAC..+0xEBC`, mastery begins at 88, the
native maximum is 100, and native all-five evaluation uses award ID 4. The
candidate direct 90 stores are not full mastery and bypass that evaluation;
zero-change/no-charge behavior, creation/inheritance, and placement remain
unresolved. VV1 is not certified.

The disabled diagnostic payload bytes are retained in their manifests but are
not rendered into stock or expanded outputs. This catalog containment does not
touch existing save ownership or fields, force-clear anything, or issue a
refund. Base Origins remains independently composable for VV1, VV3, VV4, and
VV5; VV2 base Origins remains separately contained.

## VV2 Origins containment

VV2 Origins is currently unavailable and must not be selected. A player
reported that both Time Warp and Food Point Doubler crash immediately after
their purchased/success dialog is displayed. This records the observed trigger
only; it does not infer whether the charge or action persisted. Both
`vv2_enable_origins_exclusive_features` and dependent
`vv2_origins_village_wide_upgrades` are disabled pending root-cause repair.
Unrelated VV2 optional features remain independently selectable.

The crash audit also found that the VV2 Origins builder confused `.shr` raw
offsets with virtual addresses, displacing several helper/header references by
`0x2000`. This is a hard re-enable blocker, but it is not certified as the
complete explanation for both crashes; no repair is attempted here.

VV1, VV3, and VV4 doubler new purchases and repurchases remain unavailable
until their exact-build provenance gates are cleared. VV5 stock-layout Tech and
Food Doublers support purchase, zero-cost/no-refund Remove, and full-price
repurchase. In VV5 expanded-256 modes, both writer hooks are restored to native
bytes and new doubler purchases remain unavailable; owned Remove remains
available. Expanded composition is ON HOLD: the 75-row relocation ledger covers
32 rows and leaves 43 references (36 cross-section rel32 and 7 external
absolute `.shr` pointers) outside the certified set, per disassembly commit
`8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb`. VV5 native Time Warp, Island Event,
and Barrel rows remain unavailable because their Heathen-safe target paths are
not yet proven.

The matrix is intentionally catalog-driven rather than a hard-coded feature
list, so newly enabled game-scoped patches cannot silently escape the
composition checks. It does not modify manifests, executable payloads, saves,
prices, ownership behavior, or companion DLLs.
