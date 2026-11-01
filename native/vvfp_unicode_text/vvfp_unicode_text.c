/* VVFP Unicode Text -- "Render Unicode with In-Game Fonts", all five games.

   WHAT.  Every Virtual Villagers game draws all of its text with two LDW bitmap fonts, ldwBurweed27 and
   ldwarialbold (src/vv_font_glyphs.py describes them).  A New Home's and The Lost Children's hold only
   A-Z, a-z, 0-9 and a few signs; the later three add Latin-1 but not the rest of Windows-1252 (the euro,
   curly quotes and dashes, S and Z with caron, OE, ...).  A character a font lacks is drawn -- and
   measured -- as the font's first letter.  And the game drops every typed character outside ASCII: its
   SDL_TEXTINPUT case posts a key only when SDL's UTF-8 text is ONE byte long.

   This companion gives every font every printable Windows-1252 character, and lets the player type them.

   DRAWING AND MEASURING.  The font constructor (ctor below) is detoured: the game's own constructor runs
   first, unchanged, then for the two known fonts (recognised by their stock glyph tables) the missing
   letters are made exactly as src/vv_font_glyphs.py makes them (glyphs.inc) from the font picture the
   game just loaded and the player's own Windows typefaces.  They are written as new rows UNDER the
   loaded picture -- a new SDL surface, the old one freed -- and appended to a copy of the font's glyph
   table, and the font's 256-entry index points each code at its letter.  Every routine that draws or
   measures text (draw 0x409160 / width 0x402160 in A New Home, and every word wrap and centring built
   on them) reads letters only through the font's glyph lookup (vtable +4: index, table, picture), so
   they all see the new letters with their real widths, in every colour (the tinted copies are made from
   the picture later, on demand).  The game's picture files are never changed.

   TYPING.  The SDL_TEXTINPUT case is detoured at its first instruction: a text that is ONE character
   which Windows-1252 has is posted as that byte (0x80-0xFF zero-extended, which the game's text boxes
   already accept: 0x40BEB7 takes 0x20..0xFF), anything else is skipped exactly as before.  ASCII is
   posted exactly as the stock code posts it.  So the tribe name, the villager names on the Details
   screen and every other text box take accented letters, the euro and the rest; each is one byte, so
   no box holds more bytes than before and nothing is cut inside a character.

   SAFETY.  All of a game's sites or none (native/shared/install_sites.h), each checked against its
   stock bytes first; the trampoline page is built read/write and sealed read/execute.  A font that is
   not one of the two known, not 32-bit, or whose letters cannot be made, is left exactly as the game
   built it; a fault while extending is abandoned (structured exception handling) and the font stays
   stock.  Nothing is written into any save, record or file. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "unicode_text_tables.h"
#include "glyphs.inc"

#define VT_FONT_PICTURE 0x0C        /* ldwImage*: +0 SDL_Surface* */
#define VT_FONT_TABLE   0x18        /* glyph entries {code, x1, y1, x2, y2}, code 0 ends */
#define VT_FONT_INDEX   0x1C        /* int[256]: entry of each code */
#define VT_MAX_ENTRIES  1024

typedef void *(__cdecl *sdl_create_fn)(unsigned int flags, int w, int h, int depth, unsigned int r,
                                       unsigned int g, unsigned int b, unsigned int a);
typedef void (__cdecl *sdl_free_fn)(void *surface);
typedef int (__cdecl *sdl_lock_fn)(void *surface);
typedef void (__cdecl *sdl_unlock_fn)(void *surface);

/* SDL2's SDL_Surface and SDL_PixelFormat, 32-bit. */
typedef struct sdl_format {
    unsigned int format; void *palette; unsigned char bits, bytes, pad[2];
    unsigned int rmask, gmask, bmask, amask;
    unsigned char rloss, gloss, bloss, aloss, rshift, gshift, bshift, ashift;
} sdl_format;
typedef struct sdl_surface {
    unsigned int flags; sdl_format *format; int w, h, pitch; void *pixels;
} sdl_surface;
#define SDL_RLEACCEL 0x00000002u

static const vg_game *g_game;
static unsigned char *g_tramp;            /* the constructor's first instructions, then a jump back */
static void *g_tramp_entry;
static unsigned int g_text_offset, g_text_skip, g_text_post;
static vg_gdi g_gdi;
static int g_gdi_state;                   /* 0 not opened, 1 open, -1 failed */
static int g_installed;
static volatile LONG g_fonts_extended;    /* how many fonts were given letters (for tests) */

/* ---- Typing ---------------------------------------------------------------------------------- */

/* The byte to post for SDL's UTF-8 text, or -1 to skip it as the stock code would.  One character
   only (the stock rule); ASCII is returned as itself. */
int __cdecl VvfpUnicodeTextKey(const unsigned char *s) {
    unsigned int cp;
    int n, i;
    if (s == NULL || s[0] == 0) {
        return -1;
    }
    if (s[0] < 0x80) {
        return s[1] == 0 ? (int)s[0] : -1;
    }
    if ((s[0] & 0xE0) == 0xC0) {
        cp = s[0] & 0x1Fu; n = 1;
    } else if ((s[0] & 0xF0) == 0xE0) {
        cp = s[0] & 0x0Fu; n = 2;
    } else if ((s[0] & 0xF8) == 0xF0) {
        cp = s[0] & 0x07u; n = 3;
    } else {
        return -1;
    }
    for (i = 1; i <= n; ++i) {
        if ((s[i] & 0xC0) != 0x80) {
            return -1;
        }
        cp = (cp << 6) | (s[i] & 0x3Fu);
    }
    if (s[n + 1] != 0) {
        return -1;
    }
    if ((n == 1 && cp < 0x80) || (n == 2 && cp < 0x800) || (n == 3 && cp < 0x10000) || cp > 0xFFFF) {
        return -1;                          /* overlong, or beyond Windows-1252 anyway */
    }
    for (i = 0x80; i < 0x100; ++i) {
        if (VG_CP1252[i] == cp) {
            return i;
        }
    }
    return -1;
}

__declspec(naked) static void text_hook(void) {
    __asm {
        mov     eax, esp
        add     eax, g_text_offset
        push    eax
        call    VvfpUnicodeTextKey
        add     esp, 4
        cmp     eax, -1
        je      skip
        push    eax                         /* the character, as the stock `push ecx` / `push eax` */
        push    ebx                         /* 0, as the stock code pushes */
        push    5                           /* the char message */
        jmp     dword ptr [g_text_post]
    skip:
        jmp     dword ptr [g_text_skip]
    }
}

/* ---- Drawing and measuring ------------------------------------------------------------------- */

static void extend_font(unsigned char *font, int burweed, int spacing) {
    void **picture = *(void ***)(font + VT_FONT_PICTURE);
    sdl_surface *old, *grown;
    sdl_format *fmt;
    int (*ent)[5];
    int (*table)[5];
    int *index = (int *)(font + VT_FONT_INDEX);
    unsigned char *alpha = NULL;
    vg_sheet sheet;
    vg_font f;
    int n, code, x, y, added, rows, cursor, row, w, h, locked = 0;
    int place_x[256], place_y[256];
    sdl_create_fn create = *(sdl_create_fn *)(UINT_PTR)g_game->sdl_create;
    sdl_free_fn release = *(sdl_free_fn *)(UINT_PTR)g_game->sdl_free;
    sdl_lock_fn lock = *(sdl_lock_fn *)(UINT_PTR)g_game->sdl_lock;
    sdl_unlock_fn unlock = *(sdl_unlock_fn *)(UINT_PTR)g_game->sdl_unlock;

    if (picture == NULL || (old = (sdl_surface *)picture[0]) == NULL || (fmt = old->format) == NULL
        || fmt->bytes != 4 || fmt->amask == 0 || fmt->aloss != 0 || old->w <= 0 || old->h <= 0) {
        return;
    }
    ent = *(int (**)[5])(font + VT_FONT_TABLE);
    for (n = 0; n < VT_MAX_ENTRIES && ent[n][0] != 0; ++n) {
    }
    if (n == 0 || n >= VT_MAX_ENTRIES) {
        return;
    }
    w = old->w;
    h = old->h;
    alpha = (unsigned char *)vg_alloc((size_t)w * (size_t)h);
    if (alpha == NULL) {
        return;
    }
    if (old->flags & SDL_RLEACCEL) {
        if (lock(old) != 0) {
            vg_free(alpha);
            return;
        }
        locked = 1;
    }
    for (y = 0; y < h; ++y) {
        const unsigned int *p = (const unsigned int *)((const unsigned char *)old->pixels + y * old->pitch);
        for (x = 0; x < w; ++x) {
            alpha[y * w + x] = (unsigned char)((p[x] & fmt->amask) >> fmt->ashift);
        }
    }
    if (locked) {
        unlock(old);
    }
    sheet.alpha = alpha;
    sheet.sw = w;
    sheet.sh = h;
    sheet.ent = (const int (*)[5])ent;
    sheet.n = n;
    if (g_gdi_state == 0) {
        g_gdi_state = vg_gdi_open(&g_gdi) ? 1 : -1;
    }
    if (!vg_font_open(&f, g_gdi_state == 1 ? &g_gdi : NULL, &sheet, spacing, burweed)) {
        vg_font_close(&f);
        vg_free(alpha);
        return;
    }
    /* Make every missing printable character; lay the new ones out in rows under the picture. */
    added = 0;
    rows = 0;
    cursor = 0;
    row = h + 1;
    for (code = 0x20; code < 0x100; ++code) {
        place_x[code] = -1;
        if (VG_CP1252[code] == 0 || vg_entry(&sheet, code) >= 0) {
            continue;
        }
        if (vg_glyph(&f, code) == NULL || f.source[code] == VG_ALIAS) {
            continue;
        }
        if (f.glyph[code].w > w) {
            continue;
        }
        if (rows == 0 || cursor + f.glyph[code].w > w) {
            if (rows > 0) {
                row += f.m.line + 1;
            }
            ++rows;
            cursor = 0;
        }
        place_x[code] = cursor;
        place_y[code] = row;
        cursor += f.glyph[code].w + 1;
        ++added;
    }
    if (added == 0) {
        grown = NULL;
    } else {
        grown = (sdl_surface *)create(0, w, row + f.m.line + 1, fmt->bits, fmt->rmask, fmt->gmask,
                                      fmt->bmask, fmt->amask);
    }
    table = (int (*)[5])vg_alloc(sizeof(int[5]) * (size_t)(n + added + 1));
    if ((added > 0 && grown == NULL) || table == NULL || (grown != NULL && grown->pixels == NULL)) {
        if (grown != NULL) {
            release(grown);
        }
        vg_free(table);
        vg_font_close(&f);
        vg_free(alpha);
        return;
    }
    CopyMemory(table, ent, sizeof(int[5]) * (size_t)n);
    if (grown != NULL) {
        unsigned int white = fmt->rmask | fmt->gmask | fmt->bmask;
        for (y = 0; y < h; ++y) {
            CopyMemory((unsigned char *)grown->pixels + y * grown->pitch,
                       (const unsigned char *)old->pixels + y * old->pitch, (size_t)w * 4);
        }
        added = 0;
        for (code = 0x20; code < 0x100; ++code) {
            const vg_mask *g = &f.glyph[code];
            if (place_x[code] < 0) {
                continue;
            }
            for (y = 0; y < g->h; ++y) {
                unsigned int *p = (unsigned int *)((unsigned char *)grown->pixels + (place_y[code] + y) * grown->pitch);
                for (x = 0; x < g->w; ++x) {
                    unsigned int a = g->px[y * g->w + x];
                    p[place_x[code] + x] = a ? (white | ((a << fmt->ashift) & fmt->amask)) : 0;
                }
            }
            table[n + added][0] = code;
            table[n + added][1] = place_x[code];
            table[n + added][2] = place_y[code];
            table[n + added][3] = place_x[code] + g->w;
            table[n + added][4] = place_y[code] + g->h;
            index[code] = n + added;
            ++added;
        }
    }
    ZeroMemory(table[n + added], sizeof(int[5]));
    for (code = 0x20; code < 0x100; ++code) {
        if (f.state[code] == 2 && f.source[code] == VG_ALIAS) {
            index[code] = vg_entry(&sheet, f.alias[code]);
        }
    }
    *(int (**)[5])(font + VT_FONT_TABLE) = table;
    if (grown != NULL) {
        picture[0] = grown;
        release(old);
    }
    InterlockedIncrement(&g_fonts_extended);
    vg_font_close(&f);
    vg_free(alpha);
}

static void __fastcall after_ctor(unsigned char *font, unsigned int table) {
    __try {
        if (g_game == NULL || font == NULL) {
            return;
        }
        if (table == g_game->burweed_table) {
            extend_font(font, 1, g_game->burweed_spacing);
        } else if (table == g_game->arial_table) {
            extend_font(font, 0, g_game->arial_spacing);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The constructor: thiscall(font; name, table, spacing), ret 0xC, returns its own answer. */
__declspec(naked) static void ctor_hook(void) {
    __asm {
        push    ecx                         /* the font */
        push    dword ptr [esp + 0x10]      /* spacing */
        push    dword ptr [esp + 0x10]      /* table */
        push    dword ptr [esp + 0x10]      /* name */
        call    dword ptr [g_tramp_entry]   /* the game's own constructor (ecx still the font) */
        pop     ecx
        push    eax
        mov     edx, dword ptr [esp + 0x0C] /* table: [esp] answer, +4 return, +8 name, +0xC table */
        call    after_ctor
        pop     eax
        ret     0x0C
    }
}

/* For "VVFP Translations.dll": 1 would mean the game's draw, measure and wrap decode UTF-8.  They do
   not -- every character is one Windows-1252 byte -- so translated text must be Windows-1252. */
int __stdcall VvfpGlyphsUtf8(void) {
    return 0;
}

/* Number of fonts given letters so far (for the tests' emulation). */
int __stdcall VvfpUnicodeTextFonts(void) {
    return (int)g_fonts_extended;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[2];
    const vg_game *g;
    unsigned char *page;
    unsigned int back;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    g = &VG_GAMES[game];
    page = vvfp_code_page_alloc(64);
    if (page == NULL) {
        return;
    }
    CopyMemory(page, g->ctor_bytes, (size_t)g->ctor_len);
    page[g->ctor_len] = 0xE9;
    back = (unsigned int)(g->ctor + (unsigned int)g->ctor_len - ((UINT_PTR)page + g->ctor_len + 5));
    CopyMemory(page + g->ctor_len + 1, &back, 4);
    if (!vvfp_code_page_seal(page, 64)) {
        return;
    }
    g_game = g;
    g_tramp = page;
    g_tramp_entry = page;
    g_text_offset = (unsigned int)g->text_offset;
    g_text_skip = g->text_skip;
    g_text_post = g->text_post;
    vvfp_site_branch(&sites[0], g->ctor, g->ctor_len, g->ctor_bytes, 0xE9, (const void *)ctor_hook);
    vvfp_site_branch(&sites[1], g->text_site, 7, g->text_bytes, 0xE9, (const void *)text_hook);
    if (!vvfp_install_sites(sites, 2)) {
        g_game = NULL;
        VirtualFree(page, 0, MEM_RELEASE);
        return;
    }
    g_installed = 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
