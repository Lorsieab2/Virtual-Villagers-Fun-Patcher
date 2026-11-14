# Where `{@tribe}` reads the tribe's name (G5)

The engine (`native/vvfp_story_upgrades/story_graph.inc` `cg_tribe_name`) reads the name from each game's save
manager, the singleton listed in `native/shared/game_save_slot.h`. It reads at manager + 8 + the name's offset in
the save buffer, bounded by the name field.

| Game | Manager | Read at | Field |
|---|---|---|---|
| VV1 | `[0x48AEDC]` | +0x10 | 33 bytes |
| VV2 | `[0x4997BC]` | +0x10 | 33 bytes |
| VV3 | `[0x4B309C]` | +0x12ED4 | 21 bytes |
| VV4 | `[0x4CB51C]` | +0x170C0 | 21 bytes |
| VV5 | `[0x4DACE0]` | +0x17D1C | 21 bytes |

All five offsets are proven below without the live game.

## 1. The saves hold the name at the buffer offset

I copied the owner's slot saves read-only from `Documents\LDW` to a scratch folder and parsed them with
`src/vv_tribe_rename.py` (the save layout from `native/shared/village_identity.c`). The name sits at buffer
+0x8 / +0x8 / +0x12ECC / +0x170B8 / +0x17D14.

| Game | Name in the save | Bytes |
|---|---|---|
| VV1 | "Kalahuna Tribe 1" | `4b 61 6c 61 68 75 6e 61 20 54 72 69 62 65 20 31 00` |
| VV2 | "Kalahuna Tribe 2" | the same bytes, ending `32 00` |
| VV3 | "Kalahuna Tribe 3: N" and "Kalahuna Tribe 3: M" | slots 1 and 2 |
| VV4 | "Kalahuna Tribe 4" | ending `34 00` |
| VV5 | "Kalahuna Tribe 5" | ending `35 00` (slot 1 and its backup generation 21) |

## 2. The buffer is the manager's own memory from +8

These addresses are from the stock executables.

- **Saving** passes the manager's own memory:
  - VV1 0x41BF58 `lea eax, [esi + 8]; push 0xABDC; mov ecx, esi; push eax; call`
  - VV2 0x424BE8 (the same, length 0x30370)
  - VV3 0x427D61 (the same, length 0x12F1C)
- **Loading** copies the whole file buffer back to the same place:
  - VV1 0x41BEDB `lea edi, [ebx + 8]; mov ecx, 0x2AF7; ...; rep movsd` (0x2AF7 dwords = 0xABDC bytes)
  - VV2 0x424A82 `lea edi, [ebp + 8]; mov ecx, 0xC0DC; ...; rep movsd` (= 0x30370 bytes)
- So VV1 and VV2 read the name at manager + 8 + 8 = **+0x10**.
- In every game the save slot field sits right after the buffer: manager + 8 + the buffer length (`game_save_slot.h`).

## 3. The later three games use the name field at exactly these offsets

The Secret City's +0x12ED4 is the read More Island Events' The Troubling Signs already ships (`troubling_vv3.inc`).
The Tree of Life and New Believers use the same code shape at their own offsets:

| Game | Five copies from the slot list's names into the live name (21-byte stride) | The name text box, capped at 0x14 characters | Reset |
|---|---|---|---|
| VV3 | 0x41B826.. `lea edx, [eax + 0x12ED4]` | 0x41BA14 `push 0x14; lea edi, [esi + 0x12ED4]` | 0x427F7C `mov byte ptr [esi + 0x12ED4], bl` |
| VV4 | 0x418F1F.. `lea edx, [eax + 0x170C0]` | 0x419444 `push 0x14; lea edi, [esi + 0x170C0]` | 0x41F1EC `mov byte ptr [esi + 0x170C0], bl` |
| VV5 | 0x41963F.. `lea edx, [eax + 0x17D1C]` | 0x419B94 `push 0x14; lea edi, [esi + 0x17D1C]` | |

VV4's reset, at 0x41F1EC, sits in the routine whose slot reads are 0x41F16F and 0x41F18A (`[esi + 0x17114]`). That
is the field `game_save_slot.h` names on the manager, so the name and the slot are on the same object.

## Still to see live

The offsets need nothing further. One live look in each game, with a named tribe on screen and a `{@tribe}` event,
would still confirm the words as drawn.
