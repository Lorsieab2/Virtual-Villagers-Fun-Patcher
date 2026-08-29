# VV1 mask pickup/held static audit

This is a static callsite audit only. It does not certify player-visible
pickup/held behavior.

The VV1 mask patch has three native draw chokepoints:

* `0x409410` is the seven-argument scaled draw. Its mask hook is gated to
  callers in `0x437790..0x4392D0`, the two village render loops. The two loop
  entry stashes (`0x437798` and `0x438900`) provide the record index used by
  that hook.
* `0x4093E0` is the adult five-argument draw thunk and `0x4093C0` is the
  child/swim five-argument draw thunk. Their hooks use the same village caller
  range and head-atlas checks.
* Calls from the unrelated clusters `0x40C4EF..0x40C65B`, `0x41ABA0`, and
  `0x433B5B..0x434016` are outside that range and therefore pass through
  unchanged. The static scan did not prove any of those clusters to be a
  villager pickup/held renderer.

Save-slot persistence is likewise statically bound to the stock save-builder
entry at `0x402ED0`. Its original first two instructions are
`mov eax,[esp+4]; mov edx,[ecx]`; the guarded six-byte splice replays both
loads in the owned `.vv1mc` cave, captures only validated slots 1 through 5
in `.vv1md`, and resumes at `0x402ED6`. This proves the argument and detour
preimage, not that a player save/reload cycle succeeds.

The evidence therefore supports the existing village-loop all-pose coverage,
including the native child/swim branches that converge inside the gated
range. It does **not** prove that a picked-up/held villager is rendered by one
of those callers. No pickup-specific hook was added because there is no exact
native callsite evidence authorizing one.

Player acceptance remains required for: pick up an adult and child, carry them
through each facing/action state, release them, reopen Details, save/reload,
and switch save slots. A failure in the held state must be reported separately
from the confirmed static village-loop coverage.
