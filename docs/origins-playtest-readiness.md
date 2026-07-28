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

All five legacy `vvN_origins_village_wide_upgrades` records are disabled and absent
from the catalog. Their commands 6/7/8 are bundled in one atomic payload, so
Running, Full Mastery, and Age 18 remain unavailable together until each
game's complete payload receives a GO gate. VV3's separately generated
command-6-only All Villagers Like Running feature is the sole exception and
does not expose commands 7/8. VV4 audit
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

Command 6 remains ON HOLD for VV1, VV2, VV4, and VV5 under audit
`0311443fbd078e3adcabaf7e693199989ddb9db8` and evidence clarification
`a67e05247dc822306e1d5a514524cba388ab4d69`. Running ID 38 was verified
separately in each executable. VV1 persists four Like and four Dislike DWORD
slots, VV2 persists 62 of each, and VV3-VV5 persist three of each; all use
signed `-1` as empty. The disabled helpers are non-atomic, and VV1/VV2 scan
too few slots. A future helper must skip an already-running villager entirely,
preflight an empty Like before removing dislikes, and make no mutation when
Likes are full. It must preserve unrelated slots and ordering. VV5 must reject
current faction `+0x1CEC != 0` before any preference access or count;
`+0x1CE1` is not a proved substitute. Four-counter bounded results,
no-op/no-charge recheck and rollback, ordinary/status eligibility, and
stock-plus-expanded composition remain open.

VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833`
and `1d9a39da078806aa940e4774a9068956e88347bc` close ID 38, its three
Like/three Dislike DWORD arrays at `+0xFB4..+0xFC8`, sentinel `-1`, stride
`0x1F8C`, 150/256 bounds, persistence, atomic ordering, four result counters,
and dry-run/no-charge/final unsigned recheck requirements. They do not lift
ON HOLD: commands 6/7/8 share the
944-byte `0x7B820` payload and `0x7B840/0x47B840` entry; `0x582644`
precharges while `0x7B7A0` is only a header check; the current three-counter
128-byte ABI lacks `granted`; hooks `0x6547D`/`0x65640` and payload `0xA3180`
mix unrelated Origins code; command-6-only UI guards and a complete appended
section relocation/uninstall/all-patch ledger do not exist.

Second resolution commit `d1cdeb67362487c1d577e3abae03c9424fd04fb9`
specifies the VV3 seven-row/ID-1006 exact-command UI, 16-byte four-counter
structure, four-line `char[256]` result (201-byte maximum at bound 256),
unsigned one-million dry-run/no-charge/recheck/deduct/commit transaction, and
zero-cost/no-refund non-reversing removal with repurchase. It also records
stock and expanded PE placement facts.

Semantic closure `b9c7a22eb1d7cceae25160ce4d360621e7485625` proves
`+0xE94` is a dormant retained totem-render selector, not live eligibility:
nonzero selects ID 573 **`'s totem`**, while zero plus signed health `<= 0`
selects ID 574 **`'s remains`**. Eight readers and one zero-only writer are
exhaustive; construction, new/clone/Event/puzzle/template paths have no
nonzero producer. All 64 active records in the corrected readable save corpus
and 125 active records in a 150-slot live scan were zero; CE tables do not
label the byte. Running eligibility is therefore only active `+0xF10 != 0`
and signed health `+0xE78 > 0`. VV2 `+0x558` memorials and VV5 Heathen
totems are distinct. Stage C now supplies a corrected disabled command-6-only
base extension, guarded slot, transaction body, rebuilt `@20` companion, and
stock/both-expanded render and uninstall fixtures under `data/candidates/`.
Those bytes address Sol finding `f73625582adae714473068c272b90af91a57d945`.
Stage C certification `79b122bf0850f18a101db9fb86b40407dd2db573`
approves the exact frozen artifact, which is now catalog-visible with its base
Origins dependency in stock, immediate, expanded, and expanded-progression
modes. Runtime/player confirmation remains pending. The old 944-byte payload
remains forbidden and commands 7/8 remain absent.

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

Corrective VV3 All Villagers are 18 audit
`295b5d1e228c501d0e14b1f869f11b0caa3a07bd` covers the exact 831,488-byte
build, SHA-256
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
Live evidence changed `+0xDC4` 372->360, immediately displayed age 18,
survived save/reload, and natively advanced to 361; `+0xE74` remained 372 and
`+0xE8C` remained zero. `sub_45F3E0` passes `+0xDC4` to `sub_45C640`.
`+0xE74` is the nursing/conception-age/lifecycle timestamp and must remain
unchanged. `sub_45FFE0` runs hidden food/health/mortality/reproduction steps
only while `+0xE74 < +0xDC4`; lowering target age below the timestamp pauses
those steps until target age advances beyond it. Target-only writing is not
inherently invalid, but final GO is absent: exact command-8 transaction/result
bytes and collision-certified stock plus both-expanded PE manifests remain
unbuilt.

VV2 All Villagers are 18 audit
`bd6ce555a9a197450aab7133c0a87b36fbfc6899` covers exact 724,992-byte build
SHA-256 `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.
It confirms target/display age `+0x530`, processed age `+0x534`, 20 units/year,
and age 18 value 360. Native `sub_43B690` advances target at `0x43B8FD`,
updates oldest statistics, runs life catch-up, then increments processed age at
`0x43C09A`. Command 8 writes only target age and desynchronizes the pair.
Pregnancy writer `sub_44B980` stores processed age in `+0x540`; delivery uses
`marker + 40 < processed age`. The selected-age candidate rewrites both ages
and nonzero marker to 318, violating nursing-state preservation. Scan
eligibility omits `+0x558`; transaction precharges and returns zero without
no-op refusal/recheck/rollback. Love Note `0x422006`, Gong `0x44EB3E`, and
Silver Mirror `0x4217F9` remain separate native paths. The withdrawn
non-executable `.shr` transport remains independently blocked by its `0x2000`
VA error.

The future Full Mastery contract is true native maximum 100 for every skill:
five in VV1–VV4 and six in VV5. Master thresholds or candidate value 90 are
not sufficient. This is a planning/readiness requirement only and authorizes
no contained command.

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
