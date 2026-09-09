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
        "burial_stat_offset": 0x9E84,
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
        "burial_stat_offset": 0x2E5D4,
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
        "twins_stat_offset": 0x2E5D8,
        "twins_resume_va": 0x44BA92,
        # The correcting decrement on the triplet path. edi is already the
        # manager here (0x44BACC loads it), so no extra load is needed.
        "triplet_hook_va": 0x44BAD2,
        "triplet_guard": "FF8724E50200",
        # At the END of the 106-byte run at 0x473F96, not its start, so the
        # longest contiguous zero run in this section stays as large as
        # possible for publish-time name-crash immunity.
        "triplet_wrapper_va": 0x473FED,
        "triplet_body": "dec dword ptr [edi + 0x2E5D8]",
        "triplet_replay": "inc dword ptr [edi + 0x2E524]",
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
        "burial_stat_va": 0x5824D8,
        # Every death in this game routes through one of two sibling health
        # arbiters. The proof they are the sole arbiter rather than one path
        # among several is that the ALIVE path explicitly writes -1 to the
        # cause field (0x4626DF, 0x462698): a living villager always has
        # cause -1 and a dead one a real cause id, which is also what makes
        # the count idempotent. The branch above each site tests the
        # RESULTING health, not the prior, so calling either again on an
        # already-dead villager re-enters the death path; testing the cause
        # for -1 counts the transition exactly once.
        "death_stat_va": 0x5824E0,
        "death_cause_offset": 0x10,
        "death_hooks": [
            {"hook_va": 0x4626C6, "guard": "C7410C00000000", "slot": 0x1A8},
            {"hook_va": 0x46267F, "guard": "C7410C00000000", "slot": 0x1C8},
        ],
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
        "food_stat_va": 0x4D6DEC,
        "burial_hook_va": 0x46A977,
        "burial_guard": "C686C41C000000",
        "burial_replay": "mov byte ptr [esi + 0x1CC4], 0",
        # +0x30 (0x4D6E10) is the Origins doubler ownership bitmask; see the
        # VV3 note. Burial counter and marker take +0x3C and +0x40.
        "burial_stat_va": 0x4D6E1C,
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
        "debris_stat_va": 0x4D6E24,
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
        "death_stat_va": 0x4D6E28,
        "death_cause_offset": 0x10,
        "death_hooks": [
            # 0x46AF00 sets health absolutely; 0x46AF40 applies a delta with
            # `add [ecx+0xC], eax`, so a death by cumulative damage passes
            # only through the second. Hooking one alone would miss it.
            {"hook_va": 0x46AF0F, "guard": "C7410C00000000", "slot": 0x1C8},
            {"hook_va": 0x46AF52, "guard": "C7410C00000000", "slot": 0x1E0},
        ],
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
        "food_stat_va": 0x51D364,
        "conversion_hook_va": 0x4668B0,
        "conversion_stat_va": 0x51D38C,
        "burial_hook_va": 0x473F8F,
        "burial_guard": "C686D41C000000",
        "burial_replay": "mov byte ptr [esi + 0x1CD4], 0",
        # +0x30 holds the Origins saved bit flags and +0x34 the Heathens
        # Converted total, so this game's first free reserve dword is +0x38.
        "burial_stat_va": 0x51D390,
        # Same two-arbiter shape as The Secret City; see that note.
        "death_stat_va": 0x51D398,
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


def build_game(game_id: str, config: dict[str, object], companion_hash: str) -> dict:
    source = (STOCK / str(config["exe"])).read_bytes()
    cave_file = int(config["cave_file"])
    cave_va = int(config["cave_va"])
    cave_size = int(config["cave_size"])
    dll_name_va = cave_va + 0x80
    export_name_va = cave_va + 0x9C

    code = assemble(
        f"""
            push ebx
            mov ebx, ecx
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            mov ecx, ebx
            call 0x{int(config['writer_va']):X}
            push eax
            test al, al
            jz done
            cmp edi, 1
            jl done
            cmp edi, 5
            jg done
            push 0x{dll_name_va:X}
            call dword ptr [0x{int(config['get_module_handle_iat']):X}]
            test eax, eax
            jne resolve_export
            push 0x{dll_name_va:X}
            call dword ptr [0x{int(config['load_library_iat']):X}]
            test eax, eax
            jz done
        resolve_export:
            push 0x{export_name_va:X}
            push eax
            call dword ptr [0x{int(config['get_proc_address_iat']):X}]
            test eax, eax
            jz done
            push edi
            push ebx
            push {int(config['game_number'])}
            call eax
        done:
            pop eax
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
    export_name = b"WriteVillageStatistics\0"
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

    for death in config.get("death_hooks", []):
        # Count the transition into death, once. The wrapper reads ecx only
        # and writes no register, so no value live at the hook can be lost.
        death_guard = bytes.fromhex(str(death["guard"]))
        death_slot = int(death["slot"])
        death_hook_va = int(death["hook_va"])
        death_wrapper_va = cave_va + death_slot
        death_wrapper = assemble(
            (
                "cmp dword ptr [ecx + 0x%X], -1\n"
                % int(config["death_cause_offset"])
                + "jne death_counted\n"
                + "inc dword ptr [0x%X]\n"
                % int(config["death_stat_va"])
                + "death_counted:\n"
                + "mov dword ptr [ecx + 0x0C], 0\n"
                + "jmp 0x%X" % (death_hook_va + len(death_guard))
            ),
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
        "local lifetime statistics to 'Village Statistics - Save N.txt' in the "
        "modified game folder. Later games retain the inherited per-save "
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
        "companion_files": [
            {
                "source": "assets/statistics/VVFP Statistics Export.dll",
                "destination": "VVFP Statistics Export.dll",
                "sha256": companion_hash,
            }
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
    features = [
        build_game(game_id, config, companion_hash)
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
