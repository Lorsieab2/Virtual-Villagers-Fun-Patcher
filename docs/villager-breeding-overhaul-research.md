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

Birth Control feature ownership stops at each game's named ordinary route.
The feature must not add, remove, or replace any special-outcome age, sex,
preference, eligibility, conception, pregnancy, delivery, capacity, RNG,
message, statistic, or state-write behavior. Automatic physical-capacity safety is a
separate cross-game layer applied in Stock, Collection Progression, and
Immediate Fixed; it may clamp a special outcome's physical allocation without
becoming Birth Control behavior. Birth Control does not own Island Event
pregnancy, birth, and child outcomes; in VV2, every Gong of Wonder outcome remains
outside Birth Control for the same reason. These are control-flow/provenance
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

- `sub_460C10`: the live pairing (“Embracing”) handler, step 15 of the
  villager step dispatcher `sub_46A030`, shared by the player's drop and by
  villagers pairing up on their own (see below);
- `sub_461CC0`: autonomous action/category chooser;
- `sub_466DA0`: action-15 mate selector;
- `sub_464FA0`: action-15 conception formula;
- `sub_468430`: per-villager life/catch-up loop.

### Manual and live autonomous route

Two live routes reach `sub_460C10`, both through action 3 (`sub_455420`,
which queues step 15): the player's drop (`0x440EED`, inside the drop handler
`sub_440C60`) and live autonomous pairing (`0x463FC3`, from the category
chooser's Children branch at `0x464181`, which first queues a walk to the
partner). The drop clears the dropped villager's steps, so the handler runs
at once inside the drop's call; the autonomous initiator's handler runs later,
when its walk arrives (`sub_468C10`). Catch-up executes the same step 15 in
its own executor (`sub_464FA0`) and never reaches this handler. VV5 has the
same shape: action 5 (`sub_45D010`, step 16) from the drop at `0x444028` and
from autonomous pairing at `0x46CB1E`; VV1, VV2 and VV3 likewise share their
pairing handlers between the drop and autonomous pairing (VV1 `0x4252B9` and
`0x447886` into `sub_445510`; VV2 `0x430F5E` and `0x46044C` into
`sub_45D510`; VV3 `0x4669D1` and `0x45B674` into action 4).

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
the routine returns without calling the conception writer. Therefore neither
the ordinary player-drag/manual route nor live autonomous pairing provides the
reported over-50 mother behavior, even when the skill roll would otherwise
succeed.

### Autonomous choice and the preference fallback

The chooser `sub_461CC0` uses the five-skill block beginning at `+7260`;
VV4's Breeding/Parenting skill is `+7264` (`+0x1C60`). The “Children” choice
is category `1` and the selected preference is stored at `+7280` (`+0x1C70`).
For category 1, the chooser subtracts 15 from the skill for its score and
requires the score to exceed 5 before an action can be selected. In other
words, the chooser's non-random floor is a Breeding value above 20, followed by
the stock action roll. A checked Children preference forces category 1 when the
preference override is taken; without that preference, category 1 is not
guaranteed.

This is the literal VV4/VV5 autonomous “Embracing” predicate. A checked
Children preference participates in the native override, but it is not an
absolute prerequisite: when category 1 is selected without that preference,
the native chooser retains a 25% fallback roll. VV1 reproduces this tail in its
owned helper page; VV2 and VV3 already contain the same native floor/fallback.
The Birth Control patches do not replace this random branch with a stricter
preference-only rule. They do not own Island Events, the Gong of Wonder, or any
direct event-created nursing-baby writer; the separate automatic safety layer
still protects physical allocation in every public mode.

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
upper-age gate must remain unchanged. No VV4 Birth Control executable edits are
shipped or selectable.

One later exception, added at the owner's request: the optional,
default-off "Manual Drop-Breeding overrides Birth Control" patch
(`vv4_manual_drop_breeding_overrides_birth_control`). When it is selected, the
woman-aged-50-or-older refusal after the stock conception roll (file `0x60E67`)
first tests for the player's drop -- its return address `0x440EF2` at
`[esp+0x40]`, where the drop's own call chain puts it -- and only then jumps to
the stock pregnancy-writer call at `0x460E8E`. Because live autonomous pairing
runs the same handler later, from its walk's arrival, it never matches and
keeps the stock refusal (the patch's first version skipped the refusal for
both). Every other manual rule, both stock chance rolls, autonomous pairing and
selection and the male age behavior stay stock. With that patch unselected,
VV4 is exactly the reference described above. VV5 has the same optional patch
at file `0x68BC4` (drop return address `0x44402D` at `[esp+0x4C]`).

VV1, VV2, and VV3 now have independent exact-build records. Their static
coverage is separate rather than a shared copied predicate; runtime/player
confirmation remains pending. VV3 remains ON HOLD for runtime/player
interpretation. VV5 is also a native no-patch reference: its exact-build audit
matches VV4's requested Birth Control/Breeding behavior (apart from the
optional Manual Drop-Breeding exception above, when it is selected).

### Catch-up babies (all five games, 2026-11-19)

The owner: Parenting-ticked villagers should embrace and have babies during
catch-up, "as part of birth control for all 5 games". Every game's catch-up
job turn (A New Home `0x42E790`, The Lost Children `0x43B4D0`, The Secret City
`0x45BF00`, The Tree of Life `0x465750`, New Believers `0x46E8E0`) takes the
chooser's pick and, for the Children pick only, rolls RNG(100) <= 5 before the
embrace (`cmp eax,5; jg` at `0x42E7EF`, `0x43B53C`, `0x45BF61`, `0x4657AE`,
`0x46E93E`), so it tries on 6 job turns in 100 while every other pick goes on
to its job. Live play has no such roll: there the Children pick goes straight
to the work dispatcher. Each game's Birth Control row now raises the bound to
99 (one guarded byte), so the pick always goes on to the embrace. The chooser,
the partner search, the conception roll, the population limit, huts and live
play are unchanged; children (under 280 age units) get no job turns at all.

This is the only edit the new `vv4_birth_control` and `vv5_birth_control`
rows make (on by default, like the VV1-VV3 Birth Control rows). It supersedes the
statement above that no VV4/VV5 Birth Control bytes are shipped: the historical
VV4 candidate's age-gate edits stay rejected and unapplied, and apart from that
one catch-up byte VV4 and VV5 remain the native reference.

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
the category-2 carrier at internal age `>=1000`. The catch-up embrace
(opcode 9 of the step runner `0x446C70`, called only from the catch-up job
turn `0x42E790`) is a one-partner pick in every mode since 2026-11-21 (see
"One partner per catch-up embrace" below); Birth Control adds the candidate-only
`<1000` bound to it at `0x46ECE` and keeps the initiator's stock `>=360` check. The planner hook at
`0x477FA` likewise adds only the candidate upper bound before the stock
initiator check. The chooser tail at `0x39C80`/`0x39C83` now uses the same
score floor and non-preference fallback as the VV4/VV2/VV3 chooser while
preserving VV1's native category/skill mapping. Catch-up reuses the
chooser. Direct event-created births and pending delivery remain
outside Birth Control ownership; automatic physical-capacity safety is applied
separately in every public mode. Static verification is complete; runtime/player
confirmation remains pending.

The former rejection evidence remains relevant as a negative boundary: the
historical `0x3DBBE` food gate, live instruction interiors, and uncertified
`0x56740` cave are not used by the implementation.

VV2 retains its independent two-site implementation described below; its
native chooser and conception formula already match the VV4/VV5 reference
contract. Its pregnancy writer and delivery remain outside Birth Control
ownership, while automatic physical-capacity safety applies separately in every
public mode. VV3's ordinary action-13 selector is covered by the implementation
in the next section; its native chooser, manual, conception, pregnancy, and
special routes remain unchanged by Birth Control.

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
remain outside Birth Control ownership. Automatic physical-capacity safety may
still clamp their allocations in every public mode. Static verification is
complete; runtime/player confirmation remains pending.

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
gates and remain outside Birth Control ownership. No VV5 Birth Control bytes are implemented or reserved. The automatic capacity layer remains separate.

## Implementation status

VV1, VV2, and VV3 have independent exact-build Birth Control records. VV1's
owned helper page and its guarded code edits, plus VV3's five complete
initiator-check removals, are statically verified against their recorded stock
hashes. VV2 and VV3 already contain the literal VV4/VV5 chooser score floor and
25% non-preference fallback natively; VV1 now matches that chooser tail without
changing its game-specific skill/category mapping. All three retain native
manual female/carrier gates, conception formulas, pregnancy writers, and
pending-delivery behavior outside their named route edits. Automatic
physical-capacity safety is separate and applies in every public mode.
Runtime/player confirmation remains pending. VV4 and VV5 remain native
no-patch references.

### One partner per catch-up embrace (VV1 and VV2, 2026-11-21)

The owner's decision: Birth Control must work more or less the same in all five
games, so in VV1 and VV2 the catch-up pairing uses one partner per try whether
Birth Control is ticked or not, as in VV3-VV5 ("One partner always"). A man
picks his one partner from every eligible woman, a woman hers from every
eligible man. Birth Control then only changes how often a Children-choice
villager with Parenting ticked tries (every such job turn instead of 6 in 100),
plus the partner age bound it has in the later games.

Stock VV1 and VV2 run the catch-up embrace as two scans over all 256 villager
slots in the step runner (VV1 `0x446C70` opcode 9: `0x446E70-0x44704F` then
`0x447055-0x447256`; VV2 `0x464680` opcode 12: `0x464847-0x464A4E` then
`0x464A54-0x464C63`). Each scan calls the pregnancy writer for every villager
who passes and never stops at a conception, so one man's job turn can make
every eligible woman pregnant. The runners are called only from the catch-up
job turns (VV1 `0x42E80D`/`0x42E825`, VV2 `0x43B55A`/`0x43B58C`; no absolute
pointer to either exists). The Tree of Life's catch-up embrace `0x464FA0`
instead calls its mate selector `0x466DA0` once -- every villager who can pair
is listed, one is picked with `rand(count)` -- and makes one conception roll.

The patcher's automatic safety rows (applied in Stock, Collection Progression
and Immediate Fixed, like the physical-capacity safety) replace the start of the
first scan with that pick, written in place at VV1 file `0x46E70` (208 bytes)
and VV2 file `0x64847` (231 bytes): every villager of the other sex who can pair
by the stock scans' own rules is listed (alive, candidate age `>=360`, health
above 0, not sick, not pregnant/nursing, with the scans' own initiator checks;
VV1 has no upper age, VV2 requires the woman of the pair to be under `1000`),
one is picked with the game's own RNG (`0x402F10`, `0x4031A0`), and that partner
enters the second scan at its food refusal (`0x447112`, `0x464B0E`), so the
room check, the Parenting check, the conception roll and the writer call
(`0x447238`, `0x464C4D`) are the stock code and the parentage hooks see the
frame they always saw. VV1 `0x4723D` and VV2 `0x64C52` end the embrace after
that one attempt.

Birth Control writes only the age bound inside the pick (the overlap is allowed
for exactly these bytes by `BIRTH_CONTROL_PICK_OVERLAYS` in
`src/vv_fun_patcher.py`): VV1 `0x46ECE` turns eight NOPs into `cmp edx,1000 /
jge`, so a candidate 50 or older is not listed; VV2 `0x6487E` steps over the
stock woman-initiator `<1000` rule and `0x648C0` bounds every candidate under
`1000`, man or woman. The candidate age bound that VV1's page once applied at
`0x46E96`/`0x47084` and VV2's 40-byte blocks applied at `0x6488D`/`0x64A8F` is
therefore part of the pick.

Live play already pairs one partner per embrace: VV1 step 9 runs `0x43DAD0`
from the step dispatcher `0x43DEF0`, VV2 step 12 runs `0x44F610` from
`0x44FBB0`; each takes the one villager found at the initiator's position
(`0x439350`, `0x449160`) and calls the writer at most once. Nothing live is
changed. `tests/test_birth_control_one_partner.py` emulates both runners from
their entries, stock and patched, in all three modes, with and without Birth
Control, for a man and for a woman who tries.

### VV2 exact-build implementation (`74778bd6a7d3a17dd990636cf6d4e769466800c6`)

(The two scan blocks below were Birth Control's catch-up age bound until
2026-11-21; the one-partner pick above replaced them.)

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
there is no male upper-age gate. The native VV4/VV5-style chooser score floor
and 25% non-preference fallback, token 43 exact string `work`, willingness token
39 `learning`, planner logic, conception roll, pregnancy writer, delivery, save
format, RNG, food, fertility, messages, statistics, Love Note, Gong grant,
Silver Mirror clone, and direct/event births remain outside Birth Control
ownership. Automatic physical-capacity safety remains a separate layer in all
three public modes.

The static exclusion boundary is exact:

- Love Note Island Event call file `0x22006` goes directly to the stock
  pregnancy writer and does not enter either patched scan;
- Gong "grants life" call file `0x4EB3E` likewise reaches the stock pregnancy
  writer directly, and every other Gong path remains outside the two patches;
- Silver Mirror call file `0x217F9` enters the stock clone constructor rather
  than the pregnancy writer;
- the stock pregnancy writer begins at file `0x4B980`;
- pending delivery calls its native helper at file `0x3BE8E`, then retains the
  stock marker/count clears at `0x3BF70` and `0x3BF85`; automatic safety owns
  only the delivery-capacity guard at `0x3BE8E`/`0x473F20` in every public mode;
- the manual carrier gates at `0x4F7C8..0x4F7FE` remain byte-identical;
- the six stock calls into the pregnancy writer remain at `0x22006`,
  `0x4EB3E`, `0x4F8F0`, `0x4F930`, `0x64A38`, and `0x64C4D`.

Only the predicates immediately upstream of the final two ordinary
writer-reaching calls are changed. Consequently no Island Event or Gong
outcome gains a Birth Control age, sex, preference, eligibility, conception,
pregnancy, delivery, RNG, message, statistic, or state-write rule. The separate
automatic physical-capacity layer may still clamp allocation in every public
mode.
