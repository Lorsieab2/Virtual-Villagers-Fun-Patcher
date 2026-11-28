"""The owner's GIMP workbench is never overwritten (scripts/skin_tone_sheets.py build_workbench).

The owner's rule: nothing may destroy their data.  A rebuild makes again only the .xcf files that are still
exactly what the tool wrote (each is pinned by SHA-256 in the workbench's .generated.json).  A file that
differs is the owner's: it is read first, as `import` reads it, so its edits are in "edits", and then it is
left byte for byte as it is; if it cannot be read it is left as it is too, and said so.

GIMP is stood in for (it writes and reads the .xcf files in the real tool); the sheets are a small made-up
"game" of one picture, so nothing here needs a game's art.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import numpy as np
    from PIL import Image

    import skin_tone_sheets as sheets

    HAVE = True
except ImportError:  # pragma: no cover - the tool needs numpy and scipy, which the patcher itself does not
    HAVE = False


class FakeGimp:
    """Writes an .xcf for a build job; for an export job, the layers the test says the owner painted."""

    def __init__(self):
        self.built, self.read, self.painted, self.fail_reads, self.jobs = [], [], {}, False, []
        self.spreads, self.spread_results = [], {}

    def __call__(self, script, job):
        if script is sheets._GIMP_BUILD:
            for item in job["files"]:
                names = [layer["name"] for layer in item["layers"]]
                self.jobs.append(item["layers"])
                Path(item["xcf"]).write_bytes(b"gimp xcf " + json.dumps(names).encode())
                self.built.append(Path(item["xcf"]).name)
            return ""
        if script is sheets._GIMP_SPREAD:
            for item in job["files"]:
                self.spreads.append(item)
                result = dict(self.spread_results.get(item["stem"], {"did": "unchanged", "changed": []}), xcf=item["xcf"])
                Path(item["result"]).write_text(json.dumps(result), encoding="utf-8")
            return ""
        if self.fail_reads:
            raise SystemExit("GIMP did not finish every file")
        for item in job["files"]:
            # GIMP hands the wanted layers back as one picture, one under the other, and their names in order.
            self.read.append(Path(item["xcf"]).name)
            Path(item["out"]).mkdir(parents=True, exist_ok=True)
            layers = self.painted.get(Path(item["xcf"]).name, {})
            if layers:
                width, height = next(iter(layers.values())).size
                tall = Image.new("RGBA", (width, height * len(layers)), (0, 0, 0, 0))
                for k, image in enumerate(layers.values()):
                    tall.paste(image, (0, k * height))
                tall.save(Path(item["out"]) / "layers.png")
            (Path(item["out"]) / "layers.json").write_text(json.dumps(list(layers)), encoding="utf-8")
        return ""


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class Rebuild(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.images, self.folder = root / "Images", root / "bench" / "vv1"
        self.images.mkdir()
        # One sheet: the carried-things picture, with a held baby's face in its cell (warm, lit pixels).
        art = np.zeros((25, 600, 4), np.uint8)
        art[5:12, 150:158] = (240, 190, 140, 255)
        art[12:20, 125:150] = (220, 230, 250, 255)
        Image.fromarray(art).save(self.images / "carrying.png")
        self.gimp = FakeGimp()
        patch = mock.patch.object(sheets, "run_gimp", self.gimp)
        patch.start()
        self.addCleanup(patch.stop)
        self.xcf = self.folder / "vv1_carrying.xcf"

    def build(self):
        return sheets.build_workbench("vv1", self.images, self.folder)

    def test_a_first_build_writes_and_pins_the_file(self):
        written, kept, unread = self.build()
        self.assertEqual(([Path(p).name for p in written], kept, unread), (["vv1_carrying.xcf"], [], []))
        pins = json.loads((self.folder / ".generated.json").read_text(encoding="utf-8"))[sheets.XCF_PINS]
        self.assertEqual(pins, {"carrying": sheets._file_sha(self.xcf)})
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), [])

    def test_an_untouched_file_is_made_again(self):
        self.build()
        written, kept, unread = self.build()
        self.assertEqual((len(written), kept, unread), (1, [], []))
        self.assertEqual(self.gimp.built, ["vv1_carrying.xcf"] * 2)
        self.assertEqual(self.gimp.read, [], "nothing to read: nothing was changed")

    def test_a_file_the_owner_changed_is_read_and_never_replaced(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        theirs = self.xcf.read_bytes()
        painted = Image.new("RGBA", (600, 25), (0, 0, 0, 0))     # tone 3's colour layer as the owner left it:
        painted.putpixel((152, 7), (90, 60, 40, 255))            # paint of any colour on two pixels,
        painted.putpixel((153, 7), (1, 2, 3, 9))                 # one of them faint, as a sprite's edge is
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_03.png": painted}
        written, kept, unread = self.build()
        self.assertEqual((written, kept, unread), ([], ["carrying"], []))
        self.assertEqual(self.xcf.read_bytes(), theirs, "the owner's file, byte for byte")
        self.assertEqual(self.gimp.read, ["vv1_carrying.xcf"], "read as `import` reads it")
        self.assertEqual(self.gimp.built, ["vv1_carrying.xcf"], "built once, the first time only")
        kept_layer = self.folder / "edits" / "carrying" / "skin_03.png"
        self.assertTrue(kept_layer.is_file(), "its edit is kept in edits")
        mark = np.array(Image.open(kept_layer).convert("RGBA"))
        self.assertEqual({tuple(p) for p in mark.reshape(-1, 4)}, {(255, 255, 255, 255), (0, 0, 0, 0)},
                         "kept as where the skin is: no colour of the owner's paint, none of the art")
        self.assertEqual([(int(x), int(y)) for y, x in zip(*np.nonzero(mark[..., 3]))], [(152, 7), (153, 7)])
        art = sheets.Art("vv1", self.images, self.folder / "edits", shipped=False)
        self.assertEqual(int(art.tone_mask("carrying.png", 3).sum()), 2, "tone 3 has skin where they painted")
        self.assertEqual(int(art.tone_mask("carrying.png", 4).sum()), int(art.mask("carrying.png").sum()),
                         "and every other tone keeps the sheet's own mask")
        stock = art.stock("carrying.png")
        three = art.sheet("carrying.png", sheets.core.TONES[2])
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero((three != stock).any(-1)))}, {(152, 7), (153, 7)},
                         "the tone is made on exactly those pixels, shaded from the game's own art")
        # ... and again, however often: still theirs.
        self.build()
        self.assertEqual(self.xcf.read_bytes(), theirs)

    def test_a_changed_file_that_cannot_be_read_is_left_alone(self):
        self.build()
        self.xcf.write_bytes(b"not something GIMP can open, but the owner's")
        self.gimp.fail_reads = True
        written, kept, unread = self.build()
        self.assertEqual((written, kept, unread), ([], [], ["carrying"]))
        self.assertEqual(self.xcf.read_bytes(), b"not something GIMP can open, but the owner's")
        self.assertFalse((self.folder / "edits").exists())

    def test_a_file_with_no_record_is_taken_for_the_owners(self):
        """A workbench built before the files were pinned, or a file the owner put there."""
        self.folder.mkdir(parents=True)
        self.xcf.write_bytes(b"who knows")
        written, kept, unread = self.build()
        self.assertEqual((written, kept), ([], ["carrying"]))
        self.assertEqual(self.xcf.read_bytes(), b"who knows")

    def test_pinning_an_older_workbench_skips_files_changed_since(self):
        self.build()
        manifest = self.folder / ".generated.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        del data[sheets.XCF_PINS]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        built_at = self.xcf.stat().st_mtime
        self.assertEqual(sheets.pin_as_written("vv1", self.folder, built_at - 10), [], "changed after: the owner's")
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), ["carrying"])
        self.assertEqual(sheets.pin_as_written("vv1", self.folder, built_at + 1), ["carrying"])
        self.assertEqual(sheets.changed_by_the_owner("vv1", self.folder, ["carrying"]), [])

    def test_a_build_makes_each_tone_a_group_of_paint_under_shading(self):
        self.build()
        names = json.loads(self.xcf.read_bytes()[len(b"gimp xcf "):])
        want = [sheets.LAYER_GAME, sheets.LAYER_MASK]
        for number in range(1, len(sheets.core.TONES) + 1):
            want += [sheets.paint_layer_name(number), sheets.LAYER_SHADING]
        self.assertEqual(names, want + [sheets.LAYER_TOP])
        self.assertEqual(self.gimp.jobs[-1][3]["group"], sheets.tone_layer_name(1))
        self.assertEqual(self.gimp.jobs[-1][2]["group"], sheets.tone_layer_name(1))
        self.assertEqual([(layer["clip"], layer["lock"]) for layer in self.gimp.jobs[-1][2:4]],
                         [(False, False), (True, True)], "paint: free to edit; shading: locked, shown only on paint")
        record = json.loads((self.folder / ".generated.json").read_text(encoding="utf-8"))["carrying"]
        self.assertEqual(sorted(record), ["mask.png"] + [f"skin_{n:02d}.png" for n in range(1, 11)])

    def test_a_colour_layer_still_as_built_is_not_an_edit(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" saved again, nothing painted")
        mask = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        layer = np.zeros(mask.shape + (4,), np.uint8)
        layer[mask] = (146, 98, 62, 255)
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_07.png": Image.fromarray(layer)}
        self.build()
        self.assertFalse((self.folder / "edits" / "carrying" / "skin_07.png").exists())

    def test_starting_fresh_backs_every_file_up_first(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        theirs = self.xcf.read_bytes()
        written, kept, unread = sheets.build_workbench("vv1", self.images, self.folder, fresh_backup="_before")
        self.assertEqual((len(written), kept, unread), (1, [], []))
        self.assertEqual((self.folder / "_before" / "vv1_carrying.xcf").read_bytes(), theirs, "their file is kept")
        self.assertNotEqual(self.xcf.read_bytes(), theirs, "and a fresh one is in its place")
        self.assertEqual(self.gimp.read, [], "nothing is read back")
        self.xcf.write_bytes(b"painted again")
        sheets.build_workbench("vv1", self.images, self.folder, fresh_backup="_before")
        self.assertEqual((self.folder / "_before" / "vv1_carrying.xcf").read_bytes(), theirs, "a backup is never overwritten")
        self.assertEqual((self.folder / "_before" / "vv1_carrying (2).xcf").read_bytes(), b"painted again")

    def test_publishing_ships_where_the_skin_is_and_nothing_else(self):
        """What goes into the patcher: white marks on the sprite's own pixels -- not the owner's paint colour,
        not a pixel of the game's art -- and the patcher's own maker tones exactly those pixels."""
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" and the owner's painting")
        painted = Image.new("RGBA", (600, 25), (0, 0, 0, 0))
        painted.putpixel((152, 7), (90, 60, 40, 255))            # on the baby's face
        painted.putpixel((130, 15), (90, 60, 40, 255))           # on the blanket: the owner says it is skin
        painted.putpixel((3, 3), (90, 60, 40, 255))              # off the sprite: nothing
        self.gimp.painted["vv1_carrying.xcf"] = {"skin_03.png": painted}
        self.build()
        edits, out = self.folder / "edits", self.folder.parent / "shipped"
        written = sheets.publish_edits(sheets.Art("vv1", self.images, edits, shipped=False), edits, out)
        self.assertEqual(written, ["vv1/carrying/skin_03.png"])
        mark = np.array(Image.open(out / "vv1" / "carrying" / "skin_03.png").convert("RGBA"))
        self.assertEqual({tuple(int(v) for v in p) for p in mark.reshape(-1, 4)}, {(255, 255, 255, 255), (0, 0, 0, 0)})
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero(mark[..., 3]))}, {(152, 7), (130, 15)})
        pins = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(list(pins), ["vv1/carrying/skin_03.png"])
        # The patcher's maker (Pillow only) and this tool make the same tone 3 from it.
        sys.path.insert(0, str(ROOT / "src"))
        import vv_skin_tone_art as maker
        maker.write_tone_sheets(1, self.images, self.folder.parent / "made", edits=[out / "vv1"], tones=[3])
        made = np.array(Image.open(self.folder.parent / "made" / maker.installed_name(3, "carrying.png")).convert("RGBA"))
        stock = np.array(Image.open(self.images / "carrying.png").convert("RGBA"))
        self.assertEqual({(int(x), int(y)) for y, x in zip(*np.nonzero((made != stock).any(-1)))}, {(152, 7), (130, 15)})

    def colour_layers(self, **changes):
        """Every tone's colour layer as GIMP hands it back: as built, but for {tone number: [(x, y) erased]}."""
        mask = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        layers = {}
        for number in range(1, 11):
            layer = np.zeros(mask.shape + (4,), np.uint8)
            layer[mask] = tuple(sheets.tone_colour(number)) + (255,)
            for x, y in changes.get(f"t{number}", ()):
                layer[y, x] = 0
            layers[f"skin_{number:02d}.png"] = Image.fromarray(layer)
        return layers

    def kept_marks(self):
        folder = self.folder / "edits" / "carrying"
        return {p.name: np.array(Image.open(p).convert("RGBA"))[..., 3] > 0 for p in sorted(folder.glob("skin_*.png"))}

    def test_import_can_take_the_one_changed_tone_for_all_ten(self):
        """The owner, 2026-11-28: "copy the edited pixels of one tone to the other tones"."""
        self.build()
        theirs = self.xcf.read_bytes()
        self.gimp.painted["vv1_carrying.xcf"] = self.colour_layers(t10=[(152, 7)])
        said = []
        kept = sheets.import_workbench("vv1", self.folder, same_for_all=True, say=said.append)
        marks = self.kept_marks()
        self.assertEqual(sorted(marks), [f"skin_{n:02d}.png" for n in range(1, 11)])
        self.assertEqual(len(kept), 10)
        for mark in marks.values():
            self.assertFalse(mark[7, 152], "the pixel erased in tone 10 is skin in no tone")
            self.assertTrue((mark == marks["skin_10.png"]).all())
        self.assertEqual(said, ["vv1_carrying: tone 10's paint is the skin of all 10 tones"])
        self.assertEqual(self.xcf.read_bytes(), theirs, "the .xcf is not touched")
        # Without the option, only the tone that was changed is kept.
        for path in (self.folder / "edits" / "carrying").glob("*.png"):
            path.unlink()
        sheets.import_workbench("vv1", self.folder)
        self.assertEqual(sorted(self.kept_marks()), ["skin_10.png"])

    def test_import_for_all_tones_needs_to_know_which_when_several_differ(self):
        self.build()
        self.gimp.painted["vv1_carrying.xcf"] = self.colour_layers(t10=[(152, 7)], t3=[(153, 8)])
        said = []
        # Tone 10 (Ebony) is the tone the owner edits: changed, it is the one the others follow.
        sheets.import_workbench("vv1", self.folder, same_for_all=True, say=said.append)
        marks = self.kept_marks()
        self.assertEqual(len(marks), 10)
        self.assertTrue(all((mark == marks["skin_10.png"]).all() for mark in marks.values()))
        self.assertTrue(marks["skin_03.png"][8, 153] and not marks["skin_03.png"][7, 152], "Ebony's skin, in tone 3 too")
        for path in (self.folder / "edits" / "carrying").glob("*.png"):
            path.unlink()
        self.gimp.painted["vv1_carrying.xcf"] = self.colour_layers(t9=[(152, 7)], t3=[(153, 8)])
        said = []
        sheets.import_workbench("vv1", self.folder, same_for_all=True, say=said.append)
        self.assertEqual(sorted(self.kept_marks()), ["skin_03.png", "skin_09.png"], "each read as it is")
        self.assertIn("add --from and its number", said[0])
        sheets.import_workbench("vv1", self.folder, same_for_all=True, source=3, say=said.append)
        marks = self.kept_marks()
        self.assertEqual(len(marks), 10)
        self.assertTrue(all((mark == marks["skin_03.png"]).all() for mark in marks.values()))
        self.assertTrue(marks["skin_09.png"][7, 152] and not marks["skin_09.png"][8, 153], "tone 3's skin, in tone 9 too")
        # Naming a tone that is still as built puts every tone back as built: no edit is left.
        sheets.import_workbench("vv1", self.folder, same_for_all=True, source=5, say=said.append)
        self.assertEqual(self.kept_marks(), {})

    def test_two_tones_changed_the_same_way_need_no_from(self):
        self.build()
        self.gimp.painted["vv1_carrying.xcf"] = self.colour_layers(t10=[(152, 7)], t9=[(152, 7)])
        sheets.import_workbench("vv1", self.folder, same_for_all=True, say=lambda _line: None)
        self.assertEqual(len(self.kept_marks()), 10)

    def spread(self, state=("free", ""), **more):
        with mock.patch.object(sheets, "held_open", lambda _path: state):
            return sheets.spread_tone("vv1", self.folder, **more)

    def test_spread_hands_gimp_the_file_its_record_and_each_tones_colour(self):
        self.build()
        backup = self.folder / "_b" / "vv1_carrying.xcf"
        self.gimp.spread_results["carrying"] = {"did": "spread", "changed": [10], "source": 10, "pixels": 55,
                                                "targets": list(range(1, 10)), "same": True, "backup": str(backup)}
        said = self.spread(sheets=["vv1_carrying"], backup="_b")
        item = self.gimp.spreads[0]
        record = json.loads((self.folder / ".generated.json").read_text(encoding="utf-8"))["carrying"]
        self.assertEqual(item["xcf"], str(self.xcf))
        self.assertIsNone(item["source"], "left out: GIMP finds the one tone changed")
        self.assertEqual(item["records"], {str(n): record[f"skin_{n:02d}.png"] for n in range(1, 11)})
        self.assertEqual(item["colours"]["10"], [0x32, 0x20, 0x17])
        self.assertEqual(item["backup"], str(self.folder / "_b"))
        self.assertEqual(len(said), 1)
        self.assertIn("copied Tone 10 (Ebony)'s skin to the other 9 tones", said[0][1])
        self.assertIn("All 10 tones now cover the same 55 pixels", said[0][1])
        self.assertIn("vv1_carrying.xcf", said[0][1])
        self.assertEqual(self.spread(sheets=["carrying.xcf"[:-4]], source=4)[0][0], "carrying")
        self.assertEqual(self.gimp.spreads[-1]["source"], 4)

    def test_spread_says_when_the_check_afterwards_fails(self):
        self.build()
        self.gimp.spread_results["carrying"] = {"did": "spread", "changed": [10], "source": 10, "pixels": 55,
                                                "targets": [1], "same": False, "backup": str(self.folder / "_b" / "x.xcf")}
        self.assertIn("SOMETHING WENT WRONG", self.spread()[0][1])

    def test_spread_leaves_a_file_gimp_has_open(self):
        self.build()
        said = self.spread(("open", "GIMP has it open"), yes=True)
        self.assertEqual(self.gimp.spreads, [], "GIMP is not even started")
        self.assertIn("left alone: GIMP has it open", said[0][1])

    def test_spread_does_nothing_when_it_cannot_tell_unless_told_yes(self):
        self.build()
        unknown = ("unknown", "GIMP is running, and which files it has open cannot be seen")
        with self.assertRaises(SystemExit) as stopped:
            self.spread(unknown)
        self.assertIn("Nothing was changed", str(stopped.exception))
        self.assertIn("--yes", str(stopped.exception))
        self.assertEqual(self.gimp.spreads, [])
        self.spread(unknown, yes=True)
        self.assertEqual(len(self.gimp.spreads), 1)

    def test_spread_leaves_an_older_file_and_refuses_a_missing_one(self):
        self.build()
        manifest = self.folder / ".generated.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["carrying"] = {"mask.png": data["carrying"]["mask.png"]}       # as the first workbench recorded it
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("one of the older files", self.spread()[0][1])
        self.assertEqual(self.gimp.spreads, [])
        with self.assertRaises(SystemExit):
            self.spread(sheets=["vv1_nothing"])

    def test_a_sheet_may_be_named_as_its_file(self):
        for name in ("vv1_carrying", "vv1_carrying.xcf", "carrying", "VV1_carrying"):
            self.assertEqual(sheets.sheet_stem("vv1", name), "carrying")

    def test_the_tutorial_tells_how_to_copy_a_tone(self):
        text = sheets.TUTORIAL.read_text(encoding="utf-8")
        for words in ("COPY ONE TONE'S SKIN TO ALL THE OTHERS",
                      "python scripts\\skin_tone_sheets.py spread --game vv1 --sheet vv1_carrying",
                      "python scripts\\skin_tone_sheets.py import --game vv1 --same-for-all-tones",
                      "Alpha to Selection", "Fill with FG Color", "Select > Invert", "Select > None"):
            self.assertIn(words, text)
        self.assertIn("spread --game vv1 --sheet vv1_carrying", sheets.README)

    def test_an_import_never_withdraws_a_learned_skin_and_puts_a_lost_one_back(self):
        """Found 2026-11-28: `import` after `learn --write` deleted the learned masks (they equalled the rebuilt
        files' own "Skin mask" layers), so the learned skin never reached the mod."""
        base = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        learned = base.copy()
        learned[12:20, 125:150] = True                          # the learned skin: the blanket too
        mark = np.zeros(learned.shape + (4,), np.uint8)
        mark[learned] = 255
        kept = self.folder / "edits" / "carrying" / sheets.LEARNED_MASK
        kept.parent.mkdir(parents=True)
        Image.fromarray(mark).save(kept)
        (self.folder / sheets.LEARNED).write_text(json.dumps({"sheets": ["carrying"]}), encoding="utf-8")
        self.build()                                            # as `learn --write` makes the file again
        art = sheets.Art("vv1", self.images, self.folder / "edits", shipped=False)
        self.assertTrue((art.mask("carrying.png") == learned).all(), "the learned skin is the sheet's skin")
        as_built = {"mask.png": Image.fromarray(mark)}
        for number in range(1, 11):
            layer = np.zeros(learned.shape + (4,), np.uint8)
            layer[learned] = 255
            as_built[f"skin_{number:02d}.png"] = Image.fromarray(layer)
        self.gimp.painted["vv1_carrying.xcf"] = as_built
        self.assertEqual(sheets.import_workbench("vv1", self.folder, say=lambda _line: None), [])
        self.assertTrue(kept.is_file(), "an import does not withdraw it")
        kept.unlink()                                           # as the import of 2026-11-28 left it
        said = []
        sheets.import_workbench("vv1", self.folder, say=said.append)
        self.assertTrue(kept.is_file(), "the next import puts it back from the file's own Skin mask layer")
        self.assertIn("put back", said[0])
        back = np.array(Image.open(kept).convert("RGBA"))[..., 3] > 0
        self.assertTrue((back == learned).all())
        out = self.folder.parent / "shipped"
        written = sheets.publish_edits(sheets.Art("vv1", self.images, self.folder / "edits", shipped=False),
                                       self.folder / "edits", out)
        self.assertEqual(written, ["vv1/carrying/mask.png"], "and it ships as the sheet's skin")
        shipped = np.array(Image.open(out / "vv1" / "carrying" / "mask.png").convert("RGBA"))[..., 3] > 0
        self.assertTrue((shipped == learned).all())

    def test_the_readme_says_so(self):
        self.assertIn("A file you have changed is never overwritten", sheets.README)
        self.assertNotIn("the .xcf files are replaced", sheets.README)
        self.assertIn(f'see "{sheets.TUTORIAL_NAME}" in this folder', sheets.README)

    def half_see_through(self, extra=None):
        """The sheet's own generated mask as GIMP hands it back when its layer was left at 50% opacity."""
        mask = sheets.Art("vv1", self.images, shipped=False).mask("carrying.png")
        layer = np.zeros(mask.shape + (4,), np.uint8)
        layer[mask] = (255, 255, 255, 128)
        if extra is not None:
            layer[extra[1], extra[0]] = (255, 255, 255, 128)
        return Image.fromarray(layer)

    def test_a_mask_left_at_half_opacity_is_read_whole(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" the owner marked one more pixel, at 50% opacity")
        self.gimp.painted["vv1_carrying.xcf"] = {"mask.png": self.half_see_through(extra=(140, 3))}
        self.build()
        kept = Image.open(self.folder / "edits" / "carrying" / "mask.png").convert("RGBA")
        self.assertEqual(kept.getpixel((140, 3)), (255, 255, 255, 255), "the pixel the owner marked")
        self.assertEqual(kept.getpixel((152, 7)), (255, 255, 255, 255), "the skin that was already marked")
        self.assertEqual(set(kept.getdata()), {(255, 255, 255, 255), (0, 0, 0, 0)}, "kept clean: white or nothing")

    def test_a_mask_whose_opacity_alone_changed_is_not_an_edit(self):
        self.build()
        self.xcf.write_bytes(self.xcf.read_bytes() + b" saved again with the mask at 50%")
        self.gimp.painted["vv1_carrying.xcf"] = {"mask.png": self.half_see_through()}
        self.build()
        self.assertFalse((self.folder / "edits" / "carrying" / "mask.png").exists())


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class Learn(unittest.TestCase):
    """The owner, 2026-11-28: "the other unedited gimp files should attempt to recolor the skin and nonskin
    parts based on the edited ones".  The colours the owner added to the skin, or removed from it, on the
    sheets they edited become skin, or not skin, on the sheets still as built."""

    SKIN, CLOTH, NEW, GONE, ODD = (240, 190, 140), (200, 60, 60), (150, 100, 70), (250, 240, 200), (10, 200, 10)

    def sheet(self, cells):
        """One row of 10 x 10 cells, each one colour; -> (pixels, the mask as built: SKIN and GONE are skin)."""
        art = np.zeros((10, 10 * len(cells), 4), np.uint8)
        for k, colour in enumerate(cells):
            art[:, 10 * k:10 * k + 10] = colour + (255,)
        built = np.zeros(art.shape[:2], bool)
        for k, colour in enumerate(cells):
            built[:, 10 * k:10 * k + 10] = colour in (self.SKIN, self.GONE)
        return art, built

    def learned(self):
        art, built = self.sheet([self.SKIN, self.CLOTH, self.NEW, self.GONE, self.ODD])
        skin = built.copy()
        skin[:, 20:30] = True           # the owner made every NEW pixel skin,
        skin[:, 30:40] = False          # no GONE pixel skin,
        skin[0, 40:42] = True           # and two stray ODD pixels: too few to mean anything
        counts = sheets.learn_counts(art, built, skin, 10)
        return counts, sheets.learned_rule(counts)

    def test_colours_added_become_skin_and_colours_removed_do_not(self):
        counts, (skin, non, mixed, rare) = self.learned()
        pack = lambda c: (c[0] << 16) | (c[1] << 8) | c[2]
        self.assertEqual((skin, non, mixed, rare), ({pack(self.NEW)}, {pack(self.GONE)}, set(), {pack(self.ODD)}))
        self.assertEqual(counts[pack(self.NEW)], [100, 0, 0, 0])
        self.assertEqual(counts[pack(self.SKIN)], [0, 0, 100, 0], "left as built: counted, in no rule")
        other, built = self.sheet([self.NEW, self.GONE, self.CLOTH, self.SKIN, self.ODD])
        new = sheets.apply_rule(other, built, skin, non)
        self.assertTrue(new[:, 0:10].all() and not new[:, 10:20].any(), "NEW is skin now, GONE is not")
        self.assertTrue(not new[:, 20:30].any() and new[:, 30:40].all() and not new[:, 40:50].any(), "the rest as built")

    def test_a_colour_changed_both_ways_is_left_as_built(self):
        art, built = self.sheet([self.SKIN, self.SKIN, self.CLOTH, self.CLOTH])
        skin = built.copy()
        skin[:5, 0:10] = False          # half of one skin cell removed: SKIN is still mostly skin
        skin[:, 20:30] = True           # one cloth cell added, the other left: CLOTH ends up half and half
        rule = sheets.learned_rule(sheets.learn_counts(art, built, skin, 10))
        self.assertEqual((rule[0], rule[1]), (set(), set()))
        self.assertEqual(len(rule[2]), 2, "both are mixed")

    def test_rows_the_owner_has_not_worked_on_do_not_count(self):
        art, built = self.sheet([self.SKIN, self.CLOTH])
        art, built = np.concatenate([art, art]), np.concatenate([built, built])
        skin = built.copy()
        skin[0:10, 10:20] = True        # CLOTH made skin on the first row; the second row not touched yet
        skin_colours = sheets.learned_rule(sheets.learn_counts(art, built, skin, 10))[0]
        self.assertEqual(len(skin_colours), 1, "the untouched row's cloth does not speak against it")

    def test_near_colours_can_count_together(self):
        art, built = self.sheet([(150, 100, 70), (151, 101, 71), self.SKIN])
        skin = built.copy()
        skin[:, 0:10] = True
        self.assertEqual(sheets.apply_rule(art, built, *sheets.learned_rule(sheets.learn_counts(art, built, skin, 10))[:2])[:, 10:20].any(), False)
        rule = sheets.learned_rule(sheets.learn_counts(art, built, skin, 10, 4))
        self.assertEqual(rule[0], set(), "counted together, the bucket was added on half its pixels only: mixed")

    def test_what_the_owner_made_skin_is_what_most_changed_tones_say(self):
        built = np.zeros((4, 4), bool)
        built[0] = True
        layer = lambda where: np.dstack([np.zeros((4, 4, 3), np.uint8), np.where(where, 255, 0).astype(np.uint8)])
        one = built.copy()
        one[1, 0] = True
        record = {f"skin_{n:02d}.png": sheets._sha(built) for n in range(1, 11)}
        layers = {f"skin_{n:02d}.png": layer(built) for n in range(1, 11)}
        self.assertEqual(sheets.owners_skin(layers, record, built), (None, []))
        layers["skin_10.png"] = layer(one)
        skin, tones = sheets.owners_skin(layers, record, built)
        self.assertEqual(tones, ["10"])
        self.assertTrue((skin == one).all(), "the nine tones still as built have no say")
        two = built.copy()
        two[2, 2] = True
        layers["skin_03.png"] = layers["skin_04.png"] = layer(two)
        skin, tones = sheets.owners_skin(layers, record, built)
        self.assertEqual(tones, ["10"], "Ebony is the tone the owner edits: changed, it alone speaks")
        self.assertTrue((skin == one).all())

    def test_a_dry_run_writes_nothing_and_never_reads_the_owners_own_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images, bench = root / "Images", root / "bench"
            images.mkdir()
            art = np.zeros((25, 600, 4), np.uint8)
            art[5:12, 150:158] = (240, 190, 140, 255)
            art[12:20, 125:150] = (220, 230, 250, 255)
            Image.fromarray(art).save(images / "carrying.png")
            gimp = FakeGimp()
            with mock.patch.object(sheets, "run_gimp", gimp):
                sheets.build_workbench("vv1", images, bench / "vv1")
                xcf = bench / "vv1" / "vv1_carrying.xcf"
                xcf.write_bytes(xcf.read_bytes() + b" and the owner's painting")
                mask = sheets.Art("vv1", images, shipped=False).mask("carrying.png")
                layers = {}
                for number in range(1, 11):
                    layer = np.zeros(mask.shape + (4,), np.uint8)
                    layer[mask] = 255
                    if number == 10:
                        layer[12:20, 125:150] = 255         # the owner: the blanket is skin too
                    layers[f"skin_{number:02d}.png"] = Image.fromarray(layer)
                gimp.painted["vv1_carrying.xcf"] = layers
                before = {p: p.read_bytes() for p in bench.rglob("*") if p.is_file()}
                said = []
                done = sheets.learn([("vv1", images)], bench, say=said.append)
                self.assertEqual({p: p.read_bytes() for p in bench.rglob("*") if p.is_file()}, before, "nothing written")
                self.assertEqual(done, {"vv1": {}}, "the only sheet is the owner's: never touched")
                self.assertIn("you added 200 pixels to the skin and removed 0", said[0])
                self.assertIn("1 colours are skin", said[1])
                self.assertIn("1 are yours and are never touched: carrying", said[-1])
                self.assertEqual(gimp.read, ["vv1_carrying.xcf"])


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class LearnByOutfit(unittest.TestCase):
    """The owner chose (2026-11-28) to carry what they did on a body to the SAME body's rows of the other
    sheets: an outfit's own colours, never one rule for the whole game."""

    SKIN, ROBE, SASH = (240, 190, 140), (236, 220, 170), (150, 30, 60)
    BIG = {"kind": "bodies", "cell": (80, 130), "sex": None, "first": 0}
    SMALL = {"kind": "bodies", "cell": (40, 65), "sex": "male", "first": 0}

    def big(self):
        """Two bodies, male and female columns: skin above, a robe below (built as skin: the mistake), a sash."""
        art = np.zeros((260, 160, 4), np.uint8)
        for row in (0, 1):
            for col in (0, 1):
                y, x = row * 130, col * 80
                art[y + 10:y + 50, x + 20:x + 60] = self.SKIN + (255,)
                art[y + 50:y + 110, x + 20:x + 60] = self.ROBE + (255,)
                art[y + 50:y + 56, x + 20:x + 60] = self.SASH + (255,)
        built = (art[..., :3] == self.SKIN).all(-1) | (art[..., :3] == self.ROBE).all(-1)
        skin = built.copy()
        skin[0:130, 0:80] &= ~(art[0:130, 0:80, :3] == self.ROBE).all(-1)       # the owner: male body 0's robe is cloth
        return art, built, skin

    def small(self, robe):
        art = np.zeros((130, 80, 4), np.uint8)
        for row in (0, 1):
            for col in (0, 1):
                y, x = row * 65, col * 40
                art[y + 5:y + 25, x + 10:x + 30] = self.SKIN + (255,)
                art[y + 25:y + 55, x + 10:x + 30] = robe + (255,)
        return art, (art[..., 3] > 0)

    def test_an_outfits_edit_goes_to_the_same_body_and_no_other(self):
        art, built, skin = self.big()
        tables = sheets.outfit_tables(self.BIG, art, built, skin)
        self.assertEqual(sorted(tables), [("male", 0)], "only the outfit the owner worked on")
        small, was = self.small((233, 222, 168))                # the same robe, drawn a little differently
        new, matched, skipped = sheets.apply_outfits(self.SMALL, small, was, tables)
        self.assertEqual((matched, skipped), (2, 2), "body 0's two frames; body 1's are left as built")
        self.assertFalse(new[25:55, 10:30].any() or new[25:55, 50:70].any(), "the robe is cloth on body 0's frames")
        self.assertTrue(new[5:25, 10:30].all(), "its skin stays skin")
        self.assertTrue((new[65:] == was[65:]).all(), "body 1 is exactly as built")
        women = dict(self.SMALL, sex="female")
        self.assertTrue((sheets.apply_outfits(women, small, was, tables)[0] == was).all(), "and so is the other sex")

    def test_a_colour_the_outfit_does_not_have_is_left_as_built(self):
        art, built, skin = self.big()
        tables = sheets.outfit_tables(self.BIG, art, built, skin)
        small, was = self.small((200, 220, 170))                # too far from the robe's colour: no decision
        new, _matched, _skipped = sheets.apply_outfits(self.SMALL, small, was, tables)
        self.assertTrue((new == was).all())

    def test_a_colour_the_owner_has_both_ways_decides_nothing(self):
        art, built, skin = self.big()
        skin[80:110, 20:60] = True                              # half of that robe put back as skin
        table = sheets.outfit_tables(self.BIG, art, built, skin)[("male", 0)]
        verdict = sheets.outfit_decide(table, np.array([self.ROBE, self.SKIN, self.SASH]))
        self.assertEqual(verdict.tolist(), [-1, 1, 0])

    def test_a_speck_follows_its_neighbours(self):
        art, built, skin = self.big()
        table = sheets.outfit_tables(self.BIG, art, built, skin)[("male", 0)]
        small, was = self.small(self.ROBE)
        cell, cell_was = small[0:65, 0:40].copy(), was[0:65, 0:40]
        cell[40, 20, :3] = (90, 200, 90)                        # one odd pixel in the middle of the robe
        now, followed = sheets._carry_to_cell(table, cell, cell_was, sheets.OUTFIT_RADIUS)
        self.assertEqual((bool(now[40, 20]), followed), (False, 1))

    def test_the_self_check_learns_from_one_half_and_is_scored_on_the_other(self):
        art, built, skin = self.big()
        check = sheets.outfit_self_check(self.BIG, art, built, skin)
        self.assertEqual(check["removed"], (20 * 54, 20 * 54), "the right half of the robe, all as the owner has it")
        self.assertEqual(check["added"], (0, 0))
        self.assertEqual(check["owner"], (0, 20 * 54))


@unittest.skipUnless(HAVE, "numpy, scipy or Pillow is missing")
class Guides(unittest.TestCase):
    """README.txt and the GIMP tutorial in the workbench folder: written, brought up to date, never over
    the owner's own changes."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bench = Path(tmp.name) / "bench"

    def test_written_then_up_to_date(self):
        self.assertEqual(sheets.write_guides(self.bench), {"README.txt": "written", sheets.TUTORIAL_NAME: "written"})
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_bytes(), sheets.TUTORIAL.read_bytes())
        self.assertEqual(set(sheets.write_guides(self.bench).values()), {"up to date"})

    def test_an_older_one_of_ours_is_brought_up_to_date(self):
        sheets.write_guides(self.bench)
        with mock.patch.object(sheets, "README", sheets.README + "one more line\n"):
            self.assertEqual(sheets.write_guides(self.bench)["README.txt"], "brought up to date")
            self.assertTrue((self.bench / "README.txt").read_text(encoding="utf-8").endswith("one more line\n"))

    def test_one_the_owner_changed_is_kept(self):
        sheets.write_guides(self.bench)
        for name in ("README.txt", sheets.TUTORIAL_NAME):
            (self.bench / name).write_text("my own notes", encoding="utf-8")
        with mock.patch.object(sheets, "README", sheets.README + "one more line\n"):
            done = sheets.write_guides(self.bench)
        self.assertEqual(set(done.values()), {"kept (changed by you)"})
        self.assertEqual((self.bench / "README.txt").read_text(encoding="utf-8"), "my own notes")
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_text(encoding="utf-8"), "my own notes")

    def test_one_with_no_record_is_kept(self):
        self.bench.mkdir(parents=True)
        (self.bench / sheets.TUTORIAL_NAME).write_text("put here by hand", encoding="utf-8")
        self.assertEqual(sheets.write_guides(self.bench)[sheets.TUTORIAL_NAME], "kept (changed by you)")
        self.assertEqual((self.bench / sheets.TUTORIAL_NAME).read_text(encoding="utf-8"), "put here by hand")

    def test_the_tutorial_names_the_layers_as_they_are_built(self):
        text = sheets.TUTORIAL.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.splitlines()]
        top = lines.index(sheets.LAYER_TOP + "   (locked)")
        self.assertTrue(lines[top + 1].startswith(f"{sheets.tone_layer_name(len(sheets.core.TONES))} ... {sheets.tone_layer_name(1)}"))
        self.assertTrue(lines[top + 2].startswith(sheets.LAYER_MASK) and lines[top + 2].endswith("(hidden)"))
        self.assertTrue(lines[top + 3].startswith(sheets.LAYER_GAME) and lines[top + 3].endswith("(locked)"))
        self.assertIn("python scripts\\skin_tone_sheets.py import --game vv1", text)
        self.assertIn('"import" reads the mask\n   the same at any opacity', text)
        inside = lines.index(sheets.LAYER_SHADING.replace(" (locked)", "") + " (locked)              never paint this one")
        self.assertTrue(lines[inside + 1].startswith(sheets.paint_layer_name(len(sheets.core.TONES))))
        for words in ("Pencil tool [N]", "Eraser [Shift+E]", "skin_NN.png"):
            self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
