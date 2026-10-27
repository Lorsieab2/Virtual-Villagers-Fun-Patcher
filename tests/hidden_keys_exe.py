"""Reading the stock executables for the "Hidden keys, clicks and cheats" tests (tests/test_game_mechanics_hidden_vv*.py).

keys_tested(game, start, end) lists every key a key handler of the game tests, read from the handler's own code: each
`cmp` against a command number (1000 to 1027, the translator's keys: Esc 1000 ... F10 1027) or a typed character
(32 to 126), and every case of a `switch` the compiler made into a jump table, worked out from the table itself (a
case whose entry is the table's default is not a case).  Read only."""
from __future__ import annotations

import re
import struct
from functools import lru_cache

import island_event_exe as exe_reader

COMMANDS = range(1000, 1028)
CHARACTERS = range(32, 127)


def _disasm(game: int, start: int, end: int):
    return exe_reader.exe(game).disasm(start, end)


def _imm(text: str) -> int | None:
    try:
        return int(text, 0)
    except ValueError:
        return None


def _jump_table_cases(game: int, ins: list[tuple[int, str, str]], k: int) -> set[int]:
    """The cases of the jump table whose `jmp dword ptr [reg*4 + table]` is ins[k]."""
    e = exe_reader.exe(game)
    m = re.match(r"dword ptr \[(\w+)\*4 \+ (0x[0-9a-f]+)\]", ins[k][2])
    if not m:
        return set()
    table = int(m.group(2), 16)
    index_table = None
    bound = None
    default = None
    bias = 0
    # Walk back: an optional byte index table, the bound check and its default, the bias.
    for j in range(k - 1, max(-1, k - 12), -1):
        address, mnemonic, operands = ins[j]
        if mnemonic == "movzx" and index_table is None:
            mm = re.match(r"\w+, byte ptr \[(\w+) \+ (0x[0-9a-f]+)\]", operands)
            if mm:
                index_table = int(mm.group(2), 16)
        elif mnemonic == "ja" and default is None:
            default = _imm(operands)
        elif mnemonic == "cmp" and bound is None and default is not None:
            bound = _imm(operands.split(", ")[1])
        elif bound is not None and mnemonic in ("add", "sub", "lea"):
            # index = key + add (mod 2^32), key - sub, or [reg - K]: the key is the case number plus `bias`.
            if mnemonic == "add":
                value = _imm(operands.split(", ")[1]) or 0
                bias = (-value) % 0x100000000
            elif mnemonic == "sub":
                bias = _imm(operands.split(", ")[1]) or 0
            else:
                mm = re.search(r"([+-]) (0x[0-9a-f]+)\]", operands)
                if mm:
                    bias = int(mm.group(2), 16) * (1 if mm.group(1) == "-" else -1)
            if bias >= 0x80000000:
                bias -= 0x100000000
            break
        elif bound is not None and mnemonic in ("movsx", "movzx", "mov"):
            break
    if bound is None or default is None:
        return set()
    cases = set()
    for n in range(bound + 1):
        slot = e.bytes_at(index_table + n, 1)[0] if index_table is not None else n
        target = struct.unpack("<I", e.bytes_at(table + 4 * slot, 4))[0]
        if target != default:
            cases.add(n + bias)
    return cases


@lru_cache(maxsize=None)
def keys_tested(game: int, start: int, end: int) -> frozenset[int]:
    """Every command number (1000-1027) and typed character (32-126) the code from `start` to `end` tests."""
    ins = _disasm(game, start, end)
    found: set[int] = set()
    # A chain "sub eax, 0x3fa; je ...; sub eax, 2; je ..." tests 1018, then 1020: the subtracted amount so far, per
    # register, is added to every later test of that register (reset when the register is loaded again).
    taken: dict[str, int] = {}
    for k, (address, mnemonic, operands) in enumerate(ins):
        parts = operands.split(", ")
        register = parts[0]
        if mnemonic in ("mov", "movzx", "movsx", "lea", "xor", "pop") and register in taken:
            del taken[register]
        if mnemonic == "sub" and len(parts) == 2 and _imm(parts[1]) is not None and re.fullmatch(r"e[a-d]x|e[sd]i", register):
            taken[register] = taken.get(register, 0) + _imm(parts[1])
            if ins[k + 1:k + 2] and ins[k + 1][1] in ("je", "jne", "jz", "jnz"):
                found.add(taken[register])
        elif mnemonic == "add" and len(parts) == 2 and _imm(parts[1]) is not None and register in taken:
            taken[register] -= _imm(parts[1]) if _imm(parts[1]) < 0x80000000 else _imm(parts[1]) - 0x100000000
            if ins[k + 1:k + 2] and ins[k + 1][1] in ("je", "jne", "jz", "jnz"):
                found.add(taken[register])
        elif mnemonic == "dec" and register in taken:
            taken[register] += 1
            if ins[k + 1:k + 2] and ins[k + 1][1] in ("je", "jne", "jz", "jnz"):
                found.add(taken[register])
        elif mnemonic == "cmp" and len(parts) == 2:
            value = _imm(parts[1])
            if value is None:
                continue
            value += taken.get(register, 0)
            if value in COMMANDS:
                found.add(value)
            elif value in CHARACTERS and re.match(r"(al|bl|cl|dl|byte ptr|eax|ecx|edx|ebx|esi|edi|dword ptr \[esp)", operands):
                found.add(value)
        elif mnemonic == "jmp" and "*4 +" in operands:
            found |= _jump_table_cases(game, ins, k)
    return frozenset(v for v in found if v in COMMANDS or v in CHARACTERS)


def random_picks(game: int, start: int, end: int) -> set[tuple[int, int]]:
    """Every (n, base) the code from `start` to `end` picks a string with: "push n; call rand; ...; add eax, base"."""
    out = set()
    ins = _disasm(game, start, end)
    for k, (address, mnemonic, operands) in enumerate(ins):
        if mnemonic == "push" and _imm(operands) in (30, 31, 50):
            for _a, m2, o2 in ins[k + 1:k + 8]:
                if m2 == "add" and o2.startswith("eax, ") and (_imm(o2[5:]) or 0) > 200:
                    out.add((_imm(operands), _imm(o2[5:])))
                    break
    return out


def dword_stores(game: int, start: int, end: int) -> dict[int, int]:
    """Every "mov dword ptr [reg + off], imm" from `start` to `end`: {off: imm} (the last one kept)."""
    out = {}
    for _a, mnemonic, operands in _disasm(game, start, end):
        m = re.match(r"dword ptr \[e\w\w \+ (0x[0-9a-f]+)\], (0x[0-9a-f]+|\d+)$", operands)
        if mnemonic == "mov" and m:
            out[int(m.group(1), 16)] = int(m.group(2), 0)
    return out


@lru_cache(maxsize=None)
def string_names(game: int) -> dict[int, tuple[str, str]]:
    """The Secret City to New Believers: {id: (name, text)} from the 16-byte string table (id, name, text, 0)."""
    e = exe_reader.exe(game)
    va = exe_reader.TABLES[game][0]

    def entry(v: int):
        at = e.off(v)
        if at is None:
            return None
        fields = struct.unpack_from("<4I", e.raw, at)
        name, text = e.cstring(fields[1]), e.cstring(fields[2])
        return (fields[0], name, text) if fields[0] < 0x10000 and name is not None and text is not None else None

    start = va
    while entry(start - 16):
        start -= 16
    out: dict[int, tuple[str, str]] = {}
    while (found := entry(start)) is not None:
        out.setdefault(found[0], (found[1], found[2]))
        start += 16
    return out


def fold(text: str) -> str:
    return " ".join(text.replace("\r", "").split())


@lru_cache(maxsize=None)
def commands_made(game: int, start: int, end: int) -> frozenset[int]:
    """Every command number (1000-1027) the key translator from `start` to `end` hands on: each `mov reg, imm` and
    `push imm` of one."""
    out = set()
    for address, mnemonic, operands in _disasm(game, start, end):
        if mnemonic in ("mov", "push"):
            value = _imm(operands.split(", ")[-1])
            if value in COMMANDS:
                out.add(value)
    return frozenset(out)
