/* VVFP Long Words -- part of "Fix Vanilla Bugs" in The Lost Children, The Secret City, The Tree of Life and New
   Believers (the owner's policy: a vanilla bug found along the way is fixed in every game that has it, under Fix
   Vanilla Bugs, by a companion -- not by patched executable bytes).

   THE BUG.  A word wider than the box it is laid out in (a long name, a long unbroken word in a translation or a
   Custom Island Event) is never placed by the two routines that lay text out in lines:
     * the justified paragraph (The Secret City 0x40A0C0, The Tree of Life 0x409C30, New Believers 0x409F00; every
       island event, tip and notice body) adds words to a line until it is too wide, then drops the last one -- and a
       line whose only word is too wide drops that word too, draws an empty line, and starts again on the same word,
       for ever;
     * the line fit (The Lost Children 0x4022B0, The Secret City 0x4022F0, The Tree of Life 0x402550, New Believers
       0x402500; the tips' line loops and the wrapped height measures) backs off from a line too wide to its last
       space -- and a line with no space backs off to nothing and returns one letter on, so the word loses its
       letters one empty line each until the rest of it fits (the paragraph hangs; the line fit cuts the word).
   A New Home has neither routine (its texts are broken into lines in the string table); The Lost Children has only
   the line fit.

   THE FIX (one place in each routine, so every caller is fixed):
     * the justified paragraph: at its `cmp ecx, eax` deciding whether to drop the line's last word, a line of one
       word keeps it -- the word is laid out on a line of its own, at its full width (wider than the box), and the
       paragraph goes on with the next word;
     * the line fit: at its `cmp byte [esi], ' '` starting the back-off, a line with no space keeps the letters it
       has and takes the rest of the word (up to the next space, line break or the end, and never more than the
       caller's buffer holds: the line's letter limit less one, as the stock line keeps) -- the word gets a line of
       its own at its full width.  A line with a space backs off exactly as before.
   Text with no such word goes through the very same instructions as before: the companion only decides the one
   case the stock code gets wrong.

   SAFETY.  Each site's stock bytes, and the instructions around it the stub relies on, are checked first; all of
   them or none are written (native/shared/install_sites.h).  Nothing is saved.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define LW_GAME_BASE 0x400000u

typedef struct lw_game {
    unsigned int justify_site;      /* `cmp ecx, eax` + `mov [esp+N], edi` (6 bytes), 0: none */
    unsigned char justify_stock[16];
    int justify_check;              /* bytes of justify_stock checked from the site (the jge 6 bytes later too) */
    int justify_count_at;           /* N: 0x14 (The Secret City) or 0x18 */
    unsigned int linefit_site;      /* `cmp byte [esi], 0x20; je end` (5 bytes) */
    unsigned char linefit_stock[16];
    int linefit_check;
    unsigned int linefit_end;       /* the je's target: the line ends at esi */
} lw_game;

/* The justified paragraph: cmp ecx, eax; mov [esp+N], edi; mov [esp+M], ebp; jge +0x0A.
   The line fit: cmp byte [esi], 0x20; je end; then the back-off loop's first compare (cmp esi, [esp+0x30]). */
static const lw_game LW_GAMES[6] = {
    {0},
    {0},
    {0, {0}, 0, 0,
     0x4023E5u, {0x80, 0x3E, 0x20, 0x74, 0x15, 0x8D, 0x9B, 0x00, 0x00, 0x00, 0x00, 0x3B, 0x74, 0x24, 0x30}, 15, 0x4023FFu},
    {0x40A2DCu, {0x3B, 0xC8, 0x89, 0x7C, 0x24, 0x14, 0x89, 0x6C, 0x24, 0x18, 0x7D, 0x0A}, 12, 0x14,
     0x402425u, {0x80, 0x3E, 0x20, 0x74, 0x15, 0x8D, 0x9B, 0x00, 0x00, 0x00, 0x00, 0x3B, 0x74, 0x24, 0x30}, 15,
     0x40243Fu},
    {0x409E4Du, {0x3B, 0xC8, 0x89, 0x7C, 0x24, 0x18, 0x89, 0x6C, 0x24, 0x14, 0x7D, 0x0A}, 12, 0x18,
     0x402686u, {0x80, 0x3E, 0x20, 0x74, 0x16, 0xEB, 0x03, 0x8D, 0x49, 0x00, 0x3B, 0x74, 0x24, 0x30}, 14,
     0x4026A1u},
    {0x40A11Du, {0x3B, 0xC8, 0x89, 0x7C, 0x24, 0x18, 0x89, 0x6C, 0x24, 0x14, 0x7D, 0x0A}, 12, 0x18,
     0x402636u, {0x80, 0x3E, 0x20, 0x74, 0x16, 0xEB, 0x03, 0x8D, 0x49, 0x00, 0x3B, 0x74, 0x24, 0x30}, 14,
     0x402651u},
};

static unsigned int g_justify_back;   /* the instruction after the 6 bytes replaced */
static unsigned int g_linefit_loop;   /* the stock back-off loop (the site + 5) */
static unsigned int g_linefit_end;
static int g_installed;

/* The justified paragraph, at `cmp ecx, eax` (ecx = how far the line runs past the box, eax = the index of its last
   word): the replaced `mov [esp+N], edi`, then the flags the following `jge` reads -- the stock compare, or, for a
   line of one word (eax 0), "less" so the word is kept. */
__declspec(naked) static void lw_justify_14(void) {
    __asm {
        mov dword ptr [esp + 0x14], edi
        test eax, eax
        jz one_word
        cmp ecx, eax
        jmp dword ptr [g_justify_back]
    one_word:
        cmp eax, 1
        jmp dword ptr [g_justify_back]
    }
}

__declspec(naked) static void lw_justify_18(void) {
    __asm {
        mov dword ptr [esp + 0x18], edi
        test eax, eax
        jz one_word
        cmp ecx, eax
        jmp dword ptr [g_justify_back]
    one_word:
        cmp eax, 1
        jmp dword ptr [g_justify_back]
    }
}

/* The line fit, where a line too wide (or at its letter limit) starts backing off: esi = the out buffer at the last
   letter written, edi = the source past it, ebx = the letters written, [esp+0x30] = the buffer's start, [esp+0x34]
   = the letter limit. */
__declspec(naked) static void lw_linefit(void) {
    __asm {
        cmp byte ptr [esi], 0x20
        je to_end
        push eax
        mov eax, esi
    scan:
        cmp eax, dword ptr [esp + 4 + 0x30]
        je no_space
        dec eax
        cmp byte ptr [eax], 0x20
        jne scan
        pop eax
        jmp dword ptr [g_linefit_loop]      /* a space: the stock back-off */
    no_space:
        pop eax
        cmp ebx, dword ptr [esp + 0x34]
        jl keep
        dec edi                             /* at the letter limit: the last letter starts the next line */
        jmp dword ptr [g_linefit_end]
    keep:
        inc esi                             /* the letter that ran past the width stays */
    copy:
        mov eax, dword ptr [esp + 0x34]
        dec eax
        cmp ebx, eax
        jge to_end
        mov al, byte ptr [edi]
        test al, al
        jz to_end
        cmp al, 0x20
        je to_end
        cmp al, 0x0A
        je to_end
        mov byte ptr [esi], al
        inc esi
        inc edi
        inc ebx
        jmp copy
    to_end:
        jmp dword ptr [g_linefit_end]
    }
}

/* 1 when the sites went in, 0 when they did not (or this game has none). */
__declspec(dllexport) int __stdcall VvfpLongWordsInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[2];
    const lw_game *g;
    const unsigned char *module;
    int count = 0;
    (void)shipped;
    if (g_installed || game < 2 || game > 5) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != LW_GAME_BASE) {
        return;
    }
    g = &LW_GAMES[game];
    if (!vvfp_site_holds(g->linefit_site, g->linefit_stock, g->linefit_check)) {
        return;
    }
    if (g->justify_site != 0) {
        if (!vvfp_site_holds(g->justify_site, g->justify_stock, g->justify_check)) {
            return;
        }
        g_justify_back = g->justify_site + 6u;
        vvfp_site_branch(&w[count++], g->justify_site, 6, g->justify_stock, 0xE9,
                         g->justify_count_at == 0x14 ? (const void *)lw_justify_14 : (const void *)lw_justify_18);
    }
    g_linefit_loop = g->linefit_site + 5u;
    g_linefit_end = g->linefit_end;
    vvfp_site_branch(&w[count++], g->linefit_site, 5, g->linefit_stock, 0xE9, (const void *)lw_linefit);
    if (vvfp_install_sites(w, count)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
