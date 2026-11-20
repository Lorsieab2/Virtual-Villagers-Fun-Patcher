/* VVFP VV4 Supply Cap -- "Up to 99 Cutting Tools/Soap/Cloth", The Tree of Life.

   THE OWNER (2026-11-17): storage for cutting tools, soap and cloth bolts goes from the stock cap of 6 up to 99;
   the stacked pictures look exactly as with 6 when more are stored.

   THE STOCK GAME (exact-build disassembly):
     * cutting tools: object 0x4D8614, count dword 0x4D8618.  Made 3 at a time (its produce, vtable slot 10,
       0x431400: count += 3 at 0x43140F), then capped: `mov eax,6 / cmp [esi+4],eax / jle / mov [esi+4],eax` at
       0x43142F.  Drawn as one sprite 0x18 per tool by its draw 0x431480 (loop `add edi,1 / cmp edi,[ebp+4] / jl`
       at 0x4314C8: three to a row, the second row starting at the third).
     * cloth bolts: object 0x4D8AC8, count dword 0x4D8ACC.  Made 3 at a time (0x436890: += 3 at 0x4368C2), capped
       at 6 the same way at 0x4368E2.  Drawn by the Clothing Hut 0x430C80 as one cloth_bolt sprite per bolt (bound
       ebp = the count, loop start 0x430CA6).
     * both use the same use-up 0x4369F0 (count -= n, then `cmp eax,6 / jle / mov [ecx+4],6` at 0x436A09): above 6
       a single use would put the count back to 6.
     * soap: object 0x4D8D90, count dword 0x4D8D98: made 3 at a time (0x43A2DF) and NEVER capped in the stock game
       (its use-up 0x43A410 has no upper clamp, and its draw 0x43A330 shows at most 3 bars), so soap needs nothing.
     * every count is saved and loaded as one dword without a clamp (slot 4 0x436870 / slot 3 0x4313E0; soap
       0x43A2B0 / 0x43A290), so 99 saves and loads as it is.  The readers ("Cutting tools left: %d", "Cloth bolts
       available: %d", the drops' > 0 tests) are fine with 99; achievements count what was made, never the store.

   WHAT THIS CHANGES (all sites checked stock first, written all or none, native/shared/install_sites.h):
     0x431430  1  the tools' cap 6 -> 99 (the immediate of `mov eax, 6` at 0x43142F)
     0x4368E3  1  the cloth's cap 6 -> 99 (0x4368E2)
     0x436A0B  1  the use-up's clamp test 6 -> 99 (`cmp eax, 6`)
     0x436A11  1  the use-up's clamp value 6 -> 99 (`mov [ecx+4], 6`)
     0x4314C8  8  the tools' draw loop: a jump to tool_loop_stub, which draws while i < count AND i < 6
     0x430CA6 10  the Clothing Hut's bolts: a jump to hut_bolts_stub, which bounds the loop by min(count, 6)
   Production stays 3 at a time.  Nothing is written to the save beyond the game's own count.  A save holding
   more than 6 opened without this patch keeps its count until the first use clamps it to 6 (the stock rule).
   No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define SC_GAME 4
#define SC_CAP 99
#define SC_DRAWN 6                   /* the stacked pictures never show more than the stock 6 */

#define TOOL_CAP_SITE 0x43142Fu
#define CLOTH_CAP_SITE 0x4368E2u
#define USE_CLAMP_SITE 0x436A09u
#define TOOL_LOOP_SITE 0x4314C8u
#define TOOL_LOOP_BODY 0x431497u
#define TOOL_LOOP_END 0x4314D0u
#define HUT_BOLTS_SITE 0x430CA6u
#define HUT_BOLTS_LOOP 0x430CB0u
#define HUT_BOLTS_NONE 0x430CE6u
#define SITES 5

static const unsigned char TOOL_CAP_STOCK[13] = { 0xB8, 0x06, 0x00, 0x00, 0x00, 0x39, 0x46, 0x04, 0x7E, 0x03, 0x89,
                                                  0x46, 0x04 };
static const unsigned char TOOL_CAP_OURS[13] = { 0xB8, SC_CAP, 0x00, 0x00, 0x00, 0x39, 0x46, 0x04, 0x7E, 0x03, 0x89,
                                                 0x46, 0x04 };
static const unsigned char CLOTH_CAP_STOCK[13] = { 0xB8, 0x06, 0x00, 0x00, 0x00, 0x39, 0x46, 0x04, 0x7E, 0x2D, 0x89,
                                                   0x46, 0x04 };
static const unsigned char CLOTH_CAP_OURS[13] = { 0xB8, SC_CAP, 0x00, 0x00, 0x00, 0x39, 0x46, 0x04, 0x7E, 0x2D, 0x89,
                                                  0x46, 0x04 };
static const unsigned char USE_CLAMP_STOCK[12] = { 0x83, 0xF8, 0x06, 0x7E, 0x0A, 0xC7, 0x41, 0x04, 0x06, 0x00, 0x00,
                                                   0x00 };
static const unsigned char USE_CLAMP_OURS[12] = { 0x83, 0xF8, SC_CAP, 0x7E, 0x0A, 0xC7, 0x41, 0x04, SC_CAP, 0x00,
                                                  0x00, 0x00 };
static const unsigned char TOOL_LOOP_STOCK[8] = { 0x83, 0xC7, 0x01, 0x3B, 0x7D, 0x04, 0x7C, 0xC7 };
static const unsigned char HUT_BOLTS_STOCK[10] = { 0x33, 0xDB, 0x85, 0xED, 0x7E, 0x3A, 0x8D, 0x64, 0x24, 0x00 };
/* The code the stubs return to: the tools' loop body and end, the hut's loop and its end. */
static const unsigned char TOOL_BODY_STOCK[5] = { 0xE8, 0x54, 0xB8, 0x01, 0x00 };
static const unsigned char TOOL_END_STOCK[4] = { 0x5F, 0x5E, 0x5D, 0x5B };
static const unsigned char HUT_NONE_STOCK[4] = { 0x5F, 0x5B, 0x5E, 0x5D };

static int g_installed;
static const unsigned int g_tool_body = TOOL_LOOP_BODY;
static const unsigned int g_tool_end = TOOL_LOOP_END;
static const unsigned int g_hut_loop = HUT_BOLTS_LOOP;
static const unsigned int g_hut_none = HUT_BOLTS_NONE;

/* At TOOL_LOOP_SITE (edi the tool just drawn, ebp the object): the next while i < count and i < SC_DRAWN. */
__declspec(naked) static void tool_loop_stub(void) {
    __asm {
        add edi, 1
        cmp edi, dword ptr [ebp + 4]
        jge done
        cmp edi, SC_DRAWN
        jge done
        jmp dword ptr [g_tool_body]
    done:
        jmp dword ptr [g_tool_end]
    }
}

/* At HUT_BOLTS_SITE (ebp the cloth count, already > 0): the loop bounded by min(count, SC_DRAWN). */
__declspec(naked) static void hut_bolts_stub(void) {
    __asm {
        xor ebx, ebx
        cmp ebp, SC_DRAWN
        jle bounded
        mov ebp, SC_DRAWN
    bounded:
        test ebp, ebp
        jle none
        jmp dword ptr [g_hut_loop]
    none:
        jmp dword ptr [g_hut_none]
    }
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpSupplyCapInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[SITES + 1];
    (void)shipped;
    if (g_installed || game != SC_GAME
        || !vvfp_site_holds(TOOL_LOOP_BODY, TOOL_BODY_STOCK, sizeof TOOL_BODY_STOCK)
        || !vvfp_site_holds(TOOL_LOOP_END, TOOL_END_STOCK, sizeof TOOL_END_STOCK)
        || !vvfp_site_holds(HUT_BOLTS_NONE, HUT_NONE_STOCK, sizeof HUT_NONE_STOCK)) {
        return;
    }
    vvfp_site_bytes(&w[0], TOOL_CAP_SITE, sizeof TOOL_CAP_STOCK, TOOL_CAP_STOCK, TOOL_CAP_OURS);
    vvfp_site_bytes(&w[1], CLOTH_CAP_SITE, sizeof CLOTH_CAP_STOCK, CLOTH_CAP_STOCK, CLOTH_CAP_OURS);
    vvfp_site_bytes(&w[2], USE_CLAMP_SITE, sizeof USE_CLAMP_STOCK, USE_CLAMP_STOCK, USE_CLAMP_OURS);
    vvfp_site_branch(&w[3], TOOL_LOOP_SITE, sizeof TOOL_LOOP_STOCK, TOOL_LOOP_STOCK, 0xE9, (const void *)tool_loop_stub);
    vvfp_site_branch(&w[4], HUT_BOLTS_SITE, sizeof HUT_BOLTS_STOCK, HUT_BOLTS_STOCK, 0xE9,
                     (const void *)hut_bolts_stub);
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
