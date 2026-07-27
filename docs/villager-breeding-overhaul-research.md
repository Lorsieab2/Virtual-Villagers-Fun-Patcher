# Villager Breeding Overhaul: age, preference, and parenting-skill audit

Status: research and patch-boundary definition. No executable patch is enabled by this note.

This note records the exact behavior that the planned Birth Control / Villager
Breeding Overhaul patches are allowed to change. The supplied Windows builds are
treated independently; an observation from one game is not silently applied to
another.

## VV4: what the old-mother evidence does and does not prove

The preserved VV4 IDA analysis covers `Virtual Villagers - The Tree of Life.exe`
(SHA-256 `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`).
The relevant routines are:

- `sub_460C10`: player/manual “Embracing” route;
- `sub_461CC0`: autonomous action/category chooser;
- `sub_466DA0`: action-15 mate selector;
- `sub_464FA0`: action-15 conception formula;
- `sub_468430`: per-villager life/catch-up loop.

### Manual route

`sub_460C10` first applies the ordinary eligibility checks: both ages at least
`360` internal units (18 displayed years), opposite sex/category, positive
health, no illness, no pending child, and the stock fertility gates. It then
uses the actor's Breeding/Parenting value at `+0x1C60` in this formula:

```text
R = RNG(300)
T = Breeding + 50*technology_level - 50
the conception roll succeeds when R <= T
```

The same routine has an additional explicit age gate after that roll. If either
participant is age `>=1000` (50 displayed years) and has the female category,
the routine returns without calling the conception writer. Therefore the
ordinary player-drag/manual route does **not** provide the reported over-50
mother behavior, even when the skill roll would otherwise succeed.

### Autonomous choice and the preference requirement

The chooser `sub_461CC0` uses the five-skill block beginning at `+7260`;
VV4's Breeding/Parenting skill is `+7264` (`+0x1C60`). The “Children” choice
is category `1` and the selected preference is stored at `+7280` (`+0x1C70`).
For category 1, the chooser subtracts 15 from the skill for its score and
requires the score to exceed 5 before an action can be selected. In other
words, the chooser's non-random floor is a Breeding value above 20, followed by
the stock action roll. A checked Children preference forces category 1 when the
preference override is taken; without that preference, category 1 is not
guaranteed.

This is the autonomous “Embracing” predicate that the overhaul must tighten:
both the positive Breeding/Parenting score and the checked Children preference
must be present. The patch must not alter Island Events, the Gong of Wonder, or
any direct event-created nursing-baby writer.

### Why a woman over 50 can still appear after catch-up

`sub_466DA0` is the action-15 mate selector. Its age comparison is asymmetric:
the **candidate it scans** must be younger than `1000`; the selected actor's
age is not rejected by that comparison. The selector still requires both
villagers to be at least `360`, opposite category, active/alive/not ill,
without pending children, with distinct identity/home pairs, and with positive
health.

The offline path `sub_468430` advances each villager one processed-age unit at a
time and runs the reproduction/birth state during that loop. `sub_464FA0` then
uses the actor's Breeding value in the formula above. Thus the static evidence
supports this precise explanation for the forum reports: an older woman can be
the autonomous actor during catch-up, select a younger eligible candidate, and
pass the stock Breeding roll. It is not evidence that manual dragging may
conceive at 50+, nor that a fixed “high skill” cutoff exists.

The exact numeric requirement is therefore not “skill >= N.” It is:

1. the autonomous chooser must select Children (the preference and skill score
   gates above);
2. the candidate must satisfy `sub_466DA0`'s health/age/state/identity checks;
3. the conception roll must satisfy `RNG(300) <= Breeding + 50*technology - 50`;
4. the actor must be reached by the per-unit catch-up/reproduction loop.

The existing staff/community discussion is consistent with this boundary but
is not executable proof of a hidden threshold: [LadyCFII's VV4 reply](http://www.ldwforums.com/ubbthreads/ubbthreads.php?ubb=showflat&Number=224448#Post224448)
says there is no set age limit for mothers, while the surrounding report
describes a 71-year-old adept parent nursing after the player was away. The
[older-mother discussion](http://www.ldwforums.com/ubbthreads/ubbthreads.php?ubb=showflat&Number=221623&page=1)
also describes older autonomous births. Those posts support the catch-up /
autonomous interpretation; they do not supply a numeric Breeding threshold.

## Other games and patch boundary

VV4 now has an exact-build guarded Birth Control entry. Its manual conception
tail replaces the stock female-only age rejection with an age-1000 rejection
for either participant. Its autonomous Children return path denies the
skill-selected fallback when the initiating villager's Children preference is
not checked. The patch does not touch `sub_466DA0`, so the catch-up route can
still select a younger candidate for an older actor as in the stock game.

The remaining overhaul entries will add exact-build guards for VV1, VV2, VV3,
and VV5 only after each manual and autonomous call site has a verified byte
fingerprint. The common behavioral contract is:

- manual/player conception is denied when a participating villager is age
  `>=1000`, except for a separately verified catch-up route;
- autonomous Embracing is allowed only when the initiating villager has a
  positive Breeding/Parenting skill and the Children/Parenting preference is
  checked; the candidate keeps the stock eligibility rules;
- Island Events, Gong of Wonder effects, Barrel-of-Babies-style event writers,
  and other event-created or event-nursing routes remain stock;
- no unused save fields, likes/dislikes, or record strides are repurposed.

For VV1 specifically, the existing offline loop (`sub_42E900`) is the
separately identified catch-up route. The manual `sub_43DAD0` path has no stock
upper-age comparison, so its age guard must be added without intercepting the
catch-up reproduction helpers. The autonomous preference/skill gate must be
added at the chooser/action boundary, not at the event or newborn writers.

For VV2, VV3, and VV5, the documented stock age comparisons and call chains
must be rechecked against the current manifest before any replacement is
written. No VV5 old-age exception is inferred from VV4 evidence.

## Implementation status

VV1, VV2, VV3, and VV5 remain research-only until their exact before-bytes,
non-overlapping caves, return paths, and tests are verified for each supported
SHA-256 build. VV4 is statically verified but still awaits player runtime
validation.

### VV2 exact-path audit (2026-07-26)

The Lost Children stock executable's autonomous candidate path is
`sub_44F610` (EA `0x44F610`-`0x44FBA2`). It selects a candidate through
`sub_449160`, checks opposite sex, minimum ages, health, and availability, and
then reaches the stock pregnancy writer. Its age field is record `+0x530`, and
the two internal-age-1000 comparisons are at EAs `0x44F7D7` and `0x44F7EF`.
Those comparisons are inside the autonomous/catch-up path, not a proven
player/manual conception predicate. The main saved-clock loop reaches the
gestation dispatcher through `sub_44F5C0` at EA `0x43BE8E`; twins/triplets are
handled by the adjacent `sub_44CEC0` route. No exact manual conception callsite
or autonomous preference chooser was identified, so the VV2 Birth Control
patch remains disabled. Patching either age comparison alone would incorrectly
change stock catch-up behavior.
