# Grant Running binding

This is the static, fail-closed binding contract for the selected-villager
Grant Running action (`Buy`, 40,000 tech points) across the five exact PC
builds. It does not launch a game, access saves, emit a binary, or enable a
catalog entry.

| Game | Exact persisted Like/Dislike slots | Binding status |
| --- | ---: | --- |
| VV1 | 4 / 4 | STOP; native preference write/readback and deduction paths unproved |
| VV2 | 62 / 62 | STOP; native preference write path unproved |
| VV3 | 3 / 3 | STOP; native preference-write ABI and safe composition unproved |
| VV4 | 3 / 3 | STOP; native preference-write/readback ABI unproved |
| VV5 | 3 / 3 | STOP; native preference-write ABI unproved |

Every binding scans the complete configured physical arrays. `-1` is an empty
slot, not an early terminator. The transaction rules are:

1. If any Like is already Running, skip the whole record with zero preference
   writes and zero charge, preserving duplicate Likes and every Dislike.
2. Otherwise, preflight the first physical empty Like. If none exists, make no
   writes and no charge; Dislikes remain unchanged.
3. With a destination, write Running once to that Like and clear every Running
   Dislike only after the destination is proven. Unrelated slots and ordering
   remain unchanged.
4. Complete a read-only dry run, confirm with IDOK-only semantics, reacquire
   the same identity and full slot snapshot, postverify the exact result, then
   perform one native deduction.

The reference adapter contract is strict about values and identity. Health is
an exact non-boolean signed-DWORD integer in `0..0x7FFFFFFF` and must be
positive; active is an exact non-boolean `0` or `1`; identity and resolved
record pointer are exact non-boolean unsigned-DWORD values; selected index is
an exact non-boolean integer within the manifest's physical bound. VV5 faction,
heathen-active/current-believer flags are exact non-boolean `0`/`1` values.
Eligibility gates run before either preference array is read. These reference
types and bounds make adapter input failures fail closed; they do not establish
that any native field, selected-index resolver, or record-pointer ABI is proven.

Confirmation accepts only exact integer `IDOK == 1`. Exact `IDCLOSE == 0` and
`IDCANCEL == 2` are explicit no-charge cancellations; booleans, strings,
floats, and other dialog results are invalid. Funds and every balance readback
are exact unsigned-DWORD integers. A charge requires an exact before/after
balance transition of precisely 40,000. `DeductionOutcome` remains only an
adapter assertion: a `charged` outcome without balance readback is reported as
unknown, and the deduction callback is not invoked when the before-balance
readback is unavailable.

The shared model in `src/grant_running.py` exposes adapter callbacks rather than
raw field stores. The adversarial callback tests use only in-memory synthetic
bindings and do not prove a native ABI. Reacquire exceptions or malformed
identity/balance results are structured as an unknown revalidation outcome
without propagating the callback exception. Exceptions after deduction are
classified only by the exact balance transition. Failed postverification is
no-charge; rollback is attempted only while the same identity and
candidate-written values remain provable. If rollback is unavailable, unsafe,
or partial, the result explicitly discloses that retained per-slot effects may
remain; it never claims complete restoration. A binding is not committable
unless eligibility ordering is declared and both complete native ABI gates are
certified.
The manifest `eligibility_gate_order` field is only an ordering declaration; it
does not prove a native selected-index/resolver path, VV4 status predicate, or
VV5 current-believer discriminator. `DeductionOutcome` is likewise an adapter
assertion unless balance readback independently verifies it.
The per-game evidence and STOP gates are stored under
`data/candidates/*_individual_grant_running_binding.json`.
