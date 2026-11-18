/* VVFP VV4 Harvest Caption -- "Cutting Tool Harvest Says So", The Tree of Life.

   THE OWNER (2026-11-17): a villager harvesting blackberries WITH A CUTTING TOOL should say so.

   THE STOCK GAME.  Two blackberry actions share one caption, text 0x280 "Harvesting blackberries": picking
   (action 99, 0x451C30, a villager dropped on the bush) and the harvest with a cutting tool (action 0xBE,
   0x451CE0, a villager dropped on map area 0x31 while the tribe has a cutting tool, 0x46E7E0).  Each copies the
   text into the villager's caption (+0x1CE4, at most 0x27 letters, 0x4724E0) when it starts; the harvest's queue
   sets no other caption.  The text table cannot tell them apart, so the harvest's own copy is changed here:

     0x451CF6  9  the harvest's push 0x27 / push eax (the looked-up 0x280) / lea eax, [esi+0x1CE4]

   jumps to this companion, which pushes its own caption instead of the looked-up one and goes on at 0x451CFF
   (push eax / call 0x4724E0).  "Harvesting berries with a cutting tool" (38 letters: the caption field takes 39,
   so the owner's "Harvesting blackberries with a cutting tool", 43, would be cut), in the player's language
   through VVFP Translations.dll (row vvfp.harvest_caption/vvfp_vv4_harvest_caption.caption.s0).  Picking, and
   every other caption, is the game's own.  Checked stock first, written all or none; no debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"

#define HC_GAME 4
#define CAPTION_SITE 0x451CF6u
#define CAPTION_ON 0x451CFFu

static const unsigned char CAPTION_STOCK[9] = { 0x6A, 0x27, 0x50, 0x8D, 0x86, 0xE4, 0x1C, 0x00, 0x00 };
/* The next instructions the stub returns to: push eax / call 0x4724E0 (the copy). */
static const unsigned char CAPTION_ON_STOCK[5] = { 0x50, 0xE8, 0xDB, 0x07, 0x02 };
/* The harvest's own look-up just before: push 0x280 (eSayHarvestingBlackberries). */
static const unsigned char LOOKUP_STOCK[5] = { 0x68, 0x80, 0x02, 0x00, 0x00 };
#define LOOKUP_SITE 0x451CE6u

static int g_installed;

/* The caption, translated when a translation is chosen (or `stock`, the looked-up text, on a fault). */
static const char *__cdecl caption(const char *stock) {
    const char *text = stock;
    __try {
        text = vvfp_tr("vvfp.harvest_caption/vvfp_vv4_harvest_caption.caption.s0",
                       "Harvesting berries with a cutting tool", 39);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        text = stock;
    }
    return text;
}

/* At CAPTION_SITE (eax the looked-up text, esi the villager). */
__declspec(naked) static void caption_stub(void) {
    __asm {
        pushad
        push eax
        call caption
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

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpHarvestCaptionInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[1];
    (void)shipped;
    if (g_installed || game != HC_GAME || !vvfp_site_holds(CAPTION_ON, CAPTION_ON_STOCK, sizeof CAPTION_ON_STOCK)
        || !vvfp_site_holds(LOOKUP_SITE, LOOKUP_STOCK, sizeof LOOKUP_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], CAPTION_SITE, sizeof CAPTION_STOCK, CAPTION_STOCK, 0xE9, (const void *)caption_stub);
    if (vvfp_install_sites(w, 1)) {
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
