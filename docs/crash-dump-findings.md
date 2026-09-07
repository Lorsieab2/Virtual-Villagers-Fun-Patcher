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

### Where the faulting value could have come from

`0x2E000000` occurs 238 times in the image, and none of those occurrences is
dword-aligned. Every one straddles a boundary inside adjacent string data,
because `0x2E` is the ASCII `.` in literals such as `".png"`, `"..\images\"`,
`"..\sounds\"` and `".?AVl"`.

An earlier draft of this document argued from that alignment that no vtable
could yield the value, since a well-formed vtable's slots are 4-byte aligned.
**That argument is wrong, and it is worth keeping the correction visible so it
is not reintroduced.** Review pointed out that it assumes a well-formed vtable
while reasoning about a corrupted one. `mov eax, [eax+0Ch]` on x86 reads a dword
from any byte address, so a corrupt vtable pointer `P` reaches an unaligned
occurrence `A` whenever `P == A - 0xC` -- always solvable. Alignment therefore
excludes nothing here.

What the alignment does establish is narrower, and is all that is claimed: none
of the 238 occurrences is a deliberate function pointer. They are incidental
byte sequences inside string literals, not entries any code was built to call.

The attribution in the previous section does not rest on this at all. It rests
on our three addresses appearing nowhere in the image, so an indirect call
cannot reach them regardless of how the vtable pointer was corrupted.

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

**Conclusion.** A null-pointer dereference in stock code. We patch neither the
function nor any of its callers, so nothing of ours diverted control here --
though as the section on patch coverage below sets out, that does not by itself
exclude a corruption originating elsewhere.

Two limits on this evidence, stated rather than glossed. These dumps carry
timestamps later than the machine's own clock, so they cannot be placed relative
to any change here. Their module-name strings are also scrubbed -- the name RVAs
read as heap fill -- so the module list cannot show whether the companion DLLs
were loaded. The attribution above does not depend on the module list.

## Not every "Application Error" record is a crash

The Windows event log records more than access violations under the Application
Error source, and counting rows without checking the exception code produces
badly wrong conclusions.

The largest single cluster on this machine looks alarming at first glance: 68
records against a modded A New Home build, all at one address, far more than any
other site. They are not crashes. Fifty-nine carry exception code `0x4000001F`
(`STATUS_WX86_BREAKPOINT`) and nine carry `0x4000001E`
(`STATUS_WX86_SINGLE_STEP`) -- debugger breakpoint and single-step events. All 68
fall inside a single 26-minute window on 23 August from one folder: somebody was
debugging, and the log recorded it.

Filter to `0xC0000005` before counting anything. Across all five games there are
323 Application Error rows but **234 genuine access violations**. For A New Home
the count drops from 153 rows to 76 real faults, and the distribution flattens
out to a long tail whose largest site has seven records, so it has no dominant
signature at all.

The faulting address in that cluster is also a warning about reading too much
into one instruction. It is `mov eax, [esp+arg_0]`, the first instruction of
`sub_43DEF0`, which reads the function's own argument off the stack -- an address
that can only fault if `ESP` itself is bad. Since `sub_43DEF0` is a state-machine
dispatcher with 78 call sites that tail-jumps into handlers, and at least one of
those handlers (`sub_43DAD0`) calls back into it, stack exhaustion through
recursion is an entirely plausible reading. It is also the wrong one: the records
are breakpoints, and no such crash happened. Check the exception code first.

For completeness, no VVFP patch overlaps `sub_43DEF0` or any of its 78 call
sites, with the positive control passing on the known patch at `0x402ED0`.

## Virtual Villagers 1 -- A New Home, Time Warp

The first crash reported from an actual playtest rather than found in the logs,
and the only one with a full memory dump. The player bought Time Warp and the
game crashed, in their words, "immediately when I returned to the village" --
the Tech-screen-close transition, not the aged-village state the warp produces.

`EIP = 0x00416391`, reading `0x9FE8`, `ESP` aligned, `eax = ecx = ebx = edx = 0`:

    0x416380  sub esp, 8
    0x416383  push esi
    0x416384  mov  esi, ecx
    0x416386  call sub_416350
    0x41638B  mov  eax, [esi+1480h]     ; loads a pointer out of the object
    0x416391  mov  cl,  [eax+9FE8h]     ; <-- faults, eax = 0

The faulting address equals the offset exactly, so `eax` was null.

### Two mechanisms proposed, one ruled out and one still open

This one took several attempts, and each theory is recorded with what is and is
not established about it, because each looked convincing and each would
otherwise be proposed again by the next person to open the dump.

**"The allocation failed."** The field's only writer in the whole image is
`0x4172C8`, which stores the result of `sub_41D500` unchecked. That function is
a lazy singleton which returns NULL when `operator new(0xADF4)` fails -- a clean
fit. At crash time the cached singleton `dword_48AEDC` holds `0x027D2050`, and
`edi` holds the same value, so the singleton is live and the crashing object at
`esi = 0x0BD92A48` is a different instance.

That weakens the theory but does **not** refute it, and an earlier draft of this
document claimed it did. Review pointed out the gap: a dump is one instant. It
shows the singleton populated when the process died, not whether an earlier call
returned NULL and stored it here before a later call retried and succeeded. The
chronology is not established, so this remains open rather than closed.

**"Three image loads returned NULL."** The initialiser at `0x417900` loads
`lagoon_restored.jpg`, `temple_rebuilt.jpg` and `garden_restored.png` into
`+0x1470`, `+0x1474` and `+0x1478`, and all three are zero in the dump. The file
names match the reported symptom exactly -- tech-upgrade artwork, shown on
returning to the village.

The reasoning that rules it out has to be exact, because the obvious version of
it is wrong. Review objected that `sub_40A070`'s return value is never tested by
the caller, which is precisely why a NULL from it would end up stored -- and
noted that this repository's own wrapper treats a NULL from that same
constructor as failure (`native/vv1_origins_icons/vv1_origins_icons.c:460-475`).
Both points are correct as stated.

What settles it is the constructor's only exit:

    0x40A0D6  mov  eax, esi
    0x40A0D8  pop  esi
    0x40A0E3  retn 0Ch

`sub_40A070` returns `this` unconditionally -- `esi` is the block the caller just
allocated and null-tested. It has no path returning zero. So whatever happens to
the image inside it, the field receives a non-NULL sprite pointer. (This
project's wrapper is right to check anyway: it calls the same constructor on a
block **it** allocated, and is guarding its own allocation.)

That leaves the `jz` on `operator new` as the only route to a zero here, and it
is the same open question as the theory above: the dump cannot show whether an
allocation failed earlier and a later one succeeded. `MemoryInfoList` reports
407.6 MB committed, 1532.3 MB free and a largest free block of 1098.04 MB **at
crash time**, which makes failure implausible but is not a statement about
minutes earlier.

So the image-load mechanism is ruled out: a failed load cannot put a zero in
these fields. What it collapses into is the *other* theory -- with that route
closed, the `jz` on `operator new` is the only remaining way a zero gets here,
and whether that allocation ever failed is exactly the question the dump cannot
answer, because it records one instant and that instant shows memory to spare.

One mechanism eliminated, then, and one open; and the open one is not
independent of the first -- both paths funnel into the same unanswered
allocation question. Answering it needs a second occurrence, or a way to
establish the allocation chronology.

### What the memory actually shows

A contiguous zero run from `+0x1470` to `+0x1488`, with live data on both sides:
`+0x10E0` holds `0x0D8D6F00`, `+0x14B8` holds `0x0D8D6F54`, and `+0x148C` holds
`0x0C05C445`. The object is populated -- 1282 non-zero bytes in its first 0x1500
-- so this is not a freed block and not a wholesale zeroing.

**The certain claim is only this: those fields were never populated on this
object, while its neighbours were.** An earlier draft went further and said the
initialiser "did not run", which review correctly called unsupported -- the
memory cannot distinguish between an initialiser that never ran and one that ran
and took its null branches.

Two candidate explanations therefore remain open, and both are recorded above
rather than settled:

- the initialiser never ran on this object, and something else populated its
  neighbours;
- it ran and `operator new` returned NULL for all three, which the dump cannot
  exclude because it shows only the final instant.

Which path reaches `sub_416380` on such an object is not traced either, and is
not guessed at here.

Note also that `sub_416350`, called immediately before the faulting load, clears
`+0x10` through `+0x1400` in 256 iterations of stride `0x14`. `+0x1480` lies
past that range, so the clear is not what zeroed it.

### Attribution

`sub_423390` reaches the faulting function through a **vtable slot** in
`.rdata:0x4598D0`, so this is virtual dispatch rather than a direct call.

- The bytes that fault are byte-identical to the stock executable. Comparing
  live crashed memory against the stock image: `sub_416380`, `sub_416350`,
  `sub_423390`'s tail including the call site at `0x423494`, and the vtable slot
  itself all match exactly. This is the same decisive form used for VV4, and it
  is stronger than a patch-span scan because it cannot have a coverage hole.
- VVFP has exactly two `.rdata` patches, at `0x456900` and `0x485D30`. Neither
  covers `0x4598D0`, so the slot still holds its stock target and no patch here
  redirected the dispatch. That is a statement about control flow only.
- No VVFP code calls `sub_423390`, `sub_416380`, `sub_4179D0`, `sub_417280` or
  `sub_41D500`. Every `E8` relative call in every VV1 patch payload was decoded
  and its target resolved; none of the five appears.
- The patcher's own packaging is cleared separately: it copies the game folder
  with `shutil.copytree` and no `ignore=` filter, then verifies every file by
  size and SHA-256, raising rather than continuing on any mismatch.
- The `Visual Mods` patch swaps two of the three named images. Its pinned
  preimages were checked against the player's own untouched originals and match
  exactly, as do both the replacement and restore copies against their manifest
  hashes.

One observation settles the packaging question without needing the folder, which
has since been deleted: `temple_rebuilt.jpg` is **not** a file this project
touches. Had a swap damaged the two that are, the third would still have loaded.
All three were zero, so the outcome is not specific to the swapped files.

### Status

The dereference is unchecked stock code that this project does not patch, on a
dispatch it did not redirect, in a function whose bytes it has not modified.

That is the absence of a direct call and of any control-flow redirection. It is
**not** proof that the patch is uninvolved, and the section on what patch
coverage does and does not prove applies here in full. The Time Warp purchase
runs this project's code and then returns into the stock screen-close flow, so
an unchanged dispatch can still consume state that ran earlier. Nothing measured
here excludes that, and review flagged an earlier draft of this section for
claiming otherwise.

No fix is proposed: the path that leaves the object half-initialised is
untraced, and a fix aimed at an untraced path cannot be validated. Nor is the
investigation closed -- a second occurrence, with a dump, is what would move it.

A caveat that applies to this dump as it did to the VV5 ones: its module-name
strings are scrubbed, so the loaded-module list cannot be read and is not relied
on anywhere above.

## Virtual Villagers 2 -- The Lost Children

Sixty-one records in the Windows event log, across four different builds. All 61
are genuine `0xC0000005` access violations -- unlike the A New Home cluster
above, none of these are debugger events.

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

**Conclusion.** A null or stale receiver at the compositor entry -- the same
null-`this` shape as the VV5 finding. The two mechanisms by which the hook could
have produced it were checked and ruled out: the replay does not corrupt the
receiver, and the sweep stays inside the structure.

That is as far as the evidence goes. It does not establish that the hook is
uninvolved by some path not examined here, and these are the crash sites closest
to our code anywhere in this document, so they deserve the least generous
reading. What would settle it is a reproduction, or catching the receiver going
bad; neither exists. No fix is proposed, because there is nothing yet to aim one
at.

### Records that are historical

`+0x25872` (9 records) is on a Modded Playtest build from folders dated
2026-08-10, a superseded playtest, and has not recurred.

## What patch coverage does and does not prove

Every attribution above uses patch-span overlap, and it is important to be
precise about how much that carries, because review flagged an earlier draft for
overstating it.

Patch coverage answers one question well: **did our code execute at the faulting
instruction, or place something at the address that faulted?** A hook that does
not overlap the faulting function or any of its call sites did not directly
divert control there.

It does **not** prove our code is uninvolved. A hook anywhere in the process can
corrupt an object, a heap block, or a global that stock code dereferences much
later, and the fault then lands in code we never touched. That is exactly the
shape of the VV4 finding -- a stale object reached through a vtable -- so the
possibility cannot be waved away.

Nor does seeing a fault site on an unmodified build settle the modded
occurrences. It proves the stock game *can* produce that signature; it does not
prove every modded instance has the same upstream cause. Two different causes can
converge on one faulting instruction, and a null receiver is precisely the kind
of symptom many causes share.

So the honest status of every conclusion here is: **no evidence implicates our
code, and for the VV2 compositor hook the specific mechanisms by which it could
have were checked and ruled out** -- the register-correct replay and the proven
sweep bound. That is weaker than "our code is innocent", and it is deliberately
not written as though it were. Closing any of these properly needs a
reproduction, or a traced corruption path, neither of which exists yet.

This is also why no fix is proposed anywhere in this document. A fix aimed at a
cause that has not been traced cannot be validated, and shipping one would make
the next investigation harder rather than easier.

## Standing guidance

- Our own record-stride loops across VV1-VV4 are all counted. The stock scans
  they sit near are not; do not "fix" a stock scan to match.
- Patch coverage narrows attribution, it does not close it. Never write up a
  no-overlap result as proof of innocence; say what was ruled out and what was
  not.
- Never attribute by which module name appears in the log -- a modded build still
  runs overwhelmingly stock code.
- Convert file offsets to virtual addresses through the section table before
  comparing a manifest against a disassembly, and never compare across games.
- Filter by exception code before counting; breakpoints and single-step events
  share the Application Error source with real faults.
