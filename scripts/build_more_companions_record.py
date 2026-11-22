"""Build "VVFP More Companions.dll" (the third word of companions, native/vvfp_more_companions) and write its
companion record, data/more_companions_companion.json (source, destination, SHA-256).

The owner (2026-11-17) asked for new multiplier sliders, each needing a companion of its own, and the second word of
companions VVFP Startup.dll starts (native/shared/startup_companions_2.h) had two free bits.  This chain companion,
the second word's "VVFP More Companions.dll", starts a third word (native/shared/startup_companions_3.h) whose bits
the patcher writes into "VVFP More Companions.txt" beside it; the patcher ships it with the first row that ships a
third-word companion (vv_fun_patcher._attach_more_companions), never by a catalog record.

One command after the DLL's source or the third word's list changes: this script builds it
(scripts/build_vvfp_more_companions.ps1) and pins it.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP More Companions.dll"
DLL = ROOT / "assets" / "more_companions" / DLL_NAME
RECORD = ROOT / "data" / "more_companions_companion.json"


def record(dll_sha: str) -> dict:
    return {"source": f"assets/more_companions/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha}


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_more_companions.ps1")], check=True)
    dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    RECORD.write_text(json.dumps(record(dll_sha), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", RECORD.relative_to(ROOT))


if __name__ == "__main__":
    main()
