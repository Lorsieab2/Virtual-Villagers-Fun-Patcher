/* VVFP Text Fixes -- the game-text part of "Fix Vanilla Bugs" in all five games.

   WHAT.  Typos in the games' own text that the owner approved (2026-11-17; data/vanilla_text_fixes.json and the
   table built from it, tf_fixes.inc), and The Tree of Life's and New Believers' Food Mastery line (the owner,
   2026-11-16: "At Level 2 your tribe gets a 50 percent bonus." reads "... a 50 percent bonus to collected food.").
   A typo fix applies only when the text the game would show is exactly the stock text, so Optional Text Changes',
   Guardians of Isola's and any other wording is left as it is.  The Food Mastery line is changed wherever that whole
   line stands in the description (every text patch keeps it).  Every other text is the game's (or the text patch's)
   own.  Nothing is written to a save or a file; no text is shown by this companion; no debug output.

   HOW.
   * A New Home, The Lost Children: the string table is {id, text, ...} rows in the executable that the game's
     lookup (VV1 0x433880, VV2 0x4415A0) searches for the first row with an id.  At start (VvfpStartup) that row's
     text pointer is pointed at a copy of the fixed text when it points at exactly the stock text.  VVFP
     Translations.dll starts this companion before its own table step when both are shipped, so a translation made
     for the fixed English (the template's, src/vv_translations.py) is used.
   * The Secret City, The Tree of Life, New Believers: the string table's loader fills each entry {id, name,
     built-in text, loaded text} from Assets\sm.xml.  At its end this companion fixes the entries (the loaded text,
     else the built-in one), before VVFP Translations.dll's own step after the loader:
       VV3: the loader 0x42F4F0's epilogue `add esp, 0xC8` (0x42F6A5) jumps here; the step then makes it and returns.
       VV4/VV5: the loader (0x44D750 / 0x450A60) ends with the C runtime's cookie check (call 0x47108D at 0x44D92E /
       call 0x47C00D at 0x450C3E) on both of its paths; that call comes here, and the step makes the check itself.
     Every register is kept.
   * The Tree of Life's cutting-tool harvest caption (the owner, 2026-11-17): picking blackberries (action 99,
     0x451C30) and the harvest with a cutting tool (action 0xBE, 0x451CE0) both copy text 0x280
     (eSayHarvestingBlackberries, "Harvesting blackberries") into the villager's caption (+0x1CE4, at most 0x27
     letters, 0x4724E0).  The owner's caption, "Harvesting blackberries with a cutting tool" (43 letters), does not
     fit that field, so the field gets a short mark and the full caption is drawn in its place:
       - the harvest's own copy -- 0x451CF6, `push 0x27 / push eax / lea eax, [esi+0x1CE4]` -- jumps to
         tf_caption_stub, which pushes CAPTION_MARK ("Harvesting berries with a cutting tool", 38 letters, so the
         game's own 0x27-byte copy holds it whole) when the looked-up text is exactly the stock English or the
         player's language has the caption; any other text (another patch's) is kept;
       - the field's one reader, the villager panel's Action line (0x4404F3, `add edx, 0x1CE4 / push edx` before
         its label's set-text 0x40D3E0, which copies any length onto the heap), jumps to tf_caption_shown_stub,
         which hands the label the full caption (or its translation, VVFP Translations.dll row
         vvfp.text_fixes/vvfp_text_fixes.tf_caption.s0) when the field holds exactly CAPTION_MARK, else the field.
     Nothing is written past the field; the field is never saved (the save keeps only the record's windows).
     Picking is the game's own.  Installed with the loader's site, all or none.
       - the Action label draws a caption wider than the bar's visible part with its letters a pixel closer, so the
         whole caption shows before the panel's stone frame (tf_action_draw, below; R6 live, 2026-11-21).
   * New Believers' lab equipment line (the owner, 2026-11-18): a click on the ground at place 35 writes
     "<n> of 12 pieces of lab equipment collected" (0x443AC0: sprintf of the format "%d%s12 %s" at 0x49A350, pushed
     at 0x443BB0, with strings 1183 " of " and 1184), but n counts all 24 pieces (0x413F50(0x50 ...)), so players
     read "13 of 12".  The Collections screen formats "%d%s24" (0x49A0E4).  That one push gets this companion's
     "%d%s24 %s" when the format there is exactly the stock "%d%s12 %s"; the words stay the game's string rows (and
     their translations).  Installed with the loader's site, all or none.

   SAFETY.  The sites and the instructions around them must hold the stock bytes, or nothing is written (the shared
   all-or-none writer, native/shared/install_sites.h); a table row is written only when its pointer still points at
   the stock text. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"

typedef struct {
    int game;
    const char *name;                  /* VV3-VV5: the string table name */
    unsigned int id;                   /* VV1/VV2: the table row id */
    const char *old_text;              /* exactly the stock text */
    const char *new_text;              /* the fixed text */
} tf_fix;

#include "tf_fixes.inc"
#define TF_FIX_COUNT ((int)(sizeof TF_FIXES / sizeof TF_FIXES[0]))

#define FM_NAME "eTechFoodMasteryInfo"
#define FM_OLD "At Level 2 your tribe gets a 50 percent bonus."
#define FM_NEW "At Level 2 your tribe gets a 50 percent bonus to collected food."
#define TF_MAX_TEXT 4096u

typedef struct {
    unsigned int table, count, stride;  /* VV1/VV2 rows {id, text, ...}; VV3-VV5 entries {id, name, built-in, loaded} */
    unsigned int site, cookie;          /* VV3: the epilogue `add esp, 0xC8`; VV4/VV5: the cookie-check call, the check */
    int before, length, around_n;       /* the stock bytes: around_n of them from site - before; the site's length */
    unsigned char around[16];
} tf_game;

static const tf_game GAMES[6] = {
    { 0 },
    { 0x487208u, 0x275u, 0x14u, 0, 0, 0, 0, 0, { 0 } },
    { 0x496300u, 0x36Cu, 12u, 0, 0, 0, 0, 0, { 0 } },
    /* pop esi; mov eax, ebp; pop ebp; [add esp, 0xC8]; ret; nop */
    { 0x4AB990u, 0x4BAu, 16u, 0x42F6A5u, 0, 4, 6, 12,
      { 0x5E, 0x8B, 0xC5, 0x5D, 0x81, 0xC4, 0xC8, 0x00, 0x00, 0x00, 0xC3, 0x90 } },
    /* pop ebp; xor ecx, esp; [call cookie]; add esp, 0xCC; ret; int3 */
    { 0x4C41F8u, 1338u, 16u, 0x44D92Eu, 0x47108Du, 3, 5, 16,
      { 0x5D, 0x33, 0xCC, 0xE8, 0x5A, 0x37, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
    { 0x4D31F0u, 1409u, 16u, 0x450C3Eu, 0x47C00Du, 3, 5, 16,
      { 0x5D, 0x33, 0xCC, 0xE8, 0xCA, 0xB3, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
};

/* The Tree of Life's cutting-tool harvest caption (see the top). */
#define CAPTION_SITE 0x451CF6u
#define CAPTION_ON 0x451CFFu
#define CAPTION_LOOKUP 0x451CE6u
#define CAPTION_OLD "Harvesting blackberries"
static const unsigned char CAPTION_STOCK[9] = { 0x6A, 0x27, 0x50, 0x8D, 0x86, 0xE4, 0x1C, 0x00, 0x00 };
static const unsigned char CAPTION_ON_STOCK[5] = { 0x50, 0xE8, 0xDB, 0x07, 0x02 };   /* push eax / call 0x4724E0 */
static const unsigned char CAPTION_LOOKUP_STOCK[5] = { 0x68, 0x80, 0x02, 0x00, 0x00 };   /* push 0x280 */
/* the villager panel's Action line: mov edx, [esp+0x10] / mov ecx, [ebp+0xE4] / [add edx, 0x1CE4 / push edx] /
   call 0x40D3E0 */
#define CAPTION_SHOWN_SITE 0x4404F3u
#define CAPTION_SHOWN_ON 0x4404FAu
#define CAPTION_SHOWN_BEFORE 10
static const unsigned char CAPTION_SHOWN_AROUND[22] = { 0x8B, 0x54, 0x24, 0x10, 0x8B, 0x8D, 0xE4, 0x00, 0x00, 0x00,
                                                        0x81, 0xC2, 0xE4, 0x1C, 0x00, 0x00, 0x52,
                                                        0xE8, 0xE1, 0xCE, 0xFC, 0xFF };
#define CAPTION_SHOWN_LENGTH 7
/* what the harvest writes into the 0x27-byte field: the mark the Action line draws the full caption for */
static const char CAPTION_MARK[] = "Harvesting berries with a cutting tool";
static const char caption_english[] = "Harvesting blackberries with a cutting tool";

/* The Action line drawn whole (R6 live check, 2026-11-21: "Harvesting blackberries with a cutting to").  The label
   (0x40D8A0, x 0x12E, left-aligned, Arial Bold, letter spacing 0) has no width of its own: the game draws the whole
   text, but the villager panel's stone frame (the arrows and Detail) is drawn over the bar from about x 650, so a
   caption wider than the bar's visible part is hidden there.  The owner's caption is 368 pixels; the bar shows 344.
   So the Action label gets its own copy of the label class's vtable (LABEL_VTABLE, 8 slots after its RTTI locator)
   whose draw slot (6: 0x40D3A0, the stock draw: shown -> the text control's draw 0x40CE20) is tf_action_draw: when
   the label's text is wider than ACTION_RIGHT allows, the font's letter spacing (ldwFontImpl +8, read by the game's
   width routine 0x402430 and its draw 0x409700 for every glyph) is made 1 -- at most ACTION_TIGHTEN_MAX -- pixel
   smaller for that one draw, and put back at once.  Every word stays, in the game's own font and colour; the
   letters are a pixel closer.  Any Action caption that does not fit is drawn so (a translation's too), every other
   one exactly as before.  Nothing is written to the game's code or data but the one label's vtable pointer. */
#define LABEL_VTABLE 0x48A96Cu
#define LABEL_SLOTS 8
#define LABEL_DRAW_SLOT 6
#define LABEL_DRAW 0x40D3A0u
#define FONT_WIDTH 0x402430u               /* (font; text, float scale) ret 8: the widest line, less one spacing */
#define ACTION_RIGHT 646                   /* the bar's visible part ends here (the label's own coordinates) */
#define ACTION_TIGHTEN_MAX 2
/* the RTTI locator, then the 8 slots */
static const unsigned int LABEL_VT_STOCK[LABEL_SLOTS + 1] = { 0x4AE704u, 0x40D950u, 0x40A430u, 0x40D2B0u, 0x40D320u,
                                                              0x40D340u, 0x40D360u, 0x40D3A0u, 0x40A830u };
static unsigned int g_action_vt[LABEL_SLOTS + 1];   /* the Action label's copy: [0] the locator, then the slots */

/* New Believers' lab equipment line (see the top): the ground click's format push and the stock format. */
#define LAB_SITE 0x443BB0u
#define LAB_FORMAT_VA 0x49A350u
#define LAB_OLD "%d%s12 %s"
static const char LAB_NEW[] = "%d%s24 %s";
/* push eax / lea ecx, [esp+0x18] / [push 0x49A350] / push ecx / call 0x47C046 */
static const unsigned char LAB_AROUND[17] = { 0x50, 0x8D, 0x4C, 0x24, 0x18, 0x68, 0x50, 0xA3, 0x49, 0x00, 0x51,
                                              0xE8, 0x8B, 0x84, 0x03, 0x00, 0x83 };
#define LAB_BEFORE 5

static int g_game;
static int g_installed;
static int g_caption_installed;
static int g_lab_installed;
static unsigned int g_lab_format;       /* the operand the site gets: LAB_NEW's address */
static int g_applied;                   /* texts this companion replaced (for the tests' emulation) */
static unsigned int g_cookie;
static char *g_copy[TF_FIX_COUNT];      /* each fixed text, in writable memory, for the whole session */
static char g_pool[TF_POOL_SIZE];       /* where those copies are made */
static unsigned int g_pool_used;
static char g_fm_text[TF_MAX_TEXT + sizeof FM_NEW];   /* the Food Mastery description with the new line */

/* `n` bytes at `p` are committed and readable (each region they span is asked about). */
static int tf_readable(const void *p, unsigned int n) {
    UINT_PTR at = (UINT_PTR)p, end = (UINT_PTR)p + n;
    if (p == NULL || end < at) {
        return 0;
    }
    do {
        MEMORY_BASIC_INFORMATION info;
        UINT_PTR region_end;
        if (VirtualQuery((const void *)at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
            || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
            return 0;
        }
        region_end = (UINT_PTR)info.BaseAddress + info.RegionSize;
        if (region_end <= at) {
            return 0;
        }
        at = region_end;
    } while (at < end);
    return 1;
}

/* The length of a readable string of at most `limit` bytes, or -1. */
static int tf_length(const char *s, unsigned int limit) {
    unsigned int n = 0;
    while (n < limit) {
        if ((n == 0 || ((UINT_PTR)(s + n) & 0xFFFu) == 0) && !tf_readable(s + n, 1)) {   /* once a page */
            return -1;
        }
        if (s[n] == 0) {
            return (int)n;
        }
        ++n;
    }
    return -1;
}

/* `text` is exactly `want`. */
static int tf_same(const char *text, const char *want) {
    size_t n = strlen(want);
    return text != NULL && tf_length(text, TF_MAX_TEXT) == (int)n && memcmp(text, want, n) == 0;
}

/* The fixed text `i` in this companion's own writable memory (made once), or NULL. */
static char *tf_copy(int i) {
    if (g_copy[i] == NULL) {
        size_t n = strlen(TF_FIXES[i].new_text) + 1u;
        if (n <= TF_POOL_SIZE - g_pool_used) {
            char *p = g_pool + g_pool_used;
            memcpy(p, TF_FIXES[i].new_text, n);
            g_pool_used += (unsigned int)n;
            g_copy[i] = p;
        }
    }
    return g_copy[i];
}

/* The entry's name is `name` (two of the games' own names end in a tab). */
static int tf_name_is(const char *entry_name, const char *name) {
    int n = tf_length(entry_name, 200u);
    size_t want = strlen(name);
    while (n > 0 && (entry_name[n - 1] == '\t' || entry_name[n - 1] == ' ')) {
        --n;
    }
    return n == (int)want && memcmp(entry_name, name, want) == 0;
}

/* The Food Mastery description's whole line "At Level 2 ... bonus." (followed by a line break or the end). */
static void tf_food_mastery(unsigned int *entry) {
    const char *text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
    const char *at;
    int text_n;
    size_t old_n = sizeof FM_OLD - 1, new_n = sizeof FM_NEW - 1, before;
    if (text == g_fm_text) {
        return;                                   /* already ours */
    }
    text_n = tf_length(text, TF_MAX_TEXT);
    if (text_n < 0) {
        return;
    }
    at = strstr(text, FM_OLD);
    if (at == NULL || (at[old_n] != '\n' && at[old_n] != '\0')) {
        return;
    }
    before = (size_t)(at - text);                 /* text_n < TF_MAX_TEXT: the copy fits */
    memcpy(g_fm_text, text, before);
    memcpy(g_fm_text + before, FM_NEW, new_n);
    memcpy(g_fm_text + before + new_n, at + old_n, (size_t)text_n - before - old_n + 1u);
    entry[3] = (unsigned int)(UINT_PTR)g_fm_text;
    ++g_applied;
}

/* VV3-VV5: every fix of this game in the filled string table (the first entry of each name, as the game uses). */
static void tf_fix_sm(void) {
    const tf_game *g = &GAMES[g_game];
    int done[TF_FIX_COUNT];
    int fm_done = (g_game != 4 && g_game != 5);
    unsigned int e;
    int i;
    if (g_game < 3 || !tf_readable((const void *)(UINT_PTR)g->table, g->count * g->stride)) {
        return;
    }
    for (i = 0; i < TF_FIX_COUNT; ++i) {
        done[i] = TF_FIXES[i].game != g_game || TF_FIXES[i].name == NULL;
    }
    for (e = 0; e < g->count; ++e) {
        unsigned int *entry = (unsigned int *)(UINT_PTR)(g->table + e * g->stride);
        const char *name = (const char *)(UINT_PTR)entry[1];
        if (name == NULL) {
            continue;
        }
        if (!fm_done && tf_name_is(name, FM_NAME)) {
            fm_done = 1;
            tf_food_mastery(entry);
            continue;
        }
        for (i = 0; i < TF_FIX_COUNT; ++i) {
            const char *text;
            char *copy;
            if (done[i] || !tf_name_is(name, TF_FIXES[i].name)) {
                continue;
            }
            done[i] = 1;
            text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
            if (text == g_copy[i] || !tf_same(text, TF_FIXES[i].old_text)) {
                continue;                         /* already ours, or another wording */
            }
            copy = tf_copy(i);
            if (copy != NULL) {
                entry[3] = (unsigned int)(UINT_PTR)copy;
                ++g_applied;
            }
        }
    }
}

static void __cdecl tf_after_loader_c(void) {
    __try {
        tf_fix_sm();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* VV4/VV5: in place of the loader's cookie-check call: the fixes, then the check itself (ecx kept). */
static __declspec(naked) void tf_after_loader_call(void) {
    __asm {
        pushad
        call tf_after_loader_c
        popad
        jmp dword ptr [g_cookie]
    }
}

/* VV3: in place of the loader's epilogue `add esp, 0xC8` (then its `ret`): eax, the table object, is kept. */
static __declspec(naked) void tf_after_loader_jmp(void) {
    __asm {
        pushad
        call tf_after_loader_c
        popad
        add esp, 0xC8
        ret
    }
}

/* VV1/VV2: the first row of each fixed id points at the fixed text when it points at the stock text. */
static void tf_fix_table(void) {
    static vvfp_site_write writes[TF_FIX_COUNT];
    static unsigned int expect[TF_FIX_COUNT], value[TF_FIX_COUNT];
    const tf_game *g = &GAMES[g_game];
    int i, n = 0;
    if (!tf_readable((const void *)(UINT_PTR)g->table, g->count * g->stride)) {
        return;
    }
    for (i = 0; i < TF_FIX_COUNT; ++i) {
        unsigned int r;
        if (TF_FIXES[i].game != g_game || TF_FIXES[i].name != NULL) {
            continue;
        }
        for (r = 0; r < g->count; ++r) {
            const unsigned int *row = (const unsigned int *)(UINT_PTR)(g->table + r * g->stride);
            char *copy;
            if (row[0] != TF_FIXES[i].id) {
                continue;
            }
            if (tf_same((const char *)(UINT_PTR)row[1], TF_FIXES[i].old_text) && (copy = tf_copy(i)) != NULL) {
                expect[n] = row[1];
                value[n] = (unsigned int)(UINT_PTR)copy;
                vvfp_site_bytes(&writes[n], (unsigned int)(UINT_PTR)&row[1], 4, (const unsigned char *)&expect[n],
                                (const unsigned char *)&value[n]);
                ++n;
            }
            break;                                /* the game's lookup takes the first row of an id */
        }
    }
    if (n > 0 && vvfp_install_sites(writes, n)) {
        g_applied += n;
    }
}

/* The full caption in the player's language (drawn from a pointer: any length). */
static const char *tf_caption_full(void) {
    return vvfp_tr("vvfp.text_fixes/vvfp_text_fixes.tf_caption.s0", caption_english, 0u);
}

/* The Tree of Life's cutting-tool harvest: what it copies into the field instead of `looked_up` (text 0x280's). */
static const char *__cdecl tf_caption(const char *looked_up) {
    const char *text = looked_up;
    __try {
        if (tf_caption_full() != caption_english || tf_same(looked_up, CAPTION_OLD)) {
            text = CAPTION_MARK;                  /* the language has the caption, or the stock English is in place */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        text = looked_up;
    }
    return text;
}

typedef void (__fastcall *tf_draw_fn)(void *self, void *edx);
typedef int (__fastcall *tf_width_fn)(void *font, void *edx, const char *text, float scale);

/* The pixels by which the font's letter spacing is made smaller for this draw of the Action label's text control
   `ctl` (0: it fits, or it is not a plain left-aligned label with its own font), and that spacing in `*spacing`. */
static int tf_action_tighten(unsigned char *ctl, int **spacing) {
    const char *text;
    unsigned char *font, *impl;
    int width, room, gaps, d;
    *spacing = NULL;
    if (!tf_readable(ctl, 0x5C) || ctl[0x24] != 0 || *(int *)(ctl + 0x40) != 0) {
        return 0;                              /* a text box, or not left-aligned: as the game draws it */
    }
    text = *(const char **)(ctl + 0x30);
    font = *(unsigned char **)(ctl + 0x3C);
    if (text == NULL || font == NULL || !tf_readable(font, 8)) {
        return 0;
    }
    impl = *(unsigned char **)(font + 4);
    gaps = tf_length(text, TF_MAX_TEXT) - 1;
    if (impl == NULL || !tf_readable(impl, 12) || gaps < 1) {
        return 0;
    }
    width = ((tf_width_fn)(UINT_PTR)FONT_WIDTH)(font, NULL, text, 1.0f);
    room = ACTION_RIGHT - *(int *)(ctl + 8) - *(int *)(ctl + 0x44);
    if (width <= room) {
        return 0;
    }
    d = (width - room + gaps - 1) / gaps;
    *spacing = (int *)(impl + 8);
    return d < ACTION_TIGHTEN_MAX ? d : ACTION_TIGHTEN_MAX;
}

/* The Action label's draw (its vtable's slot LABEL_DRAW_SLOT): the stock draw, its letters closer when its text is
   wider than the bar shows. */
static void __fastcall tf_action_draw(unsigned char *label, void *edx) {
    int *spacing = NULL, saved = 0, d = 0;
    (void)edx;
    __try {
        if (label[8] != 0) {                   /* shown (the stock draw's own test) */
            d = tf_action_tighten(*(unsigned char **)(label + 0x10), &spacing);
        }
        if (d > 0 && spacing != NULL) {
            saved = *spacing;
            *spacing = saved - d;
        } else {
            spacing = NULL;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        spacing = NULL;
    }
    ((tf_draw_fn)(UINT_PTR)LABEL_DRAW)(label, NULL);
    if (spacing != NULL) {
        *spacing = saved;
    }
}

/* The villager panel's Action line: the text its label gets for the caption field `field`; the label (`label`, the
   game's own, still with the label class's vtable) gets the Action label's draw (above). */
static const char *__cdecl tf_caption_shown(const char *field, unsigned int *label) {
    const char *text = field;
    __try {
        if (tf_same(field, CAPTION_MARK)) {
            text = tf_caption_full();
        }
        if (tf_readable(label, 0x14) && label[0] == LABEL_VTABLE) {
            label[0] = (unsigned int)(UINT_PTR)&g_action_vt[1];
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        text = field;
    }
    return text;
}

/* At CAPTION_SHOWN_SITE (edx the villager, ecx the label): `add edx, 0x1CE4 / push edx` with the label's text
   pushed instead, then on at CAPTION_SHOWN_ON (call the set-text). */
static __declspec(naked) void tf_caption_shown_stub(void) {
    __asm {
        add edx, 0x1CE4
        push ecx
        push ecx
        push edx
        call tf_caption_shown
        add esp, 8
        pop ecx
        push eax
        push CAPTION_SHOWN_ON
        ret
    }
}

/* At CAPTION_SITE (eax the looked-up text, esi the villager): the stock three instructions with the caption pushed
   instead, then on at CAPTION_ON (push eax / call the copy). */
static __declspec(naked) void tf_caption_stub(void) {
    __asm {
        pushad
        push eax
        call tf_caption
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        push 0x27
        push eax
        lea eax, [esi + 0x1CE4]
        push CAPTION_ON
        ret
    }
}

/* 1 once VvfpStartup has set the fixes up for this game (for the tests' emulation), else 0. */
int __stdcall VvfpTextFixesInstalled(void) {
    return g_installed;
}

/* 1 when The Tree of Life's cutting-tool harvest caption site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpTextFixesCaptionInstalled(void) {
    return g_caption_installed;
}

/* 1 when New Believers' lab equipment line site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpTextFixesLabInstalled(void) {
    return g_lab_installed;
}

/* How many texts this companion has replaced so far (for the tests' emulation). */
int __stdcall VvfpTextFixesApplied(void) {
    return g_applied;
}

/* Called once by VVFP Startup.dll before WinMain -- and, when both are shipped, first by VVFP Translations.dll
   before its own start; the second call does nothing. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    const tf_game *g;
    vvfp_site_write site[3];
    int n = 1, lab = 0;
    (void)shipped;
    if (g_installed || game < 1 || game > 5) {
        return;
    }
    g = &GAMES[game];
    if (game <= 2) {
        g_game = game;
        g_installed = 1;
        __try {
            tf_fix_table();
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return;
    }
    if (!vvfp_site_holds(g->site - (unsigned int)g->before, g->around, g->around_n)) {
        return;
    }
    g_game = game;
    g_cookie = g->cookie;
    vvfp_site_branch(&site[0], g->site, g->length, g->around + g->before, game == 3 ? 0xE9 : 0xE8,
                     game == 3 ? (const void *)tf_after_loader_jmp : (const void *)tf_after_loader_call);
    if (game == 4) {
        /* the cutting-tool harvest's caption copy (its look-up and the copy after it must be stock too) and the
           Action line that draws the field (the code round it must be stock too) */
        if (!vvfp_site_holds(CAPTION_LOOKUP, CAPTION_LOOKUP_STOCK, sizeof CAPTION_LOOKUP_STOCK)
            || !vvfp_site_holds(CAPTION_ON, CAPTION_ON_STOCK, sizeof CAPTION_ON_STOCK)
            || !vvfp_site_holds(CAPTION_SHOWN_SITE - CAPTION_SHOWN_BEFORE, CAPTION_SHOWN_AROUND,
                                sizeof CAPTION_SHOWN_AROUND)
            || !vvfp_site_holds(LABEL_VTABLE - 4u, (const unsigned char *)LABEL_VT_STOCK, sizeof LABEL_VT_STOCK)) {
            return;
        }
        /* the Action label's vtable: the label class's own, with the draw that keeps its caption in the bar */
        memcpy(g_action_vt, (const void *)(UINT_PTR)(LABEL_VTABLE - 4u), sizeof g_action_vt);
        g_action_vt[1 + LABEL_DRAW_SLOT] = (unsigned int)(UINT_PTR)tf_action_draw;
        vvfp_site_branch(&site[1], CAPTION_SITE, sizeof CAPTION_STOCK, CAPTION_STOCK, 0xE9,
                         (const void *)tf_caption_stub);
        vvfp_site_branch(&site[2], CAPTION_SHOWN_SITE, CAPTION_SHOWN_LENGTH,
                         CAPTION_SHOWN_AROUND + CAPTION_SHOWN_BEFORE, 0xE9, (const void *)tf_caption_shown_stub);
        n = 3;
    }
    if (game == 5) {
        /* the ground click's format: the push and the code round it, and the stock format text itself */
        if (!vvfp_site_holds(LAB_SITE - LAB_BEFORE, LAB_AROUND, sizeof LAB_AROUND)
            || !tf_same((const char *)(UINT_PTR)LAB_FORMAT_VA, LAB_OLD)) {
            return;
        }
        g_lab_format = (unsigned int)(UINT_PTR)LAB_NEW;
        vvfp_site_bytes(&site[1], LAB_SITE + 1u, 4, LAB_AROUND + LAB_BEFORE + 1,
                        (const unsigned char *)&g_lab_format);
        n = 2;
        lab = 1;
    }
    if (!vvfp_install_sites(site, n)) {
        g_game = 0;
        return;
    }
    g_installed = 1;
    g_caption_installed = (game == 4 && n == 3);
    g_lab_installed = lab;
    /* Nothing more here: both callers (VVFP Startup.dll and VVFP Translations.dll) start this companion before
       WinMain, when the string table has not been made, so the loader's own end (the site above) fixes it.  The
       game's data is never read here (tests/test_startup_loader.py audits every access before WinMain). */
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
