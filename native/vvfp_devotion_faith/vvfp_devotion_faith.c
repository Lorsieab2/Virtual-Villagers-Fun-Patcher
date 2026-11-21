/* VVFP Devotion Faith -- "Practicing Devotion Builds Faith and Divine Energy", New Believers.

   The owner (2026-11-21): "practicing Devotion skill should give a 1-point increase in Faith. like a small chance
   which adds up over time."  And: "people practicing devotion should also give 1 point in Divine Energy too. same
   mechanics".

   THE STOCK GAME.  A villager practises a skill in the game's one skill check 0x46B270 (thiscall on the villager,
   its record at +0x1B88; arguments: the skill 0-5 and a byte).  Skill 5 is Devotion.  It passes when rand(100) is at
   most Devotion + 33 (66 for one who likes learning, 16 for one who dislikes it; Learning 2 or 3 adds 15 or 30); a
   pass raises Devotion by (70 - Devotion) / 18 plus the Spirituality level (+1 only on 51% x (100 - Devotion)% once
   that sum is 0); a failure at Devotion 0 still gains a little.  The Devotion check is reached from:
     * Honoring (behaviour 0xA0, 0x45CB70; the Devotion job once the statue is at its first stage or solved, and the
       Retired Chief): half the sessions go to the statue's spot, and those queue the check 1 time in 4 (rand(100) <
       25, 0x45CC92) as step 10, run by the step runner 0x473B30 (0x473C69) live and by the catch-up's instant
       runner 0x46E020 while catching up;
     * preaching: the sermon's end 0x468DA0 checks the preacher's Devotion (0x468E9A).
   Heathens never use the work system and are never dropped to preach, so only believers practise Devotion.

   WHAT THIS COMPANION DOES.  The skill check's entry (5 bytes: sub esp, 0Ch / push ebx / push ebp) jumps to the
   companion.  For skill 5, a believer (+0x1CEC 0) who is not one of the six special roles (+0x1CFC 12-17: the
   Heathen Doctor, the Heathen Chief -- and the Retired Chief, who keeps that role --, the three Masters, the Heathen
   Mommy; the Earthquake God Power skips the same six) gets two separate rolls, each made with the game's own
   rand(n) 0x403660 (1 in 10 each; the owner, 2026-11-21: "1 in 10 for both is good"):
     * rand(10) < 1: Faith (+0x1CF0, a whole number) +1, a plain write, never above the game's maximum 100 (the
       setter 0x467F90's clamp); a believer already at 100 is left alone;
     * rand(10) < 1: Divine Energy +1 through the game's own adder 0x424F80 on the village manager (read from the
       word 0x4DACE0 its getter 0x425950 keeps it in), which keeps it at most the village's cap (+0x17D60).
   Then the stock check runs exactly as before (the five bytes re-run, back at 0x46B275), so the skill, its odds and
   everything after it are the game's own.  Every other skill, every Heathen and the six special roles go straight
   on with no roll made.  1 in 10: rand() % 10 < 1 comes 3,277 times in 32,768 (10.00%).

   HOW.  The site is spliced at run time, after its stock bytes are checked (native/shared/install_sites.h); no
   executable byte is patched.  The rolls are made with every register and flag saved, under structured exception
   handling (a fault: nothing more happens; the stock check still runs).  Started by VVFP More Companions.dll (the
   third word, native/shared/startup_companions_3.h).  Nothing is written but the villager's Faith and the village's
   Divine Energy; no file, no text.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define DF_GAME 5

#define DF_SITE 0x46B270u               /* the skill check's entry */
#define DF_BACK 0x46B275u               /* after the five bytes re-run here */
#define DF_RAND 0x403660u               /* the game's rand(n): rand() % n */
/* The village manager: the word its getter 0x425950 keeps it in, read, never the getter (it can build the object;
   the owner, 2026-11-18: no companion calls it -- tests/test_shipped_companions_never_build_the_game_object.py). */
#define DF_MANAGER_WORD 0x4DACE0u
#define DF_ADD_ENERGY 0x424F80u         /* the manager's Divine Energy adder (kept 0 to the cap) */
#define DF_DEVOTION 5                   /* the skill: Farming, Parenting, Healing, Research, Building, Devotion */
#define DF_RECORD 0x1B88                /* the villager's record */
#define DF_FACTION 0x1CEC               /* 0 a believer */
#define DF_FAITH 0x1CF0
#define DF_FAITH_MAX 100                /* the setter 0x467F90's clamp */
#define DF_ROLE 0x1CFC
#define DF_ROLE_FIRST_SPECIAL 12
#define DF_ROLE_LAST_SPECIAL 17
#define DF_ROLL 10                      /* rand(10) < 1: 1 in 10 (the owner, 2026-11-21) */

static const unsigned char SITE_STOCK[5] = {
    0x83, 0xEC, 0x0C,                   /* sub esp, 0Ch */
    0x53,                               /* push ebx */
    0x55                                /* push ebp */
};

typedef int (__cdecl *df_rand_fn)(int n);
typedef void (__fastcall *df_add_fn)(void *manager, void *unused, int amount);

static int g_installed;
static unsigned int g_steps;            /* Devotion practice steps seen this session (the tests read them) */
static unsigned int g_faith;            /* Faith points given this session */
static unsigned int g_energy;           /* Divine Energy rolls won this session (before the cap) */

static void df_practice(const unsigned char *villager) {
    unsigned char *record = *(unsigned char *const *)(villager + DF_RECORD);
    int role, *faith;
    if (record == NULL || record[DF_FACTION] != 0) {
        return;                         /* a Heathen: never practises, never touched */
    }
    role = *(const int *)(record + DF_ROLE);
    if (role >= DF_ROLE_FIRST_SPECIAL && role <= DF_ROLE_LAST_SPECIAL) {
        return;                         /* a puzzle Heathen's role (the Retired Chief keeps the Chief's) */
    }
    ++g_steps;
    if (((df_rand_fn)DF_RAND)(DF_ROLL) < 1) {
        faith = (int *)(record + DF_FAITH);
        if (*faith < DF_FAITH_MAX) {
            *faith += 1;
            ++g_faith;
        }
    }
    if (((df_rand_fn)DF_RAND)(DF_ROLL) < 1) {
        void *manager = *(void *const *)(UINT_PTR)DF_MANAGER_WORD;
        if (manager != NULL) {          /* always there in play: a skill check runs only on the island */
            ((df_add_fn)DF_ADD_ENERGY)(manager, NULL, 1);
            ++g_energy;
        }
    }
}

static void __stdcall df_step(const unsigned char *villager) {
    __try {
        df_practice(villager);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of the entry: [esp] the return, [esp + 4] the skill; ecx the villager. */
__declspec(naked) static void df_stub(void) {
    __asm {
        cmp dword ptr [esp + 4], DF_DEVOTION
        jne stock
        pushfd
        pushad
        push ecx
        call df_step
        popad
        popfd
    stock:
        sub esp, 0Ch
        push ebx
        push ebp
        push DF_BACK
        ret
    }
}

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpDevotionFaithInstalled(void) {
    return g_installed;
}

/* Devotion practice steps seen, Faith points given and Divine Energy rolls won this session (the tests). */
unsigned int __stdcall VvfpDevotionFaithSteps(void) {
    return g_steps;
}

unsigned int __stdcall VvfpDevotionFaithGiven(void) {
    return g_faith;
}

unsigned int __stdcall VvfpDevotionEnergyGiven(void) {
    return g_energy;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site;
    (void)shipped;
    if (g_installed || game != DF_GAME) {
        return;
    }
    vvfp_site_branch(&site, DF_SITE, (int)sizeof SITE_STOCK, SITE_STOCK, 0xE9, (const void *)df_stub);
    if (vvfp_install_sites(&site, 1)) {
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
