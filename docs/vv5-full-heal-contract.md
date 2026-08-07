# Disabled VV5 Full Heal / Cure All reference contract

This is a disabled, catalog-hidden, stock-mode-only reference contract. It
has no native output, no catalog choice, no package, no player/runtime
validation, and no save access. The generated evidence is written only under
`outputs/vv5-full-heal-contract/` by
`scripts/build_vv5_full_heal_contract.py`.

The exact disabled gate is `enabled=false`, `catalog_hidden=true`,
`catalog_enabled=false`, `expanded_fail_closed=true`, and runtime status
`pending; no package or player validation`. Native patches, emitted hooks,
candidate caves, and candidate hooks are all empty. The contract composes
with the existing disabled VV5 UI candidate, Full Mastery map, Running map,
and their parent hashes without claiming a Full Heal-owned byte range. The UI
candidate remains the separate exact-four-action model; this aggregate model
does not extend its `VV5Villager` type.

## Exact record gate

The reference scan walks physical indices `0..149` at stride `0x2F44`.
For each present record it reads active `+0x1CD4`, then current faction
`+0x1CEC`. Only an active record with current faction `0` proceeds to the
positive-health read at `+0x1C40`; only positive health proceeds to the
logical sickness-state read supplied by the reference callback. No current
Heathen is inspected for health or sickness, dead/non-positive records are
never revived, and the unproved `+0x1CE1` field is not part of this schema or
read order. No native VV5 sickness offset or sickness ABI is claimed.

Health `1..99` is partial health and targets exactly `100`. Health `100` is
unchanged unless sickness is present. A sick partial-health record contributes
once to both counters: `X sick villagers were cured` and `Y partial-health
villagers were restored to exactly 100`.

## Transaction boundary

The complete 150-record dry run occurs before confirmation. Confirmation
accepts exact `IDOK=1`; exact Cancel/close results are `0` and `2`. After OK,
the model requires a fresh all-record snapshot with identical physical index,
identity, pointer, eligibility fields, health/sickness values, and predicted
counts. It then requires a fresh funds value equal to the pre-confirmation
amount and at least 30,000 tech points before any mutation callback.

Health setting, sickness clearing, People Cured updating, and deduction are
represented only by strict `success`/`failure`/`unknown` callback contracts.
No VV5 native setter, readback, rollback, or deduction ABI is implemented or
claimed. Each callback result is postverified through the reference resolver;
the final sick and partial counts must be zero and equal the confirmed counts.
Exactly one deduction callback is permitted, and only after complete
postverification. Final reference funds must equal the original amount minus
30,000 before a verified charge is reported.

Callback failure or unknown outcomes disclose partial effects honestly. The
model does not claim rollback; after callback effects, rollback status is
unknown. A failed or unknown deduction never claims a verified charge. All
no-charge exits include `No tech points have been deducted.` where no
deduction was verified.

Player-facing success wording is singular/plural-safe and retains the exact
terms:

`Full Heal / Cure All completed: X sick villagers were cured; Y partial-health villagers were restored to exactly 100.`

Runtime/player confirmation remains required before any enablement or
packaging consideration.
