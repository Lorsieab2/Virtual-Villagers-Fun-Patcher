# Origins Player Runtime Checklist

## Current village-wide safety containment

Do not test or purchase All Villagers Like Running, Grant Full Mastery to All
Villagers, or All Villagers are 18 in the current build. All five
`vvN_origins_village_wide_upgrades` records are disabled because commands
6/7/8 share one atomic payload and Full Mastery lacks a complete per-game GO
gate. The diagnostic manifests remain available to static tests only; no
village-wide bytes are applied. Existing save fields and ownership are left
untouched, with no forced clear and no refund. The historical procedures below
are retained as the future player-validation contract, not as currently
available rows.

All Villagers Like Running is independently ON HOLD for VV1-VV5 under audit
`0311443fbd078e3adcabaf7e693199989ddb9db8` and evidence clarification
`a67e05247dc822306e1d5a514524cba388ab4d69`. Running ID 38 is independently
code-confirmed in each exact build. The persisted models are four Like/four
Dislike DWORD slots in VV1, 62/62 in VV2, and three/three in VV3-VV5, with
signed `-1` as empty. Future validation requires strict atomic behavior:
already-like skips the entire villager; otherwise preflight a free Like before
removing any Running Dislike; full Likes causes no mutation; unrelated slots
and ordering remain unchanged. VV5 current faction `+0x1CEC != 0` must be
rejected before any preference access or count, and `+0x1CE1` is not an
approved eligibility gate. The current disabled helpers do not meet this
contract, so the historical runtime procedure below must not be run.

For VV3 specifically, resolution commits
`531b0aca8d5bf051f87773e67d48b61c0ba02833` and
`1d9a39da078806aa940e4774a9068956e88347bc` close the three-plus-three
slot operation, persistence, atomic ordering, four counters, and
dry-run/no-charge/final unsigned recheck contract. Runtime validation remains
forbidden because `+0xE94` status eligibility, independent command-6 UI,
four-counter bounded result ABI, and complete stock/expanded placement and
uninstall composition are unresolved. The shared 944-byte commands 6/7/8
payload and unrelated base Origins hooks cannot be enabled selectively.

VV3 Full Mastery is specifically ON HOLD under exact-build audit
`089957227c0db6a4c3128045519ffa27b201a00e`. Its five signed DWORD skills are
`+0xEAC..+0xEBC`; mastery begins at 88, the native maximum is 100, and native
all-five evaluation uses award ID 4. The disabled candidate's direct 90 stores
are not full mastery and bypass that post-write evaluation. Zero-change/no-
charge behavior, creation/inheritance, and safe placement remain unresolved.

VV2 Full Mastery is also ON HOLD under exact-build audit
`60f649bf90b55dea3a6856d949e123bd79808782`. The five signed DWORD skills are
`+0x7E4..+0x7F4`, followed by job preference `+0x7F8`; Master begins at 88 and
native award paths cap at 100. Save/load persists the fields across 256 records
at stride `0xE48C`. The disabled candidate iterates active `+0x30`, positive
signed health `+0x52C`, writes 90, returns no changed count, and can charge the
generic 1,000,000-point transaction without a no-change result or rollback.
Creation/inheritance/Silver Mirror closure, native all-five side effects, and
safe `.shr` transport/placement remain unresolved. Gong and every Island Event
route remain native and outside this command.

VV1 Full Mastery is ON HOLD under audit
`e0bed87ce17dca5331afed1abc2d753ec3d8f0aa`. Its five signed DWORD skills are
`+0x3BC..+0x3CC`, followed by preference `+0x3D0`; Master begins at 90 and
native awards cap at 100. Save packing persists them across 32 records at
stride `0x3D8`. The candidate checks occupied `+0x28` and positive signed
health `+0x344`, writes 90 while leaving preference unchanged, and returns no
changed count. Its `state+0xA2FC` transaction lacks a changed-record preflight,
commit recheck, no-charge result, and rollback. Target 90/100 semantics,
preference/title policy, distributed side effects, creation/clone policy,
strict Golden Child/Event bypass, and placement/composition remain unresolved.

VV5 All Villagers are 18 is ON HOLD under audit
`aaddf71797c28f37b0cc1f5728e567c0601a05aa`. Displayed age is signed DWORD
`+0x1B8C`, with 20 units per year and 360 for age 18. Native refresh,
ordinary/offline increment, oldest-villager statistic, and save persistence
are mapped. The candidate raw store bypasses that native route and differs from
the selected-age path's `+0x1C3C` and nonzero `+0x1C4C` writes. Its active,
health, and current-believer tests include an unproved `+0x1CE1` exclusion;
its one-million-point transaction charges no-op/already-18 cases and returns
zero results. Nursing timer and nursing/pregnancy state must never change, and
the current helper is not proved to meet that requirement. The 43-reference
expanded relocation gap remains open.

VV4 All Villagers are 18 is ON HOLD under audit
`ab404b0c5e80cab4d327de9a51069e6e3529df27`. For exact build
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`,
displayed age is signed DWORD `+0x1B8C`, 20 units per year, with 360 meaning
age 18. Native detail refresh, increment, offline aging/oldest-stat update, and
save persistence are mapped. The candidate iterates stride `0x2E3C` over a
supplied 150/256 bound using active `+0x1CC4`, status `+0x1CC7 == 0`, and
positive signed health `+0x1C40`. Its raw store and generic unsigned
one-million-point transaction bypass native transition handling, charge no-op
cases, return zero results, and provide no rollback. Processed age `+0x1C3C`,
nursing/pregnancy companion `+0x1C4C`, pending baby count, and unrelated fields
must never change; the candidate is not proved to satisfy the complete
semantic contract. Future births, clones, Events, and stock/expanded placement
remain unresolved.

VV3 All Villagers are 18 is ON HOLD under audit
`cee9a195faed187c847672bf36d46935a9f67ad3`. For exact build
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`,
target/display age is signed DWORD `+0xDC4`, 20 units/year, and 360 means age
18. Native elapsed updater `sub_45F3E0` calls `sub_45C640` at `0x45F5C6`,
then updates the oldest statistic; catch-up `sub_45FFE0` advances distinct
processed age `+0xE74` one unit at a time through native life simulation. The
command-8 raw store leaves those dual ages unsynchronized. The selected-age
candidate changes `+0xE74` and nonzero `+0xE8C`, which violates the mandatory
nursing timer/state non-change rule. Neither route is approved. Ordinary/
status eligibility, no-op charging and zero results/no rollback, future
Event/birth/clone exclusions, and stock/expanded placement remain unresolved.

VV2 All Villagers are 18 is ON HOLD under audit
`bd6ce555a9a197450aab7133c0a87b36fbfc6899`. Exact build
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`
uses target/display age `+0x530`, processed age `+0x534`, 20 units/year, and
360 for age 18. Native `sub_43B690` advances target at `0x43B8FD`, updates the
oldest statistic, runs life simulation, and increments processed age at
`0x43C09A`. Command 8 changes only target age. Pregnancy writer `sub_44B980`
stores processed age in `+0x540`, with delivery at `marker + 40 < processed
age`; the selected-age candidate rewrites both ages and a nonzero marker to
318, so it violates mandatory nursing-state preservation. The 256-slot
stride-`0xE48C` scan tests active `+0x30`/health `+0x52C` but omits `+0x558`.
Its precharged `state+0x2EADC` transaction returns zero without no-op refusal,
recheck, or rollback. Love Note `0x422006`, Gong `0x44EB3E`, and Silver Mirror
`0x4217F9` remain separate native paths; full origin classification is not
claimed. The withdrawn non-executable `.shr` transport retains its `0x2000`
mapping error.

For any future Full Mastery validation, the required value is native maximum
100 in every skill—five skills in VV1–VV4 and six in VV5—not merely a Master
threshold. This requirement does not make any contained row available.

This is a player-test checklist for the collection-progression Origins-core
outputs. It is explicitly **runtime/player confirmation pending**; static patch
verification is not a claim that any item below has been confirmed in-game.
The former complete all-five output at
`outputs/origins-core-village-wide-playtest-all-five-collection-progression-2026-07-27`
is historical and superseded by the current VV5 stock-layout Tech/Food Doubler
implementation. Its hashes below are retained only as provenance and are not
current VV5 runtime-validation artifacts. The original pre-449483f four-game
output remains explicitly **INVALID - DO NOT RUN**; the corrected four-game
output is also superseded. VV2 has a self-contained vanilla source folder for a
future clean rebuild.

## Supported build fingerprints

These are the exact stock builds covered by the static checklist. Runtime
confirmation remains pending for every output.

## VV2 Origins withdrawal

Do not test or package the VV2 Origins pair. A player reported that both Time
Warp and Food Point Doubler crash immediately after the purchased/success
dialog is displayed. This records the observed trigger only; it does not infer
whether the charge or action persisted. The feature and its dependent
village-wide upgrade are fully contained pending root-cause repair; unrelated
VV2 features remain available.
The crash audit also found `.shr` raw-offset versus virtual-address confusion
in the VV2 builder, displacing helper/header references by `0x2000`; this is a
hard re-enable blocker but not yet a complete crash explanation.

| Game | Stock executable size | Stock SHA-256 |
| --- | ---: | --- |
| VV1 | 581,632 bytes | 1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D |
| VV2 | 724,992 bytes | 46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677 |
| VV3 | 831,488 bytes | 8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503 |
| VV4 | 929,792 bytes | 6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220 |
| VV5 | 991,232 bytes | 92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D |

## Historical/superseded all-five output kit

All five outputs use `collection_progression`, stock save layout, no save-copy
operation, and exactly these dependency-ordered features:
`vvN_enable_origins_exclusive_features`, then
`vvN_origins_village_wide_upgrades`. No appearance, mask, statistics, or other
optional feature was selected. The following historical hashes identify that
superseded kit; they must not be treated as current VV5 runtime confirmation.

| Game | Modified executable | SHA-256 |
| --- | --- | --- |
| VV1 | `Virtual Villagers - A New Home - Modded/Virtual Villagers - A New Home - Modded.exe` | `1118F1879CEF029F8D46EEBC762D4D47E3A122CBF5A3B59934DF06A5A83DB4FB` |
| VV2 | `Virtual Villagers - The Lost Children - Modded/Virtual Villagers - The Lost Children - Modded.exe` | `F7427D9E634431949841CAC0B19B964E0CAD2446538552ADF67651A79ECB1B19` |
| VV3 | `Virtual Villagers - The Secret City - Modded/Virtual Villagers - The Secret City - Modded.exe` | `B18FDB825738A1329DCD3F526C4A4677D0B4E0E643EB9B5137590578BB4EDBFF` |
| VV4 | `Virtual Villagers - The Tree of Life - Modded/Virtual Villagers - The Tree of Life - Modded.exe` | `636D7C8583DD7DC75319B0C1D4C59DD5FEADD2E7948A63CEF8A845F9DF0C674E` |
| VV5 | `Virtual Villagers - New Believers - Modded/Virtual Villagers - New Believers - Modded.exe` | `15A8AC5639D8B10F422C036EF5D2D0C73A5F82B9D03D503E8C1FCD3988603F1B` |

## Before each test

Use a backed-up vanilla save. Record the game/build SHA-256, output EXE SHA-256,
save slot, tech balance, People Cured, and every relevant villager's health,
sickness, displayed age, skills, Likes, Dislikes, and (for VV5) current faction.
Save and reload after each meaningful test. Confirm another slot remains
unchanged and that the original vanilla save is still recognized. Do not infer a
bug from one un-reproduced observation.

## Birth Control and special-outcome isolation

Birth Control, pregnancy, and Embracing tests apply only to the exact ordinary
manual, autonomous, or catch-up paths named by that game's evidence. Island
Event pregnancy, birth, and child outcomes must remain entirely native:
unchanged age, sex, preference, eligibility, conception, pregnancy, delivery,
capacity, RNG, messages, statistics, and state writes. VV2 Gong of Wonder
outcomes have the same complete exclusion.

For `vv2_birth_control`, test ordinary autonomous/catch-up pairing and stew
recipe 15 separately. Then verify that Love Note direct pregnancy, Gong life
grants, Silver Mirror cloning, already-pending delivery, and other direct
event/Gong outcomes behave exactly as stock. Do not interpret a special
outcome bypassing Birth Control as a defect; that bypass is required.

## Tech-screen rows

| Row | Cost / expected runtime check |
| --- | --- |
| Time Warp | 50,000 tech points; VV1/VV2/VV3/VV4 should advance exactly 3 displayed villager years; paused refusal shows no charge. |
| Island Event | 30,000 tech points; VV1/VV3/VV4 should call the native event. |
| Barrel of Babies | 75,000 tech points; VV1/VV3/VV4 should require three physical slots and produce the native three-child result; capacity refusal must not charge. |
| Tech Point Doubler | 500,000 tech points; VV1/VV3/VV4 unowned purchase and repurchase remain unavailable. VV5 stock supports purchase, zero-cost/no-refund Remove, and full-price repurchase; VV5 expanded-256 keeps new purchase unavailable and owned Remove available. |
| Food Point Doubler | 500,000 tech points; VV1/VV3/VV4 unowned purchase and repurchase remain unavailable. VV5 stock supports purchase, zero-cost/no-refund Remove, and full-price repurchase; VV5 expanded-256 keeps new purchase unavailable and owned Remove available. |
| Cure all Villagers | 30,000 tech points; test the sickness-only matrix below. |
| Village-wide rows | Unavailable in the current catalog. The historical contract priced All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18 at exactly 1,000,000 tech points each. |

For VV5, Time Warp, Island Event, and Barrel of Babies remain Unavailable:
selecting them must make no charge, native call, clock change, or save/state
change.

## VV2-specific runtime cases

VV2's paused Time Warp must refuse with no charge and no clock/state change.
Unlike VV1, VV3, VV4, and VV5, VV2's certified Tech Point Doubler and Food
Point Doubler paths are purchasable, removable, and repurchasable: purchase
costs 500,000 tech points, removal costs 0 and refunds 0, and repurchase costs
the full 500,000 again in the current save. VV1/VV3/VV4/VV5 unowned or
manually removed doublers remain unavailable for new purchase pending their
exact-build provenance gates.

The disabled VV2 Full Mastery candidate targets its five native skill fields;
it is not available or approved as safe. Food
Mastery is code-confirmed absent within the enumerated VV2 technology
definitions, strings, direct writer calls, and food-source call chains; Farming
only gates or unlocks sources, and Herb Mastery is unrelated. The Tech Point
and Food Point Doublers stack only
after certified native eligible gain calculations; Island Event and Gong of
Wonder outcomes—including positive, zero, negative, cap, reset, statistic,
message, and side-effect paths—remain native and are never multiplied.

## Cure all Villagers matrix

Test a sick living villager, healthy living villager, and dead sick record. In
VV5 also test a sick current Heathen and a converted believer. The dialog must
say exactly `Cured X villagers`. Only counted sick living eligible villagers
lose their sickness; health is byte-for-byte unchanged and People Cured rises
by exactly one per counted cure. Healthy, dead, and a current VV5 Heathen stay
unchanged and uncounted; a converted current believer follows the current
believer predicate.

## Village-wide rows

### All Villagers Like Running

Use one 1,000,000-tech-point purchase for the whole village. Test a free Like
with a Running Dislike, an existing Running Like, every Like slot full with non-Running Likes
with a Running Dislike, a free Like without a Dislike, dead/inactive records,
and VV5 current Heathen/converted-believer records. The result contains, in
order, these exact required lines:

`Skipped over X villagers. Reason: already likes running`

`Removed running dislike from X villagers`

The proposed full-slot result line remains future-only pending capacity proof.
No unrelated Like is replaced, no duplicate Running Like is added, and no
Running Dislike is removed from a villager who already Likes Running or has no
empty Like slot. Movement speed and movement initialization never change. VV5
current Heathens are untouched and excluded from every count.

### Grant Full Mastery to All Villagers and All Villagers are 18

These rows are unavailable; this section is a future validation contract only.
If later certified, each row would charge exactly 1,000,000 once. Full Mastery
must set the native maximum 100 in all five skills in VV1–VV4 and all six in
VV5, while preserving every required native side effect. Age must set displayed
age exactly to 18 only. Nursing/pregnancy timers and state remain unchanged;
dead/inactive records and VV5 current Heathens remain byte-identical.

## Selected-villager rows

- Grant Youth costs 50,000 and removes 35 years, clamped at displayed age 5.
- Grant Full Mastery costs 100,000 and changes only the proved skill fields.
- Grant Running costs 40,000, uses only a free normal Like slot, removes the
  Running Dislike, never changes speed, and refuses with no charge when Likes
  are full.
- Set Age to 18 costs 50,000 and must not change nursing or pregnancy state.

Every selected-villager action must revalidate identity, active/living status,
and funds. No current VV5 Heathen may be targeted or charged.

## Insufficient-funds test

For each upgrade class, start exactly one tech point below the listed cost. The
dialog must say exactly `Not enough tech points.` There must be no deduction,
partial mutation, event, or clock change.

## Failure report template

Record: game/build hash; output EXE hash; save slot; row; exact starting state;
exact dialog text; before/after tech, counters, and fields; save/reload result;
and a screenshot when available. Do not interpret the result as a bug until it
is reproduced and routed to planning/diagnostics.

The checklist does not change executable manifests, patch arrays, companions,
prices, availability, save behavior, or existing outputs. No game is launched
by static validation, and runtime/player confirmation remains pending.
