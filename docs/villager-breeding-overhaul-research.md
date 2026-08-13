# Villager Breeding Overhaul: age, preference, and parenting-skill audit

Status: exact-build static implementation and patch-boundary definition. Runtime/player confirmation remains pending.

This note records the exact behavior that the planned Birth Control / Villager
Breeding Overhaul patches are allowed to change. The supplied Windows builds are
treated independently; an observation from one game is not silently applied to
another.

## Hard special-outcome exclusion contract

Every current or future Birth Control, pregnancy, or Embracing patch is limited
to the exact ordinary manual, autonomous, or catch-up route named by its
game-specific GO evidence. It must not intercept or reinterpret a special
outcome merely because that outcome eventually reaches a shared pregnancy,
birth, clone, child, or population writer.

All Island Event pregnancy, birth, and child outcomes remain completely native.
The patch must not add, remove, or replace any Island Event age, sex,
preference, eligibility, conception, pregnancy, delivery, capacity, RNG,
message, statistic, or state-write behavior. In VV2, every Gong of Wonder
outcome has the same complete exclusion. These are control-flow/provenance
exclusions, not amount- or result-based exceptions.

Any future GO report for VV1 and VV3 must enumerate every applicable
ordinary route and prove that every Island Event or other special direct route
bypasses the proposed patch. Partial field mappings, shared-writer xrefs, or
candidate predicates are insufficient. VV4 and VV5 remain untouched native
references.

VV3 remains ON HOLD for runtime/player interpretation. Do not interpret a
special outcome bypassing Birth Control as a defect; that bypass is part of
the required native exclusion boundary.

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

VV1, VV2, and VV3 now have independent exact-build records. Their static
coverage is separate rather than a shared copied predicate; runtime/player
confirmation remains pending. VV5 is also a native no-patch reference: its
exact-build audit matches VV4's requested Birth Control/Breeding behavior.

### VV1 exact-build implementation

The 581,632-byte VV1 build has no manual-pairing age ceiling. Exact-build audit
commit `c8d268d` rejects the prior patch proposal:

- file offset `0x3DBBE` is the stock `food >= 400` gate, not an age predicate;
- `0x458D0` and `0x45930` are live instruction interiors, not code caves;
- `0x56740` is not a certified cave or placement;
- the prior proposal incorrectly rejected both sexes, while the requested VV4
  reference is sex/category-2 carrier-only at internal age `>=1000` and has no
  male upper-age ceiling.

The implemented VV1 feature uses an owned executable `.vv1bc` section at raw
`0x8E000` / VA `0x490000`; it does not consume the historical `.text` gaps or
the Origins `.shr`/code-patch ranges. The manual hook at `0x3DD03` rejects only
the category-2 carrier at internal age `>=1000`. The two action-9
writer-reaching scans at `0x46E96` and `0x47084` add candidate-only upper
bounds while preserving both stock `>=360` checks. The planner hook at
`0x477FA` likewise adds only the candidate upper bound before the stock
initiator check. The chooser tail at `0x39C80`/`0x39C83` now uses the same
score floor and non-preference fallback as the VV4/VV2/VV3 chooser while
preserving VV1's native category/skill mapping. Catch-up reuses the
chooser/action-9 route. Direct event-created births and pending delivery
remain native. Static verification is complete; runtime/player confirmation
remains pending.

The former rejection evidence remains relevant as a negative boundary: the
historical `0x3DBBE` food gate, live instruction interiors, and uncertified
`0x56740` cave are not used by the implementation.

VV2 retains its independent two-site implementation described below. VV3's
ordinary action-13 selector is covered by the implementation in the next
section; its native manual and special routes remain unchanged.

### VV3 exact-build implementation and special-outcome boundary

The implemented VV3 feature changes only the five repeated initiator-age
comparisons in the exact ordinary action-13 mate selector at file offsets
`0x5CE74`, `0x5CF35`, `0x5CFFC`, `0x5D0C0`, and `0x5D187`. Each candidate's
native `360..999` test remains intact; only the duplicate initiating-villager
`>=1000` rejection is removed. The native manual handler at VA `0x4584B0`
retains its category-1 carrier/female-only internal-age-1000 rejection for
both participants. The selector is reached by the ordinary autonomous and
catch-up action path; direct constructors, clone paths, saved pending delivery,
Island Event pregnancy/birth/child outcomes, and every other special producer
remain native. Static verification is complete; runtime/player confirmation
remains pending.

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

VV1, VV2, and VV3 have independent exact-build Birth Control records. VV1's
owned helper page and six guarded code hooks, plus VV3's five complete
initiator-check removals, are statically verified against their recorded stock
hashes. VV2 and VV3 already contain the VV4 chooser score floor and
preference fallback natively; VV1 now matches that chooser tail without
changing its game-specific skill/category mapping. Runtime/player confirmation
remains pending. VV1/VV2/VV3 records do not claim to alter special event
births, pending delivery, or unrelated writers. VV4 and VV5 remain native
no-patch references.

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

The static exclusion boundary is exact:

- Love Note Island Event call file `0x22006` goes directly to the stock
  pregnancy writer and does not enter either patched scan;
- Gong "grants life" call file `0x4EB3E` likewise reaches the stock pregnancy
  writer directly, and every other Gong path remains outside the two patches;
- Silver Mirror call file `0x217F9` enters the stock clone constructor rather
  than the pregnancy writer;
- the stock pregnancy writer begins at file `0x4B980`;
- pending delivery calls its native helper at file `0x3BE8E`, then retains the
  stock marker/count clears at `0x3BF70` and `0x3BF85`;
- the manual carrier gates at `0x4F7C8..0x4F7FE` remain byte-identical;
- the six stock calls into the pregnancy writer remain at `0x22006`,
  `0x4EB3E`, `0x4F8F0`, `0x4F930`, `0x64A38`, and `0x64C4D`.

Only the predicates immediately upstream of the final two ordinary
writer-reaching calls are changed. Consequently no Island Event or Gong
outcome gains a patched age, sex, preference, eligibility, conception,
pregnancy, delivery, capacity, RNG, message, statistic, or state-write rule.
