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

VV1 audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` now
classifies that command as ON HOLD. It confirms five signed DWORD skills
`+0x3BC..+0x3CC`, preference `+0x3D0`, Master threshold 90, native cap 100,
and persistent 32-record save packing at stride `0x3D8`. The candidate uses
occupied `+0x28` and signed health `+0x344`, writes 90 without changing
preference, returns no counts, and charges through `state+0xA2FC` without a
changed-record preflight, no-charge result, recheck, or rollback. Preference/
title policy, distributed native side effects, creation/clone policy, strict
Golden Child/Event bypass, and placement/composition remain unresolved.

VV5 All Villagers are 18 audit
`aaddf71797c28f37b0cc1f5728e567c0601a05aa` confirms age DWORD `+0x1B8C`,
20 units per year, and age 18 value 360. Native ordinary/offline aging uses
increment writer `0x46F7F0`, refreshes consumers, and can update the
oldest-villager statistic; save/restore persists the `0xA8` age object. The
candidate raw store bypasses that route and differs from the selected-age
candidate's related `+0x1C3C`/nonzero `+0x1C4C` adjustments. It tests active,
positive health, current believer `+0x1CEC == 0`, and an unproved extra
`+0x1CE1 == 0` exclusion. Its generic transaction charges no-op/already-18
cases and returns zero results. Nursing timer and nursing/pregnancy state must
never change, but the raw helper is not proved to satisfy that semantic rule.
Expanded composition remains blocked by 43 missing relocations.

VV4 All Villagers are 18 audit
`ab404b0c5e80cab4d327de9a51069e6e3529df27` covers the exact 929,792-byte
build, SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.
It confirms age `+0x1B8C`, 20 units per year, age 18 value 360, detail refresh
`sub_43BA80`, native increment `sub_465F10`, offline call `0x46663B`, oldest
statistic `dword_4D6E00`, and persistence through
`sub_45DB30`/`sub_45DBE0`. The candidate raw store bypasses native
stat/transition handling; the selected-age raw store is not native proof.
Status `+0x1CC7`, no-op charging/zero result/rollback, future birth/clone/Event
exclusions, and stock-plus-expanded placement remain unresolved.

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

VV2 Full Mastery audit `60f649bf90b55dea3a6856d949e123bd79808782`
also keeps command 7 ON HOLD. It confirms five signed DWORD skills
`+0x7E4..+0x7F4`, job preference at `+0x7F8`, Master threshold 88, native
maximum 100, persistent 256-record save/load at stride `0xE48C`, and the
candidate's active `+0x30`/health `+0x52C` iteration. The candidate writes 90
and charges through a generic transaction without changed-record counting,
zero-change/no-charge handling, result detail, or rollback. No complete native
all-five side-effect route, creation/inheritance/Silver Mirror closure, or safe
transport/placement is proved. Gong and every Island Event route remain
entirely native.

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
