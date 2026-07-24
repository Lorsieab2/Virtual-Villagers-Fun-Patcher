# VV1 School Lessons Grant Skill research

Supported executable: `Virtual Villagers - A New Home.exe`

- Size: `581,632` bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

VV1 villager records have stride `0x3D8`. The multilingual action table maps
`0xC4` to **Going to school**. The drum lesson routine is `0x444AA0`. It queues
a movement with parameter 300, followed by a wait with parameter 5 and a
random duration from 12 through 17. This signature was matched against a live
drum click for every attending child.

The five contiguous skill fields are `+0x3BC`, `+0x3C0`, `+0x3C4`, `+0x3C8`, and `+0x3CC`. This was rechecked against the stock skill-total routine at `0x43B5A0`. An earlier patch revision incorrectly began at `+0x3C4`; that revision could reach only three real skill fields and is retired.

## VV3 parity target

VV3's Leadership-level-2 Tribal Chief education route assigns action 55 to the children. The action-55 constructor places callback 42 at the end. Callback case 42 chooses one of five skills with equal odds and adds `RNG(3)+7`, or 7 through 9 points, through the stock capped skill helper.

## Completion-only patch behavior

Live queue tracing found that releases through v1.29.0 patched routine
`0x444B40`, whose branches include **Drinking well water**, rather than the
drum lesson routine. That error could leave callback 127 behind in a child
record and award skill during a later activity, while the real school action
received no callback. A second static candidate at the other branch of that
same routine was rejected when live tracing showed that drum-created queues
still lacked callback 127.

The actual drum lesson calls the queue finalizer at `0x444B28`, immediately
after constructing its stock movement and wait entries. The corrected patch
detours that finalizer call to cave `0x4566A0`, appends opcode 14 with callback
ID 127, executes the displaced stock finalizer, and resumes at the stock
epilogue. Routine `0x444B40` remains byte-for-byte stock.

VV1's action runner at `0x448600` sends opcode 14 to the callback dispatcher at
`0x43A230`. The dispatcher is detoured only for callback 127; every stock
callback follows the displaced prologue and original switch.

The queue constructor reserves `0x18` bytes of local stack before reading its
arguments. It ignores the first argument after using it to choose the villager
record, stores arguments two through five in the queue entry, forces entry
offset `+0x10` to zero, and stores the seventh argument at entry offset
`+0x14`. Opcode 14 consumes that final field as its callback ID.

Callback 127:

1. uses stock RNG `0x402F10` with bound 5 to select one of the five contiguous skill fields;
2. uses the same RNG with bound 3 and adds 7, producing 7, 8, or 9 points;
3. caps the selected field at 100;
4. returns to the action runner.

Because the callback is queued at the end instead of executing in the action constructor, an interrupted Going to school action that never reaches callback 127 earns nothing.

This patch does not change the school unlock flag, callers, attendance selection, coordinates, or the stock final queue entry.

## Verification boundary

Static verification confirms the sole caller at `0x425505`, the complete
movement-and-wait signature through `0x444B28`, the callback constructor
arguments, the callback-dispatch arguments, and the five 4-byte skill fields.
The player's Yepa counterexample showed that the prior candidate was not
reliable. The corrected `0x444AA0` drum-route build still requires a completed
player lesson with before-and-after raw skill values for final live
confirmation.
