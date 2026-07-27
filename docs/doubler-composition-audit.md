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

The current source contains static candidate guards. Until the complete
call-site audit below is finished, these are **pending/STOP evidence**, not a
runtime claim of full coverage.

## Exact-build evidence matrix

| Game | Positive tech writer / hook | Positive food writer / hook | Collection adjustment evidence | Island Event evidence | Status |
|---|---|---|---|---|---|
| VV1 A New Home | `0x41D120` / payload `tech_increment` | `0x41D140` / payload `food_increment` | No exact collection-adjustment callsite is recorded in the current Origins evidence set. | Candidate caller returns `0x428194` (tech) and `0x4281DA` (food); complete producer/caller coverage is not yet proved. | **Pending** |
| VV2 The Lost Children | `0x426290` / payload `tech_increment` | `0x4262B0` / payload `food_increment` | No exact collection-adjustment callsite is recorded in the current Origins evidence set. | Current wrappers contain one candidate return check per resource; complete producer/caller coverage is not yet proved. | **Pending** |
| VV3 The Secret City | `0x427130` / payload `tech_increment` | `0x4263F0` / payload `food_increment` | No exact collection-adjustment callsite is recorded in the current Origins evidence set. | Candidate exclusion is the dispatcher range `0x458DB0..0x45943F`; every direct and tail-jump producer still needs static proof. | **Pending** |
| VV4 The Tree of Life | `0x41E300` / payload `tech_increment` | `0x41D94F` post-mastery / payload `food_increment` | The food hook is intentionally after the native post-mastery delta. The exact collection adjustment and its representation still need an independent call-site record. | Candidate tech returns: `0x414A2D`, `0x4156FD`, `0x415874`, `0x415A86`, `0x415B4B`, `0x415D91`, `0x41673A`; food returns: `0x41494E`, `0x415213`. Exhaustive producer coverage is not yet proved. | **Pending** |
| VV5 New Believers | `0x4237B0` / payload `tech_increment` | `0x41EB6F` before stock statistics hook | The food hook is before the separate statistics hook, but the exact collection adjustment and all positive-tech composition sites still need an independent call-site record. | Event methods in `0x414A30..0x416CD0` call or tail-jump to the central writers. The current return-address blacklist is explicitly incomplete for tail-jumps; exact exclusion remains unresolved. | **STOP** |

## Required follow-up before GO

For each row, the evidence record must include the exact stock executable
SHA-256, positive writer callsites, collection adjustment functions and
rounding/field representation, every Island Event producer/caller, final
delta representation, ownership field, and the exact hook point. Static tests
must independently exercise no collection, collection only, doubler only,
collection plus doubler, and Island Event with both ownership states. The
collection-plus-doubler result must equal twice the exact native
collection-adjusted positive delta; toggling either doubler must not change an
Island Event result. Until those checks are recorded, no description should
call the exclusion complete or claim verified runtime behavior.
