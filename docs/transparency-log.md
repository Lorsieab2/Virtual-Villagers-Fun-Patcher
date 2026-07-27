# Virtual Villagers Fun Patcher — Transparency Coverage

This document is generated from the patch manifests. It is the project-level description of the differences the patcher can request; the per-output `VVFP Transparency Log.txt` is the authoritative record of the exact bytes and files used for one output.

## Automatic changes (every output)

Every output applies the selected population mode and the game's guarded population-safety edits. The collection-progression mode preserves the supported game's collection/bonus behavior while changing its declared maximum according to the manifest. The immediate-fixed mode keeps the fixed maximum. Experimental expanded-256 modes additionally apply the documented stock-save import/conversion route and physical-record expansion for VV3–VV5; VV1/VV2 already have 256 physical slots. Multiples and population-adding Island Events are saturated at the physical slot bound. No game is launched by the patcher, so runtime/player confirmation remains pending.

Available population modes: Collection Progression Max Pop, Immediate Fixed Max Pop, Experimental Expanded 256 Villagers, Experimental Expanded 256 - Collection Progression.

## Optional-patch chooser catalog

The desktop chooser presents game-scoped optional patches under the five manifest titles in this fixed order: A New Home, The Lost Children, The Secret City, The Tree of Life, and New Believers. Within each title, entries sort by case-folded display name and then patch ID. Unknown or all-games entries appear under a final `Shared / All Games` header. Checkbox variables remain keyed by patch ID; Select All, Deselect All, dependency closure, and persisted selections operate on those same variables. This is presentation-only: it changes no executable bytes, save fields, companion DLLs, or game behavior.

## Origins doubler evidence boundary

The per-game positive food/tech writer, collection-adjustment callsites, and every Island Event producer must be proved independently before an Origins doubler is considered complete. The requested final composition is per-game: Tech Point Doubler stacks with every proven collection effect that increases tech gain; Food Point Doubler stacks after Food Mastery only where that exact build proves the modifier. Golden Child is a VV1-only exclusion, Gong of Wonder is a VV2-only exclusion, and Island Event exclusions follow each game's inventory. Excluded outcomes (positive, zero, or negative) remain native. The current exact-build candidate exclusions and pending/STOP statuses are recorded in `docs/doubler-composition-audit.md`; return-address checks alone are not treated as exhaustive provenance proof.

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

#### Enable Origins Village-Wide Upgrades (`vv1_origins_village_wide_upgrades`)

Adds three optional, current-save-only Origins upgrades to the Tech-screen Upgrades window, inspired by the Virtual Villagers 1 mobile port's selected exclusive upgrades: All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18. Each costs exactly 1,000,000 tech points. Running uses the build-specific preference ID proven from the stock preference table, preserves unrelated Likes, removes Running Dislikes, and reports `Skipped over X villagers. Reason: Already 3 likes.`, `skipped over Y villagers. Reason: already likes running`, plus `Removed running dislike from X villagers` only when applicable. Mastery writes only the native skill fields. Age changes only the displayed age to 18 and does not change nursing or pregnancy timers.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager. Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv1_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x7B260.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
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

#### Easier Healing Mastery (`vv2_easier_healing_mastery`)

Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.

- Behavior changes: Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 2; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins Village-Wide Upgrades (`vv2_origins_village_wide_upgrades`)

Adds three optional, current-save-only Origins upgrades to the Tech-screen Upgrades window, inspired by the Virtual Villagers 1 mobile port's selected exclusive upgrades: All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18. Each costs exactly 1,000,000 tech points. Running uses the build-specific preference ID proven from the stock preference table, preserves unrelated Likes, removes Running Dislikes, and reports `Skipped over X villagers. Reason: Already 3 likes.`, `skipped over Y villagers. Reason: already likes running`, plus `Removed running dislike from X villagers` only when applicable. Mastery writes only the native skill fields. Age changes only the displayed age to 18 and does not change nursing or pregnancy timers.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager. Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv2_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x8B808.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv2_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with a Time Warp that advances exactly three displayed villager years, Island Event, the native Barrel of Babies event with a three-space reserved-population guard, and removable 500,000-tech-point Tech Point and Food Point Doublers, plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. Doubler ownership is confined to the current save. The certified composition applies after native collectible adjustments; Food Mastery presence is still being verified for this build. Island Event and Gong of Wonder outcomes remain native, including zero/negative and side-effect paths. The exact-build static provenance audit covers every positive Island Event and Gong food/tech writer callsite, including direct resource writes that bypass the wrappers. Runtime/player confirmation remains pending. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running uses an available normal Likes slot, removes Running from the displayed villager's Dislikes, refuses without charging when all normal Like slots are occupied, and changes no movement-speed value, predicate, or other vanilla speed logic. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with a Time Warp that advances exactly three displayed villager years, Island Event, the native Barrel of Babies event with a three-space reserved-population guard, and removable 500,000-tech-point Tech Point and Food Point Doublers, plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. Doubler ownership is confined to the current save. The certified composition applies after native collectible adjustments; Food Mastery presence is still being verified for this build. Island Event and Gong of Wonder outcomes remain native, including zero/negative and side-effect paths. The exact-build static provenance audit covers every positive Island Event and Gong food/tech writer callsite, including direct resource writes that bypass the wrappers. Runtime/player confirmation remains pending. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running uses an available normal Likes slot, removes Running from the displayed villager's Dislikes, refuses without charging when all normal Like slots are occupied, and changes no movement-speed value, predicate, or other vanilla speed logic.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x8B808.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - The Lost Children.exe', 'size': 724992, 'sha256': '46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677'}, 'positive_tech_writer': '0x426290', 'positive_food_writer': '0x4262B0', 'collection_adjustment': 'No separate global collection multiplier exists in either final writer; every eligible caller passes the final native signed delta, so the wrapper doubles that positive delta after all caller-side collection arithmetic.', 'island_event_handlers': {'two_choice_handler': {'function': '0x4204B0', 'tech_returns': ['0x4205AC'], 'food_returns': ['0x420AE9'], 'direct_resource_paths': ['direct +3000 tech result and deductions/caps bypass the positive writers']}, 'single_result_dispatcher': {'function': '0x433600', 'tech_returns': ['0x434351'], 'food_returns': ['0x433FC6'], 'direct_resource_paths': ['losses, caps, halves, resets, and unrelated resources bypass positive writers']}}, 'gong_of_wonder': {'function': '0x44E8A0', 'registered_action': 164, 'invoked_by': '0x461B10', 'tech_returns': ['0x44EA32', '0x44ED52', '0x44F202'], 'food_returns': ['0x44E9C3', '0x44EDB9', '0x44F0D9'], 'direct_resource_paths': ['negative tech and reset/zero outcomes bypass positive writers']}, 'tech_blacklist_returns': ['0x4205AC', '0x434351', '0x44EA32', '0x44ED52', '0x44F202'], 'food_blacklist_returns': ['0x420AE9', '0x433FC6', '0x44E9C3', '0x44EDB9', '0x44F0D9'], 'direct_call_inventory': {'tech': ['0x4205A7/0x4205AC', '0x43434C/0x434351', '0x4385E1/0x4385E6', '0x438741/0x438746', '0x4388A1/0x4388A6', '0x438A9B/0x438AA0', '0x438C7B/0x438C80', '0x438E5B/0x438E60', '0x44EA2D/0x44EA32', '0x44ED4D/0x44ED52', '0x44F1FD/0x44F202', '0x46345C/0x463461', '0x463468/0x46346D', '0x463474/0x463479', '0x463737/0x46373C', '0x4637C0/0x4637C5', '0x463809/0x46380E'], 'food': ['0x420AE4/0x420AE9', '0x433FC1/0x433FC6', '0x438293/0x438298', '0x438371/0x438376', '0x438445/0x43844A', '0x44E9BE/0x44E9C3', '0x44EDB4/0x44EDB9', '0x44F0D4/0x44F0D9', '0x463198/0x46319D', '0x463259/0x46325E', '0x463312/0x463317', '0x463364/0x463369', '0x4633CD/0x4633D2'], 'e9_tail_jumps_to_writers': 0}, 'hook_status': 'GO: exact-build static provenance proof complete for all positive Island Event and Gong writer callsites; runtime/player confirmation pending'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes', 'Gong of Wonder outcomes'], 'food_mastery_status': 'pending exact-build verification; no cross-game assumption', 'status': 'GO: exact-build static provenance covers the certified positive writer paths; runtime/player confirmation pending'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

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

#### Enable Origins Village-Wide Upgrades (`vv3_origins_village_wide_upgrades`)

Adds three optional, current-save-only Origins upgrades to the Tech-screen Upgrades window, inspired by the Virtual Villagers 1 mobile port's selected exclusive upgrades: All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18. Each costs exactly 1,000,000 tech points. Running uses the build-specific preference ID proven from the stock preference table, preserves unrelated Likes, removes Running Dislikes, and reports `Skipped over X villagers. Reason: Already 3 likes.`, `skipped over Y villagers. Reason: already likes running`, plus `Removed running dislike from X villagers` only when applicable. Mastery writes only the native skill fields. Age changes only the displayed age to 18 and does not change nursing or pregnancy timers.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager. Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv3_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x97488.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv3_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with Time Warp, Island Event, the native Another One of Those Barrels event with a dynamic three-space 150/256-record guard, and displayed-but-currently-unavailable 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. Time Warp advances every villager by exactly 3 displayed years at every active game speed; the required wall-clock shift is 3 hours at half speed, 6 hours at normal speed, and 10 hours at double speed. Doubler ownership is confined to the current save. The doubler contract would stack after the exact collectible/collection adjustment, but this build's collection dispatcher has unresolved computed/indirect reachability and no safe final-delta hook. Food Mastery-like award transforms are confirmed absent in the writer, strings, and bounded caller corpus. Island Event outcomes remain native; new purchase and repurchase are unavailable under the exact-build STOP gate. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only uses an available normal Likes slot on the displayed villager and removes Running from that villager's Dislikes; it refuses without charging when all normal Like slots are occupied and does not alter any movement behavior or speed value. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen with Time Warp, Island Event, the native Another One of Those Barrels event with a dynamic three-space 150/256-record guard, and displayed-but-currently-unavailable 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`. Time Warp advances every villager by exactly 3 displayed years at every active game speed; the required wall-clock shift is 3 hours at half speed, 6 hours at normal speed, and 10 hours at double speed. Doubler ownership is confined to the current save. The doubler contract would stack after the exact collectible/collection adjustment, but this build's collection dispatcher has unresolved computed/indirect reachability and no safe final-delta hook. Food Mastery-like award transforms are confirmed absent in the writer, strings, and bounded caller corpus. Island Event outcomes remain native; new purchase and repurchase are unavailable under the exact-build STOP gate. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only uses an available normal Likes slot on the displayed villager and removes Running from that villager's Dislikes; it refuses without charging when all normal Like slots are occupied and does not alter any movement behavior or speed value.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0x97488.
- Doubler evidence matrix: {'positive_tech_writer': '0x427130', 'positive_food_writer': '0x4263F0', 'collection_adjustment': {'dispatcher': 'sub_42DEB0', 'tech_writer': '0x42DF79', 'food_writer': '0x42E079', 'tech_awards': {'100': 'IDs 52-55, 64-67, 76-79, 88-91', '250': 'IDs 56-59, 68-71, 80-83, 92-95', '1500': 'IDs 60-63, 72-75, 84-87, 96-99'}, 'caller_status': 'IDA has no resolved caller to sub_42DEB0; computed/indirect reachability remains unresolved'}, 'island_event_producers': {'dispatcher': '0x458DB0-0x45943F', 'inventory': 'complete positive/zero/negative/bypass inventory including tail calls; mixed-source writers have no source tag', 'final_delta': 'sub_458DB0 emits base and bonus components through separate tech-writer calls; no single final-delta boundary is proved'}, 'writer_inventory': {'food': {'rows': 33, 'calls': 29, 'e9_tails': 4}, 'tech': {'rows': 16, 'calls': 13, 'e9_tails': 3}}, 'tail_sites': {'food': ['0x415EF1', '0x416983', '0x416BAB', '0x417A3A'], 'tech': ['0x415D44', '0x41673E', '0x418452']}, 'hook_status': 'STOP: no safe final-delta/source-aware hook, transient marker, or certified new section/cave; computed/indirect collection reachability remains unresolved'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'confirmed absent in the exact-build writer, strings, and bounded caller corpus', 'status': 'STOP: no safe final-delta/source-aware hook, transient marker, or certified new section/cave; Island Event mixed-source provenance and collection dispatcher caller remain unresolved'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 10; every edit has an exact purpose and before/after guard in the manifest.

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

#### Enable Origins Village-Wide Upgrades (`vv4_origins_village_wide_upgrades`)

Adds three optional, current-save-only Origins upgrades to the Tech-screen Upgrades window, inspired by the Virtual Villagers 1 mobile port's selected exclusive upgrades: All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18. Each costs exactly 1,000,000 tech points. Running uses the build-specific preference ID proven from the stock preference table, preserves unrelated Likes, removes Running Dislikes, and reports `Skipped over X villagers. Reason: Already 3 likes.`, `skipped over Y villagers. Reason: already likes running`, plus `Removed running dislike from X villagers` only when applicable. Mastery writes only the native skill fields. Age changes only the displayed age to 18 and does not change nursing or pregnancy timers.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager. Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv4_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xA0CD8.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv4_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen. Time Warp advances exactly 3 displayed villager years at half, normal, and double speed; Island Event uses the stock scheduler; Barrel of Babies opens the native event and requires three free physical villager records in either the 150- or 256-record game. Adds displayed-but-currently-unavailable, current-save-only 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`; the pending doubler contract stacks after exact-build collectible and Food Mastery adjustments, while Island Event outcomes remain native; purchase is unavailable until those paths are proven. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only adds Running to a free normal Like slot and removes it from Dislikes; it refuses without charging when Likes are full and never changes any movement or speed logic or value. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds the icon-based Origins Upgrades screen. Time Warp advances exactly 3 displayed villager years at half, normal, and double speed; Island Event uses the stock scheduler; Barrel of Babies opens the native event and requires three free physical villager records in either the 150- or 256-record game. Adds displayed-but-currently-unavailable, current-save-only 500,000-tech-point Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`; the pending doubler contract stacks after exact-build collectible and Food Mastery adjustments, while Island Event outcomes remain native; purchase is unavailable until those paths are proven. Adds Villager Upgrades for Grant Youth, Grant Full Mastery, Grant Running, and Set Age to 18. Grant Running only adds Running to a free normal Like slot and removes it from Dislikes; it refuses without charging when Likes are full and never changes any movement or speed logic or value.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xA0CD8.
- Doubler evidence matrix: {'build': {'filename': 'Virtual Villagers - The Tree of Life.exe', 'size': 929792, 'sha256': '6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220'}, 'positive_tech_writer': '0x41E300', 'positive_food_writer': '0x41D920', 'collection_adjustment': 'Food Mastery is applied inside sub_41D920: level 0/1=A, level 2=A+floor(A/2), level 3=2A. Collection call 0x414660 passes pre-mastery 6/35, so any eligible doubler must follow the native transform.', 'external_xref_inventory': {'tech': 21, 'food': 23}, 'tail_jump_sites': ['0x4156F8', '0x415862', '0x41586F', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x416735', '0x41520E'], 'ordinary_positive_sites': {'tech': ['0x414477', '0x414493', '0x4144AF', '0x431A9B'], 'food': ['0x414660', '0x436F15']}, 'island_event_positive_sites': {'tech': ['0x414A28', '0x4156F8', '0x415862', '0x415A81', '0x415B46', '0x415D8C', '0x416722', '0x464E58', '0x464E82', '0x464EAB'], 'food': ['0x414949', '0x41520E', '0x4643E6', '0x464433', '0x464492', '0x46450B', '0x464573', '0x4645B0', '0x4645FB']}, 'hook_status': 'STOP: inventory is complete, but no safe post-Food-Mastery doubler hook has been implemented; return-address-only exclusion is invalid for the listed E9 tails'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'confirmed in exact-build disassembly; native transform documented in doubler evidence', 'status': 'STOP: no safe post-Food-Mastery hook/section and incomplete dynamic/computed Island Event provenance'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 11; every edit has an exact purpose and before/after guard in the manifest.

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

#### Enable Origins Village-Wide Upgrades (`vv5_origins_village_wide_upgrades`)

Adds three optional, current-save-only Origins upgrades to the Tech-screen Upgrades window, inspired by the Virtual Villagers 1 mobile port's selected exclusive upgrades: All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18. Each costs exactly 1,000,000 tech points. Running uses the build-specific preference ID proven from the stock preference table, preserves unrelated Likes, removes Running Dislikes, and reports `Skipped over X villagers. Reason: Already 3 likes.`, `skipped over Y villagers. Reason: already likes running`, plus `Removed running dislike from X villagers` only when applicable. Mastery writes only the native skill fields. Age changes only the displayed age to 18 and does not change nursing or pregnancy timers. Only eligible living believers are processed; Heathens are excluded and remain untouched.

- Behavior changes: Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed. Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save. Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager. Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers. All Villagers are 18 writes only the verified displayed-age field to 360 age units.
- Explicit non-changes/exclusions: No unrelated Like is replaced or removed. No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written. The upgrades are save-scoped and do not set a global ownership bit. VV5 Heathens are excluded from all three village-wide operations.
- Dependencies: vv5_enable_origins_exclusive_features
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xAEF60.
- Evidence status: static exact-build payload and field-map verification performed; runtime/player confirmation pending
- Guarded executable edits: 1; every edit has an exact purpose and before/after guard in the manifest.

#### Enable Origins-Exclusive Features (`vv5_enable_origins_exclusive_features`)

Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds icon-based Origins Upgrades. The native Time Warp (the stock route advances exactly 3 displayed villager years), Island Event, and Barrel of Babies rows are retained but disabled until their Heathen-safe target paths are proved; selecting one reports that it is unavailable. Adds displayed-but-currently-unavailable, save-scoped Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living believer records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`; Heathens are excluded. Villager Upgrades include Grant Youth (floor age 5), six-skill Full Mastery, Set Age to 18, and Grant Running. Grant Running only adds the build-specific Running preference ID (proven at table offset 0xAEF60) to a free normal Like slot and removes that same ID from Dislikes; it never changes movement or speed logic. The pending doubler contract stacks after exact-build collectible adjustments; Food Mastery presence is still being verified for this build. Island Event outcomes remain native; purchase is unavailable until those paths are proven. Inspired by the Virtual Villagers 1 mobile port, where selected Origins-exclusive upgrades originated; this wording does not claim unsupported mobile parity.

- Behavior changes: Inspired by the Virtual Villagers 1 mobile port where these exclusive Origins upgrades originated, this selected-upgrades port adds icon-based Origins Upgrades. The native Time Warp (the stock route advances exactly 3 displayed villager years), Island Event, and Barrel of Babies rows are retained but disabled until their Heathen-safe target paths are proved; selecting one reports that it is unavailable. Adds displayed-but-currently-unavailable, save-scoped Tech Point and Food Point Doublers. Existing owned doublers remain removable at zero cost with zero refund; repurchase is temporarily disabled pending exact-build verification. Plus Cure all Villagers for 30,000 tech points. Cure all Villagers clears sickness from eligible active living believer records without changing health and increments People Cured once per sickness cleared, then displays the exact result `Cured X villagers`; Heathens are excluded. Villager Upgrades include Grant Youth (floor age 5), six-skill Full Mastery, Set Age to 18, and Grant Running. Grant Running only adds the build-specific Running preference ID (proven at table offset 0xAEF60) to a free normal Like slot and removes that same ID from Dislikes; it never changes movement or speed logic. The pending doubler contract stacks after exact-build collectible adjustments; Food Mastery presence is still being verified for this build. Island Event outcomes remain native; purchase is unavailable until those paths are proven.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Build-specific Running preference ID: 38; evidence source: exact stock executable embedded preference table at table offset 0xAEF60.
- Doubler evidence matrix: {'positive_tech_writer': '0x4237B0', 'positive_food_writer': '0x41EB6F before stock statistics hook', 'collection_adjustment': 'not independently recorded; no exact callsite claim', 'island_event_producers': ['event methods 0x414A30-0x416CD0; tail-jump coverage unresolved'], 'hook_status': 'STOP until every direct and tail-jump Island Event path is proven'}
- Doubler composition contract: {'stacking': ['every exact-build collectible/collection effect that increases tech-point gain', 'native Food Mastery technology adjustment'], 'exclusions': ['Island Event outcomes'], 'food_mastery_status': 'pending exact-build verification; no cross-game assumption', 'status': 'STOP until every direct and tail-jump producer/call path is proven'}
- Doubler purchase status: {'new_purchase': 'temporarily unavailable pending exact-build provenance verification', 'existing_owned': 'removable at zero cost with zero refund', 'repurchase': 'temporarily disabled pending exact-build provenance verification'}
- Native event safety: {'disabled_rows': ['Time Warp', 'Island Event', 'Barrel of Babies'], 'reason': 'VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.', 'evidence_status': 'STOP; no charge or native call is made for these rows'}
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 12; every edit has an exact purpose and before/after guard in the manifest.

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

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Behavior changes: After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.
- Explicit non-changes/exclusions: none declared
- Dependencies: none
- Evidence status: static source/manifest verification performed; runtime/player confirmation pending
- Guarded executable edits: 5; every edit has an exact purpose and before/after guard in the manifest.

## Transparency and validation boundaries

Each successful output writes `VVFP Transparency Log.txt` beside the modified executable and a machine-readable `.patch-log.json`. The text report is written through a temporary file only after the executable, companions, and source/output tree have been verified; its SHA-256 is recorded in JSON without self-hashing the JSON. The report lists the stock and modified hashes, every applied edit grouped by owner, PE layout/checksum differences, file additions/modifications/removals, save handling, selected feature predicates/costs/exclusions, static checks, and the explicit runtime/player-confirmation-pending status.

Historical counters that are not persisted in a save cannot be reconstructed from a current save. The statistics exporter therefore reports persisted per-save counters and derives current puzzle completion (including VV5 Puzzle 17 when the save records it) at export time.
