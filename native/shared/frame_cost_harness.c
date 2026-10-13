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
#define VV3_MASK_LIVE_COUNT     /* counts the records the live table hashes again */
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

/* The render getter as v1.35.70 shipped it: a fingerprint of every record
   for every lookup.  The live table (vv3_mask_live_refresh) must give the
   same answer as this, for every record, after every change below. */
static int fc_vv3_reference_mask(void *record) {
    const unsigned char *rec = (const unsigned char *)record;
    unsigned int fpv;
    int idx, live_idx, stored_idx, i, live_count, stored_count = 0, value = 0;
    if (record == NULL) return 0;
    if (!vv3_mask_prepare_slot()) return 0;
    idx = vv3_mask_index(record);
    if (idx < 0) return 0;
    if (rec[VV3_ACTIVE] == 0 || *(const int *)(rec + VV3_HEALTH) <= 0) return 0;
    fpv = vv3_mask_fingerprint(rec);
    if (!vv3_mask_has_stored_fingerprint(fpv)) return 0;
    live_idx = vv3_mask_unique_live_index(fpv);
    if (live_idx != idx) {
        live_count = vv3_mask_live_fingerprint_count(fpv);
        if (live_count < 2) return 0;
        for (i = 0; i < VV3_MASK_SLOTS; ++i) {
            if (g_vv3_mask[i] == 0 || g_vv3_mask_fp[i] != fpv) continue;
            if (value == 0) value = g_vv3_mask[i];
            else if (value != g_vv3_mask[i]) return 0;
            ++stored_count;
        }
        return stored_count == live_count ? value : 0;
    }
    stored_idx = vv3_mask_unique_stored_index(fpv);
    if (stored_idx < 0) return 0;
    if (stored_idx == idx) return g_vv3_mask[idx];
    return g_vv3_mask[stored_idx];
}

static unsigned int fc_rand_state = 12345u;
static unsigned int fc_rand(unsigned int n) {
    fc_rand_state = fc_rand_state * 1103515245u + 12345u;
    return ((fc_rand_state >> 8) & 0xFFFFFFu) % n;
}

/* A small pool of names and Likes, so namesakes and identical twins are common. */
static void fc_vv3_identity(unsigned char *r, unsigned int pick) {
    int k;
    memset(r + VV3_NAME, 0, VV3_NAME_LEN);
    _snprintf((char *)r + VV3_NAME, VV3_NAME_LEN, "Kid%u", pick % 12u);
    r[VV3_GENDER] = (unsigned char)((pick / 12u) & 1u);
    for (k = 0; k < 3; ++k) {
        ((int *)(r + VV3_LIKES))[k] = (int)((pick / 24u + k) % 3u);
        ((int *)(r + VV3_DISLIKES))[k] = -1;
    }
}

static unsigned char *fc_vv3_base(void) { return (unsigned char *)(UINT_PTR)g_vv3_manager_imm + 0x14; }

/* Compares the shipped getter with the reference for every record of the
   array the game points at now, and of the other array; returns mismatches. */
static int g_vv3_compared, g_vv3_nonzero, g_vv3_group_answers;
static int fc_vv3_compare(unsigned char *other) {
    unsigned char *arrays[2];
    int a, i, bad = 0;
    arrays[0] = fc_vv3_base();
    arrays[1] = other;
    for (a = 0; a < 2; ++a) {
        for (i = 0; i < VILLAGERS; ++i) {
            unsigned char *r = arrays[a] + (size_t)i * STRIDE;
            int got = VV3_GetMaskForRecord(r), want = fc_vv3_reference_mask(r);
            ++g_vv3_compared;
            if (got != want) {
                if (bad < 5) printf("  MISMATCH array %d record %d: %d, the full scan says %d\n", a, i, got, want);
                ++bad;
            }
            if (want) {
                ++g_vv3_nonzero;
                if (a == 0 && r[VV3_ACTIVE] && *(int *)(r + VV3_HEALTH) > 0
                    && vv3_mask_live_fingerprint_count(vv3_mask_fingerprint(r)) >= 2)
                    ++g_vv3_group_answers;
            }
        }
        if (VV3_GetMaskForRecord(arrays[a] + 1) != fc_vv3_reference_mask(arrays[a] + 1)) ++bad;
    }
    return bad;
}

/* Packs the living and the dead-but-active into records 0, 1, 2, ... as a
   reload does, the rest emptied. */
static void fc_vv3_pack(void) {
    unsigned char *base = fc_vv3_base();
    int i, to = 0;
    for (i = 0; i < VILLAGERS; ++i) {
        unsigned char *r = base + (size_t)i * STRIDE;
        if (!r[VV3_ACTIVE]) continue;
        if (to != i) memcpy(base + (size_t)to * STRIDE, r, STRIDE);
        ++to;
    }
    for (; to < VILLAGERS; ++to) {
        unsigned char *r = base + (size_t)to * STRIDE;
        r[VV3_ACTIVE] = 0;
        *(int *)(r + VV3_HEALTH) = 0;
    }
}

/* Binds every living owner of fp to one value, as Change Appearance for All does. */
static void fc_vv3_group_bind(unsigned int fp, unsigned char value) {
    unsigned char *base = fc_vv3_base();
    int i;
    for (i = 0; i < VILLAGERS; ++i) {
        unsigned char *r = base + (size_t)i * STRIDE;
        if (r[VV3_ACTIVE] && *(int *)(r + VV3_HEALTH) > 0 && vv3_mask_fingerprint(r) == fp) {
            g_vv3_mask[i] = value;
            g_vv3_mask_fp[i] = fp;
        }
    }
}

static void fc_vv3_mutate(unsigned int foreign_imm, unsigned int home_imm) {
    unsigned char *base = fc_vv3_base();
    int i = (int)fc_rand(VILLAGERS), j = (int)fc_rand(VILLAGERS);
    unsigned char *r = base + (size_t)i * STRIDE, *s = base + (size_t)j * STRIDE;
    switch (fc_rand(15)) {
    case 0:  *(int *)(r + VV3_HEALTH) = 0; break;                       /* a death */
    case 1:  r[VV3_ACTIVE] = 0; break;                                  /* the record freed */
    case 2:                                                             /* a birth into a freed slot */
        if (r[VV3_ACTIVE] && *(int *)(r + VV3_HEALTH) > 0) break;
        r[VV3_ACTIVE] = 1;
        *(int *)(r + VV3_HEALTH) = 100;
        fc_vv3_identity(r, fc_rand(48));
        break;
    case 3:                                                             /* an identical twin / namesake */
        r[VV3_GENDER] = s[VV3_GENDER];
        memcpy(r + VV3_NAME, s + VV3_NAME, VV3_NAME_LEN);
        memcpy(r + VV3_LIKES, s + VV3_LIKES, 24);
        break;
    case 4:  fc_vv3_pack(); break;                                      /* a reload */
    case 5:  r[VV3_NAME] = (unsigned char)('A' + fc_rand(3)); break;    /* a rename */
    case 6:  ((int *)(r + VV3_LIKES))[fc_rand(3)] = (int)fc_rand(4); break;   /* a Likes change */
    case 7:  r[VV3_NAME + VV3_NAME_LEN - 1] ^= 0x5A; break;              /* a byte past the terminator */
    case 8:                                                             /* a mask chosen for a villager */
        g_vv3_mask[i] = (unsigned char)(1 + fc_rand(5));
        g_vv3_mask_fp[i] = vv3_mask_fingerprint(r);
        break;
    case 9:                                                             /* stored under another slot */
        g_vv3_mask[j] = (unsigned char)(1 + fc_rand(5));
        g_vv3_mask_fp[j] = vv3_mask_fingerprint(r);
        break;
    case 10: g_vv3_mask[i] = 0; g_vv3_mask_fp[i] = 0; break;
    case 11:                                                            /* a whole-village group bind */
        if (r[VV3_ACTIVE] && *(int *)(r + VV3_HEALTH) > 0)
            fc_vv3_group_bind(vv3_mask_fingerprint(r), (unsigned char)(1 + fc_rand(5)));
        break;
    case 12: g_vv3_slot_bound = (int)(VILLAGERS - fc_rand(3) * 53); break;    /* another bound */
    case 13: g_vv3_manager_imm = g_vv3_manager_imm == home_imm ? foreign_imm : home_imm; break;  /* the title screen's array */
    default: *(int *)(r + VV3_HEALTH) = 1 + (int)fc_rand(100); break;    /* health moves, or a revival */
    }
}

static void fc_vv3_equivalence(void) {
    unsigned int home_imm = g_vv3_manager_imm, foreign_imm;
    unsigned char *foreign_block, *foreign;
    int step, bad = 0, i;
    /* Every masked villager drawn twice with nothing changed: nobody is hashed again. */
    frame();
    g_vv3_live_rehashed = 0;
    frame();
    CHECK(g_vv3_live_rehashed == 0, "a masked frame with no change hashes no record again (%d)", g_vv3_live_rehashed);
    g_rec[7 * STRIDE + VV3_NAME] ^= 0x01;     /* one rename */
    frame();
    CHECK(g_vv3_live_rehashed == 1, "a rename hashes that one record again (%d)", g_vv3_live_rehashed);
    g_rec[7 * STRIDE + VV3_NAME] ^= 0x01;

    foreign_block = (unsigned char *)VirtualAlloc(NULL, 0x14 + (SIZE_T)VILLAGERS * STRIDE, MEM_COMMIT | MEM_RESERVE,
                                                  PAGE_READWRITE);
    if (foreign_block == NULL) {
        CHECK(0, "the title screen's array could not be allocated");
        return;
    }
    foreign_imm = (unsigned int)(UINT_PTR)foreign_block;
    foreign = foreign_block + 0x14;
    for (i = 0; i < VILLAGERS; i += 3) {       /* a third of it copies of the village's records */
        memcpy(foreign + (size_t)i * STRIDE, g_rec + (size_t)((i * 7) % VILLAGERS) * STRIDE, STRIDE);
    }
    /* A village full of namesakes and twins: the pool has 48 identities. */
    for (i = 0; i < VILLAGERS; i += 2) fc_vv3_identity(g_rec + (size_t)i * STRIDE, fc_rand(48));
    for (i = 0; i < VILLAGERS; ++i) {
        if (fc_rand(3) == 0) fc_vv3_group_bind(vv3_mask_fingerprint(g_rec + (size_t)i * STRIDE),
                                               (unsigned char)(1 + fc_rand(5)));
    }
    bad += fc_vv3_compare(foreign);
    for (step = 0; step < 1500; ++step) {
        fc_vv3_mutate(foreign_imm, home_imm);
        bad += fc_vv3_compare(g_vv3_manager_imm == home_imm ? foreign : g_rec);
    }
    g_vv3_manager_imm = home_imm;
    g_vv3_slot_bound = VILLAGERS;
    bad += fc_vv3_compare(foreign);
    printf("  live table vs full scan: %d answers compared, %d masked, %d in twin/namesake groups\n",
           g_vv3_compared, g_vv3_nonzero, g_vv3_group_answers);
    CHECK(bad == 0, "every mask answer is the full scan's over births, deaths, reloads, renames and twins (%d differ)", bad);
    CHECK(g_vv3_nonzero > 10000 && g_vv3_group_answers > 1000,
          "the story reaches masked villagers and twin groups (%d, %d)", g_vv3_nonzero, g_vv3_group_answers);
    VirtualFree(foreign_block, 0, MEM_RELEASE);
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
#if FC_GAME == 3
    /* v1.35.71: a fingerprint of every record per masked villager drawn was
       about 1.4 ms; the live table re-reads them and hashes only a change. */
    CHECK(masked < 1000.0, "The Secret City, every villager masked, costs under 1 ms (%.1f us)", masked);
    fc_vv3_equivalence();
#endif
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
