# VV1 School Lessons Grant Skill research

Supported executable: `Virtual Villagers - A New Home.exe`

- Size: `581,632` bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

VV1 villager records have stride `0x3D8`. The multilingual action table maps `0xC5` to **Going to school**. Routine `0x444B40` assigns that action, then checks the stock school-unlocked flag at global-state offset `+0xA058`; when the flag is clear, the routine replaces the action with its stock alternative. The school-only branch begins at `0x444BF2`.

The five contiguous skill fields are `+0x3C4`, `+0x3C8`, `+0x3CC`, `+0x3D0`, and `+0x3D4`. The patch detours six complete instructions bytes at file offset `0x44BF2` into unused mapped padding at `0x565E0`. It saves registers, calls stock RNG `0x402F10` with bound 100, reduces its `0..99` result modulo five, increments the selected field by one only below 100, restores registers and all three displaced pushes, then resumes at `0x444BF8`.

This rewards each invocation of the unlocked stock Going to school branch once. It does not change the unlock flag, callers, attendance selection, coordinates, or action queue.

| File offset | Stock bytes | Patched bytes |
|---|---|---|
| `0x44BF2` | `6A646A006A00` | `E9E919010090` |
| `0x565E0` | 45 zero bytes | `606A64E828C9FAFF83C40499B905000000F7F98D8493B00000008338647D02FF00616A646A006A00E9EBE5FEFF` |
