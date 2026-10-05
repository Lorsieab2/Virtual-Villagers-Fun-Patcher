/* The orphan mask entries (orphan_masks.h), run in each game's own Origins
   companion.  32-bit only; built once per game with /DOM_GAME=1..5 and run by
   tests/test_orphan_mask_cleanup.py.

   The companion's whole source is compiled into this harness, so its own
   mask load, follow, identities, file format, folder and writer are the
   ones tested -- and the cross-check's scan and repair
   (vvfp_xc_masks_scan / vvfp_xc_masks_repair) are called the way the
   prompt calls them.  The game's memory is stood in for at the game's own
   addresses: the harness is linked fixed at 0x400000 and its zero-filled
   backing block covers them (checked at run time).  Stood in for at compile
   time: the village's header ("VVFP Save Reset.dll"), a failing disk
   (sidecar_io.h's writer) and the cross-check's clock (frozen, so no prompt
   ever opens).  Everything is written under Documents\LDW\<this exe's
   name>, which harness_ldw_tree.h leaves as it found it.

   The village, in every game: records 0 Ana, 1 Bo, 2 and 3 two villagers
   alike ("Cy", one identity), and in The Secret City to New Believers 4 a
   body awaiting burial ("Fay").  The mask file, as the last session wrote
   it: 1 Bo's mask; 5 the mask of Dee, who is gone; 6 a mask on a record
   nobody held (no identity); 7 a mask stored for "Cy"; 8 (The Secret City
   to New Believers) Fay's.  Orphans: 5 and 6.  Kept: 1, 7 (both Cys carry
   it -- ambiguous) and 8 (the save still holds the body). */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int g_fail_writes;
static int g_header_ok = 1;
static int g_header_calls;
static int g_fail_note;          /* the Repairs log note fails */
static int g_fail_after_note;    /* ... and every write after it */

static BOOL WINAPI harness_write_file(HANDLE file, LPCVOID data, DWORD size, LPDWORD wrote, LPOVERLAPPED ov) {
    if (g_fail_writes) {
        if (wrote) *wrote = 0;
        SetLastError(ERROR_DISK_FULL);
        return FALSE;
    }
    return WriteFile(file, data, size, wrote, ov);
}

static int harness_header(int game, int slot, char *out, int size) {
    ++g_header_calls;
    if (!g_header_ok) return 0;
    _snprintf_s(out, (size_t)size, _TRUNCATE, "Village: Harness Village (Save %d)\r\n", slot);
    (void)game;
    return 1;
}

static int harness_note(int game, const char *header, const char *checked, const char *body);
#define VVFP_OM_NOTE(game, header, checked, body) harness_note(game, header, checked, body)
#define VV_SIDECAR_WRITE_FILE harness_write_file
#define VVFP_OM_HEADER(game, slot, out, size) harness_header(game, slot, out, size)
#define VVFP_XC_NOW() 0u

#if OM_GAME == 3
static unsigned int g_vv3_manager_imm;   /* the executable's `mov ecx, MANAGER` immediate */
static int g_vv3_slot_bound;             /* its slot-bound immediate */
#define VV3_MANAGER_IMM_VA ((UINT_PTR)&g_vv3_manager_imm)
#define VV3_SLOT_BOUND_PTR ((UINT_PTR)&g_vv3_slot_bound)
#endif

#if OM_GAME == 1
#include "../vv1_origins_icons/vv1_origins_icons.c"
#elif OM_GAME == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#elif OM_GAME == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#elif OM_GAME == 4
#include "../vv4_origins_icons/vv4_origins_icons.c"
#elif OM_GAME == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#else
#error "build with /DOM_GAME=1..5"
#endif
#include "harness_ldw_tree.h"

static unsigned char g_backing[0x600000];   /* covers the game's own addresses */

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static int mapped(UINT_PTR lo, UINT_PTR size) {
    UINT_PTR b = (UINT_PTR)g_backing;
    return lo >= b && lo + size <= b + sizeof g_backing;
}

#define SLOT 1
#define NAME_MAX_ 0x18

/* ---- per game: the records, the identity, the file ------------------------ */
#if OM_GAME == 1
#define RECORDS 256
#define BY_RECORD 1
#define HAS_BODY 0
#define WEAK 0
static unsigned char *g_rec;
static int om_setup(void) {
    if (!mapped(VV_MASK_SCRATCH_BASE, 0x200)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, RECORDS * VV_RECORD_STRIDE, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    VV_MASK_MANAGER = g_rec;
    VV_MASK_SAVE_SLOT = SLOT;
    return g_rec != NULL;
}
static unsigned char *rec(int i) { return g_rec + (size_t)i * VV_RECORD_STRIDE; }
static void villager(int i, const char *name, int male, int family) {
    unsigned char *r = rec(i);
    memset(r, 0, VV_RECORD_STRIDE);
    if (name == NULL) return;
    r[VV_OCCUPIED_OFFSET] = 1;
    strncpy((char *)r + VV_MASK_NAME_OFFSET, name, NAME_MAX_);
    *(int *)(r + VV_GENDER_OFFSET) = male ? 1 : 2;
    *(int *)(r + VV_MASK_SCALAR_OFFSET) = family;
}
static void body(int i, const char *name) { (void)i; (void)name; }
static unsigned int identity(int i) { return vv1_mask_identity(rec(i)); }
static unsigned char mask_at(int i) {
    unsigned char p = VV_MASK_TABLE[i >> 1];
    return (unsigned char)((i & 1) ? p >> 4 : p & 0x0F);
}
static int file_path(char *out) { return vv1_mask_sidecar_path(out, MAX_PATH, SLOT); }
static DWORD file_bytes(const unsigned char *value, const unsigned int *stored, const unsigned int *roster,
                        unsigned char *out) {
    unsigned int magic = VV_MASK_SIDECAR_MAGIC_V2;
    int i;
    (void)stored;
    memcpy(out, &magic, 4);
    memset(out + 4, 0, 128);
    for (i = 0; i < RECORDS; ++i) out[4 + (i >> 1)] |= (unsigned char)((i & 1) ? value[i] << 4 : value[i]);
    memcpy(out + 4 + 128, roster, RECORDS * 4);
    return 4 + 128 + RECORDS * 4;
}
static unsigned char file_mask(const unsigned char *f, int i) {
    unsigned char p = f[4 + (i >> 1)];
    return (unsigned char)((i & 1) ? p >> 4 : p & 0x0F);
}
static void load(void) { vv1_mask_sidecar_load(); vv1_mask_follow_loaded(); }

#elif OM_GAME == 2
#define RECORDS 256
#define BY_RECORD 1
#define HAS_BODY 0
#define WEAK 1
static unsigned char *g_rec;
static int om_setup(void) {
    if (!mapped(0x4B3000, 0x1000)) return 0;
    g_rec = (unsigned char *)VirtualAlloc(NULL, (SIZE_T)RECORDS * VV2_RECORD_STRIDE, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_READWRITE);
    VV2_MASK_SLOT = SLOT;
    g_vv2_sweep_base = g_rec;
    return g_rec != NULL && vv2_mask_table_ok();
}
static unsigned char *rec(int i) { return g_rec + (size_t)i * VV2_RECORD_STRIDE; }
static void villager(int i, const char *name, int male, int family) {
    unsigned char *r = rec(i);
    memset(r, 0, VV2_RECORD_STRIDE);
    if (name == NULL) return;
    r[VV2_ACTIVE_OFFSET] = 1;
    strncpy((char *)r + VV2_NAME_OFFSET, name, NAME_MAX_ - 1);
    *(int *)(r + VV2_IDENTITY_SEX) = male ? 1 : 2;
    if (family) {
        strcpy((char *)r + VV2_FATHER_OFFSET, "Pa");
        strcpy((char *)r + VV2_MOTHER_OFFSET, "Ma");
    }
}
static void body(int i, const char *name) { (void)i; (void)name; }
static unsigned int identity(int i) {
    static unsigned int ids[RECORDS];
    vv2_roster_identities(g_rec, ids);
    return ids[i];
}
static unsigned int name_hash(int i) {
    static unsigned int names[RECORDS];
    vv2_roster_snapshot(g_rec, names);
    return names[i];
}
static unsigned char mask_at(int i) { return VV2_MASK_TABLE[i]; }
static int file_path(char *out) { return vv2_mask_sidecar_path(out); }
static DWORD file_bytes_magic(unsigned int magic, const unsigned char *value, const unsigned int *roster,
                              unsigned char *out) {
    memcpy(out, &magic, 4);
    memcpy(out + 4, roster, RECORDS * 4);
    memcpy(out + 4 + RECORDS * 4, value, RECORDS);
    return 4 + RECORDS * 4 + RECORDS;
}
static DWORD file_bytes(const unsigned char *value, const unsigned int *stored, const unsigned int *roster,
                        unsigned char *out) {
    (void)stored;
    return file_bytes_magic(VV2_MASK_SIDECAR_MAGIC_V6, value, roster, out);
}
static unsigned char file_mask(const unsigned char *f, int i) { return f[4 + RECORDS * 4 + i]; }
static void load(void) { g_vv2_have_roster = 0; g_vv2_slot = 0; Vv2MaskSyncVillage(g_rec); }

#elif OM_GAME == 3
#define RECORDS 150
#define BY_RECORD 0
#define HAS_BODY 1
#define WEAK 0
#define MANAGER 0x59E110u
static int om_setup(void) {
    if (!mapped(MANAGER, 0x14 + RECORDS * VV3_STRIDE) || !mapped(VV3_MASK_SLOT_PTR, 4)) return 0;
    g_vv3_manager_imm = MANAGER;
    g_vv3_slot_bound = RECORDS;
    *(int *)(UINT_PTR)VV3_MASK_SLOT_PTR = SLOT;
    return 1;
}
static unsigned char *rec(int i) { return (unsigned char *)(UINT_PTR)(MANAGER + 0x14u + (unsigned)i * VV3_STRIDE); }
static void villager(int i, const char *name, int male, int family) {
    unsigned char *r = rec(i);
    int k;
    memset(r, 0, VV3_STRIDE);
    if (name == NULL) return;
    r[VV3_ACTIVE] = 1;
    *(int *)(r + VV3_HEALTH) = 100;
    r[VV3_GENDER] = (unsigned char)(male ? 0 : 1);
    strncpy((char *)r + VV3_NAME, name, NAME_MAX_);
    for (k = 0; k < 3; ++k) {
        ((int *)(r + VV3_LIKES))[k] = family ? 3 + k : -1;
        ((int *)(r + VV3_DISLIKES))[k] = -1;
    }
}
static void body(int i, const char *name) { villager(i, name, 0, 0); *(int *)(rec(i) + VV3_HEALTH) = 0; }
static unsigned int identity(int i) { return vv3_mask_fingerprint(rec(i)); }
static unsigned char mask_at(int i) { return g_vv3_mask[i]; }
static int file_path(char *out) { return vv3_mask_sidecar_path(out, MAX_PATH, SLOT); }
static DWORD file_bytes(const unsigned char *value, const unsigned int *stored, const unsigned int *roster,
                        unsigned char *out) {
    unsigned int magic = VV3_MASK_MAGIC;
    unsigned char v[VV3_MASK_SLOTS];
    unsigned int s[VV3_MASK_SLOTS];
    (void)roster;
    memset(v, 0, sizeof v);
    memset(s, 0, sizeof s);
    memcpy(v, value, RECORDS);
    memcpy(s, stored, RECORDS * 4);
    memcpy(out, &magic, 4);
    memcpy(out + 4, v, sizeof v);
    memcpy(out + 4 + sizeof v, s, sizeof s);
    return 4 + sizeof v + sizeof s;
}
static unsigned char file_mask(const unsigned char *f, int i) { return f[4 + i]; }
static void load(void) { g_vv3_mask_slot = 0; vv3_mask_prepare_slot(); }

#elif OM_GAME == 4
#define RECORDS 150
#define BY_RECORD 1
#define HAS_BODY 1
#define WEAK 0
static int om_setup(void) {
    if (!mapped(0x50E5ACu, RECORDS * VV_REC_STRIDE) || !mapped(VV4_MASK_SAVE_SLOT_VA, 4)) return 0;
    *(int *)(UINT_PTR)VV4_MASK_SAVE_SLOT_VA = SLOT;
    return vv_slots() == RECORDS && VV_REC_ARRAY_BASE == 0x50E5ACu;
}
static unsigned char *rec(int i) { return (unsigned char *)(UINT_PTR)(0x50E5ACu + (unsigned)i * VV_REC_STRIDE); }
static void villager(int i, const char *name, int male, int family) {
    unsigned char *r = rec(i);
    memset(r, 0, VV_REC_STRIDE);
    if (name == NULL) return;
    r[VV_OCCUPIED_OFFSET] = 1;
    *(int *)(r + 0x1C40) = 100;
    *(int *)(r + VV_SEX_OFFSET) = male ? 1 : 0;
    strncpy((char *)r + VV_NAME_OFFSET, name, NAME_MAX_);
    if (family) {
        strcpy((char *)r + VV_FATHER_NAME_OFFSET, "Pa");
        strcpy((char *)r + VV_MOTHER_NAME_OFFSET, "Ma");
    }
}
static void body(int i, const char *name) {
    villager(i, name, 0, 0);
    rec(i)[0x1CC7] = 1;                  /* dead, its body still in the record */
    *(int *)(rec(i) + 0x1C40) = 0;
}
static unsigned int identity(int i) { return vv_fingerprint(rec(i)); }
static unsigned char mask_at(int i) { return g_mask_by_index[i]; }
static int file_path(char *out) { return vv_build_sidecar_path(out, SLOT); }
static DWORD file_bytes(const unsigned char *value, const unsigned int *stored, const unsigned int *roster,
                        unsigned char *out) {
    unsigned int header[2];
    header[0] = 3u;
    header[1] = RECORDS;
    memcpy(out, "VVMK", 4);
    memcpy(out + 4, header, 8);
    memcpy(out + 12, value, RECORDS);
    memcpy(out + 12 + RECORDS, stored, RECORDS * 4);
    memcpy(out + 12 + RECORDS * 5, roster, RECORDS * 4);
    return 12 + RECORDS * 9;
}
static unsigned char file_mask(const unsigned char *f, int i) { return f[12 + i]; }
static void load(void) {
    g_current_slot = -1;                 /* a slot change: everything is read again */
    vv_prepare_mask_state();
    vv_mask_sweep();                     /* seen alive */
    vv_mask_sweep();                     /* identity ready: the follow runs */
}

#elif OM_GAME == 5
#define RECORDS 150
#define BY_RECORD 1
#define HAS_BODY 1
#define WEAK 1
static int om_setup(void) {
    if (!mapped(0x554148u, 0x48 + RECORDS * VV5_ROSTER_STRIDE) || !mapped(0x7B1D20u, 0x100)) return 0;
    *(int *)VV5_SLOT_SCRATCH = SLOT;
    return vv5_slots() == RECORDS;
}
static unsigned char *rec(int i) { return (unsigned char *)(UINT_PTR)(0x554190u + (unsigned)i * VV5_ROSTER_STRIDE); }
static void villager(int i, const char *name, int male, int family) {
    unsigned char *r = rec(i);
    memset(r, 0, VV5_ROSTER_STRIDE);
    if (name == NULL) return;
    r[VV5_ACTIVE_OFFSET] = 1;
    *(int *)(r + VV5_SEX_OFFSET) = male ? 0 : 1;
    strncpy((char *)r + VV5_NAME_OFFSET, name, NAME_MAX_);
    if (family) {
        strcpy((char *)r + VV5_FATHER_OFFSET, "Pa");
        strcpy((char *)r + VV5_MOTHER_OFFSET, "Ma");
    }
}
static void body(int i, const char *name) { villager(i, name, 0, 0); }   /* an active record, as a body is */
static unsigned int identity(int i) { return vv5_identity(rec(i)); }
static unsigned int name_hash(int i) {
    static unsigned int names[VV5_RECORD_COUNT];
    vv5_roster_snapshot(names);
    return names[i];
}
static unsigned char mask_at(int i) {
    unsigned char p = ((unsigned char *)VV5_MASK_TABLE)[i >> 1];
    return (unsigned char)((i & 1) ? p >> 4 : p & 0x0F);
}
static int file_path(char *out) { return build_mask_sidecar_path(out); }
static DWORD file_bytes_magic(unsigned int magic, const unsigned char *value, const unsigned int *roster,
                              unsigned char *out) {
    int i;
    memcpy(out, &magic, 4);
    memcpy(out + 4, roster, RECORDS * 4);
    memset(out + 4 + RECORDS * 4, 0, RECORDS / 2);
    for (i = 0; i < RECORDS; ++i) {
        out[4 + RECORDS * 4 + (i >> 1)] |= (unsigned char)((i & 1) ? value[i] << 4 : value[i]);
    }
    return 4 + RECORDS * 4 + RECORDS / 2;
}
static DWORD file_bytes(const unsigned char *value, const unsigned int *stored, const unsigned int *roster,
                        unsigned char *out) {
    (void)stored;
    return file_bytes_magic(VV5_MASK_SIDECAR_MAGIC_V6, value, roster, out);
}
static unsigned char file_mask(const unsigned char *f, int i) {
    unsigned char p = f[4 + RECORDS * 4 + (i >> 1)];
    return (unsigned char)((i & 1) ? p >> 4 : p & 0x0F);
}
static void load(void) { g_vv5_have_roster = 0; g_vv5_slot = 0; Vv5MaskSync(); }
#endif

/* ---- files ------------------------------------------------------------------ */
static char g_path[MAX_PATH];
static char g_log[MAX_PATH];

static DWORD read_file(const char *path, unsigned char *buf, DWORD cap) {
    HANDLE f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD got = 0;
    if (f == INVALID_HANDLE_VALUE) return 0;
    if (!ReadFile(f, buf, cap, &got, NULL)) got = 0;
    CloseHandle(f);
    return got;
}

static int write_file(const char *path, const unsigned char *buf, DWORD n) {
    HANDLE f = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    DWORD put = 0;
    if (f == INVALID_HANDLE_VALUE) return 0;
    WriteFile(f, buf, n, &put, NULL);
    CloseHandle(f);
    return put == n;
}

static int exists(const char *path) { return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES; }

static int harness_note(int game, const char *header, const char *checked, const char *body) {
    if (g_fail_note) {
        if (g_fail_after_note) g_fail_writes = 1;
        return 0;
    }
    return vv_repairs_note(game, header, checked, body);
}

static int file_mask_is(int i, unsigned char v) {
    static unsigned char f[8192];
    return read_file(g_path, f, sizeof f) > 0 && file_mask(f, i) == v;
}

/* The companion's own writer (what the next table change runs). */
static int publish(void) {
#if OM_GAME == 1
    return vv1_mask_sidecar_save();
#elif OM_GAME == 2
    return vv2_mask_sidecar_save();
#elif OM_GAME == 3
    return vv3_mask_write_sidecar();
#elif OM_GAME == 4
    return vv_write_mask_sidecar();
#else
    return vv5_om_publish();
#endif
}

static char g_backup1[MAX_PATH], g_backup2[MAX_PATH];

static int count_in(const char *path, const char *what) {
    static unsigned char text[65536];
    DWORD n = read_file(path, text, sizeof text - 1);
    int c = 0;
    const char *p;
    text[n] = 0;
    for (p = (const char *)text; (p = strstr(p, what)) != NULL; ++p) ++c;
    return c;
}

/* ---- the scenario ----------------------------------------------------------- */
static unsigned char g_value[RECORDS];
static unsigned int g_stored[RECORDS], g_roster[RECORDS];
static unsigned char g_file[8192], g_now[8192];
static DWORD g_file_n;

/* The table after a reload of the repaired file.  The Tree of Life keeps
   who held each record apart from each mask's identity, so its roster names
   Fay only at her body's record and the follow moves her mask there. */
#if OM_GAME == 4
#define RELOADED "1:1 4:5 7:2"
#elif HAS_BODY
#define RELOADED "1:1 7:2 8:5"
#else
#define RELOADED "1:1 7:2"
#endif

static void village(void) {
    int i;
    for (i = 0; i < RECORDS; ++i) villager(i, NULL, 0, 0);
    villager(0, "Ana", 0, 0);
    villager(1, "Bo", 1, 0);
    villager(2, "Cy", 1, 1);
    villager(3, "Cy", 1, 1);                 /* alike: one identity for both */
    if (HAS_BODY) body(4, "Fay");
}

/* The file the last session wrote: see the top of this file. */
static void scenario_file(void) {
    unsigned int dee;
    memset(g_value, 0, sizeof g_value);
    memset(g_stored, 0, sizeof g_stored);
    memset(g_roster, 0, sizeof g_roster);
    villager(9, "Dee", 0, 0);
    dee = identity(9);
    villager(9, NULL, 0, 0);
    g_roster[0] = identity(0);
    g_roster[1] = identity(1);
    g_roster[2] = identity(2);
    g_roster[3] = identity(3);
    if (HAS_BODY) g_roster[4] = identity(4);
    g_value[1] = 1; g_stored[1] = identity(1);
    g_value[5] = 3; g_stored[5] = g_roster[5] = dee;
    g_value[6] = 4;                          /* nobody held record 6: no identity */
    g_value[7] = 2; g_stored[7] = g_roster[7] = identity(2);
    if (HAS_BODY) { g_value[8] = 5; g_stored[8] = g_roster[8] = identity(4); }
    g_file_n = file_bytes(g_value, g_stored, g_roster, g_file);
}

static void put_file_and_load(void) {
    CHECK(write_file(g_path, g_file, g_file_n), "the mask file is written (%lu bytes)", g_file_n);
    load();
    g_file_n = read_file(g_path, g_file, sizeof g_file);   /* as the load left it (written back in its format) */
}

static int table_is(const char *expect) {   /* "1:1 5:3 ..." -> every other entry 0 */
    unsigned char want[RECORDS];
    int i, idx, v, n;
    const char *p = expect;
    memset(want, 0, sizeof want);
    while (sscanf(p, "%d:%d%n", &idx, &v, &n) == 2) { want[idx] = (unsigned char)v; p += n; }
    for (i = 0; i < RECORDS; ++i) {
        if (mask_at(i) != want[i]) {
            printf("    entry %d is %d, expected %d\n", i, mask_at(i), want[i]);
            return 0;
        }
    }
    return 1;
}

int main(void) {
    char before[256], after[256];
    int found, game = OM_GAME;
    harness_ldw_tree_begin();
    printf("== game %d: the companion's own source, the game's memory stood in for ==\n", game);
    CHECK(om_setup(), "the game's addresses are in the backing block (%p..%p)",
          (void *)g_backing, (void *)(g_backing + sizeof g_backing));
    if (failures) exit(1);
    village();
    /* The companion's own identities, for scripts/vvfp_consistency_check.py to be held to
       (tests/test_orphan_mask_cleanup.py rebuilds each villager in a save and compares). */
    {
        static const char *const who[] = { "Ana", "Bo", "Cy", "Cy", "Fay" };
        int i;
        for (i = 0; i < (HAS_BODY ? 5 : 4); ++i) {
#if WEAK
            printf("IDENT %d %s %08X NAME %08X\n", i, who[i], identity(i), name_hash(i));
#elif OM_GAME == 4
            g_fp_version = 2u;
            printf("IDENT %d %s %08X V2 %08X\n", i, who[i], identity(i), vv_identity(rec(i)));
            g_fp_version = 3u;
#else
            printf("IDENT %d %s %08X\n", i, who[i], identity(i));
#endif
        }
    }
    CHECK(file_path(g_path),"the mask file's path: %s", g_path);
    CHECK(strstr(g_path, "\\Virtual Villagers Fun Patcher Data\\Village Masks\\") != NULL,
          "it is in the Village Masks folder (the #519 resolver)");
    {
        char folder[MAX_PATH];
        CHECK(vv_save_subfolder(folder, "Virtual Villagers Fun Patcher Logs\\Repairs", 64), "the Repairs folder");
        _snprintf_s(g_log, sizeof g_log, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log 1.txt", folder, game);
    }
    _snprintf_s(g_backup1, sizeof g_backup1, _TRUNCATE, "%s.before-v1.35.59-repair", g_path);
    _snprintf_s(g_backup2, sizeof g_backup2, _TRUNCATE, "%s.before-v1.35.59-repair-2", g_path);

    printf("== the load ==\n");
    scenario_file();
#if OM_GAME == 4
    /* The Tree of Life follows its table on the second sweep that sees the
       village: until then the entries are still where the file had them. */
    CHECK(write_file(g_path, g_file, g_file_n), "the mask file is written before the village is followed");
    g_current_slot = -1;
    vv_prepare_mask_state();
    vv_mask_sweep();
    CHECK(vvfp_xc_masks_scan(game, SLOT) == -1, "before the follow has run, the scan cannot tell yet");
#endif
    put_file_and_load();
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"),
          "the load keeps every entry where it was (nobody moved)");

    printf("== the scan ==\n");
    found = vvfp_xc_masks_scan(game, SLOT);
    CHECK(found == 2, "two orphans: Dee's mask and the one with no identity (scan says %d)", found);
    CHECK(vvfp_xc_masks_scan(game == 1 ? 2 : 1, SLOT) == 0, "another game's scan finds nothing here");
    CHECK(vvfp_xc_masks_scan(game, SLOT + 1) == -1, "another slot cannot be told yet");

    printf("== Not now ==\n");
    vvfp_xc_masks_repair(game, SLOT, 0);
    CHECK(read_file(g_path, g_now, sizeof g_now) == g_file_n && memcmp(g_now, g_file, g_file_n) == 0,
          "the file is byte for byte as it was");
    CHECK(!exists(g_backup1), "no backup");
    CHECK(!exists(g_log), "no Repairs log");
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"), "the table is as it was");
    CHECK(g_header_calls == 0, "nothing was even looked up");

    printf("== Repair, without the village's header ==\n");
    g_header_ok = 0;
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two");
    vvfp_xc_masks_repair(game, SLOT, 1);
    CHECK(g_header_calls == 1, "the header was asked for");
    CHECK(read_file(g_path, g_now, sizeof g_now) == g_file_n && memcmp(g_now, g_file, g_file_n) == 0
          && !exists(g_backup1) && !exists(g_log), "nothing changed, no backup, no log");
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"), "the table is as it was");
    g_header_ok = 1;

    printf("== Repair, the disk failing ==\n");
    g_fail_writes = 1;
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two");
    vvfp_xc_masks_repair(game, SLOT, 1);
    g_fail_writes = 0;
    CHECK(read_file(g_path, g_now, sizeof g_now) == g_file_n && memcmp(g_now, g_file, g_file_n) == 0,
          "the file is as it was");
    CHECK(!exists(g_backup1), "this repair's backup is gone again");
    CHECK(!exists(g_log), "nothing is listed");
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"), "the entries are back in the table");

    printf("== Repair, the Repairs log failing ==\n");
    g_fail_note = 1;
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two");
    vvfp_xc_masks_repair(game, SLOT, 1);
    CHECK(file_mask_is(5, 3) && file_mask_is(6, 4), "the file is written back with both entries");
    CHECK(!exists(g_backup1) && !exists(g_log), "no backup left, nothing listed");
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"), "the entries are back in the table");
    g_file_n = read_file(g_path, g_file, sizeof g_file);   /* as written back */
    g_fail_after_note = 1;
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two again");
    vvfp_xc_masks_repair(game, SLOT, 1);
    g_fail_note = g_fail_after_note = g_fail_writes = 0;
    CHECK(exists(g_backup1), "when the file cannot be written back either, the backup is kept: it alone holds them");
    CHECK(read_file(g_backup1, g_now, sizeof g_now) == g_file_n && memcmp(g_now, g_file, g_file_n) == 0,
          "... and it is the file as it was");
    CHECK(table_is(HAS_BODY ? "1:1 5:3 6:4 7:2 8:5" : "1:1 5:3 6:4 7:2"), "the entries are back in the table again");
    CHECK(publish(), "the next write puts them back on disk");
    CHECK(file_mask_is(5, 3) && file_mask_is(6, 4), "... both entries");
    DeleteFileA(g_backup1);
    g_file_n = read_file(g_path, g_file, sizeof g_file);

    printf("== Repair ==\n");
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two");
    vvfp_xc_masks_repair(game, SLOT, 1);
    CHECK(table_is(HAS_BODY ? "1:1 7:2 8:5" : "1:1 7:2"), "exactly the two orphans are gone from the table");
    found = (int)read_file(g_path, g_now, sizeof g_now);
    CHECK(found > 0 && file_mask(g_now, 5) == 0 && file_mask(g_now, 6) == 0, "and from the file");
    CHECK(found > 0 && file_mask(g_now, 1) == 1 && file_mask(g_now, 7) == 2
          && (!HAS_BODY || file_mask(g_now, 8) == 5), "Bo's, the alike pair's and the body's are kept in the file");
    CHECK(read_file(g_backup1, g_now, sizeof g_now) == g_file_n && memcmp(g_now, g_file, g_file_n) == 0,
          "the backup is the file as it was: %s", g_backup1);
    CHECK(count_in(g_log, "Repair 1\r\n") == 1 && count_in(g_log, "Village: Harness Village (Save 1)\r\n") == 1,
          "one Repair record under the village's header");
    CHECK(count_in(g_log, "  Mask removed: ") == 2, "two removals are listed");
    CHECK(count_in(g_log, "Red Mask") == 1 && count_in(g_log, "Purple Mask") == 1, "each by its mask");
    CHECK(count_in(g_log, "Checked: " VV_OM_CHECKED) == 1, "what was checked against what");
    CHECK(count_in(g_log, ".before-v1.35.59-repair\r\n") == 1, "and the backup's name");

    printf("== exactly once ==\n");
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 0, "the next scan finds nothing");
    vvfp_xc_masks_repair(game, SLOT, 1);
    CHECK(!exists(g_backup2) && count_in(g_log, "Repair ") == 1, "a Repair then changes nothing more");
    load();
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 0, "nor does the next load's");
    CHECK(table_is(RELOADED), "which keeps the alike pair's mask (and the body's)");
    load();
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 0 && table_is(RELOADED), "load after load");

    printf("== the village changes while the player decides ==\n");
    scenario_file();
    put_file_and_load();
    CHECK(vvfp_xc_masks_scan(game, SLOT) == 2, "asked about two");
    if (BY_RECORD) {
        villager(6, "Eve", 0, 0);                 /* a newborn takes record 6 */
    } else {
        villager(9, "Dee", 0, 0);                 /* Dee is back in the records */
    }
    vvfp_xc_masks_repair(game, SLOT, 1);
    _snprintf_s(after, sizeof after, _TRUNCATE, BY_RECORD ? (HAS_BODY ? "1:1 6:4 7:2 8:5" : "1:1 6:4 7:2")
                                                          : "1:1 5:3 7:2 8:5");
    CHECK(table_is(after), "only the entry that is still an orphan is removed");
    CHECK(exists(g_backup2), "backed up again, beside the first backup: %s", g_backup2);
    CHECK(count_in(g_log, "  Mask removed: ") == 3, "one more removal listed");
    villager(BY_RECORD ? 6 : 9, NULL, 0, 0);

#if WEAK
    printf("== an older, name-only file ==\n");
    {
        unsigned int names[RECORDS];
        unsigned int dee_name;
        int i;
        villager(9, "Dee", 0, 0);
        dee_name = name_hash(9);
        villager(9, NULL, 0, 0);
        memset(g_value, 0, sizeof g_value);
        memset(names, 0, sizeof names);
        for (i = 0; i < 5; ++i) names[i] = name_hash(i);
        g_value[5] = 3; names[5] = dee_name;       /* Dee's name: nobody is called Dee */
        g_value[9] = 2; names[9] = name_hash(2);   /* "Cy": both Cys carry the name */
#if OM_GAME == 2
        g_file_n = file_bytes_magic(VV2_MASK_SIDECAR_MAGIC, g_value, names, g_file);   /* 'VM04' */
#else
        g_file_n = file_bytes_magic(VV5_MASK_SIDECAR_MAGIC, g_value, names, g_file);   /* 'VM05' */
#endif
        put_file_and_load();
        CHECK(table_is("5:3 9:2"), "the load keeps both where they were");
        CHECK(vvfp_xc_masks_scan(game, SLOT) == 1, "one orphan: the name no villager has");
        vvfp_xc_masks_repair(game, SLOT, 1);
        CHECK(table_is("9:2"), "the name both Cys carry is kept");
        load();
        CHECK(vvfp_xc_masks_scan(game, SLOT) == 0 && table_is("9:2"), "and still kept at the next load");
    }
#endif
    (void)before;
    printf("== %d failure(s) ==\n", failures);
    exit(failures ? 1 : 0);
}

#include "save_folder.c"
