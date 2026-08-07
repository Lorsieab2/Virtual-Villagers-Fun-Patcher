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
logical sickness-state read supplied by the reference callback. Nonzero-faction
records are excluded before health or sickness, dead/non-positive records are
never revived, and the unproved `+0x1CE1` field is not part of this schema or
read order. No native VV5 sickness offset or sickness ABI is claimed.

Health `1..99` is partial health and targets exactly `100`. Health `100` is
unchanged unless sickness is present. A sick partial-health record contributes
once to both counters: `X sick villagers were cured` and `Y partial-health
villagers were restored to exactly 100`.

## Transaction boundary

The complete 150-record dry run occurs before confirmation. Confirmation
accepts exact `IDOK=1`; exact Cancel/close results are `0` and `2`. After OK,
the model requires an independently supplied snapshot binding the selected
index, resolved selected pointer, all 150 ordered records and their relevant
state, funds, People Cured, and predicted counts. The complete before snapshot
must exactly equal the pre-confirmation state before any mutation callback.

Health setting, sickness clearing, People Cured updating, and deduction are
represented only by strict `success`/`failure`/`unknown` callback contracts.
No VV5 native setter, readback, rollback, or deduction ABI is implemented or
claimed. Callback return values alone prove neither success nor failure. The
complete predicted and actual 150-record snapshots and People Cured readback
must match. Exactly one deduction callback is permitted, and only after complete
postverification. Only an exact after-balance equal to the before-balance minus
30,000 proves a charge; every missing or mismatched readback is charge-unknown.

Callback exceptions, failure, or unknown outcomes disclose that effects may
have occurred. The model does not claim rollback; after callbacks, rollback
status is unknown. It never claims no charge after a deduction attempt without
an exact unchanged balance readback.

Repository-owned source contracts use one checkout-independent hash rule:
decode strict UTF-8, normalize CRLF and lone CR to LF, then report uppercase
SHA-256. Binary manifests and payloads retain their existing raw-byte hashes.

Reference message-template wording is singular/plural-safe and retains the exact
terms:

`Full Heal / Cure All completed: X sick villagers were cured; Y partial-health villagers were restored to exactly 100.`

Runtime/player confirmation remains required before any enablement or
packaging consideration.
