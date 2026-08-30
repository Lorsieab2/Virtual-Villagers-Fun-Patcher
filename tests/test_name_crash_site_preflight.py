from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from test_name_crash_immunity import (  # noqa: E402
    EXPECTED_BASENAME,
    IMAGE_BASE,
    _synthetic_pe,
)
import vv_fun_patcher as patcher  # noqa: E402


def test_name_crash_finalizer_rejects_partial_site_mapping_without_writes() -> None:
    data = _synthetic_pe()
    original = bytes(data)
    with patch.object(
        patcher,
        "_nci_find_call_sites",
        return_value=[IMAGE_BASE + 0x27DD, IMAGE_BASE + 0x2944],
    ):
        original_mapper = patcher._nci_rva_to_off
        with patch.object(
            patcher,
            "_nci_rva_to_off",
            side_effect=lambda info, rva: None
            if rva == 0x2944
            else original_mapper(info, rva),
        ):
            result = patcher._apply_name_crash_immunity(
                data, EXPECTED_BASENAME, []
            )
    assert result == {"status": "skipped", "reason": "call site not writable"}
    assert bytes(data) == original
