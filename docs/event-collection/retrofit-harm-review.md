# V28 retrofit: harm review (for the owner's approval)

The owner's rule (2026-11-14): only VV2 totems are always protected. Nursing mothers, babies, the Golden Child and the
VV3 Chief may be harmed only where the event's own risk makes sense, with `protected: "allow"` on that role, and every
such case is listed here: the event, the outcome, the villager, the exact text and why. VV5 story villagers (the
chief, the Retired Chief, the puzzles' Heathens) stay unharmable whatever a file says.

`python scripts/collection_check.py --allow-report` lists every `allow` on a harm-capable role for checking against
this file.

## Companion K8

Range: Stone, Spirit, Strangers & Ordinary Lives 001-067 (`companion/sss/sss001`-`sss067`), 67 events. Line numbers
are the companion source's. Generator: `scripts/companion/gen_k8.py`.

One event harms a protected villager. The other harm-capable roles keep the default `auto` protection, so nursing
parents, the Golden Child and the Tribal Chief are never cast in them: SSS 018's worker (a serious injury or a death
in the collapse) and SSS 020's worker (sick from the mineral dust). SSS 053's baby scene casts a nursing parent
harmlessly (no effect).

### The Nursing Mother's Loss (`sss065_nursing_mother`, SSS 065, companion L6729-6737)

- **Villager:** role `mother`, a female villager carrying a baby (special `nursing_parent`, `protected: "allow"`).
  A nursing baby is its parent's state in every game, so the baby can be reached only through her.
- **Why:** the premise has the baby die during the event: "A nursing mother loses her infant after an illness
  despite the caregivers' efforts. The village struggles to know how to support her." The volume's own rule (L6064):
  "Rare serious consequences can affect any involved age or caregiver, including nursing mothers and children". The
  lead's decision (2026-11-14): `baby_lost` on a cast nursing parent. The mother herself is never hurt: only her baby
  is lost.
- **Requirement:** the event is drawn only when a villager is carrying a baby. A question page makes no effects, so
  each of the three answer pages carries the same `baby_lost`: whichever the player picks, the baby is lost once.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| A | "She asks for privacy and practical help; friends honor both." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | every time A is chosen |
| B | "She chooses whether and when to participate, and the baby's name is spoken with care." | `baby_lost` | every time B is chosen |
| C | "Trusted caregivers handle chores and meals; the mother's grief is neither hurried nor treated as a moral failing." | `baby_lost` | every time C is chosen |
