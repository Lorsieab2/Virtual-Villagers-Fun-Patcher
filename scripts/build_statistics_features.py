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
        "burial_hook_va": 0x45F45B,
        "burial_stat_va": 0x5824BC,
        "burial_guard": "881EE9B8010000",
        "burial_restore": "mov byte ptr [esi], bl",
        "burial_return_va": 0x45F61A,
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
        "burial_hook_va": 0x4664DC,
        "burial_stat_va": 0x4D6DFC,
        "burial_guard": "885EFD385EFD",
        "burial_restore": "mov byte ptr [esi - 3], bl; cmp byte ptr [esi - 3], bl",
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
        "burial_hook_va": 0x46FF12,
        "burial_stat_va": 0x51D374,
        "burial_guard": "889ED41C0000",
        "burial_restore": "mov byte ptr [esi + 0x1CD4], bl",
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

    burial_hook_va = config.get("burial_hook_va")
    if burial_hook_va:
        burial_guard = bytes.fromhex(str(config["burial_guard"]))
        burial_return_va = int(
            config.get(
                "burial_return_va",
                int(burial_hook_va) + len(burial_guard),
            )
        )
        burial_wrapper_va = cave_va + 0x110
        burial_wrapper = assemble(
            f"""
                inc dword ptr [0x{int(config['burial_stat_va']):X}]
                {str(config['burial_restore'])}
                jmp 0x{burial_return_va:X}
            """,
            burial_wrapper_va,
        )
        if 0x110 + len(burial_wrapper) > cave_size:
            raise RuntimeError(f"{game_id} burial wrapper exceeds cave allowance")
        payload[0x110 : 0x110 + len(burial_wrapper)] = burial_wrapper
        burial_hook_file = int(burial_hook_va) - 0x400000
        if (
            source[burial_hook_file : burial_hook_file + len(burial_guard)]
            != burial_guard
        ):
            raise RuntimeError(f"{game_id} burial hook guard does not match")
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
                    "restore the inherited Villagers Buried counter at the "
                    "one-time delayed corpse-record retirement, including catch-up"
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

    description = (
        "After each successful save of slots 1 through 5, writes the save's "
        "local lifetime statistics to 'Village Statistics - Save N.txt' in the "
        "modified game folder. Later games retain the inherited per-save "
        "statistics block even where no Statistics screen is reachable; omitted "
        "stock bookkeeping is restored by exact gameplay hooks. The original "
        "save result is preserved, and text-export failure does not turn a "
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
