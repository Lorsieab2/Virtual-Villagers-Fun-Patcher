# Origins Player Runtime Checklist

This is a player-test checklist for the collection-progression Origins-core
outputs. It is explicitly **runtime/player confirmation pending**; static patch
verification is not a claim that any item below has been confirmed in-game.
The checklist applies to the VV1, VV3, VV4, and VV5 outputs. VV2 remains
pending a self-contained local vanilla game folder and is not represented as a
playable output here.

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
| Time Warp | 50,000 tech points; VV1/VV3/VV4 should advance exactly 3 displayed villager years; paused refusal shows no charge. |
| Island Event | 30,000 tech points; VV1/VV3/VV4 should call the native event. |
| Barrel of Babies | 75,000 tech points; VV1/VV3/VV4 should require three physical slots and produce the native three-child result; capacity refusal must not charge. |
| Tech Point Doubler | 500,000 tech points; all four outputs currently show Unavailable when unowned. Existing owned Remove costs 0, refunds 0, is current-save-only, and remains unavailable for repurchase. |
| Food Point Doubler | 500,000 tech points; same unavailable/remove/no-refund/current-save rules. |
| Cure all Villagers | 30,000 tech points; test the sickness-only matrix below. |
| Village-wide rows | All Villagers Like Running, Jack-Of-All-Trades, and All Villagers are 18 cost exactly 1,000,000 tech points each. |

For VV5, Time Warp, Island Event, and Barrel of Babies remain Unavailable:
selecting them must make no charge, native call, clock change, or save/state
change.

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

### Jack-Of-All-Trades and All Villagers are 18

Each row charges exactly 1,000,000 once. Mastery must write only the native
skill fields: five skills in VV1/VV3/VV4 and six in VV5. Age must set displayed
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
