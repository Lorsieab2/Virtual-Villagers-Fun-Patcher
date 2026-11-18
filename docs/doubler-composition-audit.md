# Origins doubler composition audit

This is a static audit of the exact desktop builds currently supported by the
patcher. It is deliberately separate from the player-facing feature
descriptions: every row below is an exact-build static proof, not a claim that
the behaviour has been seen in a running game.

## The owner's scope (2026-11-17, the same rule in all five games)

- **Food Point Doubler** = only food **gathered from a food source** (bushes,
  crops, coconuts, fruit trees, honey, fish, crabs, noni, mushrooms, and each
  game's equivalents).
- **Tech Point Doubler** = research-table work (with the research bonuses the
  game works out at the research table: the fire's point, Lab Equipment, the
  VV3 chief/Magic/potion points, the VV5 second-set bonus), collectible
  duplicates, and collection effects on tech gain.
- **Never doubled:** island events, rewards (puzzles, dialogs, the Gong of
  Wonder, the Sack and Vial), purchases and cheats.
- **Owner's additions (2026-11-18):** the VV1 Golden Child's +150 food and the
  VV3 chief's grant (job event 43) are doubled; the VV4 Mossy Rocks crab is a
  food source.

## Decision rule

Each doubler is a **whitelist**: the writer wrapper doubles a positive delta
once only when the immediate return address of the writer call is one of the
exact stock returns listed for that game below, and only while the current save
owns that doubler. Every other caller -- an island event, a reward, a tail-jump
(an E9 jump into the writer, whose return address belongs to a different call),
a companion DLL's own call, an unknown caller -- stays native. This replaced the
earlier blacklists (2026-11-18), which had wrongly excluded VV4's and VV3's job
events (the research table and the gathering jobs), VV5's gathering jobs, and
every game's duplicate collectibles, and had doubled VV1's milestone dialogs,
VV2's Sack/Vial rewards and the island events that
companion DLLs run.

The composition contract is positive earned tech deltas only and positive food-source deltas only.
Native writers still perform storage/statistics updates using the doubled amount.
native writers still perform storage/statistics updates using the doubled amount.
zero and negative deltas remain native.

The sliders of #799 ("Food Gained per Food Source", "Tech Point Gain Rate")
retarget the same calls without moving their return addresses, so a scaled
source is still doubled, once, on the scaled amount.

## Exact-build whitelist matrix

| Game | Tech writer / eligible returns | Food writer / eligible returns | Status |
|---|---|---|---|
| VV1 A New Home | `0x41D120`: research at Science 1, 2, 3 (`0x43B318`, `0x43B333`, `0x43B350`). No collectibles and no fire bonus in this game. | `0x41D140`: berries `0x43AD91`, crops `0x43AED2`, fish `0x43AF41`, crab `0x43AF93`, mushroom `0x43AFFC`; the Golden Child's +150 food `0x43B0A0` (the owner, 2026-11-18). | **GO (static exact-build proof; runtime pending)** |
| VV2 The Lost Children | `0x426290`: research `0x46373C`, `0x4637C5`, the fire `0x46380E`; duplicates `0x463461`, `0x46346D`, `0x463479`. | `0x4262B0`: coconuts `0x46319D`, crops `0x46325E`, fish `0x463317`, the big catch `0x463369`, mushroom `0x4633D2`. | **GO (static exact-build proof; runtime pending)** |
| VV3 The Secret City | `0x427130`: research `0x459237`, `0x4593AF`, the chief's quarter `0x4593D5`, Magic `0x4593F2`, the chief's third / potion `0x459410`, the fire `0x45943A`; duplicate `0x42DF7E`. | `0x4263F0`: fruit `0x434AF1`, chief's fruit bonus `0x434B1A`, honey `0x431C2F`, chief's honey bonus `0x431C51`, fish `0x458EEA`, crab `0x458FE6`, mushroom `0x42E07E`, rain lift `0x434C0B`, cliff top `0x434D84`, fruit at the food bin `0x434C7C`; the chief's grant (job event 43, food by Leadership) `0x45906D` (the owner, 2026-11-18). | **GO (static exact-build proof; runtime pending)** |
| VV4 The Tree of Life | `0x41E300`: research `0x464E5D`, Lab Equipment `0x464E87`, the fire `0x464EB0`; duplicates `0x41447C`, `0x414498`, `0x4144B4`. | `0x41D920` (doubled at `0x41D94F`, after Food Mastery): blackberry bush `0x464497`, cutting-tool berries `0x464510`, yellow breadfruit `0x464578`, fish `0x4645B5`, golden fish `0x464600`, crab `0x464A4B`, Mossy Rocks crab `0x436F1A`, Cooking Pit catch-up fruit `0x468AB7`, mushroom `0x414665`, inherited fish job `0x464438`. | **GO (static exact-build proof; runtime pending)** |
| VV5 New Believers | `0x4237B0` (stock wrapper `0x7B2A00`): research `0x46DE4D`, second set's bonus `0x46DE7C`, the fire `0x46DEA5`; duplicates `0x4147BE`, `0x4147DD`, `0x4147F9`. | `0x41EB40` (stock wrapper `0x7B2B00`, after Food Mastery): noni `0x46D000`, crops `0x46D113`, lake fish `0x46D7A1`, mushroom `0x414970`, and the food jobs inherited from VV4 `0x46CFA1`, `0x46D079`, `0x46D764`, `0x46D7DE`, `0x46DB25`. | **GO (static exact-build proof; runtime pending)** |

VV5 stock-layout Tech and Food corrections are implemented with exact-build
static proof; expanded-256 modes are not public patcher modes.

### What stays native, by game

- VV1: island events (`0x428194`, `0x4281DA`, and the encounters More Island
  Events runs from its DLL), story/puzzle discoveries (`0x41A378`, `0x419459`,
  `0x419F14`), the milestone dialogs (tech `0x42BB18`, `0x42BBF7`, `0x42BCD6`,
  `0x42BE50`, `0x42BFB0`, `0x42C110`; food `0x42B86A`, `0x42B938`, `0x42BA06`).
- VV2: island events (`0x4205AC`, `0x434351`, `0x420AE9`, `0x433FC6`), the
  Gong of Wonder (tech `0x44EA32`, `0x44ED52`, `0x44F202`; food `0x44E9C3`,
  `0x44EDB9`, `0x44F0D9`), the Sack and Vial (tech `0x4385E6`, `0x438746`,
  `0x4388A6`, `0x438AA0`, `0x438C80`, `0x438E60`; food `0x438298`, `0x438376`,
  `0x43844A`). Full inventory: 17 tech and 13 food calls, with zero E9
  tail-jumps.
- VV3: island events (direct calls and the tail-jumps `0x415EF1`, `0x416983`,
  `0x416BAB`, `0x417A3A`, `0x415D44`, `0x41673E`, `0x418452`), the -5000 tech
  and the food bowl's -1.
- VV4: island events (direct calls `0x414A2D`, `0x41494E` and the tail-jumps
  `0x4156F8`, `0x415862`, `0x41586F`, `0x415A81`, `0x415B46`, `0x415D8C`,
  `0x416722`, `0x416735`, `0x41520E`), the +250 object (`0x431AA0`), the
  +80,000 tech / +5,000 food grant (`0x440889`, `0x440898`), purchases and
  deductions.
- VV5: the 16 island event outcomes and the eight writer tail paths, the
  refund return `0x419EA3`, purchases, deductions and consumption.

Earlier exclusion wording for the record: Golden Child tech-point gain, Island
Event tech-point gain and Gong of Wonder tech-point gain stay native as before;
Duplicate Collectibles tech-point gain is now doubled (the owner's scope).

### Companion DLLs that pay a food source

- **VVFP VV4 Fruit Supply.dll** ("Yellow Fruit Trees are No Longer
  Unlimited") replaces the yellow fruit credit (`0x46456C`) and the Cooking
  Pit bonus (`0x468AAB`). Its stubs push the stock return (`0x464578`,
  `0x468AB7`) and jump to `0x41D920`, so the writer sees the stock return and
  the fruit is doubled exactly like the stock call.
- **VVFP VV4 Cloth Sacks.dll** (#794, not merged when this was written) pays
  the sack's fruit by calling `0x41D920` from inside the DLL, so the return
  address is the DLL's and the whitelist does not double it. Hook point for
  that PR: before its `0x41D920` call, double the positive amount `n` once
  when bit 1 of the ownership word `dword [0x4D6E10]` is set (VV4 keeps the
  Food Doubler's ownership there; it is zero when Origins is not installed).
  That doubles before Food Mastery, which differs from the wrapper's
  after-mastery doubling by at most one food at Food Mastery level 2.

## Food Mastery status by exact build

Food Mastery affecting food-point gain is code-confirmed for VV4 and VV5, while
VV1, VV2, and VV3 are code-confirmed absent in their exact-build evidence. The
VV2 absence boundary covers the completely enumerated technology definitions,
resource strings, direct writer calls, and food-source call chains; Farming only
gates/unlocks sources and Herb Mastery is unrelated. VV4 and VV5 apply Food
Mastery inside the writer (A, A+floor(A/2), or 2A at levels 0/1, 2 and 3), and
the Food Doubler doubles the amount after it.

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
the Magic read. Island Event technology awards are explicit Tech Doubler
exclusions; duplicate collectibles are doubled (the owner's scope).

The Tech Doubler must double only an eligible positive earned-tech source
delta. It must not fold Magic, quarter-base, timed, or random components into a
different post-sum operation. Because case 26 emits components separately, the
VV3 Tech Doubler stays at the positive-writer boundary and doubles each research
component once; the whitelisted returns are its provenance-safe source boundary.
Deduction, startup and Island Event paths remain native.

## Required follow-up before GO

Status (checked 2026-11-18): this section governs rows that are still pending or STOP. There are
none: VV1 to VV5 are all marked GO above, on static exact-build proof. For each of them the manifests
record the exact whitelists (`tech_eligible_returns` / `food_eligible_returns`; VV5
`tech_positive_returns` / `food_positive_returns`), and tests/test_doubler_scope.py checks every
whitelisted return against the stock executables (each is the return of a call to that game's writer)
and runs each wrapper in an emulator: every in-scope return doubles, every out-of-scope caller is
unchanged, and nothing changes without ownership. What is not recorded is any run in a live game, so the
descriptions may state what is doubled but must not claim the behaviour has been seen at runtime.
