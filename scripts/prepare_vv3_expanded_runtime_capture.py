"""Dry-run-only VV3 Expanded-256 runtime capture preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv3_expanded_256_runtime_capture import (  # noqa: E402
    CaptureHarnessError,
    prepare_dry_run_receipt,
    receipt_bytes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight an explicitly supplied VV3 Modded 256 folder and print an unsigned pending checklist."
    )
    parser.add_argument("--dry-run", action="store_true", help="required; this harness has no launch or save-content mode")
    parser.add_argument("--evidence-json", required=True, type=Path)
    parser.add_argument("--catalog-root", required=True, type=Path)
    parser.add_argument("--game-folder", required=True, type=Path)
    parser.add_argument("--folder-inventory", required=True, type=Path)
    parser.add_argument("--modded-save-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("--dry-run is mandatory; launch/save capture is intentionally unavailable")
    try:
        receipt = prepare_dry_run_receipt(
            evidence_path=args.evidence_json,
            catalog_root=args.catalog_root,
            game_folder=args.game_folder,
            folder_inventory_path=args.folder_inventory,
            modded_save_root=args.modded_save_root,
        )
    except (CaptureHarnessError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "STOP", "runtime_go": False, "publication_ready": False, "error": str(exc)}, sort_keys=True))
        return 1
    sys.stdout.buffer.write(receipt_bytes(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
