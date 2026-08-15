# Universal permanent-purchase transaction contract

This is a disabled, reference-only evidence gate. It emits no bytes, owns no
hooks or resources, and is not loaded by the public catalog.

**Shipping disposition:** The public VV2 Origins patch ships Complete All
Collections and Reset All Collections as village-wide Tech rows implemented in
the companion DLL (`native/vv2_origins_icons/vv2_origins_icons.c`,
`ApplyVV2Collections`), each costing 1,000,000 tech points and charging only
when the collection state actually changes (no charge when everything is
already found, or already cleared). That is a deliberately shipped,
player-verified feature on a **different track** from the native exact-build
transaction this contract models. This gate is intentionally retained as a
reference-only STOP record of that native track; it is not a claim that the
shipped DLL rows are absent, and it still emits no bytes.

The inventory covers the shared Tech rows, four selected-villager rows, three
village-wide rows, Reset Collectibles, Complete All Collectibles, Equal Division, VV1's omitted
mobile Bump Max Population action, and VV5 Food Mastery levels 2 and 3.
Reset Collectibles and Complete All Collectibles are planned VV2–VV5
village-wide actions at exactly 1,000,000 tech points each. Their native
placement and implementation remain explicitly unproven.

Every game/action pair currently has all fourteen evidence gates open:
dry-run; natural zero/one/many prompt; exact IDOK; world/index/pointer/snapshot
and funds/account reacquisition; eligibility-before-read ordering; native
setter and readback; notifications/statistics; postverification; exactly one
post-success deduction; all no-charge exits; guarded rollback and truthful
partial/unknown-charge disclosure; fullscreen ownership/restoration; and
composition/Expanded proof.

Only owned Tech/Food Doublers may show Remove. Event, individual,
village-wide, healing, mastery, Running, Collections, and labor actions are
Buy-only where their UI is known. Missing evidence stops only that action and
cannot prevent unrelated catalog loading.

## Current per-game result

| Game | Inventory | Result |
|---|---:|---|
| VV1 | 19 actions | STOP: unsafe legacy routes, collectibles actions not applicable |
| VV2 | 19 actions | STOP: Origins contained; collectibles actions proposed but absent |
| VV3 | 19 actions | STOP: partial candidates only; collectibles actions proposed but absent |
| VV4 | 19 actions | STOP: partial candidates only; collectibles actions proposed but absent |
| VV5 | 19 actions | STOP: UI/native/player and lifecycle gates open |

The machine-readable matrix reports the same exact fourteen missing evidence
classes for every one of the 95 game/action bindings. The most reusable native
gaps are the game-specific selected/world resolver with stable identity, the
native funds account/readback/deduction route, and native age and preference
setters with readback. Direct stores and adjacent-game ABIs do not satisfy
those gates.

Additional action-specific gaps remain: event scheduling and population
capacity for Time Warp/Event/Barrel; ownership and eligible-award provenance
for doublers; sickness, exact-health and People Cured routes for Full Heal;
skill/evaluator semantics for Full Mastery; all physical Like/Dislike slots
and preference side effects for Running; and complete native implementations
for Collections and Equal Division. VV1 Bump Max Population is inventoried as
an omitted mobile action, not a desktop row. VV5 Food Mastery is recorded as
two stock level purchases rather than reused as evidence for another game.

Even a synthetically complete evidence object cannot set publication true;
publication requires a separately reviewed implementation assignment.
