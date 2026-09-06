# Crash dump findings

Every crash record on the development machine, checked against the binaries
that produced it. Each conclusion below names how it was measured so the next
session can re-verify it rather than trust it.

Tooling: IDA Professional 9.4 headless on the exact binaries, plus a minidump
parser validated against a dump whose contents were already known. Nothing here
rests on disassembly by inspection.

## Why a negative result needs a positive control

Several wrong conclusions in this repository's crash history came from reading
"the scan found nothing" as "the thing is not there". A scan that finds nothing
proves nothing until the same scan has been shown to find something it must
find. Every attribution below therefore carries a control, and the control is
stated alongside the result.

The same discipline applies to byte patterns. A constant appearing in an image
does not mean the image *contains* that value at a usable alignment -- see the
VV4 section, where the raw hit count and the aligned hit count give opposite
answers.

## Virtual Villagers 4 -- The Tree of Life

Two dumps. The September 5 one faults with `EIP = 0x2E000000`, which is in no
loaded module, and `ESP = 0x001AFDC9`, which is **not 4-byte aligned**.

That misalignment is the decisive fact. On x86 every push, pop, call and ret
moves `ESP` by a multiple of four, so a call/return sequence can never produce
an unaligned stack pointer. `ESP` was *assigned* a corrupt value rather than
walked to one, which means the stack around it cannot be read as a frame chain.

An earlier reading identified the innermost frame as `0x00489386`, inside the
Origins Tech handler, together with stack words `8` and `0x0D` matching the
message/event pair the guard tests. Those observations are real, but they are
read off a misaligned stack. On the correct boundary `0x00489386` sits at
`ESP+0x0B` -- *above* the stack pointer -- so it is a leftover word from a call
that had already returned normally, not a live frame.

### The guard cannot be reached from the fault

The faulting instruction was disassembled in IDA rather than inferred:

    0x00401A15  8b 01        mov  eax, [ecx]        ; vtable pointer
    0x00401A17  8b 40 0c     mov  eax, [eax+0Ch]    ; slot +0xC
    0x00401A1A  52           push edx
    0x00401A1B  6a 08        push 8
    0x00401A1D  ff d0        call eax               ; <-- faults

`ff d0` is `call eax` with an operand type of "register", so this is an indirect
call. It can only reach an address that was loaded from memory.

Scanning every segment for the dwords `0x489373`, `0x4895D3` and `0x489386` --
the guard, the handler, and the return address -- yields **zero occurrences**.
The control that makes that zero meaningful: the same scan finds `0x4018A0`
exactly once at `.rdata:0x48A614` and `0x43E9F0` exactly once at
`.rdata:0x48EC70`, which are their real vtable slots. The scanner works, so the
absence is genuine. Our code is in no function-pointer table, and `call eax`
therefore cannot reach it.

### The faulting value is not in the image

`0x2E000000` occurs 238 times in the image, and **none of those occurrences is
dword-aligned**. Every one straddles a boundary inside adjacent string data,
because `0x2E` is the ASCII `.` in literals such as `".png"`, `"..\images\"`,
`"..\sounds\"` and `".?AVl"`. A vtable slot is always 4-byte aligned, so no
vtable in this image can yield that value. Reporting the raw count of 238
without the alignment check would invert this conclusion.

For completeness, slot `+0xC` of the dispatcher vtable at `0x48A614` holds
`0x4AE36C`, which is not a function at all -- consistent with the object in
`ecx` being of a different runtime type than the dispatcher expected.

**Conclusion.** A use-after-free or otherwise corrupted object in the game's own
UI dispatch: the vtable pointer is stale, so slot `+0xC` yields garbage and both
`EIP` and `ESP` go bad together. The Origins code appears on the stack only as a
call that had already completed.

The guard's shipped bytes were dumped and are byte-correct -- both branches
converge on the stock path and the `ret 8` matches the two pushed arguments.
**It must not be patched.** There is no known reproduction, so no fix is
proposed; inventing one without a reproduction would be a change with no way to
tell whether it helped.

## Virtual Villagers 5 -- New Believers

Three dumps, all with an identical signature: `EIP = 0x473447`, reading
`0x1B80`, `ESP` aligned, with `ecx`, `eax` and `esi` all zero.

Unlike VV4 this is a fixed, repeatable fault at a real code address, and the
mechanism is unambiguous:

    0x473440  sub esp, 10h
    0x473443  push ebx
    0x473444  push esi
    0x473445  mov esi, ecx          ; thiscall -- esi = this
    0x473447  mov ecx, [esi+1B80h]  ; <-- faults

`ecx` is zero on entry, so `this` is null and the instruction reads address
`0x1B80` -- exactly the faulting address the exception record carries. A caller
passed a null object.

### Attribution, and a method error worth not repeating

A first attempt reported that seven of the caller functions contained a VVFP
patch. **That was wrong.** The manifests key patches by *file offset*, while the
disassembly addresses are *virtual addresses*, and the comparison was also
mixing manifests from four different games. The overlaps were coincidental.

Redone by converting file offsets through the VV5 PE section table, VV5 has
exactly eleven patch spans inside the stock image: `0x41890F`, `0x41EB6F`,
`0x4237B0`, `0x440A24`, `0x4415F0`, `0x44AF12`, `0x44BC20`, `0x494B32`,
`0x494B37`, `0x494EA0`, and the appended section at `0x7B2000`.

- Inside `sub_473440` (`0x473440`-`0x473583`): **zero**.
- Overlapping any of its thirty call sites: **zero**.
- Control: the same overlap test does identify the known patch at `0x41890F`.

The nearest patch to the fault is over 160 KB away.

**Conclusion.** A stock null-pointer dereference. We patch neither the function
nor any of its callers.

Two limits on this evidence, stated rather than glossed. These dumps carry
timestamps later than the machine's own clock, so they cannot be placed relative
to any change here. Their module-name strings are also scrubbed -- the name RVAs
read as heap fill -- so the module list cannot show whether the companion DLLs
were loaded. The attribution above does not depend on the module list.

## Virtual Villagers 2 -- The Lost Children

Sixty-one crash records in the Windows event log, across four different builds.

### The two most frequent sites are stock defects

`+0x4C823` (16 records) and `+0x4CEE0` (7) occur on the **unmodded**
`Virtual Villagers - The Lost Children.exe` as well as on modded copies. The
unmodded executable contains none of this project's code, so these two sites
cannot be caused by it. Both are the same stock villager-record scan:

    0x44C823  mov  dl, byte ptr [eax + 0xE48C]   ; faults
    0x44C829  add  eax, 0xE48C
    0x44C82E  inc  ecx
    0x44C82F  test dl, dl
    0x44C831  jne  0x44C823

Note the `inc ecx`: there *is* a counter. It records position only and is never
compared against a bound, so termination depends solely on reaching a zero
occupancy byte. State this as "the counter is never used as a bound" rather than
"there is no counter", or the loop reads as misdescribed.

### The two sites that appear only on modded builds

`+0x45B56` (3 records) and `+0x45B5C` (3), most recently 29 August, appear on no
unmodded build. They are the two consecutive instructions at the top of
`sub_445B50`, the village compositor:

    0x445B50  push ebx
    0x445B51  push ebp
    0x445B52  push esi
    0x445B53  mov  esi, ecx             ; thiscall
    0x445B55  push edi
    0x445B56  mov  edi, [esi+0E574D4h]  ; faults (bad this)
    0x445B5C  mov  al,  [edi+2E7F0h]    ; faults (loaded pointer was null)

This warrants care, because **the mask compositor hook patches exactly
`0x445B50`-`0x445B55`** -- the five bytes immediately before the first faulting
instruction. Two things were checked rather than assumed.

*The replay is register-correct.* The stub runs under `pushad`/`popad`, reads
the saved receiver from `[esp+0x18]` (which is `ecx`'s slot in the `pushad`
frame, not another register's), and after `popad` replays the displaced
`push ebx` / `push ebp` / `push esi` / `mov esi, ecx` before resuming at
`0x445B55`. `popad` restores `ecx`, so the `mov esi, ecx` sees the original
receiver.

*The sweep is bounded, and its bound is correct.* The loop is counted --
`cmp esi, 0x100` then `jb` -- unlike the stock scan above. Its last read touches
`gameCtx + 0xE3A7A4`, and the game's own `mov edi, [esi+0E574D4h]` proves
`gameCtx` extends to at least `+0xE574D8`, which leaves room for 257 records.
The 256-iteration bound is inside the structure, not past it.

Both faulting instructions are *after* the point where the hook has already
returned control to stock code. A fault inside the stub would report an address
in the appended code section, not here.

**Conclusion.** These are a null or stale receiver arriving from the game at the
compositor entry -- the same null-`this` shape as the VV5 finding. The hook does
not corrupt the receiver and its sweep stays in bounds. No fix is proposed: the
cause is upstream of our code and there is no reproduction.

### Records that are historical

`+0x25872` (9 records) is on a Modded Playtest build from folders dated
2026-08-10, a superseded playtest, and has not recurred.

## Standing guidance

- Our own record-stride loops across VV1-VV4 are all counted. The stock scans
  they sit near are not; do not "fix" a stock scan to match.
- Attribute a crash by patch coverage, never by which module name appears in the
  log -- a modded build still runs overwhelmingly stock code.
- Convert file offsets to virtual addresses through the section table before
  comparing a manifest against a disassembly, and never compare across games.
