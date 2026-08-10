#!/usr/bin/env python3
"""Validate and render the disabled VV4 full-256 serializer/reader candidate.

The renderer is deliberately in-memory only.  It accepts one exact expanded
parent, applies the reviewed serializer/reader repair, and recomputes the PE
checksum.  It does not install the still-unproved atomic writer and it never
writes an executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data/candidates/vv4_full256_serializer_static_candidate.json"
PARENT_SHA = "3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1"

WRAPPER = bytes.fromhex(
    "5355565731DB31FF8D7144BD0001000080BEC41C000000742F80BEC71C00000075"
    "2689F1E877DABEFFE842EEBAFF85C0743C8D843868C800005089F1E8EFCABEFF43"
    "81C70401000081C63C2E00004D75BF81FB000100007311E812EEBAFF85C0740CC6"
    "843868C8000000B001EB0231C05F5E5D5BC20400"
)
READER = bytes.fromhex(
    "5356578D794489FEBB0001000089F1E88CC7BEFF81C63C2E00004B75F031DB81FB"
    "000100007333E844EDBAFF85C0742E89DE69F60401000080BC3068C80000007418"
    "8D843068C800005089F9E88FCABEFF4381C73C2E0000EBC5B001EB0231C05F5E5B"
    "C20400"
)
GATE = bytes.fromhex(
    "FF742404E877FEFFFF84C07403C2040083C40831C05F5EC20400"
)
PAGE_SHA256 = "F33DEFF4EF943EB4371AFD3AC80F3F35BC1DB21865ADCC5F115BDF2E20A37D45"
FINAL_SHA256 = "364E35167E4DA8D9407030E42D41306A78FB50B73C7532B2D5166729EA447C43"


def require(value: object, message: str) -> None:
    if not value:
        raise ValueError(message)


def rel32(source: int, target: int, opcode: int = 0xE8) -> str:
    return bytes([opcode]).hex().upper() + struct.pack(
        "<i", target - (source + 5)
    ).hex().upper()


def section_header() -> bytes:
    header = bytearray(40)
    header[:8] = b".vv4x\0\0\0"
    struct.pack_into("<I", header, 8, 0x1000)
    struct.pack_into("<I", header, 12, 0x471000)
    struct.pack_into("<I", header, 16, 0x1000)
    struct.pack_into("<I", header, 20, 0xE3000)
    struct.pack_into("<I", header, 36, 0x60000020)
    return bytes(header)


def section_page() -> bytes:
    page = bytearray(0x1000)
    page[0 : len(WRAPPER)] = WRAPPER
    page[0x100 : 0x100 + len(READER)] = READER
    page[0x180 : 0x180 + len(GATE)] = GATE
    require(hashlib.sha256(page).hexdigest().upper() == PAGE_SHA256, "section page digest")
    return bytes(page)


def _pe_checksum(data: bytearray, checksum_offset: int) -> int:
    struct.pack_into("<I", data, checksum_offset, 0)
    total = 0
    padded = data + (b"\0" if len(data) % 2 else b"")
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(data)) & 0xFFFFFFFF


def validate(path: Path = MODEL) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(data["status"] == "static_serializer_reader_go_writer_stop", "status")
    require(
        not any(
            data[key]
            for key in (
                "enabled",
                "catalog_visible",
                "native_output",
                "runtime_go",
                "player_go",
                "publication_eligible",
            )
        ),
        "candidate must remain disabled",
    )
    require(
        data["parent"]
        == {
            "mode": "experimental_expanded_256",
            "size": 0xE3000,
            "sha256": PARENT_SHA,
            "exclusive": True,
        },
        "exclusive parent",
    )
    require(
        data["rejected_composed_parents"]
        == ["full_mastery", "full_heal", "fullscreen", "running"],
        "composed-parent rejection",
    )
    require(
        data["ledger_bindings"]["vv4"]
        == {
            "count": 13,
            "digest": "CEE01F4AEC59CB1CEE0F42E3DDDB3A24615261E628ED0629C1BFAABF421A897D",
        },
        "VV4 ledger",
    )

    section = data["section"]
    require(
        section
        == {
            "name": ".vv4x",
            "header_raw": 0x2C0,
            "raw_start": 0xE3000,
            "raw_end": 0xE4000,
            "raw_size": 0x1000,
            "rva": 0x471000,
            "va": 0x871000,
            "virtual_size": 0x1000,
            "characteristics": "RX",
            "characteristics_value": "0x60000020",
            "old_size_of_image": 0x471000,
            "new_size_of_image": 0x472000,
            "header_guard": "00" * 40,
            "final_header_bytes": section_header().hex().upper(),
            "page_sha256": PAGE_SHA256,
        },
        "section layout",
    )
    pe = data["pe_guards"]
    require(
        pe
        == {
            "e_lfanew": 0x100,
            "machine": "0x014C",
            "optional_magic": "0x010B",
            "optional_size": 0xE0,
            "image_base": "0x00400000",
            "section_alignment": "0x1000",
            "file_alignment": "0x1000",
            "size_of_headers": "0x1000",
            "section_count_offset": 0x106,
            "section_count_before": 5,
            "section_count_after": 6,
            "size_of_image_offset": 0x150,
            "checksum_offset": 0x158,
            "checksum_before": "F6A80E00",
            "checksum_after": "4FDF0E00",
        },
        "PE guards",
    )

    expected_hooks = [
        (
            "serializer_failure_gate",
            0x41F125,
            0x1F125,
            "E8766F0400",
            0x871180,
            "E856204500",
            0xE3180,
        ),
        (
            "deserializer_reader",
            0x41FD34,
            0x1FD34,
            "E8D7630400",
            0x871100,
            "E8C7134500",
            0xE3100,
        ),
    ]
    require(len(data["hooks"]) == len(expected_hooks), "hook count")
    for row, expected in zip(data["hooks"], expected_hooks):
        actual = tuple(
            row[key]
            for key in ("name", "va", "raw", "before", "target", "after", "wrapper_raw")
        )
        require(actual == expected, "hook pin")
        require(rel32(expected[1], expected[4]) == expected[5], "rel32 mismatch")

    helpers = {
        "drain": (
            "0x45EAA0",
            "0x45EAD9",
            "13BBB3D0FB0BE6970B5EB454B706229CF536487C9C5481527FE64F8EE17B5E75",
        ),
        "singleton": (
            "0x41FE70",
            "0x41FEEA",
            "CFD2040568A260D38E125A6973C4B849FBBA0440553A2A301DDA79C0317BBE08",
        ),
        "encode": (
            "0x45DB30",
            "0x45DBD1",
            "EB2932E1BAED9F12AD14928677DC1A3248DF9A0615A7C67A400A1604474844E3",
        ),
        "reset": (
            "0x45D8A0",
            "0x45D9AC",
            "BA84FBE6CC322E112B7CF8956EC433516E5623E36767FD35578CB2691A0FE469",
        ),
        "decode": (
            "0x45DBE0",
            "0x45DCD0",
            "68A1C70F2CE2F3EA627FF17F55A5D6A22C2182CE248B664440BB36EDD9358A07",
        ),
    }
    for name, pin in helpers.items():
        require(
            tuple(data["d353_helpers"][name][key] for key in ("ea", "end", "sha256"))
            == pin,
            "D353 helper pin",
        )

    exact_routines = data["exact_routines"]
    for name, va, raw, payload, digest in (
        (
            "serializer",
            0x871000,
            0xE3000,
            WRAPPER,
            "66EDFABF000302C9AD13D1794D3A6C5738DB0A78162A6FDC23406339D6187FE4",
        ),
        (
            "deserializer",
            0x871100,
            0xE3100,
            READER,
            "DDCEE8650898E484FE569C28C0473D4377FF93739C9CA45E3A3238D95975C596",
        ),
        (
            "serializer_failure_gate",
            0x871180,
            0xE3180,
            GATE,
            "7C73BF244E95BD0C0AD7FDB2D8F6CD47854F2C64A5FA2E1A3FE660E6BADFA4A1",
        ),
    ):
        routine = exact_routines[name]
        require(
            routine
            == {
                "va": va,
                "raw": raw,
                "length": len(payload),
                "bytes": payload.hex().upper(),
                "sha256": digest,
            },
            f"{name} routine",
        )

    for name, registers in (
        ("serializer", ["EBX", "EBP", "ESI", "EDI"]),
        ("deserializer", ["EBX", "ESI", "EDI"]),
    ):
        wrapper = data["wrapper_model"][name]
        require(
            wrapper["preserves"] == registers
            and wrapper["bound"] == 256
            and wrapper["return"] == "AL boolean; ret 4",
            "ABI model",
        )
        require(
            wrapper["singleton"]
            == {
                "function": "0x41FE70",
                "compact_base_offset": "0xC868",
                "null_result": "AL=0",
            },
            "singleton model",
        )
        require(len(wrapper["instruction_model"]) >= 9, "complete instruction model")
    require(
        data["wrapper_model"]["serializer"]["terminator"]
        == "write exactly one zero byte only when packed_count < 256",
        "terminator",
    )
    require(
        data["wrapper_model"]["deserializer"]["full_256_unterminated"]
        == "success without reading record 257 or tail",
        "reader bound",
    )
    require(
        data["wrapper_model"]["deserializer"]["clear_before_reset"]
        == "clear all 256 live records before resetting load index",
        "clear/reset order",
    )

    writer = data["writer_model"]
    require(
        writer["status"] == "blocked_pending_d355"
        and writer["entry"]
        == {
            "ea": "0x4039B0",
            "raw": 0x39B0,
            "before": "81EC04020000",
            "replacement_kind": "complete_entry_e9_rel32_plus_nop",
            "target": None,
            "after": None,
        },
        "writer entry guard",
    )
    atomic = writer["atomic_contract"]
    require(
        atomic["temp_create"] == "sibling CREATE_NEW | WRITE_THROUGH"
        and atomic["final_exists"] == "ReplaceFileA(final,temp,backup,0,NULL,NULL)",
        "atomic replacement contract",
    )
    require(
        atomic["required_sequence"]
        == [
            "exact write",
            "flush",
            "checked CloseHandle write handle",
            "no-follow reopen",
            "reject reparse point",
            "verify volume serial and FileId identity",
            "GetFileSizeEx equals 24 plus body",
            "compare complete 24-byte header and complete body",
            "checked CloseHandle verification handle",
        ],
        "verification sequence",
    )
    require(
        "without MOVEFILE_REPLACE_EXISTING" in atomic["final_absent"]
        and "leave it untouched and fail fatally" in atomic["final_absent"],
        "raced final policy",
    )
    require(
        atomic["temp_cleanup"] == "delete only identity-verified owned temp"
        and atomic["directory_entry_power_loss_durability"]
        == "unsupported and unproved on Windows API contract",
        "cleanup/durability policy",
    )
    require(
        atomic["api_resolution"] == "dynamic"
        and atomic["failure_policy"]
        == "fatal process abandon until all callers prove checked failure handling",
        "writer safety policy",
    )
    require(
        writer["resolver_bytes"] is None
        and writer["page_bytes"] is None
        and writer["final_sha256"] is None,
        "writer placeholders must remain null",
    )
    require(
        writer["caller_ledger"]
        == {
            "status": "complete_addresses_unproved_handling_stop",
            "sites": [
                "0x41F04D",
                "0x41F060",
                "0x41F13A",
                "0x41F14F",
                "0x41F160",
                "0x41E4C0",
            ],
            "nonreturn_primitive": None,
        },
        "writer caller ledger",
    )
    require(
        data["blocked_evidence"]
        == [
            "proved checked failure handling at all six writer caller sites or an authenticated nonreturn primitive",
            "D355 exact dynamic resolver and atomic writer bytes",
            "runtime save/load/reload and full-256 fault receipts",
            "directory-entry power-loss durability is unsupported and unproved",
        ],
        "blocker inventory",
    )
    require(
        data["final"]
        == {
            "serializer_bytes": WRAPPER.hex().upper(),
            "deserializer_bytes": READER.hex().upper(),
            "gate_bytes": GATE.hex().upper(),
            "section_sha256": PAGE_SHA256,
            "candidate_size": 0xE4000,
            "candidate_sha256": FINAL_SHA256,
        },
        "final static candidate pins",
    )
    require(
        data["uninstall"]["order"]
        == [
            "restore writer hook if a future writer is separately proved",
            "restore serializer caller",
            "restore deserializer caller",
            "restore section count and SizeOfImage",
            "remove .vv4x header",
            "truncate to parent size",
            "restore PE checksum",
        ]
        and data["uninstall"]["requires_exact_candidate_hash"] is True
        and data["uninstall"]["candidate_sha256"] == FINAL_SHA256
        and data["uninstall"]["checksum_before"] == "F6A80E00"
        and data["uninstall"]["checksum_after"] == "4FDF0E00",
        "uninstall proof",
    )
    require(section_page(), "section page")
    return data


def render_candidate(parent: bytes | bytearray, path: Path = MODEL) -> bytes:
    data = validate(path)
    parent_bytes = bytes(parent)
    require(len(parent_bytes) == 0xE3000, "wrong parent size")
    require(hashlib.sha256(parent_bytes).hexdigest().upper() == PARENT_SHA, "wrong parent")
    work = bytearray(parent_bytes)

    require(work[:2] == b"MZ", "missing MZ")
    pe_offset = struct.unpack_from("<I", work, 0x3C)[0]
    guards = data["pe_guards"]
    require(pe_offset == guards["e_lfanew"] and work[pe_offset : pe_offset + 4] == b"PE\0\0", "PE header")
    require(struct.unpack_from("<H", work, pe_offset + 4)[0] == 0x14C, "machine")
    require(struct.unpack_from("<H", work, pe_offset + 20)[0] == 0xE0, "optional size")
    optional = pe_offset + 24
    require(struct.unpack_from("<H", work, optional)[0] == 0x10B, "optional magic")
    require(struct.unpack_from("<I", work, optional + 28)[0] == 0x400000, "image base")
    require(struct.unpack_from("<I", work, optional + 32)[0] == 0x1000, "section alignment")
    require(struct.unpack_from("<I", work, optional + 36)[0] == 0x1000, "file alignment")
    require(struct.unpack_from("<I", work, optional + 60)[0] == 0x1000, "headers size")

    section = data["section"]
    require(work[section["header_raw"] : section["header_raw"] + 40] == b"\0" * 40, "section header preimage")
    require(struct.unpack_from("<H", work, guards["section_count_offset"])[0] == guards["section_count_before"], "section count")
    require(struct.unpack_from("<I", work, guards["size_of_image_offset"])[0] == section["old_size_of_image"], "SizeOfImage")
    require(work[guards["checksum_offset"] : guards["checksum_offset"] + 4].hex().upper() == guards["checksum_before"], "checksum preimage")
    for hook in data["hooks"]:
        before = bytes.fromhex(hook["before"])
        require(work[hook["raw"] : hook["raw"] + len(before)] == before, f"{hook['name']} preimage")

    struct.pack_into("<H", work, guards["section_count_offset"], guards["section_count_after"])
    struct.pack_into("<I", work, guards["size_of_image_offset"], section["new_size_of_image"])
    work[section["header_raw"] : section["header_raw"] + 40] = section_header()
    for hook in data["hooks"]:
        after = bytes.fromhex(hook["after"])
        work[hook["raw"] : hook["raw"] + len(after)] = after
    work.extend(section_page())

    checksum_offset = guards["checksum_offset"]
    checksum = _pe_checksum(work, checksum_offset)
    struct.pack_into("<I", work, checksum_offset, checksum)
    require(work[checksum_offset : checksum_offset + 4].hex().upper() == guards["checksum_after"], "checksum result")
    require(len(work) == data["final"]["candidate_size"], "candidate size")
    require(hashlib.sha256(work).hexdigest().upper() == data["final"]["candidate_sha256"], "candidate digest")
    return bytes(work)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--parent", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    validate(args.model)
    require(args.dry_run, "disabled model accepts only --dry-run")
    suffix = ""
    if args.parent:
        candidate = render_candidate(args.parent.read_bytes(), args.model)
        suffix = f"; source-bound candidate {hashlib.sha256(candidate).hexdigest().upper()}"
    print(
        "VV4 full-256 serializer/reader candidate: STOP "
        f"(static repair valid; atomic writer/native/runtime/player disabled{suffix})"
    )


if __name__ == "__main__":
    main()
