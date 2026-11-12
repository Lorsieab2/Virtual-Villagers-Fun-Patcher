/* VVFP Collectibles Stay Collected -- "Picked Up Collectibles Stay Collected When Dropped" in A New Home and The
   Lost Children (vv1_collectibles_stay_collected, vv2_collectibles_stay_collected).  The Secret City, The Tree of
   Life and New Believers do the same with plain byte flips in the executable (their rows), not with this DLL.

   WHAT (the owner, 2026-11-12).  A mushroom or collectible a villager has picked up is credited -- the food and
   Mushrooms Found, or the collection piece (tech points for a piece already found) with its tips and messages --
   exactly once, even when the villager is picked up and dropped elsewhere, or stops, before reaching the food
   store / the end of the trip.  The owner (2026-11-12): new code goes in a companion, not into the executable.

   HOW.  After every site's stock bytes (and the stock code around them that the detours rely on) are checked
   (native/shared/install_sites.h: all of them, or none):

     A New Home -- credit at the pick, never at the food store:
       * 0x43A266, the mushroom pick's own epilogue (callback 42 of the job-step dispatcher 0x43A230; only the
         pick reaches these 7 bytes: no branch and no table entry points into them).  `pop edi / pop ebp /
         pop ebx / pop esi / ret 8` becomes `jmp vv1_pick_tail` + 2 nops.  vv1_pick_tail calls the dispatcher
         itself with the same slot and callback 32 + the mushroom's kind ([manager + 0xACB0], the manager
         [esi + 0x3E010] the pick has just written), exactly as the job's own end-of-trip step would (the job
         0x444500 queues callback 0x20 / 0x21 by that kind; Super-Secret Golden Mushroom's kind 2 reaches its own
         callback 34 the same way), then runs the stock epilogue.
       * 0x444670, the job's `call 0x4399F0` that queues that end-of-trip award step, becomes `call
         vv1_no_award_step` (`ret 0x1C`: its seven pushed arguments are dropped, the step is never queued).  Nothing
         after it reads eax.

     The Lost Children -- the award step queued right after the carry step:
       * 0x45BE4D (the mushroom job 0x45BCA0) and 0x45C09A (the collectible job 0x45BF10): the `call 0x449B70` that
         appends the award step (step 17, callback 39 / 40 / 41) becomes `call vv2_award_step`.  The stub makes the
         very same call (the game builds the entry, so whatever callback the job computed -- Golden Mushroom's too
         -- is the one queued), then moves that new last entry of the child's queue (record + 0x4C, 49 entries of
         24 bytes; the job emptied the queue first, 0x4492A0) to right after the last carry step (step 15) before
         it.  The steps in between keep their order.  This is the order the patch's earlier in-place reorder
         produced.  A queue the game left full (the entry was not added) is left as it is.

   SAFETY.  Runs on the game's own thread inside the game's own job code; nothing is written to a save, a villager
   record (beyond the job's own queue order) or a file; no text is shown.  The stock award code does the crediting
   in both games.  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define CS_GAME_BASE 0x400000u

/* A New Home. */
#define VV1_DISPATCH 0x43A230u           /* the job-step callback dispatcher: thiscall (slot, callback), ret 8 */
#define VV1_PICK_CASE 0x43A24Bu          /* callback 42: the pick (mov eax,[esi+0x3E010] ... call 0x416380) */
#define VV1_PICK_TAIL 0x43A266u          /* its epilogue: pop edi / pop ebp / pop ebx / pop esi / ret 8 */
#define VV1_AWARD_CALL 0x444670u         /* the job's call 0x4399F0 queueing the end-of-trip award step */

/* The Lost Children. */
#define VV2_QUEUE_PUSH 0x449B70u         /* thiscall (slot, step, a, b, c, mode, param), ret 0x1C */
#define VV2_MUSHROOM_AWARD 0x45BE4Du     /* the mushroom job's call queueing step 17, callback 39 / 40 */
#define VV2_COLLECTIBLE_AWARD 0x45C09Au  /* the collectible job's call queueing step 17, callback 41 */
#define VV2_RECORD 0xE48Cu               /* a villager record */
#define VV2_QUEUE 0x4Cu                  /* its step queue */
#define VV2_QUEUE_LENGTH 0x31            /* entries (the push's own limit, 0x449C29) */
#define VV2_STEP_CARRY 0x0Fu
#define VV2_STEP_CALLBACK 0x11u

/* The stock bytes each detour relies on: written sites, and code only checked. */
static const unsigned char VV1_PICK_CASE_STOCK[27] = {
    0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00,                          /* mov eax, [esi+0x3E010]      */
    0xC7, 0x80, 0xAC, 0xAC, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00,  /* mov dword [eax+0xACAC], 1   */
    0x8B, 0x8E, 0x24, 0xE0, 0x03, 0x00,                          /* mov ecx, [esi+0x3E024]      */
    0xE8, 0x1A, 0xC1, 0xFD, 0xFF                                 /* call 0x416380               */
};
static const unsigned char VV1_PICK_TAIL_STOCK[7] = { 0x5F, 0x5D, 0x5B, 0x5E, 0xC2, 0x08, 0x00 };
static const unsigned char VV1_AWARD_CALL_STOCK[5] = { 0xE8, 0x7B, 0x53, 0xFF, 0xFF };        /* call 0x4399F0 */
static const unsigned char VV2_MUSHROOM_AWARD_STOCK[5] = { 0xE8, 0x1E, 0xDD, 0xFE, 0xFF };    /* call 0x449B70 */
static const unsigned char VV2_COLLECTIBLE_AWARD_STOCK[5] = { 0xE8, 0xD1, 0xDA, 0xFE, 0xFF }; /* call 0x449B70 */
/* The step number pushed just before each VV2 site (push 0x11 / push edi [/ mov ecx, esi]). */
static const unsigned char VV2_MUSHROOM_AWARD_PUSHES[3] = { 0x6A, 0x11, 0x57 };
static const unsigned char VV2_COLLECTIBLE_AWARD_PUSHES[5] = { 0x6A, 0x11, 0x57, 0x8B, 0xCE };

static int g_installed;

/* ---- A New Home ------------------------------------------------------------------------------------------- */

/* Reached by the pick's epilogue: esi the job array (this), the stack as the epilogue found it -- [esp] edi,
   [esp+4] ebp, [esp+8] ebx, [esp+0xC] esi, [esp+0x10] the dispatcher's return, [esp+0x14] the slot. */
__declspec(naked) static void vv1_pick_tail(void) {
    __asm {
        mov eax, dword ptr [esi + 0x3E010]
        mov eax, dword ptr [eax + 0xACB0]
        add eax, 0x20
        push eax                            /* callback 32 + kind */
        push dword ptr [esp + 0x18]         /* the slot */
        mov ecx, esi
        mov eax, VV1_DISPATCH
        call eax
        pop edi
        pop ebp
        pop ebx
        pop esi
        ret 8
    }
}

/* Takes the place of the job's end-of-trip `call 0x4399F0`: the step is not queued, its arguments are dropped. */
__declspec(naked) static void vv1_no_award_step(void) {
    __asm {
        ret 0x1C
    }
}

/* ---- The Lost Children ------------------------------------------------------------------------------------ */

typedef struct {
    unsigned int step, a, b, c, zero, param;
} vv2_entry;

/* The award step the game just appended to the child's queue goes right after the last carry step before it. */
static void __cdecl vv2_move_after_carry(unsigned int self, unsigned int slot, unsigned int param) {
    __try {
        vv2_entry *q = (vv2_entry *)(UINT_PTR)(self + slot * VV2_RECORD + VV2_QUEUE);
        vv2_entry award;
        int last, carry, i;
        for (i = 0; i < VV2_QUEUE_LENGTH && q[i].step != 0; ++i) {
        }
        last = i - 1;
        if (last < 1 || q[last].step != VV2_STEP_CALLBACK || q[last].param != param) {
            return;                         /* the game did not add it (a full queue): left as it is */
        }
        for (carry = last - 1; carry >= 0 && q[carry].step != VV2_STEP_CARRY; --carry) {
        }
        if (carry < 0 || carry + 1 == last) {
            return;
        }
        award = q[last];
        for (i = last; i > carry + 1; --i) {
            q[i] = q[i - 1];
        }
        q[carry + 1] = award;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* Takes the place of the job's `call 0x449B70` for the award step: ecx the villager manager, [esp+4..0x1C] the
   seven arguments (slot, step, a, b, c, mode, param). */
__declspec(naked) static void vv2_award_step(void) {
    __asm {
        push ecx
        push dword ptr [esp + 0x20]         /* param */
        push dword ptr [esp + 0x20]         /* mode */
        push dword ptr [esp + 0x20]
        push dword ptr [esp + 0x20]
        push dword ptr [esp + 0x20]
        push dword ptr [esp + 0x20]         /* step */
        push dword ptr [esp + 0x20]         /* slot */
        mov eax, VV2_QUEUE_PUSH
        call eax                            /* the game's own push (ecx unchanged since the job set it) */
        mov eax, dword ptr [esp]            /* the manager */
        push dword ptr [esp + 0x20]         /* param */
        push dword ptr [esp + 0xC]          /* slot */
        push eax
        call vv2_move_after_carry
        add esp, 0xC
        pop ecx
        ret 0x1C
    }
}

/* ---- Install ---------------------------------------------------------------------------------------------- */

/* 1 when every site of the game is installed (for the tests' emulation), else 0. */
int __stdcall VvfpCollectiblesStayCollectedInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[2];
    const unsigned char *module;
    int count = 0;
    (void)shipped;
    if (g_installed) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != CS_GAME_BASE) {
        return;                             /* every site is a VA of the games' fixed base */
    }
    if (game == 1) {
        if (!vvfp_site_holds(VV1_PICK_CASE, VV1_PICK_CASE_STOCK, sizeof VV1_PICK_CASE_STOCK)) {
            return;
        }
        vvfp_site_branch(&w[count++], VV1_PICK_TAIL, sizeof VV1_PICK_TAIL_STOCK, VV1_PICK_TAIL_STOCK, 0xE9,
                         (const void *)vv1_pick_tail);
        vvfp_site_branch(&w[count++], VV1_AWARD_CALL, sizeof VV1_AWARD_CALL_STOCK, VV1_AWARD_CALL_STOCK, 0xE8,
                         (const void *)vv1_no_award_step);
    } else if (game == 2) {
        if (!vvfp_site_holds(VV2_MUSHROOM_AWARD - sizeof VV2_MUSHROOM_AWARD_PUSHES, VV2_MUSHROOM_AWARD_PUSHES,
                             sizeof VV2_MUSHROOM_AWARD_PUSHES)
            || !vvfp_site_holds(VV2_COLLECTIBLE_AWARD - sizeof VV2_COLLECTIBLE_AWARD_PUSHES,
                                VV2_COLLECTIBLE_AWARD_PUSHES, sizeof VV2_COLLECTIBLE_AWARD_PUSHES)) {
            return;
        }
        vvfp_site_branch(&w[count++], VV2_MUSHROOM_AWARD, sizeof VV2_MUSHROOM_AWARD_STOCK, VV2_MUSHROOM_AWARD_STOCK,
                         0xE8, (const void *)vv2_award_step);
        vvfp_site_branch(&w[count++], VV2_COLLECTIBLE_AWARD, sizeof VV2_COLLECTIBLE_AWARD_STOCK,
                         VV2_COLLECTIBLE_AWARD_STOCK, 0xE8, (const void *)vv2_award_step);
    } else {
        return;
    }
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
