# Disabled VV5 UI and individual-confirmation candidate

This candidate is disabled, catalog-hidden, stock-mode-only, and has no package
or player/runtime validation. Its generated evidence is written under
`outputs/vv5-ui-confirmation-candidate/` by
`scripts/build_vv5_ui_confirmation_candidate.py`.

The disabled gate is exact: `enabled=false`, `catalog_hidden=true`,
`catalog_enabled=false`, `expanded_fail_closed=true`, runtime status remains
`pending; no package or player validation`, and both the emitted-hook list and
native patch list are empty. The manifest schema rejects unknown keys,
boolean or numeric coercion, changed call conventions, unbound active-base or
padded payload hashes, and any range with invalid bounds, address space, or
declared alignment. The stock fingerprint remains absent from this checkout,
so no enablement path can pass. The Full Mastery and Running map files are
also hash-checked as repository-owned composition inputs, including their
parent metadata and owned ranges.

The native UI contract independently guards message `8`, resource `0x6A`,
dimensions `96x39`, local `(137,2)`, event `13`, factory `0x401BD0`, and
ownership `0x40C680` for both Tech and Detail. The bound Detail path is
`sub_44B560 -> 0x7B2600`. The current emitted helper still hooks `0x44BC20`;
the candidate records that mismatch but emits no replacement until exact stock
preimage and continuation bytes at `0x44B560` have verified instruction
boundaries, ABI, ownership, and child-destructor evidence. The existing
`0x44BC20` preimage/continuation cannot be reused. The candidate preserves
`ECX=EDI` before the native `0x44FA20` thiscall, the graphic-button factory,
ownership registration, `ret 8`, and the original handler fallback prologues.
Any future enablement must also prove the proposed VA/raw range relationship;
the disabled manifest records that relationship as unverified and cannot
accept an arbitrary raw offset.

The reference transaction engine covers Youth (50,000), Full Mastery
(100,000), Running (40,000), and Set Age 18 (50,000). Every action performs a
complete dry-run, explicit IDOK/Cancel confirmation, same-index and exact
record-pointer reacquisition, exact pre-confirmation snapshot recheck,
post-confirmation funds reacquisition/equality, changed-only reference
mutation, action-specific reference postverification, and exactly one verified
reference charge outcome after postverify. Invalid selection or skills, no-op,
no empty Like, insufficient funds, cancel, stale pointer/snapshot, changed
funds, failed postverify, and failed charge verification all return without a
charge and include `No tech points have been deducted.` Running cleanup of
Running Dislikes is charged when the binding proves an existing Running Like
still has changed Dislike fields; an already-clean record remains a no-op.

The engine requires both `before_reacquire` and `before_funds_reacquire`
callbacks for every transaction invocation. It rejects missing callbacks,
non-callables, wrong callback return types, float/bool funds or confirmation
values, float/bool skill/index fields, and missing record identity. It accepts
no implicit fallback to the pre-confirmation object or funds value.
The reference charge check is exact arithmetic only; it does not perform or
claim a native deduction. Confirmation accepts only IDOK `1` or the explicit
Cancel/close results `0` and `2`.

The reference engine explicitly performs no native write, native readback, or
rollback. Its returned state and funds arithmetic are a contract test oracle,
not native runtime evidence. Exact selected-index resolver, record offsets,
writer ABIs, stock SHA-256, parent hashes, and owned append/hook ranges are
independently bound in the generated evidence manifest. Full Heal has no
candidate bytes or owned range.

The engine is save-free and does not replace the independently certified VV5
Full Mastery/trophy/fullscreen artifacts. Runtime/player confirmation remains
required before any enablement or package publication.
