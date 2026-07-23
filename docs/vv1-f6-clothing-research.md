# VV1 F6 Clothing Change Cheat Research

## Supported executable

| Size | SHA-256 |
|---:|---|
| 581,632 bytes | `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D` |

## Retained input path

The SDL event translator at virtual address `0x00403970` still recognizes SDL keycode `0x4000003F` as F6 and translates it to the game's internal key event `0x3FF` (1023). The gameplay screen handler begins at `0x0041FDF0`.

Its key-event table covers internal events 1000 through 1026. F7 (1024) and F8 (1025) retain explicit behaviors, but F6 (1023) maps to the ordinary unhandled return. No gameplay F6 branch remains in the supported executable.

## Selected villager and clothing

The gameplay screen's state pointer is at screen offset `+0x10`. The selected villager index is the state field at `+0xAD34`; `-1` means no selection. The villager-record base pointer is at screen offset `+0x20`.

VV1 contains 256 villager records with stride `0x3D8`. The occupied flag is byte `+0x28`. Clothing is the dword at `+0x364`. The stock villager initializer calls `RNG(20)` before writing this field, establishing the ordinary clothing range `0..19`.

## Patch

The patch changes the F6 map byte at file offset `0x20057` from the unhandled branch to a shared handled-key branch, then detours that branch at file offset `0x1FF2E` into unused mapped `.text` padding at file offset `0x56620`.

The detour:

1. Reads the original internal key event from the existing stack frame.
2. For every event except F6, reproduces the displaced instruction and resumes the untouched original behavior.
3. For F6, validates that the selected index is within `0..255`.
4. Resolves the selected record and verifies its occupied flag.
5. Increments clothing by one; a result of 20 or greater wraps to 0.
6. Returns through the original gameplay-key epilogue.

Because the stock renderer reads the clothing field from the villager record, no sprite or asset replacement is required.

## Boundaries

- The patch changes only the selected active villager.
- Pressing F6 with no valid active selection changes nothing.
- The cycle is `0, 1, ... 19, 0`.
- Head, sex, age, skills, health, occupation, position, action queue, and other villager fields are untouched.
- F7, F8, and every non-F6 key retain their original mappings.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
