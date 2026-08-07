# Origins static playtest-readiness gate

Village Statistics audit
`7fe0a047706693d69c9b504f7a7b0b014280dee3` confirms that
Oldest Villager is a persisted lifetime maximum in all five games, not a
current-villager or memorial scan. Villagers Buried requires an earliest
successful skeleton pickup increment; known later record-release sites are
insufficient. Retroactive memorial initialization and expanded-256 walker
coverage remain ON HOLD.

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

## VV1/VV2 Origins containment

The VV1 and VV2 Origins feature records and both dependent village-wide
records are disabled and absent from catalog, GUI, CLI, dependency resolution,
Select All, and generated per-feature transparency. Their legacy Time Warp,
Cure, Running, doubler, and selected-villager actions are historical/STOP
evidence only and must not be launched, purchased, packaged, or emitted.

VV1 re-enablement requires rebuilding the companion resource with the exact
label `Time Warp - Advances 3 Villager Years`, removing or replacing stale Cure
resources, and proving confirmation, selected/world identity and funds
reacquisition, native mutation and postverification, one deduction only after
success, and truthful no-change/no-charge and partial-failure reporting. VV2
has the same gates plus root-cause repair for the reported Time Warp and Food
Point Doubler crashes after the purchased/success dialog. Golden Child, Gong
of Wonder, and Island Event outcomes remain native.

The isolated VV1 and VV2 command-7 Full Mastery candidates are separate from
these contained Origins records. They remain catalog-visible static candidates
for stock Collection Progression and Immediate Fixed, reject Expanded-256, and
remain runtime/player-confirmation pending.

## Village-wide Origins containment

All five legacy `vvN_origins_village_wide_upgrades` records are disabled and absent
from the catalog. Their commands 6/7/8 are bundled in one atomic payload, so
Running, Full Mastery, and Age 18 remain unavailable together until each
game's complete payload receives a GO gate. VV3's separately generated
command-6-only All Villagers Like Running source remains preserved but catalog-hidden, and
VV3Run2 is hard-withdrawn from playtesting under crash audit
`36f14702b938a6235230a3fd3e0c34328d3ac745`. The exact tested EXE/DLL pair
crashed on the status-2 no-change route. Static ABI and pointer checks pass,
the save snapshot and rotations show no saved preference overwrite, and the
fault instruction remains unknown. Do not package or test this feature until
a fresh crash/no-change gate is certified. It does not expose commands 7/8.
The exact withdrawn pair is EXE
`D81FB967C9DDE2448C40744356AE08BBADFA78930ABA004CEE5BE4025C65FBD0`
and DLL
`2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9`.
Static repair is not authorized without a runtime fault capture. Required
stock breakpoints are dispatcher `0x6DF040`, entry `0x6DF120`, status-2
`0x6DF206`, status test `0x6DF091`, pre-helper `0x6DF0D7`, helper
`0x4A3400`, and Like store `0x6DF3D7`; expanded equivalents are
`0x7B8040`, `0x7B8120`, `0x7B8206`, `0x7B8091`, `0x7B80D7`, and Like store
`0x7B83D7`. Capture the exception code/fault RVA, every general-purpose
register, ESP/return stack, all four counters, and `[EBX]` immediately before
the Like store; `[EBX]` must be `FFFFFFFF`.
VV4 audit
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

Preference-matrix audit
`f1555e295e828af2165ab0b7ea9f051ac9736418` fixes the exact logical
capacities at VV1 four Likes plus four Dislikes, VV2 62 plus 62, and
VV3/VV4/VV5 three plus three. Every slot is a signed DWORD and `-1` means
empty, but readers continue through the complete fixed bound rather than
treating `-1` as a terminator. Running is ID 38 in all five exact builds.
The PC VV2 Fastest Runner option can naturally create a duplicate Running
Like at `0x420D22`, `0x420D2B`, and `0x420D37`.

Command 6 remains ON HOLD for VV1, VV2, VV4, and VV5 under audit
`0311443fbd078e3adcabaf7e693199989ddb9db8` and evidence clarification
`a67e05247dc822306e1d5a514524cba388ab4d69`. Running ID 38 was verified
separately in each executable. VV1 persists four Like and four Dislike DWORD
slots, VV2 persists 62 of each, and VV3-VV5 persist three of each; all use
signed `-1` as empty. The disabled helpers are non-atomic, and VV1/VV2 scan
too few slots. A future helper must scan every fixed Like slot; if any contains
Running, it must make zero preference writes and preserve duplicate Running
Likes and every Dislike. Otherwise it must preflight the first physical `-1`
Like before removing dislikes and make no mutation when Likes are full. With a
destination, it inserts Running exactly once and clears every Running Dislike,
preserving unrelated slots and ordering. VV5 must reject
current faction `+0x1CEC != 0` before any preference access or count;
`+0x1CE1` is not a proved substitute. Four-counter bounded results,
no-op/no-charge recheck and rollback, ordinary/status eligibility, and
stock-plus-expanded composition remains ON HOLD.

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
approved the exact frozen artifact and its catalog dependency, but later
runtime audit `36f14702b938a6235230a3fd3e0c34328d3ac745` withdraws the
VV3Run2 playtest after an intermittent status-2 no-change crash. The old
944-byte payload remains forbidden and commands 7/8 remain absent.

VV1 audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` now
classifies that command as ON HOLD. It confirms five signed DWORD skills
`+0x3BC..+0x3CC`, preference `+0x3D0`, Master threshold 90, native cap 100,
and persistent 32-record save packing at stride `0x3D8`. The candidate uses
occupied `+0x28` and signed health `+0x344`, writes 90 without changing
preference, returns no counts, and charges through `state+0xA2FC` without a
changed-record preflight, no-charge result, recheck, or rollback. Preference/
title policy, distributed native side effects, creation/clone policy, strict
Golden Child/Event bypass, and placement/composition remain unresolved.

The isolated VV1 command-7-only Full Mastery candidate supersedes that historical
Stage-A status for stock modes. C76/D82/C83 independently recertified the exact
payload and four identity outputs against source commit
`2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94`; the candidate is catalog-enabled for
`collection_progression` and `immediate_fixed` only. Its active Origins/Cure base
SHA is `5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3`,
the isolated candidate SHA is
`3DB0D70ED5512D6A38765AA71B90DE4D9C3BD5BE30CD528C17A351413B28D06F`, and
uninstall returns byte-for-byte to the active base. Expanded-256 remains
fail-closed and runtime/player confirmation remains pending.

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
Expanded composition remains ON HOLD; the 43 previously omitted current-feature
relocations are declared in the static ledger, while runtime and player gates
remain open.

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

The former VV5 Full Mastery package commit `5e52be5e41b25b0f541c3c762e8caacc2dbd150b`
was HARD WITHDRAWN after an immediate startup auto-close. WER recorded
`c0000005` at VA `0x44FA20`: both emitted base-owned constructors omitted the
required thiscall `ECX` receiver before calling the stock routine. Certification
`8193629` is revoked. The corrected bundle assigns the allocated object to
`ECX` at both sites and was independently certified under `7970cd9`. M2 passed
startup and Full Mastery live testing. The disabled geometry candidate now uses
cached `Images\\btn_trophies.png`, the proven native resource `0x6A` (96x39), at local
`(137,2)` for both Tech and Detail, preserving event 13, `sub_401BD0`, and
`0x40C680` ownership; independent emitted-byte recertification remains
required.

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

VV2 Full Mastery command 7 is statically enabled and catalog-visible only for
stock Collection Progression and Immediate Fixed under independent emitted-byte
GO evidence `13f4341201fa7757d23f77c5c17602bbe7bbf21d`; runtime/player confirmation
remains pending. It is a repeatable Buy-only action with no Remove state. The
transaction uses five fresh manager/state acquisition boundaries, completes a
full dry run and confirmation before mutation, rechecks eligibility and funds,
and applies changed-only native skill writes to raise signed-DWORD skills to
exact 100. Native sub_44D4C0 runs exactly once globally after complete
exact-100 postverification. A fresh manager/state acquisition then derives Elder and
totem telemetry, including villagers left unmarked at the native 50-totem cap,
performs a fresh unsigned funds recheck, and makes the one 1,000,000-point
deduction. Commands 6 and 8, ownership, Remove, Gong, Island Events, and the
withdrawn VV2 Origins transport are not part of this candidate; Expanded-256
modes reject before output. If a native write succeeds but later
postverification fails, partial skill changes may remain because rollback is
not proved safe, but no Technology Points are deducted.

VV1, VV3, and VV4 doubler new purchases and repurchases remain unavailable
until their exact-build provenance gates are cleared. VV5 stock-layout Tech and
Food Doublers support purchase, zero-cost/no-refund Remove, and full-price
repurchase. In VV5 expanded-256 modes, both writer hooks are restored to native
bytes and new doubler purchases remain unavailable; owned Remove remains
available. Expanded composition is ON HOLD. The cited static current-feature
ledger is complete at 66 rows: 23 payload-internal absolute, 36 cross-section
rel32, and 7 external absolute `.shr` rows, including all 43 previously omitted
current-feature references, per disassembly commit
`8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb`. This is not runtime, save, catch-up,
or player evidence. VV5 native Time Warp, Island Event, and Barrel rows remain
unavailable because their Heathen-safe target paths are not yet proven.

VV3 Magic Level-1 audit `4c588ffd36765d750533fe9694f8fda5c8e82736`
confirms that Magic level 1 or higher contributes a deterministic flat `+1`
tech point to each completed research callback. It changes no research speed,
duration, base award, RNG probability/amount, or Research-skill gain. The
native order is base, optional quarter-base, Magic `+1`, timed `+1`, then an
independent RNG `+1`; ordinary and special/catch-up paths converge before
Magic. Collection duplicates and Island Events are separate producers. A
future Tech Doubler must double the complete eligible positive native sum once
after those additions and exclude Island Events. VV3 Tech Doubler purchase
remains unavailable because case 26 emits separate writer calls and no
provenance-safe post-sum hook or source tag is certified.

The matrix is intentionally catalog-driven rather than a hard-coded feature
list, so newly enabled game-scoped patches cannot silently escape the
composition checks. It does not modify manifests, executable payloads, saves,
prices, ownership behavior, or companion DLLs.
The isolated VV2 command-7-only Full Mastery implementation is statically
enabled and catalog-visible only for stock Collection Progression and Immediate
Fixed under independent emitted-byte GO evidence
`13f4341201fa7757d23f77c5c17602bbe7bbf21d`, with implementation/source bound
to `895340333d55273e599f2dce5ab0db42cbc6d0ab`. It sets only below-100 values
in the five native skill fields to 100. Native sub_44D4C0 runs exactly once
globally after complete exact-100 postverification. It then
reacquires fresh manager/state, derives fresh telemetry, rechecks unsigned
funds, and performs the single native deduction. Commands 6 and 8 remain
absent, both withdrawn VV2 Origins manifests remain disabled, Expanded-256
modes reject before output, and runtime/player confirmation remains pending.

The isolated VV4 command-7-only implementation is emitted-byte certified under
`91a01eba0dc561b1244184301837b7199868c490` and catalog-enabled. It validates
five ordered Float32 skills, raises only values below 100 through native
`sub_46AD80`, and deducts the unsigned one-million-point cost once through
native `sub_41E300` after the complete no-op/warning/final-recheck sequence.
Commands 6/8 and the legacy atomic village-wide record remain unavailable;
runtime/player confirmation is pending.

The isolated VV3 command-7-only Full Mastery implementation is independently
recertified for the exact stock executable under disassembly commit
`1e6ad7fd610d2fe9d80416fb218366ccd7d0656b`. It resolves record zero through
native `sub_45C840` against fixed current-save manager `0x0059E110` before the
initial dry run and again after OK, uses literal physical bound 150 for both
dry runs and commit, raises only below-100 skills through native `sub_455740`,
and calls native `sub_462500` once per changed villager. It is catalog-enabled
for `collection_progression` and `immediate_fixed` playtesting only. Both
expanded-256 modes reject it and remain ON HOLD; commands 6/8, raw skill
stores, ownership/Remove, and save-format changes remain absent.
