from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


def _build_and_source():
    build = next(item for item in patcher.load_builds() if item.id == "vv1")
    return build, ROOT / "research" / "stock-executables" / build.input_name


def _finalizer(suffix: bytes, owner: str):
    def finalize(data, _basename, applied):
        data.extend(suffix)
        applied.append(
            {"offset": "0x0", "before": "", "after": "", "owner": owner}
        )
        return {"status": "applied"}

    return finalize


def test_dry_run_hashes_and_ledgers_finalizer_output() -> None:
    build, source = _build_and_source()
    rendered = bytearray(b"rendered bytes")
    with patch.object(patcher, "identify", return_value=build), patch.object(
        patcher, "render_patched_bytes", return_value=(rendered, [])
    ), patch.object(
        patcher,
        "_apply_name_crash_immunity",
        side_effect=_finalizer(b" finalized", "dry-run-test"),
    ):
        result = patcher.dry_run(source)

    assert result["result_sha256"] == hashlib.sha256(
        b"rendered bytes finalized"
    ).hexdigest().upper()
    assert result["patches"][0]["owner"] == "dry-run-test"


def test_dry_run_all_hashes_and_ledgers_finalizer_output() -> None:
    build, source = _build_and_source()
    rendered = bytearray(b"bulk rendered")
    with patch.object(
        patcher, "validate_all_sources", return_value=[(build, source)]
    ), patch.object(
        patcher, "render_patched_bytes", return_value=(rendered, [])
    ), patch.object(
        patcher,
        "_apply_name_crash_immunity",
        side_effect=_finalizer(b" finalized", "bulk-test"),
    ):
        result = patcher.dry_run_all({"vv1": source})

    assert result[0]["result_sha256"] == hashlib.sha256(
        b"bulk rendered finalized"
    ).hexdigest().upper()
    assert result[0]["patches"][0]["owner"] == "bulk-test"
