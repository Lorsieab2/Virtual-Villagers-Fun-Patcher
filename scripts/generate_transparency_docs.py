"""Generate the committed project transparency coverage document."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, load_patch_modes  # noqa: E402


def _items(values) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def build_document() -> str:
    patches = load_fun_patches()
    candidate_map_path = ROOT / "data" / "candidates" / "vv3_running_candidate_map.json"
    candidate = (
        json.loads(candidate_map_path.read_text(encoding="utf-8"))
        if candidate_map_path.is_file()
        else None
    )
    # Keep the dedicated VV3 Full Heal section sourced from the authoritative
    # manifest even though the enabled candidate also appears in the catalog.
    full_heal_path = ROOT / "data" / "candidates" / "vv3_full_heal_cure_all_candidate.json"
    full_heal = (
        json.loads(full_heal_path.read_text(encoding="utf-8"))
        if full_heal_path.is_file()
        else None
    )
    vv3_running_path = ROOT / "data" / "candidates" / "vv3_individual_grant_running_candidate.json"
    vv3_running_revised_path = ROOT / "data" / "candidates" / "vv3_individual_grant_running_revised_candidate.json"
    vv3_running = json.loads(vv3_running_path.read_text(encoding="utf-8")) if vv3_running_path.is_file() else None
    vv3_running_revised = json.loads(vv3_running_revised_path.read_text(encoding="utf-8")) if vv3_running_revised_path.is_file() else None
    by_game = {build.id: [p for p in patches if p.game_id == build.id] for build in load_builds()}
    lines = [
        "# Virtual Villagers Fun Patcher — Transparency Coverage",
        "",
        "This document is generated from the patch manifests. It is the project-level description of the differences the patcher can request; the per-output `VVFP Transparency Log.txt` is the authoritative record of the exact bytes and files used for one output.",
        "",
        "## Automatic changes (every output)",
        "",
        "Every output applies the selected population mode and the game's guarded population-safety edits. The collection-progression mode preserves the supported game's collection/bonus behavior while changing its declared maximum according to the manifest. The immediate-fixed mode keeps the fixed maximum. Experimental expanded-256 modes additionally apply the documented stock-save import/conversion route and physical-record expansion for VV3–VV5; VV1/VV2 already have 256 physical slots. Multiples and population-adding Island Events are saturated at the physical slot bound. No game is launched by the patcher, so runtime/player confirmation remains pending.",
        "",
        "Available population modes: "
        + ", ".join(mode.name for mode in load_patch_modes())
        + ".",
        "",
        "## Optional-patch chooser catalog",
        "",
        "The desktop chooser presents game-scoped optional patches under the five manifest titles in this fixed order: A New Home, The Lost Children, The Secret City, The Tree of Life, and New Believers. Within each title, entries sort by case-folded display name and then patch ID. Unknown or all-games entries appear under a final `Shared / All Games` header. Checkbox variables remain keyed by patch ID; Select All, Deselect All, dependency closure, and persisted selections operate on those same variables. This is presentation-only: it changes no executable bytes, save fields, companion DLLs, or game behavior.",
        "",
        "## Origins doubler evidence boundary",
        "",
        "The per-game positive food/tech writer, collection-adjustment callsites, and every Island Event producer must be proved independently before an Origins doubler is considered complete. The requested final composition is per-game: Tech Point Doubler stacks with every proven collection effect that increases tech gain; Food Point Doubler stacks after Food Mastery only where that exact build proves the modifier. Golden Child is a VV1-only exclusion, Gong of Wonder is a VV2-only exclusion, and Island Event exclusions follow each game's inventory. Excluded outcomes (positive, zero, or negative) remain native. The current exact-build candidate exclusions and pending/STOP statuses are recorded in `docs/doubler-composition-audit.md`; return-address checks alone are not treated as exhaustive provenance proof.",
        "",
        "VV3 Magic Level-1 audit `4c588ffd36765d750533fe9694f8fda5c8e82736` exhaustively enumerates nine Magic-index reads and finds only one research consumer: sub_458DB0 case 26 getter call 0x4593DC. Magic level 1 or higher contributes a deterministic separate +1 tech writer call after the base and optional quarter-base awards and before timed and independent RNG additions. It changes no research speed, duration, base award, RNG probability/amount, or Research-skill gain. Ordinary and special/catch-up research converge before Magic; collection duplicates and Island Events are separate producers. A future Tech Doubler must double the complete eligible positive native research sum once after all additions and exclude Island Events. VV3 Tech Doubler remains unavailable because case 26 emits components separately and no provenance-safe post-sum hook or source tag is certified.",
        "",
        "## Birth Control scope",
        "",
        "The exact-build VV4/VV5 breeding audit confirms that both games already provide the requested VV4-style Birth Control/Breeding behavior natively. VV4 and VV5 are untouched no-patch references; no Birth Control runtime bytes are offered, applied, or reserved for either game. VV1 and VV3 remain ON HOLD pending separate exact-build evidence.",
        "",
        "Every current or future Birth Control, pregnancy, or Embracing patch is limited to the exact ordinary manual, autonomous, or catch-up route named by its game-specific evidence. All Island Event pregnancy, birth, and child outcomes remain completely native and bypass patched age, sex, preference, eligibility, conception, pregnancy, delivery, capacity, RNG, messages, statistics, and state writes. Every VV2 Gong of Wonder outcome has the same complete exclusion. These are control-flow/provenance exclusions, not result- or amount-based exceptions.",
        "",
        "VV1 exact-build audit `c8d268d` rejects its former byte proposal: `0x3DBBE` is the stock food>=400 gate rather than an age predicate, `0x458D0` and `0x45930` are live instruction interiors, and `0x56740` is uncertified. Stock manual pairing has no age ceiling; the requested reference would be sex/category-2 carrier-only with no male ceiling. Complete coverage requires planner scan `0x4477AF` plus action-9 writer-reaching scans `0x446E70` and `0x447070`; catch-up reuses that path, while direct event births and pending delivery remain native. The disabled historical `vv1_birth_control` entry has no executable patches and remains ON HOLD.",
        "",
        "VV2 exact-build feature `vv2_birth_control` is limited to the two complete 40-byte writer-reaching opcode-12 candidate scans at file offsets `0x6488D` and `0x64A8F`, based on disassembly commit `74778bd6a7d3a17dd990636cf6d4e769466800c6`. It preserves candidate sex in EDX and rejects an already-loaded candidate age in EAX at 1000 or above. The stock manual carrier/female-only gate and lack of a male upper-age gate remain unchanged. Love Note call `0x22006`, Gong life-grant call `0x4EB3E`, Silver Mirror clone call `0x217F9`, pregnancy writer `0x4B980`, pending-delivery path, chooser scoring, planner, saves, RNG, resources, statistics, and all direct event/Gong routes remain native. This does not claim broader breeding parity.",
        "",
        "## VV2 Origins containment",
        "",
        "The VV2 Origins pair is disabled pending root-cause repair. A player reported that both Time Warp and Food Point Doubler crash immediately after their purchased/success dialog is displayed. This records the trigger only and does not infer whether the charge or action persisted. The crash audit also found `.shr` raw-offset versus virtual-address confusion in the VV2 builder, displacing helper/header references by `0x2000`; this is a hard re-enable blocker but not certified as the complete explanation. Both disabled VV2 Origins records are contained; unrelated VV2 optional features remain available and retain their prior projections.",
        "",
        "VV2 Grant Full Mastery to All Villagers is catalog-visible only for stock Collection Progression and Immediate Fixed modes after static emitted-byte GO evidence recorded by `13f4341201fa7757d23f77c5c17602bbe7bbf21d`, with binary implementation/source bound to `895340333d55273e599f2dce5ab0db42cbc6d0ab`. The isolated command-7-only feature scans active +0x30, positive signed health +0x52C, non-totem +0x558 records; writes only below-100 native skill DWORDs +0x7E4..+0x7F4 to 100; then native sub_44D4C0 runs exactly once globally after complete exact-100 postverification. It is a repeatable 1,000,000-point Buy action with complete dry-run, exact no-change/no-charge result, universal OK/Cancel confirmation, final unsigned funds and eligibility recheck, one deduction, and one commit. After the global evaluator, the transaction reacquires fresh manager/state, derives fresh telemetry, rechecks unsigned funds, and performs the single native deduction. Telemetry reports changed villagers, newly native-marked Elders, and changed villagers left unmarked at the native 50-totem cap. Commands 6/8, ownership, Remove, withdrawn `.shr`, Gong, Island Events, and unrelated record fields are absent. Expanded-256 modes reject before output. Runtime/player confirmation remains pending.",
        "",
        "Superseded historical evidence (withdrawn; not current behavior): VV1 Full Mastery audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` confirms five contiguous signed DWORD skills at +0x3BC..+0x3CC, job preference +0x3D0, Master threshold 90, native cap 100, and persistent 32-record save packing at stride 0x3D8. The former candidate iterated occupied +0x28 and positive signed health +0x344, wrote 90 through raw stores, returned no changed count, and used state+0xA2FC for a one-million-point transaction without preflight, commit recheck, no-charge no-op result, or rollback. Those 90-point/raw-store semantics and unresolved-route findings are withdrawn and do not describe the current enabled candidate.",
        "",
        "### Current VV1 Full Mastery enablement",
        "",
        "The exact VV1 Full Mastery candidate is enabled and catalog-visible only for stock `collection_progression` and `immediate_fixed` after C76/D82/C83 independent static recertification against source commit `2f22a8b435918bf01b95aa4b9a6e6f4287d0ac94`. Its five skill fields are signed DWORD integers and every eligible field must be exact integer 100. The true pool transport is `state=[Tech+0x0C]` then `pool=[state+0xADE8]`; eligibility excludes Golden Child records (`+0x36C == 199`), and the current transaction performs a complete dry run, explicit confirmation, native `sub_437230` writes, full recheck, then one deduction. Preference `+0x3D0` is never written or normalized; no naming or preference code is changed, and a checked preference remains authoritative. With no checked preference, D115 confirms stock `sub_43B520` compares +0x3BC Parenting/code2, +0x3C0 Building/code4, +0x3C8 Healing/code5, +0x3C4 Farming/code1, then +0x3CC Research/code3 using strict-greater comparisons; all-equal skills retain code2 and native mapping renders Master Parent. The isolated candidate hash is `3DB0D70ED5512D6A38765AA71B90DE4D9C3BD5BE30CD528C17A351413B28D06F`; its companion DLL is `4736E5EFB8F680E3B1F124D1920A9390D9F6427260E60743039FA80F8646CCB3`. The C76 bundle also proves active Origins/Cure base `5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3`, combined audit `9B5CA9671558DE0A8CACB6E62AD98BA6C692522D253374DA74E52984B53FF230`, and exact uninstall equality to the active base. Expanded-256 remains ON HOLD/fail-closed, ordinary Origins composition remains collision-fail-closed, and runtime/player confirmation is pending.",
        "",
        "VV5 All Villagers are 18 audit `aaddf71797c28f37b0cc1f5728e567c0601a05aa` confirms signed age DWORD +0x1B8C, 20 units per displayed year, and age 18 value 360. Native detail refresh, ordinary/offline increment writer 0x46F7F0, oldest-villager statistic update, and persistence of the 0xA8 age object are mapped. The disabled candidate raw store bypasses that native route and differs from the selected-age candidate's related +0x1C3C and nonzero +0x1C4C writes. It tests active +0x1CD4, positive health +0x1C40, current-believer faction +0x1CEC==0, and an unproved extra +0x1CE1==0 exclusion. Its 0x51D5F8/native-tech-writer transaction charges no-op and already-18 cases, returns zero results, and has no tied recheck or rollback. Nursing timer and nursing/pregnancy state must never change; this raw helper is not proved to satisfy that semantic rule. Expanded composition remains ON HOLD with 43 missing relocations.",
        "",
        "VV4 All Villagers are 18 audit `ab404b0c5e80cab4d327de9a51069e6e3529df27` covers exact 929,792-byte build SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220 and confirms signed age +0x1B8C, 20 units/year, age 18 value 360, detail refresh sub_43BA80, native increment sub_465F10, offline call 0x46663B then oldest statistic dword_4D6E00, and persistence through sub_45DB30/sub_45DBE0. The disabled stride-0x2E3C candidate takes a 150/256 bound and tests active +0x1CC4, status +0x1CC7==0, and positive signed health +0x1C40. Its raw store bypasses native statistic/transition handling; a selected-age raw store is not native proof, and status semantics remain incomplete. The unsigned 1,000,000-point 0x4D6F88/sub_41E300 transaction charges no-op/all-already-18 cases, returns zero results, and has no rollback. Processed age +0x1C3C, nursing/pregnancy companion +0x1C4C, pending baby count, and unrelated fields must never change. Future birth/clone/Event exclusion and full stock-plus-expanded placement/composition remain unresolved.",
        "",
        "Corrective VV3 All Villagers are 18 audit `295b5d1e228c501d0e14b1f869f11b0caa3a07bd` covers exact 831,488-byte build SHA-256 8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503. Live evidence changed target/display age +0xDC4 from 372 to 360, immediately displayed age 18, survived save/reload, and natively advanced to 361; nursing/conception-age/lifecycle timestamp +0xE74 stayed 372 and pregnancy +0xE8C stayed zero. sub_45F3E0 passes +0xDC4 to sub_45C640. +0xE74 must never be synchronized by the patch. sub_45FFE0 runs hidden food, health, mortality, and reproduction life steps only while +0xE74 < +0xDC4; lowering target age below the unchanged timestamp pauses those steps until target age advances beyond it. A target-only write is not inherently invalid, but this is not final GO: exact command-8 transaction/result bytes and collision-certified stock plus both-expanded PE manifests remain absent.",
        "",
        "VV2 All Villagers are 18 audit `bd6ce555a9a197450aab7133c0a87b36fbfc6899` covers exact 724,992-byte build SHA-256 46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677 and confirms signed target/display age +0x530, processed age +0x534, 20 units/year, and age 18 value 360. Native sub_43B690 advances target at 0x43B8FD, updates the oldest statistic, runs full life catch-up, then increments processed age at 0x43C09A. Command 8 writes only target age and desynchronizes the pair. Pregnancy writer sub_44B980 stores processed age in +0x540 and delivery requires marker+40<processed; the selected-age candidate writes both ages to 360 and nonzero +0x540 to 318, violating nursing-state preservation. Its stride-0xE48C 256-slot scan checks active +0x30/health +0x52C but omits +0x558, while state+0x2EADC precharges with zero results and no no-op/recheck/rollback. Love Note 0x422006, Gong 0x44EB3E, and Silver Mirror 0x4217F9 remain separate native paths without claiming complete origin classification. The withdrawn non-executable `.shr` transport retains VAs 0x2000 below the actual mapping.",
        "",
        "The future Full Mastery contract requires true native maximum 100 for every skill: five skills in VV1-VV4 and six in VV5. Master thresholds and candidate value 90 are not Full Mastery. This planning/readiness requirement does not authorize any contained runtime command.",
        "VV4 Full Mastery UI Playtest 3 is HARD WITHDRAWN and both its base and individual Full Mastery records are catalog-hidden after a 0xC0000005 crash at RVA 0x89E0C / VA 0x489E0C. The individual-menu result calls at 0x4897CA and 0x489ABB incorrectly targeted the show-menu epilogue at 0x489573 instead of the exact 54-byte result helper at 0x489ACA/file 0x89ACA; its `ret 8` consumed the result-message pointer as the return address. The disabled repair candidate installs the guarded helper in a 64-byte zero cave and retargets both calls. Individual Full Mastery remains STOP because its command still lacks the complete native exact-100 transaction, while all-villager command 7 is separately withheld pending D25 recertification. The native trophy UI repair, Cure containment, unrelated features, and Expanded-256 ON HOLD are unchanged.",
        "",
        "The former VV5 Full Mastery package commit `5e52be5e41b25b0f541c3c762e8caacc2dbd150b` was HARD WITHDRAWN after an immediate startup auto-close. WER reports APPCRASH `c0000005` at VA `0x44FA20`, whose stock first instruction `8B09` dereferences the thiscall receiver in ECX. The emitted base Origins Tech and Detail constructors called this routine after allocation without assigning the new object to ECX. Certification `8193629` is revoked. The corrected bundle assigns `ECX=EDI` before both calls and was independently certified under `7970cd9`; M2 passed startup and Full Mastery live testing. The disabled geometry candidate now uses the native cached `Images\\btn_trophies.png` resource `0x53` (96x39) at local `(137,2)` for both Tech and Detail, preserving event 13, `sub_401BD0`, and `0x40C680` ownership; independent emitted-byte recertification remains required.",
        "",
        "## All Villagers Like Running evidence boundary",
        "",
        "Cross-game audit `0311443fbd078e3adcabaf7e693199989ddb9db8`, evidence clarification `a67e05247dc822306e1d5a514524cba388ab4d69`, and final preference matrix `f1555e295e828af2165ab0b7ea9f051ac9736418` place command 6 independently ON HOLD for VV1, VV2, VV4, and VV5 while fixing the logical arrays: VV1 four Like plus four Dislike signed DWORDs, VV2 62 plus 62, and VV3-VV5 three plus three. Signed -1 is empty but never an early terminator; readers scan the complete fixed bound. Running ID 38 was code-confirmed separately in each executable. PC VV2 Fastest Runner option 2 can naturally create duplicate Running Likes through 0x420D22, 0x420D2B, and 0x420D37. The disabled legacy helpers violate the required per-villager atomic order, and VV1/VV2 inspect too few slots. Any already-Running Like must skip the entire villager with zero preference writes, preserving duplicate Likes and every Dislike. Otherwise the first physical -1 must be proved before removing any Running Dislike; full Likes means no mutation; with a destination, insert once and clear every Running Dislike while preserving unrelated slots and ordering. VV5 must reject current faction +0x1CEC != 0 before any preference read/count, while +0x1CE1 is unsafe and unproved. Required future lines are exactly `Skipped over X villagers. Reason: already likes running` and `Removed running dislike from X villagers`; the proposed full-slot line remains future-only pending capacity proof. The main Official LDW Cheat Tables is the primary vanilla-name set; Official LDW Cheat Tables  (Backup!!) backs up Main for recovery/version comparison. Official LDW Cheat Tables - Copy is strong player-confirmed runtime evidence used with renamed/copied base-game executables whose filenames contain - Copy or a variation; translating its addresses still requires fingerprinting the underlying executable and accounting for process/module-name-dependent Cheat Engine scripts. Exact executable evidence controls.",
        "",
        "VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833` and `1d9a39da078806aa940e4774a9068956e88347bc` close exact ID 38, three Like plus three Dislike DWORD slots at +0xFB4..+0xFC8, sentinel -1, stride 0x1F8C, supplied 150/256 bounds, persistence, the write-only preference interval, atomic ordering, and dry-run/no-charge/final unsigned recheck requirements. Its finalized four future lines begin with `Granted Running to %u villagers`; the exact complete set is recorded below. At that audit stage +0xE94 semantics were still open. Commands 6/7/8 occupy one forbidden 944-byte atomic payload at file 0x7B820 with shared entry 0x7B840/VA 0x47B840; 0x582644 precharges and 0x7B7A0 is only a header check; the three-counter 128-byte ABI lacks granted; hooks 0x6547D/0x65640 and payload 0xA3180 mix unrelated Origins mechanics; command-6-only UI guards and a complete appended-section relocation/uninstall/all-patch ledger are absent.",
        "",
        "VV3 second resolution `d1cdeb67362487c1d577e3abae03c9424fd04fb9` specified every architecture item while leaving naturally nonzero +0xE94 as its then-open semantic gate. Exactly eight direct readers exist at 0x455993, 0x4568A3, 0x45C9AA, 0x468D4C, 0x469081, 0x46915C, 0x4692C8, and 0x4697EF; sole direct writer 0x45F2B1 writes zero during retirement/reset. Save/load/copy preserve it, no direct nonzero writer is found, and strong player-confirmed CE tables do not label it. The specified hooks 0x6547D/0x65640 use a Running-only seven-row state, maximum ID 1006, exact command==6 dispatch, 16-byte four-counter structure, and exact lines `Granted Running to %u villagers`, `Skipped over %u villagers. Reason: already likes running`, `Skipped over %u villagers. Reason: all like slots are occupied`, and `Removed running dislike from %u villagers`; at bound 256 they require at most 201 bytes including CRLF/NUL, fitting char[256]. Its former owned/removable transaction model is revoked; current corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` requires repeatable Buy with no ownership-bit access. Stock PE is ImageBase 0x400000, alignments 0x1000/0x1000, five sections, SizeOfHeaders 0x1000, SizeOfImage 0x2DF000, checksum zero, file end 0xCB000, with one section-header slot; expanded moves .shr/.rsrc to 0x3A1000/0x3A2000 and SizeOfImage to 0x3B8000 across 1,263 guards.",
        "",
        "VV3 semantic closure `b9c7a22eb1d7cceae25160ce4d360621e7485625` identifies +0xE94 as a dormant retained per-villager totem-render selector, not a live eligibility discriminator. At 0x468D4C, nonzero selects localization 573, exact suffix `'s totem`; zero with signed health <= 0 selects 574, `'s remains`. The eight readers and sole zero writer are exhaustive; constructors, new/clone, Event, puzzle, and template paths have no nonzero producer. The corrected readable save corpus had 64 active records all zero, and a live 150-slot scan had 125 active records all zero; strong player-confirmed CE tables contain no E94 label. Running therefore uses only active +0xF10 != 0 and signed health +0xE78 > 0. VV2 +0x558 memorials and VV5 Heathen totems are separate. The only remaining ON HOLD boundary is deterministic command-6-only extension/transaction bytes and collision-certified stock/expanded PE manifests. The old 944-byte commands 6/7/8 payload remains forbidden because it precharges, exposes commands 7/8, lacks granted, and uses the wrong callback ABI; injection bytes remain withheld for implementation, not E94 semantics.",
        "",
        (
            "VV3 Running is catalog-hidden and VV3Run2 is hard-withdrawn from playtesting under crash audit `36f14702b938a6235230a3fd3e0c34328d3ac745`. The exact tested EXE/DLL pair crashed on the status-2 no-change route. Static ABI and pointer checks pass, save snapshot/rotation evidence shows no saved preference overwrite, and the fault instruction remains unknown. Do not package or test it until a fresh crash/no-change gate is certified. Corrective contract `0095e605b3b488129c0623efd642e9352d8586c0` defines a repeatable Buy action with no ownership-bit access. Base Origins owns the `.vvrun` page and guarded no-op slot; commands 7/8 remain absent. The corrected no-op slot SHA-256 is "
            + (candidate["noop_slot_sha256"] if candidate else "not generated")
            + ", the Running slot SHA-256 is "
            + (candidate["running_slot_sha256"] if candidate else "not generated")
            + ", and the unchanged companion exposes `ShowOriginsVillageWideResult@20` while retaining its existing exports. Replacement runtime testing is pending. Persistent fields are serialized/restored but remain legitimately mutable by later native aging, work, events, catch-up, and other game mechanics; the patch gate is immediate write preservation, save roundtrip, and noninterception of native future writers."
        ),
        "",
        "## Origins village-wide atomic-payload containment",
        "",
        "All five legacy `vvN_origins_village_wide_upgrades` records remain disabled and absent from the catalog, GUI, CLI, Select All, dependency resolution, and rendered outputs because commands 6, 7, and 8 share one unsafe atomic payload. VV2's separate command-7 Full Mastery candidate is statically enabled and catalog-visible only for stock Collection Progression and Immediate Fixed; its runtime/player confirmation remains pending and Expanded-256 rejects before output. Commands 6/8, Remove, Cure, Gong, and Island Event routes remain absent from that candidate. VV3's village-wide command-6 Running remains withdrawn and absent; the separate selected-villager command-2 candidate is static-enabled only after the certified VV3 Full Mastery prerequisite and remains runtime-pending. VV4 audit `628e0d9217b92b9cd695655842b09d74689a0238` and VV5 audit `02581c8f518e27ebd5fc7d2972db5597ab08ed35` keep their mastery commands contained. Disabled legacy manifests retain diagnostic payload bytes but apply none; containment never alters save ownership or issues refunds.",
        "",
        "## VV3 Full Heal / Cure All candidate",
        "",
        "The revised VV3 Full Heal / Cure All candidate is enabled and catalog-visible only for certified Collection Progression and Immediate Fixed; implementation is complete at `" + str(full_heal.get("provenance", {}).get("implementation_commit", "not recorded")) + "` with parent `" + str(full_heal.get("provenance", {}).get("implementation_parent_commit", "not recorded")) + "`. Independent static GO reports D209/C213 are recorded without inventing audit or acceptance commit identities; runtime/player validation remains pending. This generated disclosure is sourced from its authoritative candidate manifest.",
        "- Partial-write disclosure: "
        + (str(full_heal.get("partial_failure_limit", "not recorded")) if full_heal else "not recorded"),
        "",
        "## VV3 Grant Running containment",
        "",
        "The historical VV3 selected-villager Grant Running record is withdrawn and catalog-hidden. Its Likes-only helper never inspects or clears Running Dislikes (+0xFC0/+0xFC4/+0xFC8), so it is not exposed or composed; prior emitted bytes and packages remain immutable evidence.",
        "",
        "The revised six-slot candidate is disabled/catalog-hidden and emits no output. Its contract snapshots all Like and Dislike slots, preserves duplicate Likes, clears every Running Dislike, and writes only the first physical empty Like when no Running Like exists. Native preference side effects and a safe composed command-1/command-2 dispatcher remain unproved, so the candidate is STOP/runtime-pending. MessageBoxA accepts only EAX==1 (IDOK); EAX==2 and every other result are no-write/no-charge.",
        "",
        "### VV4 Full Heal / Cure All candidate (disabled)",
        "",
        "The VV4 `Full Heal / Cure All` candidate is disabled and catalog-hidden. "
        "It is bound to stock SHA-256 `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` "
        "and the certified VV4 Full Mastery parents for Collection Progression and Immediate Fixed only. "
        "Production composition resolves the complete dependency-first chain "
        "`vv4_complete_scales_golden_fish` -> `vv4_enable_origins_exclusive_features` -> "
        "`vv4_full_mastery_all_stage_a_candidate` -> `vv4_write_village_statistics`; "
        "the resulting pre-Full-Heal executables are pinned to the certified Collection and Immediate hashes. "
        "Its contract enumerates physical indices 0..149 through the native resolver, counts overlapping "
        "eligible sickness and health 1..99 records, confirms both predicted counts for 30,000 tech points, "
        "rechecks state and funds, clears sickness, restores partial health through the native setter, "
        "postverifies exact health 100/sickness 0, and deducts once through ECX=0x4D6F88/call 0x41E300. "
        "The candidate-owned companion is `VVFP Origins Icons.dll`, a deterministic structural RT_DIALOG 201/203 repack (SHA-256 165F327783DFECAB4C42DB28D6F926BCA46397F725F036BFC367BB659384C0AC, 298,496 bytes); it clones parent items 20..24, inserts the native five-item command-5 row before item 25, adds the ID 1005 Buy control and real RT_ICON 46..49 / RT_GROUP_ICON 110 artwork, updates the resource-directory size to 0x33800, and preserves the `Origins Upgrades` caption, dialog 202, exports, code, and non-resource bytes. "
        "People Cured is the separate [0x4D6DF0] statistic. Every no-charge route includes "
        "`No tech points have been deducted.` Expanded-256 and unknown compositions reject before output. "
        "The exact VV4 command-5 detour and `.vv4hc` page remain pending independent disassembly; existing "
        "Full Mastery UI/runtime bytes and the withdrawn legacy Cure route are unchanged.",
        "",
    ]
    for build in load_builds():
        lines.extend(
            [
                f"## {build.title}",
                "",
                "### Automatic population and safety changes",
                "",
                f"Supported stock identity is the exact `{build.input_name}` build recorded in `data/builds.json`. The automatic edits are the selected population mode plus {len(build.safety_patches)} guarded safety edits. The modified output retains the untouched stock executable beside the modified executable. Stock modes preserve vanilla save format; expanded modes use the documented guarded compatibility/conversion path.",
                "",
                "### Optional features",
                "",
            ]
        )
        game_patches = sorted(by_game[build.id], key=lambda p: (p.name.casefold(), p.id))
        for patch in game_patches:
            raw = patch.raw
            lines.append(f"#### {patch.name} (`{patch.id}`)")
            lines.append("")
            description = patch.description
            if patch.id.endswith("_enable_origins_exclusive_features"):
                description += " Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity."
            lines.append(description)
            lines.append("")
            behavior = _items(raw.get("behavior_changes", [patch.description]))
            exclusions = _items(raw.get("explicit_non_changes", raw.get("exclusions", [])))
            dependencies = _items(raw.get("dependencies", []))
            lines.append("- Behavior changes: " + (" ".join(behavior) or "none declared"))
            lines.append("- Explicit non-changes/exclusions: " + (" ".join(exclusions) or "none declared"))
            if raw.get("partial_failure_limit"):
                lines.append("- Partial-write disclosure: " + str(raw["partial_failure_limit"]))
            lines.append("- Dependencies: " + (", ".join(dependencies) or "none"))
            if "running_preference_id" in raw:
                evidence = raw.get("running_preference_evidence", {})
                lines.append(
                    "- Build-specific Running preference ID: "
                    + str(raw["running_preference_id"])
                    + "; evidence source: "
                    + str(evidence.get("source", "not recorded"))
                    + " at table offset "
                    + str(evidence.get("table_file_offset", "not recorded"))
                    + "."
                )
            if "doubler_evidence" in raw:
                lines.append("- Doubler evidence matrix: " + str(raw["doubler_evidence"]))
            if "doubler_composition_contract" in raw:
                lines.append(
                    "- Doubler composition contract: "
                    + str(raw["doubler_composition_contract"])
                )
            if "doubler_purchase_status" in raw:
                lines.append("- Doubler purchase status: " + str(raw["doubler_purchase_status"]))
            if "native_event_safety" in raw:
                lines.append("- Native event safety: " + str(raw["native_event_safety"]))
            lines.append(
                "- Evidence status: "
                + raw.get(
                    "evidence_status",
                    "static source/manifest verification performed; runtime/player confirmation pending",
                )
            )
            lines.append(
                f"- Guarded executable edits: {len(raw.get('patches', []))}; every edit has an exact purpose and before/after guard in the manifest."
            )
            lines.append("")
    lines.extend(
        [
            "## Transparency and validation boundaries",
            "",
            "Each successful output writes `VVFP Transparency Log.txt` beside the modified executable and a machine-readable `.patch-log.json`. The text report is written through a temporary file only after the executable, companions, and source/output tree have been verified; its SHA-256 is recorded in JSON without self-hashing the JSON. The report lists the stock and modified hashes, every applied edit grouped by owner, PE layout/checksum differences, file additions/modifications/removals, save handling, selected feature predicates/costs/exclusions, static checks, and the explicit runtime/player-confirmation-pending status.",
            "",
            "Historical counters that are not persisted in a save cannot be reconstructed from a current save. The statistics exporter therefore reports persisted per-save counters and derives current puzzle completion (including VV5 Puzzle 17 when the save records it) at export time.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    (ROOT / "docs" / "transparency-log.md").write_text(
        build_document(), encoding="utf-8"
    )
