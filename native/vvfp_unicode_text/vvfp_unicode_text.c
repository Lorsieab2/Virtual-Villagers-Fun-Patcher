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
   stock.  Nothing is written into any save or record.

   v1.35.89 -- ANY CHARACTER, IN UTF-8 (text_utf8.h, runtime_glyphs.inc, text_hooks.inc, long_names.inc).
   Text is read by one rule everywhere: a well-formed UTF-8 sequence is its character, any other byte
   its Windows-1252 character, so every older name reads as before.  The game's width, draw, line
   fitting, counted draw and justification routines are detoured: text with UTF-8 in it is drawn by
   units (grapheme clusters, shaped runs), each character a font holds from the font, every other one
   from pages of letters made at run time from the player's Windows fonts (colour emoji included), and
   all of it through the game's own draw and width routines.  Text boxes take any character whole,
   erase whole characters, never cut by pixels, and take VV_SHARED_NAME_BYTES bytes; a name longer than
   its field leaves the box as a short form whose whole name is kept in a per-save file.  Built with
   VVFP_FONT_OVERRIDE this same source is "VVFP Unicode Font.dll" ("Use Unicode Font"): every letter is
   a page letter drawn in the face the player chose. */
#include <windows.h>
#include <string.h>
#include <usp10.h>
#include "../shared/install_sites.h"
#include "../shared/save_folder.h"
#include "../shared/per_save_data.h"
#include "../shared/game_save_slot.h"
#include "unicode_text_tables.h"
#include "text_routines.h"
#include "text_utf8.h"
#include "text_layout.h"
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
static int g_game_number;
static unsigned char *g_tramp;            /* the constructor's first instructions, then a jump back */
static void *g_tramp_entry;
static unsigned int g_text_offset, g_text_skip, g_text_post;
static vg_gdi g_gdi;
static int g_gdi_state;                   /* 0 not opened, 1 open, -1 failed */
static int g_installed;
static volatile LONG g_fonts_extended;    /* how many fonts were given letters (for tests) */

static HINSTANCE g_self;            /* this companion (DllMain) */
#include "runtime_glyphs.inc"
#include "long_names.inc"
#include "text_hooks.inc"

/* ---- Typing ---------------------------------------------------------------------------------- */

/* What to post for SDL's UTF-8 text: one ASCII character as the stock code posts it; any other
   well-formed text as VT_MARK | slot << 8 (text_hooks.inc: the focused box takes it whole); -1 to skip
   it as the stock code would (empty, malformed, or nothing printable). */
int __cdecl VvfpUnicodeTextKey(const unsigned char *s) {
    __try {
        return vt_text_key(s);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
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
    /* Pages of letters made while the game runs take this font's size, baseline and pixel format. */
    rg_register(font, burweed, &f, fmt);
    if (g_override) {
        /* "Use Unicode Font": every letter is a page letter; the font's own are not extended. */
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

/* For "VVFP Translations.dll": 1 = the game's draw, measure and line breaking read UTF-8 (text_utf8.h's
   rule) and call VvfpTranslateText first, so translated text may be any UTF-8.  0 until installed. */
int __stdcall VvfpGlyphsUtf8(void) {
    return g_installed ? 1 : 0;
}

/* For the companions that write logs (native/shared/long_name.h): the whole name of a long name's short
   form (long_names.inc), or `name` itself.  The answer stays valid for the rest of the game. */
const char *__stdcall VvfpLongName(const char *name) {
    __try {
        const unsigned char *whole = g_game != NULL ? ln_full_of((const unsigned char *)name) : NULL;
        if (whole != NULL) {
            return (const char *)whole;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return name;
}

/* For the save call of the statistics companion (native/shared/long_name.h vv_long_names_flush): every Long Names
   record not yet kept is written now, before the game saves, so a long name set just before a quit is in its file. */
int __stdcall VvfpLongNamesFlush(void) {
    __try {
        if (g_game != NULL) {
            ln_flush_pending(1);
            return 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

/* Number of fonts given letters so far (for the tests' emulation). */
int __stdcall VvfpUnicodeTextFonts(void) {
    return (int)g_fonts_extended;
}

/* Units of text made into page letters so far, and texts the companion drew or measured (tests). */
int __stdcall VvfpUnicodeTextUnits(void) {
    return (int)g_units_made;
}

int __stdcall VvfpUnicodeTextOwnDraws(void) {
    return (int)g_own_draws;
}

/* "Use Unicode Font": the face the player chose, from "VVFP Unicode Font.txt" beside this companion (in the
   patcher's files folder; UTF-8; the patcher writes it).  First line: the face (Segoe UI when there is none).
   Second line, when the player chose a font FILE in the Unicode Font window: its name inside the "Unicode Font"
   folder beside this companion; the file is loaded for this game only (AddFontResourceExW with FR_PRIVATE), never
   installed in Windows.  A name with a path in it is ignored. */
static void read_override_face(void) {
    WCHAR path[MAX_PATH], dir[MAX_PATH];
    DWORD n = GetModuleFileNameW(g_self, path, MAX_PATH);
    HANDLE f;
    char raw[512];
    DWORD got = 0;
    int i, start, second = 0;
    lstrcpyW(g_override_face, L"Segoe UI");
    if (n == 0 || n >= MAX_PATH) {
        return;
    }
    while (n > 0 && path[n - 1] != L'\\') {
        --n;
    }
    path[n] = 0;
    if ((int)n + 22 > MAX_PATH) {
        return;                         /* the folder and "VVFP Unicode Font.txt" do not fit a path */
    }
    CopyMemory(dir, path, ((size_t)n + 1) * sizeof(WCHAR));
    lstrcatW(path, L"VVFP Unicode Font.txt");
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return;
    }
    if (ReadFile(f, raw, sizeof raw - 1, &got, NULL) && got > 0) {
        raw[got] = 0;
        start = (got >= 3 && (unsigned char)raw[0] == 0xEF && (unsigned char)raw[1] == 0xBB) ? 3 : 0;
        for (i = start; raw[i]; ++i) {
            if (raw[i] == '\r' || raw[i] == '\n') {
                raw[i] = 0;
                second = i + 1;
                break;
            }
        }
        if (raw[start] && MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw + start, -1, g_override_face, 64) <= 0) {
            lstrcpyW(g_override_face, L"Segoe UI");
        }
        if (second > 0) {
            WCHAR file[104];
            while (raw[second] == '\r' || raw[second] == '\n') {
                ++second;
            }
            for (i = second; raw[i] && raw[i] != '\r' && raw[i] != '\n'; ++i) {
                if (raw[i] == '\\' || raw[i] == '/' || raw[i] == ':') {
                    raw[second] = 0;                    /* a name with a path in it: ignored */
                    break;
                }
            }
            if (raw[i] == '\r' || raw[i] == '\n') {
                raw[i] = 0;
            }
            /* the room needed is the folder, "Unicode Font\\" and the name's own length (with its NUL), not the buffer's */
            int name_len = raw[second] ? MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw + second, -1, file, 104) : 0;
            if (name_len > 0 && (int)n + 13 + name_len <= MAX_PATH) {
                lstrcatW(dir, L"Unicode Font\\");
                lstrcatW(dir, file);
                AddFontResourceExW(dir, FR_PRIVATE, NULL);
            }
        }
    }
    CloseHandle(f);
}

/* A detour at a routine's entry: its first `len` bytes move to a trampoline that jumps back. */
static unsigned char *g_page_at;

static void *tramp(unsigned int va, int len, const unsigned char *bytes) {
    unsigned char *t = g_page_at;
    unsigned int back;
    CopyMemory(t, bytes, (size_t)len);
    t[len] = 0xE9;
    back = (unsigned int)(va + (unsigned int)len - ((UINT_PTR)t + (unsigned int)len + 5));
    CopyMemory(t + len + 1, &back, 4);
    g_page_at += 16;
    return t;
}

#define VT_SITES 13

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[VT_SITES];
    const vg_game *g;
    const vt_game *v;
    unsigned char *page;
    void *t_ctor, *t_width, *t_draw, *t_linefit = NULL, *t_nbyte = NULL, *t_justify = NULL, *t_ctl, *t_edit,
         *t_set, *t_get, *t_type;
    int n = 0;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
#ifdef VVFP_FONT_OVERRIDE
    g_override = 1;
    read_override_face();
#endif
    g = &VG_GAMES[game];
    v = &VT_GAMES[game];
    page = vvfp_code_page_alloc(256);
    if (page == NULL) {
        return;
    }
    g_page_at = page;
    t_ctor = tramp(g->ctor, g->ctor_len, g->ctor_bytes);
    t_width = tramp(v->width, 7, STOCK_WIDTH);
    t_draw = tramp(v->draw, 7, STOCK_DRAW);
    if (v->linefit) t_linefit = tramp(v->linefit, 5, STOCK_LINEFIT);
    if (v->nbyte) t_nbyte = tramp(v->nbyte, 7, STOCK_NBYTE);
    if (v->justify) t_justify = tramp(v->justify, 6, STOCK_JUSTIFY);
    t_ctl = tramp(v->ctldraw, 6, STOCK_CTLDRAW);
    t_edit = tramp(v->seteditable, 5, STOCK_SETEDITABLE);
    t_set = tramp(v->settext, 6, STOCK_SETTEXT);
    t_get = tramp(v->gettext, 6, STOCK_GETTEXT);
    t_type = tramp(v->chartype, 7, STOCK_CHARTYPE);
    if (!vvfp_code_page_seal(page, 256)) {
        return;
    }
    g_game = g;
    g_game_number = game;
    g_vt = v;
    g_tramp = page;
    g_tramp_entry = t_ctor;
    g_text_offset = (unsigned int)g->text_offset;
    g_text_skip = g->text_skip;
    g_text_post = g->text_post;
    g_width = (vt_width_fn)t_width;
    g_ref_width = vt_reference_width;
    g_draw = (vt_draw_fn)t_draw;
    g_linefit = (vt_linefit_fn)t_linefit;
    g_nbyte = (vt_nbyte_fn)t_nbyte;
    g_justify = (vt_justify_fn)t_justify;
    g_ctldraw = (vt_ctldraw_fn)t_ctl;
    g_seteditable = (vt_seteditable_fn)t_edit;
    g_settext = (vt_settext_fn)t_set;
    g_gettext = (vt_gettext_fn)t_get;
    g_chartype_tramp = t_type;
    g_handler = (vt_handler_fn)(UINT_PTR)v->handler;
    g_backspace_back = (void *)(UINT_PTR)(v->backspace + 8);
    vvfp_site_branch(&sites[n++], g->ctor, g->ctor_len, g->ctor_bytes, 0xE9, (const void *)ctor_hook);
    vvfp_site_branch(&sites[n++], g->text_site, 7, g->text_bytes, 0xE9, (const void *)text_hook);
    vvfp_site_branch(&sites[n++], v->width, 7, STOCK_WIDTH, 0xE9, (const void *)width_hook);
    vvfp_site_branch(&sites[n++], v->draw, 7, STOCK_DRAW, 0xE9, (const void *)draw_hook);
    if (v->linefit) vvfp_site_branch(&sites[n++], v->linefit, 5, STOCK_LINEFIT, 0xE9, (const void *)linefit_hook);
    if (v->nbyte) vvfp_site_branch(&sites[n++], v->nbyte, 7, STOCK_NBYTE, 0xE9, (const void *)nbyte_hook);
    if (v->justify) vvfp_site_branch(&sites[n++], v->justify, 6, STOCK_JUSTIFY, 0xE9, (const void *)justify_hook);
    vvfp_site_branch(&sites[n++], v->ctldraw, 6, STOCK_CTLDRAW, 0xE9, (const void *)ctldraw_hook);
    vvfp_site_branch(&sites[n++], v->seteditable, 5, STOCK_SETEDITABLE, 0xE9, (const void *)seteditable_hook);
    vvfp_site_branch(&sites[n++], v->settext, 6, STOCK_SETTEXT, 0xE9, (const void *)settext_hook);
    vvfp_site_branch(&sites[n++], v->gettext, 6, STOCK_GETTEXT, 0xE9, (const void *)gettext_hook);
    vvfp_site_branch(&sites[n++], v->chartype, 7, STOCK_CHARTYPE, 0xE9, (const void *)chartype_hook);
    vvfp_site_branch(&sites[n++], v->backspace, 8, STOCK_BACKSPACE, 0xE9, (const void *)backspace_hook);
    if (!vvfp_install_sites(sites, n)) {
        g_game = NULL;
        g_vt = NULL;
        VirtualFree(page, 0, MEM_RELEASE);
        return;
    }
    g_installed = 1;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
