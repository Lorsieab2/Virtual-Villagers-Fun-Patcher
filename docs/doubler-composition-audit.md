# Origins doubler composition audit

This is a static audit of the exact desktop builds currently supported by the
patcher. It is deliberately separate from the player-facing feature
descriptions: a return-address guard is a candidate exclusion, not proof that
every Island Event result path is covered.

## Decision rule

For a supported build to be marked **GO**, the doubler must be applied after
that build's complete collection adjustment and before the final positive
resource write. Every Island Event food and tech producer (including direct
calls and tail-jumps) must be proven to reach an exclusion path. Island Event results are never doubled, regardless of whether the result is positive, zero,
or negative. A collection-adjusted positive delta is doubled only after the
native collection calculation has completed. Deductions and initialization
writes retain their native values.

The requested final composition contract is per-game: Tech Point Doubler stacks
with every proven collection effect that increases tech gain; Food Point
Doubler stacks after Food Mastery only where that exact build proves the
modifier. Golden Child is a VV1-only exclusion, Gong of Wonder is a VV2-only
exclusion, and Island Event exclusions follow each game's inventory. This is a
requirement for each exact-build GO audit, not a claim that pending/STOP games
share mechanics or are already verified.

The current source contains static guards. VV2 is marked **GO** below because
the exact-build inventory and provenance exclusions are complete; this is a
static proof only and is not a claim of runtime/player confirmation. VV1, VV3,
and VV4 remain STOP. VV5 stock-layout Tech and Food corrections are implemented
with exact-build static proof; VV5 expanded-256 composition remains ON HOLD.

## Exact-build evidence matrix

| Game | Positive tech writer / hook | Positive food writer / hook | Collection adjustment evidence | Island Event evidence | Status |
|---|---|---|---|---|---|
| VV1 A New Home | `0x41D120` / payload `tech_increment` | `0x41D140` / payload `food_increment` | No Food Mastery-like food transform or collection tech multiplier was found in this exact build; ordinary Science modifies research amounts before any future eligible hook. | Candidate caller returns `0x428194` (tech) and `0x4281DA` (food); arbitrary computed/indirect producer coverage and safe executable placement are not proved. | **STOP** |
| VV2 The Lost Children | `0x426290` / payload `tech_increment` | `0x4262B0` / payload `food_increment` | Exact build `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` (724,992 bytes) has no separate global collection multiplier in either final writer; callers pass the final native signed delta. | `0x4204B0` returns `0x4205AC`/`0x420AE9`; `0x433600` returns `0x434351`/`0x433FC6`; Gong `0x44E8A0` returns tech `0x44EA32`, `0x44ED52`, `0x44F202` and food `0x44E9C3`, `0x44EDB9`, `0x44F0D9`. Exact wrapper blacklists cover all five tech and all five food returns; direct +3000, losses, caps, resets, and zero paths bypass the positive writers. Full inventory is 17 tech and 13 food calls, with zero E9 tail-jumps. | **GO (static exact-build proof; runtime pending)** |
| VV3 The Secret City | `0x427130` / payload `tech_increment` | `0x4263F0` / payload `food_increment` | Exact build `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` has no Food Mastery-like award transform. Audit `4c588ffd36765d750533fe9694f8fda5c8e82736` exhaustively finds nine Magic-index reads; only `sub_458DB0` case 26 at `0x4593DC` affects research. Magic >= 1 contributes a deterministic separate `+1` writer call after base and optional quarter-base awards, before timed and independent RNG additions; it changes no speed, duration, base award, RNG probability/amount, or Research-skill gain. Collection dispatcher `sub_42DEB0` awards tech 100/250/1,500 and resolves writers at `0x42DF79` and `0x42E079`; IDA has no resolved caller to it. | Complete inventory: food 33 rows (29 calls, E9 tails `0x415EF1`, `0x416983`, `0x416BAB`, `0x417A3A`); tech 16 rows (13 calls, E9 tails `0x415D44`, `0x41673E`, `0x418452`). Ordinary and special/catch-up research converge before Magic, but case 26 emits `B + quarter + Magic + timed + RNG` as separate writer calls. Collection duplicates and Island Events are separate producers. A future Tech Doubler must double the complete eligible positive native sum once after all additions and exclude Island Events; no safe post-sum/source-aware hook or source tag is proven. | **STOP** |
| VV4 The Tree of Life | `0x41E300` / payload `tech_increment` | `0x41D920` native writer; Food Mastery completes before any eligible doubler | Exact build `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` has 21 external tech and 23 external food writer references. Collection call `0x414660` supplies pre-mastery 6/35; native Food Mastery is A, A+floor(A/2), or 2A for levels 0/1, 2, and 3. | Complete inventory records event tails `0x4156F8`, `0x415862`, `0x41586F`, `0x415A81`, `0x415B46`, `0x415D8C`, `0x416722`, `0x416735`, food tail `0x41520E`, and generic event direct sites. No return-address-only exclusion can classify the E9 tails. | **STOP** |
| VV5 New Believers | `0x4237B0` / stock wrapper `0x7B2A00` | `0x41EB40` / stock wrapper `0x7B2B00` after Food Mastery | Exact build `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` (991,232 bytes) has Food Mastery tech ID 4: the upgrade from level 1 to 2 costs 3,000 and the upgrade from level 2 to 3 costs 40,000 tech points; positive A becomes A, A+floor(A/2), or 2A; zero/negative inputs bypass. Ordinary collection return `0x414970` maps base 6/35 to 6/35, 9/52, or 12/70. | Stock-layout Tech and Food positive-whitelist corrections are implemented: eligible stock returns are doubled once and Island Event, startup, consumption, deduction, zero/negative, and unknown callers remain native. Expanded-256 restores both native writer hooks and keeps new purchases unavailable. The expanded relocation audit (disassembly commit `8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb`) covers 32 of 75 references; 36 cross-section rel32 and 7 external absolute `.shr` references remain outside the certified set. | **STOCK GO; EXPANDED ON HOLD** |

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
awards are separate producers.

Any future Tech Doubler must first calculate that full eligible positive native
research sum, including Magic, quarter-base, timed, and random additions, and
then double it exactly once. Island Events remain excluded. Because case 26
currently emits components separately and the shared writer also receives
Island Events, deductions, startup, collection, and unrelated producers, the
VV3 Tech Doubler remains unavailable pending a provenance-safe post-sum hook or
source tag.

## Required follow-up before GO

For each pending/STOP row, the evidence record must include the exact stock executable
SHA-256, positive writer callsites, collection adjustment functions and
rounding/field representation, every Island Event producer/caller, final
delta representation, ownership field, and the exact hook point. Static tests
must independently exercise no collection, collection only, doubler only,
collection plus doubler, and Island Event with both ownership states. For the
collection-plus-doubler result must equal twice the exact native
collection-adjusted positive delta; toggling either doubler must not change an
Island Event result. Until those checks are recorded, no description should
call the exclusion complete or claim verified runtime behavior.

## VV2 exact-build inventory and exclusions

The Lost Children build is 724,992 bytes with SHA-256
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.
The positive writer wrappers receive the final signed caller delta. They
exclude these exact immediate caller return addresses on a per-call basis:

- Tech: `0x4205AC`, `0x434351`, `0x44EA32`, `0x44ED52`, `0x44F202`.
- Food: `0x420AE9`, `0x433FC6`, `0x44E9C3`, `0x44EDB9`, `0x44F0D9`.

The wrapper keeps the stock ABI (`ECX` save manager and signed delta at
`[ESP+4]` on entry), preserves `EBX`, and reads the delta at `[ESP+8]` after
its prologue. A positive, non-excluded call is doubled once only when the
current save owns the corresponding doubler; zero and negative deltas are
forwarded unchanged.

The complete direct-call inventory is 17 tech calls and 13 food calls. The
inventory has no E9 tail-jumps to either central writer. Six positive Gong
branches and both Island Event handler sites are included in the exclusion
sets. Direct +3000 Island Event tech, negative tech, losses, caps, halves,
resets, zero outcomes, and unrelated-resource paths remain native because they
bypass the positive writers. This is the VV2-specific composition evidence and
must not be generalized to another game.
