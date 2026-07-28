# Origins Player Runtime Checklist

## Current village-wide safety containment

Do not test or purchase Grant Full Mastery to All Villagers or All Villagers
are 18 in the current build. All five legacy
`vvN_origins_village_wide_upgrades` records are disabled because commands
6/7/8 share one atomic payload and Full Mastery lacks a complete per-game GO
gate. The diagnostic manifests remain available to static tests only; no
village-wide bytes are applied. Existing save fields and ownership are left
untouched, with no forced clear and no refund. The historical procedures below
are retained as the future player-validation contract, not as currently
available rows. VV3's independently rebuilt command-6-only **All Villagers
Like Running** source remains catalog-visible, but VV3Run2 is hard-withdrawn
from playtesting under crash audit
`36f14702b938a6235230a3fd3e0c34328d3ac745`. The exact tested EXE/DLL pair
crashed on the status-2 no-change route; static ABI/pointers pass, no saved
overwrite was found, and the fault instruction remains unknown. Do not
package or continue runtime testing until a fresh certified gate. Commands 7
and 8 remain absent.

All Villagers Like Running remains ON HOLD for VV1, VV2, VV4, and VV5 under audit
`0311443fbd078e3adcabaf7e693199989ddb9db8` and evidence clarification
`a67e05247dc822306e1d5a514524cba388ab4d69`. Running ID 38 is independently
code-confirmed in each exact build. Final preference-matrix audit
`f1555e295e828af2165ab0b7ea9f051ac9736418` proves fixed four Like/four
Dislike DWORD slots in VV1, 62/62 in VV2, and three/three in VV3-VV5. Signed
`-1` means empty but never terminates the scan; every fixed slot is examined.
PC VV2 Fastest Runner can naturally create duplicate Running Likes through
`0x420D22`, `0x420D2B`, and `0x420D37`. Future validation requires strict
atomic behavior: any Running Like skips the entire villager with zero
preference writes, preserving every duplicate Like and every Dislike.
Otherwise preflight the first physical `-1` before removing any Running
Dislike; full Likes causes no mutation; with a destination, insert Running
once and clear every Running Dislike while preserving unrelated slots and
ordering. VV5 current faction `+0x1CEC != 0` must be
rejected before any preference access or count, and `+0x1CE1` is not an
approved eligibility gate. The disabled legacy helpers do not meet this
contract. VV3 alone uses the separately certified implementation below.

For VV3 specifically, resolution commits
`531b0aca8d5bf051f87773e67d48b61c0ba02833` and
`1d9a39da078806aa940e4774a9068956e88347bc` close the three-plus-three
slot operation, persistence, atomic ordering, four counters, and
dry-run/no-charge/final unsigned recheck contract. The shared 944-byte
commands 6/7/8 payload remains forbidden.
Second resolution `d1cdeb67362487c1d577e3abae03c9424fd04fb9` specifies the
Running-only seven-row/ID-1006 UI, four-counter `char[256]` result, atomic
one-million-point transaction, and dual-layout PE boundaries. Its former
owned/removable model is revoked: Running is a repeatable Buy action and never
reads, sets, or clears an ownership bit.

Semantic closure `b9c7a22eb1d7cceae25160ce4d360621e7485625` identifies
`+0xE94` as a dormant totem-render selector, not eligibility. Nonzero selects
ID 573 **`'s totem`**; zero with signed health `<= 0` selects ID 574
**`'s remains`**. The exhaustive eight-reader/zero-only-writer scan found no
constructor, new/clone, Event, puzzle, or template nonzero producer. All 64
active corrected save records and 125 active records in the 150-slot live
scan were zero, and CE tables contain no label. The future Running predicate
is active `+0xF10 != 0` plus signed health `+0xE78 > 0`, without `+0xE94`.
VV2 `+0x558` memorials and VV5 Heathen totems remain separate mechanics.
Stage C certification
`79b122bf0850f18a101db9fb86b40407dd2db573` covered the former frozen
command-6-only artifact, but its owned-state behavior is revoked. Corrective
contract `0095e605b3b488129c0623efd642e9352d8586c0` specifies a repeatable Buy,
an exact nonblank no-change result with no deduction, and confirmation before
a positive transaction. Final static certification
`c62fba9214de7c6092365e99c72bd81a59d3888c` was superseded for runtime
readiness by crash audit `36f14702b938a6235230a3fd3e0c34328d3ac745`.
VV3Run2 is withdrawn; commands 7 and 8 remain unavailable.

VV3 Full Mastery is specifically ON HOLD under exact-build audit
`089957227c0db6a4c3128045519ffa27b201a00e`. Its five signed DWORD skills are
`+0xEAC..+0xEBC`; mastery begins at 88, the native maximum is 100, and native
all-five evaluation uses award ID 4. The disabled candidate's direct 90 stores
are not full mastery and bypass that post-write evaluation. Zero-change/no-
charge behavior, creation/inheritance, and safe placement remain unresolved.

VV2 Full Mastery is independently emitted-byte certified under
`913be6982bc17d606470f31d3df3d3430942cb6a`. The isolated command-7-only
feature scans active `+0x30`, positive signed health `+0x52C`, non-totem
`+0x558` records and changes only native skill DWORDs `+0x7E4..+0x7F4` that
are below 100. It then calls native `sub_44D4C0` exactly once per changed
villager. The repeatable 1,000,000-point Buy transaction performs a complete
dry-run, exact no-change/no-charge result, universal OK/Cancel confirmation,
final unsigned funds and eligibility recheck, one deduction, and one commit.
Commands 6/8, ownership, Remove, withdrawn `.shr`, Gong, and Island Events are
absent. Static certification is complete; runtime/player confirmation remains
pending.

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

VV3 All Villagers are 18 remains ON HOLD under corrective audit
`295b5d1e228c501d0e14b1f869f11b0caa3a07bd`. For exact build
`8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`,
target/display age is signed DWORD `+0xDC4`, 20 units/year, and 360 means age
18. Live `+0xDC4` 372->360 immediately displayed 18, survived reload, and
natively advanced to 361; `+0xE74` stayed 372 and `+0xE8C` stayed zero.
`sub_45F3E0` passes `+0xDC4` to `sub_45C640`. `+0xE74` is the
nursing/conception-age/lifecycle timestamp and must not be synchronized.
`sub_45FFE0` runs hidden food/health/mortality/reproduction steps only while
`+0xE74 < +0xDC4`; lowering target age below it pauses those steps until the
target advances beyond the timestamp. Target-only writing is not inherently
invalid, but exact command-8 transaction/result bytes and collision-certified
stock plus both-expanded PE manifests remain absent, so this is not GO.

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
| Village-wide rows | VV2's isolated Grant Full Mastery to All Villagers is available for runtime playtesting at 1,000,000 tech points. VV3Run2 is hard-withdrawn pending a fresh crash/no-change gate. Every legacy bundled row and every command 8 row remain unavailable. |

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

The certified VV2 Full Mastery playtest feature targets its five native skill
fields and excludes commands 6/8 and withdrawn VV2 Origins. Food
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

The corrected VV3 design is a repeatable `Buy` action and never exposes
`Remove` or reads, sets, or clears ownership bit `0x4`. An all-already-Running
dry run must show exactly
`Everyone already likes running.\r\nNo tech points have been deducted.`
without warning, charge, or writes. A positive dry run must show the universal
permanent-change OK/Cancel warning; Cancel is inert, while OK performs the
identical final dry recheck before the unsigned funds check, one deduction, and
one commit.

Use one 1,000,000-tech-point purchase for the whole village. Test a free Like
with a Running Dislike, an existing Running Like, every Like slot full with non-Running Likes
with a Running Dislike, a free Like without a Dislike, dead/inactive records,
and VV5 current Heathen/converted-believer records. The result contains, in
order, these exact required lines:

`Skipped over X villagers. Reason: already likes running`

`Removed running dislike from X villagers`

The proposed full-slot result line remains future-only pending capacity proof.
No unrelated Like is replaced and no new duplicate Running Like is added.
Pre-existing duplicate Running Likes and every Dislike remain unchanged on an
already-like skip. No Running Dislike is removed from a villager who already
Likes Running or has no empty Like slot. Movement speed and movement
initialization never change. VV5 current Heathens are untouched and excluded
from every count.

### Grant Full Mastery to All Villagers and All Villagers are 18

VV3 All Villagers Like Running is hard-withdrawn from replacement runtime
testing under crash audit `36f14702b938a6235230a3fd3e0c34328d3ac745`.
The other games and commands remain a
future validation contract only.
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
