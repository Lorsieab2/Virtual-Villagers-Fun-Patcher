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

**No entries.** K8 adds no `protected: "allow"` and no harm to a nursing parent, a baby, the Golden Child or the VV3
Chief.

- The harm-capable roles keep the default `auto` protection, so nursing parents, the Golden Child and the Tribal
  Chief are never cast in them: SSS 018's worker (a serious injury or a death in the collapse) and SSS 020's worker
  (sick from the mineral dust).
- SSS 053's baby scene casts a nursing parent harmlessly (no effect).
- SSS 065 The Nursing Mother's Loss: the infant has already died, as part of the premise (the lead, 2026-11-14), so
  the mother is an adult woman who need not be nursing, and the baby is text only. Nothing is harmed.

## Companion K7

Range: The Four Ways of Knowing 001-060 (`companion/fwk/fwk001`-`fwk060`), 60 events. Line numbers are the companion
source's. Generator: `scripts/companion/gen_k7.py`.

| Event | Outcome | Villager | Exact text | Why |
|---|---|---|---|---|
| `fwk053_nursing_mother` The Nursing Mother's Impossible Day | choice C (L5972) | `mother`, a nursing parent (female), `protected: "allow"`: `sick` | "Overextend herself and become ill." | The event is about a nursing mother; the player's own choice says she becomes ill. Illness, not injury or death; the baby is untouched. |

- The other harm-capable roles keep the default `auto` protection: FWK 046's apprentice (choice C "Find them injured
  in an isolated place.": a minor injury, health_change -30..-10; choice D "Face an unresolved disappearance.":
  vanish, missing with no grave) and FWK 055's craftsperson (choice C "Give up and develop a dislike of the craft.":
  a dislike of work).
- Part I (001-040) has no harm at all.
