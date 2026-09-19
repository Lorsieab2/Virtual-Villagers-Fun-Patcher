# VV5 village mask rendering: the mechanism that works

Reference documentation, extracted from a binary that is confirmed working.

**Provenance.** The owner still had the v1.34.38 patcher and confirmed that build
renders village masks correctly. A VV5 was patched with it and the resulting
executable disassembled. Every address, byte and instruction below is read out
of that working binary. Nothing here is inferred from source or reasoning.

This document exists because four successive attempts to reimplement this
feature failed, each in a different visible way, and each attempt was reasoned
from the stock call sites rather than from a working build.

**Which v1.34.38 zip.** There are two, and only one of them is this mechanism.
`outputs/Virtual-Villagers-Fun-Patcher-v1.34.38-source.zip` in this repository
contains the OVERLAY: it patches the believer draw at `0x47279C` and leaves both
epilogues stock. The zip the owner actually downloaded and ran, kept outside the
repository, contains the flip and has no `mask_overlay` at all. Building from
the wrong one reproduces the broken build while appearing to confirm the
working one, which happened once during this work. Check which mechanism a
candidate source contains before trusting it as a reference:

```
grep -c "mask_overlay\|mask_arm"   scripts/build_vv5_task9_native_actions.py   # overlay build
grep -c "mask_flip\|mask_restore"  scripts/build_vv5_task9_native_actions.py   # working build
```

**Verification of the restoration.** A VV5 patched with the restored builder was
diffed against a VV5 patched with the owner's working zip, across the whole
villager render function and both page routines. `mask_flip` is byte-identical.
`mask_restore` differs only where the literal-zero stores documented in section 4
become loads of the saved values. The two remaining bytes, at `0x472B14` and
`0x472B5C`, are the filler after a 5-byte `jmp` that replaced 6 stolen bytes:
`0x90` here against `0x00` in the working build, and never executed in either.

 VILLAGE MASK MECHANISM — extracted from v1.34.38

Extracted by patching a VV5 with the owner's v1.34.38 patcher (owner-confirmed rendering village masks correctly) and disassembling the result. This is the reference implementation. Everything below is read out of a working binary, not inferred.

### 1. It does NOT hook the believer head draw

This is the single most important fact, and it is the opposite of what the current code does.

| address | stock | **v1.34.38 (WORKS)** | current (broken) |
|---|---|---|---|
| `0x47279C` believer head draw | `E83FCEFDFF` | **`E83FCEFDFF` — UNPATCHED** | `E85FD23500` hooked to `mask_overlay` |

The working build never touches the draw call. It lets the game's own renderer draw the mask, by changing what the villager *is* for the duration of that draw.

### 2. The complete set of patched sites

Diffing the working exe against stock, inside the villager render region:

```
00472481  len 4   8B8C24BC -> E97AD335   arm hook   -> jmp 0x7CF800
00472486  len 2   0000     -> 9090       (padding)
00472B0F  len 4   81C4A800 -> E9ECCE35   restore #1 -> jmp 0x7CFA00
00472B57  len 4   81C4A800 -> E9A4CE35   restore #2 -> jmp 0x7CFA00
00472C04  len 10  83FE0A7505BE0F00 -> BE3C000000909090
00472C49  len 7   83C65A3BDE7C06   -> E9B21802009090
```

Three hooks matter: **one arm site and TWO restore sites**, both of which replace an `add esp, 0xA8` epilogue.

### 3. `mask_flip` @ `0x7CF800` — the arm routine

Entered from `0x472481`, returns to `0x472488`.

```asm
007CF800  push  eax
007CF801  push  edx
007CF802  cmp   byte [0x7B1D6C], 0      ; sidecar loaded yet?
007CF809  jne   loaded
007CF80B  call  0x7CFD00                ; mask_load_once
loaded:
007CF810  call  0x7CFC00                ; mask_get -> eax = 0..5
007CF815  test  eax, eax
007CF817  je    done                    ; 0 = no mask
007CF81D  cmp   eax, 5
007CF820  ja    done                    ; out of range
007CF826  cmp   byte [0x7B1D00], 0
007CF82D  jne   done                    ; already armed, do not nest
007CF833  cmp   byte [esi+0x1CEC], 0
007CF83A  jne   done                    ; BELIEVERS ONLY - never touch a real heathen

007CF840  mov   byte  [0x7B1D00], 1     ; armed
007CF847  mov   dword [0x7B1D10], esi   ; remember which villager

; SAVE the three colour fields before overwriting them
007CF84D  movzx edx, byte [esi+0x1CED]
007CF854  mov   dword [0x7B1D04], edx   ; saved orange
007CF85A  movzx edx, byte [esi+0x1CEE]
007CF861  mov   dword [0x7B1D08], edx   ; saved red
007CF867  movzx edx, byte [esi+0x1CFC]
007CF86E  mov   dword [0x7B1D0C], edx   ; saved purple/chief

; CLEAR them, then set exactly one according to the mask colour
007CF874  mov   byte [esi+0x1CED], 0
007CF87B  mov   byte [esi+0x1CEE], 0
007CF882  mov   byte [esi+0x1CFC], 0

007CF889  cmp   eax, 2 / je orange
007CF88E  cmp   eax, 3 / je red
007CF893  cmp   eax, 4 / je purple
007CF898  cmp   eax, 5 / je chief
          jmp   setfaction              ; 1 = BLUE, all three left at 0
orange:   mov   byte [esi+0x1CED], 1
red:      mov   byte [esi+0x1CEE], 1
purple:   mov   byte [esi+0x1CFC], 0x0C
chief:    mov   byte [esi+0x1CFC], 0x0D
setfaction:
007CF8C1  mov   byte [esi+0x1CEC], 1    ; render as heathen for this draw
done:
007CF8C8  pop   edx
007CF8C9  pop   eax
007CF8CA  mov   ecx, [esp+0xBC]         ; the stolen instruction
007CF8D1  jmp   0x472488
```

**Mask colour to field mapping:**

| mask | field written |
|---|---|
| 1 blue | none — all three cleared |
| 2 orange | `+0x1CED = 1` |
| 3 red | `+0x1CEE = 1` |
| 4 purple | `+0x1CFC = 0x0C` |
| 5 chief | `+0x1CFC = 0x0D` |

Plus `+0x1CEC = 1` in every masked case, which is what makes the stock renderer take the heathen branch at `0x472729` and select the mask sprite itself.

### 4. `mask_restore` @ `0x7CFA00` — and the latent bug

Entered from both `0x472B0F` and `0x472B57`, each replacing `add esp, 0xA8`.

```asm
007CFA00  cmp   byte [0x7B1D00], 0
007CFA07  je    skip
007CFA09  push  eax
007CFA0A  push  edx
007CFA0B  mov   eax, [0x7B1D10]
007CFA10  mov   byte [eax+0x1CEC], 0    ; faction back to believer
007CFA17  mov   byte [eax+0x1CED], 0    ; <-- WRITES ZERO, NOT THE SAVED VALUE
007CFA1E  mov   byte [eax+0x1CEE], 0    ; <-- WRITES ZERO, NOT THE SAVED VALUE
007CFA25  mov   edx, [0x7B1D0C]
007CFA2B  mov   byte [eax+0x1CFC], dl   ; this one IS restored properly
007CFA31  mov   byte [0x7B1D00], 0
007CFA38  pop   edx
007CFA39  pop   eax
skip:
007CFA3A  add   esp, 0xA8               ; the stolen instruction
007CFA40  ret   8
```

**Note the defect:** `+0x1CED` and `+0x1CEE` are saved to `0x7B1D04` / `0x7B1D08` but restored as **literal zero**. Only `+0x1CFC` is genuinely restored. A mask on an orange or red villager silently clears that villager's colour. This is worth fixing when the mechanism is restored — the saved values are right there.

### 5. Scratch layout

| address | holds |
|---|---|
| `0x7B1D00` | armed flag (1 while a villager is flipped) |
| `0x7B1D04` | saved `+0x1CED` (orange) |
| `0x7B1D08` | saved `+0x1CEE` (red) |
| `0x7B1D0C` | saved `+0x1CFC` (purple/chief) |
| `0x7B1D10` | the flipped villager's record pointer |
| `0x7B1D20` | `MASK_TABLE`, one nibble per villager |
| `0x7B1D6C` | sidecar-loaded flag |

Note `0x7B1D04` means **saved orange flag** here. In the current broken code the same address is reused for the raw mask choice, which is a different thing entirely.

### 6. Why this works and the overlay never could

The heathen branch at `0x472732` does not accept a mask number. It *picks* its sprite argument from one of three caller stack slots according to the villager's own colour flags:

```
cmp byte [esi+0x1CED], 0   ; orange -> edx <- [esp+0x4C]
cmp byte [esi+0x1CEE], 0   ; red    -> edx <- [esp+0x54]
otherwise                          edx <- [esp+0x30]
```

Those are sprite handles the caller already prepared. The flip works because it lets the game make that selection. Nothing supplied from outside can substitute for it, which is why all four attempted argument orderings for `mask_overlay` failed — argument 1 crashed (it is dereferenced as an object pointer), argument 8 landed in a float slot, argument 6 drew a ghost body, and the caller-slot variant drew nothing.

### 7. The real defect in the working mechanism

The flip itself was never wrong. What caused the retired-chief crash is that the restore lives in a **function epilogue**: if anything faults between the arm and that epilogue, the villager is left permanently heathen with its colour fields zeroed.

So the fix is to keep this mechanism and make the restore unskippable, not to replace it with a second draw call.
