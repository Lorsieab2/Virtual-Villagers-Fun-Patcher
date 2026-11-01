"""Picture Studio (Tools tab): the shared pieces and the window.

* src/vv_picture_image.py: the engine's atlas cut (single sheets and grids, clamping and wrapping, as A New
  Home's 0x409F90 cuts them -- proven against the game in tests/test_pictures_vv1.py), the place-scaled
  centring, the blitter's box-average downscale and surface alpha (proven pixel for pixel against the game's
  blitter in tests/test_pictures_vv1.py), PNG round trips, export sizes, and the Studio's picture cache (built
  from a game folder's Images and Assets, all or nothing, checked against its manifest).
* src/vv_pictures_common.py: the patcher's head-look file, read as native/vvfp_head_look keeps it.
* src/vv_picture_studio.py: the window on a fake renderer -- the save list, a picture, Make your own, Save PNG,
  Save all in a group and Save the whole village into new folders; Find game... refuses a folder that is not
  the game's.  Skips when there is no Tk display.
* The release zip carries every module, and the Tools tab opens the window.

Everything here is synthetic: never the owner's saves, never game art.
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_common as common  # noqa: E402


def solid(w: int, h: int, rgba=(10, 20, 30, 255)) -> pi.Image:
    return pi.Image(w, h, bytes(rgba) * (w * h))


def numbered(w: int, h: int) -> pi.Image:
    """Every pixel different: (x, y, x + y, 255)."""
    image = pi.Image(w, h)
    for y in range(h):
        for x in range(w):
            at = (y * w + x) * 4
            image.data[at:at + 4] = bytes((x % 256, y % 256, (x + y) % 256, 255))
    return image


class AtlasCut(unittest.TestCase):
    def test_one_sheet(self) -> None:
        atlas = pi.Atlas("male_heads.png", 7, 20)
        size = {"male_heads.png": (280, 1300)}.get
        self.assertEqual(atlas.cell(size, 0, 0), ("male_heads.png", (0, 0, 40, 65)))
        self.assertEqual(atlas.cell(size, 6, 19), ("male_heads.png", (240, 1235, 280, 1300)))
        # past the last column or row: clamped, as 0x409F90 does
        self.assertEqual(atlas.cell(size, 9, 25), ("male_heads.png", (240, 1235, 280, 1300)))

    def test_a_grid_of_sheets(self) -> None:
        atlas = pi.Atlas("male_bodies", 32, 20, sheets=(2, 2))
        self.assertEqual(atlas.files(), ["male_bodies00.png", "male_bodies10.png", "male_bodies01.png",
                                         "male_bodies11.png"])
        size = lambda _name: (640, 650)  # noqa: E731
        self.assertEqual(atlas.cell(size, 0, 0), ("male_bodies00.png", (0, 0, 40, 65)))
        self.assertEqual(atlas.cell(size, 17, 0), ("male_bodies10.png", (40, 0, 80, 65)))
        self.assertEqual(atlas.cell(size, 3, 12), ("male_bodies01.png", (120, 130, 160, 195)))
        self.assertEqual(atlas.cell(size, 31, 19), ("male_bodies11.png", (600, 585, 640, 650)))
        # a row past the grid wraps to the sheets from the start (the sheet index modulo the sheet count)
        self.assertEqual(atlas.cell(size, 0, 20), ("male_bodies00.png", (0, 0, 40, 65)))

    def test_a_three_page_grid(self) -> None:
        atlas = pi.Atlas("female_bodies", 32, 30, sheets=(2, 3))
        size = lambda _name: (640, 650)  # noqa: E731
        self.assertEqual(atlas.cell(size, 20, 29), ("female_bodies12.png", (160, 585, 200, 650)))

    def test_centring_and_scales(self) -> None:
        self.assertEqual(pi.centre_offset(40, 65, 100), (0, 0))
        # 80 %: rounded 32 x 52 (ftol(w x s + 0.5)); the cell moves by half the shrink, C division
        self.assertEqual(pi.centre_offset(40, 65, 80), (4, 6))
        self.assertEqual(pi.percent_scale(80), struct.unpack("<f", struct.pack("<f", 80 * pi.f32(0.01)))[0])
        self.assertEqual(pi.scaled_size(40, 65, pi.percent_scale(80)), (31, 51))
        self.assertEqual(pi.surface_alpha(0.5), 128)
        self.assertEqual(pi.surface_alpha(0.9), 229)          # the 32-bit 0.9 is just under 0.9
        self.assertEqual(pi.surface_alpha(1.0), 255)


class Blitter(unittest.TestCase):
    def test_unscaled_is_the_cell(self) -> None:
        sheet = numbered(20, 10)
        self.assertEqual(pi.blit_piece(sheet, (4, 2, 9, 7), 1.0), sheet.sub(4, 2, 5, 5))

    def test_half_size_averages_two_by_two(self) -> None:
        sheet = pi.Image(4, 4)
        for i, value in enumerate((0, 100, 200, 40) * 4):
            sheet.data[i * 4:i * 4 + 4] = bytes((value, value, value, 255 if value else 0))
        piece = pi.blit_piece(sheet, (0, 0, 4, 4), 0.5)
        self.assertEqual((piece.width, piece.height), (2, 2))
        # the boxes run from the last one's end + 1 to trunc(position) + 1 (never past the cell), the
        # position starting half a step before the cell and growing by 2: x (and y) 0..2, then 3..3.
        # Plain averages of every channel, alpha included: (0 + 100 + 200) / 3, (0 + 255 + 255) / 3.
        self.assertEqual(piece.pixel(0, 0), (100, 100, 100, 170))
        self.assertEqual(piece.pixel(1, 0), (40, 40, 40, 255))

    def test_surface_alpha_on_draw(self) -> None:
        canvas = pi.Image(1, 1)
        canvas.draw(solid(1, 1, (200, 100, 50, 255)), 0, 0, pi.surface_alpha(0.5))
        self.assertEqual(canvas.pixel(0, 0), (200, 100, 50, (255 * 128 + 127) >> 8))

    def test_render_plan_crops_to_the_blits(self) -> None:
        class Source:
            def read(self, name):
                return numbered(40, 65).to_png() if name == "a.png" else None
        sheets = pi.Sheets(Source())
        plan = [pi.Draw("a.png", (0, 0, 40, 65), 100, 200), pi.Draw("a.png", (0, 0, 20, 30), 90, 250, what="x")]
        image = pi.render_plan(sheets, plan)
        self.assertEqual((image.width, image.height), (50, 80))
        self.assertEqual(plan[0].key(), ("a.png", (0, 0, 40, 65), 100, 200, 1.0, 255))
        with self.assertRaises(pi.PictureError):
            pi.render_plan(sheets, [pi.Draw("missing.png", (0, 0, 1, 1), 0, 0)])

    def test_png_round_trip_and_export(self) -> None:
        image = pi.Image(5, 3)
        image.data[(1 * 5 + 2) * 4:(1 * 5 + 2) * 4 + 4] = bytes((1, 2, 3, 200))
        self.assertEqual(pi.decode_png(image.to_png()), image)
        out = pi.export(image, scale=4, margin=0)
        self.assertEqual((out.width, out.height), (4, 4))
        out = pi.export(image, scale=1, margin=pi.MARGIN)
        self.assertEqual((out.width, out.height), (1 + 2 * pi.MARGIN, 1 + 2 * pi.MARGIN))
        self.assertEqual(pi.export(image, size=(20, 0), margin=0).width, 20)
        with self.assertRaises(pi.PictureError):
            pi.export(image, size=(0, 0))

    def test_pe_resource_reads_a_companions_picture(self) -> None:
        dll = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
        if not dll.is_file():
            self.skipTest("the companion is not in this checkout")
        data = pi.pe_resource(dll.read_bytes(), 10, 5000)
        self.assertTrue(data.startswith(pi.PNG_MAGIC))
        self.assertIsNone(pi.pe_resource(dll.read_bytes(), 10, 4999))
        self.assertIsNone(pi.pe_resource(b"not a PE", 10, 5000))


class Cache(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="vvps"))
        self.game = self.tmp / "game"
        (self.game / "Images").mkdir(parents=True)
        (self.game / "Assets").mkdir()
        for name in ("a.png", "b.png"):
            (self.game / "Images" / name).write_bytes(solid(4, 4).to_png())
        (self.game / "Assets" / "animpts.dat").write_bytes(b"\x01\x02\x03")
        self.root = self.tmp / "cache"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_built_once_then_read_from_the_cache(self) -> None:
        source = pi.picture_source(4, [self.tmp / "nowhere", self.game], ["a.png", "b.png"], root=self.root,
                                   data_files=["animpts.dat"])
        self.assertEqual(source.problem, "")
        self.assertEqual(source.read("a.png"), (self.game / "Images" / "a.png").read_bytes())
        self.assertEqual(source.read("Assets/animpts.dat"), b"\x01\x02\x03")
        self.assertEqual(source.read("animpts.dat"), b"\x01\x02\x03")
        manifest = json.loads((self.root / "The Tree of Life" / pi.MANIFEST).read_text(encoding="utf-8"))
        self.assertTrue(manifest["files"]["animpts.dat"]["data"])
        # the game folder may go: the cache holds everything
        shutil.rmtree(self.game)
        again = pi.picture_source(4, [], ["a.png", "b.png"], root=self.root, data_files=["animpts.dat"])
        self.assertEqual(again.read("animpts.dat"), b"\x01\x02\x03")

    def test_a_changed_cache_file_is_not_used(self) -> None:
        pi.picture_source(1, [self.game], ["a.png"], root=self.root)
        (self.root / "A New Home" / "a.png").write_bytes(solid(4, 4, (9, 9, 9, 9)).to_png())
        self.assertFalse(pi.CacheSource(1, ["a.png"], self.root).ok)

    def test_a_folder_without_every_picture_is_not_the_game(self) -> None:
        self.assertFalse(pi.is_game_folder(1, self.game, ["a.png", "c.png"]))
        self.assertFalse(pi.is_game_folder(4, self.game, ["a.png"], ["anims.dat"]))
        source = pi.picture_source(1, [self.game], ["a.png", "c.png"], root=self.root)
        self.assertIn("Find game", source.problem)
        self.assertIsNone(source.read("a.png"))

    def test_patcher_art_comes_first(self) -> None:
        art = self.tmp / "mine.png"
        art.write_bytes(b"patcher")
        source = pi.picture_source(1, [self.game], ["a.png"], {"Mine.png": art}, root=self.root)
        self.assertEqual(source.read("mine.png"), b"patcher")

    def test_the_game_folder_is_only_read(self) -> None:
        before = {p: p.read_bytes() for p in self.game.rglob("*") if p.is_file()}
        pi.picture_source(4, [self.game], ["a.png", "b.png"], root=self.root, data_files=["animpts.dat"])
        self.assertEqual({p: p.read_bytes() for p in self.game.rglob("*") if p.is_file()}, before)


class HeadLooks(unittest.TestCase):
    """native/vvfp_head_look/head_look_store.inc's file, read as the companion follows a look."""

    def villager(self, game: int, name: bytes, rank: int) -> common.SaveVillager:
        data = bytearray(0x200)
        at = 0x100
        data[at:at + len(name)] = name
        if game == 1:
            struct.pack_into("<i", data, at - 0x20, 2)            # sex (+0x350)
            struct.pack_into("<i", data, at - 4, 7)               # family (+0x36C)
        else:
            lay = common._checker().LAYOUTS[game]
            struct.pack_into("<i", data, at + lay.gender, 1)
            data[at + lay.father:at + lay.father + 4] = b"Dad\0"
        return common.SaveVillager(rank, name.decode(), False, 400, 3, 4, 100, at, bytes(data))

    def test_identity_is_the_companions(self) -> None:
        v = self.villager(1, b"Aki", 0)
        h = 2166136261
        for b in v.data[v.at - 0x20:v.at - 0x1C] + v.data[v.at - 4:v.at]:
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
        stable = h
        h = 2166136261
        for b in b"Aki":
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
        h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
        h = ((h ^ stable) * 16777619) & 0xFFFFFFFF
        self.assertEqual(common.head_look_identity(1, v), h)

    def test_each_look_follows_its_villager(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="vvhl"))
        try:
            people = [self.villager(4, b"Aki", 0), self.villager(4, b"Bo", 1), self.villager(4, b"Cy", 2)]
            count = 150
            ids = [0] * count
            looks = [0] * count
            ids[5], looks[5] = common.head_look_identity(4, people[1]), common.LOOK_OLD      # moved since written
            ids[9], looks[9] = common.head_look_identity(4, people[2]), common.LOOK_YOUNG
            ids[11], looks[11] = 12345, common.LOOK_OLD                                       # nobody now
            raw = b"VHL2" + struct.pack("<II", 4, count) + struct.pack(f"<{count}I", *([0] * count)) \
                + struct.pack(f"<{count}I", *ids) + bytes(looks)
            path = tmp / "Virtual Villagers Fun Patcher" / "Save 2" / "Data" / "Head Looks"
            path.mkdir(parents=True)
            (path / "Head Looks - Save 2.dat").write_bytes(raw)
            self.assertEqual(common.head_looks_by_rank(tmp, 4, 2, people), {1: common.LOOK_OLD, 2: common.LOOK_YOUNG})
            # another game's file is not read
            (path / "Head Looks - Save 2.dat").write_bytes(raw[:4] + struct.pack("<I", 5) + raw[8:])
            self.assertEqual(common.head_looks_by_rank(tmp, 4, 2, people), {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_old_head(self) -> None:
        self.assertFalse(common.old_head(1099))
        self.assertTrue(common.old_head(1100))
        self.assertTrue(common.old_head(0, common.LOOK_OLD))
        self.assertFalse(common.old_head(3000, common.LOOK_YOUNG))


class Release(unittest.TestCase):
    def test_every_module_ships(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name in ["vv_picture_studio", "vv_picture_image", "vv_pictures_common"] + \
                [f"vv_pictures_vv{n}" for n in range(1, 6)]:
            with self.subTest(module=name):
                self.assertIn(f'"src/{name}.py"', release)
        self.assertIn('"docs/picture-studio.md"', release)

    def test_no_game_art_ships(self) -> None:
        """Picture Studio reads the games' pictures (and drawing tables) from the player's own copy: the
        release zip carries none of the files any renderer reads from the game, and the patcher art it draws
        with is the patcher's own (assets\\, or a shipped companion)."""
        import importlib
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_release
        shipped = {Path(f).name.casefold() for f in build_release.FILES}
        for n in range(1, 6):
            module = importlib.import_module(f"vv_pictures_vv{n}")
            game = list(module.required_files()) + list(getattr(module, "required_data_files", lambda: [])())
            for name in game:
                with self.subTest(game=n, file=name):
                    self.assertNotIn(Path(name).name.casefold(), shipped)
            for name, path in module.patcher_art().items():
                with self.subTest(game=n, patcher=name):
                    self.assertNotIn(name.casefold(), {g.casefold() for g in game})
                    self.assertTrue(Path(path).resolve().is_relative_to(ROOT / "assets"), path)
                    if n == 3:
                        # The release carries The Secret City's atlas inside its Origins companion, which the
                        # renderer reads when the loose file is not there (tests/test_pictures_vv3.py).
                        self.assertIn(module.SHIPPED_DLL.relative_to(ROOT).as_posix(), build_release.FILES)
                    else:
                        self.assertIn(Path(path).relative_to(ROOT).as_posix(), build_release.FILES)
        # The Lost Children's masks come from inside its shipped Origins companion.
        import vv_pictures_vv2
        self.assertIn(vv_pictures_vv2.ORIGINS_DLL.relative_to(ROOT).as_posix(), build_release.FILES)

    def test_from_my_save_offers_every_pose_control_make_your_own_has(self) -> None:
        """Codex (PR #660, The Secret City's carried item): what the save does not keep -- pose, direction,
        frame, head turn, carried item, litter, shadow... -- is picked on From my save with the same
        controls Make your own has, in every game.  Left out: what the save itself gives (appearance,
        age, mask, head look, and the fields named below)."""
        import importlib
        from_save = {"sex", "stage", "life", "head", "body", "mask", "look",
                     "expecting", "dead_frame", "skeleton"}      # The Tree of Life / The Lost Children: the save's own
        for n in range(1, 6):
            module = importlib.import_module(f"vv_pictures_vv{n}")
            renderer = module.load(pi.Pictures(n, None))
            saved = {f.key for f in renderer.saved_fields()}
            for subject in renderer.custom_choices():
                if subject.key != "villager":
                    continue
                for field in subject.fields:
                    if field.key in from_save:
                        continue
                    with self.subTest(game=n, field=field.key):
                        self.assertIn(field.key, saved)

    def test_the_tools_tab_opens_it(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("vv_picture_studio.open_picture_studio(self, None)", source)
        self.assertIn('_help_button(genealogy_tools, "picture_studio")', source)


# ------------------------------------------------------------------ the window, on a fake renderer

class FakeRenderer:
    game = 2
    problem = ""

    def __init__(self) -> None:
        self.calls = []

    def saved_items(self, folder, slot):
        return [pi.SavedItem("0", "Aki (adult, 30 years)", "Villagers", "villager", "detail"),
                pi.SavedItem("1", "Bo (child, 5 years)", "Villagers", "villager"),
                pi.SavedItem("2", "Cy (adult, 70 years)", "Bodies awaiting burial", "body")]

    def saved_fields(self):
        return (pi.Field("frame", "Frame", tuple(pi.Option(k, f"Frame {k + 1}") for k in range(3)), 1),
                pi.Field("skeleton", "Skeleton", (pi.Option(None, "As the save has it"), pi.Option(2, "Frame 3")),
                         None))

    def render_saved(self, folder, slot, item_id, **pose):
        self.calls.append(("saved", item_id, pose))
        if item_id == "2":
            raise pi.PictureError("cannot")
        return solid(3 + int(item_id), 5)

    def custom_choices(self):
        return [pi.Subject("villager", "Villager", (
            pi.Field("sex", "Sex", (pi.Option("male", "Male"), pi.Option("female", "Female")), "female"),
            pi.Field("mask", "Mask", (pi.Option(0, "(None)"), pi.Option(1, "Blue Mask", patcher=True)), 0)))]

    def render_custom(self, spec):
        self.calls.append(("custom", dict(spec)))
        return solid(7, 9)


class FakeModule:
    GAME = 2

    @staticmethod
    def required_files():
        return ["a.png"]

    @staticmethod
    def patcher_art():
        return {}

    renderer = None

    @classmethod
    def load(cls, source):
        cls.renderer = FakeRenderer()
        return cls.renderer


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import tkinter as tk
        try:
            cls.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"no Tk display: {exc}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def setUp(self) -> None:
        import vv_picture_studio as ps
        self.ps = ps
        self.tmp = Path(tempfile.mkdtemp(prefix="vvpw"))
        self.saves = self.tmp / "saves"
        self.saves.mkdir()
        self.saved = (ps.load_renderer_module, common.save_folders, common.slots, pi.CACHE_ROOT)
        ps.load_renderer_module = lambda game: FakeModule
        common.save_folders = lambda game, documents=None: [self.saves]
        common.slots = lambda folder, game: [(1, "Kalahuna Tribe 2")]
        pi.CACHE_ROOT = self.tmp / "cache"
        self.window = ps.open_window(self.root, 2)
        self.window.quiet = True
        self.root.update()

    def tearDown(self) -> None:
        self.window.close()
        self.ps.load_renderer_module, common.save_folders, common.slots, pi.CACHE_ROOT = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def select(self, label: str) -> None:
        node = next(n for n, item in self.window.item_nodes.items() if item.label == label)
        self.window.save_tree.selection_set(node)
        self.window.save_tree.event_generate("<<TreeviewSelect>>")
        self.root.update()

    def test_the_save_list_and_a_picture(self) -> None:
        w = self.window
        self.assertEqual(w.game, 2)
        self.assertEqual([i.label for i in w.items], ["Aki (adult, 30 years)", "Bo (child, 5 years)",
                                                     "Cy (adult, 70 years)"])
        self.assertEqual(set(w.location_nodes), {"Villagers", "Bodies awaiting burial"})
        self.select("Aki (adult, 30 years)")
        self.assertEqual(w.shown["save"], solid(3, 5))
        # the pose pickers' defaults, a None key included
        self.assertEqual(FakeModule.renderer.calls[-1], ("saved", "0", {"frame": 1, "skeleton": None}))
        self.select("Cy (adult, 70 years)")
        self.assertNotIn("save", w.shown)

    def test_save_png_and_groups(self) -> None:
        w = self.window
        self.select("Bo (child, 5 years)")
        w.size_var.set("2x")
        path = w.save_png("save", str(self.tmp / "bo.png"))
        image = pi.decode_png(path.read_bytes())
        self.assertEqual((image.width, image.height), ((4 + 2 * pi.MARGIN) * 2, (5 + 2 * pi.MARGIN) * 2))
        group = w.save_group(str(self.tmp))
        self.assertEqual(sorted(p.name for p in group.iterdir()),
                         ["Aki (adult, 30 years).png", "Bo (child, 5 years).png"])
        village = w.save_village(str(self.tmp))
        self.assertEqual(sorted(p.name for p in village.iterdir()), ["Bodies awaiting burial", "Villagers"])
        self.assertIn("Cy (adult, 70 years): cannot", w.last_message)
        self.assertEqual(len(list((village / "Villagers").iterdir())), 2)
        w.size_var.set("custom")
        w.width_var.set("x")
        self.assertIsNone(w.save_png("save", str(self.tmp / "bad.png")))
        self.assertIn("whole number", w.last_message)

    def test_make_your_own(self) -> None:
        w = self.window
        self.assertEqual(w.custom_spec(), {"subject": "villager", "sex": "female", "mask": 0})
        box = w.custom_boxes["villager"]["mask"]["box"]
        self.assertEqual(box.cget("values")[1], "Blue Mask" + self.ps.PATCHER_MARK)
        box.current(1)
        box.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(FakeModule.renderer.calls[-1], ("custom", {"subject": "villager", "sex": "female", "mask": 1}))
        path = w.save_png("custom", str(self.tmp / "made.png"))
        self.assertTrue(path.is_file())
        self.assertEqual(w.picture_name("custom"), "Female - Blue Mask")

    def test_find_game_refuses_a_folder_that_is_not_the_game(self) -> None:
        result = self.window.find_game(str(self.tmp))
        self.assertIn("is not a", result)

    def test_find_game_copies_the_pictures(self) -> None:
        game = self.tmp / "My Game"
        (game / "Images").mkdir(parents=True)
        (game / "Images" / "a.png").write_bytes(solid(2, 2).to_png())
        self.assertEqual(self.window.find_game(str(game)), "")
        self.assertTrue((self.tmp / "cache" / "The Lost Children" / "a.png").is_file())

    def test_export_options(self) -> None:
        self.assertEqual(self.ps.export_options("4x"), {"margin": pi.MARGIN, "scale": 4})
        self.assertEqual(self.ps.export_options("custom", "100", "", margin=False), {"margin": 0, "size": (100, 0)})


class GreyHairDetection(unittest.TestCase):
    def test_a_patched_game_folder(self) -> None:
        import vv_picture_studio as ps
        tmp = Path(tempfile.mkdtemp(prefix="vvgh"))
        try:
            self.assertIsNone(ps.grey_hair_patched([tmp / "none"]))
            (tmp / "Images").mkdir()
            self.assertFalse(ps.grey_hair_patched([tmp]))
            for name in ps.GREY_HAIR_FILES:
                (tmp / "Images" / name).write_bytes(b"x")
            self.assertTrue(ps.grey_hair_patched([tmp]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
