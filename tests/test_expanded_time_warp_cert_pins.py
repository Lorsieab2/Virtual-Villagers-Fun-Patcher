from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    EXPANDED_TIME_WARP_ARTIFACT_SHA256,
    VV5_TASK9_SOURCE_TEXT_SHA256,
    source_text_sha256,
)


def test_vv3_time_warp_manifest_keeps_its_own_certified_identity() -> None:
    expected = "F5094E6275F6A019B001B89E265B71ACD365499C00E57E45AB5AFB6C44C9A8C8"
    actual = source_text_sha256(
        (ROOT / "data" / "vv3_expanded_time_warp.json").read_bytes()
    )
    assert EXPANDED_TIME_WARP_ARTIFACT_SHA256["vv3"]["manifest"] == expected
    assert actual == expected
    assert expected != VV5_TASK9_SOURCE_TEXT_SHA256["manifest"]
