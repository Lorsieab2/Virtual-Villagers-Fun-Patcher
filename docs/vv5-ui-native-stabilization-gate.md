# VV5 UI/native stabilization gate

`data/vv5_ui_native_stabilization_gate.json` is an additive, disabled evidence
gate. It does not add a catalog entry, emit a patch, launch the game, read or
write saves, or claim runtime/player success.

The gate preserves exactly four individual actions: `youth`, `full_mastery`,
`running`, and `age_18`. Full Heal, Tech, and Detail native output remains
disabled, catalog-hidden, publication-false, and represented by empty native
hooks, caves, patches, and ranges.

## Bound evidence

The Detail input method at `0x44B560` is pinned as a method entry and is
explicitly rejected as an event-13 route. D339 mechanical evidence is recorded
for the separate event method `[0x44BC20,0x44BD4C)`, the registered ID-13
control/ownership chain, the exact offline `0x4BC20` preimage/detour and
continuation, and the required fallback/teardown facts. This is offline
mechanical evidence only; hot uninstall, runtime, and player receipts remain
STOP.

The C260 window-flags defect is preserved as rejected evidence: the candidate
uses `0x7B2A64`, while the authenticated string begins at `0x7B2A63` and the
requested symbol is `DL_GetWindowFlags`. No one-byte repair is emitted.

The resource binding is `Images\\btn_trophies.png`, resource `0x6A`, dimensions
`96x39`, local `(137,2)`, event 13, factory `0x401BD0`, and ownership
`0x40C680`. Caption text is intentionally null and unverified until an
authenticated caption receipt exists.

## Transaction and fullscreen requirements

Every individual action requires dry-run, exact `IDOK=1` confirmation, both
mandatory reacquire callbacks, exact selected-index/world/record-pointer/
account identity, full snapshot equality, exact funds-before/after readback,
postverification, and at most one deduction after final postverification.
Unknown charge and partial-effect outcomes must be disclosed; no no-charge
claim is valid without exact balance readback. The current Python model remains
reference arithmetic only: it has no native write, native readback, native
rollback, or later-stage account-identity token.

The Running adapter shape is mandatory before any native binding: the selection
callback returns `(world, record, selected_index, resolved_pointer)`, the
account/balance callback returns `(world, account, balance)`, and deduction
receives `(world, account, amount)`. `world_identity` is an exact positive,
non-bool value under the gate's strict reference validator. World, selection,
record, pointer, account, balance, or callback-exception mismatch fails closed
at first write, Like/full postverify, pre-deduction, balance readback, and every
rollback restore.

The fullscreen owner contract requires capture before leave, same-process
revalidation, no foreground fallback, and one centralized terminal cleanup
epilogue. Owner output and all four Tech/Detail windowed/fullscreen receipts
remain absent.

Validate the gate with:

```text
python scripts/validate_vv5_ui_native_stabilization_gate.py
python -m unittest tests.test_vv5_ui_native_stabilization_gate
```
