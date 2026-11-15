# V28 retrofit: harm review (for the owner's approval)

The owner's rule (2026-11-14): only VV2 totems are always protected. Nursing mothers, babies, the Golden Child and the
VV3 Chief may be harmed only where the event's own risk makes sense, with `protected: "allow"` on that role, and every
such case is listed here: the event, the outcome, the villager, the exact text and why. VV5 story villagers (the
chief, the Retired Chief, the puzzles' Heathens) stay unharmable whatever a file says.

`python scripts/collection_check.py --allow-report` lists every `allow` on a harm-capable role for checking against
this file.

## Part A

Range: `original/`, `universal/`, `v6/`, `vv5_isolan/`, `v8/`, `v9/`, `v10/`, `v11/` (51 events).

**No entries.** The Part A retrofit adds no `protected: "allow"` and no harm to a nursing parent, a baby, the Golden
Child or the VV3 Chief.

- The one harmful effect added in Part A is the serious-injury `health_change` on The Doctors' Dilemma's patient
  (outcome "lasting effects", L1609-1610). That role keeps the default `protected: "auto"`, so nursing parents, the
  Golden Child and the VV3 Chief are never cast as the patient.
- The special villagers this range already casts take only harmless effects: The Last Song Before Sunset's nursing
  parent gains a little Parenting (no `allow` needed for a gain); The Lullaby, The Child of Legend, The Chief's
  Monumental Speech, The Chief and the Pearl and The Little Things They Remember are unchanged.

## Part B

One event in Part B's range harms a protected villager. Everything else Part B added harms no special villager:
the Golden Child scenes (V14), the Chief's events and contests (exclusive, V17) and the V27 baby events stay
harmless, and every other harm-capable role keeps the default `auto` protection (nursing parents, the Golden Child
and the Tribal Chief are never cast in it).

### Two Lives, One Decision (`all_v20_d1_two_lives`, V20 D1, source L8950-8968)

- **Villager:** role `mother`, a female villager carrying a baby (special `nursing_parent`, `protected: "allow"`).
  Before the retrofit the patient was an uncast stranger (decision Q11), so nothing happened to anyone.
- **Why:** the whole event is about this risk: "A pregnant villager lies gravely ill; the healers fear for both
  mother and unborn child." The V28 addendum asks for exactly this case ("A nursing mother may lose her baby through
  illness, accident, or another event-specific tragedy"; "both may die only if the event truly endangers both").
  Every effect follows an outcome the owner wrote. The three deaths (A3, A4, B4) are very rare (2 against a normal
  20; the source gives no odds), per V28's global rule; the other outcomes keep equal weight.
- **Requirement:** the event is now drawn only when a villager is carrying a baby.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| A2 | "The mother survives but the child dies; a solemn mourning follows." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | 20 of 64 in choice A |
| A3 | "The child survives but the mother dies; the family remembers her courage." | `birth_then_die`, cause Unknown causes (the game's own delivery brings the baby now, early if need be; then she dies with a grave) | very rare: 2 of 64 in choice A |
| A4 | "Neither survives; the healer questions whether the decision was right." | `kill`, cause Unknown causes (the baby she carries is lost with her) | very rare: 2 of 64 in choice A |
| A5 | "Both survive, though the mother requires prolonged care." | `health_change` -30..-10 | 20 of 64 in choice A |
| B2 | "The mother survives but loses the baby." | `baby_lost` | 20 of 62 in choice B |
| B3 | "The condition worsens, demanding a desperate intervention." | `health_change` -30..-10 | 20 of 62 in choice B |
| B4 | "Both die; villagers disagree about whether waiting was a mistake." | `kill`, cause Unknown causes (and the baby) | very rare: 2 of 62 in choice B |
| C2 | "She chooses gentler care; her recovery is prolonged and uncertain." | `health_change` -30..-10 | 1 in 3 of choice C |

- **Done:** A3, "The child survives but the mother dies; the family remembers her courage." **Owner (2026-11-14):** A3 must change so the child really survives. It now uses the `birth_then_die` effect (cie-v6-binary.md 23): the game's own delivery brings the baby, then the mother dies; very rare, as a death.
- **Owner decision (2026-11-14): APPROVED as built** -- the cast pregnant villager, `baby_lost` and the very rare kills; A3's `birth_then_die` is approved with the rest of D1.

## Companion K5

Range: Companion Anthology Vol 1 Part 4 N051-N069 (`companion/c5/c5dn051`-`c5dn069`) and The Lives Between Legends
001-060 (`companion/lbl/lbl001`-`lbl060`), 79 events. Line numbers are the companion source's.

One event harms a protected villager. Every other harm-capable role in this range keeps the default `auto`
protection, so nursing parents, the Golden Child and the Tribal Chief are never cast in it: LBL 016's hurt
apprentice, 025's child who falls ill, 026's injured and missing teens, 027's child who falls and 059's straining
elder. The other baby scenes (LBL 037-040, 042, 045 and N057) cast a nursing parent only harmlessly (Parenting or
nothing), and 043's bereaved mother is a woman who is not nursing (the baby is text).

### The Sudden Fever (`lbl044_sudden_fever`, LBL 044, companion L4368-4378)

- **Villager:** role `mother`, a female villager carrying a baby (special `nursing_parent`, `protected: "allow"`).
  A nursing baby is its parent's state in every game, so the baby can be reached only through her.
- **Why:** the event is about the baby's illness, and the owner wrote its fatal branch: "A baby becomes ill during a
  difficult season." The engine rules say nursing mothers and infants "are not immune to plausible fatal events"
  (L3784). The mother herself is never hurt: only her baby is lost.
- **Requirement:** the event is drawn only when a villager is carrying a baby.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| 1 | "Prompt care brings recovery." | small Parenting to the mother | 20 of 45 |
| 2 | "The baby remains ill and needs ongoing attention." | small Parenting to the mother (the baby cannot be made `sick`: it is not a villager) | 20 of 45 |
| 3 | "A rare fatal outcome leaves the family mourning." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | rare: 5 of 45 (the source's own "rare") |

## Companion K6

Range: The Lives Between Legends 061-120 (`companion/lbl/lbl061`-`lbl120`), 60 events, generator
`scripts/companion/gen_k6.py`. Line numbers are the companion source's.

**No entries.** No role in this range uses `protected: "allow"`. The harm-capable roles keep the default `auto`
protection, so nursing parents, the Golden Child and the Tribal Chief are never cast in them:

| Event | Outcome | Villager | Exact text | Effect | Chance |
|---|---|---|---|---|---|
| The Bottomless Pool (`lbl073_bottomless_pool`, L4753-4767) | 2 | `explorer` | "A dangerous dive causes injury." | `health_change` -30..-10 | 20 of 45 |
| The Bottomless Pool | 3 | `explorer` | "The explorer disappears and an uncertain search begins." | `vanish` (missing is not dead: no grave) | rare: 5 of 45 |
| The Dangerous Proof (`lbl082_dangerous_proof`, L4874-4884) | 3 | `teen` | "They are injured and must confront their recklessness." | `health_change` -30..-10 | 1 in 3 |
