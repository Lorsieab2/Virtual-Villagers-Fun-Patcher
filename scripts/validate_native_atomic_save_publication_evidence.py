from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from native_atomic_save_publication_evidence import validate_file
result = validate_file(ROOT / "data" / "native_atomic_save_publication_evidence.json")
print(json.dumps({"structural": result.structural, "evidence_complete": result.evidence_complete, "publication_allowed": result.publication_allowed, "errors": list(result.errors)}, indent=2))
raise SystemExit(0 if result.evidence_complete and result.publication_allowed else 1)
