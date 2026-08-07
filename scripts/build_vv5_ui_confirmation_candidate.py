"""Build the disabled VV5 UI/individual-transaction candidate evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from vv5_individual_transactions import transaction_contracts


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_BASE = ROOT / "data" / "vv5_origins_feature.json"
OUTPUT = ROOT / "outputs" / "vv5-ui-confirmation-candidate"
OUTPUT_MANIFEST = OUTPUT / "candidate.json"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_SIZE = 0x1000
TECH_EVENT = 13
DETAIL_EVENT = 13
DETAIL_NATIVE_HANDLER_VA = 0x44B560
CURRENT_DETAIL_HOOK_VA = 0x44BC20


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def active_payload() -> bytes:
    manifest = json.loads(ACTIVE_BASE.read_text(encoding="utf-8"))
    patch = next(item for item in manifest["patches"] if item["offset"] == "0xDB000")
    payload = bytes.fromhex(patch["after"]).ljust(PAYLOAD_SIZE, b"\0")
    if len(payload) != PAYLOAD_SIZE:
        raise RuntimeError(f"VV5 active Origins payload must be {PAYLOAD_SIZE:#x} bytes")
    return payload


def bound_payload() -> tuple[bytes, list[dict[str, str]]]:
    """Bind the exact native route without emitting an unguarded hook."""

    payload = active_payload()
    if payload[0x0B] != TECH_EVENT or payload[0xCB] != DETAIL_EVENT or payload[0x128] != DETAIL_EVENT:
        raise RuntimeError("VV5 UI event bytes do not match the native 13/13 binding")
    return payload, []


def build_manifest() -> dict[str, object]:
    original = active_payload()
    payload, changes = bound_payload()
    return {
        "id": "vv5_ui_confirmation_candidate",
        "game_id": "vv5",
        "name": "DISABLED Candidate: VV5 UI and Individual Confirmations",
        "enabled": False,
        "catalog_hidden": True,
        "catalog_enabled": False,
        "runtime_status": "pending; no package or player validation",
        "allowed_modes": ["collection_progression", "immediate_fixed"],
        "unsupported_patch_modes": [
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        ],
        "expanded_fail_closed": True,
        "dependencies": ["vv5_enable_origins_exclusive_features"],
        "source": {
            "stock_sha256": STOCK_SHA256,
            "active_base": "data/vv5_origins_feature.json",
            "active_payload_sha256": sha(original),
            "bound_payload_sha256": sha(payload),
        },
        "native_routing": {
            "message": 8,
            "tech": {
                "event": 13,
                "factory": "0x401BD0",
                "ownership": "0x40C680",
                "status": "native route preserved",
            },
            "detail": {
                "event": DETAIL_EVENT,
                "factory": "0x401BD0",
                "ownership": "0x40C680",
                "native_handler": f"0x{DETAIL_NATIVE_HANDLER_VA:X}",
                "current_emitted_hook": f"0x{CURRENT_DETAIL_HOOK_VA:X}",
                "status": "disabled pending exact guarded preimage for the native Detail handler",
            },
            "patches": changes,
            "call_convention": [
                "preserve ECX=EDI before native 0x44FA20 thiscall",
                "preserve native 0x401BD0 factory and 0x40C680 ownership registration",
                "preserve ret 8 and original handler fallback prologues",
            ],
        },
        "individual_actions": transaction_contracts(),
        "implementation": {
            "transaction_engine": "src/vv5_individual_transactions.py",
            "native_writer_policy": "native action writes are permitted only after postverify in the disabled candidate design",
            "save_policy": "no save reads or writes are performed by the reference engine",
        },
    }


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    OUTPUT_MANIFEST.write_text(json.dumps(build_manifest(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT_MANIFEST), "sha256": sha(OUTPUT_MANIFEST.read_bytes())}, indent=2))


if __name__ == "__main__":
    main()
