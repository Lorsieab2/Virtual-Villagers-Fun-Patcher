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

   SAFETY.  The sites and the instructions around them must hold the stock bytes, or nothing is written (the shared
   all-or-none writer, native/shared/install_sites.h); a table row is written only when its pointer still points at
   the stock text. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

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
    unsigned int singleton;             /* VV3-VV5: the string table object's pointer (0 until it is made) */
    int before, length, around_n;       /* the stock bytes: around_n of them from site - before; the site's length */
    unsigned char around[16];
} tf_game;

static const tf_game GAMES[6] = {
    { 0 },
    { 0x487208u, 0x275u, 0x14u, 0, 0, 0, 0, 0, 0, { 0 } },
    { 0x496300u, 0x36Cu, 12u, 0, 0, 0, 0, 0, 0, { 0 } },
    /* pop esi; mov eax, ebp; pop ebp; [add esp, 0xC8]; ret; nop */
    { 0x4AB990u, 0x4BAu, 16u, 0x42F6A5u, 0, 0x593A74u, 4, 6, 12,
      { 0x5E, 0x8B, 0xC5, 0x5D, 0x81, 0xC4, 0xC8, 0x00, 0x00, 0x00, 0xC3, 0x90 } },
    /* pop ebp; xor ecx, esp; [call cookie]; add esp, 0xCC; ret; int3 */
    { 0x4C41F8u, 1338u, 16u, 0x44D92Eu, 0x47108Du, 0x4DFF28u, 3, 5, 16,
      { 0x5D, 0x33, 0xCC, 0xE8, 0x5A, 0x37, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
    { 0x4D31F0u, 1409u, 16u, 0x450C3Eu, 0x47C00Du, 0x525704u, 3, 5, 16,
      { 0x5D, 0x33, 0xCC, 0xE8, 0xCA, 0xB3, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
};

static int g_game;
static int g_installed;
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

/* 1 once VvfpStartup has set the fixes up for this game (for the tests' emulation), else 0. */
int __stdcall VvfpTextFixesInstalled(void) {
    return g_installed;
}

/* How many texts this companion has replaced so far (for the tests' emulation). */
int __stdcall VvfpTextFixesApplied(void) {
    return g_applied;
}

/* Called once by VVFP Startup.dll before WinMain -- and, when both are shipped, first by VVFP Translations.dll
   before its own start; the second call does nothing. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    const tf_game *g;
    vvfp_site_write site;
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
    vvfp_site_branch(&site, g->site, g->length, g->around + g->before, game == 3 ? 0xE9 : 0xE8,
                     game == 3 ? (const void *)tf_after_loader_jmp : (const void *)tf_after_loader_call);
    if (!vvfp_install_sites(&site, 1)) {
        g_game = 0;
        return;
    }
    g_installed = 1;
    /* the string table was already made (never at game start): fix it now */
    if (tf_readable((const void *)(UINT_PTR)g->singleton, 4) && *(const unsigned int *)(UINT_PTR)g->singleton != 0) {
        tf_after_loader_c();
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
