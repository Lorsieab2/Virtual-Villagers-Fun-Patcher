# Disabled VV5 UI and individual-confirmation candidate

This candidate is disabled, catalog-hidden, stock-mode-only, and has no package
or player/runtime validation. Its generated evidence is written under
`outputs/vv5-ui-confirmation-candidate/` by
`scripts/build_vv5_ui_confirmation_candidate.py`.

The native UI contract is message `8`, Tech event `13`, Detail event `13`, and
the bound Detail path `sub_44B560 -> 0x7B2600`. The current emitted helper
still hooks `0x44BC20`; the candidate records that mismatch but emits no
unguarded replacement until the exact stock preimage at `0x44B560` is
available. It preserves `ECX=EDI` before the native `0x44FA20` thiscall, the
`0x401BD0` graphic-button factory, `0x40C680` ownership registration, `ret 8`,
and the original handler fallback prologues.

The reference transaction engine covers Youth (50,000), Full Mastery
(100,000), Running (40,000), and Set Age 18 (50,000). Every action performs a
complete dry-run, explicit IDOK/Cancel confirmation, same-index and identity
reacquisition, exact snapshot/eligibility recheck, changed-only mutation,
action-specific postverification, and exactly one charge after postverify.
Invalid selection or skills, no-op, no empty Like, insufficient funds,
cancel, stale recheck, and failed postverify all return without a charge and
include `No tech points have been deducted.`

The engine is save-free and does not replace the independently certified VV5
Full Mastery/trophy/fullscreen artifacts. Runtime/player confirmation remains
required before any enablement or package publication.
