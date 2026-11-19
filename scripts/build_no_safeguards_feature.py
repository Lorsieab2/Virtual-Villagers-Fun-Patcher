"""Build "VVFP No Safeguards.dll" (native/vvfp_no_safeguards; No Safeguards for Island Events (and Additional Events
too), the game's own island events, all five games) and write its companion record, data/no_safeguards_companion.json
(source, destination, SHA-256), which vv_fun_patcher._attach_no_safeguards ships with each game's
vvN_island_events_any_time row.  The row itself is written elsewhere (scripts/build_island_event_content_features.py).

Each game's sites, and what they lift and keep, are in native/vvfp_no_safeguards/ns_vvN.inc
(docs/no-safeguards-island-events.md).  tests/test_no_safeguards.py checks every site against the stock executables
and runs the install by emulation.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP No Safeguards.dll"
DLL = ROOT / "assets" / "no_safeguards" / DLL_NAME
RECORD = ROOT / "data" / "no_safeguards_companion.json"


def record(dll_sha: str) -> dict:
    return {"source": f"assets/no_safeguards/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha}


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_no_safeguards.ps1")], check=True)
    dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    RECORD.write_text(json.dumps(record(dll_sha), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", RECORD.relative_to(ROOT))


if __name__ == "__main__":
    main()
