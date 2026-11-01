"""Picture Studio's Everything tab: the shared pieces (src/vv_pictures_assets.py), the window's tab
(src/vv_picture_studio_everything.py) and what holds for all five games' tables (src/vv_assets_vv<n>.py).

Each game's own drawing rules are proven against its executable in tests/test_assets_vv<n>.py, and the JPEG
reader against the games' own libjpeg in tests/test_vv_jpeg.py.  Here: the framework on synthetic pictures
(always runs), the release (no game art ships, the patcher's art does), and, when research/game-images holds the
games' pictures, that every picture file of every game is listed and every composed entry draws.
"""
from __future__ import annotations

import importlib
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
import vv_pictures_assets as pa  # noqa: E402

IMAGES = ROOT / "research" / "game-images"


def png(width: int, height: int, pixel=lambda x, y: (255, 0, 0, 255)) -> bytes:
    image = pi.Image(width, height)
    for y in range(height):
        for x in range(width):
            at = (y * width + x) * 4
            image.data[at:at + 4] = bytes(pixel(x, y))
    return image.to_png()


class Source:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.problem = ""

    def read(self, name: str):
        return next((v for k, v in self.files.items() if k.casefold() == name.casefold()), None)

    def names(self):
        return list(self.files)


def game_folder(game: int) -> Path:
    return IMAGES / f"Virtual Villagers - {pi.GAME_FOLDERS[game]}"


class Framework(unittest.TestCase):
    def setUp(self) -> None:
        # a 4 x 2 sheet of 8 x 8 cells; a picture with two blobs and a clear gap; an opaque picture
        blobs = png(20, 6, lambda x, y: (0, 0, 255, 255) if (x < 5 or x >= 12) and y < 4 else (0, 0, 0, 0))
        self.sheets = pa.AssetSheets(Source({"sheet.png": png(32, 16), "blobs.png": blobs,
                                             "vvfp_extra.png": png(3, 3), "opaque.png": png(5, 5)}))

    def test_source_sheets_cut_as_the_table_says_and_list_every_other_file(self) -> None:
        table = [pa.SheetSpec("sheet.png", 4, 2, where="0x401000")]
        assets = {a.label: a for a in pa.source_sheet_assets(self.sheets, table)}
        self.assertEqual(set(assets), {"sheet.png", "blobs.png", "vvfp_extra.png", "opaque.png"})
        sheet = assets["sheet.png"]
        self.assertEqual(len(sheet.frames), 8)
        self.assertEqual(sheet.frames[5].plan[0].rect, (8, 8, 16, 16))
        self.assertFalse(sheet.unused)
        self.assertTrue(assets["blobs.png"].unused and assets["blobs.png"].lazy)
        self.assertTrue(assets["vvfp_extra.png"].patcher and not assets["vvfp_extra.png"].unused)
        self.assertEqual(assets["blobs.png"].shown, "blobs.png (unused)")

    def test_an_unused_sheet_is_cut_at_its_own_gaps(self) -> None:
        asset = next(a for a in pa.source_sheet_assets(self.sheets, []) if a.label == "blobs.png")
        frames = pa.frames_of(self.sheets, asset)
        self.assertEqual([f.plan[0].rect for f in frames], [(0, 0, 20, 6), (0, 0, 5, 4), (12, 0, 20, 4)])
        self.assertIn(pa.NOT_PLACED, asset.note)

    def test_patcher_images_are_the_patchers(self) -> None:
        asset = next(a for a in pa.source_sheet_assets(self.sheets, [], patcher_images=["opaque.png"])
                     if a.label == "opaque.png")
        self.assertTrue(asset.patcher)
        self.assertEqual(asset.group, "Added by the patcher")

    def test_render_plan_layers_alpha_tint_and_the_opaque_copy(self) -> None:
        plan = (pi.Draw("opaque.png", (0, 0, 5, 5), 0, 0), pi.Draw("blobs.png", (0, 0, 5, 4), 2, 2, 1.0, 0.5),
                pa.TintDraw("opaque.png", (0, 0, 2, 2), 10, 0, tint=(128, 255, 255)))
        image = pa.render_plan(self.sheets, plan)
        self.assertEqual((image.width, image.height), (12, 6))
        self.assertEqual(image.pixel(0, 0), (255, 0, 0, 255))
        # the faded blue over red, as vv_picture_image's Image.draw blends it
        want = pi.Image(5, 5)
        want.draw(self.sheets.image("opaque.png"), 0, 0)
        want.draw(self.sheets.image("blobs.png").sub(0, 0, 5, 4), 2, 2, pi.surface_alpha(0.5))
        self.assertEqual(image.pixel(3, 3), want.pixel(3, 3))
        self.assertEqual(image.pixel(10, 0), (128, 0, 0, 255))
        self.assertNotEqual(pa.TintDraw("a", (0, 0, 1, 1), 0, 0).key(), pi.Draw("a", (0, 0, 1, 1), 0, 0).key())

    def test_save_assets_by_category_and_group(self) -> None:
        table = [pa.SheetSpec("sheet.png", 4, 2)]
        assets = [pa.one(self.sheets, "o", pa.SCENE, "The island", "opaque.png")] + \
            pa.source_sheet_assets(self.sheets, table)
        target = Path(tempfile.mkdtemp(prefix="vvpa"))
        try:
            saved, failed = pa.save_assets(self.sheets, assets, target, {"scale": 2, "margin": 0})
            self.assertEqual(failed, [])
            self.assertEqual(saved, 1 + 8 + 3 + 1 + 1)
            self.assertTrue((target / "Scene" / "The island.png").is_file())
            cells = target / "Source sheets" / "Built by the game" / "sheet"
            self.assertEqual(len([p for p in cells.glob("*.png") if p.is_file()]), 8)
            picture = pi.decode_png((target / "Scene" / "The island.png").read_bytes())
            self.assertEqual((picture.width, picture.height), (10, 10))
            self.assertTrue((target / "Source sheets" / "Never loaded by the game" / "blobs (unused)").is_dir())
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_an_interlaced_png_reads_as_its_pixels(self) -> None:
        """A few of the games' unused sheets are Adam7-interlaced: read as libpng reads them."""
        w, h = 11, 7
        pixels = [[(x * 20, y * 30, (x + y) * 9, 255 if (x + y) % 3 else 128) for x in range(w)] for y in range(h)]
        raw = bytearray()
        for x0, y0, dx, dy in pa.ADAM7:
            xs, ys = range(x0, w, dx), range(y0, h, dy)
            if not xs or not ys:
                continue
            for y in ys:
                raw += b"\0" + b"".join(bytes(pixels[y][x]) for x in xs)
        head = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 1)
        data = pi.PNG_MAGIC + pi._chunk(b"IHDR", head) + pi._chunk(b"IDAT", zlib.compress(bytes(raw))) + \
            pi._chunk(b"IEND", b"")
        image = pa.decode_picture(data)
        self.assertEqual([[image.pixel(x, y) for x in range(w)] for y in range(h)], pixels)

    def test_all_assets_sorts_by_category(self) -> None:
        class Module:
            @staticmethod
            def sheet_table():
                return [pa.SheetSpec("sheet.png", 4, 2)]

            @staticmethod
            def assets(sheets):
                return [pa.one(sheets, "b", pa.SCREENS, "Title", "opaque.png"),
                        pa.one(sheets, "a", pa.CREATURES, "Fish", "opaque.png")]
        order = [a.category for a in pa.all_assets(1, self.sheets, Module)]
        self.assertEqual(order[:2], [pa.CREATURES, pa.SCREENS])
        self.assertEqual(order[2:], [pa.UNUSED] * 2 + [pa.SHEETS] * 4)     # blobs and opaque are also Unused


class Cache(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="vvpc"))
        self.game = self.tmp / "game"
        (self.game / "Images").mkdir(parents=True)
        (self.game / "Images" / "a.png").write_bytes(png(2, 2))
        (self.game / "Images" / "b.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        (self.game / "Images" / "notes.css").write_text("x")
        self.root = self.tmp / "cache"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_every_picture_is_copied_once_then_read_from_the_cache(self) -> None:
        before = {p.name: p.read_bytes() for p in (self.game / "Images").iterdir()}
        source = pa.picture_source(1, [self.game], root=self.root)
        self.assertIsInstance(source.base, pa.EverythingCache)
        self.assertEqual(sorted(source.names()), ["a.png", "b.jpg"])
        self.assertEqual({p.name: p.read_bytes() for p in (self.game / "Images").iterdir()}, before)
        again = pa.picture_source(1, [], root=self.root)
        self.assertEqual(again.read("A.PNG"), before["a.png"])

    def test_a_changed_cache_file_is_not_used(self) -> None:
        pa.picture_source(1, [self.game], root=self.root)
        (self.root / pi.GAME_FOLDERS[1] / "a.png").write_bytes(png(3, 3))
        self.assertFalse(pa.EverythingCache(1, self.root).ok)
        self.assertIsInstance(pa.picture_source(1, [self.game], root=self.root).base, pa.EverythingCache)

    def test_no_game_folder(self) -> None:
        source = pa.picture_source(3, [], root=self.root)
        self.assertIsNone(source.base)
        self.assertIn("Find game", source.problem)

    def test_patcher_art_in_a_shipped_dll(self) -> None:
        dll = ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll"
        if not dll.is_file():
            self.skipTest("the Origins DLL is not in assets")
        overlay = pa.PatcherOverlay(None, {"masks.png": (dll, 10, 5000)})
        self.assertTrue(overlay.read("masks.png").startswith(pi.PNG_MAGIC))
        self.assertIsNone(pa.read_patcher_art(ROOT / "assets" / "no such file.png"))


class EveryGame(unittest.TestCase):
    """What every game's table must be, without the games' files."""

    def modules(self):
        return [(n, importlib.import_module(f"vv_assets_vv{n}")) for n in range(1, 6)]

    def test_each_module_is_found_by_name(self) -> None:
        for n, module in self.modules():
            with self.subTest(game=n):
                self.assertIs(pa.load_module(n), module)
                self.assertEqual(module.GAME, n)
                specs = module.sheet_table()
                self.assertGreater(len(specs), 50)
                self.assertTrue(all(isinstance(s, pa.SheetSpec) for s in specs))

    def test_origins_icons_and_replacement_art_come_from_what_ships(self) -> None:
        for n in range(1, 6):
            for group in range(101, 111):
                with self.subTest(game=n, icon=group):
                    where = pa.origins_icon(n, group)
                    self.assertIsNotNone(where)
                    self.assertTrue(pa.read_patcher_art(where).startswith(pi.PNG_MAGIC))
        self.assertEqual(sorted(r for _m, r, _p in pa.mod_art(1).values()),
                         ["MapX1Y2.jpg", "MapX2Y1.jpg", "garden_restored.png", "lagoon_restored.jpg"])
        self.assertEqual(len(pa.mod_art(5)), 12)
        self.assertEqual(pa.mod_art(2), {})

    def test_a_game_without_pictures_lists_nothing_and_does_not_fail(self) -> None:
        for n, module in self.modules():
            with self.subTest(game=n):
                sheets = pa.AssetSheets(Source({}))
                self.assertEqual([a for a in module.assets(sheets) if not a.patcher], [])

    def test_the_release_ships_the_code_not_the_games_art(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_release
        files = set(build_release.FILES)
        # The game-art check covers what Picture Studio could ship; the replacement-art patches' own payload
        # folders (Visual Mods, Guardians of Isola: vv_pictures_assets.MOD_ART) are those patches'.
        payloads = ("data/vv1_visual_mods/", "data/guardians_of_isola/")
        shipped = {Path(f).name.casefold() for f in files if not f.startswith(payloads)}
        for name in ("vv_pictures_assets", "vv_picture_studio_everything", "vv_jpeg",
                     *(f"vv_assets_vv{n}" for n in range(1, 6))):
            self.assertIn(f"src/{name}.py", files)
        self.assertIn("docs/picture-studio-assets.md", files)
        for n, module in self.modules():
            game_files = {f.casefold() for s in module.sheet_table() for f in s.files()}
            for name in game_files:
                with self.subTest(game=n, file=name):
                    self.assertNotIn(name, shipped)
            for name, where in module.patcher_art().items():
                with self.subTest(game=n, patcher=name):
                    path = where[0] if isinstance(where, tuple) else where
                    self.assertIn(Path(path).resolve().relative_to(ROOT).as_posix(), files)
                    self.assertIsNotNone(pa.read_patcher_art(where))


@unittest.skipUnless(IMAGES.is_dir(), "the games' pictures (research/game-images) are needed")
class TheGamesPictures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="vvpg"))
        cls.loaded = {}
        for n in range(1, 6):
            if game_folder(n).is_dir():
                cls.loaded[n] = pa.load(n, [game_folder(n)], root=cls.tmp)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_picture_file_is_listed(self) -> None:
        for n, (sheets, _module, assets, problem) in self.loaded.items():
            with self.subTest(game=n):
                self.assertEqual(problem, "")
                listed = {d.file.casefold() for a in assets for f in a.frames for d in f.plan}
                files = {f.casefold() for f in pa.game_pictures(game_folder(n))}
                self.assertEqual(files - listed, set())
                keys = [a.key for a in assets]
                self.assertEqual(len(keys), len(set(keys)))
                self.assertTrue(all(a.category in pa.CATEGORIES for a in assets))
                self.assertTrue(all(a.frames for a in assets))

    def test_every_composed_entry_draws(self) -> None:
        for n, (sheets, _module, assets, _problem) in self.loaded.items():
            for asset in assets:
                if asset.category == pa.SHEETS:
                    continue
                with self.subTest(game=n, asset=asset.key):
                    image = pa.render_frame(sheets, asset.frames[len(asset.frames) // 2])
                    self.assertGreater(image.width * image.height, 0)
                    for frame in asset.frames:
                        for draw in frame.plan:
                            w, h = sheets.size(draw.file)
                            l, t, r, b = draw.rect
                            self.assertTrue(0 <= l <= r <= w and 0 <= t <= b <= h, (draw, w, h))


class Window(unittest.TestCase):
    """The tab inside the real window, on a synthetic game folder."""

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
        import vv_pictures_common as common
        self.ps, self.common = ps, common
        self.tmp = Path(tempfile.mkdtemp(prefix="vvpe"))
        game = self.tmp / "game"
        (game / "Images").mkdir(parents=True)
        (game / "Images" / "a.png").write_bytes(png(4, 4))
        (game / "Images" / "b.png").write_bytes(png(6, 2, lambda x, y: (0, 255, 0, 255) if x != 2 else (0, 0, 0, 0)))
        self.saved = (common.save_folders, pi.CACHE_ROOT, pa.load_module)
        common.save_folders = lambda game_, documents=None: []
        pi.CACHE_ROOT = self.tmp / "cache"

        class Module:
            GAME = 1

            @staticmethod
            def sheet_table():
                return [pa.SheetSpec("a.png", 2, 2)]

            @staticmethod
            def assets(sheets):
                return [pa.one(sheets, "t", pa.TECH, "Farming bar", "a.png")] if sheets.has("a.png") else []

            @staticmethod
            def patcher_art():
                return {}
        pa.load_module = lambda n: Module
        self.window = ps.open_window(self.root, 1, game_folders=[game])
        self.window.quiet = True
        self.root.update()

    def tearDown(self) -> None:
        self.window.close()
        self.common.save_folders, pi.CACHE_ROOT, pa.load_module = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_list_show_and_save(self) -> None:
        tab = self.window.everything
        tab.load()
        tree = tab.tree
        # (A New Home's Visual Mods art is the patcher's own, always listed)
        self.assertEqual([tree.item(n, "text") for n in tree.get_children()],
                         [pa.TECH, pa.PATCHER, pa.UNUSED, pa.SHEETS])
        node = next(n for n, a in tab.nodes.items() if a.label == "b.png")
        tree.selection_set(node)
        tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        self.assertEqual(len(tab.frame_box.cget("values")), 3)       # whole and its two pieces
        out = self.tmp / "out"
        out.mkdir()
        self.assertTrue(tab.save_png(str(out / "b.png")).is_file())
        target = tab.save_all(str(out), category=pa.SHEETS)
        self.assertEqual(len([p for p in target.rglob("*.png") if p.is_file()]), 4 + 3)
        everything = tab.save_all(str(out))
        self.assertTrue((everything / "UI - Tech screen" / "Farming bar.png").is_file())

    def test_the_tab_is_there_beside_the_villager_tabs(self) -> None:
        notebook = self.window.notebook
        titles = [notebook.tab(t, "text") for t in notebook.tabs()]
        self.assertEqual(titles[-1], "Everything")


if __name__ == "__main__":
    unittest.main()
