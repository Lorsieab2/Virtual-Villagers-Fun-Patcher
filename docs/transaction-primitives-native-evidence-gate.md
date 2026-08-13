# VV3-VV5 permanent-action transaction primitive evidence gate

This additive gate is disabled. It does not emit native code, alter C337 action
files, expose catalog choices, or treat an adjacent writer as proof of a
different operation.

The bound action-family vocabulary is permanent Tech, Youth, Full Mastery,
Running, Age 18, and Full Heal. Every family remains STOP until each required
primitive has an exact function VA, file offset, guarded bytes, calling
convention, input/output registers, stack cleanup, xrefs, complete-folder
provenance, and runtime/player receipts.

Required primitives are:

- selected physical index, current world/save manager, resolved record pointer,
  and stable identity through final reacquisition;
- active/living/status/faction eligibility in proved order—VV5 must check
  faction `+0x1CEC` first, and `+0x1CE1` is forbidden;
- native account getter, exact deduction setter, balance readback, and
  notification;
- native age setter plus both companion/timer fields, catch-up, and Oldest
  Villager side effects;
- native Like/Dislike setter plus readback, action-queue refresh, and
  notification;
- exact native confirmation result ABI where applicable; and
- postverification plus the exact partial-effect/process-fault boundary.

Direct field stores do not qualify. A nearby skill writer does not qualify as
an age, preference, funds, or identity primitive. Static addresses from another
action family cannot be promoted without the complete per-game evidence row.

## Current gap matrix

| Primitive | VV3 | VV4 | VV5 |
| --- | --- | --- | --- |
| Selection/identity | STOP/null | STOP/null | STOP/null |
| Eligibility ordering | STOP/null | STOP/null | STOP/null; faction +1CEC first required |
| Funds transaction | STOP/null | STOP/null | STOP/null |
| Age mutation/catch-up/Oldest | STOP/null | STOP/null | STOP/null |
| Like/Dislike mutation/queue | STOP/null | STOP/null | STOP/null |
| Confirmation ABI | STOP/null | STOP/null | STOP/null |
| Postverify/partial-effect boundary | STOP/null | STOP/null | STOP/null |

The contract, schema, and validator are
`data/transaction_primitives_native_evidence.json`,
`data/transaction_primitives_native_evidence.schema.json`, and
`src/transaction_primitives_native_evidence.py`.
