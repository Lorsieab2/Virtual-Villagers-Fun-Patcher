# Virtual Villagers Fun Patcher — Transparency Coverage

This document is generated from the patch manifests. It is the project-level description of the differences the patcher can request; the per-output `VVFP Transparency Log.txt` is the authoritative record of the exact bytes and files used for one output.

## Automatic changes (every output)

Every output applies the selected population mode. No Population Increase preserves the stock cap, progression, and population-allocation behavior. The collection-progression mode preserves the supported game's collection/bonus behavior while changing its declared maximum according to the manifest. The immediate-fixed mode keeps the fixed maximum and applies the guarded population-safety edits. No game is launched by the patcher, so runtime/player confirmation remains pending.

Available population modes: No Population Increase, Collection Progression Max Pop, Immediate Fixed Max Pop.

## Optional-patch chooser catalog

The desktop chooser presents game-scoped optional patches under the five manifest titles in this fixed order: A New Home, The Lost Children, The Secret City, The Tree of Life, and New Believers. Within each title, entries sort by case-folded display name and then patch ID. Unknown or all-games entries appear under a final `Shared / All Games` header. Checkbox variables remain keyed by patch ID; Select All, Deselect All, dependency closure, and persisted selections operate on those same variables. This is presentation-only: it changes no executable bytes, save fields, companion DLLs, or game behavior.

## Origins doubler evidence boundary

Food Point Doubler changes only the positive food-source delta added to village stores. Tech Point Doubler changes only the positive earned-tech delta at its certified source boundary. Each eligible source value is doubled once; zero and negative deltas remain native, and native writers continue their normal storage/statistics updates using the doubled amount. No doubler changes deductions, initialization, ownership, counters, or unrelated resources. The explicit tech exclusions are Golden Child in VV1, Island Events in every game, Gong of Wonder in VV2, and Duplicate Collectibles wherever that route is present. VV5 stock-layout Tech and Food corrections are implemented with exact-build static proof. The current exact-build boundaries and pending/STOP statuses are recorded in `docs/doubler-composition-audit.md`; return-address checks alone are not treated as exhaustive provenance proof.

VV3 Magic Level-1 audit `4c588ffd36765d750533fe9694f8fda5c8e82736` exhaustively enumerates nine Magic-index reads and finds only one research consumer: sub_458DB0 case 26 getter call 0x4593DC. Magic level 1 or higher contributes a deterministic separate +1 tech writer call after the base and optional quarter-base awards and before timed and independent RNG additions. It changes no research speed, duration, base award, RNG probability/amount, or Research-skill gain. Ordinary and special/catch-up research converge before Magic; collection duplicates and Island Events are explicit Tech Doubler exclusions. The Tech Doubler changes only an eligible positive earned-tech source delta at the positive-writer boundary; separate Magic components and no-source paths remain native.

## Birth Control scope

The exact-build VV4/VV5 breeding audit confirms that both games already provide the requested VV4-style Birth Control/Breeding behavior natively. VV4 and VV5 are untouched no-patch references; no Birth Control runtime bytes are offered, applied, or reserved for either game. VV1, VV2, and VV3 now have separate exact-build records with static verification complete and runtime/player confirmation pending.

Every current or future Birth Control, pregnancy, or Embracing patch is limited to the exact ordinary manual, autonomous, or catch-up route named by its game-specific evidence. All Island Event pregnancy, birth, and child outcomes remain completely native and bypass patched age, sex, preference, eligibility, conception, pregnancy, delivery, capacity, RNG, messages, statistics, and state writes. Every VV2 Gong of Wonder outcome has the same complete exclusion. These are control-flow/provenance exclusions, not result- or amount-based exceptions.

VV1 exact-build audit `c8d268d` rejects its former byte proposal: `0x3DBBE` is the stock food>=400 gate rather than an age predicate, `0x458D0` and `0x45930` are live instruction interiors, and `0x56740` is uncertified. The active `vv1_birth_control` record instead owns a `.vv1bc` executable page at raw `0x8E000` / VA `0x490000`, hooks the manual route at `0x3DD03`, the action-9 writer-reaching scans at `0x46E96` and `0x47084`, and the planner at `0x477FA`, and preserves the stock lower bounds while adding only candidate upper bounds. Catch-up reuses that route; direct event births and pending delivery remain native.
VV3 exact-build feature `vv3_birth_control` changes only the five repeated initiator-age blocks at `0x5CE74`, `0x5CF35`, `0x5CFFC`, `0x5D0C0`, and `0x5D187`. Each native candidate `360..999` check remains; only the ordinary action-13 selector's duplicate initiator upper rejection is removed. The native manual handler at VA `0x4584B0`, direct event births, pending delivery, clone paths, and other special producers remain native.

VV2 exact-build feature `vv2_birth_control` is limited to the two complete 40-byte writer-reaching opcode-12 candidate scans at file offsets `0x6488D` and `0x64A8F`, based on disassembly commit `74778bd6a7d3a17dd990636cf6d4e769466800c6`. It preserves candidate sex in EDX and rejects an already-loaded candidate age in EAX at 1000 or above. The stock manual carrier/female-only gate and lack of a male upper-age gate remain unchanged. Love Note call `0x22006`, Gong life-grant call `0x4EB3E`, Silver Mirror clone call `0x217F9`, pregnancy writer `0x4B980`, pending-delivery path, chooser scoring, planner, saves, RNG, resources, statistics, and all direct event/Gong routes remain native. This does not claim broader breeding parity.

## VV1/VV2 Origins playtest boundary

The current selectable VV1/VV2 Origins records are the complete Tech and Villager Detail menus plus their dependent Village-Wide menus. Historical standalone Full Mastery records are retained as evidence only: they are not catalog-selectable and are excluded from release packaging. Static verification is complete; runtime/player confirmation remains pending. Native unrelated handlers, including Golden Child, Gong of Wonder, and Island Events, remain outside the custom routes.

Historical VV2 standalone Full Mastery records are retained as evidence only and are not selectable. The current VV2 Origins menus own both Village-Wide and Detail-screen Full Mastery, target exact skill value 100, skip inactive/dead/totem records, and use the verified native skill writer where applicable. The native mastery evaluator address remains unclaimed pending proof. The reported VV2 Time Warp and Food Point Doubler crash occurred immediately after the purchased/success dialog; runtime/player confirmation remains pending.

Superseded historical evidence (withdrawn; not current behavior): VV1 Full Mastery audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` confirms five contiguous signed DWORD skills at +0x3BC..+0x3CC, job preference +0x3D0, Master threshold 90, native cap 100, and persistent 32-record save packing at stride 0x3D8. The former candidate iterated occupied +0x28 and positive signed health +0x344, wrote 90 through raw stores, returned no changed count, and used state+0xA2FC for a one-million-point transaction without preflight, commit recheck, no-charge no-op result, or rollback. Those 90-point/raw-store semantics and unresolved-route findings are withdrawn and do not describe the current enabled candidate.

### VV1 standalone Full Mastery status

The standalone VV1 Full Mastery candidate and its individual child are retained as historical evidence only and are no longer catalog-selectable or included in the release. The current VV1 Origins feature provides the required Detail-screen and Village-Wide Full Mastery rows, with exact 100 targets and runtime/player confirmation pending.

VV5 All Villagers are 18 audit `aaddf71797c28f37b0cc1f5728e567c0601a05aa` confirms signed age DWORD +0x1B8C, 20 units per displayed year, and age 18 value 360. Native detail refresh, ordinary/offline increment writer 0x46F7F0, oldest-villager statistic update, and persistence of the 0xA8 age object are mapped. The disabled candidate raw store bypasses that native route and differs from the selected-age candidate's related +0x1C3C and nonzero +0x1C4C writes. It tests active +0x1CD4, positive health +0x1C40, current-believer faction +0x1CEC==0, and an unproved extra +0x1CE1==0 exclusion. Its 0x51D5F8/native-tech-writer transaction charges no-op and already-18 cases, returns zero results, and has no tied recheck or rollback. Nursing timer and nursing/pregnancy state must never change; this raw helper is not proved to satisfy that semantic rule. The current-feature relocation ledger is statically complete at 66 rows (23 payload-internal absolute + 36 cross-section rel32 + 7 external absolute), including 43 formerly omitted references; Expanded composition, runtime, save, catch-up, and player gates remain ON HOLD.

VV4 All Villagers are 18 audit `ab404b0c5e80cab4d327de9a51069e6e3529df27` covers exact 929,792-byte build SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220 and confirms signed age +0x1B8C, 20 units/year, age 18 value 360, detail refresh sub_43BA80, native increment sub_465F10, offline call 0x46663B then oldest statistic dword_4D6E00, and persistence through sub_45DB30/sub_45DBE0. The disabled stride-0x2E3C candidate takes a 150/256 bound and tests active +0x1CC4, status +0x1CC7==0, and positive signed health +0x1C40. Its raw store bypasses native statistic/transition handling; a selected-age raw store is not native proof, and status semantics remain incomplete. The unsigned 1,000,000-point 0x4D6F88/sub_41E300 transaction charges no-op/all-already-18 cases, returns zero results, and has no rollback. Processed age +0x1C3C, nursing/pregnancy companion +0x1C4C, pending baby count, and unrelated fields must never change. Future birth/clone/Event exclusion and full stock-plus-expanded placement/composition remain unresolved.

Corrective VV3 All Villagers are 18 audit `295b5d1e228c501d0e14b1f869f11b0caa3a07bd` covers exact 831,488-byte build SHA-256 8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503. Live evidence changed target/display age +0xDC4 from 372 to 360, immediately displayed age 18, survived save/reload, and natively advanced to 361; nursing/conception-age/lifecycle timestamp +0xE74 stayed 372 and pregnancy +0xE8C stayed zero. sub_45F3E0 passes +0xDC4 to sub_45C640. +0xE74 must never be synchronized by the patch. sub_45FFE0 runs hidden food, health, mortality, and reproduction life steps only while +0xE74 < +0xDC4; lowering target age below the unchanged timestamp pauses those steps until target age advances beyond it. A target-only write is not inherently invalid, but this is not final GO: exact command-8 transaction/result bytes and collision-certified stock plus both-expanded PE manifests remain absent.

VV2 All Villagers are 18 audit `bd6ce555a9a197450aab7133c0a87b36fbfc6899` covers exact 724,992-byte build SHA-256 46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677 and confirms signed target/display age +0x530, processed age +0x534, 20 units/year, and age 18 value 360. Native sub_43B690 advances target at 0x43B8FD, updates the oldest statistic, runs full life catch-up, then increments processed age at 0x43C09A. Command 8 writes only target age and desynchronizes the pair. Pregnancy writer sub_44B980 stores processed age in +0x540 and delivery requires marker+40<processed; the selected-age candidate writes both ages to 360 and nonzero +0x540 to 318, violating nursing-state preservation. Its stride-0xE48C 256-slot scan checks active +0x30/health +0x52C but omits +0x558, while state+0x2EADC precharges with zero results and no no-op/recheck/rollback. Love Note 0x422006, Gong 0x44EB3E, and Silver Mirror 0x4217F9 remain separate native paths without claiming complete origin classification. The withdrawn non-executable `.shr` transport retains VAs 0x2000 below the actual mapping.

The future Full Mastery contract requires true native maximum 100 for every skill: five skills in VV1-VV4 and six in VV5. Master thresholds and candidate value 90 are not Full Mastery. This planning/readiness requirement does not authorize any contained runtime command.
VV4 Full Mastery UI Playtest 3 is HARD WITHDRAWN and both its base and individual Full Mastery records are catalog-hidden after a 0xC0000005 crash at RVA 0x89E0C / VA 0x489E0C. The individual-menu result calls at 0x4897CA and 0x489ABB incorrectly targeted the show-menu epilogue at 0x489573 instead of the exact 54-byte result helper at 0x489ACA/file 0x89ACA; its `ret 8` consumed the result-message pointer as the return address. The disabled repair candidate installs the guarded helper in a 64-byte zero cave and retargets both calls. Individual Full Mastery remains STOP because its command still lacks the complete native exact-100 transaction, while all-villager command 7 is separately withheld pending D25 recertification. The native trophy UI repair, Cure containment, unrelated features, and Expanded-256 ON HOLD are unchanged.

The former VV5 Full Mastery package commit `5e52be5e41b25b0f541c3c762e8caacc2dbd150b` was HARD WITHDRAWN after an immediate startup auto-close. WER reports APPCRASH `c0000005` at VA `0x44FA20`, whose stock first instruction `8B09` dereferences the thiscall receiver in ECX. The emitted base Origins Tech and Detail constructors called this routine after allocation without assigning the new object to ECX. Certification `8193629` is revoked. The corrected bundle assigns `ECX=EDI` before both calls and was independently certified under `7970cd9`; M2 passed startup and Full Mastery live testing. That withdrawn historical note used resource identifier `0x53`; it is superseded by the current exact VV5 geometry contract, which binds the native cached `Images\btn_trophies.png` resource `0x6A` (96x39) at local `(137,2)` for both Tech and Detail, preserving event 13, `sub_401BD0`, and `0x40C680` ownership; independent emitted-byte recertification remains required.

## All Villagers Like Running evidence boundary

Cross-game audit `0311443fbd078e3adcabaf7e693199989ddb9db8`, evidence clarification `a67e05247dc822306e1d5a514524cba388ab4d69`, and final preference matrix `f1555e295e828af2165ab0b7ea9f051ac9736418` place command 6 independently ON HOLD for VV1, VV2, VV4, and VV5 while fixing the logical arrays: VV1 four Like plus four Dislike signed DWORDs, VV2 62 plus 62, and VV3-VV5 three plus three. Signed -1 is empty but never an early terminator; readers scan the complete fixed bound. Running ID 38 was code-confirmed separately in each executable. PC VV2 Fastest Runner option 2 can naturally create duplicate Running Likes through 0x420D22, 0x420D2B, and 0x420D37. The disabled legacy helpers violate the required per-villager atomic order, and VV1/VV2 inspect too few slots. Any already-Running Like must skip the entire villager with zero preference writes, preserving duplicate Likes and every Dislike. Otherwise the first physical -1 must be proved before removing any Running Dislike; full Likes means no mutation; with a destination, insert once and clear every Running Dislike while preserving unrelated slots and ordering. VV5 must reject current faction +0x1CEC != 0 before any preference read/count, while +0x1CE1 is unsafe and unproved. Required future lines are exactly `Skipped over X villagers. Reason: already likes running` and `Removed running dislike from X villagers`; the proposed full-slot line remains future-only pending capacity proof. The main Official LDW Cheat Tables is the primary vanilla-name set; Official LDW Cheat Tables  (Backup!!) backs up Main for recovery/version comparison. Official LDW Cheat Tables - Copy is strong player-confirmed runtime evidence used with renamed/copied base-game executables whose filenames contain - Copy or a variation; translating its addresses still requires fingerprinting the underlying executable and accounting for process/module-name-dependent Cheat Engine scripts. Exact executable evidence controls.

VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833` and `1d9a39da078806aa940e4774a9068956e88347bc` record historical static ID 38, three Like plus three Dislike DWORD slots at +0xFB4..+0xFC8, sentinel -1, stride 0x1F8C, supplied 150/256 bounds, and a proposed future transaction contract. These static facts and legacy emitted bytes do not prove native selected-index/resolver, preference read/write, notification, deduction, or rollback ABIs. Its result lines remain future-only. At that audit stage +0xE94 semantics were still open. Commands 6/7/8 occupy one forbidden 944-byte atomic payload at file 0x7B820 with shared entry 0x7B840/VA 0x47B840; the legacy precharge and three-counter ABI remain non-authoritative for the current three-Like/three-Dislike contract.

VV3 second resolution `d1cdeb67362487c1d577e3abae03c9424fd04fb9` specified every architecture item while leaving naturally nonzero +0xE94 as its then-open semantic gate. Exactly eight direct readers exist at 0x455993, 0x4568A3, 0x45C9AA, 0x468D4C, 0x469081, 0x46915C, 0x4692C8, and 0x4697EF; sole direct writer 0x45F2B1 writes zero during retirement/reset. Save/load/copy preserve it, no direct nonzero writer is found, and strong player-confirmed CE tables do not label it. The specified hooks 0x6547D/0x65640 use a Running-only seven-row state, maximum ID 1006, exact command==6 dispatch, 16-byte four-counter structure, and exact lines `Granted Running to %u villagers`, `Skipped over %u villagers. Reason: already likes running`, `Skipped over %u villagers. Reason: all like slots are occupied`, and `Removed running dislike from %u villagers`; at bound 256 they require at most 201 bytes including CRLF/NUL, fitting char[256]. Its former owned/removable transaction model is revoked; current corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` requires repeatable Buy with no ownership-bit access. Stock PE is ImageBase 0x400000, alignments 0x1000/0x1000, five sections, SizeOfHeaders 0x1000, SizeOfImage 0x2DF000, checksum zero, file end 0xCB000, with one section-header slot; expanded moves .shr/.rsrc to 0x3A1000/0x3A2000 and SizeOfImage to 0x3B8000 across 1,263 guards.

VV3 semantic closure `b9c7a22eb1d7cceae25160ce4d360621e7485625` identifies +0xE94 as a dormant retained per-villager totem-render selector, not a live eligibility discriminator. At 0x468D4C, nonzero selects localization 573, exact suffix `'s totem`; zero with signed health <= 0 selects 574, `'s remains`. The eight readers and sole zero writer are exhaustive; constructors, new/clone, Event, puzzle, and template paths have no nonzero producer. The corrected readable save corpus had 64 active records all zero, and a live 150-slot scan had 125 active records all zero; strong player-confirmed CE tables contain no E94 label. Running therefore uses only active +0xF10 != 0 and signed health +0xE78 > 0. VV2 +0x558 memorials and VV5 Heathen totems are separate. The only remaining ON HOLD boundary is deterministic command-6-only extension/transaction bytes and collision-certified stock/expanded PE manifests. The old 944-byte commands 6/7/8 payload remains forbidden because it precharges, exposes commands 7/8, lacks granted, and uses the wrong callback ABI; injection bytes remain withheld for implementation, not E94 semantics.

VV3 Running is catalog-hidden and VV3Run2 is hard-withdrawn from playtesting under crash audit `36f14702b938a6235230a3fd3e0c34328d3ac745`. The exact tested EXE/DLL pair crashed on the status-2 no-change route. Static ABI and pointer checks pass, save snapshot/rotation evidence shows no saved preference overwrite, and the fault instruction remains unknown. Do not package or test it until a fresh crash/no-change gate is certified. Corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` defines a repeatable Buy action with no ownership-bit access. Base Origins owns the `.vvrun` page and guarded no-op slot; commands 7/8 remain absent. The corrected no-op slot SHA-256 is 42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3, the Running slot SHA-256 is 3F8F3BD7FD6C1BA8D8517539581D96F8D7B14D3BF959C74157FF970E432E5B13, and the unchanged companion exposes `ShowOriginsVillageWideResult@20` while retaining its existing exports. Replacement runtime testing is pending. Persistent fields are serialized/restored but remain legitimately mutable by later native aging, work, events, catch-up, and other game mechanics; the patch gate is immediate write preservation, save roundtrip, and noninterception of native future writers.

## Origins village-wide atomic-payload playtest boundary

The five current `vvN_origins_village_wide_upgrades` records are the sole selectable Village-Wide menu routes. Commands 6, 7, and 8 share one guarded payload after each matching base Origins dependency. Each row is a 1,000,000-tech-point buy action; static generation never alters save ownership or issues refunds. Historical standalone Full Mastery and individual Full Mastery records are not selectable and are not released.

## VV3 Full Heal / Cure All candidate

The VV3 Full Heal / Cure All candidate is disabled, catalog-hidden, and blocked by its withdrawn historical Running dependency. Its implementation provenance is recorded at `49595a75b65cd0561811593ba19825239ec97dde` with parent `38510cc21b7cd322a52fbabc936794dfc8601ccc`; independent static D209/C213 reports do not authorize catalog exposure or runtime-ready use. This generated disclosure is sourced from its authoritative candidate manifest.
- Partial-write disclosure: If native writes begin and a later write or postverification fails, earlier verified health, sickness, or People Cured effects may remain. No tech points are deducted on that failure, but complete rollback of native side effects is not claimed.

## VV3 Grant Running containment

The historical VV3 selected-villager Grant Running record is withdrawn and catalog-hidden. Its Likes-only helper never inspects or clears Running Dislikes (+0xFC0/+0xFC4/+0xFC8), so it is not exposed or composed; prior emitted bytes and packages remain immutable evidence.

The revised three-Like/three-Dislike candidate is disabled/catalog-hidden and emits no output. Its contract snapshots all Like and Dislike slots, preserves duplicate Likes, clears every Running Dislike, and writes only the first physical empty Like when no Running Like exists. Native preference side effects and a safe composed command-1/command-2 dispatcher remain unproved, so the candidate is STOP/runtime-pending. MessageBoxA accepts only EAX==1 (IDOK); EAX==2 and every other result are no-write/no-charge.

### VV4 Full Heal / Cure All candidate (disabled)

The VV4 `Full Heal / Cure All` candidate is disabled and catalog-hidden. It is bound to stock SHA-256 `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` and the certified VV4 Full Mastery parents for Collection Progression and Immediate Fixed only. Production composition resolves the complete dependency-first chain `vv4_complete_scales_golden_fish` -> `vv4_enable_origins_exclusive_features` -> `vv4_full_mastery_all_stage_a_candidate` -> `vv4_write_village_statistics`; the resulting pre-Full-Heal executables are pinned to the certified Collection and Immediate hashes. Its contract enumerates physical indices 0..149 through the native resolver, counts overlapping eligible sickness and health 1..99 records, confirms both predicted counts for 30,000 tech points, rechecks state and funds, clears sickness, restores partial health through the native setter, postverifies exact health 100/sickness 0, and deducts once through ECX=0x4D6F88/call 0x41E300. The candidate-owned companion is `VVFP Origins Icons.dll`, a deterministic structural RT_DIALOG 201/203 repack (SHA-256 165F327783DFECAB4C42DB28D6F926BCA46397F725F036BFC367BB659384C0AC, 298,496 bytes); it clones parent items 20..24, inserts the native five-item command-5 row before item 25, adds the ID 1005 Buy control and real RT_ICON 46..49 / RT_GROUP_ICON 110 artwork, updates the resource-directory size to 0x33800, and preserves the `Origins Upgrades` caption, dialog 202, exports, code, and non-resource bytes. People Cured is the separate [0x4D6DF0] statistic. Every no-charge route includes `No tech points have been deducted.` Expanded-256 and unknown compositions reject before output. The exact VV4 command-5 detour and `.vv4hc` page remain pending independent disassembly; existing Full Mastery UI/runtime bytes and the withdrawn legacy Cure route are unchanged.

## Virtual Villagers - A New Home

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - A New Home.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 17 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Birth Control (`vv1_birth_control`)

Applies the requested VV4-style ordinary-route boundary to the exact VV1 build. Manual pairing rejects only a category-2 carrier at internal age>=1000; the two action-9 writer-reaching scans and the planner reject only scanned candidates at internal age>=1000; initiator males and older autonomous initiators retain no upper-age ceiling. Direct event births and pending delivery remain native.

- Behavior changes: The manual pairing hook at file offset 0x3DD03 routes through an owned .vv1bc page and rejects only the category-2 carrier participant at internal age>=1000. The action-9 writer-reaching scans at 0x46E96 and 0x47084 retain their stock candidate and initiator lower bounds while adding only a candidate upper bound. The planner scan at 0x477FA adds only a candidate upper bound before the stock initiator lower-bound check.
- Explicit non-changes/exclusions: No male upper-age gate is added. The existing candidate sex/category checks, writer calls, chooser, planner action dispatch, pregnancy writer, delivery, save format, RNG, fertility, capacity, messages, and statistics remain native. Direct event-created births, pending delivery, and every route outside the named ordinary manual/planner/action-9 boundaries remain native.
- Dependencies: none
- Evidence status: implemented from exact-build disassembly; static verification complete, runtime/player confirmation pending
- Guarded executable edits: 4; every edit has an exact purpose and before/after guard in the manifest.

#### Builder Action Fixes (`vv1_builder_action_fixes`)

Villagers whose selected job is Building try the stock construction dispatcher at every food level, while autonomous construction project IDs 9, 10, and 11 are eligible only after their signed progress is greater than zero; the other project gates and manual, existing-work, and repair routes remain stock.

- Behavior changes: Villagers whose selected job is Building try the stock construction dispatcher at every food level, while autonomous construction project IDs 9, 10, and 11 are eligible only after their signed progress is greater than zero; the other project gates and manual, existing-work, and repair routes remain stock.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 6; every edit has an exact purpose and before/after guard in the manifest.

#### Continue Research at Max Technologies (`vv1_continue_research_at_max_technologies`)

Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.

- Behavior changes: Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv1_origins_village_wide_upgrades`)

Adds the Origins Upgrades button to the Tech screen. Food and Tech Point Doublers each cost 500,000 tech points, double eligible positive gains, and can be removed for no refund. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events, Duplicate Collectibles, and Golden Child tech gains are excluded.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly 4 physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged. Grant Full Mastery to All Villagers writes native mastery values and runs the native award evaluator for each changed eligible villager. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit.
- Dependencies: vv1_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x7B260.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv1_enable_origins_exclusive_features`)

Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Golden Child tech gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Golden Child tech gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x7B260.
- Doubler evidence matrix: {'positive_tech_writer': '0x41D120', 'positive_food_writer': '0x41D140', 'collection_adjustment': 'not independently recorded; no exact callsite claim', 'island_event_producers': ['0x428194 tech', '0x4281DA food'], 'tech_exclusions': ['Golden Child tech-point gain (no tech award route in this exact build)', 'Duplicate Collectibles tech-point gain (no duplicate-collectible tech writer route in this exact build)', 'Island Event tech-point gain (return 0x428194)'], 'hook_status': 'GO: exact-build positive writer wrappers double eligible positive deltas once; Island Event returns remain native; runtime/player confirmation pending'}
- Doubler composition contract: {'stacking': ['positive earned tech deltas only', 'positive food-source deltas only'], 'exclusions': ['Golden Child tech-point gain', 'Island Event tech-point gain', 'Duplicate Collectibles tech-point gain'], 'food_mastery_status': 'confirmed absent for this fingerprint; no Food Mastery-like food transform', 'status': 'GO: exact-build positive writer wrappers double eligible positive deltas once; Island Event returns remain native; runtime/player confirmation pending'}
- Doubler purchase status: {'new_purchase': 'available at 500,000 tech points for each doubler', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'available again at 500,000 tech points after removal'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

#### Magic Fruit of Life Alters Mortality (`vv1_magic_fruit_alters_mortality`)

Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.

- Behavior changes: Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 5; every edit has an exact purpose and before/after guard in the manifest.

#### Reenable F6 Clothing Change Cheat (`vv1_f6_clothing_change_cheat`)

The clothing shortcut cycles the selected active villager through the stock outfits: pressing F6 spends 5,000 tech points to advance to the next outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.

- Behavior changes: The clothing shortcut cycles the selected active villager through the stock outfits: pressing F6 spends 5,000 tech points to advance to the next outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 3; every edit has an exact purpose and before/after guard in the manifest.

#### School Lessons Grant Skill (`vv1_school_lessons_grant_skill`)

Each child who finishes the unlocked Going to school activity gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Behavior changes: Each child who finishes the unlocked Going to school activity gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 4; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv1_write_village_statistics`)

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Behavior changes: After a successful save, writes the village's lifetime statistics to a Village Statistics text file.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

## Virtual Villagers - The Lost Children

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - The Lost Children.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 13 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Birth Control (`vv2_birth_control`)

Limits only the two writer-reaching opcode-12 candidate scans used by ordinary autonomous/catch-up pairing and stew recipe 15: a candidate whose already-loaded internal age in EAX is 1000 or greater is rejected while candidate sex remains preserved in EDX. The stock manual carrier/female-only age gate remains unchanged and no male upper-age gate is added.

- Behavior changes: The writer-reaching opcode-12 candidate scans at file offsets 0x6488D and 0x64A8F reject candidates whose already-loaded internal age in EAX is at least 1000. Both complete 40-byte guarded blocks are one atomic VV2-only optional feature.
- Explicit non-changes/exclusions: The stock manual carrier/female-only age<1000 gate is unchanged, and no male upper-age gate is added. Chooser scoring, token 43 exact string work, willingness token 39 learning, planner logic, pregnancy writer, delivery, save format, RNG, food, fertility, capacity, messages, and statistics are unchanged. Love Note event, Gong grant, Silver Mirror clone, direct/event births, and every path outside the two writer-reaching opcode-12 candidate scans remain native.
- Dependencies: none
- Evidence status: implemented from exact-build disassembly commit 74778bd6a7d3a17dd990636cf6d4e769466800c6; static verification complete, runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Easier Healing Mastery (`vv2_easier_healing_mastery`)

Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.

- Behavior changes: Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv2_origins_village_wide_upgrades`)

Adds the Origins Upgrades button to the Tech screen. Food and Tech Point Doublers each cost 500,000 tech points, double eligible positive gains, and can be removed for no refund. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events, Duplicate Collectibles, and Gong of Wonder tech gains are excluded.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly 62 physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged. Grant Full Mastery to All Villagers writes native mastery values and runs the native award evaluator for each changed eligible villager. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit.
- Dependencies: vv2_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x8B808.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv2_enable_origins_exclusive_features`)

Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Gong of Wonder tech gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Gong of Wonder tech gains remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x8B808.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - The Lost Children.exe', 'size': 724992, 'sha256': '46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677'}, 'positive_tech_writer': '0x426290', 'positive_food_writer': '0x4262B0', 'collection_adjustment': 'No separate global collection multiplier exists in either final writer; every eligible caller passes the final native signed delta, so the wrapper doubles that positive delta after all caller-side collection arithmetic.', 'island_event_handlers': {'two_choice_handler': {'function': '0x4204B0', 'tech_returns': ['0x4205AC'], 'food_returns': ['0x420AE9'], 'direct_resource_paths': ['direct +3000 tech result and deductions/caps bypass the positive writers']}, 'single_result_dispatcher': {'function': '0x433600', 'tech_returns': ['0x434351'], 'food_returns': ['0x433FC6'], 'direct_resource_paths': ['losses, caps, halves, resets, and unrelated resources bypass positive writers']}}, 'gong_of_wonder': {'function': '0x44E8A0', 'registered_action': 164, 'invoked_by': '0x461B10', 'tech_returns': ['0x44EA32', '0x44ED52', '0x44F202'], 'food_returns': ['0x44E9C3', '0x44EDB9', '0x44F0D9'], 'direct_resource_paths': ['negative tech and reset/zero outcomes bypass positive writers']}, 'duplicate_collectibles': {'function': '0x463426', 'tech_returns': ['0x463461', '0x46346D', '0x463479'], 'behavior': 'an already-completed collectible routes to the tech writer'}, 'tech_blacklist_returns': ['0x4205AC', '0x434351', '0x44EA32', '0x44ED52', '0x44F202', '0x463461', '0x46346D', '0x463479'], 'food_blacklist_returns': ['0x420AE9', '0x433FC6', '0x44E9C3', '0x44EDB9', '0x44F0D9'], 'direct_call_inventory': {'tech': ['0x4205A7/0x4205AC', '0x43434C/0x434351', '0x4385E1/0x4385E6', '0x438741/0x438746', '0x4388A1/0x4388A6', '0x438A9B/0x438AA0', '0x438C7B/0x438C80', '0x438E5B/0x438E60', '0x44EA2D/0x44EA32', '0x44ED4D/0x44ED52', '0x44F1FD/0x44F202', '0x46345C/0x463461', '0x463468/0x46346D', '0x463474/0x463479', '0x463737/0x46373C', '0x4637C0/0x4637C5', '0x463809/0x46380E'], 'food': ['0x420AE4/0x420AE9', '0x433FC1/0x433FC6', '0x438293/0x438298', '0x438371/0x438376', '0x438445/0x43844A', '0x44E9BE/0x44E9C3', '0x44EDB4/0x44EDB9', '0x44F0D4/0x44F0D9', '0x463198/0x46319D', '0x463259/0x46325E', '0x463312/0x463317', '0x463364/0x463369', '0x4633CD/0x4633D2'], 'e9_tail_jumps_to_writers': 0}, 'hook_status': 'GO: exact-build static provenance proof covers the positive writer callsites and excludes Island Event, Gong, and duplicate-collectible tech awards; runtime/player confirmation pending'}
- Doubler composition contract: {'stacking': ['positive earned tech deltas only', 'positive food-source deltas only'], 'exclusions': ['Island Event tech-point gain', 'Gong of Wonder tech-point gain', 'Duplicate Collectibles tech-point gain'], 'food_mastery_status': 'confirmed absent in exact-build audit: enumerated technology definitions, resource strings, direct writer calls, and food-source call chains; Farming gates/unlocks sources only; Herb Mastery is unrelated', 'status': 'GO: exact-build static provenance covers the certified positive delta boundaries; native writers still perform storage/statistics updates for the doubled amount; runtime/player confirmation pending'}
- Doubler purchase status: {'status': 'Tech and Food Doublers are available at 500,000 tech points; owned upgrades can be removed for no refund and bought again.', 'new_purchase': 'available at 500,000 tech points for each doubler', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'available again at 500,000 tech points after removal'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 22; every edit has an exact purpose and before/after guard in the manifest.

#### Gong of Wonder Coconuts Fix (`vv2_gong_of_wonder_coconuts_fix`)

When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.

- Behavior changes: When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Hospital Recovery Heals (`vv2_hospital_recovery_heals`)

A villager who completes Recovering at the hospital gains exactly 1 health point, capped at 100. Stock VV2's hospital recovery action does not change health.

- Behavior changes: A villager who completes Recovering at the hospital gains exactly 1 health point, capped at 100. Stock VV2's hospital recovery action does not change health.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Teaching Children Grants Skill (`vv2_teaching_children_grants_skill`)

Each child who finishes a Teaching Children lesson gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Behavior changes: Each child who finishes a Teaching Children lesson gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv2_write_village_statistics`)

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Behavior changes: After a successful save, writes the village's lifetime statistics to a Village Statistics text file.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

## Virtual Villagers - The Secret City

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - The Secret City.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 8 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Birth Control (`vv3_birth_control`)

Limits only the ordinary autonomous/catch-up mate selector used by action 13: the scanned candidate remains in the stock internal-age 360..999 range, while the initiating villager no longer receives an extra upper-age rejection. VV3's native manual category-1 age gate remains unchanged and no male upper-age gate is added.

- Behavior changes: The five repeated candidate-selector blocks at file offsets 0x5CE74, 0x5CF35, 0x5CFFC, 0x5D0C0, and 0x5D187 retain each candidate's stock age<1000 check while removing only the initiator's duplicate age<1000 check. The ordinary action-13 autonomous/catch-up route therefore follows the VV4 reference boundary: the scanned candidate is capped at internal age 999, but the initiating villager has no male or female upper-age ceiling in this selector.
- Explicit non-changes/exclusions: The native VV3 manual pairing handler at VA 0x4584B0 retains its category-1 carrier/female-only internal-age-1000 rejection for both participants. Action selection, preference scoring, the conception writer, pending delivery, save format, RNG, health, fertility, capacity, messages, and statistics are unchanged. Direct event-created births, Island Events, clone paths, and every route outside the ordinary action-13 mate selector remain native.
- Dependencies: none
- Evidence status: implemented from exact-build disassembly; static verification complete, runtime/player confirmation pending
- Guarded executable edits: 5; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv3_origins_village_wide_upgrades`)

Adds the Origins Upgrades button to the Tech screen. Food and Tech Point Doublers each cost 500,000 tech points, double eligible positive gains, and can be removed for no refund. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events and Duplicate Collectibles are excluded.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly 3 physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged. Grant Full Mastery to All Villagers writes native mastery values and runs the native award evaluator for each changed eligible villager. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit.
- Dependencies: vv3_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x97488.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv3_enable_origins_exclusive_features`)

Adds Origins-style upgrade buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events and Duplicate Collectibles remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Adds Origins-style upgrade buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled, while Island Events and Duplicate Collectibles remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x97488.
- Doubler evidence matrix: {'positive_tech_writer': '0x427130', 'positive_food_writer': '0x4263F0', 'collection_adjustment': {'dispatcher': 'sub_42DEB0', 'tech_writer': '0x42DF79', 'food_writer': '0x42E079', 'tech_awards': {'100': 'IDs 52-55, 64-67, 76-79, 88-91', '250': 'IDs 56-59, 68-71, 80-83, 92-95', '1500': 'IDs 60-63, 72-75, 84-87, 96-99'}, 'caller_status': 'IDA has no resolved caller to sub_42DEB0; computed/indirect reachability remains unresolved'}, 'duplicate_collectibles': {'dispatcher': 'sub_42DEB0', 'tech_return': '0x42DF79', 'behavior': 'an already-completed collectible routes to the tech writer'}, 'island_event_producers': {'dispatcher': '0x458DB0-0x45943F', 'inventory': 'complete positive/zero/negative/bypass inventory including tail calls; mixed-source writers have no source tag', 'final_delta': 'sub_458DB0 emits base and bonus components through separate tech-writer calls; no single final-delta boundary is proved'}, 'writer_inventory': {'food': {'rows': 33, 'calls': 29, 'e9_tails': 4}, 'tech': {'rows': 16, 'calls': 13, 'e9_tails': 3}}, 'tail_sites': {'food': ['0x415EF1', '0x416983', '0x416BAB', '0x417A3A'], 'tech': ['0x415D44', '0x41673E', '0x418452']}, 'tail_bypass_sites': {'food': ['0x415EF1', '0x416983', '0x416BAB', '0x417A3A'], 'tech': ['0x415D44', '0x41673E', '0x418452']}, 'hook_status': 'GO: positive writer wrappers double eligible positive deltas once; duplicate collectibles and audited Island Event calls remain native; runtime/player confirmation pending'}
- Doubler composition contract: {'stacking': ['positive earned tech deltas only', 'positive food-source deltas only'], 'exclusions': ['Island Event tech-point gain', 'Duplicate Collectibles tech-point gain'], 'food_mastery_status': 'confirmed absent in the exact-build writer, strings, and bounded caller corpus', 'status': 'GO: positive writer wrappers double eligible positive deltas once; duplicate collectibles and audited Island Event calls remain native; runtime/player confirmation pending'}
- Doubler purchase status: {'new_purchase': 'available at 500,000 tech points for each doubler', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'available again at 500,000 tech points after removal'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 18; every edit has an exact purpose and before/after guard in the manifest.

#### Everyone Tries On the Robe (`vv3_everyone_tries_on_robe`)

Dropping an active, living, non-nursing villager on the robe keeps that villager's complete stock try-on or Tribal Chief result, then sends every other active, living, non-nursing villager through the stock failed-fit Trying on the robe action. Followers use the native status, walk, gestures, and temporary try-on appearance but never receive the successful fit, persistent Chief clothing, or Chief state.

- Behavior changes: After the stock callback reports a handled robe drop and leaves the eligible initiator in action 120 or 121, every other eligible VV3 villager is sent through the stock failed-fit action 121 robe sequence. The runtime loop accepts only the authenticated stock bound 150.
- Explicit non-changes/exclusions: Dead, inactive, and nursing villagers are skipped. The dropped initiator keeps the complete stock action 120 or action 121 result and remains the only villager eligible to become Tribal Chief. Followers never receive success action 120, persistent Chief clothing, or Chief state, and the wrapper does not read or write candidate fields +0xE80/+0xE88 or change the puzzle, pregnancy/nursing state, health, age, skills, preferences, or saved record layout.
- Dependencies: none
- Evidence status: independently reviewed exact-build static implementation; install/uninstall and stock/Expanded composition are automated, while player runtime confirmation remains pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.
- Mode-specific guarded edits: collection_progression=1, immediate_fixed=1; these rows are selected only for the named population mode.

#### Nature Level 1 Actually Replenishes Food Sources Faster (`vv3_nature_honey_refill`)

Nature level 1 or higher reduces fruit-tree refills from 3 hours to 2 hours 15 minutes and honey refills from 1 hour to 45 minutes. Fruit trees retain their stock Nature quantity bonus, while honey gains the same proportional quantity bonus.

- Behavior changes: Nature level 1 or higher reduces fruit-tree refills from 3 hours to 2 hours 15 minutes and honey refills from 1 hour to 45 minutes. Fruit trees retain their stock Nature quantity bonus, while honey gains the same proportional quantity bonus.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 7; every edit has an exact purpose and before/after guard in the manifest.

#### Nature Level 3 Actually Alters Mortality (`vv3_nature_level_three_alters_mortality`)

Nature level 3 shifts every ordinary villager's complete mortality curve seven displayed years later. The stock Medicine threshold is calculated first, so the benefits stack, and the shared aging loop applies the change during ordinary play and time catch-up.

- Behavior changes: Nature level 3 shifts every ordinary villager's complete mortality curve seven displayed years later. The stock Medicine threshold is calculated first, so the benefits stack, and the shared aging loop applies the change during ordinary play and time catch-up.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Pointing Out a Rare Collectible Always Works (`vv3_rare_collectible_retry`)

When the Tribal Chief completes Pointing out a rare collectible, rejected random choices are rerolled until the stock game finds an eligible rare collectible. This prevents the full stock cooldown from being spent without a collectible appearing while preserving the original rare categories, collectible IDs, collection rules, and placement logic.

- Behavior changes: When the Tribal Chief completes Pointing out a rare collectible, rejected random choices are rerolled until the stock game finds an eligible rare collectible. This prevents the full stock cooldown from being spent without a collectible appearing while preserving the original rare categories, collectible IDs, collection rules, and placement logic.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 3; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv3_write_village_statistics`)

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Behavior changes: After a successful save, writes the village's lifetime statistics to a Village Statistics text file.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

## Virtual Villagers - The Tree of Life

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - The Tree of Life.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 10 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Complete Fish Scales = Golden Fish in Nets (`vv4_complete_scales_golden_fish`)

Golden Fish become eligible in the fishing nets only after all 12 Fish Scales are collected. This changes the stock partial-collection threshold while preserving the completed collection's original 25% Golden Fish chance and every other fishing outcome.

- Behavior changes: Golden Fish become eligible in the fishing nets only after all 12 Fish Scales are collected. This changes the stock partial-collection threshold while preserving the completed collection's original 25% Golden Fish chance and every other fishing outcome.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv4_origins_village_wide_upgrades`)

Adds the Origins Upgrades button to the Tech screen. Food and Tech Point Doublers each cost 500,000 tech points, double eligible positive gains, and can be removed for no refund. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events and Duplicate Collectibles are excluded.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly 3 physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged. Grant Full Mastery to All Villagers uses the native Float32 skill writer for each changed skill and postverifies exact 100.0 values. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit.
- Dependencies: vv4_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xA0CD8.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv4_enable_origins_exclusive_features`)

Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled after native Food Mastery, while Island Events and Duplicate Collectibles remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Food and Tech Point Doublers for 500,000 tech points each; eligible positive gains are doubled after native Food Mastery, while Island Events and Duplicate Collectibles remain unchanged. The Village-Wide menu adds Running, Full Mastery, and Make Villagers Young Adults.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xA0CD8.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - The Tree of Life.exe', 'size': 929792, 'sha256': '6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220'}, 'positive_tech_writer': '0x41E300', 'positive_food_writer': '0x41D920', 'collection_adjustment': 'Food Mastery is applied inside sub_41D920: level 0/1=A, level 2=A+floor(A/2), level 3=2A. Collection call 0x414660 passes pre-mastery 6/35, so any eligible doubler must follow the native transform.', 'external_xref_inventory': {'tech': 21, 'food': 23}, 'tail_jump_sites': ['0x4156F8', '0x415862', '0x41586F', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x416735', '0x41520E'], 'ordinary_positive_sites': {'tech': ['0x414477', '0x414493', '0x4144AF', '0x431A9B'], 'food': ['0x414660', '0x436F15']}, 'duplicate_collectibles': {'function': 'sub_414410', 'tech_returns': ['0x41447C', '0x414498', '0x4144B4'], 'behavior': 'an already-completed collectible routes to the tech writer'}, 'island_event_positive_sites': {'tech': ['0x414A28', '0x4156F8', '0x415862', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x464E58', '0x464E82', '0x464EAB'], 'food': ['0x414949', '0x41520E', '0x4643E6', '0x464433', '0x464492', '0x46450B', '0x464573', '0x4645B0', '0x4645FB']}, 'tail_bypass_sites': {'tech': ['0x4156F8', '0x415862', '0x41586F', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x416735'], 'food': ['0x41520E']}, 'hook_status': 'GO: positive writer wrappers run after native Food Mastery; duplicate collectibles, direct Island Event calls, and audited Island Event tail-jumps remain native; runtime/player confirmation pending'}
- Doubler composition contract: {'stacking': ['positive earned tech deltas only', 'positive food-source deltas only'], 'exclusions': ['Island Event tech-point gain', 'Duplicate Collectibles tech-point gain'], 'food_mastery_status': 'confirmed in exact-build disassembly; native transform documented in doubler evidence', 'status': 'GO: positive writer wrappers double eligible positive deltas once after native adjustments; duplicate collectibles and audited Island Event paths remain native; runtime/player confirmation pending'}
- Doubler purchase status: {'new_purchase': 'available at 500,000 tech points for each doubler', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'available again at 500,000 tech points after removal'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 23; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv4_write_village_statistics`)

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Behavior changes: After a successful save, writes the village's lifetime statistics to a Village Statistics text file.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 3; every edit has an exact purpose and before/after guard in the manifest.

## Virtual Villagers - New Believers

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - New Believers.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 13 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Easier Devotee Training (`vv5_easier_devotee_training`)

Villagers with positive Devotion skill can spontaneously use the stock Honoring action. Statue-drop Honoring remains available for training beginners, while villagers with no Devotion skill do not autonomously Honor.

- Behavior changes: Villagers with positive Devotion skill can spontaneously use the stock Honoring action. Statue-drop Honoring remains available for training beginners, while villagers with no Devotion skill do not autonomously Honor.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 3; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv5_origins_village_wide_upgrades`)

Adds the Origins Upgrades button to the Tech screen. Food and Tech Point Doublers each cost 500,000 tech points, double eligible positive gains, and can be removed for no refund. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events and Duplicate Collectibles are excluded; only Believers are processed and Heathens are skipped.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly 3 physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged. Grant Full Mastery to All Villagers writes native mastery values and runs the native award evaluator for each changed eligible villager. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv5_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xAEF60.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (Task9 native actions) (`vv5_enable_origins_exclusive_features`)

Adds Origins-style upgrade menus to Tech and Villager Details. The menus offer Full Mastery, Running, Make Villagers Young Adults, and Full Heal/Cure All for Believers; Heathens are skipped. Time Warp, Island Event, and Barrel of Babies remain unavailable. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Adds Origins-style upgrade menus to Tech and Villager Details. The menus offer Full Mastery, Running, Make Villagers Young Adults, and Full Heal/Cure All for Believers; Heathens are skipped. Time Warp, Island Event, and Barrel of Babies remain unavailable.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xAEF60.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - New Believers.exe', 'size': 991232, 'sha256': '92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D'}, 'positive_tech_writer': '0x4237B0', 'tech_positive_returns': ['0x46DE4D', '0x46DE7C', '0x46DEA5'], 'tech_excluded_refund_return': '0x419EA3', 'tech_exclusions': ['all 16 Island Event outcomes', 'Duplicate Collectibles (returns 0x4147BE, 0x4147DD, and 0x4147F9)', 'all eight writer tail paths', 'technology purchase/spending/deduction paths', 'zero and negative deltas', 'unknown caller returns'], 'positive_food_writer': '0x41EB40 before storage/statistics channels', 'food_mastery': {'technology_id': 4, 'levels': {'1': 'A', '2': 'A+floor(A/2)', '3': '2A'}, 'costs': {'level_1_to_2': 3000, 'level_2_to_3': 40000}, 'zero_negative_inputs': 'bypass mastery', 'collection_return': '0x414970', 'collection_base_to_native': {'6': [6, 9, 12], '35': [35, 52, 70]}}, 'collection_adjustment': 'Food-source return 0x414970 supplies the base delta; native Food Mastery completes before the Food Point Doubler doubles the final positive source delta once.', 'island_event_producers': ['Island Event, startup, consumption, and unknown callers remain native; unknown callers cannot match return 0x414970'], 'tech_writer_hook': {'virtual_address': '0x4237B0', 'file_offset': '0x237B0', 'before': '568B742408', 'after': 'E94BF23800', 'wrapper_virtual_address': '0x7B2A00', 'wrapper_file_offset': '0xDBA00', 'wrapper_bytes': '8B44240485C07E2BF70588D3510001000000741F813C244DDE46007412813C247CDE46007409813C24A5DE46007504D1642404568B7424080131E9780DC7FF', 'ownership_address': '0x51D388', 'ownership_mask': '0x1', 'eligible_returns': ['0x46DE4D', '0x46DE7C', '0x46DEA5'], 'excluded_refund_return': '0x419EA3', 'branch_destinations': ['0x7B2A4A', '0x7B2A4E', '0x4237B7']}, 'stock_hook': {'virtual_address': '0x41EB6F', 'file_offset': '0x1EB6F', 'before': '85F67E3456', 'after': 'E98C3F3900', 'wrapper_virtual_address': '0x7B2B00', 'wrapper_file_offset': '0xDBB00', 'wrapper_bytes': '85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF', 'ownership_address': '0x51D388', 'ownership_mask': '0x2', 'eligible_return': '0x414970', 'branch_destinations': ['0x41EB74', '0x41EBA7']}, 'hook_status': 'stock-layout implemented: exact Tech three-return and Food positive-whitelist wrappers; expanded-256 restores both exact stock hooks and remains native for doubler runtime.'}
- Doubler composition contract: {'stacking': ['positive earned tech deltas only', 'positive food-source deltas only'], 'exclusions': ['Island Event tech-point gain', 'Duplicate Collectibles tech-point gain'], 'food_mastery_status': 'confirmed in exact-build disassembly; technology ID 4 and separate level 1 to 2 / level 2 to 3 native transforms documented', 'status': 'stock-layout implemented: only eligible earned/source deltas are doubled once; native writers continue storage/statistics updates for the doubled amount; expanded-256 keeps both native writers and disables only new doubler purchases.'}
- Doubler purchase status: {'status': 'stock-layout Tech and Food Doubler purchase/remove/repurchase implemented; expanded-256 new purchases are marker-gated unavailable', 'new_purchase': 'Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases'}
- Native event safety: {'disabled_rows': ['Time Warp', 'Island Event', 'Barrel of Babies'], 'reason': 'VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.', 'evidence_status': 'STOP; no charge or native call is made for these rows'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.
- Mode-specific guarded edits: experimental_expanded_256=7, experimental_expanded_256_progression=7; these rows are selected only for the named population mode.

#### Heathen Mommy Puzzle Restoration (`vv5_heathen_mommy_puzzle`)

Restores the natural Heathen Mommy to newly created villages as a tag-17 Heathen mother with one nursing baby, using two physical slots, and restores the hidden 17th Heathen Parent graphic and full-tile rollover messages to the Puzzles screen. Existing saves are not retroactively given a new mother.

- Behavior changes: Restores the natural Heathen Mommy to newly created villages as a tag-17 Heathen mother with one nursing baby, using two physical slots, and restores the hidden 17th Heathen Parent graphic and full-tile rollover messages to the Puzzles screen. Existing saves are not retroactively given a new mother.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 11; every edit has an exact purpose and before/after guard in the manifest.

#### Statue Drops: Normal Action or Honoring (`vv5_statue_polishing_or_honoring`)

Statue drops use skill-aware choices: Honoring is available only to villagers with positive Devotion, while Building a statue and Polishing the Statue require positive Building skill. When both outcomes are eligible, the choice is 50/50; otherwise the eligible normal action is kept.

- Behavior changes: Statue drops use skill-aware choices: Honoring is available only to villagers with positive Devotion, while Building a statue and Polishing the Statue require positive Building skill. When both outcomes are eligible, the choice is 50/50; otherwise the eligible normal action is kept.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

#### VV4 Nursery School Divisor Parity (`vv5_vv4_nursery_divisor_parity`)

For parity with Virtual Villagers 4, changes VV5's six-skill spread lesson divisor from five to six. VV5 normally distributes one-fifth of a lesson to each of six skills, an arithmetic inconsistency that awards six-fifths in total; this patch distributes exactly one-sixth to each skill without claiming whether the original inconsistency was intentional.

- Behavior changes: For parity with Virtual Villagers 4, changes VV5's six-skill spread lesson divisor from five to six. VV5 normally distributes one-fifth of a lesson to each of six skills, an arithmetic inconsistency that awards six-fifths in total; this patch distributes exactly one-sixth to each skill without claiming whether the original inconsistency was intentional.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv5_write_village_statistics`)

After a successful save, writes the village's lifetime statistics to a Village Statistics text file, including current puzzle totals.

- Behavior changes: After a successful save, writes the village's lifetime statistics to a Village Statistics text file, including current puzzle totals.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 4; every edit has an exact purpose and before/after guard in the manifest.

## Transparency and validation boundaries

Each successful output writes `VVFP Transparency Log.txt` beside the modified executable and a machine-readable `.patch-log.json`. The text report is written through a temporary file only after the executable, companions, and source/output tree have been verified; its SHA-256 is recorded in JSON without self-hashing the JSON. The report lists the stock and modified hashes, every applied edit grouped by owner, PE layout/checksum differences, file additions/modifications/removals, save handling, selected feature predicates/costs/exclusions, static checks, and the explicit runtime/player-confirmation-pending status.

Historical counters that are not persisted in a save cannot be reconstructed from a current save. The statistics exporter therefore reports persisted per-save counters and derives current puzzle completion (including VV5 Puzzle 17 when the save records it) at export time.
