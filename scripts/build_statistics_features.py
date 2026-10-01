"""Build the exact-save-hook Village Statistics feature payloads."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
OUTPUT = ROOT / "data" / "statistics_features.json"
COMPANION = ROOT / "assets" / "statistics" / "VVFP Statistics Export.dll"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


POPULATION_COMPANION = ROOT / "assets/population/VVFP Population Export.dll"

# PENDING FIELDS, NOT COUNTERS.
#
# The owner's rule: patcher-owned state lives in .dat files beside the saves,
# never in the save itself. Every counter hook below therefore increments a
# PENDING field -- scratch space inside the block the game saves and loads
# wholesale -- and the save wrapper hands the whole save to the statistics
# companion, whose PreSave adds each pending value into the slot's
# "Village Statistics - Save N.dat", ORs the pending stew bits into
# "Stew Discoveries - Save N.dat", and zeroes the pending fields before the
# stock writer runs. A saved file only ever holds zeros there.
#
# Keeping them inside the saved/loaded block is what makes a village switch
# safe: loading another village overwrites the pending area with that save's
# zeros, discarding the previous village's unsaved events exactly as the game
# discards its own unsaved progress, and each game's new-village reset zeroes
# the block too (VV1 0x41C40E rep stosd +0x9E4C..+0x9ED7, VV2 0x425210
# +0x2E528..+0x2E607, VV3 0x426450 / VV4 0x41D9D0 / VV5 0x41EBF0 the whole
# 0x98-byte live block).
#
# The fields the earlier builds counted into (VV1 +0x9E84/+0x9E88, VV2
# +0x2E5D4..+0x2E5DC, VV3 +0x38..+0x48, VV4 +0x0C/+0x3C..+0x48, VV5
# +0x0C/+0x34..+0x40) are FROZEN: nothing writes them any more, and the
# companion reads each exactly once, when the slot's .dat is first created,
# as that counter's starting total.
#
# Every pending field was verified free: zero stock references (byte search
# for the displacement or absolute address across .text), no reference in any
# rendered patch of any public feature in any mode, none in native/ or a
# shipped DLL, and none anywhere in the repository history.

GAMES = {
    "vv1": {
        "title": "Virtual Villagers - A New Home",
        "exe": "Virtual Villagers - A New Home.exe",
        "game_number": 1,
        "hook_file": 0x1BF63,
        "hook_va": 0x41BF63,
        "writer_va": 0x403160,
        "cave_file": 0x56730,
        "cave_va": 0x456730,
        "cave_size": 0xD0,
        "load_library_iat": 0x457010,
        "get_module_handle_iat": 0x4570D0,
        "get_proc_address_iat": 0x4570D4,
        "burial_hook_va": 0x448F65,
        "burial_guard": "C644392800",
        "burial_manager": "mov eax, dword ptr [edi + 0x3E010]",
        "burial_stat_offset": 0x9E9C,  # pending (old field +0x9E84 frozen)
        "burial_replay": "mov byte ptr [ecx + edi + 0x28], 0",
    },
    "vv2": {
        "title": "Virtual Villagers - The Lost Children",
        "exe": "Virtual Villagers - The Lost Children.exe",
        "game_number": 2,
        "hook_file": 0x24BF3,
        "hook_va": 0x424BF3,
        "writer_va": 0x4033F0,
        "cave_file": 0x73E50,
        "cave_va": 0x473E50,
        "cave_size": 0xD0,
        "load_library_iat": 0x474010,
        "get_module_handle_iat": 0x4740D0,
        "get_proc_address_iat": 0x4740D4,
        "burial_hook_va": 0x46503B,
        "burial_guard": "C644323000",
        "burial_manager": "mov eax, dword ptr [esi + 0xE574D4]",
        "burial_stat_offset": 0x2E5E0,  # pending (old field +0x2E5D4 frozen)
        "burial_replay": "mov byte ptr [edx + esi + 0x30], 0",
        # Counted in two parts, because The Lost Children's childbirth is
        # cumulative rather than exclusive: the twins branch sets litter 2 and
        # falls THROUGH into the triplet test, which may overwrite it with 3.
        #
        # 0x44BA8C, the instruction after the twins branch, is reached by every
        # multiple birth and by nothing else -- the saturation guard detours
        # the branch itself and rejoins here only when it allows the birth. So
        # it counts twins and triplets alike.
        #
        # 0x44BAD2 is the stock triplets increment, reached only once a birth
        # has actually been promoted to triplets. Decrementing the twins
        # counter there removes exactly the births the first hook
        # over-counted, leaving twins counting twins only, matching the
        # mutually exclusive behaviour of the later games.
        #
        # The epilogue at 0x44BAD8 would have been simpler but the parentage
        # feature already detours it, and two features cannot own one address.
        "twins_hook_va": 0x44BA8C,
        "twins_guard": "8B87D474E500",
        "twins_wrapper_va": 0x473DF4,
        "twins_manager": "mov eax, dword ptr [edi + 0xE574D4]",
        "twins_stat_offset": 0x2E5E4,  # pending (old field +0x2E5D8 frozen)
        "twins_resume_va": 0x44BA92,
        # The correcting decrement on the triplet path. edi is already the
        # manager here (0x44BACC loads it), so no extra load is needed.
        "triplet_hook_va": 0x44BAD2,
        "triplet_guard": "FF8724E50200",
        # At the END of the 106-byte run at 0x473F96, not its start, so the
        # longest contiguous zero run in this section stays as large as
        # possible for publish-time name-crash immunity.
        "triplet_wrapper_va": 0x473FED,
        "triplet_body": "dec dword ptr [edi + 0x2E5E4]",
        "triplet_replay": "inc dword ptr [edi + 0x2E524]",
        # Total Stews Found. sub_425B90 is the cook routine: ECX is the
        # manager, and the three herb slots +0x3043C/+0x30440/+0x30444 hold
        # herb ids 0x30..0x35 -- written only by the six herb-drop handlers in
        # the dispatcher 0x461B10, each into an EMPTY slot, and cleared only at
        # this routine's own end (0x4260E2) -- and all seven of its callers sit
        # in that dispatcher, each after the pot is full. Every stew the game
        # makes passes here, including the ones the Special Stews logic skips.
        # Its recipe test 0x425B60 COUNTS occurrences of a herb across the
        # three slots, so ingredient order does not matter to the game; the
        # hook records the ORDERED triple ((h1*6)+h2)*6+h3 and the companion
        # normalises it to the sorted multiset.
        "stew": {
            "hook_va": 0x425B90,
            # push ebp ; push esi ; push edi ; mov esi, ecx ; xor edi, edi
            "guard": "5556578BF133FF",
            "manager_reg": "ecx",
            "slots": (0x3043C, 0x30440, 0x30444),
            "first_herb": 0x30,
            "herb_count": 6,
            # Pending ordered-triple bits, 216 of them, at manager+0x2E5E8..
            # +0x2E602 (27 bytes; +0x2E5E0/+0x2E5E4 are the pending burial and
            # twins counters). Inside the saved extent and zeroed by the
            # new-village reset 0x425210.
            "bits": 0x2E5E8,
            # The Lost Children has no free contiguous run for this routine:
            # its statistics cave is full and its one large zero run (0x73F42)
            # belongs to the publish-time crash-immunity wrapper. So the
            # routine is laid over NOP padding between functions -- each run
            # follows a `ret`, is the target of no branch, is stock 0x90, and
            # is claimed by no public feature in any mode -- chained with
            # jumps. The publish-time cave finder takes only zero runs, so it
            # can never reuse these.
            "runs": (
                (0x4255D3, 13), (0x425A83, 13), (0x425B53, 13),
                (0x426113, 13), (0x426153, 13), (0x4261C2, 14),
                (0x426282, 14), (0x4262A3, 13), (0x4262C3, 13),
                (0x426691, 15), (0x426EA2, 14), (0x4272B3, 13),
            ),
        },
    },
    "vv3": {
        "title": "Virtual Villagers - The Secret City",
        "exe": "Virtual Villagers - The Secret City.exe",
        "game_number": 3,
        "hook_file": 0x27D6C,
        "hook_va": 0x427D6C,
        "writer_va": 0x403530,
        "cave_file": 0x7B464,
        "cave_va": 0x47B464,
        "cave_size": 0x200,
        "load_library_iat": 0x47C124,
        "get_module_handle_iat": 0x47C074,
        "get_proc_address_iat": 0x47C128,
        "burial_hook_va": 0x462293,
        "burial_guard": "C687100F000000",
        "burial_replay": "mov byte ptr [edi + 0xF10], 0",
        # +0x30 (0x5824D0) is the Origins doubler ownership bitmask, whose
        # bits 0 and 1 mark the Tech and Food Doublers owned. Incrementing it
        # per pickup would grant doublers and be reset by Origins purchases,
        # so this and its marker start at +0x38.
        "burial_stat_va": 0x5824EC,  # pending +0x4C (old +0x38 frozen)
        # The robing routine sub_45FBC0, whose first instruction loads the
        # villager record. It is the ONLY writer of the chief flag +0xE80 in
        # the image, and its single caller sub_431FE0 is the ceremony -- which
        # goes on to call the puzzle-progress routine at 0x432042, so the
        # puzzle is downstream of robing and a hook here catches the
        # replacement chiefs the puzzle never fires for.
        "robing_hook_va": 0x45FBC0,
        "robing_guard": "8B4424048B88740E0000",
        # +0x38/+0x3C are burials and their marker, +0x40 the death counter,
        # so the next free per-save reserve dword is +0x44.
        "robing_stat_va": 0x5824F4,  # pending +0x54 (old +0x44 frozen)
        # One-time seed marker for the robing counter, at +0x48. A save
        # created before the hook existed has had chiefs the counter never
        # saw, so the raw counter would read 0 for a village that plainly
        # has a chief. Gated on a dedicated marker rather than on the
        # counter being zero, because a genuine new village with no chief
        # yet is indistinguishable from an unseeded one by value alone.
        "robing_marker_va": 0x5824E8,
        # Every death in this game routes through one of two sibling health
        # arbiters. The proof they are the sole arbiter rather than one path
        # among several is that the ALIVE path explicitly writes -1 to the
        # cause field (0x4626DF, 0x462698): a living villager always has
        # cause -1 and a dead one a real cause id, which is also what makes
        # the count idempotent. The branch above each site tests the
        # RESULTING health, not the prior, so calling either again on an
        # already-dead villager re-enters the death path; testing the cause
        # for -1 counts the transition exactly once.
        "death_stat_va": 0x5824F0,  # pending +0x50 (old +0x40 frozen)
        "death_cause_offset": 0x10,
        "death_hooks": [
            {"hook_va": 0x4626C6, "guard": "C7410C00000000", "slot": 0x1A8},
            {"hook_va": 0x46267F, "guard": "C7410C00000000", "slot": 0x1C8},
        ],
        # Stews Found: the Alchemy Lab potions. sub_430A50 is the brew: it
        # rolls rand(100) against the brewer's odds and on failure (0x430A9C
        # jle) the potion blows up and it never reaches 0x430AAC. On success
        # 0x430AAC -- the ONLY caller of sub_430510 -- passes the three herbs
        # (pot+8, +0xC, +0x10) as stack arguments with ECX = the recipe
        # object. Herbs are 0x1F..0x25 (seven, including the faction herbs):
        # the recipe key 0x430270 indexes a seven-counter array by herb-0x1F
        # and packs the COUNTS, so order does not matter to the game.
        "stew": {
            "hook_va": 0x430510,
            # push ebx ; mov ebx, [esp+0xC]
            "guard": "538B5C240C",
            "stack_args": True,
            "first_herb": 0x1F,
            "herb_count": 7,
            # 343 pending ordered-triple bits at live +0x58..+0x82.
            "bits_va": 0x5824F8,
            # Free gap after the robing wrapper (0xB4..0xC8) and before the
            # burial wrapper (0x190).
            "slot": 0xCC,
        },
    },
    "vv4": {
        "title": "Virtual Villagers - The Tree of Life",
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "game_number": 4,
        "hook_file": 0x1F13A,
        "hook_va": 0x41F13A,
        "writer_va": 0x4039B0,
        "cave_file": 0x89173,
        "cave_va": 0x489173,
        "cave_size": 0x200,
        "load_library_iat": 0x48A1E0,
        "get_module_handle_iat": 0x48A1D8,
        "get_proc_address_iat": 0x48A1DC,
        "food_hook_va": 0x41D987,
        "food_stat_va": 0x4D6E3C,  # pending +0x5C (old +0x0C frozen)
        "burial_hook_va": 0x46A977,
        "burial_guard": "C686C41C000000",
        "burial_replay": "mov byte ptr [esi + 0x1CC4], 0",
        # +0x30 (0x4D6E10) is the Origins doubler ownership bitmask; see the
        # VV3 note. Burial counter and marker take +0x3C and +0x40.
        "burial_stat_va": 0x4D6E30,  # pending +0x50 (old +0x3C frozen)
        # Village Elders: no burial hook. An earlier revision stored its own
        # elder verdict in grave byte +0x37, but the burial writer stores the
        # dword [villager+0x1C44] at grave+0x34 (0x45D524) right after, so the
        # byte never held the verdict; and a one-time seed that set it pushed
        # +0x34 outside the -1..4 range the memorial loader 0x45D6E0 accepts,
        # which rejects the whole memorial. Elders are now tracked in a
        # per-save .dat file by the statistics companion instead (the owner:
        # "if the game doesn't keep track of it, make a .dat file").
        # Debris is not discrete pieces -- the stream carries an obstruction
        # level at debris-manager +0x14 that each clearing action decrements
        # by one. The game's own unit for that action is the Civil Engineer
        # trophy's ("You kept 1000 units of debris from building up"), which
        # this same instruction credits one unit to on the very next lines.
        # The trophy's progress field stops accruing once earned, so it cannot
        # serve as the lifetime total itself; this counts the same event
        # without the cap.
        "debris_hook_va": 0x43965A,
        "debris_guard": "834614FF6A01",
        # Two whole instructions, because the first is only four bytes and a
        # five-byte jump cannot replace it alone. Nothing branches between
        # them: the jnz above targets 0x4396A1, outside the range.
        "debris_replay": (
            "add dword ptr [esi + 0x14], -1 ; push 1"
        ),
        "debris_stat_va": 0x4D6E38,  # pending +0x58 (old +0x44 frozen)
        # 0x190 holds the burial wrapper (18 bytes, ends 0x1A2).
        "debris_slot": 0x1A8,
        # Every death in this game routes through one of two sibling health
        # arbiters, exactly as in The Secret City and New Believers. What
        # proves they are the sole arbiter rather than one path among several
        # is that the ALIVE path explicitly writes -1 to the cause field
        # (0x46AF28, 0x46AF6B): a living villager always carries -1 and a dead
        # one a real cause id.
        #
        # That is also what makes the count idempotent. The branch above each
        # hook tests the RESULTING health, not the prior, so calling either
        # routine again on an already-dead villager re-enters the death path;
        # testing the cause for -1 counts the transition exactly once.
        #
        # The ordering is load-bearing and reads as incidental: each hook site
        # is the health-zeroing store, which runs BEFORE the cause write two
        # instructions later (0x46AF0F -> 0x46AF16, 0x46AF52 -> 0x46AF59). At
        # hook time the cause field therefore still holds the PRIOR value. A
        # hook placed after the cause write would see the new cause every time
        # and count nothing at all.
        #
        # +0x48, not the +0x40 the other two games use: +0x40 is this game's
        # burial marker. The reserve layouts are not parallel across games.
        # Stock code touches this block only up to +0x2C, so +0x48 is free of
        # both stock use and every other patch.
        "death_stat_va": 0x4D6E34,  # pending +0x54 (old +0x48 frozen)
        "death_cause_offset": 0x10,
        "death_hooks": [
            # 0x46AF00 sets health absolutely; 0x46AF40 applies a delta with
            # `add [ecx+0xC], eax`, so a death by cumulative damage passes
            # only through the second. Hooking one alone would miss it.
            {"hook_va": 0x46AF0F, "guard": "C7410C00000000", "slot": 0x1C8},
            {"hook_va": 0x46AF52, "guard": "C7410C00000000", "slot": 0x1E0},
        ],
        # Stews Found. The CAlchemyPot brew 0x42EDE0 looks the herbs
        # (pot+0xC/+0x10/+0x14, 0x1F..0x22: spicy, sweet, soapy, pulpy vines)
        # up, then 0x42DC80 decides success. 0x22 is also the item the cloth
        # vine-cutter carries (job 0x7A, 0x436B98 push 0x22 ; call 0x4697C0):
        # the game has one pulpy-vine item, so vines dropped on the herb pile
        # for cloth, and any stew mixing them with other herbs, are recorded
        # like every other stew (tests/test_unique_stews.py
        # TreeOfLifeVineStewTests). Failure returns at 0x42EE43;
        # success always reaches 0x42EE5F (directly, or after the brewer's
        # animation at 0x42EE48), where the pot clears flag 0x18 and the two
        # water flags -- 9 (fresh, byte 0x704EEC) at 0x42EE6B and 0xA (salt,
        # byte 0x704F00) at 0x42EE77. The hook runs BEFORE those clears, so
        # the water type is still readable. The recipe lookup 0x42DBF0 keys
        # on the herb counts, and its fallback 0x42ECA0 makes the result salty
        # exactly when flag 0xA is set, which is the rule recorded here.
        "stew": {
            "hook_va": 0x42EE5F,
            # push 0x18 ; mov ecx, 0x705148
            "guard": "6A18B948517000",
            "pot_reg": "esi",
            "slots": (0xC, 0x10, 0x14),
            "first_herb": 0x1F,
            "herb_count": 4,
            "salt_flag_va": 0x704F00,
            # 128 pending bits (64 ordered triples x fresh/salt) at live
            # +0x60..+0x6F.
            "bits_va": 0x4D6E40,
            # Free gap after the food wrapper (0xD0), before the burial
            # wrapper (0x190).
            "slot": 0xEC,
        },
    },
    "vv5": {
        "title": "Virtual Villagers - New Believers",
        "exe": "Virtual Villagers - New Believers.exe",
        "game_number": 5,
        "hook_file": 0x245FA,
        "hook_va": 0x4245FA,
        "writer_va": 0x403940,
        "cave_file": 0x94932,
        "cave_va": 0x494932,
        "cave_size": 0x200,
        "load_library_iat": 0x4951E0,
        "get_module_handle_iat": 0x4951D8,
        "get_proc_address_iat": 0x4951DC,
        "food_hook_va": 0x41EBA7,
        "food_stat_va": 0x51D3A8,  # pending +0x50 (old +0x0C frozen)
        "conversion_hook_va": 0x4668B0,
        "conversion_stat_va": 0x51D3A4,  # pending +0x4C (old +0x34 frozen)
        "burial_hook_va": 0x473F8F,
        "burial_guard": "C686D41C000000",
        "burial_replay": "mov byte ptr [esi + 0x1CD4], 0",
        # +0x30 holds the Origins saved bit flags and +0x34 the Heathens
        # Converted total, so this game's first free reserve dword is +0x38.
        "burial_stat_va": 0x51D39C,  # pending +0x44 (old +0x38 frozen)
        # Same two-arbiter shape as The Secret City; see that note.
        "death_stat_va": 0x51D3A0,  # pending +0x48 (old +0x40 frozen)
        "death_cause_offset": 0x10,
        "death_hooks": [
            {"hook_va": 0x475902, "guard": "C7410C00000000", "slot": 0x1A8},
            {"hook_va": 0x4758BF, "guard": "C7410C00000000", "slot": 0x1C8},
        ],
    },
}


def assemble(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


_JCC_REL32 = {"ja": b"\x0F\x87", "jb": b"\x0F\x82", "je": b"\x0F\x84", "jne": b"\x0F\x85"}


def chain_assemble(
    items: list[tuple[str, ...]],
    runs: tuple[tuple[int, int], ...],
) -> list[tuple[int, bytes]]:
    """Lay a routine over several separate padding runs, joined by jumps.

    `items` is a list of ("asm", text), ("label", name) and ("jcc", cc, name)
    entries. Conditional branches to a label are always encoded rel32, so
    every item's size is fixed before any address is known and one layout
    pass determines every label. An item is placed in the current run only
    if it still leaves five bytes for the jump to the next run, except the
    last item, which must itself end the flow (the jump back into the game).
    Returns the (va, bytes) actually written in each run used.
    """
    def place(labels: dict[str, int] | None) -> tuple[list[tuple[int, bytes]], dict[str, int]]:
        found: dict[str, int] = {}
        pieces: list[tuple[int, bytearray]] = []
        run_index = 0
        cursor = runs[0][0]
        pieces.append((cursor, bytearray()))
        for position, item in enumerate(items):
            last = position == len(items) - 1
            if item[0] == "label":
                found[item[1]] = cursor
                continue
            if item[0] == "jcc":
                size = 6
            else:
                size = len(assemble(item[1], cursor))
            end = runs[run_index][0] + runs[run_index][1]
            if cursor + size + (0 if last else 5) > end:
                run_index += 1
                if run_index >= len(runs):
                    raise RuntimeError("routine does not fit the padding runs")
                pieces[-1][1].extend(rel32_jump(cursor, runs[run_index][0]))
                cursor = runs[run_index][0]
                pieces.append((cursor, bytearray()))
                end = runs[run_index][0] + runs[run_index][1]
                if cursor + size + (0 if last else 5) > end:
                    raise RuntimeError("an instruction is larger than a padding run")
            if item[0] == "jcc":
                target = (labels or {}).get(item[2], cursor)
                encoded = _JCC_REL32[item[1]] + int(target - cursor - 6).to_bytes(
                    4, "little", signed=True)
            else:
                encoded = assemble(item[1], cursor)
            if len(encoded) != size:
                raise RuntimeError("instruction size changed between passes")
            pieces[-1][1].extend(encoded)
            cursor += size
        return [(va, bytes(blob)) for va, blob in pieces if blob], found

    _, labels = place(None)
    placed, again = place(labels)
    if again != labels:
        raise RuntimeError("chain layout did not converge")
    return placed


def stew_routine(stew: dict[str, object]) -> list[tuple[str, ...]]:
    """The stew-completion hook body, as chain_assemble items.

    Records the ORDERED herb triple in a pending bitset:
        index = ((h1 * n) + h2) * n + h3,   h = herb - first_herb, n = herb_count
    and for The Tree of Life additionally `index * 2 + salt`. Each herb is
    range-checked first, so a value the game never produces cannot set a bit
    outside the bitset; nothing is recorded then. The companion normalises
    each ordered triple to its sorted multiset when it flushes the bits into
    the .dat, because every one of these games matches recipes on herb
    COUNTS, not order.

    pushfd/pushad around the body restore every register and flag, and the
    stolen instruction(s) are replayed verbatim before jumping back.
    """
    first = int(stew["first_herb"])
    count = int(stew["herb_count"])
    if stew.get("stack_args"):
        # At entry [esp+4..0xC] are the three herbs; pushfd + pushad move
        # them up by 0x24.
        sources = ["dword ptr [esp + 0x28]", "dword ptr [esp + 0x2C]", "dword ptr [esp + 0x30]"]
    else:
        base = str(stew.get("manager_reg") or stew.get("pot_reg"))
        sources = [f"dword ptr [{base} + 0x{int(o):X}]" for o in stew["slots"]]
    items: list[tuple[str, ...]] = [("asm", "pushfd"), ("asm", "pushad")]
    for position, source in enumerate(sources):
        register = "eax" if position == 0 else "edx"
        items += [
            ("asm", f"mov {register}, {source}"),
            ("asm", f"sub {register}, 0x{first:X}"),
            ("asm", f"cmp {register}, {count - 1}"),
            ("jcc", "ja", "stew_done"),
        ]
        if position:
            items += [("asm", f"imul eax, eax, {count}"), ("asm", "add eax, edx")]
    if stew.get("salt_flag_va"):
        items += [
            ("asm", "xor edx, edx"),
            ("asm", f"cmp byte ptr [0x{int(stew['salt_flag_va']):X}], 0"),
            ("asm", "setne dl"),
            ("asm", "lea eax, [edx + eax*2]"),
        ]
    if stew.get("bits_va"):
        items.append(("asm", f"bts dword ptr [0x{int(stew['bits_va']):X}], eax"))
    else:
        items.append(
            ("asm", f"bts dword ptr [{stew['manager_reg']} + 0x{int(stew['bits']):X}], eax"))
    items += [("label", "stew_done"), ("asm", "popad"), ("asm", "popfd")]
    guard = bytes.fromhex(str(stew["guard"]))
    items += [("asm", ".byte " + ", ".join("0x%02X" % b for b in guard))]
    items.append(("asm", "jmp 0x%X" % (int(stew["hook_va"]) + len(guard))))
    return items


# New Believers keeps its Heathens in the same villager array as the tribe.
# The record's faction byte +0x1CEC is 0 for a believer and nonzero for a
# Heathen: the game's own population count 0x4713F0 counts only records whose
# byte is 0, the conversion routine 0x4668B0 clears it (0x46697D), and the
# events that turn a believer into a Heathen set it (0x415D0C, 0x416C5B).
#
# THE OWNER (2026-09-30): Heathens never count as villagers anywhere in the
# statistics log unless a row explicitly asks for them; a converted Heathen
# counts like any villager from the moment of conversion, never before. These
# are the stock counters that could credit a Heathen, each guarded on that
# byte at the moment the stock code counts. Every other row was traced and
# needs no guard (see docs/village-statistics-verification.md).
VV5_FACTION = 0x1CEC
VV5_BELIEVER_GUARDS = (
    # Oldest Villager. The per-villager update 0x46FE90 skips AGING for a
    # Heathen (0x470077 cmp [esi+0x1CEC],bl / jne 0x47008D) but then falls
    # into the Oldest Villager maximum at 0x47008D regardless -- so a Heathen
    # spawned at internal age 1000 set the row to 50 on a new village's first
    # frame (observed live, v1.35.41). Retargeting that jne past the maximum
    # (0x4700B9, where both paths rejoin) keeps the Heathen unaged exactly as
    # before and leaves the maximum to believers.
    {
        "va": 0x47007F,
        "before": "750C",
        "after": "7538",
        "purpose": (
            "Oldest Villager: a Heathen, which the game already never ages, "
            "no longer enters the Oldest Villager maximum either"
        ),
    },
)


def vv5_believers_only(
    source: bytes,
    payload: bytearray,
    cave_va: int,
    cave_size: int,
) -> list[dict[str, object]]:
    """New Believers: the statistics counters that could credit a Heathen.

    Each detour is a whole stolen instruction (or pair) replaced by a jump and
    NOPs; each wrapper tests the faction byte and either counts exactly as the
    stock instruction did or skips only the count, then resumes where the stock
    instruction would have continued. No wrapper writes a register.
    """
    patches: list[dict[str, object]] = []
    for guard in VV5_BELIEVER_GUARDS:
        site = int(guard["va"]) - 0x400000
        before = bytes.fromhex(str(guard["before"]))
        if source[site : site + len(before)] != before:
            raise RuntimeError(f"vv5 guard at {guard['va']:#x} does not match")
        patches.append({
            "offset": f"0x{site:X}",
            "before": before.hex().upper(),
            "after": str(guard["after"]),
            "purpose": str(guard["purpose"]),
        })

    def place(slot: int, source_text: str, limit: int) -> int:
        wrapper = assemble(source_text, cave_va + slot)
        if slot + len(wrapper) > limit or slot + len(wrapper) > cave_size:
            raise RuntimeError(f"vv5 believer wrapper at cave+{slot:#x} overruns its gap")
        if any(payload[slot : slot + len(wrapper)]):
            raise RuntimeError(f"vv5 believer wrapper at cave+{slot:#x} would overwrite the cave")
        payload[slot : slot + len(wrapper)] = wrapper
        return cave_va + slot

    def detour(site_va: int, stolen_hex: str, wrapper_va: int, purpose: str) -> None:
        site = site_va - 0x400000
        stolen = bytes.fromhex(stolen_hex)
        if source[site : site + len(stolen)] != stolen:
            raise RuntimeError(f"vv5 detour site {site_va:#x} does not match")
        patches.append({
            "offset": f"0x{site:X}",
            "before": stolen.hex().upper(),
            "after": (rel32_jump(site_va, wrapper_va)
                      + b"\x90" * (len(stolen) - 5)).hex().upper(),
            "purpose": purpose,
        })

    # People Cured, the drag-a-healer cure 0x468C10 (the auto-cure 0x46E020
    # picks its patient through 0x470B40, which already requires +0x1CEC == 0).
    # Its patient finder 0x4706F0 has no faction test, and a Heathen reaches it
    # in play two ways: The Missing Kids' bad outcome (0x416120) makes its
    # second child -- picked Heathen-only at 0x415E80 -- sick, and the purple
    # Heathen (+0x1CFC == 12) is cured without being sick, which is also how it
    # is converted (0x468D0D, before the +1 at 0x468D4D). The faction is
    # therefore captured when the cure BEGINS, at the sickness test 0x468C3C
    # (reached only with a patient), into the local dword [esp+0x18]: the
    # second half of the position the routine passed by value to 0x4706F0 and
    # never reads again. push/pop move the whole dword without a register.
    # Every path from there to the +1 is balanced (each callee cleans its own
    # arguments), so [esp+0x18] addresses the same slot at 0x468D4D.
    capture_va = place(0xEC, """
        push dword ptr [esi + 0x1CEC]
        pop dword ptr [esp + 0x18]
        cmp byte ptr [esi + 0x1C48], bl
        jne 0x468C61
        jmp 0x468C44
    """, 0x108)
    detour(0x468C3C, "389E481C0000751D", capture_va,
           "People Cured: note whether the healer's patient was a Heathen when "
           "the cure began, then run the stock sickness test unchanged")
    cured_va = place(0xB4, """
        cmp byte ptr [esp + 0x18], 0
        jne heathen_patient
        add dword ptr [0x51D368], 1
    heathen_patient:
        jmp 0x468D54
    """, 0xD0)
    detour(0x468D4D, "830568D3510001", cured_va,
           "People Cured: a patient who was a Heathen when the cure began is "
           "not counted; a believer, or a converted Heathen, counts as before")

    # Babies Made, Twins Birthed, Triplets Birthed: all counted inside the
    # conception routine 0x465E00 (ESI = the mother), which has no faction
    # test and is reached with a Heathen mother by Abandoned Infants
    # (0x471A50 picks every living woman) and by a believer paired with a
    # Heathen through the partner finder 0x4705D0. Each +1 is guarded on the
    # mother. The saturation guards (0x465F10/0x465F23) resume at the first
    # two of these sites and the parentage trampoline at the third, so each is
    # still entered exactly where they expect.
    triplets_va = place(0x108, """
        cmp byte ptr [esi + 0x1CEC], 0
        jne heathen_mother
        add dword ptr [0x51D384], 1
    heathen_mother:
        jmp 0x465F21
    """, 0x130)
    detour(0x465F1A, "830584D3510001", triplets_va,
           "Triplets Birthed: a Heathen mother's triplets are not counted")
    twins_va = place(0x154, """
        cmp byte ptr [esi + 0x1CEC], 0
        jne heathen_mother
        add dword ptr [0x51D380], 1
    heathen_mother:
        jmp 0x465F34
    """, 0x190)
    detour(0x465F2D, "830580D3510001", twins_va,
           "Twins Birthed: a Heathen mother's twins are not counted")
    babies_va = place(0x16C, """
        cmp byte ptr [esi + 0x1CEC], 0
        jne heathen_mother
        add dword ptr [0x51D360], ecx
    heathen_mother:
        jmp 0x465F44
    """, 0x190)
    detour(0x465F3E, "010D60D35100", babies_va,
           "Babies Made: a Heathen mother's babies are not counted")
    return patches


def build_game(
    game_id: str,
    config: dict[str, object],
    companion_hash: str,
    population_hash: str,
) -> dict:
    source = (STOCK / str(config["exe"])).read_bytes()
    cave_file = int(config["cave_file"])
    cave_va = int(config["cave_va"])
    cave_size = int(config["cave_size"])
    dll_name_va = cave_va + 0x80
    export_name_va = cave_va + 0x9C

    # The full-save wrapper. It replaces the stock `call writer` at the save
    # routine's primary-slot save, where EDI holds the slot and ECX the
    # manager, and the three stack arguments are the buffer, its size and the
    # slot.
    #
    # For a primary slot (1..5) whose companion resolves, the whole save goes
    # through SaveVillageStatistics(game, manager, slot, writer, buffer, size):
    # the companion first FLUSHES the patch's pending counters and stew bits
    # into that slot's .dat files and zeroes them in memory -- so the stock
    # writer, which it then calls with the original arguments, saves only
    # zeros in those fields and nothing patcher-owned persists in the save --
    # and after a successful save writes the statistics log. The writer's
    # result is returned unchanged in EAX.
    #
    # Any other slot (the meta save 0 and the +0x14 backup copies), or a
    # missing companion or export, calls the stock writer directly with the
    # original arguments, so a save never depends on the companion.
    code = assemble(
        f"""
            push ebx
            mov ebx, ecx
            cmp edi, 1
            jl direct
            cmp edi, 5
            jg direct
            push 0x{dll_name_va:X}
            call dword ptr [0x{int(config['get_module_handle_iat']):X}]
            test eax, eax
            jne resolve_export
            push 0x{dll_name_va:X}
            call dword ptr [0x{int(config['load_library_iat']):X}]
            test eax, eax
            jz direct
        resolve_export:
            push 0x{export_name_va:X}
            push eax
            call dword ptr [0x{int(config['get_proc_address_iat']):X}]
            test eax, eax
            jz direct
            push dword ptr [esp + 0xC]
            push dword ptr [esp + 0xC]
            push 0x{int(config['writer_va']):X}
            push edi
            push ebx
            push {int(config['game_number'])}
            call eax
            pop ebx
            ret 0x0C
        direct:
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            mov ecx, ebx
            call 0x{int(config['writer_va']):X}
            pop ebx
            ret 0x0C
        """,
        cave_va,
    )
    if len(code) > 0x80:
        raise RuntimeError(f"{game_id} wrapper exceeds code allowance: {len(code):#x}")
    payload = bytearray(cave_size)
    payload[: len(code)] = code
    dll_name = b"VVFP Statistics Export.dll\0"
    export_name = b"SaveVillageStatistics\0"
    payload[0x80 : 0x80 + len(dll_name)] = dll_name
    payload[0x9C : 0x9C + len(export_name)] = export_name
    extra_patches: list[dict[str, object]] = []

    food_hook_va = config.get("food_hook_va")
    if food_hook_va:
        food_wrapper_va = cave_va + 0xD0
        food_wrapper = assemble(
            f"""
                test esi, esi
                jle no_food_count
                add dword ptr [0x{int(config['food_stat_va']):X}], esi
            no_food_count:
                add dword ptr [edi], esi
                mov eax, dword ptr [edi]
                jns nonnegative_food
                jmp 0x{int(food_hook_va) + 6:X}
            nonnegative_food:
                jmp 0x{int(food_hook_va) + 0x11:X}
            """,
            food_wrapper_va,
        )
        if 0xD0 + len(food_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} food wrapper exceeds cave allowance")
        payload[0xD0 : 0xD0 + len(food_wrapper)] = food_wrapper
        food_hook_file = int(food_hook_va) - 0x400000
        food_guard = bytes.fromhex("01378B07790B")
        if source[food_hook_file : food_hook_file + 6] != food_guard:
            raise RuntimeError(f"{game_id} central food hook guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{food_hook_file:X}",
                "before": food_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(food_wrapper_va - int(food_hook_va) - 5).to_bytes(
                        4, "little", signed=True
                    )
                    + b"\x90"
                ).hex().upper(),
                "purpose": (
                    "restore the inherited Food Gathered counter for every final "
                    "positive food award while preserving stock underflow handling"
                ),
            }
        )

    conversion_hook_va = config.get("conversion_hook_va")
    if conversion_hook_va:
        conversion_wrapper_va = cave_va + 0x130
        conversion_wrapper = assemble(
            f"""
                cmp dword ptr [ecx + 0x1CFC], 17
                jne ordinary_conversion
                add dword ptr [0x{int(config['conversion_stat_va']):X}], 2
                jmp conversion_counted
            ordinary_conversion:
                inc dword ptr [0x{int(config['conversion_stat_va']):X}]
            conversion_counted:
                sub esp, 0x10
                push esi
                mov esi, ecx
                jmp 0x{int(conversion_hook_va) + 6:X}
            """,
            conversion_wrapper_va,
        )
        if 0x130 + len(conversion_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} conversion wrapper exceeds cave allowance")
        payload[0x130 : 0x130 + len(conversion_wrapper)] = conversion_wrapper
        conversion_hook_file = int(conversion_hook_va) - 0x400000
        conversion_guard = bytes.fromhex("83EC10568BF1")
        if (
            source[
                conversion_hook_file :
                conversion_hook_file + len(conversion_guard)
            ]
            != conversion_guard
        ):
            raise RuntimeError(f"{game_id} conversion hook guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{conversion_hook_file:X}",
                "before": conversion_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(
                        conversion_wrapper_va - int(conversion_hook_va) - 5
                    ).to_bytes(4, "little", signed=True)
                    + b"\x90"
                ).hex().upper(),
                "purpose": (
                    "count every completed Heathen conversion once in the "
                    "per-save reserve, counting the tag-17 Heathen Mommy as two"
                ),
            }
        )

    robing_hook_va = config.get("robing_hook_va")
    if robing_hook_va:
        # Chiefs Robed, as a LIFETIME total rather than a roster snapshot.
        #
        # A walk of living villagers carrying the chief flag reports the
        # chiefs a village holds NOW, so it falls back to 1 -- or 0 -- as
        # chiefs die and are replaced, and the requirements forbid exactly
        # that: lifetime totals "must not be reconstructed only from current
        # village state when that would lose historical events".
        #
        # This hook sits on the robing routine's first instruction, which is
        # the single place the chief flag is ever written, so every robing is
        # counted once and no replacement is missed. The two displaced
        # instructions are replayed before returning to the stock body.
        #
        # 0xB4 is the first 4-byte-aligned free byte after the export name.
        # That name is "WriteVillageStatistics" plus a NUL at 0x9C -- 23 bytes, so it
        # occupies 0x9C..0xB2 INCLUSIVE and its terminator lives at 0xB2.
        # Starting at 0xB2 overwrites that NUL, leaving the name unterminated
        # so GetProcAddress reads past it and the companion is never found;
        # tests/test_patcher.py catches exactly that. Scanning the built
        # payload for zero runs cannot distinguish a terminator from a gap,
        # which is how the wrong offset was picked the first time.
        # The burial wrapper sits at 0x190, so 0xB4..0x18F is the usable gap.
        robing_wrapper_va = cave_va + 0xB4
        robing_wrapper = assemble(
            f"""
                inc dword ptr [0x{int(config['robing_stat_va']):X}]
                mov eax, [esp + 4]
                mov ecx, [eax + 0xE74]
                jmp 0x{int(robing_hook_va) + 10:X}
            """,
            robing_wrapper_va,
        )
        if 0xB4 + len(robing_wrapper) > 0x190:
            raise RuntimeError(f"{game_id} robing wrapper overruns the free cave gap")
        payload[0xB4 : 0xB4 + len(robing_wrapper)] = robing_wrapper
        robing_hook_file = int(robing_hook_va) - 0x400000
        robing_guard = bytes.fromhex(str(config["robing_guard"]))
        if source[robing_hook_file : robing_hook_file + len(robing_guard)] != robing_guard:
            raise RuntimeError(f"{game_id} robing hook guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{robing_hook_file:X}",
                "before": robing_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(
                        robing_wrapper_va - int(robing_hook_va) - 5
                    ).to_bytes(4, "little", signed=True)
                    + b"\x90" * (len(robing_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "count every robing once in the per-save reserve, including "
                    "the replacement chiefs the one-shot chief puzzle never "
                    "fires for"
                ),
            }
        )

    burial_hook_va = config.get("burial_hook_va")
    if burial_hook_va:
        # The pickup event is the instruction that clears the corpse's
        # awaiting-burial latch. It runs before the grave array is consulted,
        # so it still fires once the array is full -- which a hook on the
        # burial writer's call site would not, because that writer scans its
        # 500 slots and returns false without recording anything when none is
        # free. The latch guard immediately above it means a second dispatch
        # for the same villager exits before reaching here, so this counts
        # exactly once per skeleton.
        burial_guard = bytes.fromhex(str(config["burial_guard"]))
        # The later games keep their statistics block at a fixed global, so the
        # counter is a single absolute increment. A New Home and The Lost
        # Children reach theirs through a pointer, so those load the manager
        # first and increment at an offset from it. Both forms clobber only
        # EAX, whose next use at each hook is a write (VV1 0x448F84 lea eax,
        # VV2 0x465042 mov eax), so no live value is lost.
        if "burial_stat_va" in config:
            burial_body = (
                f"inc dword ptr [0x{int(config['burial_stat_va']):X}]"
            )
            burial_slot = 0x190
        else:
            burial_body = (
                f"{config['burial_manager']}\n"
                f"                inc dword ptr "
                f"[eax + 0x{int(config['burial_stat_offset']):X}]"
            )
            # VV1 and VV2 have only a 0xD0 cave, whose tail past the export
            # name string is the one free run. 0xB4 leaves the strings intact.
            burial_slot = 0xB4
        burial_wrapper_va = cave_va + burial_slot
        burial_wrapper = assemble(
            f"""
                {burial_body}
                {config['burial_replay']}
                jmp 0x{int(burial_hook_va) + len(burial_guard):X}
            """,
            burial_wrapper_va,
        )
        if burial_slot + len(burial_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} burial wrapper exceeds cave allowance")
        if any(payload[burial_slot : burial_slot + len(burial_wrapper)]):
            raise RuntimeError(f"{game_id} burial wrapper would overwrite the cave")
        payload[burial_slot : burial_slot + len(burial_wrapper)] = burial_wrapper
        burial_hook_file = int(burial_hook_va) - 0x400000
        if (
            source[burial_hook_file : burial_hook_file + len(burial_guard)]
            != burial_guard
        ):
            raise RuntimeError(f"{game_id} burial hook guard does not match")
        # The stolen bytes are always one whole instruction, so the five-byte
        # jump plus however many NOPs the instruction is longer replaces it
        # exactly and no branch lands inside it. The later games steal seven
        # bytes and need two NOPs; VV1 and VV2 steal exactly five and need
        # none. The wrapper replays the clear before returning, so the corpse
        # is still removed.
        extra_patches.append(
            {
                "offset": f"0x{burial_hook_file:X}",
                "before": burial_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(burial_wrapper_va - int(burial_hook_va) - 5).to_bytes(
                        4, "little", signed=True
                    )
                    + b"\x90" * (len(burial_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "count every skeleton pickup once in the per-save reserve, "
                    "including pickups made after the memorial array is full"
                ),
            }
        )

    twins_hook_va = config.get("twins_hook_va")
    if twins_hook_va:
        # The Lost Children is the only game with no twins counter of its own.
        # Its childbirth routine is cumulative rather than exclusive: the twins
        # branch sets litter 2 and falls through into the triplets test, so the
        # existing increment at 0x44BAD2 fires only for triplets and a
        # twins-only birth leaves via 0x44BAA5 or 0x44BAB4 without counting.
        # Hooking the twins branch itself therefore counts every multiple birth
        # once, and a later promotion to triplets does not double count because
        # the triplets increment targets a different field.
        #
        # This wrapper does not fit the 0xD0 statistics cave, whose free tail
        # the burial wrapper already uses, so it lives in the game's own .text
        # slack -- zero padding between VirtualSize and SizeOfRawData, verified
        # stock-zero and clear of every range other features claim there.
        twins_wrapper_va = int(config["twins_wrapper_va"])
        twins_guard = bytes.fromhex(str(config["twins_guard"]))
        twins_wrapper = assemble(
            (
                str(config["twins_manager"]) + "\n"
                + "inc dword ptr [eax + 0x%X]\n"
                % int(config["twins_stat_offset"])
                + "jmp 0x%X" % int(config["twins_resume_va"])
            ),
            twins_wrapper_va,
        )
        twins_hook_file = int(twins_hook_va) - 0x400000
        twins_wrapper_file = twins_wrapper_va - 0x400000
        if source[twins_hook_file : twins_hook_file + len(twins_guard)] != twins_guard:
            raise RuntimeError(f"{game_id} twins hook guard does not match")
        if any(source[twins_wrapper_file : twins_wrapper_file + len(twins_wrapper)]):
            raise RuntimeError(f"{game_id} twins wrapper site is not stock zero padding")
        extra_patches.append(
            {
                "offset": f"0x{twins_wrapper_file:X}",
                "before": "00" * len(twins_wrapper),
                "after": twins_wrapper.hex().upper(),
                "purpose": (
                    "install the twins counter wrapper in stock zero padding"
                ),
            }
        )
        extra_patches.append(
            {
                "offset": f"0x{twins_hook_file:X}",
                "before": twins_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(twins_wrapper_va - int(twins_hook_va) - 5).to_bytes(
                        4, "little", signed=True
                    )
                    + b"\x90" * (len(twins_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "count every twin birth the saturation guard allows once "
                    "in the per-save reserve"
                ),
            }
        )

    triplet_hook_va = config.get("triplet_hook_va")
    if triplet_hook_va:
        # Removes the over-count the twins hook makes for a birth that is
        # later promoted to triplets. Reached only on the triplet path, so
        # every decrement pairs with exactly one earlier increment.
        triplet_guard = bytes.fromhex(str(config["triplet_guard"]))
        triplet_wrapper_va = int(config["triplet_wrapper_va"])
        triplet_wrapper = assemble(
            (
                str(config["triplet_body"]) + "\n"
                + str(config["triplet_replay"]) + "\n"
                + "jmp 0x%X"
                % (int(triplet_hook_va) + len(triplet_guard))
            ),
            triplet_wrapper_va,
        )
        triplet_hook_file = int(triplet_hook_va) - 0x400000
        triplet_wrapper_file = triplet_wrapper_va - 0x400000
        if (
            source[triplet_hook_file : triplet_hook_file + len(triplet_guard)]
            != triplet_guard
        ):
            raise RuntimeError(f"{game_id} triplet hook guard does not match")
        if any(
            source[
                triplet_wrapper_file : triplet_wrapper_file + len(triplet_wrapper)
            ]
        ):
            raise RuntimeError(
                f"{game_id} triplet wrapper site is not stock zero padding"
            )
        extra_patches.append(
            {
                "offset": f"0x{triplet_wrapper_file:X}",
                "before": "00" * len(triplet_wrapper),
                "after": triplet_wrapper.hex().upper(),
                "purpose": (
                    "install the triplet correction wrapper in stock zero "
                    "padding"
                ),
            }
        )
        extra_patches.append(
            {
                "offset": f"0x{triplet_hook_file:X}",
                "before": triplet_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(
                        triplet_wrapper_va - int(triplet_hook_va) - 5
                    ).to_bytes(4, "little", signed=True)
                    + b"\x90" * (len(triplet_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "remove the twins over-count for a birth promoted to "
                    "triplets, so twins counts twins only"
                ),
            }
        )

    debris_hook_va = config.get("debris_hook_va")
    if debris_hook_va:
        debris_guard = bytes.fromhex(str(config["debris_guard"]))
        debris_slot = int(config["debris_slot"])
        debris_wrapper_va = cave_va + debris_slot
        debris_wrapper = assemble(
            "inc dword ptr [0x%X]\n%s\njmp 0x%X"
            % (
                int(config["debris_stat_va"]),
                str(config["debris_replay"]).replace(" ; ", "\n"),
                int(debris_hook_va) + len(debris_guard),
            ),
            debris_wrapper_va,
        )
        if debris_slot + len(debris_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} debris wrapper exceeds cave allowance")
        if any(payload[debris_slot : debris_slot + len(debris_wrapper)]):
            raise RuntimeError(f"{game_id} debris wrapper would overwrite the cave")
        payload[debris_slot : debris_slot + len(debris_wrapper)] = debris_wrapper
        debris_hook_file = int(debris_hook_va) - 0x400000
        if (
            source[debris_hook_file : debris_hook_file + len(debris_guard)]
            != debris_guard
        ):
            raise RuntimeError(f"{game_id} debris hook guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{debris_hook_file:X}",
                "before": debris_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(debris_wrapper_va - int(debris_hook_va) - 5).to_bytes(
                        4, "little", signed=True
                    )
                    + b"\x90" * (len(debris_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "count every unit of stream debris cleared in the per-save "
                    "reserve, without the trophy's earned-once cap"
                ),
            }
        )

    stew = config.get("stew")
    if stew:
        # Unique stews: record the ordered herb triple of every stew the game
        # completes in the pending bitset; see stew_routine and the "stew"
        # notes in GAMES. The companion's PreSave turns the bits into the
        # slot's Stew Discoveries .dat.
        stew_hook_va = int(stew["hook_va"])
        stew_guard = bytes.fromhex(str(stew["guard"]))
        stew_hook_file = stew_hook_va - 0x400000
        if source[stew_hook_file : stew_hook_file + len(stew_guard)] != stew_guard:
            raise RuntimeError(f"{game_id} stew hook guard does not match")
        items = stew_routine(stew)
        if "runs" in stew:
            runs = tuple((int(va), int(length)) for va, length in stew["runs"])
            for run_va, run_length in runs:
                run_file = run_va - 0x400000
                if source[run_file : run_file + run_length] != b"\x90" * run_length:
                    raise RuntimeError(f"{game_id} stew run {run_va:#x} is not stock NOP padding")
                # A run must follow a return: the byte before it ends `ret`
                # (C3) or `ret imm16` (C2 xx xx), so nothing falls into it.
                if source[run_file - 1] != 0xC3 and source[run_file - 3] != 0xC2:
                    raise RuntimeError(f"{game_id} stew run {run_va:#x} does not follow a return")
            placed = chain_assemble(items, runs)
            for piece_va, piece in placed:
                piece_file = piece_va - 0x400000
                extra_patches.append(
                    {
                        "offset": f"0x{piece_file:X}",
                        "before": source[piece_file : piece_file + len(piece)].hex().upper(),
                        "after": piece.hex().upper(),
                        "purpose": (
                            "install part of the stew-discovery recorder in stock "
                            "NOP padding between functions"
                        ),
                    }
                )
            stew_entry_va = placed[0][0]
        else:
            stew_slot = int(stew["slot"])
            stew_entry_va = cave_va + stew_slot
            placed = chain_assemble(items, ((stew_entry_va, cave_size - stew_slot),))
            if len(placed) != 1:
                raise RuntimeError(f"{game_id} stew routine is not contiguous")
            routine = placed[0][1]
            if any(payload[stew_slot : stew_slot + len(routine)]):
                raise RuntimeError(f"{game_id} stew routine would overwrite the cave")
            payload[stew_slot : stew_slot + len(routine)] = routine
        extra_patches.append(
            {
                "offset": f"0x{stew_hook_file:X}",
                "before": stew_guard.hex().upper(),
                "after": (
                    rel32_jump(stew_hook_va, stew_entry_va)
                    + b"\x90" * (len(stew_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "record which herb combination every completed stew used, "
                    "for the unique Stews Found statistic"
                ),
            }
        )

    for death in config.get("death_hooks", []):
        # Count the transition into death, once. The wrapper reads ecx only
        # and writes no register, so no value live at the hook can be lost.
        death_guard = bytes.fromhex(str(death["guard"]))
        death_slot = int(death["slot"])
        death_hook_va = int(death["hook_va"])
        death_wrapper_va = cave_va + death_slot
        # The counting half, then the stolen bytes replayed VERBATIM, then the
        # return jump. An earlier version emitted `mov dword ptr [ecx+0x0C], 0`
        # as the replay, which is correct only because every game shipping this
        # feature hooks that same instruction: the hardcoded text and the
        # site's own `guard` bytes are the same seven bytes. Replaying the
        # guard is strictly more general and, for the games already shipping,
        # emits exactly what the hardcoded form did -- an equivalence checked
        # by regenerating this manifest and requiring it byte-identical, not
        # argued.
        # Two idempotency gates, because the games are not alike.
        #
        # The Secret City, The Tree of Life and New Believers keep a cause of
        # death beside the health field, and the arbiter that zeroes health
        # writes the cause immediately after. Hooking before that write means
        # the wrapper still sees the PRIOR cause, so `cause == -1` is exactly
        # "this villager was alive a moment ago" and counts the transition
        # once however many times the arbiter runs.
        #
        # The Lost Children and A New Home have no cause field at all, so that
        # gate does not transfer. There the transition is read from the health
        # value itself: count only when the pre-value was positive and the
        # result is not. `death_pre_reg` names the register holding the health
        # value before the site's mutation commits; sites whose pre-value is
        # not in a register are hooked through the pointer instead and carry
        # `death_pre_ptr`.
        cause_offset = config.get("death_cause_offset")
        post_gate = None
        if cause_offset is not None:
            gate = (
                "cmp dword ptr [ecx + 0x%X], -1\n" % int(cause_offset)
                + "jne death_counted\n"
            )
        else:
            pre = str(death.get("pre_reg", "")).strip()
            if not pre:
                raise RuntimeError(
                    f"{game_id} death hook {death_hook_va:#x} has no "
                    "death_cause_offset and no pre_reg: the wrapper cannot "
                    "tell a death from an ordinary injury, and counting "
                    "every mutation would report wounds as deaths"
                )
            # The pre-check is all that can run BEFORE the stolen instruction;
            # the post-check has to run AFTER it, because until the mutation is
            # replayed the field still holds the pre-value. An earlier version
            # emitted both halves in the prologue, which put `cmp [ptr], 0`
            # against memory the site had not yet written -- so `jg` always
            # took the skip and the counter could never increment. The wrapper
            # is therefore three parts rather than two.
            gate = "cmp %s, 0\njle death_counted\n" % pre
            post_gate = (
                "cmp dword ptr [%s], 0\n" % str(death["post_ptr"])
                + "jg death_counted\n"
                + "inc dword ptr [0x%X]\n" % int(config["death_stat_va"])
                + "death_counted:\n"
            )
        # The stolen bytes are emitted INSIDE the single assembly rather than
        # concatenated around it, so `death_counted` resolves for gates on
        # both sides of the replay. Assembling the halves separately cannot
        # work: each assemble() call has its own symbol table, and a label
        # defined in one fragment is missing from the other.
        replay = "".join(".byte 0x%02X\n" % b for b in death_guard)
        if post_gate is None:
            body = (
                gate
                + "inc dword ptr [0x%X]\n" % int(config["death_stat_va"])
                + "death_counted:\n"
                + replay
            )
        else:
            body = gate + replay + post_gate
        death_wrapper = assemble(
            body + "jmp 0x%X" % (death_hook_va + len(death_guard)),
            death_wrapper_va,
        )
        if death_slot + len(death_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} death wrapper exceeds cave allowance")
        if any(payload[death_slot : death_slot + len(death_wrapper)]):
            raise RuntimeError(f"{game_id} death wrapper would overwrite the cave")
        payload[death_slot : death_slot + len(death_wrapper)] = death_wrapper
        death_hook_file = death_hook_va - 0x400000
        if (
            source[death_hook_file : death_hook_file + len(death_guard)]
            != death_guard
        ):
            raise RuntimeError(f"{game_id} death hook guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{death_hook_file:X}",
                "before": death_guard.hex().upper(),
                "after": (
                    b"\xE9"
                    + int(death_wrapper_va - death_hook_va - 5).to_bytes(
                        4, "little", signed=True
                    )
                    + b"\x90" * (len(death_guard) - 5)
                ).hex().upper(),
                "purpose": (
                    "count every villager death once, at the health arbiter "
                    "that assigns the cause of death"
                ),
            }
        )

    if game_id == "vv2":
        # Points Earned counted one research path twice. On the path taken
        # when [container+0x2EA7C] == 3 the research routine calls the award
        # routine 0x426290 -- which already adds the amount to both the
        # spendable tech total (+0x2EADC) and the Points Earned statistic
        # (+0x2E4FC) -- and then adds the same EDI to +0x2E4FC again at
        # 0x463742. Every other path, and every other game, adds once. The
        # second add is removed; spendable tech is unaffected.
        double_add_file = 0x63742
        double_add = bytes.fromhex("01B8FCE40200")   # add dword ptr [eax+0x2E4FC], edi
        if source[double_add_file : double_add_file + 6] != double_add:
            raise RuntimeError("vv2 Points Earned double-add guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{double_add_file:X}",
                "before": double_add.hex().upper(),
                "after": "90" * 6,
                "purpose": (
                    "Points Earned: remove the second add of the same research "
                    "award (0x426290 already counted it)"
                ),
            }
        )

    if game_id in ("vv3", "vv4", "vv5"):
        # People Cured counted failed healing attempts. After the healer's
        # treatment roll (call ...; test al, al), a success clears the sick
        # flag and falls into the +1, but the failure branch `je` jumps
        # straight to that same +1. Retargeting the `je` past the increment
        # makes only an actual cure count; the failure path then continues
        # exactly where the stock code goes after the increment.
        #   (je site, stock rel8 -> the +1, fixed rel8 -> the next instruction)
        je_site, stock_rel, fixed_rel = {
            "vv3": (0x45B968, 0x07, 0x0D),   # +1 at 0x45B971 (inc [0x5824B0]); next 0x45B977
            "vv4": (0x465179, 0x07, 0x0E),   # +1 at 0x465182 (add [0x4D6DF0],1); next 0x465189
            "vv5": (0x46E1F9, 0x07, 0x0E),   # +1 at 0x46E202 (add [0x51D368],1); next 0x46E209
        }[game_id]
        je_file = je_site - 0x400000
        if source[je_file : je_file + 2] != bytes([0x74, stock_rel]):
            raise RuntimeError(f"{game_id} People Cured branch guard does not match")
        extra_patches.append(
            {
                "offset": f"0x{je_file:X}",
                "before": bytes([0x74, stock_rel]).hex().upper(),
                "after": bytes([0x74, fixed_rel]).hex().upper(),
                "purpose": (
                    "People Cured: a failed healing roll skips the increment, "
                    "so only an actual cure is counted"
                ),
            }
        )

    if game_id == "vv5":
        extra_patches += vv5_believers_only(source, payload, cave_va, cave_size)

    hook_file = int(config["hook_file"])
    hook_va = int(config["hook_va"])
    stock_call = rel32_call(hook_va, int(config["writer_va"]))
    if source[hook_file : hook_file + 5] != stock_call:
        raise RuntimeError(f"{game_id} full-save call guard does not match")
    if any(source[cave_file : cave_file + cave_size]):
        raise RuntimeError(f"{game_id} statistics cave is not stock zero padding")

    puzzle_clause = (
        "Puzzle totals are read from the current save state during export so existing saves are reported accurately. "
        if game_id != "vv5"
        else "Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. "
    )
    description = (
        "After each successful save of slots 1 through 5, writes the save's "
        "local lifetime statistics to 'Village Statistics v2 - Save N.txt' in "
        "the 'Virtual Villagers Fun Patcher Logs\\Village Statistics' folder "
        "beside the game's saves (an earlier 'Village Statistics - Save N.txt' "
        "is kept unchanged). Counts the game does not keep are stored in "
        "per-save .dat files in 'Virtual Villagers Fun Patcher Data'. Later "
        "games retain the inherited per-save "
        "statistics block even where no Statistics screen is reachable; omitted "
        "stock bookkeeping is restored by exact gameplay hooks. "
        + puzzle_clause
        + "The original save result is preserved, and text-export failure does not turn a "
        "successful game save into a failure."
    )
    return {
        "id": f"{game_id}_write_village_statistics",
        "game_id": game_id,
        "name": "Write Village Statistics to Text File",
        "description": description,
        "output_tag": "Village Statistics Text Export",
        # A New Home's roster gets its "Parents:" lines from Show Parents'
        # companion; the roster itself is written without it.
        "needs_on": (
            [
                {
                    "id": "vv1_show_parents",
                    "for": "the \"Parents:\" lines in the Village Population roster",
                },
            ]
            if game_id == "vv1"
            else []
        ),
        "companion_files": [
            {
                "source": "assets/statistics/VVFP Statistics Export.dll",
                "destination": "VVFP Statistics Export.dll",
                "sha256": companion_hash,
            },
            # The Village Population roster, which the statistics companion
            # calls after a successful save. It ships for all five games
            # because the call is inside that DLL rather than in the
            # executable: the roster needed no appended section, no
            # composition overlay against every other appending feature, and
            # no code cave. "dll over cave space always".
            #
            # It must be present whenever the statistics companion is, or the
            # call finds nothing and the roster silently never appears.
            {
                "source": "assets/population/VVFP Population Export.dll",
                "destination": "VVFP Population Export.dll",
                "sha256": population_hash,
            },
        ],
        "patches": [
            {
                "offset": f"0x{hook_file:X}",
                "before": stock_call.hex().upper(),
                "after": rel32_call(hook_va, cave_va).hex().upper(),
                "purpose": (
                    "route the stock full-save call through a wrapper that "
                    "exports statistics only after a successful primary-slot save"
                ),
            },
            {
                "offset": f"0x{cave_file:X}",
                "before_fill": "00",
                "length": cave_size,
                "after_base64": __import__("base64").b64encode(payload).decode("ascii"),
                "purpose": (
                    "call the stock writer unchanged, preserve its Boolean result, "
                    "and invoke the hash-verified statistics companion for slots 1-5"
                ),
            },
        ] + extra_patches,
    }


def main() -> None:
    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
    population_hash = hashlib.sha256(
        POPULATION_COMPANION.read_bytes()).hexdigest().upper()
    features = [
        build_game(game_id, config, companion_hash, population_hash)
        for game_id, config in GAMES.items()
    ]
    OUTPUT.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "companion_sha256": companion_hash,
                "features": features,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
