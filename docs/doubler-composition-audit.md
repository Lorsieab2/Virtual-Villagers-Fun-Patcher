# Origins doubler composition audit

This is a static audit of the exact desktop builds currently supported by the
patcher. It is deliberately separate from the player-facing feature
descriptions: a return-address guard is a candidate exclusion, not proof that
every Island Event result path is covered.

## Decision rule

For a supported build to be marked **GO**, Food Point Doubler must change only
the positive food-source delta that is about to be added to village stores, and
Tech Point Doubler must change only the positive earned-tech delta at its
certified source boundary. Each eligible source value is doubled once; zero
and negative deltas remain native. The patch does not alter deductions,
initialization, ownership, counters, or unrelated resources. The native writer
still performs its normal storage and statistics updates using the doubled
amount.

The composition contract is positive earned tech deltas only and positive food-source deltas only.
Native writers still perform storage/statistics updates using the doubled amount.
native writers still perform storage/statistics updates using the doubled amount.
zero and negative deltas remain native.

The required exclusions are explicit and global: Golden Child tech-point gain
in VV1, Island Event tech-point gain in every game, Gong of Wonder tech-point
gain in VV2, and Duplicate Collectibles tech-point gain in every game where
that route is present. Food-source collection adjustments and native Food
Mastery remain upstream game logic; the Food Doubler changes only the resulting
positive food-source amount. This is a requirement for each exact-build GO
audit, not a claim that pending/STOP games share mechanics or are already
verified.

Named exclusions: Golden Child tech-point gain; Island Event tech-point gain;
Gong of Wonder tech-point gain; Duplicate Collectibles tech-point gain.

The current source contains static guards. VV1 through VV4 are marked **GO**
below because their exact-build positive-writer paths and named exclusions are
implemented; this is a static proof only and is not a claim of runtime/player
confirmation. VV5 stock-layout Tech and Food corrections are implemented with
exact-build static proof; expanded-256 modes are not public patcher modes.

## Exact-build evidence matrix

| Game | Positive tech writer / hook | Positive food writer / hook | Collection adjustment evidence | Island Event evidence | Status |
|---|---|---|---|---|---|
| VV1 A New Home | `0x41D120` / payload `tech_increment` | `0x41D140` / payload `food_increment` | No Food Mastery-like food transform or collection tech multiplier was found in this exact build; ordinary Science modifies research amounts before the eligible writer hook. Golden Child has no proven tech-award route in this image. | Caller returns `0x428194` (tech) and `0x4281DA` (food) remain native; Golden Child and Duplicate Collectibles have no certified writer route in this image. | **GO (static exact-build proof; runtime pending)** |
| VV2 The Lost Children | `0x426290` / payload `tech_increment` | `0x4262B0` / payload `food_increment` | Exact build `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` (724,992 bytes) has no separate global collection multiplier in either final writer; callers pass the final native signed delta. | `0x4204B0` returns `0x4205AC`/`0x420AE9`; `0x433600` returns `0x434351`/`0x433FC6`; Gong `0x44E8A0` returns tech `0x44EA32`, `0x44ED52`, `0x44F202` and food `0x44E9C3`, `0x44EDB9`, `0x44F0D9`. The duplicate-collectible route returns tech at `0x463461`, `0x46346D`, and `0x463479`. Exact wrapper blacklists cover all eight tech exclusions and all five food exclusions; direct +3000, losses, caps, resets, and zero paths bypass the positive writers. Full inventory is 17 tech and 13 food calls, with zero E9 tail-jumps. | **GO (static exact-build proof; runtime pending)** |
| VV3 The Secret City | `0x427130` / payload `tech_increment` | `0x4263F0` / payload `food_increment` | Exact build `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` has no Food Mastery-like award transform. Audit `4c588ffd36765d750533fe9694f8fda5c8e82736` exhaustively finds nine Magic-index reads; the wrapper leaves those separate native writer calls unchanged. | Complete inventory: food 33 rows (29 calls, E9 tails `0x415EF1`, `0x416983`, `0x416BAB`, `0x417A3A`); tech 16 rows (13 calls, E9 tails `0x415D44`, `0x41673E`, `0x418452`). The duplicate-collectible return `0x42DF79` is excluded, and all audited Island Event tail-jumps bypass the doubler. | **GO (static exact-build proof; runtime pending)** |
| VV4 The Tree of Life | `0x41E300` / payload `tech_increment` | `0x41D920` native writer; Food Mastery completes before any eligible doubler | Exact build `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` has 21 external tech and 23 external food writer references. Collection call `0x414660` supplies pre-mastery 6/35; native Food Mastery is A, A+floor(A/2), or 2A for levels 0/1, 2, and 3. | Duplicate-collectible returns `0x41447C`, `0x414498`, and `0x4144B4`, direct Island Event returns are blacklisted, and event tails `0x4156F8`, `0x415862`, `0x41586F`, `0x415A81`, `0x415B46`, `0x415D8C`, `0x416722`, `0x416735`, food tail `0x41520E` bypass the doubler. | **GO (static exact-build proof; runtime pending)** |
| VV5 New Believers | `0x4237B0` / stock wrapper `0x7B2A00` | `0x41EB40` / stock wrapper `0x7B2B00` after Food Mastery | Exact build `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` (991,232 bytes) has Food Mastery tech ID 4: the upgrade from level 1 to 2 costs 3,000 and the upgrade from level 2 to 3 costs 40,000 tech points; positive A becomes A, A+floor(A/2), or 2A; zero/negative inputs bypass. Ordinary collection return `0x414970` maps base 6/35 to 6/35, 9/52, or 12/70. | Stock-layout Tech doubles only the three certified positive earned-tech returns `0x46DE4D`, `0x46DE7C`, and `0x46DEA5`. Duplicate-collectible returns `0x4147BE`, `0x4147DD`, and `0x4147F9`, Island Event, startup, consumption, deduction, zero/negative, and unknown callers remain native. Food doubles only the certified positive food-source return. | **GO (static exact-build proof; runtime pending)** |

## Food Mastery status by exact build

Food Mastery affecting food-point gain is code-confirmed for VV4 and VV5, while
VV1, VV2, and VV3 are code-confirmed absent in their exact-build evidence. The
VV2 absence boundary covers the completely enumerated technology definitions,
resource strings, direct writer calls, and food-source call chains; Farming only
gates/unlocks sources and Herb Mastery is unrelated. VV4 and VV5 use separate
exact-build implementations; their native transforms are documented in their
evidence rows.

## VV3 Magic Level-1 research composition

Exact-build audit `4c588ffd36765d750533fe9694f8fda5c8e82736`
enumerates all nine Magic-index reads. The only research consumer is
`sub_458DB0` case 26 at getter call `0x4593DC`. Let `B` be the native base
research award after the ordinary speed division where applicable, `Q` the
quarter-base predicate, `M` one when Magic is at least level 1, `T` the timed
effect addition, and `G` the independent `RNG(100) < 10` addition:

`NativeResearchGain = B + (Q ? floor(B/4) : 0) + M + T + G`

The five components are separate integer writer calls in that order. Magic is
always a flat `+1`, including when truncation makes `B` zero. It does not alter
action/tick frequency, duration, the base award, RNG probability or amount, or
Research-skill gain. Ordinary and special/catch-up research converge before
the Magic read. Collection duplicate awards and Island Event technology
awards are explicit Tech Doubler exclusions.

The Tech Doubler must double only an eligible positive earned-tech source
delta. It must not fold Magic, quarter-base, timed, or random components into a
different post-sum operation, and the duplicate-collectible and Island Event
routes remain native. Because case 26 emits components separately, the VV3
Tech Doubler remains at the positive-writer boundary and uses the audited
source exclusions as its provenance-safe source boundary. The separate Magic,
timed, random, deduction, startup, and collection paths remain native where
they do not match an eligible positive writer source.

## Required follow-up before GO

For each future pending/STOP row, the evidence record must include the exact stock executable
SHA-256, positive writer callsites, collection adjustment functions and
rounding/field representation, every Island Event producer/caller, final
delta representation, ownership field, and the exact hook point. Static tests
must independently exercise no source, source only, doubler only, source plus
doubler, and each named exclusion with both ownership states. For the source-
plus-doubler case, the result must equal twice the exact native positive source
delta; toggling either doubler must not change an excluded result. Until those
checks are recorded, no description should call the exclusion complete or claim
verified runtime behavior.

## VV2 exact-build inventory and exclusions

The Lost Children build is 724,992 bytes with SHA-256
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.
The positive writer wrappers receive the final signed caller delta. They
exclude these exact immediate caller return addresses on a per-call basis:

- Tech: `0x4205AC`, `0x434351`, `0x44EA32`, `0x44ED52`, `0x44F202`,
  `0x463461`, `0x46346D`, `0x463479`.
- Food: `0x420AE9`, `0x433FC6`, `0x44E9C3`, `0x44EDB9`, `0x44F0D9`.

The wrapper keeps the stock ABI (`ECX` save manager and signed delta at
`[ESP+4]` on entry), preserves `EBX`, and reads the delta at `[ESP+8]` after
its prologue. A positive, non-excluded call is doubled once only when the
current save owns the corresponding doubler; zero and negative deltas are
forwarded unchanged.

The complete direct-call inventory is 17 tech calls and 13 food calls. The
inventory has no E9 tail-jumps to either central writer. Six positive Gong
branches, both Island Event handler sites, and the three duplicate-collectible
tech returns are included in the exclusion sets. Direct +3000 Island Event
tech, negative tech, losses, caps, halves,
resets, zero outcomes, and unrelated-resource paths remain native because they
bypass the positive writers. This is the VV2-specific composition evidence and
must not be generalized to another game.
