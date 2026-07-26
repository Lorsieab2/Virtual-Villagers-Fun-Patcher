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
}


def assemble(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def build_game(game_id: str, config: dict[str, int | str], companion_hash: str) -> dict:
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

    hook_file = int(config["hook_file"])
    hook_va = int(config["hook_va"])
    stock_call = rel32_call(hook_va, int(config["writer_va"]))
    if source[hook_file : hook_file + 5] != stock_call:
        raise RuntimeError(f"{game_id} full-save call guard does not match")
    if any(source[cave_file : cave_file + cave_size]):
        raise RuntimeError(f"{game_id} statistics cave is not stock zero padding")

    return {
        "id": f"{game_id}_write_village_statistics",
        "game_id": game_id,
        "name": "Write Village Statistics to Text File",
        "description": (
            "After each successful save of slots 1 through 5, writes the stock "
            "local lifetime statistics to 'Village Statistics - Save N.txt' "
            "in the modified game folder. The original save result is preserved, "
            "and a text-export failure does not turn a successful game save into "
            "a failure."
        ),
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
        ],
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
