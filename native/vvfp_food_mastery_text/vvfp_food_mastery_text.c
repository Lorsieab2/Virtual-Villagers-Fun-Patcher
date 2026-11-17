/* VVFP Food Mastery Text -- part of "Fix Vanilla Bugs" in The Tree of Life and New Believers.

   WHAT.  The Food Mastery tech's description (the string table's "eTechFoodMasteryInfo") says "At Level 2 your
   tribe gets a 50 percent bonus." without saying what the bonus is for.  The owner (2026-11-16): it reads "At Level
   2 your tribe gets a 50 percent bonus to collected food." for every player, whatever text patch is installed
   (Optional Text Changes replaces The Tree of Life's Assets\sm.xml, Guardians of Isola New Believers'; every one of
   them keeps that line as it is).  Only that line changes; the rest of the description, and every other text, is
   the game's (or the text patch's) own.

   HOW.  The string table's loader (VV4 0x44D750, VV5 0x450A60; called once, from the string table's constructor)
   fills each entry {id, name, built-in text, loaded text} from Assets\sm.xml and ends with the C runtime's cookie
   check (VV4 0x44D92E: call 0x47108D; VV5 0x450C3E: call 0x47C00D), on both of its paths.  That call is pointed at
   fm_after_loader, which first puts the new line in the description and then makes the cookie check itself
   (every register kept).  The description is found by its name in the table; its text (the loaded one, else the
   built-in) is copied into this companion's own buffer with the line replaced, and the entry's loaded text points
   at the copy.  A description without that exact line (another patch's wording) is left as it is.

   This runs inside the loader, so it comes before VVFP Translations.dll's own step after the loader (it wraps the
   loader's call site, VV4 0x44D98A / VV5 0x450C9D): a translation of the new line (whose key holds the new
   English's hash, src/vv_translations.py) is put in place as usual, and one made for the old English is not used.

   SAFETY.  The call site and the instructions around it must hold the stock bytes, or nothing is written (the
   shared all-or-none writer, native/shared/install_sites.h).  Nothing is written to a save or a file; no text is
   shown by this companion.  No debug output. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define FM_NAME "eTechFoodMasteryInfo"
#define FM_OLD "At Level 2 your tribe gets a 50 percent bonus."
#define FM_NEW "At Level 2 your tribe gets a 50 percent bonus to collected food."
#define FM_MAX_TEXT 4096u

typedef struct {
    unsigned int table, count;       /* the string table: 16-byte entries {id, name, built-in, loaded} */
    unsigned int site, cookie;       /* the loader's cookie-check call and the check */
    unsigned int singleton;          /* the string table object's pointer (0 until it is made) */
    unsigned char around[16];        /* the stock bytes from site - 3: xor ecx, esp; call; add esp, 0xCC */
} fm_game;

static const fm_game GAMES[6] = {
    { 0 }, { 0 }, { 0 }, { 0 },
    { 0x4C41F8u, 1338u, 0x44D92Eu, 0x47108Du, 0x4DFF28u,
      { 0x5D, 0x33, 0xCC, 0xE8, 0x5A, 0x37, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
    { 0x4D31F0u, 1409u, 0x450C3Eu, 0x47C00Du, 0x525704u,
      { 0x5D, 0x33, 0xCC, 0xE8, 0xCA, 0xB3, 0x02, 0x00, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00, 0xC3, 0xCC } },
};
#define FM_AROUND_BEFORE 3            /* `pop ebp; xor ecx, esp` before the call */

static int g_game;
static int g_installed;
static int g_fixed;                   /* the description holds the new line (for the tests' emulation) */
static unsigned int g_cookie;
static char g_text[FM_MAX_TEXT + sizeof FM_NEW];   /* the description with the new line, for the whole session */

static int fm_readable(const void *p, unsigned int n) {
    MEMORY_BASIC_INFORMATION info;
    if (p == NULL || VirtualQuery(p, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)p + n <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

/* The length of a readable string of at most `limit` bytes, or -1. */
static int fm_length(const char *s, unsigned int limit) {
    unsigned int n = 0;
    while (n < limit) {
        if (!fm_readable(s + n, 1)) {
            return -1;
        }
        if (s[n] == 0) {
            return (int)n;
        }
        ++n;
    }
    return -1;
}

static void fm_fix(void) {
    const fm_game *g = &GAMES[g_game];
    unsigned int i;
    if (g_game == 0 || !fm_readable((const void *)(UINT_PTR)g->table, g->count * 16u)) {
        return;
    }
    for (i = 0; i < g->count; ++i) {
        unsigned int *entry = (unsigned int *)(UINT_PTR)(g->table + i * 16u);
        const char *name = (const char *)(UINT_PTR)entry[1];
        const char *text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
        const char *at;
        int name_n, text_n;
        size_t old_n = sizeof FM_OLD - 1, new_n = sizeof FM_NEW - 1, before;
        char *copy;
        name_n = fm_length(name, 64u);
        if (name_n != (int)(sizeof FM_NAME - 1) || memcmp(name, FM_NAME, sizeof FM_NAME - 1) != 0) {
            continue;
        }
        if (text == g_text) {
            return;                               /* already ours */
        }
        text_n = fm_length(text, FM_MAX_TEXT);
        if (text_n < 0) {
            return;
        }
        at = strstr(text, FM_OLD);
        /* the whole line: it ends there (a line break or the text's end) */
        if (at == NULL || (at[old_n] != '\n' && at[old_n] != '\0')) {
            return;
        }
        copy = g_text;                            /* text_n < FM_MAX_TEXT: the copy fits */
        before = (size_t)(at - text);
        memcpy(copy, text, before);
        memcpy(copy + before, FM_NEW, new_n);
        memcpy(copy + before + new_n, at + old_n, (size_t)text_n - before - old_n + 1u);
        entry[3] = (unsigned int)(UINT_PTR)copy;
        g_fixed = 1;
        return;                                   /* the game uses the first entry of a name */
    }
}

static void __cdecl fm_after_loader_c(void) {
    __try {
        fm_fix();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of the loader's cookie-check call: the description fixed, then the check itself (ecx kept). */
static __declspec(naked) void fm_after_loader(void) {
    __asm {
        pushad
        call fm_after_loader_c
        popad
        jmp dword ptr [g_cookie]
    }
}

/* 1 when the call is installed (for the tests' emulation), else 0. */
int __stdcall VvfpFoodMasteryTextInstalled(void) {
    return g_installed;
}

/* 1 once the description holds the new line (for the tests' emulation), else 0. */
int __stdcall VvfpFoodMasteryTextFixed(void) {
    return g_fixed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    const fm_game *g;
    vvfp_site_write site;
    (void)shipped;
    if (g_installed || (game != 4 && game != 5)) {
        return;
    }
    g = &GAMES[game];
    if (!vvfp_site_holds(g->site - FM_AROUND_BEFORE, g->around, (int)sizeof g->around)) {
        return;
    }
    g_game = game;
    g_cookie = g->cookie;
    vvfp_site_branch(&site, g->site, 5, g->around + FM_AROUND_BEFORE, 0xE8, (const void *)fm_after_loader);
    if (!vvfp_install_sites(&site, 1)) {
        g_game = 0;
        return;
    }
    g_installed = 1;
    /* the string table was already made (never at game start): fix it now */
    if (fm_readable((const void *)(UINT_PTR)g->singleton, 4)
        && *(const unsigned int *)(UINT_PTR)g->singleton != 0) {
        fm_after_loader_c();
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
