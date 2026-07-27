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
