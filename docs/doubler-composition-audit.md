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

The requested final composition contract is to stack with each game's native
collectible tech-point gains and Food Mastery technology adjustment. Golden Child behavior,
Island Event outcomes, and Gong of Wonder outcomes must remain unmultiplied.
This is a requirement for each exact-build GO audit, not a claim that the
pending/STOP games are already verified.

The current source contains static guards. VV2 is marked **GO** below because
the exact-build inventory and provenance exclusions are complete; this is a
static proof only and is not a claim of runtime/player confirmation. The other
games remain pending/STOP until their own exact-build audits are complete.

## Exact-build evidence matrix

| Game | Positive tech writer / hook | Positive food writer / hook | Collection adjustment evidence | Island Event evidence | Status |
|---|---|---|---|---|---|
| VV1 A New Home | `0x41D120` / payload `tech_increment` | `0x41D140` / payload `food_increment` | No exact collection-adjustment callsite is recorded in the current Origins evidence set. | Candidate caller returns `0x428194` (tech) and `0x4281DA` (food); complete producer/caller coverage is not yet proved. | **Pending** |
| VV2 The Lost Children | `0x426290` / payload `tech_increment` | `0x4262B0` / payload `food_increment` | Exact build `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` (724,992 bytes) has no separate global collection multiplier in either final writer; callers pass the final native signed delta. | `0x4204B0` returns `0x4205AC`/`0x420AE9`; `0x433600` returns `0x434351`/`0x433FC6`; Gong `0x44E8A0` returns tech `0x44EA32`, `0x44ED52`, `0x44F202` and food `0x44E9C3`, `0x44EDB9`, `0x44F0D9`. Exact wrapper blacklists cover all five tech and all five food returns; direct +3000, losses, caps, resets, and zero paths bypass the positive writers. Full inventory is 17 tech and 13 food calls, with zero E9 tail-jumps. | **GO (static exact-build proof; runtime pending)** |
| VV3 The Secret City | `0x427130` / payload `tech_increment` | `0x4263F0` / payload `food_increment` | No exact collection-adjustment callsite is recorded in the current Origins evidence set. | Candidate exclusion is the dispatcher range `0x458DB0..0x45943F`; every direct and tail-jump producer still needs static proof. | **Pending** |
| VV4 The Tree of Life | `0x41E300` / payload `tech_increment` | `0x41D920` native writer; Food Mastery completes before any eligible doubler | Exact build `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` has 21 external tech and 23 external food writer references. Collection call `0x414660` supplies pre-mastery 6/35; native Food Mastery is A, A+floor(A/2), or 2A for levels 0/1, 2, and 3. | Complete inventory records event tails `0x4156F8`, `0x415862`, `0x41586F`, `0x415A81`, `0x415B46`, `0x415D8C`, `0x416722`, `0x416735`, food tail `0x41520E`, and generic event direct sites. No return-address-only exclusion can classify the E9 tails. | **STOP** |
| VV5 New Believers | `0x4237B0` / payload `tech_increment` | `0x41EB6F` before stock statistics hook | The food hook is before the separate statistics hook, but the exact collection adjustment and all positive-tech composition sites still need an independent call-site record. | Event methods in `0x414A30..0x416CD0` call or tail-jump to the central writers. The current return-address blacklist is explicitly incomplete for tail-jumps; exact exclusion remains unresolved. | **STOP** |

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
