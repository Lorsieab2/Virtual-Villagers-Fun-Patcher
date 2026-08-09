from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import vv5_protected_test_runtime as runtime  # noqa: E402


class VV5ProtectedTestRuntimeTests(unittest.TestCase):
    @staticmethod
    def _write_fake_wheel(root: Path, filename: str, module: str) -> Path:
        wheel = root / filename
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(f"{module}/__init__.py", "loaded = True\n")
            archive.writestr(
                f"{module}-0.0.0.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {module}\nVersion: 0.0.0\n",
            )
        return wheel

    def test_runner_extracts_local_wheels_and_returns_read_only_receipt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_root = root / "wheels"
            wheel_root.mkdir()
            self._write_fake_wheel(
                wheel_root, "keystone_engine-0.0.0-py3-none-any.whl", "keystone"
            )
            self._write_fake_wheel(
                wheel_root, "capstone-0.0.0-py3-none-any.whl", "capstone"
            )
            test_path = root / "candidate_test.py"
            test_path.write_text(
                "import capstone\nimport keystone\nimport subprocess\nimport sys\nimport unittest\n"
                "class CandidateTest(unittest.TestCase):\n"
                "    def test_local_dependencies(self):\n"
                "        self.assertTrue(capstone.loaded and keystone.loaded)\n"
                "    def test_nested_process_sees_prepared_runtime(self):\n"
                "        result = subprocess.run([sys.executable, '-c', 'import capstone, keystone; print(capstone.loaded and keystone.loaded)'], capture_output=True, text=True)\n"
                "        self.assertEqual(result.returncode, 0, result.stderr)\n"
                "        self.assertEqual(result.stdout.strip(), 'True')\n",
                encoding="utf-8",
            )

            receipt = runtime.run_vv5_candidate_validation(
                root,
                wheel_roots=[wheel_root],
                test_path=test_path,
                python_executable=Path(sys.executable),
            )

            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["returncode"], 0)
            self.assertFalse(receipt["network_access"])
            self.assertEqual(receipt["writes"], [])
            self.assertEqual(set(receipt["wheels"]), {"capstone", "keystone"})

    def test_runner_imports_optional_local_pefile_when_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_root = root / "wheels"
            wheel_root.mkdir()
            self._write_fake_wheel(
                wheel_root, "keystone_engine-0.0.0-py3-none-any.whl", "keystone"
            )
            self._write_fake_wheel(
                wheel_root, "capstone-0.0.0-py3-none-any.whl", "capstone"
            )
            self._write_fake_wheel(
                wheel_root, "pefile-0.0.0-py3-none-any.whl", "pefile"
            )
            test_path = root / "candidate_test.py"
            test_path.write_text(
                "import capstone\nimport keystone\nimport pefile\nimport unittest\n"
                "class CandidateTest(unittest.TestCase):\n"
                "    def test_all_local_dependencies(self):\n"
                "        self.assertTrue(capstone.loaded and keystone.loaded and pefile.loaded)\n",
                encoding="utf-8",
            )

            receipt = runtime.run_vv5_candidate_validation(
                root,
                wheel_roots=[wheel_root],
                test_path=test_path,
                python_executable=Path(sys.executable),
                require_pefile=True,
            )

            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(set(receipt["wheels"]), {"capstone", "keystone", "pefile"})

    def test_missing_dependency_fails_closed_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "wheels").mkdir()
            (root / "wheels" / "keystone_engine-0.9.2-py3-none-any.whl").write_bytes(b"local")

            with self.assertRaises(runtime.ProtectedRuntimeError) as raised:
                runtime.resolve_local_wheels(root, [root / "wheels"])

            self.assertIn("STOP_MISSING_LOCAL_WHEEL", str(raised.exception))
            self.assertIn("capstone", str(raised.exception))
            self.assertIn("No network access was attempted", str(raised.exception))

    def test_local_wheel_discovery_is_repository_scoped_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_root = root / ".tools" / "keystone-runtime"
            wheel_root.mkdir(parents=True)
            wheels = {
                "keystone_engine-0.9.2-cp311-none-win_amd64.whl": b"keystone",
                "capstone-5.0.1-cp311-none-win_amd64.whl": b"capstone",
            }
            for name, payload in wheels.items():
                (wheel_root / name).write_bytes(payload)

            discovered = runtime.discover_local_wheels(root, [wheel_root])

            self.assertEqual(
                discovered,
                {
                    "keystone": (wheel_root / "keystone_engine-0.9.2-cp311-none-win_amd64.whl",),
                    "capstone": (wheel_root / "capstone-5.0.1-cp311-none-win_amd64.whl",),
                    "pefile": (),
                },
            )

    def test_acl_blocked_local_wheel_fails_closed_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel_root = root / "wheels"
            wheel_root.mkdir()
            self._write_fake_wheel(
                wheel_root, "keystone_engine-0.0.0-py3-none-any.whl", "keystone"
            )
            self._write_fake_wheel(
                wheel_root, "capstone-0.0.0-py3-none-any.whl", "capstone"
            )

            with mock.patch.object(Path, "open", side_effect=PermissionError("ACL denied")):
                with self.assertRaises(runtime.ProtectedRuntimeError) as raised:
                    runtime.resolve_local_wheels(root, [wheel_root])

            self.assertIn("local wheel is not readable", str(raised.exception))
            self.assertIn("No network access was attempted", str(raised.exception))

    def test_wheel_extraction_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wheel = root / "capstone-5.0.1-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("../escape.py", "raise AssertionError")
            local = runtime.LocalWheel("capstone", wheel, wheel.stat().st_size, "0" * 64)
            with self.assertRaises(runtime.ProtectedRuntimeError):
                runtime._safe_extract(local, root / "runtime")


if __name__ == "__main__":
    unittest.main()
