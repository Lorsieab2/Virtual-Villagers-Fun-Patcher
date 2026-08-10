"""Build, validate, and in-memory render the disabled VV3 save repair."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "candidates" / "vv3_full256_serializer_candidate.json"
SOURCE = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
PARENTS = (
    (
        "experimental_expanded_256",
        "657D321B2F1E9E6D6C223DB1FF0BBA38C2D761A97A6E7F21B98CE1826531A848",
        "322A0D00",
        "27F40C00",
        "585EC60285F20A55658B5CB77E8A81D5B6A632B3A399058F01EB732B4777976B",
    ),
    (
        "experimental_expanded_256_progression",
        "3A35745C00102A0964DF6E81B77707539C5BDC03501011F43FF1D2809015B211",
        "3CA50D00",
        "316F0D00",
        "3B93CFDD98112D54F4457AA4E84838F98E577DF0AF1B9C20903E1C4CC8F276A8",
    ),
)
MANIFEST_ROWS_SHA256 = "04B93127BC4D5C6787AB013DE9205813D44947DBC16A370DBC234C06588AC3FB"

SERIALIZER = bytes.fromhex(
    "5355565783EC048D7114E851FBC6FF85C0745A89042431DB31FFBD000100008A86"
    "100F000084C0742489F1E8A0CDC9FF8B04248D84386C7800005089F1E81EC4C9FF"
    "84C074274381C71C01000081C68C1F00004D75C981FB00010000730B8B0424C684"
    "386C78000000B001EB0231C083C4045F5E5D5BC20400"
)
READER = bytes.fromhex(
    "5355565783EC088D7914E851F9C6FF85C0746C89042431DB81FB00010000731589"
    "DE69F61C01000080BC306C78000000740343EBE3895C240489FEBD0001000089F1"
    "E8B9CDC9FF81C68C1F00004D75F031DB3B5C2404732389DE69F61C0100008B0424"
    "8D84306C7800005089F9E8BED5C9FF4381C78C1F0000EBD7B001EB0231C083C408"
    "5F5E5D5BC20400"
)
GATE = bytes.fromhex(
    "FF742404E837FCFFFF84C07403C2040083C40831C05F5EC20400"
)
PAGE_SHA256 = "9F82D59D1436B17ACA69CD637AB40D44DF35323DA46600AAA5FD07315C249B64"
SECTION_HEADER = bytes.fromhex(
    "2E767633737600000010000000903B000010000000C00C00000000000000000000"
    "00000020000060"
)

WRITER_CALLSITES = (
    ("settings_tail_manager_nonnull", "settings-tail", "EDI==0", "ESI!=0", "ESI+0x12F24", "0x88", "0", "0x27C7D", "0x427C7D", "E8AEB8FDFF", "E87E173900"),
    ("settings_tail_manager_null", "settings-tail", "EDI==0", "ESI==0", "0", "0x88", "0", "0x27C92", "0x427C92", "E899B8FDFF", "E869173900"),
    ("full_village_manager_nonnull", "full-village", "EDI!=0", "ESI!=0", "ESI+0x8", "caller size: 0x12F1C stock or expanded size", "nonzero", "0x27D6C", "0x427D6C", "E8BFB7FDFF", "E88F163900"),
    ("full_village_manager_null", "full-village", "EDI!=0", "ESI==0", "0", "caller full size: 0x12F1C stock or expanded size", "nonzero", "0x27D81", "0x427D81", "E8AAB7FDFF", "E87A163900"),
)
ABIS = (
    ("drain_record", "0x455DD0", "0x455E0A", "26C8489FBAB307D110D1A8045368ECF16DD12F937F6EDE322097445BF2CEAAB1", "thiscall ECX=live; no args; ret; no status"),
    ("manager_getter", "0x428B60", "0x428BCD", "C5B6EE39E6DE419C32D141C5E42037261E26DE253ED38F874EC3FD9E3312E4A0", "no args; EAX=singleton or null"),
    ("compact_writer", "0x455460", "0x4554F5", "C71380CCF4F747B79B36C4BB2BE3EC9716AEF0EE3A6BC972AA2CFDB6563209FD", "thiscall ECX=live; push compact; ret 4; AL=1"),
    ("reset_record", "0x456000", "0x45611C", "8ADD4452CE6228B03A1ED53249C5DA3E6B3FBEF9864527F0EB423EC66E658024", "thiscall ECX=live; no args; ret; no status"),
    ("compact_reader", "0x456830", "0x4568D2", "FF9DFFE894F90B9C47BDDD92A29253CCF78A8277DC7C97E1198528093257C959", "thiscall ECX=live; push compact; ret 4; AL=1"),
)


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def rel32(source: int, target: int) -> str:
    return "E8" + struct.pack("<i", target - (source + 5)).hex().upper()


def section_page() -> bytes:
    page = bytearray(0x1000)
    page[: len(SERIALIZER)] = SERIALIZER
    page[0x200 : 0x200 + len(READER)] = READER
    page[0x3C0 : 0x3C0 + len(GATE)] = GATE
    require(hashlib.sha256(page).hexdigest().upper() == PAGE_SHA256, "section page digest")
    return bytes(page)


def _writer_rows() -> list[dict[str, object]]:
    parent_hashes = [parent[1] for parent in PARENTS]
    return [
        {
            "id": identifier,
            "route": route,
            "route_condition": route_condition,
            "manager_condition": manager_condition,
            "body": body,
            "size": size,
            "save_id": save_id,
            "raw": raw,
            "va": va,
            "preimage": preimage,
            "expected": expected,
            "validated_parent_sha256": parent_hashes,
            "emitted": None,
        }
        for (
            identifier,
            route,
            route_condition,
            manager_condition,
            body,
            size,
            save_id,
            raw,
            va,
            preimage,
            expected,
        ) in WRITER_CALLSITES
    ]


def model() -> dict[str, object]:
    return {
        "schema": "vvfp.vv3_full256_serializer_static_candidate",
        "schema_version": 2,
        "candidate_id": "vv3-full256-serializer-reader-disabled",
        "status": "static_serializer_reader_go_writer_rollback_stop",
        "enabled": False,
        "catalog_visible": False,
        "native_output": False,
        "source_sha256": SOURCE,
        "expanded_manifest": {
            "path": "data/expanded_256.json",
            "row_count": 1263,
            "rows_sha256": MANIFEST_ROWS_SHA256,
        },
        "parents": [
            {
                "mode": mode,
                "sha256": parent_sha,
                "size": "0xCC000",
                "sections": 6,
                "size_of_image": "0x3B9000",
                "pe_checksum_before": checksum_before,
                "result_sha256": result_sha,
                "result_size": "0xCD000",
                "result_sections": 7,
                "result_size_of_image": "0x3BA000",
                "pe_checksum_after": checksum_after,
            }
            for mode, parent_sha, checksum_before, checksum_after, result_sha in PARENTS
        ],
        "pe_guards": {
            "e_lfanew": "0x108",
            "machine": "0x014C",
            "optional_magic": "0x010B",
            "optional_size": "0xE0",
            "image_base": "0x00400000",
            "section_alignment": "0x1000",
            "file_alignment": "0x1000",
            "size_of_headers": "0x1000",
            "section_count_raw": "0x10E",
            "section_count_before": "0600",
            "section_count_after": "0700",
            "size_of_image_raw": "0x158",
            "size_of_image_before": "00903B00",
            "size_of_image_after": "00A03B00",
            "checksum_raw": "0x160",
        },
        "section_plan": {
            "name": ".vv3sv",
            "header_raw": "0x2F0",
            "raw_start": "0xCC000",
            "raw_end": "0xCD000",
            "rva": "0x3B9000",
            "va": "0x7B9000",
            "size": "0x1000",
            "characteristics": "RX",
            "characteristics_value": "0x60000020",
            "header_guard": "00" * 40,
            "header_bytes": SECTION_HEADER.hex().upper(),
            "section_sha256": PAGE_SHA256,
        },
        "hooks": [
            {
                "id": "serializer_failure_gate",
                "stock_function": "0x45EF80",
                "raw": "0x27D57",
                "va": "0x427D57",
                "preimage": "E824720300",
                "target": "0x7B93C0",
                "after": "E864163900",
                "sole_callsite": True,
            },
            {
                "id": "deserializer_reader",
                "stock_function": "0x45C860",
                "raw": "0x28A4C",
                "va": "0x428A4C",
                "preimage": "E80F3E0300",
                "target": "0x7B9200",
                "after": "E8AF073900",
                "sole_callsite": True,
            },
        ],
        "exact_routines": {
            "serializer": {
                "va": "0x7B9000",
                "raw": "0xCC000",
                "length": len(SERIALIZER),
                "bytes": SERIALIZER.hex().upper(),
                "sha256": hashlib.sha256(SERIALIZER).hexdigest().upper(),
            },
            "deserializer": {
                "va": "0x7B9200",
                "raw": "0xCC200",
                "length": len(READER),
                "bytes": READER.hex().upper(),
                "sha256": hashlib.sha256(READER).hexdigest().upper(),
            },
            "serializer_failure_gate": {
                "va": "0x7B93C0",
                "raw": "0xCC3C0",
                "length": len(GATE),
                "bytes": GATE.hex().upper(),
                "sha256": hashlib.sha256(GATE).hexdigest().upper(),
            },
        },
        "abis": [
            {"id": identifier, "start": start, "end": end, "sha256": sha, "contract": contract}
            for identifier, start, end, sha, contract in ABIS
        ],
        "wrapper_model": {
            "compact_base": "call 0x428B60 then EAX+0x786C; formal serializer/deserializer pointer is ignored",
            "record_size": "0x11C",
            "logical_indices": "0..255",
            "padding": "256..259 forbidden",
            "serializer": [
                "ECX=live+0x14; save caller argument",
                "call 0x428B60; null => AL=0",
                "for exactly 256 live records apply active/current filters",
                "ECX=live; call 0x455DD0",
                "compact=singleton+0x786C+packed*0x11C",
                "push compact; ECX=live; call 0x455460; AL=0 => fail",
                "terminator only when packed_count<256",
                "count==256 returns AL=1 without tail write",
            ],
            "deserializer": [
                "ECX=live+0x14; call 0x428B60; null => AL=0",
                "scan no more than 256 compact records for a zero terminator",
                "exactly 256 unterminated compact records are accepted",
                "reset exactly 256 live records through 0x456000",
                "decode exactly the bounded compact count through 0x456830",
                "record 257 and tail are never read or written",
            ],
            "register_stack_gate": "wrappers preserve EBX/ESI/EDI/EBP and restore ESP exactly; compact helpers pop one argument with ret 4",
            "serializer_bytes": SERIALIZER.hex().upper(),
            "deserializer_bytes": READER.hex().upper(),
            "gate_bytes": GATE.hex().upper(),
            "section_sha256": PAGE_SHA256,
        },
        "caller_failure_gate": {
            "load_caller_tests_al": True,
            "save_caller_tests_al": True,
            "save_caller_patch_raw": "0x27D57",
            "save_caller_preimage": "E824720300",
            "save_caller_after": "E864163900",
            "recoverable_failure": True,
            "reason": "reviewed gate returns through the existing caller failure epilogue when serializer AL is zero",
        },
        "atomic_writer_plan": {
            "classification": "disabled_plan_pending_exact_writer",
            "stock_writer": "0x403530",
            "wrapper_va": "0x7B9400",
            "wrapper_raw": "0xCC400",
            "callsites": _writer_rows(),
            "transaction": [
                "sibling temporary path without numeric save slot",
                "CREATE_NEW plus WRITE_THROUGH",
                "write exact expanded file",
                "flush close and reopen no-follow",
                "verify exact size and authenticated integrity",
                "existing final uses ReplaceFileA flags 0",
                "absent final uses MoveFileExA WRITE_THROUGH without replace-existing",
                "fatal non-returning failure until every caller checks result",
            ],
            "dynamic_api_resolver_bytes": None,
            "wrapper_bytes": None,
            "wrapper_sha256": None,
            "import_changes": None,
            "enabled": False,
            "native_output": False,
            "blocker": "exact atomic writer and checked caller handling remain unproved",
        },
        "whole_load_rollback": {
            "status": "STOP",
            "hook_raw": None,
            "hook_preimage": None,
            "hook_after": None,
            "snapshot_bytes": None,
            "rollback_bytes": None,
            "final_sha256": None,
        },
        "uninstall_ledger": {
            "restore_hooks": [
                {"raw": "0x27D57", "bytes": "E824720300"},
                {"raw": "0x28A4C", "bytes": "E80F3E0300"},
            ],
            "restore_section_header": "00" * 40,
            "truncate_to": "0xCC000",
            "checksum_restore": {mode: checksum_before for mode, _, checksum_before, _, _ in PARENTS},
            "order": [
                "restore and verify both hook preimages",
                "restore section count and SizeOfImage",
                "restore and verify original section header bytes",
                "truncate only candidate-owned 0xCC000..0xCD000",
                "restore parent checksum",
            ],
        },
        "decision": {
            "static_layout_go": True,
            "serializer_reader_static_go": True,
            "atomic_writer_go": False,
            "whole_load_rollback_go": False,
            "native_output": False,
            "enabled": False,
            "runtime_go": False,
            "player_go": False,
            "publication_ready": False,
            "status": "STOP",
        },
    }


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def build() -> dict[str, object]:
    value = model()
    value["canonical_sha256"] = hashlib.sha256(canonical_bytes(value)).hexdigest().upper()
    return value


def validate(value: dict[str, object] | None = None) -> dict[str, object]:
    observed = value
    if observed is None:
        observed = json.loads(OUTPUT.read_text(encoding="utf-8"))
    require(observed == build(), "candidate model is stale")
    expanded = json.loads((ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8"))["games"]["vv3"]
    rows = expanded["patches"]
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest().upper()
    require(expanded["patch_count"] == 1263 and len(rows) == 1263, "VV3 manifest row count")
    require(digest == MANIFEST_ROWS_SHA256, "VV3 manifest row digest")
    return observed


def validate_writer_callsites(value: dict[str, object]) -> bool:
    return value["atomic_writer_plan"]["callsites"] == _writer_rows()


def _checksum(data: bytearray, offset: int) -> int:
    struct.pack_into("<I", data, offset, 0)
    total = 0
    padded = data + (b"\0" if len(data) % 2 else b"")
    for index in range(0, len(padded), 2):
        total += padded[index] | (padded[index + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(data)) & 0xFFFFFFFF


def render_candidate(parent: bytes | bytearray, mode: str) -> bytes:
    value = validate()
    parent_row = next((row for row in value["parents"] if row["mode"] == mode), None)
    require(parent_row is not None, "unknown parent mode")
    parent_bytes = bytes(parent)
    require(len(parent_bytes) == 0xCC000, "wrong parent size")
    require(hashlib.sha256(parent_bytes).hexdigest().upper() == parent_row["sha256"], "wrong parent")
    work = bytearray(parent_bytes)
    guards = value["pe_guards"]
    require(work[:2] == b"MZ", "missing MZ")
    pe = struct.unpack_from("<I", work, 0x3C)[0]
    require(pe == 0x108 and work[pe : pe + 4] == b"PE\0\0", "PE header")
    require(struct.unpack_from("<H", work, pe + 4)[0] == 0x14C, "machine")
    require(struct.unpack_from("<H", work, pe + 20)[0] == 0xE0, "optional size")
    optional = pe + 24
    require(struct.unpack_from("<H", work, optional)[0] == 0x10B, "optional magic")
    require(struct.unpack_from("<I", work, optional + 28)[0] == 0x400000, "image base")
    require(struct.unpack_from("<I", work, optional + 32)[0] == 0x1000, "section alignment")
    require(struct.unpack_from("<I", work, optional + 36)[0] == 0x1000, "file alignment")
    require(struct.unpack_from("<I", work, optional + 60)[0] == 0x1000, "headers size")
    require(work[0x10E:0x110].hex().upper() == guards["section_count_before"], "section count")
    require(work[0x158:0x15C].hex().upper() == guards["size_of_image_before"], "SizeOfImage")
    require(work[0x160:0x164].hex().upper() == parent_row["pe_checksum_before"], "checksum preimage")
    require(work[0x2F0:0x318] == b"\0" * 40, "section header preimage")
    for hook in value["hooks"]:
        raw = int(hook["raw"], 0)
        before = bytes.fromhex(hook["preimage"])
        require(work[raw : raw + len(before)] == before, f"{hook['id']} preimage")

    work[0x10E:0x110] = bytes.fromhex(guards["section_count_after"])
    work[0x158:0x15C] = bytes.fromhex(guards["size_of_image_after"])
    work[0x2F0:0x318] = SECTION_HEADER
    for hook in value["hooks"]:
        raw = int(hook["raw"], 0)
        work[raw : raw + 5] = bytes.fromhex(hook["after"])
    work.extend(section_page())
    checksum = _checksum(work, 0x160)
    struct.pack_into("<I", work, 0x160, checksum)
    require(work[0x160:0x164].hex().upper() == parent_row["pe_checksum_after"], "checksum result")
    require(len(work) == int(parent_row["result_size"], 0), "candidate size")
    require(hashlib.sha256(work).hexdigest().upper() == parent_row["result_sha256"], "candidate digest")
    return bytes(work)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--mode", choices=[parent[0] for parent in PARENTS])
    args = parser.parse_args(argv)
    value = build()
    if args.check:
        target = args.output or OUTPUT
        observed = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None
        require(observed == value, "candidate model is stale")
        validate(observed)
        return 0
    if args.dry_run:
        validate()
        suffix = ""
        if args.parent:
            require(args.mode is not None, "--mode is required with --parent")
            rendered = render_candidate(args.parent.read_bytes(), args.mode)
            suffix = f"; source-bound candidate {hashlib.sha256(rendered).hexdigest().upper()}"
        print(
            "VV3 full-256 serializer/reader candidate: STOP "
            f"(static repair valid; atomic writer/whole-load rollback/runtime/player disabled{suffix})"
        )
        return 0
    raw = canonical_bytes(value)
    if args.output:
        args.output.write_bytes(raw)
    else:
        print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
