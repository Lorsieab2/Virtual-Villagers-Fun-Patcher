"""Generate the disabled VV4 Full Heal / Cure All metadata contract.

This generator intentionally refuses to emit an executable until the exact
VV4 command-5 boundary and native helper layout have independent disassembly
evidence.  It is still the source of truth for the candidate's transaction,
composition, message, and fail-closed metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate.json"
MAP = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate_map.json"
DOC = ROOT / "docs/vv4-full-heal-candidate.md"
STOCK_SHA256 = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8"))


def generate(output_root: Path | None = None) -> tuple[Path, Path, Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    artifact_map = json.loads(MAP.read_text(encoding="utf-8-sig"))
    if manifest["enabled"] or not manifest["catalog_hidden"] or manifest["catalog_enabled"]:
        raise RuntimeError("VV4 Full Heal must remain disabled and catalog-hidden pending recertification")
    if manifest["source"]["stock_sha256"] != STOCK_SHA256 or artifact_map["source"]["sha256"] != STOCK_SHA256:
        raise RuntimeError("VV4 Full Heal stock fingerprint is not immutable")
    hook = manifest["hook"]
    if hook["hook_before_parent"] != "E941FEFFFF9090" or hook["hook_after"] != "E9EC792B009090":
        raise RuntimeError("VV4 Full Heal command-5 parent hook guard is not immutable")
    if hook["shim_bytes"] != "83F8050F854C84D4FFE9F2000000" or hook["transaction_entry_va"] != "0x741100":
        raise RuntimeError("VV4 Full Heal command gate shim is not immutable")
    if not hook["unknown_until_recertified"]:
        raise RuntimeError("VV4 Full Heal cannot be enabled before native helper recertification")
    if output_root is None:
        root = ROOT
    else:
        root = Path(output_root).resolve()
    out_manifest = root / MANIFEST.relative_to(ROOT)
    out_map = root / MAP.relative_to(ROOT)
    out_doc = root / DOC.relative_to(ROOT)
    _write(out_manifest, manifest)
    _write(out_map, artifact_map)
    doc = DOC.read_text(encoding="utf-8")
    out_doc.parent.mkdir(parents=True, exist_ok=True)
    out_doc.write_bytes(doc.encode("utf-8"))
    return out_manifest, out_map, out_doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    generate(args.output_root)


if __name__ == "__main__":
    main()
