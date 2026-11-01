"""Picture Studio's Text tab (src/vv_pictures_text.py): the games' own text drawing, proven.

* The tables: data/vv_font_tables.json is what the stock executables hold (scripts/build_vv_font_tables.py
  --check), and each font's line height, letter spacing, cells and byte index are what the game's own font
  loader leaves in memory, run in Unicorn on the stock executable.
* The draw: every game's own text draw (and its centred draw, and its width) run in Unicorn on sample
  strings -- every byte 0x01-0xFF among them, several lines, several places and colours -- and every blit it
  makes (the sheet cell, the place, the fade, the recolour mask) equals the renderer's plan.
* The Unicode renderer: text the font can draw is drawn pixel for pixel as the game draws it, accents and
  other scripts and emoji are made, the sources are told apart, the name counter and the character search.

Everything emulated needs Unicorn, pefile and the stock executables (research/stock-executables), and skips
without them (CI); the pictures tests need research/game-images.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_text as text  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_UNICORN = True
except ImportError:                                    # CI: no Unicorn
    HAVE_UNICORN = False

EXES = ROOT / "research" / "stock-executables"
ART = ROOT / "research" / "game-images"
FPCW = 0x027F


def exe_path(game: int) -> Path:
    return EXES / f"Virtual Villagers - {text.TITLES[game]}.exe"


def images(game: int) -> Path:
    return ART / f"Virtual Villagers - {text.TITLES[game]}" / "Images"


def can_emulate(game: int) -> bool:
    return HAVE_UNICORN and exe_path(game).is_file()


def have_art(game: int) -> bool:
    return all((images(game) / name).is_file() for name in text.sheet_names(game))


# Each game's routines (docs/picture-studio-text.md "The game's text code").  `draw` is the renderer's text
# draw (thiscall renderer; text, x, y, colour, font), `centred` the graphics object's (ecx = {renderer};
# text, cx, y, colour, font), `width` the font's (ecx = font; text, float scale).
GAMES = {
    1: dict(new=0x44AF03, delete=0x44AEAE, exists=0x40A490, img_ctor=0x40A530, img_surface=None,
            ctor={"arialbold": 0x412790, "burweed": 0x4126F0},
            draw=0x409160, centred=0x4094C0, boxed=0x409510, width=0x402160, faded=0x403D70),
    2: dict(new=0x467F83, delete=0x467F2E, exists=0x40A690, img_ctor=0x40A730, img_surface=None,
            ctor={"arialbold": 0x413160, "burweed": 0x4130F0},
            draw=0x409360, centred=0x4096B0, boxed=0x409700, width=0x4021F0, faded=0x404000),
    3: dict(new=0x46EC93, delete=0x46EC3E, exists=0x40B330, img_ctor=0x40B3D0, img_surface=None,
            ctor={"arialbold": 0x424540, "burweed": 0x4244B0},
            draw=0x409CD0, centred=0x40A070, boxed=None, width=0x402230, faded=0x404620),
    4: dict(new=0x470C5C, delete=0x470B7B, exists=0x40AF70, img_ctor=0x40B050, img_surface=0x41DDD0,
            ctor={"arialbold": 0x41D820, "burweed": 0x41D890},
            draw=0x409700, centred=0x409BE0, boxed=None, width=0x402430, faded=0x404CB0),
    5: dict(new=0x47BBDC, delete=0x47BAFB, exists=0x40B470, img_ctor=0x40B550, img_surface=0x41EFF0,
            ctor={"arialbold": 0x41E840, "burweed": 0x41E8B0},
            draw=0x409930, centred=0x409EB0, boxed=None, width=0x4023E0, faded=0x404C40),
}

SAMPLES = (
    b"Hello, World!",
    b"The quick brown fox jumps over the lazy dog 0123456789",
    b"Line one\nLine two\n\nLine four",
    b"Caf\xe9 \xc0\xe7\xf1\xfc\xdf \xa9 \x80\x9f",
    b"abcdefghijklmnopqrs",
    bytes(range(1, 10)) + bytes(range(11, 256)),       # every byte but NUL and the line break
)
COLOURS = (0xFFFFFFFF, 0xFF0080FF, 0x80FFFFFF, 0x4000FF00, 0x00123456)
PLACES = ((0, 0), (37, 11), (300, 205))


def s32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def f32bits(x: float) -> int:
    return struct.unpack("<I", struct.pack("<f", x))[0]


def bits_f32(v: int) -> float:
    return struct.unpack("<f", struct.pack("<I", v & 0xFFFFFFFF))[0]


class GameText:
    """One game in Unicorn: its two fonts built by its own constructors and loader, a renderer whose text
    draw records every blit.  Only operator new / delete, the file check, the picture object (an SDL
    surface of the stock sheet's size, every pixel white), the SDL calls the recolour makes and the two
    blits (recorded) are stood in for."""

    def __init__(self, game: int) -> None:
        self.game = game
        c = self.c = GAMES[game]
        p = self.p = Process(exe_path(game).read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name:
                    stub = API_STUBS + slot * 16
                    slot += 1
                    p.mu.mem_write(stub, b"\xC3")
                    p.api_names[stub] = imp.name.decode()
                    p.mu.mem_write(imp.address, struct.pack("<I", stub))
        self.sizes = {info["sheet"].casefold(): tuple(info["sheet_size"]) for info in text.font_infos(game)}
        self.names: dict[int, str] = {}
        self.masks: dict[int, int] = {}
        self.blits: list[tuple] = []
        p.stub(c["new"], lambda q: (q.alloc(max(q.arg(0), 4)), 0))
        p.stub(c["delete"], lambda q: (0, 0))
        p.stub(c["exists"], lambda q: (1, 0))
        p.stub(c["img_ctor"], self._picture)
        if c["img_surface"]:
            p.stub(c["img_surface"], lambda q: (q.u32(q.reg("ecx")), 0))
        p.stub(c["faded"], self._faded)
        p.api_handlers.update({
            "SDL_CreateRGBSurface": self._create,
            "SDL_LockSurface": lambda q: (0, 0),
            "SDL_UnlockSurface": lambda q: (0, 0),
            "SDL_FreeSurface": lambda q: (0, 0),
            "SDL_MapRGBA": lambda q: ((q.arg(1) & 0xFF) | (q.arg(2) & 0xFF) << 8 | (q.arg(3) & 0xFF) << 16
                                      | (q.arg(4) & 0xFF) << 24, 0),
            "SDL_UpperBlit": self._blit,
        })
        self.format = p.alloc(0x40)
        p.write(self.format + 8, bytes((32, 4)))
        p.write(self.format + 0xC, struct.pack("<4I", 0xFF, 0xFF00, 0xFF0000, 0xFF000000))
        self.screen = self.surface(16, 16, "screen")
        self.renderer = p.alloc(0x200)
        p.put32(self.renderer + 0x30, self.screen)
        p.write(self.renderer + 0x60, struct.pack("<4i", -100000, -100000, 100000, 100000))
        self.graphics = p.alloc(0x10)
        p.put32(self.graphics, self.renderer)
        self.fonts = {}
        for key, ctor in c["ctor"].items():
            obj = p.alloc(0x10)
            self.call(ctor, [], ecx=obj)
            self.fonts[key] = obj
        p.put32(self.renderer + 0x5C, self.fonts["burweed"])

    def call(self, fn: int, args, ecx=None) -> int:
        self.p.mu.reg_write(UC_X86_REG_FPCW, FPCW)
        return self.p.call(fn, list(args), ecx=ecx, limit=20_000_000)

    def surface(self, w: int, h: int, name: str) -> int:
        p = self.p
        s = p.alloc(0x40)
        p.put32(s + 4, self.format)
        p.put32(s + 8, w)
        p.put32(s + 0xC, h)
        p.put32(s + 0x10, w * 4)
        pixels = p.alloc(max(4, w * h * 4))
        p.write(pixels, b"\xFF" * (w * h * 4))
        p.put32(s + 0x14, pixels)
        self.names[s] = name
        return s

    def bytes_(self, data: bytes) -> int:
        at = self.p.alloc(len(data) + 1)
        self.p.write(at, data + b"\0")
        return at

    # ---- the stand-ins
    def _picture(self, q):
        name = q.cstring(q.arg(0)).replace("/", "\\").rsplit("\\", 1)[-1]
        w, h = self.sizes[name.casefold()]
        q.put32(q.reg("ecx"), self.surface(w, h, name))
        q.write(q.reg("ecx") + 4, b"\x01")
        return q.reg("ecx"), 4

    def _create(self, q):
        s = self.surface(s32(q.arg(1)), s32(q.arg(2)), "recolour")
        return s, 0

    def _mask(self, surface: int) -> int:
        """The recolour's AND mask: the first pixel of a recoloured copy of the all-white sheet."""
        if self.names.get(surface) != "recolour":
            return 0xFFFFFFFF
        return self.p.u32(self.p.u32(surface + 0x14))

    def _blit(self, q):
        src, rect_at, _dst, place_at = (q.arg(i) for i in range(4))
        x, y, w, h = struct.unpack("<4i", q.read(rect_at, 16))
        dx, dy = struct.unpack("<2i", q.read(place_at, 8))
        self.blits.append(((x, y, x + w, y + h), dx, dy, 255, self._mask(src)))
        return 0, 0

    def _faded(self, q):
        a = [q.arg(i) for i in range(10)]
        assert bits_f32(a[8]) == 1.0, "text is never scaled"
        self.blits.append((tuple(s32(v) for v in a[3:7]), s32(a[1]), s32(a[2]), pi.surface_alpha(bits_f32(a[7])),
                           self._mask(a[0])))
        return 0, 0x28

    # ---- the game's text routines
    def draw(self, key: str, data: bytes, x: int, y: int, colour: int) -> list[tuple]:
        self.blits = []
        self.call(self.c["draw"], [self.bytes_(data), x & 0xFFFFFFFF, y & 0xFFFFFFFF, colour, self.fonts[key]],
                  ecx=self.renderer)
        return self.blits

    def centred(self, key: str, data: bytes, cx: int, y: int) -> list[tuple]:
        self.blits = []
        self.call(self.c["centred"], [self.bytes_(data), cx, y, 0xFFFFFFFF, self.fonts[key]], ecx=self.graphics)
        return self.blits

    def boxed(self, key: str, data: bytes, x1: int, x2: int, y: int) -> list[tuple]:
        self.blits = []
        self.call(self.c["boxed"], [self.bytes_(data), x1, x2, y, 0xFFFFFFFF, self.fonts[key]], ecx=self.graphics)
        return self.blits

    def width(self, key: str, data: bytes) -> int:
        return s32(self.call(self.c["width"], [self.bytes_(data), f32bits(1.0)], ecx=self.fonts[key]))

    def loaded(self, key: str) -> tuple[list, list, int, int]:
        """(cells as (code, rect), index[256], line height, spacing) as the game's loader left them."""
        impl = self.p.u32(self.fonts[key] + 4)
        table = self.p.u32(impl + 0x18)
        cells = []
        while True:
            row = struct.unpack("<5i", self.p.read(table + 20 * len(cells), 20))
            if row[0] == 0:
                break
            cells.append((row[0], row[1:]))
        index = list(struct.unpack("<256I", self.p.read(impl + 0x1C, 1024)))
        return cells, index, s32(self.p.u32(impl + 4)), s32(self.p.u32(impl + 8))


def expected(font: text.GameFont, data: bytes, x: int, y: int, colour: int) -> list[tuple]:
    """The renderer's plan, as the blits the game records."""
    if (colour >> 24) & 0xFF == 0:
        colour = text.DEFAULT_COLOUR
    rgb = colour & 0xFFFFFF
    mask = 0xFFFFFFFF if rgb == 0xFFFFFF else (0xFF000000 | rgb)
    fade = (colour >> 24) & 0xFF
    alpha = 255 if fade == 255 else pi.surface_alpha(fade / 255.0)
    return [(d.rect, d.x, d.y, alpha, mask) for d in text.game_plan(font, data, x, y)]


class TablesAreTheGames(unittest.TestCase):
    @unittest.skipUnless(all(exe_path(g).is_file() for g in text.TITLES) and HAVE_UNICORN,
                         "the stock executables (and pefile) are needed")
    def test_the_json_is_what_the_executables_hold(self) -> None:
        import build_vv_font_tables as build
        self.assertEqual(build.dump(build.build()), text.TABLES.read_text(encoding="utf-8"),
                         "run python scripts/build_vv_font_tables.py")

    def test_every_game_has_its_two_fonts(self) -> None:
        for game in text.TITLES:
            infos = text.font_infos(game)
            self.assertEqual([i["key"] for i in infos], ["arialbold", "burweed"])
            self.assertEqual([i["name"] for i in infos], ["Arial Bold (game font)", "Burweed (game font)"])
            for info in infos:
                font = text.GameFont(game, info["key"])
                self.assertEqual(font.line_height, 20 if info["key"] == "arialbold" else 27)
                self.assertEqual(font.spacing, 1 if (game in (1, 2) and info["key"] == "arialbold") else 0)

    def test_the_glyph_sets(self) -> None:
        early = set(b" !\"',-./0123456789:?`" + bytes(range(0x41, 0x5B)) + bytes(range(0x61, 0x7B)))
        for game in (1, 2):
            for key in text.FONT_KEYS:
                font = text.GameFont(game, key)
                self.assertEqual({b for b in range(256) if font.has[b]}, early, (game, key))
                self.assertEqual(font.cell(ord("#")).code, ord("A"), "a byte with no cell draws the first")
        for game in (3, 4, 5):
            for key in text.FONT_KEYS:
                font = text.GameFont(game, key)
                have = {b for b in range(256) if font.has[b]}
                self.assertTrue(set(range(0x20, 0x7F)) <= have, (game, key))
                self.assertTrue(set(range(0xC0, 0x100)) <= have, (game, key))
                self.assertFalse(have & set(range(0x80, 0xA1)), (game, key))
                self.assertEqual(font.cell(0x80).code, ord("!"))

    @unittest.skipUnless(all(have_art(g) for g in text.TITLES), "research/game-images is needed")
    def test_the_stock_sheet_sizes(self) -> None:
        for game in text.TITLES:
            for info in text.font_infos(game):
                head = (images(game) / info["sheet"]).read_bytes()[:24]
                self.assertEqual(list(struct.unpack(">II", head[16:24])), info["sheet_size"])


class _Emulated:
    game = 0

    @classmethod
    def setUpClass(cls) -> None:
        if not can_emulate(cls.game):
            raise unittest.SkipTest(f"the stock {text.TITLES[cls.game]} executable (and Unicorn) are needed")
        cls.emu = GameText(cls.game)
        cls.fonts = {key: text.GameFont(cls.game, key) for key in text.FONT_KEYS}

    def test_the_loader(self) -> None:
        for key, font in self.fonts.items():
            cells, index, line_height, spacing = self.emu.loaded(key)
            self.assertEqual([(c.code, c.rect) for c in font.cells], [(code, tuple(r)) for code, r in cells], key)
            self.assertEqual(font.index, index, key)
            self.assertEqual(font.line_height, line_height, key)
            self.assertEqual(font.spacing, spacing, key)

    def test_the_text_draw(self) -> None:
        n = 0
        for key, font in self.fonts.items():
            for data in SAMPLES:
                for x, y in PLACES:
                    for colour in COLOURS:
                        game = self.emu.draw(key, data, x, y, colour)
                        self.assertEqual(expected(font, data, x, y, colour), game,
                                         f"{key} {data[:20]!r} at {x},{y} in {colour:08X}")
                        n += len(game)
        self.assertGreater(n, 10000)

    def test_the_width_and_the_centred_draw(self) -> None:
        for key, font in self.fonts.items():
            for data in SAMPLES:
                self.assertEqual(font.width(data), self.emu.width(key, data), (key, data[:20]))
                game = self.emu.centred(key, data, 400, 50)
                start = text.centred_x(font, data, 400)
                self.assertEqual(expected(font, data, start, 50, 0xFFFFFFFF), game, (key, data[:20]))
                if self.emu.c["boxed"]:
                    game = self.emu.boxed(key, data, 100, 621, 50)
                    start = 100 + int((621 - 100 - font.width(data)) / 2)
                    self.assertEqual(expected(font, data, start, 50, 0xFFFFFFFF), game, (key, data[:20]))

    def test_the_renderer_lays_game_text_out_as_the_game_does(self) -> None:
        """The Unicode renderer's places for text the font has are the game's own draw's."""
        for key, font in self.fonts.items():
            sample = "".join(chr(b) for b in range(0x20, 0x7F) if font.has[b])
            sample = sample[:40] + "\n" + sample[40:]
            data = text.game_bytes(sample)
            renderer = text.TextRenderer(self.game, key, pi.Image(*font.sheet_size))
            lines = renderer.lines(sample)
            places = []
            for n, line in enumerate(lines):
                x = 0
                for piece in line:
                    self.assertEqual(piece.source, text.SOURCE_GAME, piece.cluster)
                    places.append((piece.game_rect, x, n * font.line_height))
                    x += piece.advance + font.spacing
            game = self.emu.draw(key, data, 0, 0, 0xFFFFFFFF)
            self.assertEqual([(r, x, y) for r, x, y, _a, _m in game], places, key)


class AnewHomeDrawsText(_Emulated, unittest.TestCase):
    game = 1


class TheLostChildrenDrawsText(_Emulated, unittest.TestCase):
    game = 2


class TheSecretCityDrawsText(_Emulated, unittest.TestCase):
    game = 3


class TheTreeOfLifeDrawsText(_Emulated, unittest.TestCase):
    game = 4


class NewBelieversDrawsText(_Emulated, unittest.TestCase):
    game = 5


def _sheet(game: int, key: str) -> pi.Image:
    return pi.decode_png((images(game) / text.font_info(game, key)["sheet"]).read_bytes())


class Rendering(unittest.TestCase):
    def test_the_loader_wraps_a_long_strip(self) -> None:
        entries = [[65, 0, 0, 10, 20], [66, 10, 0, 25, 20], [-23, 25, 0, 40, 20]]
        cells, index, lh = text.load_table(entries, 30)
        self.assertEqual(lh, 20)
        self.assertEqual([c.rect for c in cells], [(0, 0, 10, 20), (10, 0, 25, 20), (0, 21, 15, 41)])
        self.assertEqual(index[0xE9], 2)
        self.assertEqual(index[ord("C")], 0)

    def test_the_recolour_ands_the_colour(self) -> None:
        image = pi.Image(2, 1, bytearray((255, 255, 255, 255, 200, 100, 50, 128)))
        out = text._and_tint(image, (0x0F, 0xF0, 0x55))
        self.assertEqual(bytes(out.data), bytes((0x0F, 0xF0, 0x55, 255, 200 & 0x0F, 100 & 0xF0, 50 & 0x55, 128)))

    @unittest.skipUnless(have_art(5) and have_art(1), "research/game-images is needed")
    def test_game_text_is_the_games_pixels(self) -> None:
        for game in (1, 5):
            for key in text.FONT_KEYS:
                sheet = _sheet(game, key)
                font = text.GameFont(game, key, (sheet.width, sheet.height))
                sample = "Hello, World!\nThe quick brown fox" if game == 1 else "Café À la crème\n© 2009"
                for colour in (text.DEFAULT_COLOUR, 0xFF002245, 0x80FFFFFF):
                    made = text.TextRenderer(game, key, sheet).render(sample, colour)
                    self.assertEqual(made.counts, {text.SOURCE_GAME: len(sample.replace("\n", ""))})
                    self.assertEqual(made.boxes, [])
                    stock = text.game_render(font, sheet, text.game_bytes(sample), colour)
                    self.assertEqual(made.image.cropped(0), stock.cropped(0), (game, key, hex(colour)))

    @unittest.skipUnless(have_art(1) and have_art(5), "research/game-images is needed")
    def test_missing_characters_are_made_and_marked(self) -> None:
        import vv_glyph_maker
        if not vv_glyph_maker.available():
            self.skipTest("the glyph maker needs Windows")
        r1 = text.TextRenderer(1, "arialbold", _sheet(1, "arialbold"))
        made = r1.render("Café #1")
        self.assertEqual(made.counts.get(text.SOURCE_GAME), 5)
        self.assertEqual(made.counts.get(text.SOURCE_MADE), 2)
        self.assertEqual({b[5] for b in made.boxes}, {"é", "#"})
        e = r1.piece("é")
        self.assertIn("accents generated", e.detail)
        r5 = text.TextRenderer(5, "burweed", _sheet(5, "burweed"))
        self.assertEqual(r5.piece("é").source, text.SOURCE_GAME, "New Believers has é")
        self.assertEqual(r5.piece("é").source, text.SOURCE_GAME, "decomposed text is the same letter")
        self.assertEqual(r5.piece("ǩ").source, text.SOURCE_MADE)
        self.assertEqual(r5.piece("中").source, text.SOURCE_MADE)
        for emoji in ("\U0001F44D\U0001F3FD", "\U0001F468‍\U0001F469‍\U0001F467"):
            piece = r5.piece(emoji)
            self.assertEqual(piece.source, text.SOURCE_EMOJI)
            self.assertEqual(len(r5.lines(emoji)[0]), 1, "an emoji sequence stays one glyph")
        made = r5.render("\U0001F44D", 0xFF000000)
        colours = {bytes(made.image.data[i:i + 3]) for i in range(0, len(made.image.data), 4)
                   if made.image.data[i + 3] == 255}
        self.assertGreater(len(colours), 3, "emoji keep their colours under a text colour")
        styled = r5.piece("Ł")
        alphas = {styled.image.data[i] for i in range(3, len(styled.image.data), 4)} - {0}
        self.assertTrue(alphas <= set(r5.style.alpha_levels), "generated glyphs use the sheet's alpha levels")

    @unittest.skipUnless(have_art(3), "research/game-images is needed")
    def test_alignment(self) -> None:
        r = text.TextRenderer(3, "arialbold", _sheet(3, "arialbold"))
        sample = "Wide line here\nab"
        left = r.render(sample, align=text.ALIGN_LEFT)
        right = r.render(sample, align=text.ALIGN_RIGHT)
        centre = r.render(sample, align=text.ALIGN_CENTRE)
        self.assertEqual(left.image, centre.image, "the game centres the block: every line starts together")
        self.assertEqual((left.image.width, left.image.height), (right.image.width, right.image.height))
        self.assertNotEqual(left.image, right.image)

    @unittest.skipUnless(have_art(4), "research/game-images is needed")
    def test_the_outlined_title(self) -> None:
        r = text.TextRenderer(4, "burweed", _sheet(4, "burweed"))
        plain = r.render("Tree", 0xFFF5E762)
        outlined = r.render("Tree", 0xFFF5E762, effect=text.EFFECT_OUTLINED)
        self.assertEqual((outlined.image.width, outlined.image.height), (plain.image.width + 3, plain.image.height + 3))


class Helpers(unittest.TestCase):
    def test_the_name_counter_counts_utf8(self) -> None:
        self.assertEqual(text.name_fit(1, "Hiji"), (4, 27, True))
        self.assertEqual(text.name_fit(2, "Élodie"), (7, 23, True))
        self.assertEqual(text.name_fit(5, "\U0001F600" * 7), (28, 24, False))
        self.assertFalse(text.name_fit(3, "a\nb")[2])

    def test_character_search(self) -> None:
        self.assertIn("é", text.search_characters("e acute"))
        self.assertEqual(text.search_characters("U+1F600")[0], "\U0001F600")
        self.assertEqual(text.search_characters("e9")[0], "é")
        self.assertIn("か", text.search_characters("hiragana letter ka"))
        self.assertEqual(text.search_characters("   "), [])

    def test_the_palette(self) -> None:
        for game in text.TITLES:
            colours = text.game_colours(game)
            self.assertEqual(colours[0].value, text.DEFAULT_COLOUR)
            self.assertIn((0, 0, 0), [c.rgb for c in colours])
        self.assertEqual(text.GAME_COLOURS[3].rgb, (0x45, 0x22, 0x00))
        self.assertEqual(text.colour_value((1, 2, 3), 4), 0x04030201)

    def test_the_patchers_own_glyphs_come_before_generated_ones(self) -> None:
        """(b): vv_font_glyphs' letter (the one the patched game draws) is used, and marked patcher-made;
        the game's own letter still comes first."""
        import types

        class Glyph:
            def __init__(self, source: str) -> None:
                self.source = source

            def image(self, colour):
                return pi.Image(7, 20, bytes(colour) + b"\xff" + bytes(7 * 20 * 4 - 4))

        calls = []

        def glyph(game, font, char, images_dir):
            calls.append((game, font, char, Path(images_dir).name))
            return Glyph("game" if char == "A" else "composed:Arial")

        fake = types.ModuleType("vv_font_glyphs")
        fake.glyph = glyph
        sys.modules["vv_font_glyphs"] = fake
        try:
            sheet = pi.Image(728, 40)
            r = text.TextRenderer(1, "arialbold", sheet, images_dir=Path("Fonts"))
            self.assertEqual(r.piece("A").source, text.SOURCE_GAME)
            piece = r.piece("é")
            self.assertEqual((piece.source, piece.advance, piece.image.height), (text.SOURCE_PATCHER, 7, 20))
            self.assertEqual(calls, [("vv1", "ldwarialbold", "é", "Fonts")])
            self.assertIsNone(text.patcher_glyph(1, "arialbold", "A", Path("Fonts")), "the game's own is not the patcher's")
            self.assertIsNone(text.patcher_glyph(1, "arialbold", "é", None), "no sheets folder, no patcher glyph")
        finally:
            del sys.modules["vv_font_glyphs"]

    def test_right_to_left_runs_are_one_piece(self) -> None:
        parts = ["a", " ", "م", "ر", " ", "ح", "!", " ", "ש"]
        self.assertEqual(text._rtl_runs(parts), ["a", " ", "مر ح", "!", " ", "ש"])

    def test_clusters_without_the_maker(self) -> None:
        import vv_pictures_text as t
        saved = t._maker
        t._maker = lambda: None
        try:
            self.assertEqual(t.clusters("éa\r\nb"), ["é", "a", "\n", "b"])
        finally:
            t._maker = saved


@unittest.skipUnless(have_art(5), "research/game-images is needed")
class TextTabWindow(unittest.TestCase):
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
        import shutil
        import tempfile
        import vv_picture_studio as ps
        import vv_pictures_common as common
        from test_picture_studio import FakeModule
        self.ps, self.common, self.shutil = ps, common, shutil
        self.tmp = Path(tempfile.mkdtemp(prefix="vvtext"))
        self.saved = (ps.load_renderer_module, common.save_folders, common.slots, pi.CACHE_ROOT)
        ps.load_renderer_module = lambda game: FakeModule
        common.save_folders = lambda game, documents=None: []
        common.slots = lambda folder, game: []
        pi.CACHE_ROOT = self.tmp / "cache"
        self.window = ps.open_window(self.root, 5, game_folders=[images(5).parent])
        self.window.quiet = True
        self.root.update()
        self.tab = self.window.text_tab

    def tearDown(self) -> None:
        self.window.close()
        self.ps.load_renderer_module, self.common.save_folders, self.common.slots, pi.CACHE_ROOT = self.saved
        self.shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_tab_draws_and_saves(self) -> None:
        tab = self.tab
        self.assertEqual([k for k, _n in tab.fonts][:2], ["arialbold", "burweed"])
        self.assertTrue((pi.CACHE_ROOT / text.CACHE_SUBFOLDER / "New Believers" / "ldwBurweed27.png").is_file(),
                        "the sheets are copied into the Studio's own folder")
        tab.set_text("Hello\nWorld")
        tab.refresh()
        self.assertEqual(tab.rendered.counts, {text.SOURCE_GAME: 10})
        self.assertIs(self.window.shown["text"], tab.rendered.image)
        self.window.size_var.set("2x")
        path = tab.save(str(self.tmp / "hello.png"))
        saved = pi.decode_png(path.read_bytes())
        self.assertEqual(saved, pi.export(tab.rendered.image, scale=2))
        tab.insert("Ǫ")
        tab.refresh()
        self.assertIn("1 generated", tab.info.cget("text"))
        self.assertIn("As a villager name: 13 bytes", tab.name_label.cget("text"))
        self.assertIn("a name is one line", tab.name_label.cget("text"))
        tab.stock_var.set(True)
        tab.refresh()
        self.assertEqual(tab.rendered.boxes, [])
        picker = tab.open_picker()
        picker.query.set("latin small letter eth")
        picker.search()
        picker.insert_selected()
        self.assertTrue(tab.get_text().endswith("Ǫð"))
        picker.window.destroy()


if __name__ == "__main__":
    unittest.main()
