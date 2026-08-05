# Virtual Villagers Fun Patcher — Transparency Coverage

This document is generated from the patch manifests. It is the project-level description of the differences the patcher can request; the per-output `VVFP Transparency Log.txt` is the authoritative record of the exact bytes and files used for one output.

## Automatic changes (every output)

Every output applies the selected population mode and the game's guarded population-safety edits. The collection-progression mode preserves the supported game's collection/bonus behavior while changing its declared maximum according to the manifest. The immediate-fixed mode keeps the fixed maximum. Experimental expanded-256 modes additionally apply the documented stock-save import/conversion route and physical-record expansion for VV3–VV5; VV1/VV2 already have 256 physical slots. Multiples and population-adding Island Events are saturated at the physical slot bound. No game is launched by the patcher, so runtime/player confirmation remains pending.

Available population modes: Collection Progression Max Pop, Immediate Fixed Max Pop, Experimental Expanded 256 Villagers, Experimental Expanded 256 - Collection Progression.

## Optional-patch chooser catalog

The desktop chooser presents game-scoped optional patches under the five manifest titles in this fixed order: A New Home, The Lost Children, The Secret City, The Tree of Life, and New Believers. Within each title, entries sort by case-folded display name and then patch ID. Unknown or all-games entries appear under a final `Shared / All Games` header. Checkbox variables remain keyed by patch ID; Select All, Deselect All, dependency closure, and persisted selections operate on those same variables. This is presentation-only: it changes no executable bytes, save fields, companion DLLs, or game behavior.

## Origins doubler evidence boundary

The per-game positive food/tech writer, collection-adjustment callsites, and every Island Event producer must be proved independently before an Origins doubler is considered complete. The requested final composition is per-game: Tech Point Doubler stacks with every proven collection effect that increases tech gain; Food Point Doubler stacks after Food Mastery only where that exact build proves the modifier. Golden Child is a VV1-only exclusion, Gong of Wonder is a VV2-only exclusion, and Island Event exclusions follow each game's inventory. Excluded outcomes (positive, zero, or negative) remain native. The current exact-build candidate exclusions and pending/STOP statuses are recorded in `docs/doubler-composition-audit.md`; return-address checks alone are not treated as exhaustive provenance proof.

VV3 Magic Level-1 audit `4c588ffd36765d750533fe9694f8fda5c8e82736` exhaustively enumerates nine Magic-index reads and finds only one research consumer: sub_458DB0 case 26 getter call 0x4593DC. Magic level 1 or higher contributes a deterministic separate +1 tech writer call after the base and optional quarter-base awards and before timed and independent RNG additions. It changes no research speed, duration, base award, RNG probability/amount, or Research-skill gain. Ordinary and special/catch-up research converge before Magic; collection duplicates and Island Events are separate producers. A future Tech Doubler must double the complete eligible positive native research sum once after all additions and exclude Island Events. VV3 Tech Doubler remains unavailable because case 26 emits components separately and no provenance-safe post-sum hook or source tag is certified.

## Birth Control scope

The exact-build VV4/VV5 breeding audit confirms that both games already provide the requested VV4-style Birth Control/Breeding behavior natively. VV4 and VV5 are untouched no-patch references; no Birth Control runtime bytes are offered, applied, or reserved for either game. VV1 and VV3 remain ON HOLD pending separate exact-build evidence.

Every current or future Birth Control, pregnancy, or Embracing patch is limited to the exact ordinary manual, autonomous, or catch-up route named by its game-specific evidence. All Island Event pregnancy, birth, and child outcomes remain completely native and bypass patched age, sex, preference, eligibility, conception, pregnancy, delivery, capacity, RNG, messages, statistics, and state writes. Every VV2 Gong of Wonder outcome has the same complete exclusion. These are control-flow/provenance exclusions, not result- or amount-based exceptions.

VV1 exact-build audit `c8d268d` rejects its former byte proposal: `0x3DBBE` is the stock food>=400 gate rather than an age predicate, `0x458D0` and `0x45930` are live instruction interiors, and `0x56740` is uncertified. Stock manual pairing has no age ceiling; the requested reference would be sex/category-2 carrier-only with no male ceiling. Complete coverage requires planner scan `0x4477AF` plus action-9 writer-reaching scans `0x446E70` and `0x447070`; catch-up reuses that path, while direct event births and pending delivery remain native. The disabled historical `vv1_birth_control` entry has no executable patches and remains ON HOLD.

VV2 exact-build feature `vv2_birth_control` is limited to the two complete 40-byte writer-reaching opcode-12 candidate scans at file offsets `0x6488D` and `0x64A8F`, based on disassembly commit `74778bd6a7d3a17dd990636cf6d4e769466800c6`. It preserves candidate sex in EDX and rejects an already-loaded candidate age in EAX at 1000 or above. The stock manual carrier/female-only gate and lack of a male upper-age gate remain unchanged. Love Note call `0x22006`, Gong life-grant call `0x4EB3E`, Silver Mirror clone call `0x217F9`, pregnancy writer `0x4B980`, pending-delivery path, chooser scoring, planner, saves, RNG, resources, statistics, and all direct event/Gong routes remain native. This does not claim broader breeding parity.

## VV2 Origins containment

The VV2 Origins pair is disabled pending root-cause repair. A player reported that both Time Warp and Food Point Doubler crash immediately after their purchased/success dialog is displayed. This records the trigger only and does not infer whether the charge or action persisted. The crash audit also found `.shr` raw-offset versus virtual-address confusion in the VV2 builder, displacing helper/header references by `0x2000`; this is a hard re-enable blocker but not certified as the complete explanation. Both disabled VV2 Origins records are contained; unrelated VV2 optional features remain available and retain their prior projections.

VV2 Grant Full Mastery to All Villagers is catalog-visible only for stock Collection Progression and Immediate Fixed modes after static emitted-byte GO evidence recorded by `13f4341201fa7757d23f77c5c17602bbe7bbf21d`, with binary implementation/source bound to `895340333d55273e599f2dce5ab0db42cbc6d0ab`. The isolated command-7-only feature scans active +0x30, positive signed health +0x52C, non-totem +0x558 records; writes only below-100 native skill DWORDs +0x7E4..+0x7F4 to 100; then native sub_44D4C0 runs exactly once globally after complete exact-100 postverification. It is a repeatable 1,000,000-point Buy action with complete dry-run, exact no-change/no-charge result, universal OK/Cancel confirmation, final unsigned funds and eligibility recheck, one deduction, and one commit. After the global evaluator, the transaction reacquires fresh manager/state, derives fresh telemetry, rechecks unsigned funds, and performs the single native deduction. Telemetry reports changed villagers, newly native-marked Elders, and changed villagers left unmarked at the native 50-totem cap. Commands 6/8, ownership, Remove, withdrawn `.shr`, Gong, Island Events, and unrelated record fields are absent. Expanded-256 modes reject before output. Runtime/player confirmation remains pending.

Superseded historical evidence (withdrawn; not current behavior): VV1 Full Mastery audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` confirms five contiguous signed DWORD skills at +0x3BC..+0x3CC, job preference +0x3D0, Master threshold 90, native cap 100, and persistent 32-record save packing at stride 0x3D8. The former candidate iterated occupied +0x28 and positive signed health +0x344, wrote 90 through raw stores, returned no changed count, and used state+0xA2FC for a one-million-point transaction without preflight, commit recheck, no-charge no-op result, or rollback. Those 90-point/raw-store semantics and unresolved-route findings are withdrawn and do not describe the current enabled candidate.

### Current VV1 Full Mastery enablement

The exact VV1 Full Mastery candidate is enabled and catalog-visible only for stock `collection_progression` and `immediate_fixed` after C76/D82/C83 independent static recertification against source commit `2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94`. Its five skill fields are signed DWORD integers and every eligible field must be exact integer 100. The true pool transport is `state=[Tech+0x0C]` then `pool=[state+0xADE8]`; eligibility excludes Golden Child records (`+0x36C == 199`), and the current transaction performs a complete dry run, explicit confirmation, native `sub_437230` writes, full recheck, then one deduction. Preference `+0x3D0` is never written or normalized; no naming or preference code is changed, and a checked preference remains authoritative. With no checked preference, D115 confirms stock `sub_43B520` compares +0x3BC Parenting/code2, +0x3C0 Building/code4, +0x3C8 Healing/code5, +0x3C4 Farming/code1, then +0x3CC Research/code3 using strict-greater comparisons; all-equal skills retain code2 and native mapping renders Master Parent. The isolated candidate hash is `3DB0D70ED5512D6A38765AA71B90DE4D9C3BD5BE30CD528C17A351413B28D06F`; its companion DLL is `4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3`. The C76 bundle also proves active Origins/Cure base `5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3`, combined audit `9B5CA9671558DE0A8CACB6E62AD98BA6C692522D253374DA74E52984B53FF230`, and exact uninstall equality to the active base. Expanded-256 remains ON HOLD/fail-closed, ordinary Origins composition remains collision-fail-closed, and runtime/player confirmation is pending.

VV5 All Villagers are 18 audit `aaddf71797c28f37b0cc1f5728e567c0601a05aa` confirms signed age DWORD +0x1B8C, 20 units per displayed year, and age 18 value 360. Native detail refresh, ordinary/offline increment writer 0x46F7F0, oldest-villager statistic update, and persistence of the 0xA8 age object are mapped. The disabled candidate raw store bypasses that native route and differs from the selected-age candidate's related +0x1C3C and nonzero +0x1C4C writes. It tests active +0x1CD4, positive health +0x1C40, current-believer faction +0x1CEC==0, and an unproved extra +0x1CE1==0 exclusion. Its 0x51D5F8/native-tech-writer transaction charges no-op and already-18 cases, returns zero results, and has no tied recheck or rollback. Nursing timer and nursing/pregnancy state must never change; this raw helper is not proved to satisfy that semantic rule. Expanded composition remains ON HOLD with 43 missing relocations.

VV4 All Villagers are 18 audit `ab404b0c5e80cab4d327de9a51069e6e3529df27` covers exact 929,792-byte build SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220 and confirms signed age +0x1B8C, 20 units/year, age 18 value 360, detail refresh sub_43BA80, native increment sub_465F10, offline call 0x46663B then oldest statistic dword_4D6E00, and persistence through sub_45DB30/sub_45DBE0. The disabled stride-0x2E3C candidate takes a 150/256 bound and tests active +0x1CC4, status +0x1CC7==0, and positive signed health +0x1C40. Its raw store bypasses native statistic/transition handling; a selected-age raw store is not native proof, and status semantics remain incomplete. The unsigned 1,000,000-point 0x4D6F88/sub_41E300 transaction charges no-op/all-already-18 cases, returns zero results, and has no rollback. Processed age +0x1C3C, nursing/pregnancy companion +0x1C4C, pending baby count, and unrelated fields must never change. Future birth/clone/Event exclusion and full stock-plus-expanded placement/composition remain unresolved.

Corrective VV3 All Villagers are 18 audit `295b5d1e228c501d0e14b1f869f11b0caa3a07bd` covers exact 831,488-byte build SHA-256 8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503. Live evidence changed target/display age +0xDC4 from 372 to 360, immediately displayed age 18, survived save/reload, and natively advanced to 361; nursing/conception-age/lifecycle timestamp +0xE74 stayed 372 and pregnancy +0xE8C stayed zero. sub_45F3E0 passes +0xDC4 to sub_45C640. +0xE74 must never be synchronized by the patch. sub_45FFE0 runs hidden food, health, mortality, and reproduction life steps only while +0xE74 < +0xDC4; lowering target age below the unchanged timestamp pauses those steps until target age advances beyond it. A target-only write is not inherently invalid, but this is not final GO: exact command-8 transaction/result bytes and collision-certified stock plus both-expanded PE manifests remain absent.

VV2 All Villagers are 18 audit `bd6ce555a9a197450aab7133c0a87b36fbfc6899` covers exact 724,992-byte build SHA-256 46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677 and confirms signed target/display age +0x530, processed age +0x534, 20 units/year, and age 18 value 360. Native sub_43B690 advances target at 0x43B8FD, updates the oldest statistic, runs full life catch-up, then increments processed age at 0x43C09A. Command 8 writes only target age and desynchronizes the pair. Pregnancy writer sub_44B980 stores processed age in +0x540 and delivery requires marker+40<processed; the selected-age candidate writes both ages to 360 and nonzero +0x540 to 318, violating nursing-state preservation. Its stride-0xE48C 256-slot scan checks active +0x30/health +0x52C but omits +0x558, while state+0x2EADC precharges with zero results and no no-op/recheck/rollback. Love Note 0x422006, Gong 0x44EB3E, and Silver Mirror 0x4217F9 remain separate native paths without claiming complete origin classification. The withdrawn non-executable `.shr` transport retains VAs 0x2000 below the actual mapping.

The future Full Mastery contract requires true native maximum 100 for every skill: five skills in VV1-VV4 and six in VV5. Master thresholds and candidate value 90 are not Full Mastery. This planning/readiness requirement does not authorize any contained runtime command.
VV4 Full Mastery UI Playtest 3 is HARD WITHDRAWN and both its base and individual Full Mastery records are catalog-hidden after a 0xC0000005 crash at RVA 0x89E0C / VA 0x489E0C. The individual-menu result calls at 0x4897CA and 0x489ABB incorrectly targeted the show-menu epilogue at 0x489573 instead of the exact 54-byte result helper at 0x489ACA/file 0x89ACA; its `ret 8` consumed the result-message pointer as the return address. The disabled repair candidate installs the guarded helper in a 64-byte zero cave and retargets both calls. Individual Full Mastery remains STOP because its command still lacks the complete native exact-100 transaction, while all-villager command 7 is separately withheld pending D25 recertification. The native trophy UI repair, Cure containment, unrelated features, and Expanded-256 ON HOLD are unchanged.

The former VV5 Full Mastery package commit `5e52be5e41b25b0f541c3c762e8caacc2dbd150b` was HARD WITHDRAWN after an immediate startup auto-close. WER reports APPCRASH `c0000005` at VA `0x44FA20`, whose stock first instruction `8B09` dereferences the thiscall receiver in ECX. The emitted base Origins Tech and Detail constructors called this routine after allocation without assigning the new object to ECX. Certification `8193629` is revoked. The corrected bundle assigns `ECX=EDI` before both calls and was independently certified under `7970cd9`; M2 passed startup and Full Mastery live testing. The disabled geometry candidate now uses the native cached `Images\btn_trophies.png` resource `0x53` (96x39) at local `(137,2)` for both Tech and Detail, preserving event 13, `sub_401BD0`, and `0x40C680` ownership; independent emitted-byte recertification remains required.

## All Villagers Like Running evidence boundary

Cross-game audit `0311443fbd078e3adcabaf7e693199989ddb9db8`, evidence clarification `a67e05247dc822306e1d5a514524cba388ab4d69`, and final preference matrix `f1555e295e828af2165ab0b7ea9f051ac9736418` place command 6 independently ON HOLD for VV1, VV2, VV4, and VV5 while fixing the logical arrays: VV1 four Like plus four Dislike signed DWORDs, VV2 62 plus 62, and VV3-VV5 three plus three. Signed -1 is empty but never an early terminator; readers scan the complete fixed bound. Running ID 38 was code-confirmed separately in each executable. PC VV2 Fastest Runner option 2 can naturally create duplicate Running Likes through 0x420D22, 0x420D2B, and 0x420D37. The disabled legacy helpers violate the required per-villager atomic order, and VV1/VV2 inspect too few slots. Any already-Running Like must skip the entire villager with zero preference writes, preserving duplicate Likes and every Dislike. Otherwise the first physical -1 must be proved before removing any Running Dislike; full Likes means no mutation; with a destination, insert once and clear every Running Dislike while preserving unrelated slots and ordering. VV5 must reject current faction +0x1CEC != 0 before any preference read/count, while +0x1CE1 is unsafe and unproved. Required future lines are exactly `Skipped over X villagers. Reason: already likes running` and `Removed running dislike from X villagers`; the proposed full-slot line remains future-only pending capacity proof. The main Official LDW Cheat Tables is the primary vanilla-name set; Official LDW Cheat Tables  (Backup!!) backs up Main for recovery/version comparison. Official LDW Cheat Tables - Copy is strong player-confirmed runtime evidence used with renamed/copied base-game executables whose filenames contain - Copy or a variation; translating its addresses still requires fingerprinting the underlying executable and accounting for process/module-name-dependent Cheat Engine scripts. Exact executable evidence controls.

VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833` and `1d9a39da078806aa940e4774a9068956e88347bc` close exact ID 38, three Like plus three Dislike DWORD slots at +0xFB4..+0xFC8, sentinel -1, stride 0x1F8C, supplied 150/256 bounds, persistence, the write-only preference interval, atomic ordering, and dry-run/no-charge/final unsigned recheck requirements. Its finalized four future lines begin with `Granted Running to %u villagers`; the exact complete set is recorded below. At that audit stage +0xE94 semantics were still open. Commands 6/7/8 occupy one forbidden 944-byte atomic payload at file 0x7B820 with shared entry 0x7B840/VA 0x47B840; 0x582644 precharges and 0x7B7A0 is only a header check; the three-counter 128-byte ABI lacks granted; hooks 0x6547D/0x65640 and payload 0xA3180 mix unrelated Origins mechanics; command-6-only UI guards and a complete appended-section relocation/uninstall/all-patch ledger are absent.

VV3 second resolution `d1cdeb67362487c1d577e3abae03c9424fd04fb9` specified every architecture item while leaving naturally nonzero +0xE94 as its then-open semantic gate. Exactly eight direct readers exist at 0x455993, 0x4568A3, 0x45C9AA, 0x468D4C, 0x469081, 0x46915C, 0x4692C8, and 0x4697EF; sole direct writer 0x45F2B1 writes zero during retirement/reset. Save/load/copy preserve it, no direct nonzero writer is found, and strong player-confirmed CE tables do not label it. The specified hooks 0x6547D/0x65640 use a Running-only seven-row state, maximum ID 1006, exact command==6 dispatch, 16-byte four-counter structure, and exact lines `Granted Running to %u villagers`, `Skipped over %u villagers. Reason: already likes running`, `Skipped over %u villagers. Reason: all like slots are occupied`, and `Removed running dislike from %u villagers`; at bound 256 they require at most 201 bytes including CRLF/NUL, fitting char[256]. Its former owned/removable transaction model is revoked; current corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` requires repeatable Buy with no ownership-bit access. Stock PE is ImageBase 0x400000, alignments 0x1000/0x1000, five sections, SizeOfHeaders 0x1000, SizeOfImage 0x2DF000, checksum zero, file end 0xCB000, with one section-header slot; expanded moves .shr/.rsrc to 0x3A1000/0x3A2000 and SizeOfImage to 0x3B8000 across 1,263 guards.

VV3 semantic closure `b9c7a22eb1d7cceae25160ce4d360621e7485625` identifies +0xE94 as a dormant retained per-villager totem-render selector, not a live eligibility discriminator. At 0x468D4C, nonzero selects localization 573, exact suffix `'s totem`; zero with signed health <= 0 selects 574, `'s remains`. The eight readers and sole zero writer are exhaustive; constructors, new/clone, Event, puzzle, and template paths have no nonzero producer. The corrected readable save corpus had 64 active records all zero, and a live 150-slot scan had 125 active records all zero; strong player-confirmed CE tables contain no E94 label. Running therefore uses only active +0xF10 != 0 and signed health +0xE78 > 0. VV2 +0x558 memorials and VV5 Heathen totems are separate. The only remaining ON HOLD boundary is deterministic command-6-only extension/transaction bytes and collision-certified stock/expanded PE manifests. The old 944-byte commands 6/7/8 payload remains forbidden because it precharges, exposes commands 7/8, lacks granted, and uses the wrong callback ABI; injection bytes remain withheld for implementation, not E94 semantics.

VV3 Running is catalog-hidden and VV3Run2 is hard-withdrawn from playtesting under crash audit `36f14702b938a6235230a3fd3e0c34328d3ac745`. The exact tested EXE/DLL pair crashed on the status-2 no-change route. Static ABI and pointer checks pass, save snapshot/rotation evidence shows no saved preference overwrite, and the fault instruction remains unknown. Do not package or test it until a fresh crash/no-change gate is certified. Corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` defines a repeatable Buy action with no ownership-bit access. Base Origins owns the `.vvrun` page and guarded no-op slot; commands 7/8 remain absent. The corrected no-op slot SHA-256 is 42FC601B51E8AAC069B70355502C32B6985A2471E26B683A61A68EA3B91BE4E3, the Running slot SHA-256 is 3F8F3BD7FD6C1BA8D8517539581D96F8D7B14D3BF959C74157FF970E432E5B13, and the unchanged companion exposes `ShowOriginsVillageWideResult@20` while retaining its existing exports. Replacement runtime testing is pending. Persistent fields are serialized/restored but remain legitimately mutable by later native aging, work, events, catch-up, and other game mechanics; the patch gate is immediate write preservation, save roundtrip, and noninterception of native future writers.

## Origins village-wide atomic-payload containment

All five legacy `vvN_origins_village_wide_upgrades` records remain disabled and absent from the catalog, GUI, CLI, Select All, dependency resolution, and rendered outputs because commands 6, 7, and 8 share one unsafe atomic payload. VV2's separate command-7 Full Mastery candidate is statically enabled and catalog-visible only for stock Collection Progression and Immediate Fixed; its runtime/player confirmation remains pending and Expanded-256 rejects before output. Commands 6/8, Remove, Cure, Gong, and Island Event routes remain absent from that candidate. VV3's village-wide command-6 Running remains withdrawn and absent; the separate selected-villager command-2 candidate is static-enabled only after the certified VV3 Full Mastery prerequisite and remains runtime-pending. VV4 audit `628e0d9217b92b9cd695655842b09d74689a0238` and VV5 audit `02581c8f518e27ebd5fc7d2972db5597ab08ed35` keep their mastery commands contained. Disabled legacy manifests retain diagnostic payload bytes but apply none; containment never alters save ownership or issues refunds.

## VV3 Full Heal / Cure All candidate

The revised VV3 Full Heal / Cure All candidate is enabled and catalog-visible only for certified Collection Progression and Immediate Fixed; implementation is complete at `49595a75b65cd0561811593ba19825239ec97dde` with parent `38510cc21b7cd322a52fbabc936794dfc8601ccc`. Independent static GO reports D209/C213 are recorded without inventing audit or acceptance commit identities; runtime/player validation remains pending. This generated disclosure is sourced from its authoritative candidate manifest.
- Partial-write disclosure: If native writes begin and a later write or postverification fails, earlier verified health, sickness, or People Cured effects may remain. No tech points are deducted on that failure, but complete rollback of native side effects is not claimed.

### VV4 Full Heal / Cure All candidate (disabled)

The VV4 `Full Heal / Cure All` candidate is disabled and catalog-hidden. It is bound to stock SHA-256 `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` and the certified VV4 Full Mastery parents for Collection Progression and Immediate Fixed only. Its contract enumerates physical indices 0..149 through the native resolver, counts overlapping eligible sickness and health 1..99 records, confirms both predicted counts for 30,000 tech points, rechecks state and funds, clears sickness, restores partial health through the native setter, postverifies exact health 100/sickness 0, and deducts once through ECX=0x4D6F88/call 0x41E300. The candidate-owned companion is `VVFP Origins Icons.dll`, a deterministic RT_DIALOG 201/203 structural repack (SHA-256 CF468556C14306FB74884BC48F23D5506CCFB5FC2B670364FA143BC1141E0EE7, 283,136 bytes); it inserts the native five-item command-5 row between command 4 and the following row, adds the ID 1005 Buy control and resource ID 110, and preserves the `Origins Upgrades` caption, dialog 202, exports, code, and non-resource bytes. People Cured is the separate [0x4D6DF0] statistic. Every no-charge route includes `No tech points have been deducted.` Expanded-256 and unknown compositions reject before output. The exact VV4 command-5 detour and `.vv4hc` page remain pending independent disassembly; existing Full Mastery UI/runtime bytes and the withdrawn legacy Cure route are unchanged.

## Virtual Villagers - A New Home

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - A New Home.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 17 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Builder Action Fixes (`vv1_builder_action_fixes`)

Villagers whose selected job is Building try the stock construction dispatcher at every food level, making them autonomously build and repair more reliably during ordinary play and time catch-up.

- Behavior changes: Villagers whose selected job is Building try the stock construction dispatcher at every food level, making them autonomously build and repair more reliably during ordinary play and time catch-up.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Continue Research at Max Technologies (`vv1_continue_research_at_max_technologies`)

Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.

- Behavior changes: Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv1_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds an icon-based Upgrades screen containing a Time Warp that advances exactly three displayed villager years, Island Event, the native Barrel of Babies event with a three-space capacity guard, and the displayed-but-currently-unavailable 500,000-tech-point Tech Point Doubler and Food Point Doubler. Existing owned doublers remain removable at zero cost with no refund; repurchase is temporarily disabled pending exact-build verification, plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. The doubler contract stacks after exact-build collectible adjustments; no Food Mastery-like food transform or collection tech multiplier was found in this fingerprint. Ordinary Science still modifies research amounts before any future eligible doubler hook. Golden Child and Island Event outcomes remain native; purchase is unavailable until safe hook and all-producer provenance are proven. The effect is stored in the current save rather than a global INI. Adds an icon-based Villager Upgrades screen containing Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18 for the displayed villager. Grant Full Mastery preserves a checked job preference and chooses Farming when none is checked so VV1 does not show the incomplete title Master. Grant Running adds running to an available Likes slot on the displayed villager, removes running from that villager's Dislikes slots, and refuses without charging when no Like slot is available; it does not alter movement speed, movement initialization, or any custom running flag. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds an icon-based Upgrades screen containing a Time Warp that advances exactly three displayed villager years, Island Event, the native Barrel of Babies event with a three-space capacity guard, and the displayed-but-currently-unavailable 500,000-tech-point Tech Point Doubler and Food Point Doubler. Existing owned doublers remain removable at zero cost with no refund; repurchase is temporarily disabled pending exact-build verification, plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. The doubler contract stacks after exact-build collectible adjustments; no Food Mastery-like food transform or collection tech multiplier was found in this fingerprint. Ordinary Science still modifies research amounts before any future eligible doubler hook. Golden Child and Island Event outcomes remain native; purchase is unavailable until safe hook and all-producer provenance are proven. The effect is stored in the current save rather than a global INI. Adds an icon-based Villager Upgrades screen containing Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18 for the displayed villager. Grant Full Mastery preserves a checked job preference and chooses Farming when none is checked so VV1 does not show the incomplete title Master. Grant Running adds running to an available Likes slot on the displayed villager, removes running from that villager's Dislikes slots, and refuses without charging when no Like slot is available; it does not alter movement speed, movement initialization, or any custom running flag.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x7B260.
- Doubler evidence matrix: {'positive_tech_writer': '0x41D120', 'positive_food_writer': '0x41D140', 'collection_adjustment': 'not independently recorded; no exact callsite claim', 'island_event_producers': ['0x428194 tech', '0x4281DA food'], 'hook_status': 'STOP: no safe executable cave/section and arbitrary computed or indirect producer provenance is not proven'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain'], 'exclusions': ['Golden Child behavior', 'Island Event outcomes'], 'food_mastery_status': 'confirmed absent for this fingerprint; no Food Mastery-like food transform', 'status': 'STOP: no safe executable cave/section and arbitrary computed or indirect producer provenance is not proven'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

#### Grant Full Mastery to All Villagers (`vv1_full_mastery_all_stage_a_candidate`)

enabled/catalog-visible stock-only command-7 Full Mastery candidate. Commands 6/8, ownership, Remove, Golden Child, and Island Event paths are absent; Expanded-256 is rejected before output.

- Behavior changes: enabled/catalog-visible stock-only command-7 Full Mastery candidate. Commands 6/8, ownership, Remove, Golden Child, and Island Event paths are absent; Expanded-256 is rejected before output.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: C76/D82/C83 GO against exact source commit 2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94; rendered payload and exact uninstall identities are hash-bound below; runtime/player confirmation remains pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Magic Fruit of Life Alters Mortality (`vv1_magic_fruit_alters_mortality`)

Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.

- Behavior changes: Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 5; every edit has an exact purpose and before/after guard in the manifest.

#### Reenable F6 Clothing Change Cheat (`vv1_f6_clothing_change_cheat`)

Pressing F6 spends 5,000 tech points to cycle the selected active villager to the next stock outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.

- Behavior changes: Pressing F6 spends 5,000 tech points to cycle the selected active villager to the next stock outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.
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

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
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

#### Gong of Wonder Coconuts Fix (`vv2_gong_of_wonder_coconuts_fix`)

When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.

- Behavior changes: When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Grant Full Mastery to All Villagers (`vv2_full_mastery_all_stage_a_candidate`)

Enabled command-7-only stock candidate for stock Collection Progression and Immediate Fixed modes. Runtime/player confirmation remains pending. The repaired transaction uses the native manager getter, changed-only native skill writer, native Elder evaluator, and native tech-point writer; no raw skill stores, precharge, .shr transport, Gong, or Island Event paths are emitted. Expanded-256 modes are rejected before output.

- Behavior changes: Enabled command-7-only stock candidate for stock Collection Progression and Immediate Fixed modes. Runtime/player confirmation remains pending. The repaired transaction uses the native manager getter, changed-only native skill writer, native Elder evaluator, and native tech-point writer; no raw skill stores, precharge, .shr transport, Gong, or Island Event paths are emitted. Expanded-256 modes are rejected before output.
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

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

## Virtual Villagers - The Secret City

### Automatic population and safety changes

Supported stock identity is the exact `Virtual Villagers - The Secret City.exe` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus 8 guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.

### Optional features

#### Enable Origins-Exclusive Features (`vv3_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with Time Warp, Island Event, the native Another One of Those Barrels event with a dynamic three-space 150/256-record guard, and displayed-but-currently-unavailable 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. The legacy sickness-only Origins Cure route is preserved byte-for-byte for provenance but is dominated before dispatch and unreachable in this composition; the certified command-5 Full Heal / Cure All transaction replaces it at 30,000 tech points. Time Warp advances every villager by exactly 3 displayed years at every active game speed; the required wall-clock shift is 3 hours at half speed, 6 hours at normal speed, and 10 hours at double speed. Doubler ownership is confined to the current save. The doubler contract would stack after the exact collectible/collection adjustment, but this build's collection dispatcher has unresolved computed/indirect reachability and no safe final-delta hook. Food Mastery-like award transforms are confirmed absent in the writer, strings, and bounded caller corpus. Island Event outcomes remain native; new purchase and repurchase are unavailable under the exact-build STOP gate. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only uses an available normal Likes slot on the displayed villager and removes Running from that villager's Dislikes; it refuses without charging when all normal Like slots are occupied and does not alter any movement behavior or speed value. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with Time Warp, Island Event, the native Another One of Those Barrels event with a dynamic three-space 150/256-record guard, and displayed-but-currently-unavailable 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. The legacy sickness-only Origins Cure route is preserved byte-for-byte for provenance but is dominated before dispatch and unreachable in this composition; the certified command-5 Full Heal / Cure All transaction replaces it at 30,000 tech points. Time Warp advances every villager by exactly 3 displayed years at every active game speed; the required wall-clock shift is 3 hours at half speed, 6 hours at normal speed, and 10 hours at double speed. Doubler ownership is confined to the current save. The doubler contract would stack after the exact collectible/collection adjustment, but this build's collection dispatcher has unresolved computed/indirect reachability and no safe final-delta hook. Food Mastery-like award transforms are confirmed absent in the writer, strings, and bounded caller corpus. Island Event outcomes remain native; new purchase and repurchase are unavailable under the exact-build STOP gate. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only uses an available normal Likes slot on the displayed villager and removes Running from that villager's Dislikes; it refuses without charging when all normal Like slots are occupied and does not alter any movement behavior or speed value.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x97488.
- Doubler evidence matrix: {'positive_tech_writer': '0x427130', 'positive_food_writer': '0x4263F0', 'collection_adjustment': {'dispatcher': 'sub_42DEB0', 'tech_writer': '0x42DF79', 'food_writer': '0x42E079', 'tech_awards': {'100': 'IDs 52-55, 64-67, 76-79, 88-91', '250': 'IDs 56-59, 68-71, 80-83, 92-95', '1500': 'IDs 60-63, 72-75, 84-87, 96-99'}, 'caller_status': 'IDA has no resolved caller to sub_42DEB0; computed/indirect reachability remains unresolved'}, 'island_event_producers': {'dispatcher': '0x458DB0-0x45943F', 'inventory': 'complete positive/zero/negative/bypass inventory including tail calls; mixed-source writers have no source tag', 'final_delta': 'sub_458DB0 emits base and bonus components through separate tech-writer calls; no single final-delta boundary is proved'}, 'writer_inventory': {'food': {'rows': 33, 'calls': 29, 'e9_tails': 4}, 'tech': {'rows': 16, 'calls': 13, 'e9_tails': 3}}, 'tail_sites': {'food': ['0x415EF1', '0x416983', '0x416BAB', '0x417A3A'], 'tech': ['0x415D44', '0x41673E', '0x418452']}, 'hook_status': 'STOP: no safe final-delta/source-aware hook, transient marker, or certified new section/cave; computed/indirect collection reachability remains unresolved'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'confirmed absent in the exact-build writer, strings, and bounded caller corpus', 'status': 'STOP: no safe final-delta/source-aware hook, transient marker, or certified new section/cave; Island Event mixed-source provenance and collection dispatcher caller remain unresolved'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 9; every edit has an exact purpose and before/after guard in the manifest.

#### Full Heal / Cure All (`vv3_full_heal_cure_all_candidate`)

Enabled/catalog-visible VV3 Full Heal / Cure All command-5 Buy candidate for certified Collection Progression and Immediate Fixed compositions after Origins + Full Mastery + individual Grant Running; static evidence is GO from D209/C213 and runtime/player validation remains pending.

- Behavior changes: Command 5 performs the certified Full Heal / Cure All transaction at 30,000 tech points.
- Explicit non-changes/exclusions: Expanded-256 and unknown builds remain fail-closed; the withdrawn village-wide Running route is absent. The candidate is stock-mode only and does not add Remove or ownership behavior.
- Partial-write disclosure: If native writes begin and a later write or postverification fails, earlier verified health, sickness, or People Cured effects may remain. No tech points are deducted on that failure, but complete rollback of native side effects is not claimed.
- Dependencies: vv3_individual_grant_running_candidate
- Evidence status: implementation generated at 49595a75b65cd0561811593ba19825239ec97dde; source/test state audited at e2f1a466b61392d161a0df2fbf8da94fc05ee4ca; independent static GO reports D209/C213; runtime/player validation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Grant Full Mastery to All Villagers (`vv3_full_mastery_all_stage_a_candidate`)

Stock-only command-7 repeatable Buy candidate using fixed manager 0x0059E110, native resolver sub_45C840, native skill writer sub_455740, and Award evaluator sub_462500; commands 6/8 are absent.

- Behavior changes: Stock-only command-7 repeatable Buy candidate using fixed manager 0x0059E110, native resolver sub_45C840, native skill writer sub_455740, and Award evaluator sub_462500; commands 6/8 are absent.
- Explicit non-changes/exclusions: none declared
- Dependencies: vv3_enable_origins_exclusive_features
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Grant Running to Selected Villager (`vv3_individual_grant_running_candidate`)

Enabled/catalog-visible stock Collection Progression/Immediate Fixed-only selected-villager Grant Running candidate composed after the certified VV3 Full Mastery chain. The withdrawn village-wide command-6 Running candidate is not reused or modified; runtime/player validation remains pending.

- Behavior changes: Command-2 selected-villager Grant Running is an exact 40,000-tech-point Buy action, repeatable=true, ownership=null, remove=false.
- Explicit non-changes/exclusions: The GUI dependency closure selects the certified VV3 Full Mastery prerequisite; direct API/CLI selections containing only this ID fail closed and do not auto-expand. The withdrawn village-wide command-6 Running candidate remains absent and is not reused or modified.
- Dependencies: vv3_full_mastery_all_stage_a_candidate
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

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

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 3; every edit has an exact purpose and before/after guard in the manifest.

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

#### Enable Origins-Exclusive Features (`vv4_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen. Time Warp advances exactly 3 displayed villager years at half, normal, and double speed; Island Event uses the stock scheduler; Barrel of Babies opens the native event and requires three free physical villager records in either the 150- or 256-record game. Adds displayed-but-currently-unavailable, current-save-only 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. The legacy Cure row and command 5 are withdrawn, unavailable, unreachable, and not part of this playtest; Full Heal/Cure All repair remains pending. The pending doubler contract stacks after exact-build collectible and Food Mastery adjustments, while Island Event outcomes remain native; purchase is unavailable until those paths are proven. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only adds Running to a free normal Like slot and removes it from Dislikes; it refuses without charging when Likes are full and never changes any movement or speed logic or value. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen. Time Warp advances exactly 3 displayed villager years at half, normal, and double speed; Island Event uses the stock scheduler; Barrel of Babies opens the native event and requires three free physical villager records in either the 150- or 256-record game. Adds displayed-but-currently-unavailable, current-save-only 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. The legacy Cure row and command 5 are withdrawn, unavailable, unreachable, and not part of this playtest; Full Heal/Cure All repair remains pending. The pending doubler contract stacks after exact-build collectible and Food Mastery adjustments, while Island Event outcomes remain native; purchase is unavailable until those paths are proven. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only adds Running to a free normal Like slot and removes it from Dislikes; it refuses without charging when Likes are full and never changes any movement or speed logic or value.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xA0CD8.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - The Tree of Life.exe', 'size': 929792, 'sha256': '6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220'}, 'positive_tech_writer': '0x41E300', 'positive_food_writer': '0x41D920', 'collection_adjustment': 'Food Mastery is applied inside sub_41D920: level 0/1=A, level 2=A+floor(A/2), level 3=2A. Collection call 0x414660 passes pre-mastery 6/35, so any eligible doubler must follow the native transform.', 'external_xref_inventory': {'tech': 21, 'food': 23}, 'tail_jump_sites': ['0x4156F8', '0x415862', '0x41586F', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x416735', '0x41520E'], 'ordinary_positive_sites': {'tech': ['0x414477', '0x414493', '0x4144AF', '0x431A9B'], 'food': ['0x414660', '0x436F15']}, 'island_event_positive_sites': {'tech': ['0x414A28', '0x4156F8', '0x415862', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x464E58', '0x464E82', '0x464EAB'], 'food': ['0x414949', '0x41520E', '0x4643E6', '0x464433', '0x464492', '0x46450B', '0x464573', '0x4645B0', '0x4645FB']}, 'hook_status': 'STOP: inventory is complete, but no safe post-Food-Mastery doubler hook has been implemented; return-address-only exclusion is invalid for the listed E9 tails'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'confirmed in exact-build disassembly; native transform documented in doubler evidence', 'status': 'STOP: no safe post-Food-Mastery hook/section and incomplete dynamic/computed Island Event provenance'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Evidence status: D33/C28 GO on exact repaired payload commit 1f5b84535cd8c3c6566b18e9e1ed3a767cedc956; D19 payload and D21 metadata evidence retained; Playtest 3 withdrawal remains historical evidence
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

#### Grant Full Mastery to All Villagers (`vv4_full_mastery_all_stage_a_candidate`)

Stock-mode command-7 repeatable Buy plus command-1 individual candidate using native Float32 skill writer sub_46AD80; commands 6/8 are absent. The legacy Cure row and command 5 are withdrawn and unreachable in this candidate.

- Behavior changes: Stock-mode command-7 repeatable Buy plus command-1 individual candidate using native Float32 skill writer sub_46AD80; commands 6/8 are absent. The legacy Cure row and command 5 are withdrawn and unreachable in this candidate.
- Explicit non-changes/exclusions: stock executable bytes outside the certified candidate payload shared Origins DLL bytes VV3 certified stock-mode bytes commands 6 and 8 Expanded-256 behavior (ON HOLD/fail-closed) save files and save format
- Dependencies: vv4_enable_origins_exclusive_features
- Evidence status: D33/C28 GO on exact repaired payload commit 1f5b84535cd8c3c6566b18e9e1ed3a767cedc956; D19 payload and D21 metadata evidence retained; prior Playtest 3 crash evidence retained
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv4_write_village_statistics`)

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 4; every edit has an exact purpose and before/after guard in the manifest.

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

#### Grant Full Mastery to All Villagers (`vv5_full_mastery_all_stage_a_candidate`)

Command-7 village-wide and guarded command-1 selected-Believer Full Mastery candidate using native six-skill Float32 writer sub_475730; commands 6/8 are absent.

- Behavior changes: Command-7 village-wide and guarded command-1 selected-Believer Full Mastery candidate using native six-skill Float32 writer sub_475730; commands 6/8 are absent.
- Explicit non-changes/exclusions: none declared
- Dependencies: vv5_enable_origins_exclusive_features
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

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

#### VV5 Origins Full Mastery Extension Base (`vv5_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds icon-based Origins Upgrades. The native Time Warp (the stock route advances exactly 3 displayed villager years), Island Event, and Barrel of Babies rows are retained but disabled until their Heathen-safe target paths are proved; selecting one reports that it is unavailable. The stock-layout Tech Point and Food Point Doublers are available for their configured 500,000-tech-point purchases; each existing owned doubler remains removable at zero cost with zero refund, and each removed doubler can be repurchased at the full configured price in stock layout. Expanded-256 keeps both new purchases unavailable while preserving owned Remove. The legacy Cure row and command 5 are withdrawn, unavailable, bypassed by the EB5F containment gate, unreachable, and not part of this candidate; Full Heal/Cure All repair remains pending. Villager Upgrades include Grant Youth (floor age 5), six-skill Full Mastery, Set Age to 18, and Grant Running. Grant Running only adds the build-specific Running preference ID (proven at table offset 0xAEF60) to a free normal Like slot and removes that same ID from Dislikes; it never changes movement or speed logic. VV5 Food Mastery is technology ID 4: the upgrade from level 1 to 2 costs 3,000 tech points and the upgrade from level 2 to 3 costs 40,000 tech points; central food writer 0x41EB40 applies positive A as A, A+floor(A/2), or 2A before food storage, statistics, and other downstream channels; zero and negative inputs bypass mastery. Ordinary collection return 0x414970 is eligible: base 6/35 becomes 6/35, 9/52, or 12/70 by mastery level. The Food Point Doubler runs after mastery and doubles the final positive eligible delta once. Island Event, startup, consumption, and unknown callers remain native. The stock Tech wrapper at 0x4237B0 is the exact six-return positive whitelist to .shr 0x7B2A00; 0x419EA3 clothing refunds remain native. The stock Food wrapper is the exact positive whitelist at 0x41EB6F to .shr 0x7B2B00. Expanded-256 restores both native five-byte hooks and keeps new doubler purchases unavailable pending complete rel32 relocation proof. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds icon-based Origins Upgrades. The native Time Warp (the stock route advances exactly 3 displayed villager years), Island Event, and Barrel of Babies rows are retained but disabled until their Heathen-safe target paths are proved; selecting one reports that it is unavailable. The stock-layout Tech Point and Food Point Doublers are available for their configured 500,000-tech-point purchases; each existing owned doubler remains removable at zero cost with zero refund, and each removed doubler can be repurchased at the full configured price in stock layout. Expanded-256 keeps both new purchases unavailable while preserving owned Remove. The legacy Cure row and command 5 are withdrawn, unavailable, bypassed by the EB5F containment gate, unreachable, and not part of this candidate; Full Heal/Cure All repair remains pending. Villager Upgrades include Grant Youth (floor age 5), six-skill Full Mastery, Set Age to 18, and Grant Running. Grant Running only adds the build-specific Running preference ID (proven at table offset 0xAEF60) to a free normal Like slot and removes that same ID from Dislikes; it never changes movement or speed logic. VV5 Food Mastery is technology ID 4: the upgrade from level 1 to 2 costs 3,000 tech points and the upgrade from level 2 to 3 costs 40,000 tech points; central food writer 0x41EB40 applies positive A as A, A+floor(A/2), or 2A before food storage, statistics, and other downstream channels; zero and negative inputs bypass mastery. Ordinary collection return 0x414970 is eligible: base 6/35 becomes 6/35, 9/52, or 12/70 by mastery level. The Food Point Doubler runs after mastery and doubles the final positive eligible delta once. Island Event, startup, consumption, and unknown callers remain native. The stock Tech wrapper at 0x4237B0 is the exact six-return positive whitelist to .shr 0x7B2A00; 0x419EA3 clothing refunds remain native. The stock Food wrapper is the exact positive whitelist at 0x41EB6F to .shr 0x7B2B00. Expanded-256 restores both native five-byte hooks and keeps new doubler purchases unavailable pending complete rel32 relocation proof.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xAEF60.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - New Believers.exe', 'size': 991232, 'sha256': '92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D'}, 'positive_tech_writer': '0x4237B0', 'tech_positive_returns': ['0x4147BE', '0x4147DD', '0x4147F9', '0x46DE4D', '0x46DE7C', '0x46DEA5'], 'tech_excluded_refund_return': '0x419EA3', 'tech_exclusions': ['all 16 Island Event outcomes', 'all eight writer tail paths', 'technology purchase/spending/deduction paths', 'zero and negative deltas', 'unknown caller returns'], 'positive_food_writer': '0x41EB40 before storage/statistics channels', 'food_mastery': {'technology_id': 4, 'levels': {'1': 'A', '2': 'A+floor(A/2)', '3': '2A'}, 'costs': {'level_1_to_2': 3000, 'level_2_to_3': 40000}, 'zero_negative_inputs': 'bypass mastery', 'collection_return': '0x414970', 'collection_base_to_native': {'6': [6, 9, 12], '35': [35, 52, 70]}}, 'collection_adjustment': 'Ordinary collection return 0x414970 supplies base 6/35; native Food Mastery produces 6/35, 9/52, or 12/70 after the level 1 to 2 (3,000 tech points) and level 2 to 3 (40,000 tech points) upgrades. The Food Point Doubler must follow this transform and double the final positive eligible delta once.', 'island_event_producers': ['Island Event, startup, consumption, and unknown callers remain native; unknown callers cannot match return 0x414970'], 'tech_writer_hook': {'virtual_address': '0x4237B0', 'file_offset': '0x237B0', 'before': '568B742408', 'after': 'E94BF23800', 'wrapper_virtual_address': '0x7B2A00', 'wrapper_file_offset': '0xDBA00', 'wrapper_bytes': '8B44240485C07E46F70588D3510001000000743A813C24BE474100742D813C24DD4741007424813C24F9474100741B813C244DDE46007412813C247CDE46007409813C24A5DE46007504D1642404568B7424080131E95D0DC7FF', 'ownership_address': '0x51D388', 'ownership_mask': '0x1', 'eligible_returns': ['0x4147BE', '0x4147DD', '0x4147F9', '0x46DE4D', '0x46DE7C', '0x46DEA5'], 'excluded_refund_return': '0x419EA3', 'branch_destinations': ['0x7B2A4A', '0x7B2A4E', '0x4237B7']}, 'stock_hook': {'virtual_address': '0x41EB6F', 'file_offset': '0x1EB6F', 'before': '85F67E3456', 'after': 'E98C3F3900', 'wrapper_virtual_address': '0x7B2B00', 'wrapper_file_offset': '0xDBB00', 'wrapper_bytes': '85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF', 'ownership_address': '0x51D388', 'ownership_mask': '0x2', 'eligible_return': '0x414970', 'branch_destinations': ['0x41EB74', '0x41EBA7']}, 'hook_status': 'stock-layout implemented: exact Tech six-return and Food positive-whitelist wrappers; expanded-256 restores both exact stock hooks and remains native for doubler runtime.'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'confirmed in exact-build disassembly; technology ID 4 and separate level 1 to 2 / level 2 to 3 native transforms documented', 'status': 'stock-layout implemented: Tech and Food Doublers run after their native adjustments; expanded-256 keeps both native writers and disables only new doubler purchases.'}
- Doubler purchase status: {'status': 'stock-layout Tech and Food Doubler purchase/remove/repurchase implemented; expanded-256 new purchases are marker-gated unavailable', 'new_purchase': 'Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases'}
- Native event safety: {'disabled_rows': ['Time Warp', 'Island Event', 'Barrel of Babies'], 'reason': 'VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.', 'evidence_status': 'STOP; no charge or native call is made for these rows'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 11; every edit has an exact purpose and before/after guard in the manifest.

#### Write Village Statistics to Text File (`vv5_write_village_statistics`)

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 5; every edit has an exact purpose and before/after guard in the manifest.

## Transparency and validation boundaries

Each successful output writes `VVFP Transparency Log.txt` beside the modified executable and a machine-readable `.patch-log.json`. The text report is written through a temporary file only after the executable, companions, and source/output tree have been verified; its SHA-256 is recorded in JSON without self-hashing the JSON. The report lists the stock and modified hashes, every applied edit grouped by owner, PE layout/checksum differences, file additions/modifications/removals, save handling, selected feature predicates/costs/exclusions, static checks, and the explicit runtime/player-confirmation-pending status.

Historical counters that are not persisted in a save cannot be reconstructed from a current save. The statistics exporter therefore reports persisted per-save counters and derives current puzzle completion (including VV5 Puzzle 17 when the save records it) at export time.
