/* The TEST build of native/shared/island_timer_keep.h: the same keeper and the
   same five games' sites and stubs the Origins companions compile, with the
   slot, the roster, the clock, the save's time and the per-slot file held in
   memory so the emulator tests (tests/test_bought_events_keep_natural_timer.py)
   can drive them beside a rendered executable.  Built by
   scripts/build_island_timer_keep_test.ps1 into tests/test_dlls/; never
   shipped. */
#define ITK_TEST 1
#include "island_timer_keep.h"
#include "island_timer_vv1.inc"
#include "island_timer_vv2.inc"
#include "island_timer_vv3.inc"
#include "island_timer_vv4.inc"
#include "island_timer_vv5.inc"

/* The refund of a Barrel of Babies that can never arrive (barrel_refund.h), with the message
   recorded instead of shown. */
static int test_told, test_told_amount;
#define VV_BARREL_REFUND_TELL(refunded) (++test_told, test_told_amount = (refunded))
#include "barrel_refund.h"

static int test_slot;
static unsigned int test_roster[ITK_ROSTER];

static int __stdcall test_slot_fn(void) {
    return test_slot;
}

static int test_roster_fn(unsigned int *out) {
    int i, n = 0;
    for (i = 0; i < ITK_ROSTER; ++i) {
        out[i] = test_roster[i];
        n += test_roster[i] != 0u;
    }
    return n;
}

static itk_game test_games[6] = {
    { 0 },
    { 1, ITK_VV1_SITES, sizeof ITK_VV1_SITES / sizeof ITK_VV1_SITES[0], test_slot_fn, test_roster_fn, "x" },
    { 2, ITK_VV2_SITES, sizeof ITK_VV2_SITES / sizeof ITK_VV2_SITES[0], test_slot_fn, test_roster_fn, "x" },
    { 3, ITK_VV3_SITES, sizeof ITK_VV3_SITES / sizeof ITK_VV3_SITES[0], test_slot_fn, test_roster_fn, "x" },
    { 4, ITK_VV4_SITES, sizeof ITK_VV4_SITES / sizeof ITK_VV4_SITES[0], test_slot_fn, test_roster_fn, "x" },
    { 5, ITK_VV5_SITES, sizeof ITK_VV5_SITES / sizeof ITK_VV5_SITES[0], test_slot_fn, test_roster_fn, "x" },
};

/* Install for `game` (every site verified, then written).  1 when in place. */
__declspec(dllexport) int __stdcall ItkProbeInstall(int game) {
    if (game < 1 || game > 5) {
        return 0;
    }
    return itk_install(&test_games[game]);
}

/* Site `index` of `game`: its address and length (0 past the end). */
__declspec(dllexport) int __stdcall ItkProbeSite(int game, int index, unsigned int *va) {
    if (game < 1 || game > 5 || index < 0 || index >= test_games[game].site_count) {
        return 0;
    }
    *va = test_games[game].sites[index].va;
    return test_games[game].sites[index].length;
}

/* The village on screen: its slot and its roster (ITK_ROSTER identities). */
__declspec(dllexport) void __stdcall ItkProbeVillage(int slot, const unsigned int *roster) {
    test_slot = slot;
    memcpy(test_roster, roster, sizeof test_roster);
}

/* A new process: nothing in memory; the file stays when `keep_file`. */
__declspec(dllexport) void __stdcall ItkProbeSession(int keep_file) {
    itk_active = 0;
    itk_fire_pending = 0;
    itk_checked = 0;
    memset(&itk_rec, 0, sizeof itk_rec);
    if (!keep_file) {
        itk_test_have_file = 0;
    }
}

/* The slot's save is written now (0: no save on disk). */
__declspec(dllexport) void __stdcall ItkProbeSaved(int saved) {
    itk_test_save_time = saved ? ++itk_test_now : 0u;
}

/* out[0] a bought event on its way, out[1] its distance, out[2] its slot,
   out[3] the trigger found it due, out[4] the file is there, out[5] the
   file's distance. */
__declspec(dllexport) void __stdcall ItkProbeState(unsigned int *out) {
    out[0] = (unsigned int)itk_active;
    out[1] = itk_rec.delta;
    out[2] = itk_rec.slot;
    out[3] = (unsigned int)itk_fire_pending;
    out[4] = (unsigned int)itk_test_have_file;
    out[5] = itk_test_file.delta;
}

/* The Story / Cheat Upgrades' arm, as its host table hands it over. */
__declspec(dllexport) void __stdcall ItkProbeStoryArming(void *field, unsigned int value) {
    itk_story_arming(field, value);
}

/* Whether a bought island event is on its way, as the island-event rows'
   locks ask it (the Origins companions directly, the Story / Cheat Upgrades
   through their host table). */
__declspec(dllexport) int __stdcall ItkProbeOnItsWay(void) {
    return itk_story_on_its_way();
}

/* Start Over or a deleted tribe in `slot` (VvfpOriginsVillageReset). */
__declspec(dllexport) void __stdcall ItkProbeVillageReset(int slot) {
    itk_village_reset(slot);
}

/* The Tree of Life's and New Believers' barrel refund, as their Origins companions wire it
   (vv4_origins_icons.c VV4_BARREL_REFUND, vv5_task9_origins.c VV5_BARREL_REFUND), with the price
   the test sets (the Origins price, or 0 when the upgrades are free) and the Barrel's file a count. */
static int test_price, test_withdrawn;
static int t4_pending(void) { return *(volatile unsigned char *)(UINT_PTR)0x00728B04u != 0; }
static int t4_island(void) { return *(volatile unsigned char *)(UINT_PTR)0x00728B08u != 0; }
static void t4_cancel(void) {
    *(volatile unsigned char *)(UINT_PTR)0x00728B04u = 0;
    *(volatile unsigned char *)(UINT_PTR)0x00728B00u = 0;
}
static int t5_pending(void) { return (*(volatile unsigned int *)(UINT_PTR)0x0051D388u & 0x0Cu) != 0; }
static int t5_island(void) { return (*(volatile unsigned int *)(UINT_PTR)0x0051D388u & 0x30u) != 0; }
static void t5_cancel(void) { *(volatile unsigned int *)(UINT_PTR)0x0051D388u &= ~0x0Cu; }
static int t_price(void) { return test_price; }
static void t_withdrawn(void) { ++test_withdrawn; }
static const vv_barrel_refund_game TEST_REFUND[2] = {
    { 4, 0x467610u, 0x43FA4Au, (volatile int *)(UINT_PTR)0x004D6F88u,
      t4_pending, t4_island, t4_cancel, t_price, t_withdrawn },
    { 5, 0x4713F0u, 0x4426F7u, (volatile int *)(UINT_PTR)0x0051D5F8u,
      t5_pending, t5_island, t5_cancel, t_price, NULL },
};

__declspec(dllexport) void __stdcall ItkProbeBarrelRefund(int game, int price) {
    test_price = price;
    if (game == 4 || game == 5) {
        vv_br_install(&TEST_REFUND[game - 4]);
    }
}

/* out[0] refunds made, out[1] messages, out[2] the last message's amount, out[3] files withdrawn. */
__declspec(dllexport) void __stdcall ItkProbeBarrelState(int *out) {
    out[0] = vv_br_count;
    out[1] = test_told;
    out[2] = test_told_amount;
    out[3] = test_withdrawn;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
