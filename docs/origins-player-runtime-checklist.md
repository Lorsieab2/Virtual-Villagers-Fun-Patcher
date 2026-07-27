# Origins Player Runtime Checklist

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

## Tech-screen rows

| Row | Cost / expected runtime check |
| --- | --- |
| Time Warp | 50,000 tech points; VV1/VV2/VV3/VV4 should advance exactly 3 displayed villager years; paused refusal shows no charge. |
| Island Event | 30,000 tech points; VV1/VV3/VV4 should call the native event. |
| Barrel of Babies | 75,000 tech points; VV1/VV3/VV4 should require three physical slots and produce the native three-child result; capacity refusal must not charge. |
| Tech Point Doubler | 500,000 tech points; VV1/VV3/VV4 unowned purchase and repurchase remain unavailable. VV5 stock supports purchase, zero-cost/no-refund Remove, and full-price repurchase; VV5 expanded-256 keeps new purchase unavailable and owned Remove available. |
| Food Point Doubler | 500,000 tech points; VV1/VV3/VV4 unowned purchase and repurchase remain unavailable. VV5 stock supports purchase, zero-cost/no-refund Remove, and full-price repurchase; VV5 expanded-256 keeps new purchase unavailable and owned Remove available. |
| Cure all Villagers | 30,000 tech points; test the sickness-only matrix below. |
| Village-wide rows | All Villagers Like Running, Grant Full Mastery to All Villagers, and All Villagers are 18 cost exactly 1,000,000 tech points each. |

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

VV2 Grant Full Mastery to All Villagers covers its five native skills. Food
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
with a Running Dislike, an existing Running Like, three full non-Running Likes
with a Running Dislike, a free Like without a Dislike, dead/inactive records,
and VV5 current Heathen/converted-believer records. The result contains, in
order:

`Skipped over X villagers. Reason: Already 3 likes.`

`skipped over Y villagers. Reason: already likes running`

Append only when applicable:

`Removed running dislike from Z villagers`

No unrelated Like is replaced, no duplicate Running Like is added, every
Running Dislike on an eligible villager is cleared even when the villager is
full/already-running, and movement speed or movement initialization never
changes. VV5 current Heathens are untouched and excluded from every count.

### Grant Full Mastery to All Villagers and All Villagers are 18

Each row charges exactly 1,000,000 once. Mastery must write only the native
skill fields: five skills in VV1–VV4 and six in VV5. Age must set displayed
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
