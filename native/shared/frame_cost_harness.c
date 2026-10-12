/* What each game's Origins companion costs per frame at 256 villagers.

   The companion's whole source is compiled in (one build per game,
   /DFC_GAME=1..5), linked fixed at 0x400000 like
   orphan_masks_game_harness.c, with a zero-filled backing block standing in
   for the game's own addresses.  The villager table is a 256-record block of
   its own, handed to the companion where it looks for it.  The Documents
   folder is redirected to the folder on the command line, so nothing is
   ever read or written under the real Documents\LDW.  The other companions
   (Cause of Death, Story Upgrades, ...) are not shipped here, so their
   bridges are no-ops: their own costs are timed by their own harnesses.

   What one frame of play calls, per game (scripts/build_*_feature.py):
     1  Vv1MaskTick, once (the village render tick)
     2  Vv2MaskSweep, once (the compositor)
     3  per villager drawn: VV3WorldMaskDrawAt's work -- the cross-check
        bridge, the purchase tick and VV3_GetMaskForRecord (the mask cell's
        draw itself is the game's and is not called)
     4  Vv4MaskCacheSurface once (the present), and per villager drawn the
        mask lookup of Vv4MaskGetForRecord (its atlas build is the game's)
     5  per villager drawn: Vv5MaskSync

   Prints the microseconds per frame with no masks and with every villager
   masked, and how many files were opened or probed in the timed frames
   (none may be).  Exit code 0 when every bound holds; the bounds are
   generous (a whole frame at 60 fps is 16 667 us) and the file count is
   exact.  Built and run by tests/test_frame_cost.py. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];
static wchar_t g_docs_w[MAX_PATH];
static int g_files;               /* opens and probes while counting */

static BOOL WINAPI fc_special_a(HWND o, LPSTR out, int c, BOOL cr) { (void)o; (void)c; (void)cr; lstrcpyA(out, g_docs); return TRUE; }
static BOOL WINAPI fc_special_w(HWND o, LPWSTR out, int c, BOOL cr) { (void)o; (void)c; (void)cr; lstrcpyW(out, g_docs_w); return TRUE; }
static HRESULT WINAPI fc_folder_a(HWND o, int c, HANDLE t, DWORD f, LPSTR out) { (void)o; (void)c; (void)t; (void)f; lstrcpyA(out, g_docs); return S_OK; }
static HRESULT WINAPI fc_folder_w(HWND o, int c, HANDLE t, DWORD f, LPWSTR out) { (void)o; (void)c; (void)t; (void)f; lstrcpyW(out, g_docs_w); return S_OK; }
static HANDLE WINAPI fc_open_a(LPCSTR p, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD d, DWORD f, HANDLE t) {
    ++g_files;
    return CreateFileA(p, a, s, sa, d, f, t);
}
static HANDLE WINAPI fc_open_w(LPCWSTR p, DWORD a, DWORD s, LPSECURITY_ATTRIBUTES sa, DWORD d, DWORD f, HANDLE t) {
    ++g_files;
    return CreateFileW(p, a, s, sa, d, f, t);
}
static DWORD WINAPI fc_attr_a(LPCSTR p) { ++g_files; return GetFileAttributesA(p); }
static DWORD WINAPI fc_attr_w(LPCWSTR p) { ++g_files; return GetFileAttributesW(p); }

#if FC_GAME != 4   /* The Tree of Life declares its own import: redirected in main instead */
#define SHGetSpecialFolderPathA fc_special_a
#endif
#define SHGetSpecialFolderPathW fc_special_w
#define SHGetFolderPathA fc_folder_a
#define SHGetFolderPathW fc_folder_w
#define CreateFileA fc_open_a
#define CreateFileW fc_open_w
#define GetFileAttributesA fc_attr_a
#define GetFileAttributesW fc_attr_w
#define VVFP_XC_NOW() 0u          /* the cross-check's clock, frozen: its scan never starts */

#if FC_GAME == 3
static unsigned int g_vv3_manager_imm;
static int g_vv3_slot_bound;
#define VV3_MANAGER_IMM_VA ((UINT_PTR)&g_vv3_manager_imm)
#define VV3_SLOT_BOUND_PTR ((UINT_PTR)&g_vv3_slot_bound)
#endif

#if FC_GAME == 1
#include "../vv1_origins_icons/vv1_origins_icons.c"
#elif FC_GAME == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#elif FC_GAME == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#elif FC_GAME == 4
#include "../vv4_origins_icons/vv4_origins_icons.c"
#elif FC_GAME == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#else
#error "build with /DFC_GAME=1..5"
#endif
#include "save_folder.c"

#undef CreateFileA
#undef CreateFileW
#undef GetFileAttributesA
#undef GetFileAttributesW

static unsigned char g_backing[0x600000];   /* covers the game's own addresses */

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static int mapped(UINT_PTR lo, UINT_PTR size) {
    UINT_PTR b = (UINT_PTR)g_backing;
    return lo >= b && lo + size <= b + sizeof g_backing;
}

#define VILLAGERS 256
#define SLOT 1
static unsigned char *g_rec;

#if FC_GAME == 1
#define STRIDE VV_RECORD_STRIDE
static int fc_setup(void) {
    if (!mapped(VV_MASK_SCRATCH_BASE, 0x200) || !mapped(0x0048D700, 8)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    VV_MASK_MANAGER = g_rec;
    VV_MASK_SAVE_SLOT = SLOT;
    return g_rec != NULL;
}
static void villager(int i) {
    unsigned char *r = g_rec + (size_t)i * STRIDE;
    r[VV_OCCUPIED_OFFSET] = 1;
    _snprintf((char *)r + VV_MASK_NAME_OFFSET, 0x18, "Villager%03d", i);
    *(int *)(r + VV_GENDER_OFFSET) = 1 + (i & 1);
    *(int *)(r + VV_MASK_SCALAR_OFFSET) = i * 7;
}
static void mask_all(void) {
    int i;
    for (i = 0; i < VILLAGERS; ++i) vv1_mask_set(g_rec + (size_t)i * STRIDE, (unsigned char)(1 + i % 4));
}
static int calls_per_frame(void) { return 1; }
static void frame(void) { Vv1MaskTick(); }

#elif FC_GAME == 2
#define STRIDE VV2_RECORD_STRIDE
static int fc_setup(void) {
    if (!mapped(0x4B3000, 0x1000)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    VV2_MASK_SLOT = SLOT;
    return g_rec != NULL && vv2_mask_table_ok();
}
static void villager(int i) {
    unsigned char *r = g_rec + (size_t)i * STRIDE;
    r[VV2_ACTIVE_OFFSET] = 1;
    _snprintf((char *)r + VV2_NAME_OFFSET, 0x16, "Villager%03d", i);
    *(int *)(r + VV2_IDENTITY_SEX) = 1 + (i & 1);
}
static void mask_all(void) {
    int i;
    for (i = 0; i < VILLAGERS; ++i) VV2_MASK_TABLE[i] = (unsigned char)(1 + i % 4);
}
static int calls_per_frame(void) { return 1; }
static void frame(void) { Vv2MaskSweep(g_rec); }

#elif FC_GAME == 3
#define STRIDE VV3_STRIDE
static int fc_setup(void) {
    if (!mapped(VV3_MASK_SLOT_PTR, 4) || !mapped(0x006E0058, 4)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, 0x14 + (SIZE_T)VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_READWRITE);
    g_vv3_manager_imm = (unsigned int)(UINT_PTR)g_rec;
    g_vv3_slot_bound = VILLAGERS;
    g_rec += 0x14;
    *(int *)(UINT_PTR)VV3_MASK_SLOT_PTR = SLOT;
    return 1;
}
static void villager(int i) {
    unsigned char *r = g_rec + (size_t)i * STRIDE;
    int k;
    r[VV3_ACTIVE] = 1;
    *(int *)(r + VV3_HEALTH) = 100;
    r[VV3_GENDER] = (unsigned char)(i & 1);
    _snprintf((char *)r + VV3_NAME, 0x18, "Villager%03d", i);
    for (k = 0; k < 3; ++k) {
        ((int *)(r + VV3_LIKES))[k] = (i + k) % 40;
        ((int *)(r + VV3_DISLIKES))[k] = -1;
    }
}
static void mask_all(void) {
    int i;
    vv3_mask_prepare_slot();
    for (i = 0; i < VILLAGERS; ++i) {
        g_vv3_mask[i] = (unsigned char)(1 + i % 4);
        g_vv3_mask_fp[i] = vv3_mask_fingerprint(g_rec + (size_t)i * STRIDE);
    }
}
static int calls_per_frame(void) { return VILLAGERS; }
static int g_seen_masks;
static void frame(void) {
    int i;
    for (i = 0; i < VILLAGERS; ++i) {
        vvfp_crosscheck_bridge(3, 1);
        vv3_paid_tick();
        g_seen_masks += VV3_GetMaskForRecord(g_rec + (size_t)i * STRIDE) > 0;
    }
}

#elif FC_GAME == 4
#define STRIDE VV_REC_STRIDE
static int fc_setup(void) {
    if (!mapped(VV4_MASK_SAVE_SLOT_VA, 4) || !mapped(0x00728B04, 4)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_vv_rec_base = (unsigned int)(UINT_PTR)g_rec;
    g_vv_slots = VILLAGERS;
    *(int *)(UINT_PTR)VV4_MASK_SAVE_SLOT_VA = SLOT;
    return g_rec != NULL;
}
static void villager(int i) {
    unsigned char *r = g_rec + (size_t)i * STRIDE;
    r[VV_OCCUPIED_OFFSET] = 1;
    *(int *)(r + 0x1C40) = 100;
    *(int *)(r + VV_SEX_OFFSET) = i & 1;
    _snprintf((char *)r + VV_NAME_OFFSET, 0x18, "Villager%03d", i);
    strcpy((char *)r + VV_FATHER_NAME_OFFSET, "Pa");
    strcpy((char *)r + VV_MOTHER_NAME_OFFSET, "Ma");
}
static void mask_all(void) {
    int i;
    vv_prepare_mask_state();
    for (i = 0; i < VILLAGERS; ++i) {
        g_mask_by_index[i] = (unsigned char)(1 + i % 4);
        g_mask_fp[i] = vv_fingerprint(g_rec + (size_t)i * STRIDE);
    }
}
static int calls_per_frame(void) { return 1 + VILLAGERS; }
static int g_seen_masks;
static void frame(void) {
    int i;
    Vv4MaskCacheSurface(NULL);
    for (i = 0; i < VILLAGERS; ++i) {
        vvfp_crosscheck_bridge(4, 1);
        vv_prepare_mask_state();
        g_seen_masks += vv_get_mask(g_rec + (size_t)i * STRIDE) > 0;
    }
}

#elif FC_GAME == 5
#define STRIDE VV5_ROSTER_STRIDE
static int fc_setup(void) {
    if (!mapped(VV5_SLOT_SCRATCH, 4) || !mapped(VV5_256_MASK_TABLE, 0x80)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    g_vv5_rec_base = (unsigned int)(UINT_PTR)g_rec;
    g_vv5_slots = VILLAGERS;
    *(int *)VV5_SLOT_SCRATCH = SLOT;
    return g_rec != NULL && vv5_slots() == VILLAGERS;
}
static void villager(int i) {
    unsigned char *r = g_rec + (size_t)i * STRIDE;
    r[VV5_ACTIVE_OFFSET] = 1;
    *(int *)(r + VV5_SEX_OFFSET) = i & 1;
    _snprintf((char *)r + VV5_NAME_OFFSET, 0x18, "Villager%03d", i);
    if (i >= VILLAGERS - 150) r[0x1CEC] = 1;      /* 150 Heathens */
}
static void mask_all(void) {
    unsigned char *t = vv5_mask_table();
    int i;
    for (i = 0; i < VILLAGERS; ++i) {
        t[i >> 1] = (unsigned char)((i & 1) ? (t[i >> 1] & 0x0F) | ((1 + i % 4) << 4) : (t[i >> 1] & 0xF0) | (1 + i % 4));
    }
}
static int calls_per_frame(void) { return VILLAGERS; }
static void frame(void) {
    int i;
    for (i = 0; i < VILLAGERS; ++i) (void)Vv5MaskSync();
}
#endif


/* The Documents folder of every shell32 lookup, redirected in shell32 itself
   (a jump at the entry): The Tree of Life declares its own import of
   SHGetSpecialFolderPathA, which no macro can reach. */
static int fc_jump(const char *name, void *to) {
    unsigned char *at = (unsigned char *)GetProcAddress(LoadLibraryA("shell32.dll"), name);
    DWORD old;
    if (at == NULL || !VirtualProtect(at, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
    at[0] = 0xE9;
    *(int *)(at + 1) = (int)((unsigned char *)to - (at + 5));
    VirtualProtect(at, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, 5);
    return 1;
}
static int fc_redirect_shell(void) {
    return fc_jump("SHGetSpecialFolderPathA", (void *)fc_special_a) && fc_jump("SHGetSpecialFolderPathW", (void *)fc_special_w)
        && fc_jump("SHGetFolderPathA", (void *)fc_folder_a) && fc_jump("SHGetFolderPathW", (void *)fc_folder_w);
}

static double time_frames(int n) {
    LARGE_INTEGER fr, a, b;
    int f;
    QueryPerformanceFrequency(&fr);
    QueryPerformanceCounter(&a);
    for (f = 0; f < n; ++f) frame();
    QueryPerformanceCounter(&b);
    return (double)(b.QuadPart - a.QuadPart) * 1e6 / (double)fr.QuadPart / n;
}

int main(int argc, char **argv) {
    int i;
    double plain, masked;
    if (argc < 2) {
        printf("usage: frame_cost_harness <documents folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, g_docs, -1, g_docs_w, MAX_PATH);
    if (!fc_redirect_shell()) {
        printf("  FAIL the Documents folder could not be redirected\n== 1 failure(s) ==\n");
        return 1;
    }
    printf("== game %d, %d villagers ==\n", FC_GAME, VILLAGERS);
    if (!fc_setup()) {
        printf("  FAIL the game's addresses are not in the backing block\n== 1 failure(s) ==\n");
        return 1;
    }
    for (i = 0; i < VILLAGERS; ++i) villager(i);
    for (i = 0; i < 20; ++i) frame();           /* the village settles: slot, sidecar, roster */
    g_files = 0;
    plain = time_frames(200);
    printf("  frame, no masks: %.1f us (%d companion calls)\n", plain, calls_per_frame());
    CHECK(g_files == 0, "no file is opened or probed in 200 frames without masks (%d)", g_files);
    mask_all();
    for (i = 0; i < 20; ++i) frame();
    g_files = 0;
    masked = time_frames(200);
    printf("  frame, every villager masked: %.1f us\n", masked);
    CHECK(g_files == 0, "no file is opened or probed in 200 frames with masks (%d)", g_files);
    CHECK(plain < 2000.0, "a frame without masks costs under 2 ms (%.1f us)", plain);
    CHECK(masked < 4000.0, "a frame with every villager masked costs under 4 ms (%.1f us)", masked);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
