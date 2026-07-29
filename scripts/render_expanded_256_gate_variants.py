"""Render ignored, static-only 256-capacity audit images.

The script does not package or launch a game.  It renders the population patch
alone and with every currently enabled same-game feature, recording exact
hashes and patch ownership so collision and relocation checks are reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import identify, load_fun_patches, render_patched_bytes  # noqa: E402


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_exe")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    source = Path(args.source_exe)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    build = identify(source)
    enabled = [
        patch.id
        for patch in load_fun_patches()
        if patch.raw.get("game_id") == build.id
    ]

    results = []
    for mode in (
        "collection_progression",
        "immediate_fixed",
        "experimental_expanded_256",
        "experimental_expanded_256_progression",
    ):
        for label, feature_ids in (("base", []), ("all-current", enabled)):
            record = {
                "mode": mode,
                "variant": label,
                "feature_ids": feature_ids,
            }
            try:
                rendered, applied = render_patched_bytes(
                    source, build, mode, feature_ids
                )
                output = output_dir / f"{build.id}-{mode}-{label}.exe"
                output.write_bytes(rendered)
                record.update(
                    {
                        "status": "PASS",
                        "output": str(output),
                        "size": len(rendered),
                        "sha256": _sha256(rendered),
                        "applied_patch_count": len(applied),
                        "owner_counts": {
                            owner: sum(1 for patch in applied if patch["owner"] == owner)
                            for owner in sorted({patch["owner"] for patch in applied})
                        },
                    }
                )
            except Exception as exc:
                record.update(
                    {
                        "status": "STOP",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            results.append(record)

    payload = {
        "game_id": build.id,
        "source": str(source),
        "source_sha256": _sha256(source.read_bytes()),
        "enabled_same_game_features": enabled,
        "results": results,
    }
    (output_dir / f"{build.id}-render-ledger.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
