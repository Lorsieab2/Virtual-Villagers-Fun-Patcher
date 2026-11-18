/* VVFP VV4 Empty Sources -- "No Tool Harvest from Empty Sources", The Tree of Life.

   THE OWNER (2026-11-18): a cutting tool or a cloth sack is never used up on a food source that has no food left.

   THE STOCK GAME.  A villager dropped where the tribe's cutting tools harvest the blackberries (map area 0x31, the
   handler 0x46E7E0) with a tool on hand uses one tool at once (0x46E86F: push esi / push 1 / call 0x4369F0 on the
   tools' object 0x4D8614) and starts the harvest (action 0xBE), whatever the bush holds: with 0 berries the trip
   brings 0 food (job event 14: n = the berries, at most 30) and the tool is gone.  Picking at an empty bush is
   refused by the game itself (the bush's drop 0x46F881: action 0x3F with text 0xA7, "There is not enough to
   harvest.").

   WHAT THIS CHANGES.
     0x46E86F  8  the harvest's tool use: with 0 berries ([game + 0x170F8]) the villager gets the empty bush's own
                  refusal (action 0x3F, text 0xA7) and the drop ends there (0x46E89B: al = 1, ret), no tool used;
                  with 1 or more the stock push esi / push 1 / call 0x4369F0 and on (0x46E877), unchanged.
   The cloth sack ("VVFP VV4 Cloth Sacks.dll", Cloth Sacks for Yellow Fruit) asks whether this companion is loaded
   (GetModuleHandleW) and, with it, refuses the same way when "Yellow Fruit Trees are No Longer Unlimited" says the
   tree holds 0 fruit, before any cloth is used.  Without Cloth Sacks this companion does the cutting tool alone.
   Checked stock first, written all or none; no debug output. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define ES_GAME 4
#define GAME_GET 0x41FE70u
#define G_BERRIES 0x170F8u
#define DO_ACTION 0x45DEC0u
#define REFUSE_ACTION 0x3F
#define REFUSE_TEXT 0xA7             /* eSayNotEnoughToHarvest, the empty bush's own */
#define USE_UP 0x4369F0u
#define TOOL_SITE 0x46E86Fu
#define TOOL_ON 0x46E877u
#define DROP_DONE 0x46E89Bu

static const unsigned char TOOL_STOCK[8] = { 0x56, 0x6A, 0x01, 0xE8, 0x79, 0x81, 0xFC, 0xFF };   /* call 0x4369F0 */
static const unsigned char TOOL_ON_STOCK[4] = { 0x8B, 0x74, 0x24, 0x14 };
static const unsigned char DROP_DONE_STOCK[6] = { 0xB0, 0x01, 0x83, 0xC4, 0x08, 0xC3 };

static int g_installed;
static const unsigned int g_use_up = USE_UP;
static const unsigned int g_tool_on = TOOL_ON;
static const unsigned int g_drop_done = DROP_DONE;

typedef unsigned char *(__cdecl *game_get_fn)(void);
typedef char (__fastcall *do_action_fn)(void *self, void *unused, int action, void *block);

/* The harvest is about to use a tool: 1 when the bush is empty and the villager was refused instead. */
static int __cdecl on_harvest(unsigned char *villager) {
    int refused = 0;
    __try {
        const unsigned char *game = ((game_get_fn)(UINT_PTR)GAME_GET)();
        if (game != NULL && villager != NULL && *(const int *)(game + G_BERRIES) <= 0) {
            int block[8];
            memset(block, 0, sizeof block);
            block[0] = REFUSE_TEXT;
            block[1] = -1;
            ((do_action_fn)(UINT_PTR)DO_ACTION)(villager, NULL, REFUSE_ACTION, block);
            refused = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        refused = 0;
    }
    return refused;
}

/* At TOOL_SITE (ecx the tools' object, [esp+0x10] the villager). */
__declspec(naked) static void tool_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x30]
        call on_harvest
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jnz refused
        push esi
        push 1
        call dword ptr [g_use_up]
        jmp dword ptr [g_tool_on]
    refused:
        jmp dword ptr [g_drop_done]
    }
}

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpEmptySourcesInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[1];
    (void)shipped;
    if (g_installed || game != ES_GAME || !vvfp_site_holds(TOOL_ON, TOOL_ON_STOCK, sizeof TOOL_ON_STOCK)
        || !vvfp_site_holds(DROP_DONE, DROP_DONE_STOCK, sizeof DROP_DONE_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], TOOL_SITE, sizeof TOOL_STOCK, TOOL_STOCK, 0xE9, (const void *)tool_stub);
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
