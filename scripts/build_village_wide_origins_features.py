"""Build the optional village-wide Origins upgrade payloads.

The base Origins payload owns the menu and purchase plumbing.  These payloads
are deliberately independent: each writes only a certified zero-filled
extension cave containing a signature, a tiny ABI header, and the three
save-scoped record walkers.  The base payload's dormant extension ABI can call
the entry point when this feature is selected; the optional manifest never
rewrites the base Origins cave.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"

# These are the certified optional extension locations from the implementation
# plan.  Cure is kept at the beginning of the reserve; the optional payload is
# intentionally placed after it so the two manifests are composable.
CONFIG = {
    "vv1": {
        "title": "Virtual Villagers - A New Home",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - A New Home.exe",
        "sha256": "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
        "cave_offset": 0x8B004,
        "cave_va": 0x48D004,
        "payload_offset": 0x8B180,
        "stride": 0x3D8,
        "first": "ecx",
        "active": 0x28,
        "health": 0x344,
        "age": 0x348,
        "skills": (0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC),
        "likes": 0x398,
        "dislikes": 0x3A8,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 90,
    },
    "vv2": {
        "title": "Virtual Villagers - The Lost Children",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Lost Children.exe",
        "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
        "cave_offset": 0x9A004,
        "cave_va": 0x49C004,
        # The VV2 base Origins UI uses 0x9A180-0x9A7CB for its preflight and
        # event helpers. Keep this optional village-wide payload after that
        # occupied range inside the same executable .shr reserve.
        "payload_offset": 0x9A800,
        "stride": 0xE48C,
        "first": "ecx",
        "active": 0x30,
        "health": 0x52C,
        "age": 0x530,
        "skills": (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4),
        "likes": 0x5F0,
        "dislikes": 0x6E8,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 90,
    },
    "vv3": {
        "title": "Virtual Villagers - The Secret City",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Secret City.exe",
        "sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        "cave_offset": 0x7B664,
        "cave_va": 0x47B664,
        "payload_offset": 0x7B820,
        "stride": 0x1F8C,
        "first": "ecx",
        "active": 0xF10,
        "health": 0xE78,
        "age": 0xDC4,
        "skills": (0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC),
        "likes": 0xFB4,
        "dislikes": 0xFC0,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 90,
    },
    "vv4": {
        "title": "Virtual Villagers - The Tree of Life",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        "cave_offset": 0xCC004,
        "cave_va": 0x728004,
        "payload_offset": 0xCC220,
        "stride": 0x2E3C,
        "first": "ecx",
        "active": 0x1CC4,
        "dead": 0x1CC7,
        "health": 0x1C40,
        "age": 0x1B8C,
        "skills": (0x1C5C, 0x1C60, 0x1C64, 0x1C68, 0x1C6C),
        "likes": 0x1E60,
        "dislikes": 0x1E6C,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 0x42B40000,
    },
    "vv5": {
        "title": "Virtual Villagers - New Believers",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - New Believers.exe",
        "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        "cave_offset": 0x94339,
        "cave_va": 0x494339,
        "payload_offset": 0x94C20,
        "code_size": 0x260,
        "mastery_code_offset": 0x150,
        "age_code_offset": 0x1F0,
        "stride": 0x2F44,
        "first": "ecx",
        "active": 0x1CD4,
        "heathen_active_guard": 0x1CE1,
        "faction": 0x1CEC,
        "health": 0x1C40,
        "age": 0x1B8C,
        "skills": (7260, 7264, 7268, 7272, 7276, 7280),
        "likes": 8028,
        "dislikes": 8040,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": True,
        "master_value": 0x42B40000,
    },
}


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def _hex_word(value: int) -> str:
    return f"0x{value:X}"


def _first_expression(config: dict) -> str:
    return config["first"]


def _record_setup(config: dict) -> str:
    return "mov esi, ecx"


def _eligibility(config: dict, label: str) -> str:
    active = config["active"]
    health = config["health"]
    result = [
        f"cmp byte ptr [esi + {_hex_word(active)}], 0",
        f"je {label}",
    ]
    if config.get("dead") is not None:
        result.extend(
            [
                f"cmp byte ptr [esi + {_hex_word(config['dead'])}], 0",
                f"jne {label}",
            ]
        )
    result.extend(
        [
        f"cmp dword ptr [esi + {_hex_word(health)}], 0",
        f"jle {label}",
        ]
    )
    if config["heathen"]:
        result.extend(
            [
                f"cmp byte ptr [esi + {_hex_word(config['heathen_active_guard'])}], 0",
                f"jne {label}",
                f"cmp byte ptr [esi + {_hex_word(config['faction'])}], 0",
                f"jne {label}",
            ]
        )
    return "\n".join(result)


def build_payload(config: dict) -> tuple[bytes, dict[str, int]]:
    cave_va = config["cave_va"]
    payload_va = config["cave_va"] + (config["payload_offset"] - config["cave_offset"])
    # Entry is deliberately at a stable offset from the signature.  The base
    # Origins payload can check the signature and call this entry without
    # knowing the optional implementation's internal layout.
    entry_va = payload_va + 0x20
    running_va = payload_va + 0x70
    mastery_va = payload_va + config.get("mastery_code_offset", 0x190)
    age_va = payload_va + config.get("age_code_offset", 0x250)
    code = bytearray(b"\0" * config.get("code_size", 0x390))

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - payload_va
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(f"optional payload exceeds reserve at {va:#x}")
        if any(code[start:end]):
            raise RuntimeError(f"optional payload overlap at {va:#x}")
        code[start:end] = payload

    put(
        entry_va,
        f"""
            cmp eax, 6
            je 0x{running_va:X}
            cmp eax, 7
            je 0x{mastery_va:X}
            cmp eax, 8
            je 0x{age_va:X}
            xor edx, edx
            xor ecx, ecx
            mov eax, -1
            ret
        """,
    )

    put(
        running_va,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebx, edx
            {_record_setup(config)}
            xor edi, edi
            xor ebp, ebp
            xor eax, eax
        running_loop:
            test ebx, ebx
            jz running_done
            {_eligibility(config, 'running_next')}
            lea edx, [esi + {_hex_word(config['likes'])}]
            mov ecx, 3
        running_scan:
            cmp dword ptr [edx], {_hex_word(config['running_preference_id'])}
            jne running_not_running
            inc ebp
            jmp running_remove_dislikes
        running_not_running:
            cmp dword ptr [edx], -1
            je running_store_like
            add edx, 4
            dec ecx
            jne running_scan
            inc edi
            jmp running_remove_dislikes
        running_store_like:
            mov dword ptr [edx], {_hex_word(config['running_preference_id'])}
        running_remove_dislikes:
            lea edx, [esi + {_hex_word(config['dislikes'])}]
            mov ecx, 3
        running_dislike_check:
            cmp dword ptr [edx], {_hex_word(config['running_preference_id'])}
            je running_has_dislike
            add edx, 4
            dec ecx
            jne running_dislike_check
            jmp running_next
        running_has_dislike:
            inc eax
            lea edx, [esi + {_hex_word(config['dislikes'])}]
            mov ecx, 3
        running_dislike_scan:
            cmp dword ptr [edx], {_hex_word(config['running_preference_id'])}
            jne running_dislike_next
            mov dword ptr [edx], -1
        running_dislike_next:
            add edx, 4
            dec ecx
            jne running_dislike_scan
        running_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp running_loop
        running_done:
            mov ecx, eax
            mov eax, edi
            mov edx, ebp
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )

    skill_writes = "\n".join(
        f"mov dword ptr [esi + {_hex_word(offset)}], {_hex_word(config['master_value'])}"
        for offset in config["skills"]
    )
    put(
        mastery_va,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebx, edx
            {_record_setup(config)}
        mastery_loop:
            test ebx, ebx
            jz mastery_done
            {_eligibility(config, 'mastery_next')}
            {skill_writes}
        mastery_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp mastery_loop
        mastery_done:
            xor eax, eax
            xor edx, edx
            xor ecx, ecx
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )

    put(
        age_va,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebp, ecx
            mov ebx, edx
            {_record_setup(config)}
        age_loop:
            test ebx, ebx
            jz age_done
            {_eligibility(config, 'age_next')}
            mov dword ptr [esi + {_hex_word(config['age'])}], 360
        age_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp age_loop
        age_done:
            xor eax, eax
            xor edx, edx
            xor ecx, ecx
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )

    header = bytearray(b"VVFPOWU\0")
    header.extend((1).to_bytes(4, "little"))
    header.extend((entry_va - payload_va).to_bytes(4, "little"))
    header.extend((3).to_bytes(4, "little"))
    if len(header) > 0x20:
        raise AssertionError("optional ABI header grew beyond the reserved header")
    header.extend(b"\0" * (0x20 - len(header)))
    payload = bytes(header + code)
    return payload, {
        "signature_offset": config["payload_offset"],
        "entry_offset": config["payload_offset"] + (entry_va - payload_va),
        "running_offset": config["payload_offset"] + (running_va - payload_va),
        "mastery_offset": config["payload_offset"] + (mastery_va - payload_va),
        "age_offset": config["payload_offset"] + (age_va - payload_va),
    }


def main() -> None:
    stock_dir = ROOT / "research" / "stock-executables"
    for game_id, config in CONFIG.items():
        stock_path = stock_dir / config["exe"]
        original = stock_path.read_bytes()
        actual_hash = hashlib.sha256(original).hexdigest().upper()
        if actual_hash != config["sha256"]:
            raise RuntimeError(f"{game_id} stock SHA-256 mismatch: {actual_hash}")
        payload, entries = build_payload(config)
        offset = config["payload_offset"]
        before = original[offset : offset + len(payload)]
        if len(before) != len(payload) or any(before):
            raise RuntimeError(
                f"{game_id} optional reserve is not certified zero-filled at 0x{offset:X}"
            )
        rendered = bytearray(original)
        rendered[offset : offset + len(payload)] = payload
        out_dir = ROOT / "research" / f"{game_id}-origins-village-wide"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_exe = out_dir / f"{config['title']} - Origins Village Wide Research.exe"
        out_exe.write_bytes(rendered)
        feature_id = f"{game_id}_origins_village_wide_upgrades"
        feature_name = "Enable Origins Village-Wide Upgrades"
        enabled = True
        description = (
            (
                "Requested static/playtest package: enables the existing Origins Tech-screen "
                "Upgrades button and menu, then "
                "adds the village-wide rows from the Virtual Villagers 1 mobile port: "
            )
            if enabled
            else (
                "Retains the historical Origins rows from the Virtual Villagers 1 mobile port "
                "as disabled diagnostic provenance rather than public Tech-screen upgrades: "
            )
        ) + (
            "All Villagers Like Running, Grant Full Mastery to All Villagers, and All "
            "Villagers are 18. Each row costs 1,000,000 tech points in the current save. "
            "The legacy Running helper and its preference-table facts are not native ABI "
            "proof. Mastery writes only the native skill fields. Age changes only the "
            "displayed age to 18 and does not change nursing or pregnancy timers."
        )
        if game_id == "vv5":
            description += " Only eligible living believers are processed; Heathens are excluded and remain untouched."
        feature = {
            "id": feature_id,
            "game_id": game_id,
            "running_preference_id": config["running_preference_id"],
            "running_preference_evidence": {
                "source": "exact stock executable embedded preference table",
                "table_file_offset": {
                    "vv1": "0x7B260",
                    "vv2": "0x8B808",
                    "vv3": "0x97488",
                    "vv4": "0xA0CD8",
                    "vv5": "0xAEF60",
                }[game_id],
                "entry_name": "running",
            },
            "name": feature_name,
            "description": description,
            "output_tag": "Origins Village-Wide Upgrades",
            "dependencies": [f"{game_id}_enable_origins_exclusive_features"],
            "extension_abi": {
                "signature": "VVFPOWU",
                "signature_offset": f"0x{entries['signature_offset']:X}",
                "entry_offset": f"0x{entries['entry_offset']:X}",
                "entry_virtual_address": f"0x{config['cave_va'] + (entries['entry_offset'] - config['cave_offset']):X}",
                "calling_convention": "near call with EAX=command 6/7/8, ECX=first physical record pointer, EDX=physical record bound; command 6 returns full-Like skips in EAX, already-Running (already-running) skips in EDX, and villagers with a removed Running dislike in ECX; commands 7/8 return zero counts; invalid commands return EAX=-1 and EDX/ECX=0; preserves EBX/ESI/EDI/EBP/ESP",
                "commands": {
                    "6": "All Villagers Like Running",
                    "7": "Grant Full Mastery to All Villagers",
                    "8": "All Villagers are 18",
                },
            },
            "record_fields": {
                "stride": f"0x{config['stride']:X}",
                "first_record_argument": "ECX",
                "active_offset": f"0x{config['active']:X}",
                "health_offset": f"0x{config['health']:X}",
                "age_offset": f"0x{config['age']:X}",
                "likes_offset": f"0x{config['likes']:X}",
                "dislikes_offset": f"0x{config['dislikes']:X}",
                "running_preference_id": config["running_preference_id"],
                "skill_offsets": [f"0x{offset:X}" for offset in config["skills"]],
                "bound_source": "EDX physical record bound",
            },
            "behavior_changes": [
                "Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed.",
                "Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save.",
                "Running scans exactly three normal Like and Dislike slots, reports full-Like and already-Running counts, and reports villagers whose Running dislike was removed; duplicate Running Dislikes are all cleared but count once per villager.",
                "Grant Full Mastery to All Villagers writes the native five- or six-skill mastery fields for eligible living villagers.",
                "All Villagers are 18 writes only the verified displayed-age field to 360 age units.",
            ],
            "running_preference_id": config["running_preference_id"],
            "explicit_non_changes": [
                "No unrelated Like is replaced or removed.",
                "No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written.",
                "The upgrades are save-scoped and do not set a global ownership bit.",
                "VV5 Heathens are excluded from all three village-wide operations.",
            ],
            "evidence_status": "static exact-build payload and field-map verification performed; runtime/player confirmation pending",
            "cave": {
                "file_offset": f"0x{offset:X}",
                "virtual_address": f"0x{config['cave_va'] + (offset - config['cave_offset']):X}",
                "length": len(payload),
                "reserved_range": f"0x{config['cave_offset']:X}-0x{config['cave_offset'] + 0x1000:X}",
                "ownership": "optional Origins village-wide payload only",
            },
            "companion_files": [],
            "patches": [
                {
                    "offset": f"0x{offset:X}",
                    "before": before.hex().upper(),
                    "after": payload.hex().upper(),
                    "purpose": "install the optional signed Origins village-wide ABI payload without overwriting base Origins bytes",
                }
            ],
        }
        # This user-requested package exposes the complete five-game set as
        # static/runtime-playtest options. It does not claim player or runtime
        # GO, and the package documentation preserves the reported crash gates.
        feature["enabled"] = enabled
        if game_id == "vv5":
            feature["record_fields"].update(
                {
                    "heathen_active_guard_offset": f"0x{config['heathen_active_guard']:X}",
                    "faction_offset": f"0x{config['faction']:X}",
                    "eligibility": "active != 0, heathen-active guard == 0, faction == believer (0), health > 0",
                }
            )
        manifest_path = ROOT / "data" / f"{feature_id}.json"
        manifest_path.write_text(json.dumps(feature, indent=2) + "\n", encoding="utf-8")
        print(f"{game_id}: {len(payload):#x} bytes -> {manifest_path}")


if __name__ == "__main__":
    main()
