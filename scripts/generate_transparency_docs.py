"""Generate the committed project transparency coverage document."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, load_patch_modes  # noqa: E402


def _items(values) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def build_document() -> str:
    patches = load_fun_patches()
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
        "VV2 Full Mastery audit `60f649bf90b55dea3a6856d949e123bd79808782` confirms five contiguous signed DWORD skills at +0x7E4..+0x7F4, job preference at +0x7F8, Master threshold 88, native maximum 100, and persistence across 256 physical records at stride 0xE48C. The disabled candidate iterates active +0x30 and positive signed health +0x52C, writes 90, returns no changed count, and uses a generic 1,000,000-point transaction without zero-change/no-charge handling, result detail, or rollback. Candidate 90 is not full native 100; no complete native all-five side-effect route, creation/inheritance/Silver Mirror closure, or safe withdrawn `.shr` transport/placement is proved. Gong and every Island Event route remain entirely native, including selection, RNG, messages, statistics, and writes.",
        "",
        "VV1 Full Mastery audit `e0bed87ce17dca5331afed1abc2d753ec3d8f0aa` confirms five contiguous signed DWORD skills at +0x3BC..+0x3CC, job preference +0x3D0, Master threshold 90, native cap 100, and persistent 32-record save packing at stride 0x3D8. The disabled candidate iterates occupied +0x28 and positive signed health +0x344, writes 90 while leaving preference unchanged, returns no changed count, and uses state+0xA2FC for a one-million-point transaction without preflight, commit recheck, no-charge no-op result, or rollback. Target 90-versus-100 semantics, preference/title policy, distributed native side effects and the lack of a complete all-five route, creation/clone policy, strict Golden Child and Island Event bypass, and placement/composition remain unresolved.",
        "",
        "VV5 All Villagers are 18 audit `aaddf71797c28f37b0cc1f5728e567c0601a05aa` confirms signed age DWORD +0x1B8C, 20 units per displayed year, and age 18 value 360. Native detail refresh, ordinary/offline increment writer 0x46F7F0, oldest-villager statistic update, and persistence of the 0xA8 age object are mapped. The disabled candidate raw store bypasses that native route and differs from the selected-age candidate's related +0x1C3C and nonzero +0x1C4C writes. It tests active +0x1CD4, positive health +0x1C40, current-believer faction +0x1CEC==0, and an unproved extra +0x1CE1==0 exclusion. Its 0x51D5F8/native-tech-writer transaction charges no-op and already-18 cases, returns zero results, and has no tied recheck or rollback. Nursing timer and nursing/pregnancy state must never change; this raw helper is not proved to satisfy that semantic rule. Expanded composition remains ON HOLD with 43 missing relocations.",
        "",
        "VV4 All Villagers are 18 audit `ab404b0c5e80cab4d327de9a51069e6e3529df27` covers exact 929,792-byte build SHA-256 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220 and confirms signed age +0x1B8C, 20 units/year, age 18 value 360, detail refresh sub_43BA80, native increment sub_465F10, offline call 0x46663B then oldest statistic dword_4D6E00, and persistence through sub_45DB30/sub_45DBE0. The disabled stride-0x2E3C candidate takes a 150/256 bound and tests active +0x1CC4, status +0x1CC7==0, and positive signed health +0x1C40. Its raw store bypasses native statistic/transition handling; a selected-age raw store is not native proof, and status semantics remain incomplete. The unsigned 1,000,000-point 0x4D6F88/sub_41E300 transaction charges no-op/all-already-18 cases, returns zero results, and has no rollback. Processed age +0x1C3C, nursing/pregnancy companion +0x1C4C, pending baby count, and unrelated fields must never change. Future birth/clone/Event exclusion and full stock-plus-expanded placement/composition remain unresolved.",
        "",
        "VV3 All Villagers are 18 audit `cee9a195faed187c847672bf36d46935a9f67ad3` covers exact 831,488-byte build SHA-256 8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503 and confirms signed target/display age +0xDC4, 20 units/year, and age 18 value 360. Native elapsed updater sub_45F3E0 calls sub_45C640 at 0x45F5C6 and updates the oldest statistic; catch-up sub_45FFE0 advances separate processed age +0xE74 one unit at a time through native life simulation. The disabled stride-0x1F8C helper uses a 150/256 bound and active +0xF10/positive health +0xE78, but writes only +0xDC4=360 and leaves dual ages unsynchronized. The selected-age candidate instead changes +0xE74 and nonzero nursing/pregnancy +0xE8C, violating the mandatory nursing-state non-change requirement. Neither raw route is semantically safe. Ordinary/status eligibility, no-op/all-already-18 charge with zero results/no rollback, future Event/birth/clone exclusions, and full stock-plus-expanded placement/composition remain unresolved.",
        "",
        "VV2 All Villagers are 18 audit `bd6ce555a9a197450aab7133c0a87b36fbfc6899` covers exact 724,992-byte build SHA-256 46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677 and confirms signed target/display age +0x530, processed age +0x534, 20 units/year, and age 18 value 360. Native sub_43B690 advances target at 0x43B8FD, updates the oldest statistic, runs full life catch-up, then increments processed age at 0x43C09A. Command 8 writes only target age and desynchronizes the pair. Pregnancy writer sub_44B980 stores processed age in +0x540 and delivery requires marker+40<processed; the selected-age candidate writes both ages to 360 and nonzero +0x540 to 318, violating nursing-state preservation. Its stride-0xE48C 256-slot scan checks active +0x30/health +0x52C but omits +0x558, while state+0x2EADC precharges with zero results and no no-op/recheck/rollback. Love Note 0x422006, Gong 0x44EB3E, and Silver Mirror 0x4217F9 remain separate native paths without claiming complete origin classification. The withdrawn non-executable `.shr` transport retains VAs 0x2000 below the actual mapping.",
        "",
        "The future Full Mastery contract requires true native maximum 100 for every skill: five skills in VV1-VV4 and six in VV5. Master thresholds and candidate value 90 are not Full Mastery. This planning/readiness requirement does not authorize any contained runtime command.",
        "",
        "## All Villagers Like Running evidence boundary",
        "",
        "Cross-game audit `0311443fbd078e3adcabaf7e693199989ddb9db8` and evidence clarification `a67e05247dc822306e1d5a514524cba388ab4d69` place command 6 independently ON HOLD for every exact supported build. Running ID 38 was code-confirmed separately in each executable. VV1 has four Like plus four Dislike signed DWORD slots, VV2 has 62 plus 62, and VV3-VV5 have three plus three; all use signed -1 as empty and each complete array's persistence was traced. The disabled helpers violate the required per-villager atomic order, and VV1/VV2 inspect too few slots. An already-Running Like must skip the entire villager; otherwise an empty Like must be proved before removing any Running Dislike; full Likes means no mutation; unrelated slots and ordering remain unchanged. VV5 must reject current faction +0x1CEC != 0 before any preference read/count, while +0x1CE1 is unsafe and unproved. Remaining shared gates are a bounded four-counter result ABI, final unsigned no-op/no-charge recheck and rollback, complete ordinary/status eligibility, and safe stock-plus-expanded composition. Required future lines are exactly `Skipped over X villagers. Reason: already likes running` and `Removed running dislike from X villagers`; the proposed full-slot line remains future-only pending capacity proof. The main Official LDW Cheat Tables is the primary vanilla-name set; Official LDW Cheat Tables  (Backup!!) backs up Main for recovery/version comparison. Official LDW Cheat Tables - Copy is strong player-confirmed runtime evidence used with renamed/copied base-game executables whose filenames contain - Copy or a variation; translating its addresses still requires fingerprinting the underlying executable and accounting for process/module-name-dependent Cheat Engine scripts. Exact executable evidence controls.",
        "",
        "VV3 resolution commits `531b0aca8d5bf051f87773e67d48b61c0ba02833` and `1d9a39da078806aa940e4774a9068956e88347bc` close exact ID 38, three Like plus three Dislike DWORD slots at +0xFB4..+0xFC8, sentinel -1, stride 0x1F8C, supplied 150/256 bounds, persistence, the write-only preference interval, atomic ordering, and dry-run/no-charge/final unsigned recheck requirements. Its four future lines are `Added Running Like to %u villagers`, `Skipped over %u villagers. Reason: already likes running`, `Removed running dislike from %u villagers`, and `Skipped over %u villagers. Reason: all like slots are occupied`. VV3 remains ON HOLD: +0xE94 status semantics are unresolved; commands 6/7/8 occupy one 944-byte atomic payload at file 0x7B820 with shared entry 0x7B840/VA 0x47B840; 0x582644 precharges and 0x7B7A0 is only a header check; the three-counter 128-byte ABI lacks granted; hooks 0x6547D/0x65640 and payload 0xA3180 mix unrelated Origins mechanics; command-6-only UI guards and a complete appended-section relocation/uninstall/all-patch ledger are absent.",
        "",
        "## Origins village-wide atomic-payload containment",
        "",
        "All five `vvN_origins_village_wide_upgrades` records are disabled and absent from the catalog, GUI, CLI, Select All, dependency resolution, and rendered outputs. Commands 6, 7, and 8 share one atomic payload, so All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18 remain unavailable together until each game receives a full-payload GO gate. VV4 audit `628e0d9217b92b9cd695655842b09d74689a0238` proves that direct 90.0 mastery stores bypass eight native mutations. VV5 audit `02581c8f518e27ebd5fc7d2972db5597ab08ed35` records unresolved counter, eligibility, no-change, inheritance, and expanded-layout requirements. VV3 audit `089957227c0db6a4c3128045519ffa27b201a00e` confirms five signed DWORD skills at +0xEAC..+0xEBC, mastery 88, native maximum 100, and native all-five evaluation/award ID 4; the candidate direct 90 stores are not full mastery and bypass that evaluation, while zero-change/no-charge behavior, creation/inheritance, and placement remain unresolved. VV1 is not certified. Disabled manifests retain diagnostic payload bytes but apply none of them; containment does not touch save fields, force-clear ownership, or issue refunds. Base Origins remains independently available except for the separately contained VV2 pair.",
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
