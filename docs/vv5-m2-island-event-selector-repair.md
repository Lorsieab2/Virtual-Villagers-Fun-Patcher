# VV5 M2 Island Event selector repair contract

Status: **HARD WITHDRAWN; repair contract only**. This document does not enable,
package, launch, or modify a game build.

## Exact failure

Supported stock build: `Virtual Villagers - New Believers.exe`, SHA-256
`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.

The M2 build used the same selector hook in both stock/immediate and expanded
layouts. At file/RVA `0x1890F` (VA `0x41890F`) the stock instruction stream is:

```text
0x41890F  8B 74 84 14       mov esi,[esp+eax*4+14]   ; 4 bytes
0x418913  6A 64             push 100                  ; 2 bytes
0x418915  E8 46 AD FE FF    call 0x403660             ; 5 bytes
0x41891A  83 C4 08          add esp,8                 ; valid continuation
```

The broken M2 replacement is `E9 6C 98 39 00 90 90`. It consumes only seven
bytes, through the call opcode, and leaves the call displacement at
`0x418916..0x418919`. Its `.shr` routine unconditionally jumps to `0x418916`.
Consequently WER EIPs `0x418917` and `0x418918` are mid-instruction bytes, not
valid entry points. The original call also used cdecl cleanup by the caller;
removing it without preserving the two-push stack contract is independently
unsafe.

The native due-event route is `sub_442350 -> sub_4187F0 -> sub_418870`.
`sub_418870` selects an event, opens it through the native construction/dialog
path, and records its seen flag. The repair must leave all code after
`0x41891A` native, including event open, callbacks, close, and return paths.

## Deterministic replacement body

The body below replays the overwritten instructions, preserves the original
random call, and forces event index 30 only when marker mask `0x4` is set. It
returns to the first valid instruction after the overwritten call. No path
targets `0x418916`, `0x418917`, or `0x418918`.

```asm
; entry VA is payload VA + 0x180
mov esi, dword ptr [esp + eax*4 + 0x14]
test dword ptr [0x51D388], 4
jz native_random
and dword ptr [0x51D388], 0xFFFFFFFB
mov esi, 30
native_random:
push 100
call 0x403660
jmp 0x41891A
```

The assembled body is 40 bytes. At stock/immediate payload VA `0x7B2000`
(file offset `0xDB000`), selector offset `+0x180` (file `0xDB180`, VA
`0x7B2180`) it is:

```text
8B748414F70588D3510004000000740C832588D35100FBBE1E000000
6A64E8BD14C5FFE97267C6FF
```

The exact seven-byte hook replacement is:

```text
E9 6C 98 39 00 90 90
```

For both expanded-256 layouts, the payload remains at file offset `0xDB000`
but is relocated to VA `0x8EB000`; selector VA is `0x8EB180`. The expanded
body and hook are:

```text
8B748414F70588D3510004000000740C832588D35100FBBE1E000000
6A64E8BD84B1FFE972D7B2FF

E9 6C 28 4D 00 90 90
```

Only the two rel32 fields differ between layouts: the hook-to-body jump and the
call/jump inside the relocated body. The absolute marker address and native
callee stay at `0x51D388` and `0x403660`.

The selector slot is 40 bytes. For a fresh stock/immediate page its complete
preimage must be 40 zero bytes. For repair of the withdrawn M2 stock/immediate
build, the exact 36-byte broken preimage is:

```text
8BB4846C090000F70588D3510004000000740C832588D35100FBBE1E000000E97267C6FF
```

followed by four unchanged bytes. In an expanded M2 page the corresponding
broken preimage ends with `E9 72 D7 B2 FF` instead of `E9 72 67 C6 FF`.
Any other slot bytes are foreign and must fail closed.

The enclosing M2 `.shr` section is the existing raw range `0xDB000..0xDBFFF`
(RVA `0x3B2000`, VA `0x7B2000`) with patched executable characteristics
`0xF0000040`; stock is `0xD0000040`. Expanded layouts keep the same raw range
and relocate the section VA to `0x8EB000` (RVA `0x4EB000`). The selector repair
does not add a section, change section count, alter `SizeOfImage`, change the
checksum policy, or touch the existing `.vv5fm` page. Those enclosing header
and append guards remain mandatory and must match the selected M2 manifest.

## ABI and preservation contract

- Entry state is exactly the state at stock `0x41890F`: EAX is the result of
  the first `sub_403660` call and ESP still includes the earlier `push edi`.
- ESI receives the selected event index. Marker set changes only ESI to 30 and
  clears mask `0x4`; marker clear leaves the native selected index unchanged.
- The second `sub_403660(100)` call is still made. Its cdecl return and
  caller-cleanup behavior remain native.
- The trampoline pushes exactly the original second argument and performs no
  additional register saves. The native `add esp,8` at `0x41891A` therefore
  cleans both the earlier `push edi` and trampoline `push 100` exactly as in
  stock.
- EAX/ECX/EDX/flags remain subject only to the same native call and the valid
  continuation. ESI is the intentional event-index output; EBX/EBP/EDI and
  stack ownership remain under the surrounding native function.
- No event dialog, callback, seen-bit, save, skill, faction, or Full Mastery
  field is written by this body except the existing one-shot marker clear.

## Guards and ownership

Apply atomically only when all of the following match:

1. Exact executable fingerprint above.
2. Hook bytes are the known broken M2 bytes (`E9 6C9839009090`) or the exact
   stock guard (`8B7484146A64E8`) for a fresh generation.
3. The owned selector payload range is the known broken body or zero-filled
   stock range; reject every other byte sequence.
4. The `.shr` section and any existing `.vv5fm` section headers match the
   selected stock/immediate or expanded layout manifest.

The selector bytes are owned by the VV5 Origins base feature. They must not be
removed independently while any dependent Origins page is installed. Removal
requires the repaired hook/body guards, restores the exact stock seven-byte
hook and original `.shr` bytes, then restores the original section flags and
headers according to the enclosing feature's uninstall transaction. A guard
failure is a hard stop; never truncate or overwrite a foreign payload.

No new absolute or indirect references are introduced. The only rel32 targets
are the repaired body, `0x403660`, and valid continuation `0x41891A`.

## Required static vectors

The candidate remains disabled until all vectors pass for stock/immediate,
expanded-256, and expanded-256-progression:

- empty event list: selector hook is not reached;
- marker clear: native event index and random call match stock;
- marker set: mask `0x4` clears once, event index becomes 30, random call still
  executes, and native event construction/dialog/seen/return paths are reached;
- repeated scheduling after marker clear does not force event 30;
- stack sentinel before selector equals sentinel after `add esp,8`;
- no EIP or branch target equals `0x418916`, `0x418917`, or `0x418918`;
- all other marker bits (doubler ownership masks `1` and `2`) are unchanged;
- malformed hook/body/header guards refuse application;
- uninstall restores the exact stock hook, payload bytes, section flags, file
  length, and `SizeOfImage` for the chosen layout;
- composition with Full Mastery and all unrelated Origins paths leaves their
  bytes and behavior unchanged.

This contract is a static repair specification only. The VV5M2 runtime remains
withdrawn and no save repair or relaunch is authorized.
