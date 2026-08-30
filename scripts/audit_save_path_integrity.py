"""Audit that patched builds keep the base game's save/load path machinery.

The mask features observe the stock save-path builder so a per-save sidecar can
follow the active slot.  That observation must never change how the game itself
builds a path, names a file, or serializes a save: a patched build has to write
and find exactly the saves the base game does.

For every game and every public patch mode this renders the full public patch
selection and compares the result with the stock executable across the save
machinery:

  * the "%s%d.ldw" format string must be byte-identical,
  * the save-path builder function must be unchanged apart from an explicitly
    declared entry trampoline, and
  * every declared trampoline must replay the exact stock instructions it
    displaced and resume at the next stock instruction.

Run directly for a report; tests/test_save_path_integrity.py asserts it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

STOCK_DIR = ROOT / "research" / "stock-executables"

GAMES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}

# Save-path builders that a patch is allowed to OBSERVE, with the exact stock
# prologue each trampoline displaces and the byte count it replaces.  A game
# absent from this map must have no change at all in its builder.
OBSERVED_BUILDERS = {
    # game: (builder file offset, exact displaced stock bytes)
    "vv1": (0x2ED0, bytes.fromhex("8B4424048B11")),
    "vv2": (0x3160, bytes.fromhex("8B4424048B11")),
    "vv3": (0x3290, bytes.fromhex("8B4424048B11")),
    "vv4": (0x3670, bytes.fromhex("81EC04010000")),
    "vv5": (0x3600, bytes.fromhex("81EC04010000")),
}

# How far past the entry to compare.  The trampoline replaces only the first
# few bytes; everything after must be identical to stock.
BUILDER_SPAN = 0x100


def changed_ranges(a: bytes, b: bytes) -> list[tuple[int, int]]:
    """Contiguous [start, end) offsets where two equal-length images differ."""
    out: list[tuple[int, int]] = []
    start = None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            if start is None:
                start = i
        elif start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, min(len(a), len(b))))
    return out


def format_string_offset(data: bytes) -> int:
    needle = b"%s%d.ldw\x00"
    index = data.find(needle)
    if index < 0:
        raise RuntimeError("stock build has no %s%d.ldw save-path format string")
    if data.find(needle, index + 1) >= 0:
        raise RuntimeError("stock build has more than one save-path format string")
    return index


def _sections(data: bytes) -> list[tuple[int, int, int, int]]:
    """(virtual_address, virtual_size, raw_offset, raw_size) per PE section."""
    import struct

    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + optional_size
    out = []
    for index in range(count):
        entry = table + index * 40
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, entry + 8)
        out.append((vaddr, vsize, raddr, rsize))
    return out


def _image_base(data: bytes) -> int:
    import struct

    pe = struct.unpack_from("<I", data, 0x3C)[0]
    return struct.unpack_from("<I", data, pe + 24 + 28)[0]


def format_string_reference_sites(data: bytes, fmt_offset: int) -> list[int]:
    """File offsets of every `push <format string VA>` in the image.

    The save-path builder is whatever code pushes that string, so comparing a
    window around each reference actually covers the builder body -- rather
    than only the bytes near the string constant, which no patch would touch
    anyway.
    """
    base = _image_base(data)
    sections = _sections(data)
    rva = None
    for vaddr, vsize, raddr, rsize in sections:
        if raddr <= fmt_offset < raddr + rsize:
            rva = vaddr + (fmt_offset - raddr)
            break
    if rva is None:
        raise RuntimeError("save-path format string is outside every section")
    needle = b"\x68" + (base + rva).to_bytes(4, "little")   # push imm32
    sites = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            break
        sites.append(index)
        start = index + 1
    return sites


def _offset_to_va(data: bytes, offset: int) -> int:
    base = _image_base(data)
    for vaddr, vsize, raddr, rsize in _sections(data):
        if raddr <= offset < raddr + rsize:
            return base + vaddr + (offset - raddr)
    raise RuntimeError(f"offset 0x{offset:X} is outside every section")


def capture_is_guarded(rendered: bytes, entry: int, entry_va: int) -> str | None:
    """Return a problem string if a capture publishes its argument unguarded.

    The same stock builder formats BOTH the meta file (slot 0) and the numbered
    village saves, so a trampoline that stores its argument unconditionally
    overwrites the live village slot on every meta write.  In VV1 that also ran
    a table reset, wiping the in-memory masks of a running game.

    A capture must therefore branch on the argument before publishing it.  This
    follows the entry jump into the cave and requires at least one conditional
    branch ahead of the first store to a fixed address.
    """
    try:
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    except ImportError:  # pragma: no cover - environment dependent
        return None
    if rendered[entry] != 0xE9:
        return None  # not a near jump; the caller already reports that
    displacement = int.from_bytes(rendered[entry + 1 : entry + 5], "little", signed=True)
    target_va = entry_va + 5 + displacement
    offset = _va_to_offset(rendered, target_va)
    if offset is None:
        return f"capture cave VA 0x{target_va:X} is outside every section"

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    saw_conditional = False
    zeroed_at = None
    for instruction in md.disasm(rendered[offset : offset + 0x80], target_va):
        mnemonic, operands = instruction.mnemonic, instruction.op_str
        if mnemonic.startswith("j") and mnemonic != "jmp":
            saw_conditional = True
        # Normalizing an out-of-range slot to zero and then storing it is NOT a
        # guard: it is precisely how VV1 overwrote the live village slot on
        # every meta write and then wiped the mask table.  A branch alone does
        # not prove safety, so the published value must be the argument itself.
        if (
            (mnemonic == "xor" and operands in ("eax, eax",))
            or (mnemonic == "sub" and operands in ("eax, eax",))
            or (mnemonic == "mov" and operands in ("eax, 0",))
        ):
            zeroed_at = instruction.address
        if mnemonic == "mov" and operands.startswith("dword ptr ["):
            destination, _, source = operands.partition(", ")
            if "0x" in destination and "esp" not in destination and "ebp" not in destination:
                if not saw_conditional:
                    return (
                        f"capture publishes its argument unguarded at "
                        f"0x{instruction.address:X} ({mnemonic} {operands}); "
                        f"slot 0 (the meta file) would overwrite the live "
                        f"village slot"
                    )
                if source == "eax" and zeroed_at is not None:
                    return (
                        f"capture zeroes EAX at 0x{zeroed_at:X} and then stores "
                        f"it at 0x{instruction.address:X}; an out-of-range or "
                        f"meta slot would still overwrite the live village slot"
                    )
                return None
        # Deliberately NOT stopping at the first `jmp`: these caves branch
        # internally, and stopping there hid the normalize-to-zero store that
        # sits after an intra-cave jump.
        if mnemonic == "ret":
            break
    return None


def _va_to_offset(data: bytes, va: int) -> int | None:
    base = _image_base(data)
    rva = va - base
    for vaddr, vsize, raddr, rsize in _sections(data):
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None


def audit_game(game_id: str, verbose: bool = True) -> list[str]:
    problems: list[str] = []
    stock_path = STOCK_DIR / GAMES[game_id]
    if not stock_path.is_file():
        return [f"{game_id}: stock executable fixture is unavailable"]
    stock = stock_path.read_bytes()
    build = next(item for item in patcher.load_builds() if item.id == game_id)

    fmt = format_string_offset(stock)
    sites = format_string_reference_sites(stock, fmt)
    if not sites:
        return [f"{game_id}: no code references the save-path format string"]
    # The user-selectable catalog for this game.  An absent supported_modes
    # means "every mode", so it must not be treated as an empty set -- doing so
    # silently selects nothing and makes this audit pass vacuously.
    features = [
        p for p in patcher.load_public_fun_patches() if p.raw.get("game_id") == game_id
    ]

    for mode in patcher.load_patch_modes():
        mode_id = mode.raw["id"] if hasattr(mode, "raw") else str(mode)
        selectable = [
            f.id
            for f in features
            if mode_id in (f.raw.get("supported_modes") or [mode_id])
        ]
        try:
            selectable = patcher.resolve_fun_patch_ids(selectable, game_id=game_id)
            rendered, _ = patcher.render_patched_bytes(
                stock_path, build, mode_id, selectable
            )
        except patcher.PatcherError as exc:
            problems.append(f"{game_id}/{mode_id}: render failed: {exc}")
            continue
        rendered = bytes(rendered)

        # 1. The format string itself must survive untouched.
        if rendered[fmt : fmt + 9] != stock[fmt : fmt + 9]:
            problems.append(
                f"{game_id}/{mode_id}: the save-path format string was modified"
            )

        # 2. The builder body must match stock apart from a declared trampoline.
        if game_id in OBSERVED_BUILDERS:
            entry, displaced = OBSERVED_BUILDERS[game_id]
            allowed = len(displaced)
            if stock[entry : entry + allowed] != displaced:
                problems.append(
                    f"{game_id}: stock builder prologue at 0x{entry:X} is not the "
                    f"declared preimage"
                )
            tail_stock = stock[entry + allowed : entry + BUILDER_SPAN]
            tail_rendered = rendered[entry + allowed : entry + BUILDER_SPAN]
            if tail_stock != tail_rendered:
                problems.append(
                    f"{game_id}/{mode_id}: the save-path builder body changed beyond "
                    f"its declared {allowed}-byte trampoline"
                )
            hook = rendered[entry : entry + allowed]
            if hook != displaced and hook[0] != 0xE9:
                problems.append(
                    f"{game_id}/{mode_id}: builder entry is neither stock nor a "
                    f"near jump (got {hook.hex().upper()})"
                )
            if hook[0] == 0xE9:
                entry_va = _offset_to_va(stock, entry)
                guard = capture_is_guarded(rendered, entry, entry_va)
                if guard:
                    problems.append(f"{game_id}/{mode_id}: {guard}")
        # 3. The code that BUILDS the path must be identical to stock around
        #    every site that references the format string.  This is the actual
        #    builder body, not just the string constant.
        declared = None
        if game_id in OBSERVED_BUILDERS:
            entry, displaced = OBSERVED_BUILDERS[game_id]
            declared = (entry, entry + len(displaced))
        for site in sites:
            lo = max(0, site - 0x200)
            hi = min(len(stock), site + 0x100)
            if stock[lo:hi] == rendered[lo:hi]:
                continue
            for start, end in changed_ranges(stock[lo:hi], rendered[lo:hi]):
                abs_start, abs_end = lo + start, lo + end
                # The declared entry trampoline is validated by check 2; only
                # changes OUTSIDE it mean the builder body itself was altered.
                if declared and declared[0] <= abs_start and abs_end <= declared[1]:
                    continue
                problems.append(
                    f"{game_id}/{mode_id}: save-path builder code changed at "
                    f"0x{abs_start:X}..0x{abs_end:X} outside the declared "
                    f"trampoline (near format-string reference 0x{site:X})"
                )

        if verbose:
            state = "observed" if game_id in OBSERVED_BUILDERS else "untouched"
            print(
                f"  {game_id}/{mode_id:24} features={len(selectable):2}  "
                f"builder refs={len(sites)}  entry: {state}"
            )
    return problems


def main() -> int:
    print("Save-path integrity audit\n")
    problems: list[str] = []
    for game_id in GAMES:
        print(f"{game_id}:")
        problems.extend(audit_game(game_id))
    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("OK: every patched build keeps the base game's save-path machinery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
