# Villager Breeding Overhaul: age, preference, and parenting-skill audit

Status: research and patch-boundary definition. No executable patch is enabled by this note.

This note records the exact behavior that the planned Birth Control / Villager
Breeding Overhaul patches are allowed to change. The supplied Windows builds are
treated independently; an observation from one game is not silently applied to
another.

## VV4: what the old-mother evidence does and does not prove

The preserved VV4 IDA analysis covers `Virtual Villagers - The Tree of Life.exe`
(929,792 bytes; SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`).
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

The historical VV4 Birth Control candidate is rejected/superseded. VV4 is the
untouched vanilla Breeding and Embracing reference: its stock manual conception
and autonomous selection mechanics, older-mother behavior, and lack of a male
upper-age gate must remain unchanged. No VV4 executable edits are shipped or
selectable.

The remaining overhaul entries for VV1, VV2, and VV3 are independent ON HOLD
tasks. They require exact-build coverage rather than a shared copied predicate.
VV5 is also a native no-patch reference: its exact-build audit matches VV4's
requested Birth Control/Breeding behavior.

### VV1 exact-build rejected proposal (`c8d268d`)

The 581,632-byte VV1 build has no manual-pairing age ceiling. Exact-build audit
commit `c8d268d` rejects the prior patch proposal:

- file offset `0x3DBBE` is the stock `food >= 400` gate, not an age predicate;
- `0x458D0` and `0x45930` are live instruction interiors, not code caves;
- `0x56740` is not a certified cave or placement;
- the prior proposal incorrectly rejected both sexes, while the requested VV4
  reference is sex/category-2 carrier-only at internal age `>=1000` and has no
  male upper-age ceiling.

Complete VV1 coverage requires the planner scan at `0x4477AF` plus the
action-9 writer-reaching commit scans at `0x446E70` and `0x447070`. Catch-up
reuses the chooser/action-9 path. Direct event-created births and pending
delivery remain native. VV1 therefore remains ON HOLD until a complete exact
safe hook and placement are proved; no replacement bytes are proposed here.

For VV2 and VV3, the documented stock age comparisons and call chains must be
rechecked against the current manifest before any replacement is written.

### VV5 exact-build audit: native no-patch reference

The New Believers build (`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`,
991,232 bytes) is a native no-patch reference. Its manual pair handler
`0x4689A0`, autonomous chooser `0x46A3C0`, candidate selector `0x470A10`,
pregnancy wrapper `0x467D20`, and pregnancy writer `0x465E00` match the VV4
paths at `0x460C10`, `0x461CC0`, `0x466DA0`, `0x460990`, and `0x45E7B0`,
respectively, after accounting for VV5's sixth Devotion skill shifting the
preference storage from `+0x1C70` to `+0x1C74`. Both manual handlers retain a
female-only internal-age-1000 rejection and no male upper-age gate; candidate
selectors reject only the scanned candidate, not the initiator. Offline
delivery uses the native pending-plus-40 comparison and clears the pending
marker/count. Direct event and puzzle births bypass these manual/autonomous
gates and remain native. No VV5 Birth Control bytes are implemented or
reserved.

## Implementation status

VV1 and VV3 remain research-only until their exact before-bytes,
non-overlapping placement, return paths, and tests are verified for each
supported SHA-256 build. VV1's rejected historical patch list is empty; no
invalid food-gate or live-code edit is offered. VV2 implements only the two
certified writer-reaching opcode-12 candidate scans described below. VV4 and
VV5 are native no-patch references; no Birth Control runtime patch is offered,
applied, or reserved for either game.

### VV2 exact-build implementation (`74778bd6a7d3a17dd990636cf6d4e769466800c6`)

The Lost Children build is exactly 724,992 bytes with SHA-256
`46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`.
Its Birth Control feature is one atomic optional patch containing two complete
40-byte guarded replacements:

- file `0x6488D` / VA `0x46488D`; the new `JGE` targets `0x464A3D`;
- file `0x64A8F` / VA `0x464A8F`; the new `JGE` targets `0x464C52`.

Each replacement preserves candidate sex in `EDX`, compares the already-loaded
candidate age in `EAX` with 1000, and rejects only at the corresponding
writer-reaching opcode-12 candidate commit. Together the two scans cover
ordinary autonomous/catch-up pairing and stew recipe 15. The patch does not
claim broader breeding parity.

The stock manual carrier/female-only age-less-than-1000 gate remains unchanged;
there is no male upper-age gate. Chooser scoring, token 43 exact string `work`,
willingness token 39 `learning`, planner logic, pregnancy writer, delivery,
save format, RNG, food, fertility, capacity, messages, statistics, Love Note,
Gong grant, Silver Mirror clone, and direct/event births remain native.
