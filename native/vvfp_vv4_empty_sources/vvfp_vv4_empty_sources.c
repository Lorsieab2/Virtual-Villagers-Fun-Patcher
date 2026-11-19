/* VVFP VV4 Empty Sources -- Fix Vanilla Bugs (The Tree of Life): no tool harvest from an empty bush.

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

   THE GRAND FEAST (the owner, 2026-11-19: "for the grand stew berries and fruit harvested by cutting tools or
   sacks should count").  The stock game takes blackberries to the stew only as picked berries: a villager dropped
   on the bush while the pot wants berries (0x46F8AC: 0x42DDE0, the feast brewing and its berries flag pot+0xB21
   still 0) gets the stew action 0x90 with item 0 instead of the picking trip, and the pot's item listener 0x42EA30
   sets the flag when it is put down at the pot (table 0x42EB4C: item 0 -> case 0, 0x42EADE).  The fruit trip does
   the same at its end (0x4349A3: 0x42DDA0, then text 0x241 and the stew action 0x90 with item 0x37 queued by
   0x469F30 in place of the food bin).  The cutting-tool harvest (action 0xBE, 0x451CE0) always carries its
   berries (item 0x3E) to the food bin; item 0x3E is not even offered to the pot (the item registry 0x4CC0A0 gives
   the pot, 0x4D76DC, only items 0x1F..0x25, 6, 0, 0x76..0x78, 0x38 and 0x37: 0x413360).  So, the same way:
     0x451DB2  9  the harvest's carry of its berries (push 0x3E / mov ecx,esi / call 0x4697C0), after its three cuts
                  and its Farming check, at the bushes: while the pot wants berries (0x42DDE0, asked as the bush
                  asks it) the stew action 0x90 with item 0 -- the bush's own stew trip, picked berries -- is queued
                  by 0x469F30 as the fruit trip queues its stew action, and the harvest ends there (0x451DF3: the
                  queue started).  No food bin, no job event 14: no food is paid and no berries are taken from the
                  bush, as on the bush's own stew trip.  Otherwise the stock carry and on (0x451DBB), unchanged.
   A harvest that fails its Farming check still ends before the carry, as in the stock game.  The cloth sack's own
   stew trip is "VVFP VV4 Cloth Sacks.dll"'s.
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

/* The Grand Feast. */
#define POT 0x4D76D8u
#define POT_WANTS_BERRIES 0x42DDE0u  /* thiscall: the feast brewing and its berries flag not yet set */
#define QUEUE_ACTION 0x469F30u       /* thiscall(villager; action, block): an action step */
#define CARRY 0x4697C0u              /* thiscall(villager; item): the carry step */
#define STEW_ACTION 0x90
#define ITEM_HARVEST 0x3E
#define ITEM_BERRIES 0               /* picked berries: the pot's feast berries (0x42EB4C -> 0x42EADE) */
#define CARRY_SITE 0x451DB2u
#define CARRY_ON 0x451DBBu
#define HARVEST_END 0x451DF3u        /* mov ecx,esi / pop esi / jmp 0x46A030 */
#define SITES 2
static const unsigned char CARRY_STOCK[9] = { 0x6A, 0x3E, 0x8B, 0xCE, 0xE8, 0x05, 0x7A, 0x01, 0x00 };
static const unsigned char HARVEST_END_STOCK[6] = { 0x8B, 0xCE, 0x5E, 0xE9, 0x35, 0x82 };

static int g_installed;
static const unsigned int g_use_up = USE_UP;
static const unsigned int g_tool_on = TOOL_ON;
static const unsigned int g_drop_done = DROP_DONE;
static const unsigned int g_carry = CARRY;
static const unsigned int g_carry_on = CARRY_ON;
static const unsigned int g_harvest_end = HARVEST_END;

typedef unsigned char *(__cdecl *game_get_fn)(void);
typedef char (__fastcall *do_action_fn)(void *self, void *unused, int action, void *block);
typedef char (__fastcall *wants_fn)(void *self, void *unused);
typedef void (__fastcall *queue_action_fn)(void *self, void *unused, int action, void *block);

/* The harvest is about to carry its berries: 1 when the pot wants berries and the stew action was queued instead. */
static int __cdecl on_carry(unsigned char *villager) {
    int stew = 0;
    __try {
        if (villager != NULL && ((wants_fn)(UINT_PTR)POT_WANTS_BERRIES)((void *)(UINT_PTR)POT, NULL) != 0) {
            int block[8];
            memset(block, 0, sizeof block);
            block[0] = ITEM_BERRIES;
            ((queue_action_fn)(UINT_PTR)QUEUE_ACTION)(villager, NULL, STEW_ACTION, block);
            stew = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        stew = 0;
    }
    return stew;
}

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

/* At CARRY_SITE (esi the villager): the stew action queued and the harvest's end, or the stock carry and on. */
__declspec(naked) static void carry_stub(void) {
    __asm {
        pushad
        push esi
        call on_carry
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jnz stew
        push ITEM_HARVEST
        mov ecx, esi
        call dword ptr [g_carry]
        jmp dword ptr [g_carry_on]
    stew:
        jmp dword ptr [g_harvest_end]
    }
}

/* 1 when the sites are installed (for the tests' emulation), else 0. */
int __stdcall VvfpEmptySourcesInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[SITES];
    (void)shipped;
    if (g_installed || game != ES_GAME || !vvfp_site_holds(TOOL_ON, TOOL_ON_STOCK, sizeof TOOL_ON_STOCK)
        || !vvfp_site_holds(DROP_DONE, DROP_DONE_STOCK, sizeof DROP_DONE_STOCK)
        || !vvfp_site_holds(HARVEST_END, HARVEST_END_STOCK, sizeof HARVEST_END_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], TOOL_SITE, sizeof TOOL_STOCK, TOOL_STOCK, 0xE9, (const void *)tool_stub);
    vvfp_site_branch(&w[1], CARRY_SITE, sizeof CARRY_STOCK, CARRY_STOCK, 0xE9, (const void *)carry_stub);
    if (vvfp_install_sites(w, SITES)) {
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
