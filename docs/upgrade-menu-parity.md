# Upgrade-menu parity contract

`data/upgrade_menu_parity_contract.json` is the current production contract for
the visible Origins-style Tech and Villager Details menus in VV1 through VV5.
It is intentionally separate from historical candidate, STOP, forensic, and
player-pending evidence records.

## What is fixed

The contract fixes the visible shell and prompt vocabulary:

- Tech caption: `Origins Upgrades`.
- Details caption: `Villager Upgrades`.
- Every active menu has `Cancel` control ID 2 and the hint `Press ESC to exit this menu.`.
- The common purchase prompt is `Do you want to buy %s for %s tech points?`, followed by `Press OK to confirm, or Cancel.`.
- Owned upgrades use an explicit `Remove` button with no purchase prompt. The
  result uses the no-refund grammar recorded in the JSON contract:
  `%s was removed. No refund was issued.` VV2's historical Buy-on-Remove path
  and VV3's historical removal prompt are not the contract.
- A selected-villager genetics change uses `Warning: This will change the villager's head genetics.`.
- A village-wide head change uses the selected-sex warning that identifies descendant impact and ends with `Proceed?`.

The ordered action rows, exact control IDs, labels, numeric costs, and formatted
cost text are authoritative in the `actions.tech` and `actions.details` arrays.
VV1 omits Collections as `omitted_not_applicable`; VV2 uses resource IDs 211
(Tech) and 212 (Details). VV3 dialog 203 remains a dormant historical route and
is not promoted by this contract.

## Architecture boundaries

The stock VV5 shell and prompt wording are the observable visual reference, not
a universal transaction-order reference. Each action retains its own proven
native ABI, revalidation, mutation, readback, persistence, and charge strategy.
The per-game owner and separate Tech/Details visibility strategies are recorded
under `games` in the JSON. They intentionally differ: VV4 Details keeps all
five rows clickable with informational checkmarks/no-op results, VV1 uses a
Done/disabled Details terminal state, and VV3/VV5 disable satisfied Details
rows. VV5 uses the captured same-process `BeginOriginsOwner` /
`GetOriginsOwner` / `EndOriginsOwner` lifecycle; the other games retain their
build-specific fullscreen preparation and modal owner routes.

VV5 Expanded has a deliberately limited capability boundary. Its companion
marks Tech rows 6–13 and Details row 4 as `Unavailable` and disabled through
`STATE_LIMITED_CAPABILITY` (0x400000, the first bit above the dialog's row and
unavailable masks). Those controls must not remain enabled and fall
through to a no-op result.

## Evidence boundary

Source/resource tests validate the contract against the active `.rc` templates
and native dialog procedures. This establishes source agreement only. It does
not establish that a player saw the menu, that a native write persisted, or that
the final charge was correct. Those claims remain `needs_player_confirmation`
until the runtime checklist in the JSON is completed on the exact builds.

The contract does not modify or reinterpret existing forensic contracts. In
particular, historical disabled/hidden routes remain governed by their existing
manifests and evidence gates.

## Expanded Time Warp evidence boundary

`include_expanded_time_warp=True` is an explicit evidence-loader path; it does
not make either experimental mode catalog-visible or re-enable removed modes.
The VV3 manifest, map, and core retain their authenticated frozen archival
bindings and companion identity. The current tree cannot regenerate the full
VV3 composition because the experimental patch modes were removed, so the
loader does not claim current builder/companion reproducibility. Its independent
proof is limited to the frozen `build_page()` page hash
(`D169B49C63731970FBE832256C8975806301EE16FC872C6F1B608C6E1FB73C92`) and
authenticated artifact cross-equality; runtime and player confirmation remain
pending. VV5 uses the current regenerated manifest/map companion identity
(1,753,088 bytes) and final overlay string offset `0xFB0C9`.
