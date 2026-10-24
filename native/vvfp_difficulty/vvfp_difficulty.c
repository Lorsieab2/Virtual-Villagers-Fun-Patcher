/* VVFP Difficulty -- "Difficulty Settings" (The Tree of Life, New Believers;
   rows built by scripts/build_difficulty_features.py, previews in
   docs/vv4-difficulty-options-preview.png and
   docs/vv5-difficulty-options-preview.png).  Puts back the Options dialog's Difficulty
   row -- Easy / Normal / Hard, as A New Home, The Lost Children and The
   Secret City have it -- so the player can choose the level the game
   already plays by.

   THE STOCK GAMES.  The Tree of Life and New Believers keep the difficulty
   exactly as The Secret City does: one game-state field (VV4 +0x170F4, VV5
   +0x17D54; 0 Easy, 1 Normal, 2 Hard), set to 1 by the state's constructor
   (VV4 0x41F483, VV5 0x4249D3), saved with the village (inside the state
   block the save writes, VV4 0x1710C bytes and VV5 0x17D78 bytes from
   +8), and read by the same rules as The Secret City's: a new village's
   starting food (VV4 0x41F3A3, VV5 0x4248EB: Easy +300, Hard -99), the
   per-villager food use, starvation and healing (VV4 0x4684E5..0x4686B0,
   VV5 0x472DBB..) and the sickness roll (VV4 0x45E938, VV5 0x465F58).
   The Options dialog's click handler (VV4 0x41AD60, VV5 0x41B5C0) still
   writes the field from three click areas (VV4 0x41B159 / 0x41B187 /
   0x41B1B9, VV5 0x41B9B9 / 0x41B9E7 / 0x41BA19), but the dialog's drawing
   (VV4 0x41A5A0, VV5 0x41ADF0) no longer draws the row -- its strings
   (VV4 0x534-0x537, VV5 0x57E-0x581) are never shown -- and those click
   areas lie under the Game Speed buttons, which take the click first; only
   a thin strip above them is left, so the choice is invisible.

   WHAT THIS COMPANION DOES, at run time over verified stock bytes only:

   1. ROOM FOR IT.  The dialog's frame is drawn in whole 64-pixel tiles
      (0x40DA30 / VV5 0x40DF20: rows = ceil(height / 64)), and the dialog
      widget -- the frame's size, centred on the screen -- is what the Done
      button and the Music Tracks checkboxes are placed from, while the rows
      are drawn from +0x80 = widget top + (frame height - height) / 2.  So the
      height grows by whole tiles and keeps that 2-pixel offset: VV4 0x1FC ->
      0x23C (frame 512 -> 576, one tile, the most the 800 x 600 screen
      holds), VV5 0x1FC -> 0x27C (512 -> 640, two tiles, on 1024 x 768), at
      both places the constructor uses it.  Everything -- frame, title,
      sliders, checkboxes, every row, Done and every click area -- then
      stays where it was relative to the frame, and Done keeps its stock
      distance from the frame's bottom.

   2. A ROW FOR IT.  The Difficulty row goes directly above Game Speed, as
      in The Secret City.  VV5: at Game Speed's old place (y+0x161, its own
      0x64 row spacing), Game Speed moving down 0x64; the frame's second
      tile leaves 28 more pixels above Done.  VV4: one tile is 64 pixels,
      less than its 0x50 row spacing, so Difficulty sits 0x48 below
      Fullscreen (y+0x145) and Game Speed 0x48 below it (y+0x18D, +0x40),
      which keeps Game Speed's stock distance to Done.  Game Speed moves by
      rewriting the immediates of its ten radio-button draws, its heading,
      its four labels and its four click areas.

   3. DRAWING IT.  At the join point after the Game Speed radio buttons and
      before their heading (VV4 0x41A906, VV5 0x41B156), the row is drawn
      with the dialog's own art and text routines, exactly as the Game
      Speed row draws itself: the heading "Difficulty" (VV4 0x534, VV5
      0x57E) at (x+0x32, row heading y), three radio buttons -- the
      dialog's own radioblank / radioselected images -- at x+0xC8,
      x+0x13C, x+0x1B0 with the selected one for the field's value, and
      under them "Easy", "Normal" (the Game Speed row's own "Normal", as
      the earlier games use it) and "Hard" at Game Speed's first three label
      positions.

   4. CLICKING IT.  The stock handler's own three difficulty areas, which
      write the field, move onto the new row's buttons: the same insets as
      the Game Speed buttons (y+0x0A..y+0x2F from the button's top), so
      clicking near Game Speed never changes the difficulty unseen.  No
      sound plays, as in the stock handler (and The Secret City's).

   Nothing else is written: no save byte, no file, no villager.  Only The
   Tree of Life (game 4) and New Believers (game 5) install, and only when
   every site is stock; otherwise nothing is written at all
   (native/shared/install_sites.h: every site, or none). */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include "../shared/install_sites.h"

#define VV4_GAME 4
#define VV5_GAME 5

/* One verified rewrite: `length` stock bytes at `va` become `after`. */
struct site {
    unsigned int va;
    int length;
    unsigned char stock[6];
    unsigned char after[6];
};

/* The dialog object (theOptionsDialog), the same layout in both games. */
#define DLG_STATE 0x74     /* the game state */
#define DLG_X 0x78         /* the dialog's left edge */
#define DLG_Y 0x80         /* the dialog's top edge */
#define DLG_BLANK 0x8C     /* radioblank.png */
#define DLG_SELECTED 0x90  /* radioselected.png */
#define DLG_GRAPHICS 0x9C  /* the graphics context */
#define DLG_STRINGS 0xA8   /* the string table */

struct game {
    int number;
    unsigned int difficulty;      /* the game-state field */
    unsigned int text_font;       /* the dialog's text-colour global the stock rows pass */
    unsigned int get_string;      /* thiscall(strings; id) -> const char* */
    unsigned int draw_left;       /* thiscall(graphics; text, x, y, colour, 0): headings */
    unsigned int draw_centred;    /* thiscall(graphics; text, x, y, colour, 0): labels */
    unsigned int draw_image;      /* thiscall(graphics; image, x, y) */
    int heading_string;           /* "Difficulty" */
    int label_strings[3];         /* "Easy", "Normal", "Hard" */
    int row_y;                    /* the radio buttons' top, from the dialog's top */
    int heading_y;
    int label_y;
    int label_x[3];               /* absolute, as the stock Game Speed labels are */
    unsigned int hook;            /* the draw join point */
    unsigned int hook_return;     /* the instruction after the stolen one */
    unsigned char hook_stock[6];  /* mov ecx, [text_font] */
    const struct site *sites;
    int site_count;
};

/* ---- The Tree of Life ------------------------------------------------- */
static const struct site VV4_SITES[] = {
    /* the dialog's height, 0x1FC -> 0x23C: the frame's size, the centring */
    { 0x41A07D, 5, { 0x68, 0xFC, 0x01, 0x00, 0x00 }, { 0x68, 0x3C, 0x02, 0x00, 0x00 } },
    { 0x41A109, 5, { 0x2D, 0xFC, 0x01, 0x00, 0x00 }, { 0x2D, 0x3C, 0x02, 0x00, 0x00 } },
    /* Game Speed's ten radio-button draws, y+0x14D -> y+0x18D */
    { 0x41A747, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A770, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A799, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A7D2, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A80B, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A834, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A871, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A89A, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A8C3, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    { 0x41A8EC, 6, { 0x81, 0xC1, 0x4D, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0x8D, 0x01, 0x00, 0x00 } },
    /* Game Speed's heading y+0x152 -> y+0x192, its four labels y+0x17F -> y+0x1BF */
    { 0x41A91E, 6, { 0x81, 0xC2, 0x52, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0x92, 0x01, 0x00, 0x00 } },
    { 0x41A954, 6, { 0x81, 0xC2, 0x7F, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0xBF, 0x01, 0x00, 0x00 } },
    { 0x41A984, 6, { 0x81, 0xC1, 0x7F, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xBF, 0x01, 0x00, 0x00 } },
    { 0x41A9C1, 5, { 0x05, 0x7F, 0x01, 0x00, 0x00 }, { 0x05, 0xBF, 0x01, 0x00, 0x00 } },
    { 0x41A9F7, 6, { 0x81, 0xC2, 0x7F, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0xBF, 0x01, 0x00, 0x00 } },
    /* the click areas, each button's top + 0x0A .. + 0x2F as the stock
       buttons': Difficulty's tops y+0x150 -> y+0x14F and bottoms
       y+0x175 -> y+0x174 (its buttons at y+0x145); Game Speed's tops
       y+0x157 -> y+0x197 and bottoms y+0x17C -> y+0x1BC */
    { 0x41AD83, 6, { 0x8D, 0x90, 0x50, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0x4F, 0x01, 0x00, 0x00 } },
    { 0x41ADCB, 6, { 0x8D, 0x90, 0x75, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0x74, 0x01, 0x00, 0x00 } },
    { 0x41ADE0, 6, { 0x8D, 0xB8, 0x75, 0x01, 0x00, 0x00 }, { 0x8D, 0xB8, 0x74, 0x01, 0x00, 0x00 } },
    { 0x41ADF1, 6, { 0x8D, 0x90, 0x57, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0x97, 0x01, 0x00, 0x00 } },
    { 0x41AE2C, 6, { 0x8D, 0xB8, 0x7C, 0x01, 0x00, 0x00 }, { 0x8D, 0xB8, 0xBC, 0x01, 0x00, 0x00 } },
};

/* ---- New Believers ---------------------------------------------------- */
static const struct site VV5_SITES[] = {
    /* the dialog's height, 0x1FC -> 0x27C */
    { 0x41A8D1, 5, { 0x68, 0xFC, 0x01, 0x00, 0x00 }, { 0x68, 0x7C, 0x02, 0x00, 0x00 } },
    { 0x41A95B, 5, { 0x2D, 0xFC, 0x01, 0x00, 0x00 }, { 0x2D, 0x7C, 0x02, 0x00, 0x00 } },
    /* Game Speed's ten radio-button draws, y+0x161 -> y+0x1C5 */
    { 0x41AF97, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41AFC0, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41AFE9, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B022, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B05B, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B084, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B0C1, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B0EA, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B113, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    { 0x41B13C, 6, { 0x81, 0xC1, 0x61, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xC5, 0x01, 0x00, 0x00 } },
    /* Game Speed's heading y+0x172 -> y+0x1D6, its four labels y+0x194 -> y+0x1F8 */
    { 0x41B16E, 6, { 0x81, 0xC2, 0x72, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0xD6, 0x01, 0x00, 0x00 } },
    { 0x41B1A4, 6, { 0x81, 0xC2, 0x94, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0xF8, 0x01, 0x00, 0x00 } },
    { 0x41B1D4, 6, { 0x81, 0xC1, 0x94, 0x01, 0x00, 0x00 }, { 0x81, 0xC1, 0xF8, 0x01, 0x00, 0x00 } },
    { 0x41B211, 5, { 0x05, 0x94, 0x01, 0x00, 0x00 }, { 0x05, 0xF8, 0x01, 0x00, 0x00 } },
    { 0x41B247, 6, { 0x81, 0xC2, 0x94, 0x01, 0x00, 0x00 }, { 0x81, 0xC2, 0xF8, 0x01, 0x00, 0x00 } },
    /* the click areas: Difficulty's tops y+0x150 -> y+0x16B and bottoms
       y+0x175 -> y+0x190 (the Game Speed buttons' old ones); Game Speed's
       tops y+0x16B -> y+0x1CF and bottoms y+0x190 -> y+0x1F4 */
    { 0x41B5E3, 6, { 0x8D, 0x90, 0x50, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0x6B, 0x01, 0x00, 0x00 } },
    { 0x41B62B, 6, { 0x8D, 0x90, 0x75, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0x90, 0x01, 0x00, 0x00 } },
    { 0x41B640, 6, { 0x8D, 0xB8, 0x75, 0x01, 0x00, 0x00 }, { 0x8D, 0xB8, 0x90, 0x01, 0x00, 0x00 } },
    { 0x41B651, 6, { 0x8D, 0x90, 0x6B, 0x01, 0x00, 0x00 }, { 0x8D, 0x90, 0xCF, 0x01, 0x00, 0x00 } },
    { 0x41B68C, 6, { 0x8D, 0xB8, 0x90, 0x01, 0x00, 0x00 }, { 0x8D, 0xB8, 0xF4, 0x01, 0x00, 0x00 } },
};

static const struct game VV4 = {
    VV4_GAME, 0x170F4u, 0x4CCB08u, 0x44D3D0u, 0x409BD0u, 0x409BE0u, 0x409960u,
    0x534, { 0x535, 0x53A, 0x537 },
    0x145, 0x14A, 0x177, { 0x135, 0x1AB, 0x21F },
    0x41A906u, 0x41A90Cu, { 0x8B, 0x0D, 0x08, 0xCB, 0x4C, 0x00 },
    VV4_SITES, (int)(sizeof VV4_SITES / sizeof VV4_SITES[0]),
};

static const struct game VV5 = {
    VV5_GAME, 0x17D54u, 0x4DC948u, 0x4506D0u, 0x409EA0u, 0x409EB0u, 0x409B90u,
    0x57E, { 0x57F, 0x584, 0x581 },
    0x161, 0x172, 0x194, { 0x1A5, 0x21B, 0x28E },
    0x41B156u, 0x41B15Cu, { 0x8B, 0x0D, 0x48, 0xC9, 0x4D, 0x00 },
    VV5_SITES, (int)(sizeof VV5_SITES / sizeof VV5_SITES[0]),
};

/* The radio buttons' columns, from the dialog's left edge (the Game Speed
   row's first three). */
static const int ROW_X[3] = { 0xC8, 0x13C, 0x1B0 };

typedef const char *(__fastcall *get_string_fn)(void *strings, void *unused, int id);
typedef void (__fastcall *draw_text_fn)(void *graphics, void *unused, const char *text,
                                        int x, int y, unsigned int colour, int zero);
typedef void (__fastcall *draw_image_fn)(void *graphics, void *unused, void *image, int x, int y);

static const struct game *active;
static unsigned int hook_return;   /* where the stock drawing goes on */
static unsigned int hook_colour;   /* the global the stolen instruction reads */

#define FIELD(object, offset, type) (*(type *)((unsigned char *)(object) + (offset)))

/* Draw the Difficulty row on the dialog, as the Game Speed row draws
   itself.  A value outside 0..2 (never written by the game) selects no
   button, as the Game Speed row does for an unknown speed. */
static void __cdecl draw_difficulty(unsigned char *dialog) {
    const struct game *g = active;
    void *graphics = FIELD(dialog, DLG_GRAPHICS, void *);
    void *strings = FIELD(dialog, DLG_STRINGS, void *);
    unsigned char *state = FIELD(dialog, DLG_STATE, unsigned char *);
    int x = FIELD(dialog, DLG_X, int);
    int y = FIELD(dialog, DLG_Y, int);
    int level = *(int *)(state + g->difficulty);
    get_string_fn get_string = (get_string_fn)(uintptr_t)g->get_string;
    draw_text_fn draw_left = (draw_text_fn)(uintptr_t)g->draw_left;
    draw_text_fn draw_centred = (draw_text_fn)(uintptr_t)g->draw_centred;
    draw_image_fn draw_image = (draw_image_fn)(uintptr_t)g->draw_image;
    int i;
    for (i = 0; i < 3; ++i) {
        void *image = FIELD(dialog, level == i ? DLG_SELECTED : DLG_BLANK, void *);
        draw_image(graphics, 0, image, x + ROW_X[i], y + g->row_y);
    }
    draw_left(graphics, 0, get_string(strings, 0, g->heading_string),
              x + 0x32, y + g->heading_y, *(unsigned int *)(uintptr_t)g->text_font, 0);
    for (i = 0; i < 3; ++i) {
        draw_centred(graphics, 0, get_string(strings, 0, g->label_strings[i]),
                     g->label_x[i], y + g->label_y, *(unsigned int *)(uintptr_t)g->text_font, 0);
    }
}

/* Entered by the jump at the draw join point with esi = the dialog; every
   register and flag is handed back, then the stolen `mov ecx, [colour]`
   runs and the stock drawing goes on. */
static __declspec(naked) void draw_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call draw_difficulty
        add esp, 4
        popad
        popfd
        mov ecx, hook_colour
        mov ecx, dword ptr [ecx]
        jmp dword ptr [hook_return]
    }
}

/* Every site and the draw hook, all or none (native/shared/install_sites.h):
   each verified stock, all made writable, then all written; if any of it
   fails nothing is written and the game keeps its stock dialog. */
static vvfp_site_write writes[32];

static void install(const struct game *g) {
    int i;
    if (active != NULL || g->site_count + 1 > (int)(sizeof writes / sizeof writes[0])) {
        return;
    }
    for (i = 0; i < g->site_count; ++i) {
        vvfp_site_bytes(&writes[i], g->sites[i].va, g->sites[i].length, g->sites[i].stock,
                        g->sites[i].after);
    }
    vvfp_site_branch(&writes[g->site_count], g->hook, 6, g->hook_stock, 0xE9, (const void *)draw_stub);
    hook_return = g->hook_return;
    hook_colour = g->text_font;
    active = g;                          /* the stub reads these once the hook is in */
    if (!vvfp_install_sites(writes, g->site_count + 1)) {
        active = NULL;
    }
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game == VV4_GAME) {
        install(&VV4);
    } else if (game == VV5_GAME) {
        install(&VV5);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
