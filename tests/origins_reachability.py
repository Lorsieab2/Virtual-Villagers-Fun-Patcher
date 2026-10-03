"""Reachability of patcher-owned bytes in a rendered executable.

Used by the "no unreachable Origins code" tests. Given a rendered image and
the VA ranges a feature owns, it finds every byte of those ranges that live
code can reach, so a test can require that nothing else is left there.

* Roots: every rel32 jmp/call/jcc target and every 32-bit value found
  anywhere OUTSIDE the owned ranges that lands inside them -- the hooks,
  pointers and tables through which the game enters patcher code. Being
  conservative (a coincidental value counts as a root) can only make more
  bytes live, never fewer.
* From the roots: disassembly following fall-through, direct branch and
  call targets, jump/call tables (`[disp + reg*4]`, read until an entry
  leaves the owned ranges), `push imm; ret`, `mov reg, imm ... jmp/call reg`,
  and any immediate into a code range (a routine address handed to another
  routine).
* Any other immediate or displacement made by REACHED code is a data
  reference: it marks the C string it points at, the whole known data object
  it falls in (price tables and the like), or four bytes.

Only references made by reached code count, so code reachable solely from
other dead code is reported dead too.

PATH-SENSITIVE ON REGISTER VALUES. A path the code's own earlier tests rule
out is not followed. Codex (#506 review) found the first version marked VV2's
Tech-menu fallback live although every command value had already been
dispatched before it: syntactic reachability is not reachability. So each
path carries, per general register, the values it can hold -- exactly, as a
set, while there are few of them, otherwise as an unsigned interval -- and a
`cmp reg, imm` / `test reg, reg` followed by a conditional jump narrows them
on each side; a side no value can take is never taken. A call into owned code is entered with the caller's intervals, so a
helper only ever called with ebx = 5 has its ebx != 5 arm reported dead.

What it assumes, and why that is safe:

* A callee preserves ebx, esi, edi, ebp and esp, and may change eax, ecx,
  edx and the flags -- the Win32 calling convention every game routine,
  DLL export and patcher helper here follows. A patcher-owned callee that
  provably hands eax, ecx or edx back unchanged on every path to its `ret`
  (it pushes and pops them, say) keeps them across the call; the proof
  tracks the routine's own stack and gives up -- keeping the convention's
  answer -- on anything it cannot follow.
* Any write it does not model (pop, arithmetic, a memory load, a partial
  register) makes the register unknown. Unknown only ever means "any value",
  which can only make more bytes live.
* An address may be reached with many distinct intervals; past a small cap
  they are merged into their hull, which again only widens.

So every bias is toward reporting MORE code as live: a byte this reports
dead is dead on every path the code's own branches allow.
"""
from __future__ import annotations

import struct

import capstone
from capstone import x86 as X
import pefile

TERMINATORS = {"ret", "retf", "jmp", "int3", "ud2", "hlt"}

# The eight general registers, and every narrower name that writes into one.
_GPR = (
    X.X86_REG_EAX, X.X86_REG_ECX, X.X86_REG_EDX, X.X86_REG_EBX,
    X.X86_REG_ESP, X.X86_REG_EBP, X.X86_REG_ESI, X.X86_REG_EDI,
)
_PARENT = {
    X.X86_REG_EAX: 0, X.X86_REG_AX: 0, X.X86_REG_AL: 0, X.X86_REG_AH: 0,
    X.X86_REG_ECX: 1, X.X86_REG_CX: 1, X.X86_REG_CL: 1, X.X86_REG_CH: 1,
    X.X86_REG_EDX: 2, X.X86_REG_DX: 2, X.X86_REG_DL: 2, X.X86_REG_DH: 2,
    X.X86_REG_EBX: 3, X.X86_REG_BX: 3, X.X86_REG_BL: 3, X.X86_REG_BH: 3,
    X.X86_REG_ESP: 4, X.X86_REG_SP: 4,
    X.X86_REG_EBP: 5, X.X86_REG_BP: 5,
    X.X86_REG_ESI: 6, X.X86_REG_SI: 6,
    X.X86_REG_EDI: 7, X.X86_REG_DI: 7,
}
_FULL = {reg: index for index, reg in enumerate(_GPR)}
TOP = None                       # an unknown register: any value
IMPOSSIBLE = "impossible"        # a branch side no value can take
_UNKNOWN = (TOP,) * 8
_CALLER_SAVED = (0, 1, 2)        # eax, ecx, edx
_STATES_PER_ADDRESS = 12         # past this, merge into the hull
_MASK = 0xFFFFFFFF
_SIGNED_ALIASES = {"jl": "jb", "jge": "jae", "jg": "ja", "jle": "jbe"}


_SMALL = 64                      # a value range this small is kept as a set


def _bounds(value):
    """(lowest, highest) of a known value; the whole range for TOP."""
    if value is TOP:
        return 0, _MASK
    if isinstance(value, frozenset):
        return min(value), max(value)
    return value


def _single(value):
    """The one value a register can hold, or None."""
    if isinstance(value, frozenset) and len(value) == 1:
        return next(iter(value))
    if isinstance(value, tuple) and value[0] == value[1]:
        return value[0]
    return None


def _shrink(lo, hi):
    """An interval, kept exactly as a set when it is small."""
    if lo > hi:
        return IMPOSSIBLE
    if hi - lo < _SMALL:
        return frozenset(range(lo, hi + 1))
    return (lo, hi)


def _join(a, b):
    if a is TOP or b is TOP:
        return TOP
    if isinstance(a, frozenset) and isinstance(b, frozenset) and len(a | b) <= _SMALL:
        return a | b
    (alo, ahi), (blo, bhi) = _bounds(a), _bounds(b)
    return (min(alo, blo), max(ahi, bhi))


def _join_states(states):
    regs = list(states[0][0])
    flags = states[0][1]
    for other_regs, other_flags in states[1:]:
        regs = [_join(x, y) for x, y in zip(regs, other_regs)]
        if other_flags != flags:
            flags = None
    return (tuple(regs), flags)


def _signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


_TESTS = {
    "je": lambda v, i: v == i, "jz": lambda v, i: v == i,
    "jne": lambda v, i: v != i, "jnz": lambda v, i: v != i,
    "jb": lambda v, i: v < i, "jae": lambda v, i: v >= i,
    "ja": lambda v, i: v > i, "jbe": lambda v, i: v <= i,
    "jl": lambda v, i: _signed(v) < _signed(i), "jge": lambda v, i: _signed(v) >= _signed(i),
    "jg": lambda v, i: _signed(v) > _signed(i), "jle": lambda v, i: _signed(v) <= _signed(i),
}


def _narrow(value, condition, imm):
    """(taken, not taken) values of a register after `cmp reg, imm` and the
    conditional jump `condition`; IMPOSSIBLE when that side cannot happen.

    A small set is narrowed exactly, value by value, so a jump chain that
    peels rows off one at a time leaves exactly the rows still possible --
    an interval cannot hold the hole a handled row leaves in the middle."""
    test = _TESTS.get(condition)
    if test is None:
        return value, value
    if isinstance(value, frozenset):
        taken = frozenset(v for v in value if test(v, imm))
        other = value - taken
        return (taken or IMPOSSIBLE), (other or IMPOSSIBLE)
    lo, hi = _bounds(value)
    if condition in _SIGNED_ALIASES:
        # Signed and unsigned agree only when both sides are non-negative.
        if hi > 0x7FFFFFFF or imm > 0x7FFFFFFF:
            return value, value
        condition = _SIGNED_ALIASES[condition]
    if condition in ("je", "jz"):
        if not lo <= imm <= hi:
            return IMPOSSIBLE, value
        taken = frozenset((imm,))
        if lo == hi:
            return taken, IMPOSSIBLE
        if lo == imm:
            return taken, _shrink(lo + 1, hi)
        if hi == imm:
            return taken, _shrink(lo, hi - 1)
        return taken, value
    if condition in ("jne", "jnz"):
        equal, unequal = _narrow(value, "je", imm)
        return unequal, equal
    if condition == "jb":
        return _shrink(lo, min(hi, imm - 1)), _shrink(max(lo, imm), hi)
    if condition == "jae":
        below, above = _narrow(value, "jb", imm)
        return above, below
    if condition == "ja":
        return _shrink(max(lo, imm + 1), hi), _shrink(lo, min(hi, imm))
    if condition == "jbe":
        above, below = _narrow(value, "ja", imm)
        return below, above
    return value, value


# The stdcall imports patcher code calls, by the bytes they pop.
_IMPORT_POPS = {
    b"LoadLibraryA": 4, b"LoadLibraryW": 4, b"GetProcAddress": 8,
    b"GetModuleHandleA": 4, b"GetModuleHandleW": 4, b"MessageBoxA": 16,
    b"FreeLibrary": 4, b"GetModuleFileNameA": 12, b"GetModuleFileNameW": 12,
}


def _imports(data: bytes) -> dict[int, int]:
    """{IAT slot VA: bytes the import pops} for the imports above."""
    pe = pefile.PE(data=data, fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
    )
    found = {}
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        for symbol in entry.imports:
            if symbol.name in _IMPORT_POPS:
                found[symbol.address] = _IMPORT_POPS[symbol.name]
    return found


def _load(data: bytes):
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    size = pe.OPTIONAL_HEADER.SizeOfImage
    image = bytearray(size)
    image[: pe.OPTIONAL_HEADER.SizeOfHeaders] = data[: pe.OPTIONAL_HEADER.SizeOfHeaders]
    executable = []
    for section in pe.sections:
        raw = data[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
        image[section.VirtualAddress: section.VirtualAddress + len(raw)] = raw[: size - section.VirtualAddress]
        if section.Characteristics & 0x20000000:
            executable.append(
                (section.VirtualAddress, section.VirtualAddress + max(section.Misc_VirtualSize, len(raw)))
            )
    return image, base, size, executable


def reach(data: bytes, regions, data_objects=None, code_ranges=None, trace=None, edges=None,
          states=None):
    """Return (image, base, live VAs) for the owned `regions` of `data`.

    regions:      [(lo, hi)] owned VA ranges.
    data_objects: {va: length} data objects (tables) inside the regions.
    code_ranges:  [(lo, hi)] ranges where an immediate pointing in is code.
    trace:        optional dict, filled with {va: the va it was first reached
                  from} (None for a root) -- for explaining a result.
    edges:        optional dict, filled with {va of a conditional jump:
                  [taken ever possible, fall-through ever possible]} -- a
                  False is a check whose outcome the code already decided.
    states:       optional dict, filled with {va: [the register states it was
                  explored with]} -- for explaining a result.
    """
    data_objects = dict(data_objects or {})
    code_ranges = list(code_ranges or [])

    def in_object(v):
        return next(((o, n) for o, n in data_objects.items() if o <= v < o + n), None)

    image, base, size, executable = _load(data)

    def is_string(v):
        """A NUL-terminated run of four or more printable characters: the
        names handed to LoadLibrary/GetProcAddress and the messages. Decoded
        as code they are junk whose stray jumps make real dead code look
        live. Code that happened to read as text would be reported dead, a
        loud failure rather than a silent pass."""
        at = v - base
        length = 0
        while 0 <= at + length < size and 0x20 <= image[at + length] < 0x7F:
            length += 1
        return length >= 4 and 0 <= at + length < size and image[at + length] == 0

    def in_code(v):
        return (
            any(lo <= v < hi for lo, hi in code_ranges)
            and in_object(v) is None
            and not is_string(v)
        )

    inside = bytearray(size)
    for lo, hi in regions:
        inside[lo - base: hi - base] = b"\1" * (hi - lo)

    def owned(va):
        return 0 <= va - base < size and inside[va - base]

    unknown = (_UNKNOWN, None)
    work: list[tuple[int, tuple, int | None]] = []
    data_refs: set[int] = set()
    view = memoryview(image)
    for shift in range(4):
        words = struct.iter_unpack("<I", view[shift: shift + (size - shift) // 4 * 4])
        for index, (value,) in enumerate(words):
            if not inside[shift + index * 4] and owned(value):
                data_refs.add(value)
                if in_code(value):
                    work.append((value, unknown, None))
    for lo, hi in executable:
        for rva in range(lo, min(hi, size - 6)):
            if inside[rva]:
                continue
            op = image[rva]
            if op in (0xE8, 0xE9):
                target = (base + rva + 5 + struct.unpack_from("<i", image, rva + 1)[0]) & _MASK
            elif op == 0x0F and 0x80 <= image[rva + 1] <= 0x8F:
                target = (base + rva + 6 + struct.unpack_from("<i", image, rva + 2)[0]) & _MASK
            else:
                continue
            if owned(target):
                work.append((target, unknown, None))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    decoded: dict[int, object] = {}

    def decode(va):
        if va not in decoded:
            decoded[va] = next(md.disasm(bytes(image[va - base: va - base + 16]), va), None)
        return decoded[va]

    live: set[int] = set()
    code_seen: set[int] = set()
    seen_states: dict[int, list] = {}
    import_pops = _imports(data)
    summaries: dict[int, frozenset] = {}

    def ret_pops(target):
        """Bytes a routine's `ret` pops, from its first one -- an owned
        routine or a game routine in an executable section."""
        va = target
        for _ in range(4000):
            if not any(lo <= va - base < hi for lo, hi in executable):
                return None
            insn = decode(va)
            if insn is None:
                return None
            if insn.mnemonic == "ret":
                return insn.operands[0].imm if insn.operands else 0
            va += insn.size
        return None

    def preserved(target):
        """The caller-saved registers (0 eax, 1 ecx, 2 edx) an owned routine
        provably returns unchanged; empty when anything is in doubt."""
        if target in summaries:
            return summaries[target]
        summaries[target] = frozenset()          # recursion: assume nothing
        entry = tuple(("in", index) for index in range(8))
        todo = [(target, entry, ())]
        visited = set()
        kept = {0, 1, 2}
        steps = 0
        while todo:
            va, regs_in, stack = todo.pop()
            if (va, regs_in, stack) in visited:
                continue
            visited.add((va, regs_in, stack))
            steps += 1
            if steps > 4000 or len(stack) > 64 or not owned(va):
                return summaries[target]
            insn = decode(va)
            if insn is None:
                return summaries[target]
            regs_now = list(regs_in)
            stack_now = list(stack)
            m, ops = insn.mnemonic, insn.operands
            nxt = va + insn.size
            if m == "ret":
                if stack_now:
                    return summaries[target]
                kept &= {i for i in (0, 1, 2) if regs_now[i] == ("in", i)}
                continue
            if m == "push":
                if ops[0].type == X.X86_OP_REG and ops[0].reg in _FULL:
                    stack_now.append(regs_now[_FULL[ops[0].reg]])
                else:
                    stack_now.append(None)
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if m == "pop":
                if not stack_now or ops[0].type != X.X86_OP_REG or ops[0].reg not in _FULL:
                    return summaries[target]
                regs_now[_FULL[ops[0].reg]] = stack_now.pop()
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if m in ("pushal", "pushad"):
                stack_now.extend(regs_now[i] for i in (0, 1, 2, 3, 4, 5, 6, 7))
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if m in ("popal", "popad"):
                if len(stack_now) < 8:
                    return summaries[target]
                values = stack_now[-8:]
                del stack_now[-8:]
                for i in (0, 1, 2, 3, 5, 6, 7):
                    regs_now[i] = values[i]
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if m in ("pushfd", "pushfl"):
                stack_now.append(None)
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if m in ("popfd", "popfl"):
                if not stack_now:
                    return summaries[target]
                stack_now.pop()
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            _, written = insn.regs_access()
            written_gprs = {_PARENT[r] for r in written if r in _PARENT}
            if insn.group(capstone.CS_GRP_CALL):
                op = ops[0]
                if op.type == X.X86_OP_IMM and owned(op.imm & _MASK):
                    pops = ret_pops(op.imm & _MASK)
                    keep = preserved(op.imm & _MASK)
                elif op.type == X.X86_OP_IMM:
                    pops = ret_pops(op.imm & _MASK)     # a game routine
                    keep = frozenset()
                elif op.type == X.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                    pops = import_pops.get(op.mem.disp & _MASK)
                    keep = frozenset()
                elif op.type == X.X86_OP_REG:
                    # A DLL export the routine resolved: stdcall, so it pops
                    # the arguments pushed for it -- every value pushed since
                    # the last saved register. (Were it not, the routine's
                    # own pops would restore the wrong values.)
                    pops = 0
                    while len(stack_now) > pops // 4 and stack_now[-1 - pops // 4] is None:
                        pops += 4
                    keep = frozenset()
                else:
                    return summaries[target]
                if pops is None or pops % 4 or len(stack_now) < pops // 4:
                    return summaries[target]
                if pops:
                    del stack_now[-(pops // 4):]
                for i in (0, 1, 2):
                    if i not in keep:
                        regs_now[i] = None
                todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                continue
            if 4 in written_gprs:
                # esp changed other than by push/pop/call: only a whole
                # number of slots added or subtracted is followed.
                if (
                    m in ("add", "sub") and ops[0].type == X.X86_OP_REG
                    and ops[0].reg == X.X86_REG_ESP and ops[1].type == X.X86_OP_IMM
                    and ops[1].imm % 4 == 0
                ):
                    count = ops[1].imm // 4
                    if m == "sub":
                        count = -count
                    if count > 0:
                        if len(stack_now) < count:
                            return summaries[target]
                        del stack_now[-count:]
                    else:
                        stack_now.extend([None] * -count)
                    todo.append((nxt, tuple(regs_now), tuple(stack_now)))
                    continue
                return summaries[target]
            for index in written_gprs:
                regs_now[index] = None
            if (
                m == "mov" and len(ops) == 2 and ops[0].type == X.X86_OP_REG
                and ops[0].reg in _FULL and ops[1].type == X.X86_OP_REG and ops[1].reg in _FULL
            ):
                regs_now[_FULL[ops[0].reg]] = regs_in[_FULL[ops[1].reg]]
            branch = insn.group(capstone.CS_GRP_JUMP)
            if branch:
                op = ops[0]
                if op.type != X.X86_OP_IMM:
                    return summaries[target]
                destination = op.imm & _MASK
                if not owned(destination):
                    return summaries[target]     # a tail jump out
                todo.append((destination, tuple(regs_now), tuple(stack_now)))
                if m == "jmp":
                    continue
            elif m in TERMINATORS:
                return summaries[target]
            todo.append((nxt, tuple(regs_now), tuple(stack_now)))
        summaries[target] = frozenset(kept)
        return summaries[target]

    def admit(va, state):
        """The state to explore `va` with, or None when it adds nothing."""
        seen = seen_states.setdefault(va, [])
        if state in seen:
            return None
        if len(seen) >= _STATES_PER_ADDRESS:
            state = _join_states(seen + [state])
            if state in seen:
                return None
        seen.append(state)
        return state

    while work:
        va, state, came_from = work.pop()
        if not owned(va):
            continue
        state = admit(va, state)
        if state is None:
            continue
        if trace is not None:
            trace.setdefault(va, came_from)
        insn = decode(va)
        if insn is None:
            continue
        code_seen.add(va)
        live.update(range(va, va + insn.size))
        regs, flags = list(state[0]), state[1]
        operands = insn.operands
        mnemonic = insn.mnemonic
        branch = insn.group(capstone.CS_GRP_JUMP) or insn.group(capstone.CS_GRP_CALL)
        is_call = insn.group(capstone.CS_GRP_CALL)
        targets: list[int] = []
        for op in operands:
            if op.type == X.X86_OP_IMM:
                value = op.imm & _MASK
                if not owned(value):
                    continue
                if branch:
                    targets.append(value)
                elif in_code(value):
                    work.append((value, unknown, va))
                elif mnemonic == "push":
                    following = decode(va + insn.size)
                    if following is not None and following.mnemonic == "ret":
                        work.append((value, (tuple(regs), None), va))
                    else:
                        data_refs.add(value)
                else:
                    data_refs.add(value)
            elif op.type == X.X86_OP_MEM:
                value = op.mem.disp & _MASK
                if not owned(value):
                    continue
                if branch and op.mem.index != 0:
                    entry = value
                    while owned(entry):
                        target = struct.unpack_from("<I", image, entry - base)[0]
                        if not owned(target):
                            break
                        live.update(range(entry, entry + 4))
                        targets.append(target)
                        entry += 4
                else:
                    data_refs.add(value)
            elif op.type == X.X86_OP_REG and branch:
                known = regs[_FULL[op.reg]] if op.reg in _FULL else TOP
                single = _single(known)
                if single is not None and owned(single):
                    targets.append(single)

        # The register and flag effects of this instruction.
        _, written = insn.regs_access()
        written_gprs = {_PARENT[r] for r in written if r in _PARENT}
        writes_flags = X.X86_REG_EFLAGS in written or insn.eflags != 0
        new_flags = None if writes_flags else flags
        if new_flags is not None and new_flags[1] in written_gprs:
            new_flags = None              # the compared register changed
        exact = None
        if (
            mnemonic == "mov" and len(operands) == 2
            and operands[0].type == X.X86_OP_REG and operands[0].reg in _FULL
        ):
            if operands[1].type == X.X86_OP_IMM:
                value = operands[1].imm & _MASK
                exact = (_FULL[operands[0].reg], frozenset((value,)))
            elif operands[1].type == X.X86_OP_REG and operands[1].reg in _FULL:
                exact = (_FULL[operands[0].reg], regs[_FULL[operands[1].reg]])
        elif (
            mnemonic == "xor" and len(operands) == 2
            and operands[0].type == operands[1].type == X.X86_OP_REG
            and operands[0].reg == operands[1].reg and operands[0].reg in _FULL
        ):
            exact = (_FULL[operands[0].reg], frozenset((0,)))
        if (
            mnemonic == "cmp" and len(operands) == 2
            and operands[0].type == X.X86_OP_REG and operands[0].reg in _FULL
            and operands[1].type == X.X86_OP_IMM
        ):
            new_flags = ("cmp", _FULL[operands[0].reg], operands[1].imm & _MASK)
        elif (
            mnemonic == "test" and len(operands) == 2
            and operands[0].type == operands[1].type == X.X86_OP_REG
            and operands[0].reg == operands[1].reg and operands[0].reg in _FULL
        ):
            new_flags = ("test", _FULL[operands[0].reg], 0)

        after = list(regs)
        for index in written_gprs:
            after[index] = TOP
        if exact is not None:
            after[exact[0]] = exact[1]

        if is_call:
            # The callee starts with the caller's values; afterwards only
            # the caller-saved registers and the flags are unknown.
            entry_state = (tuple(regs), None)
            for target in targets:
                work.append((target, entry_state, va))
            returned = list(regs)
            keep = frozenset()
            if len(targets) == 1 and owned(targets[0]):
                keep = preserved(targets[0])
            for index in _CALLER_SAVED:
                if index not in keep:
                    returned[index] = TOP
            work.append((va + insn.size, (tuple(returned), None), va))
            continue

        if branch and mnemonic.startswith("j") and mnemonic != "jmp":
            # A conditional jump: narrow on each side when the flags are
            # from a known comparison.
            taken_regs, fall_regs = list(regs), list(regs)
            taken_ok = fall_ok = True
            if flags is not None and (flags[0] == "cmp" or mnemonic in ("je", "jne", "jz", "jnz")):
                _, reg, imm = flags
                taken, fall = _narrow(regs[reg], mnemonic, imm)
                taken_ok, fall_ok = taken is not IMPOSSIBLE, fall is not IMPOSSIBLE
                taken_regs[reg], fall_regs[reg] = taken, fall
            if edges is not None:
                seen_edge = edges.setdefault(va, [False, False])
                seen_edge[0] = seen_edge[0] or taken_ok
                seen_edge[1] = seen_edge[1] or fall_ok
            if taken_ok:
                for target in targets:
                    work.append((target, (tuple(taken_regs), flags), va))
            if fall_ok:
                work.append((va + insn.size, (tuple(fall_regs), flags), va))
            continue

        next_state = (tuple(after), new_flags)
        for target in targets:
            work.append((target, next_state, va))
        if mnemonic in TERMINATORS:
            continue
        work.append((va + insn.size, next_state, va))

    if states is not None:
        states.update(seen_states)
    for ref in data_refs:
        obj = in_object(ref)
        if obj:
            live.update(range(obj[0], obj[0] + obj[1]))
            continue
        if ref in code_seen:
            continue
        cursor = ref
        while owned(cursor) and image[cursor - base] and cursor - ref < 512:
            live.add(cursor)
            cursor += 1
        live.update(range(ref, ref + 4))
    return image, base, live


def unreached(image, base, live, lo, hi):
    """Non-zero bytes of [lo, hi) that nothing reaches, as merged runs."""
    runs: list[list[int]] = []
    for va in range(lo, hi):
        if image[va - base] and va not in live:
            if runs and va - runs[-1][1] <= 1:
                runs[-1][1] = va + 1
            else:
                runs.append([va, va + 1])
    return [f"{a:#x}-{b:#x}" for a, b in runs]


def owned_caves(applied, owners):
    """Merged VA ranges of the applied rows `owners` wrote into zero caves.

    Rows written over stock code (a non-zero preimage) are hooks, entered by
    the game's own fall-through rather than by any reference, so they are not
    caves and are left out.
    """
    rows = []
    for row in applied:
        if row.get("owner") not in owners or not row.get("virtual_address"):
            continue
        after = bytes.fromhex(row.get("after", ""))
        before = bytes.fromhex(row.get("before", "") or "")
        if len(after) < 8 or any(before):
            continue
        va = int(row["virtual_address"], 0)
        rows.append([va, va + len(after)])
    rows.sort()
    merged: list[list[int]] = []
    for lo, hi in rows:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [tuple(r) for r in merged]
