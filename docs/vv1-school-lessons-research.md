# VV1 School Lessons Grant Skill research

Supported executable: `Virtual Villagers - A New Home.exe`

- Size: `581,632` bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

VV1 villager records have stride `0x3D8`. The multilingual action table maps `0xC5` to **Going to school**. Routine `0x444B40` assigns that action, then checks the stock school-unlocked flag at global-state offset `+0xA058`; when the flag is clear, the routine replaces the action with its stock alternative. The school-only branch begins at `0x444BF2`.

The five contiguous skill fields are `+0x3C4`, `+0x3C8`, `+0x3CC`, `+0x3D0`, and `+0x3D4`.

## VV3 parity target

VV3's Leadership-level-2 Tribal Chief education route assigns action 55 to the children. The action-55 constructor places callback 42 at the end. Callback case 42 chooses one of five skills with equal odds and adds `RNG(3)+7`, or 7 through 9 points, through the stock capped skill helper.

## Completion-only patch behavior

The original final queue entry at `0x444C50` is converted to opcode 17, callback ID 127. A detour at `0x444C64` appends the displaced stock final queue entry after that callback and then calls the original queue finalizer. The callback dispatcher at `0x43A230` is detoured only for callback 127; every stock callback follows the displaced prologue and original switch.

Callback 127:

1. uses stock RNG `0x402F10` with bound 5 to select one of the five contiguous skill fields;
2. uses the same RNG with bound 3 and adds 7, producing 7, 8, or 9 points;
3. caps the selected field at 100;
4. returns to the action runner.

Because the callback is queued at the end instead of executing in the action constructor, an interrupted Going to school action that never reaches callback 127 earns nothing.

This patch does not change the school unlock flag, callers, attendance selection, coordinates, or the stock final queue entry.
