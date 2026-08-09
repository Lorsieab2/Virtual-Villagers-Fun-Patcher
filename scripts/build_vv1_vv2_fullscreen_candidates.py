"""Emit disabled VV1/VV2 fullscreen-safe candidate evidence.

The executable wrappers are the fixed oracle blobs supplied by the native
audit.  They are overlaid only into the reserved zero portions of the already
certified Full Mastery append page.  This builder never changes the public
catalog and never writes a game/save directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vv_fun_patcher import FunPatch, identify, render_patched_bytes  # noqa: E402

ORIGINS_DLL = ROOT / "assets/origins/VVFP Origins Icons.dll"
ORIGINS_DLL_SHA256 = "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9"
WINDOWS_CURE_DLL_SHA256 = "846BA4EDF29E52689883A6E20DBF5CB92244DBB52531D7573EDAFF6C9C91543D"


def recompute_pe_checksum(data: bytes) -> bytes:
    """Recompute the PE checksum after the append-page/header transaction."""
    out = bytearray(data)
    pe = int.from_bytes(out[0x3C:0x40], "little")
    field = pe + 24 + 64
    if field + 4 > len(out):
        raise RuntimeError("invalid PE checksum field")
    out[field:field + 4] = b"\0\0\0\0"
    total = 0
    for off in range(0, len(out), 2):
        word = out[off] | ((out[off + 1] if off + 1 < len(out) else 0) << 8)
        total = (total & 0xFFFF) + (total >> 16) + word
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    checksum = (total + len(out)) & 0xFFFFFFFF
    out[field:field + 4] = checksum.to_bytes(4, "little")
    return bytes(out)

ORACLE = {
    "vv1": {
        "stock": ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe",
        "origins": ROOT / "data/vv1_origins_feature.json",
        "fm": ROOT / "data/candidates/vv1_full_mastery_all_candidate.json",
        "base_sha256": {"collection_progression": "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3", "immediate_fixed": "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3"},
        "parent_size": 0x8E000,
        "append_raw": 0x8E000,
        "section_va": 0x490000,
        "wrapper_offsets": (0x1000, 0x1200, 0x1400),
        "wrapper_vas": (0x491000, 0x491200, 0x491400),
        "strings_va": 0x491F00,
        "hooks": {
            "tech": (0x456910, bytes.fromhex("E8AB000000"), bytes.fromhex("E8EBA60300")),
            "detail": (0x456DA0, bytes.fromhex("E87C000000"), bytes.fromhex("E85BA40300")),
        },
        "fm_hook_offset": 0xE,
        "fm_hook_after": bytes.fromhex("E8ED130000"),
        "cure_guard": (0x456A88, bytes.fromhex("83FB06"), bytes.fromhex("83FB05")),
        # The legacy price gate alone still let command 5 fall into the
        # shared 1,000,000-tech-point commands 5-8 path.  Keep commands 0-4
        # and 6-8 byte-identical, but route exactly EBX==5 to the existing
        # no-action continuation before the price/funds call.
        "cure_preprice_guard": (
            (0x456A8D, bytes.fromhex("83FB08"), bytes.fromhex("83FB05")),
            (0x456A90, bytes.fromhex("0F872FFFFFFF"), bytes.fromhex("0F842FFFFFFF")),
            0x4569C5,
        ),
        "companion_name": "VVFP VV1 Fullscreen Safe Candidate.dll",
    },
    "vv2": {
        "stock": ROOT / "research/stock-executables/Virtual Villagers - The Lost Children.exe",
        "origins": ROOT / "data/vv2_origins_feature.json",
        "fm": ROOT / "data/candidates/vv2_full_mastery_all_candidate.json",
        "base_sha256": {"collection_progression": "F58F9DAFBE0C6B9B08AA3C491D1731F474DBC80D0DA50A0BF9AA8BFFBE2331AA", "immediate_fixed": "66B642366BBEA817896CFBED950445D9F9895B39C05AD93B8DC75695EFF3B7A8"},
        "parent_size": 0xB1000,
        "append_raw": 0xB1000,
        "section_va": 0x4B3000,
        "wrapper_offsets": (0x1400, 0x1600, 0x1800),
        "wrapper_vas": (0x4B4400, 0x4B4600, 0x4B4800),
        "strings_va": 0x4B4F00,
        "hooks": {
            "tech": (0x4943B6, bytes.fromhex("E82D020000"), bytes.fromhex("E845000200")),
            "detail": (0x494476, bytes.fromhex("E82D040000"), bytes.fromhex("E885010200")),
        },
        "fm_hook_offset": 0xE,
        "fm_hook_after": bytes.fromhex("E8ED170000"),
        "cure_guard": (0x4946A5, bytes.fromhex("83FB06"), bytes.fromhex("83FB05")),
        "companion_name": "VVFP VV2 Fullscreen Safe Candidate.dll",
    },
}

WRAPPERS = {
    "vv1": [
        bytes.fromhex("5589E553565783EC0C894DF0E87F70F7FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068001F4900FF151070450085C00F849700000068091F490050FF15D470450085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E83628F7FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E82A59FCFF6A0189F9E81128F7FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E8FC58FCFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
        bytes.fromhex("5589E553565783EC0C894DF0E87F6EF7FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068001F4900FF151070450085C00F849700000068091F490050FF15D470450085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E83626F7FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E88B5BFCFF6A0189F9E81126F7FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E85D5BFCFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
        bytes.fromhex("5589E553565783EC0C894DF0E87F6CF7FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068001F4900FF151070450085C00F849700000068091F490050FF15D470450085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E83624F7FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E86AECFFFF6A0189F9E81124F7FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E83CECFFFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
    ],
    "vv2": [
        bytes.fromhex("5589E553565783EC0C894DF0E80F3FF5FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068004F4B00FF151040470085C00F849700000068094F4B0050FF15D440470085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E8C6F6F4FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E85201FEFF6A0189F9E8A1F6F4FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E82401FEFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
        bytes.fromhex("5589E553565783EC0C894DF0E80F3DF5FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068004F4B00FF151040470085C00F849700000068094F4B0050FF15D440470085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E8C6F4F4FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E81202FEFF6A0189F9E8A1F4F4FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E8E401FEFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
        bytes.fromhex("5589E553565783EC0C894DF0E80F3BF5FF85C00F84C100000089C68B3E85FF0F84B50000008B5F3885DB0F84AA00000068004F4B00FF151040470085C00F849700000068094F4B0050FF15D440470085C00F84830000008945EC53FFD083C404250110000074513D0110000075588945E86A0089F9E8C6F2F4FF8B45EC53FFD083C404A901100000753CC6471E018B4DF0E86AE8FFFF6A0189F9E8A1F2F4FF8B45EC53FFD083C40425011000003B45E87514C6471E00EB22C6471E018B4DF0E83CE8FFFFEB148B45EC53FFD083C404A9011000000F94C088471E83C40C5F5E5B89EC5DC3"),
    ],
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2) + "\n").replace("\n", "\r\n").encode()


def dialog_spans(blob: bytes) -> list[tuple[int, int, str | None]]:
    if blob[:4] != b"\x01\0\xff\xff":
        raise RuntimeError("resource 201 is not DIALOGEX")
    count = int.from_bytes(blob[16:18], "little")
    def skip(cursor: int) -> int:
        first = int.from_bytes(blob[cursor:cursor + 2], "little")
        if first == 0:
            return cursor + 2
        if first == 0xFFFF:
            return cursor + 4
        cursor += 2
        while blob[cursor:cursor + 2] != b"\0\0":
            cursor += 2
        return cursor + 2
    cursor = 26
    cursor = skip(cursor); cursor = skip(cursor); cursor = skip(cursor)
    cursor += 6; cursor = skip(cursor)
    spans = []
    for _ in range(count):
        cursor = (cursor + 3) & ~3
        start = cursor; cursor += 24; cursor = skip(cursor)
        title_start = cursor; title_end = skip(cursor)
        raw = blob[title_start:title_end]
        title = None if raw[:2] in (b"\0\0", b"\xff\xff") else raw[:-2].decode("utf-16le")
        extra = int.from_bytes(blob[title_end:title_end + 2], "little")
        cursor = title_end + 2 + extra * 2
        end = (cursor + 3) & ~3
        spans.append((start, end, title)); cursor = end
    if cursor > len(blob):
        raise RuntimeError("DIALOGEX walk escaped leaf")
    return spans


def transform_companion(source: Path) -> bytes:
    import pefile
    source_bytes = source.read_bytes()
    if len(source_bytes) != 295936 or sha(source_bytes) != ORIGINS_DLL_SHA256:
        raise RuntimeError("Origins companion parent hash/size mismatch")
    pe = pefile.PE(str(source), fast_load=False)
    data = bytearray(source_bytes)
    leaves = {}
    for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        kind = typ.name.string.decode() if typ.name else typ.struct.Id
        if kind != 5:
            continue
        for ent in typ.directory.entries:
            ident = ent.name.string.decode() if ent.name else ent.struct.Id
            if ident in (201, 202):
                leaf = ent.directory.entries[0].data.struct
                leaves[ident] = (pe.get_offset_from_rva(leaf.OffsetToData), leaf.Size)
    if set(leaves) != {201, 202}:
        raise RuntimeError("VV1/VV2 companion must expose exactly RT_DIALOG 201 and 202")
    off, size = leaves[201]
    dialog = bytes(data[off:off + size])
    spans = dialog_spans(dialog)
    item_ids = [int.from_bytes(dialog[start + 20:start + 24], "little") for start, _, _ in spans]
    if len(spans) != 46 or [i for i, (_, _, t) in enumerate(spans) if t == "Cure all Villagers"] != [27]:
        raise RuntimeError("unexpected Cure row layout")
    if item_ids.count(1005) != 1 or item_ids[29] != 1005:
        raise RuntimeError("unexpected Cure Buy button identity")
    compact = dialog[:spans[25][0]] + dialog[spans[30][0]:]
    compact += bytes(size - len(compact))
    compact = bytearray(compact); compact[16:18] = (41).to_bytes(2, "little")
    after = dialog_spans(bytes(compact))
    after_ids = [int.from_bytes(compact[start + 20:start + 24], "little") for start, _, _ in after]
    if len(after) != 41 or any(t == "Cure all Villagers" for _, _, t in after) or 1005 in after_ids:
        raise RuntimeError("Cure row removal did not produce 41 strict items")
    data[off:off + size] = compact
    return bytes(data)


def build_mode(game: str, mode: str) -> tuple[bytes, bytes, dict[str, object]]:
    cfg = ORACLE[game]
    stock = cfg["stock"]
    origin = FunPatch(json.loads(cfg["origins"].read_text(encoding="utf-8")))
    fm = json.loads(cfg["fm"].read_text(encoding="utf-8"))
    build = identify(stock)
    parent, _ = render_patched_bytes(stock, build, mode, [], _fun_patches_override=[origin])
    parent = bytearray(parent)
    if len(parent) != cfg["parent_size"] or sha(parent) != cfg["base_sha256"][mode]:
        raise RuntimeError(f"{game} {mode} Origins parent identity mismatch")
    for _, (va, before, after) in cfg["hooks"].items():
        off = va - 0x400000
        if bytes(parent[off:off + 5]) != before:
            raise RuntimeError(f"{game} hook preimage mismatch at {va:#x}")
        parent[off:off + 5] = after
    cure_va, cure_before, cure_after = cfg["cure_guard"]
    cure_off = cure_va - 0x400000
    if bytes(parent[cure_off:cure_off + len(cure_before)]) != cure_before:
        raise RuntimeError(f"{game} legacy Cure guard preimage mismatch")
    parent[cure_off:cure_off + len(cure_after)] = cure_after
    preprice = cfg.get("cure_preprice_guard")
    if preprice:
        for va, before, after in preprice[:2]:
            off = va - 0x400000
            if bytes(parent[off:off + len(before)]) != before:
                raise RuntimeError(f"{game} command-5 pre-price guard preimage mismatch at {va:#x}")
            parent[off:off + len(after)] = after
    layout = fm["pe_append_transaction"]["layouts"][mode]
    page = bytearray(bytes.fromhex(layout["append_bytes"]))
    if len(page) != 0x2000 or bytes(page[cfg["fm_hook_offset"]:cfg["fm_hook_offset"] + 5]) != bytes.fromhex("E8ED000000"):
        raise RuntimeError(f"{game} frozen Full Mastery page preimage mismatch")
    for item in layout["header_patches"]:
        off = int(item["offset"], 0)
        before = bytes.fromhex(item["before"])
        after = bytes.fromhex(item["after"])
        if bytes(parent[off:off + len(before)]) != before:
            raise RuntimeError(f"{game} append header preimage mismatch at {item['offset']}")
        parent[off:off + len(after)] = after
    page[cfg["fm_hook_offset"]:cfg["fm_hook_offset"] + 5] = cfg["fm_hook_after"]
    strings = b"SDL2.dll\0SDL_GetWindowFlags\0"
    if cfg["strings_va"] - cfg["section_va"] != 0x1F00:
        raise RuntimeError("string placement mismatch")
    for off, wrapper in zip(cfg["wrapper_offsets"], WRAPPERS[game]):
        if len(wrapper) != 228:
            raise RuntimeError(f"{game} wrapper is not exactly 228 bytes")
        if any(page[off:off + len(wrapper)]):
            raise RuntimeError(f"{game} wrapper slot is not reserved zero space")
        page[off:off + len(wrapper)] = wrapper
    page[0x1F00:0x1F00 + len(strings)] = strings
    output = recompute_pe_checksum(bytes(parent + page))
    return output, bytes(page), {"origins_parent_sha256": cfg["base_sha256"][mode], "page_sha256": sha(page), "output_sha256": sha(output), "output_size": len(output)}


def emit(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=False)
    for game, cfg in ORACLE.items():
        companion = transform_companion(ORIGINS_DLL)
        for mode in ("collection_progression", "immediate_fixed"):
            output, page, hashes = build_mode(game, mode)
            preprice = cfg.get("cure_preprice_guard")
            stem = f"vv{game[-1]}_fullscreen_safe_candidate"
            (output_root / f"{stem}_{mode}.exe").write_bytes(output)
            (output_root / f"{stem}_{mode}_page.bin").write_bytes(page)
            (output_root / f"VVFP VV{game[-1]} Fullscreen Safe Candidate.dll").write_bytes(companion)
            manifest = {
                "id": stem, "game_id": game, "enabled": False, "catalog_hidden": True,
                "catalog_enabled": False, "supported_modes": ["collection_progression", "immediate_fixed"],
                "expanded_rejected": True, "mode": mode, "status": "disabled evidence only",
                "oracle_wrappers": ["0x%X" % x for x in cfg["wrapper_vas"]],
                "wrapper_length": 228, "strings": "SDL2.dll\\0SDL_GetWindowFlags\\0",
                "strings_va": "0x%X" % cfg["strings_va"], "hooks": {k: "E" + v[2].hex().upper()[2:] for k, v in cfg["hooks"].items()},
                "fullscreen_contract": {
                    "mask": "0x1001", "native_transition": "ECX=engine; push bool; call; ret4",
                    "owner_pid_centering": True,
                    "owner_status": "required companion-side contract; candidate disabled pending independent proof",
                },
                "shared_append_owner": "Origins; Full Mastery removal is required before Origins truncation",
                "companion": {
                    "filename": cfg["companion_name"], "sha256": sha(companion), "size": len(companion),
                    "parent_sha256": ORIGINS_DLL_SHA256, "restore_sha256": ORIGINS_DLL_SHA256,
                    "resource_201_items": 41, "resource_202_unchanged": True,
                    "install": "atomic candidate-owned replacement; exact parent restore on remove",
                },
                "cure_guard": {"va": "0x%X" % cfg["cure_guard"][0], "before": cfg["cure_guard"][1].hex().upper(), "after": cfg["cure_guard"][2].hex().upper()},
                "legacy_cure_containment": {
                    "status": (
                        "contained; command 5 is rejected before price/funds/legacy Cure, while commands 0-4 and command 7 remain bytewise on their certified paths"
                        if preprice else
                        "contained; Cure row is removed; command 5 remains withheld pending a dedicated pre-price rejection guard"
                    ),
                    **({"command5_preprice_rejection": {
                        "compare": {"va": "0x456A8D", "before": "83FB08", "after": "83FB05"},
                        "branch": {"va": "0x456A90", "before": "0F872FFFFFFF", "after": "0F842FFFFFFF"},
                        "target": "0x4569C5",
                        "legacy_deductions": ["0x456AD5", "0x456AB3"],
                        "legacy_cure": "0x456B9D",
                    }} if preprice else {}),
                    "full_heal_status": "pending; no replacement is enabled or catalog-visible",
                    "resource_202_unchanged": True,
                },
                "wrapper_sha256": [sha(w) for w in WRAPPERS[game]],
                "hashes": hashes,
            }
            (output_root / f"{stem}_{mode}.json").write_bytes(json_bytes(manifest))
        (output_root / f"vv{game[-1]}_fullscreen_safe_candidate_contract.json").write_bytes(json_bytes({"game_id": game, "enabled": False, "catalog_hidden": True, "oracle": cfg["wrapper_vas"], "owner_pid_centering": True}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    emit(args.output_root)


if __name__ == "__main__":
    main()
