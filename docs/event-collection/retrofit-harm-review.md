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
  Every effect follows an outcome the owner wrote. The two deaths (A4, B4) are very rare (2 against a normal
  20; the source gives no odds), per V28's global rule; the other outcomes keep equal weight.
- **Requirement:** the event is now drawn only when a villager is carrying a baby.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| A2 | "The mother survives but the child dies; a solemn mourning follows." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | 20 of 82 in choice A |
| A4 | "Neither survives; the healer questions whether the decision was right." | `kill`, cause Unknown causes (the baby she carries is lost with her) | very rare: 2 of 82 in choice A |
| A5 | "Both survive, though the mother requires prolonged care." | `health_change` -30..-10 | 20 of 82 in choice A |
| B2 | "The mother survives but loses the baby." | `baby_lost` | 20 of 62 in choice B |
| B3 | "The condition worsens, demanding a desperate intervention." | `health_change` -30..-10 | 20 of 62 in choice B |
| B4 | "Both die; villagers disagree about whether waiting was a mistake." | `kill`, cause Unknown causes (and the baby) | very rare: 2 of 62 in choice B |
| C2 | "She chooses gentler care; her recovery is prolonged and uncertain." | `health_change` -30..-10 | 1 in 3 of choice C |

- **Not made:** A3, "The child survives but the mother dies; the family remembers her courage." The games keep an
  unborn baby only as the mother's own state, so killing her would end the baby too and contradict the text. A3 stays
  told only and harms no one. **Owner question:** keep A3 told only, or kill the mother there as well (the baby would
  then be lost with her)?
- **Owner question:** approve this case, or return D1 to an uncast stranger (no effects)?
