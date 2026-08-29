import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"
RESOURCE_SYNC = ROOT / "scripts" / "build_vv3_safe_upgrade_resources.py"
NATIVE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
DEF = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.def"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
HEAD_DOC = ROOT / "docs" / "head-mask-rendering.md"
PROOF_DOC = ROOT / "docs" / "vv3-mask-offscreen-proof.md"
STATUS_DOC = ROOT / "docs" / "vv3-heathen-mask-status.md"
TRACE_DOC = ROOT / "docs" / "vv3-pickup-trace-handoff.md"


class VV3PickupTruthTests(unittest.TestCase):
    def test_disproven_effect_sites_have_no_generator_or_manifest_hook(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        offsets = {int(item["offset"], 0) for item in manifest["patches"]}

        # The addresses remain in explanatory evidence comments, but no stale cave,
        # redirect, or function-pointer symbol may survive in the active generator.
        for forbidden in (
            "WORLD_HELD_CALLSITE_VA",
            "WORLD_HELD2_CALLSITE_VA",
            "WORLD_HELD_WRAP_CAVE_VA",
            "WORLD_HELD2_WRAP_CAVE_VA",
            "world_held_wrap_cave",
            "world_held2_wrap_cave",
            "world_held_wrap_redirect",
            "world_held2_wrap_redirect",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn(0x34357, offsets)
        self.assertNotIn(0x344B3, offsets)
        self.assertIn("WORLD_INDEXFN_PTR", source)

    def test_native_companion_has_no_false_held_exports_or_state_probe(self) -> None:
        native = NATIVE.read_text(encoding="utf-8")
        definition = DEF.read_text(encoding="utf-8")
        sync = RESOURCE_SYNC.read_text(encoding="utf-8")
        for text in (native, definition, sync):
            self.assertNotIn("VV3HeldMaskDraw", text)
            self.assertNotIn("VV3HeldMaskDraw2", text)
            self.assertNotIn("VV3WorldMaskFlush", text)
            self.assertNotIn("g_vv3_held_diag", text)
            self.assertNotIn("VV3_WORLD_CARRIED_OFF", text)
        self.assertIn("0x434357", native)
        self.assertIn("0x4344B3", native)
        self.assertIn("timed UI/effect renderer", native)
        self.assertIn("g_vv3_stash_valid  = 1", native)
        self.assertNotIn("VV3WorldMaskDraw(idx)", native)

    def test_docs_record_static_boundary_and_trace_handoff(self) -> None:
        head = HEAD_DOC.read_text(encoding="utf-8")
        proof = PROOF_DOC.read_text(encoding="utf-8")
        status = STATUS_DOC.read_text(encoding="utf-8")
        trace = TRACE_DOC.read_text(encoding="utf-8")
        for text in (head, proof, status):
            self.assertIn("0x434357", text)
            self.assertIn("0x4344B3", text)
            self.assertIn("timed", text.lower())
        self.assertIn("held owner", head.lower())
        self.assertIn("0x460d10", head.lower())
        self.assertIn("player trace", proof.lower())
        self.assertIn("held/action ownership", status.lower())
        self.assertIn("unsupported action states fail closed", status.lower())
        self.assertIn("sub_4605F0", trace)
        self.assertIn("0x42E3F5", trace)
        self.assertIn("Player acceptance handoff", trace)


if __name__ == "__main__":
    unittest.main()
