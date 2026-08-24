# VV1 read-only doubler reverse-engineering audit

This report is read-only evidence for the exact stock image supplied by the
project. No tracked project file was changed.

## Input and tools

- Input: `inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe`
- Size: 581,632 bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`
- Analyzer: IDA Pro 9.4 / Hex-Rays 9.4.0.260610
- Complete Hex-Rays output and xref records: `vv1-audit.json`

The JSON contains the full decompilation for every direct writer caller and
for the event/action parents used for provenance checking.

## Native writer boundary

Tech writer `sub_41D120` at VA `0x41D120` has stock bytes:

```text
8B4424040181FCA20000010181209E0000C20400
```

Hex-Rays decompiles it as:

```c
int __thiscall sub_41D120(_DWORD *this, int delta) {
    *(this + 10431) += delta;
    *(this + 10120) += delta;
    return delta;
}
```

Food writer `sub_41D140` at VA `0x41D140` has stock bytes:

```text
8B4424040181ECA20000010181289E0000C20400
```

Hex-Rays decompiles it as:

```c
int __thiscall sub_41D140(_DWORD *this, int delta) {
    *(this + 10427) += delta;
    *(this + 10122) += delta;
    return delta;
}
```

The stock writers contain no separate call to a statistics or event handler;
their visible native behavior is the two storage/statistic DWORD additions and
`ret 4`. A source-bound fix should still modify the delta before entering these
native writers, rather than duplicating their stores in a replacement hook.

## All direct tech writer xrefs

| Call VA | Return VA | Direct caller | Static route |
|---|---|---|---|
| `0x41A373` | `0x41A378` | `sub_419380` | shared Island Event result site; cases 7 and 15 converge here |
| `0x42818F` | `0x428194` | `sub_427CA0` | Island Event: Good Little Monkey, `900 * a3` tech |
| `0x42BB13` | `0x42BB18` | `sub_42B740` | Island Event crate/tool reward, +3000 |
| `0x42BBF2` | `0x42BBF7` | `sub_42B740` | Island Event crate/tool reward, +2000 |
| `0x42BCD1` | `0x42BCD6` | `sub_42B740` | Island Event crate/tool reward, +1000 |
| `0x42BE4B` | `0x42BE50` | `sub_42B740` | Island Event crate/tool reward, +1500 |
| `0x42BFAB` | `0x42BFB0` | `sub_42B740` | Island Event crate/tool reward, +1000 |
| `0x42C10B` | `0x42C110` | `sub_42B740` | Island Event crate/tool reward, +500 |
| `0x43B313` | `0x43B318` | `sub_43A230` | ordinary research path, `v55 / 7` |
| `0x43B32E` | `0x43B333` | `sub_43A230` | ordinary research path, `v55 / 5` |
| `0x43B34B` | `0x43B350` | `sub_43A230` | ordinary research path, `v55 / 3` |

The three `sub_43A230` tech calls are the same ordinary research case with
different native research-speed divisors. The six `sub_42B740` calls are in an
event handler reached from `sub_42D050`; its strings include crate/tool reward
text and “tech points.”

There is an additional provenance join that the direct-xref list alone misses:

```text
0x419C3A: jmp 0x41A36D
0x41A373: call sub_41D120
```

`sub_419380` case 7 (“Let the child try research”) tail-jumps into the same
call site used by case 15 (“Let the researchers have it”). Both are Island
Event outcomes, so a return-address-only guard at `0x41A378` cannot make either
one eligible.

No direct VV1 tech writer route for Duplicate Collectibles was found in the
exact image. The Golden Child strings map to IDs 57/58/59 and the traced
Golden Child writer path is food-only; no Golden Child tech writer call was
found.

## All direct food writer xrefs

| Call VA | Return VA | Direct caller | Static route |
|---|---|---|---|
| `0x419454` | `0x419459` | `sub_419380` | Island Event whale outcome, +1000 food |
| `0x419F0F` | `0x419F14` | `sub_419380` | event-created mushroom source, `random(200) + 300` food |
| `0x4281D5` | `0x4281DA` | `sub_427CA0` | Island Event: Greedy Little Monkey, `200 * a3` food |
| `0x42B865` | `0x42B86A` | `sub_42B740` | Island Event crate food, +1500 |
| `0x42B933` | `0x42B938` | `sub_42B740` | Island Event crate food, +1000 |
| `0x42BA01` | `0x42BA06` | `sub_42B740` | Island Event crate food, +500 |
| `0x43AD8C` | `0x43AD91` | `sub_43A230` | ordinary action/resource case 14; `max(2, field/130)` and source-field decrement |
| `0x43AECD` | `0x43AED2` | `sub_43A230` | ordinary action/resource case 15; +7 and source-field decrement |
| `0x43AF3C` | `0x43AF41` | `sub_43A230` | ordinary action/resource case 16; +9 |
| `0x43AF8E` | `0x43AF93` | `sub_43A230` | ordinary action/resource case 17; +55 |
| `0x43AFF7` | `0x43AFFC` | `sub_43A230` | mixed case 32; +8; case 33 tail-joins this same site with +45 |
| `0x43B09B` | `0x43B0A0` | `sub_43A230` | Golden Child case 39, +150 food |

The case-33 join is:

```text
0x43B04C: push 0x2D
0x43B04E: jmp 0x43AFF1
0x43AFF7: call sub_41D140
```

The Golden Child mapping is byte-backed by the string table at `0x487208`:
ID 59 points to VA `0x47E2D0`, “The Golden Child magically created food!”.
Cases 37 and 38 directly modify resource fields and call message IDs 57/58;
case 39 reaches the food writer at return `0x43B0A0` and then queues message
ID 59. This is not a food-source collection delta.

## Current patch finding

The current VV1 generator redirects the central writers:

```text
0x41D120: E9 3B 9B 03 00  -> 0x456C60
0x41D140: E9 6B 9B 03 00  -> 0x456CB0
```

The generated wrappers inspect the caller return address at `[ESP+4]`, double
any positive delta when the corresponding ownership flag is set, skip only
`0x428194` for tech and `0x4281DA` for food, then reproduce the native two
additions and return.

That is not a safe source boundary:

1. Tech return `0x41A378` is shared by two Island Event outcomes through the
   `0x419C3A` tail jump, but the wrapper does not exclude it.
2. All six `sub_42B740` tech rewards are Island Event outcomes, but none are
   excluded.
3. The current food wrapper doubles the Golden Child food result at
   `0x43B0A0`.
4. The current food wrapper also doubles whale, monkey, and crate event rewards;
   those are not established as ordinary food-source collection writes.
5. The current wrapper reproduces the visible stock writer stores instead of
   changing the source delta and then entering the native writer.

Therefore the existing VV1 doubler implementation is correctly marked **STOP**
for the requested “no more, no less” contract.

## Concrete safe-fix boundary

The minimum source-bound tech candidate proven by this audit is the three
ordinary research call sites returning `0x43B318`, `0x43B333`, and `0x43B350`.
All event call sites, including the shared `0x41A378` site, should remain
native until separately proven otherwise.

For food, cases 14–17 at returns `0x43AD91`, `0x43AED2`, `0x43AF41`, and
`0x43AF93` are the only ordinary action/resource sites with source-field
evidence in this audit. The mixed case-32/33 site at `0x43AFFC` should remain
native until its action provenance is independently resolved. Event rewards and
the Golden Child site at `0x43B0A0` should remain native.

The safe implementation shape is a per-call-site helper that doubles the
already-computed positive delta, pushes that site’s exact continuation, and
tail-enters `sub_41D120` or `sub_41D140`. This preserves the native writer’s
storage/statistic updates. Unknown or mixed callsites must stay native/fail
closed. A final GO still requires emitted-byte tests for every listed source and
every exclusion, plus runtime/player confirmation separately from this static
report.

## Read-only test note

`py -3 -m unittest tests.test_doubler_audit` ran 14 tests and failed one
pre-existing deterministic transparency-document comparison because the
checked-in generated document does not match the current generator output.
This audit did not alter that tracked documentation mismatch.
