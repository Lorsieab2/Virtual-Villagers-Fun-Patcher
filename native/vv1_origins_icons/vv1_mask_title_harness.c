/* A New Home's mask file at the title screen.  32-bit only.

   Drives the committed "VVFP VV1 Origins Icons.dll" over a fake villager
   array at the game's own addresses (the records pointer 0x491098, the mask
   table 0x491000, the slot 0x4911F4, the newborn-dirty flag 0x4911FC), with
   its Documents redirected to a throwaway folder under %TEMP%
   (native/shared/harness_redirect_documents.h): nothing touches the real
   Documents\LDW.

   The owner's v1.35.67 session lost A New Home's parents at the title screen:
   the game's slot field already named slot 1 while the array held the
   founders the startup slot list had seeded, and the empty table committed
   against them was written over the file.  The mask table runs the same kind
   of per-frame logic; this checks it never does that
   (native/shared/foreign_sidecar.h).

   Usage:  vv1_mask_title_harness.exe "<path to VVFP VV1 Origins Icons.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include "../shared/harness_redirect_documents.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define TABLE_VA    0x00491000u
#define RECORDS_PTR 0x00491098u
#define SLOT_VA     0x004911F4u
#define DIRTY_VA    0x004911FCu
#define STRIDE      0x3D8u
#define COUNT       256
#define OCCUPIED    0x28u
#define GENDER      0x350u
#define SCALAR      0x36Cu
#define NAME        0x370u
#define TABLE_BYTES 128

typedef void (__stdcall *void_t)(void);

/* Linked fixed at 0x400000 with this block large enough to hold the game's
   page 0x480000..0x4A0000 (vv5_mask_identity_harness.c's way). */
static unsigned char g_backing[0x300000];
static unsigned char g_records[COUNT * STRIDE];

static int map_range(unsigned int lo, unsigned int size) {
    unsigned int b = (unsigned int)(UINT_PTR)g_backing;
    return lo >= b && lo + size <= b + sizeof g_backing;
}

static void put(int i, const char *name, int male, int scalar) {
    unsigned char *r = g_records + (size_t)i * STRIDE;
    memset(r, 0, STRIDE);
    if (name == NULL) {
        return;
    }
    r[OCCUPIED] = 1;
    *(int *)(r + GENDER) = male ? 1 : 2;
    *(int *)(r + SCALAR) = scalar;
    lstrcpynA((char *)r + NAME, name, 0x1C);
}

static void clear_village(void) {
    memset(g_records, 0, sizeof g_records);
}

static unsigned char *table(void) { return (unsigned char *)TABLE_VA; }

static HMODULE g_dll;
static void_t g_restore, g_tick;

/* A fresh game process: the DLL's state and the exe's scratch start empty. */
static int load(const char *path) {
    if (g_dll != NULL) {
        FreeLibrary(g_dll);
    }
    memset(table(), 0, TABLE_BYTES);
    *(unsigned char *)DIRTY_VA = 0;
    g_dll = LoadLibraryA(path);
    if (g_dll == NULL || !harness_redirect_documents(g_dll)) {
        return 0;
    }
    g_restore = (void_t)GetProcAddress(g_dll, "Vv1MaskRestore");
    g_tick = (void_t)GetProcAddress(g_dll, "Vv1MaskTick");
    return g_restore != NULL && g_tick != NULL;
}

static void ticks(int n) {
    int i;
    for (i = 0; i < n; ++i) {
        g_tick();
    }
}

static DWORD read_file(const char *p, unsigned char *buf, DWORD cap) {
    HANDLE h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ReadFile(h, buf, cap, &got, NULL);
    CloseHandle(h);
    return got;
}

int main(int argc, char **argv) {
    /* The whole process's Documents is a throwaway %TEMP% folder: no harness ever
       writes under the real Documents\LDW (the owner's rule, 2026-10-10). */
    if (!harness_redirect_documents_process()) {
        fprintf(stderr, "cannot redirect Documents to a throwaway folder; not running\n");
        return 2;
    }
    char exe[MAX_PATH], file[MAX_PATH], *base, *dot;
    static unsigned char good[8192], now[8192];
    DWORD good_n, now_n;
    if (argc < 2) {
        printf("usage: harness <dll>\n");
        return 2;
    }
    printf("== fake game memory at the game's addresses ==\n");
    CHECK(map_range(0x480000, 0x20000), "the game's page 0x480000..0x4A0000 is inside the harness image");
    if (failures) return 1;
    memset((void *)0x480000, 0, 0x20000);
    *(unsigned char **)RECORDS_PTR = g_records;
    *(unsigned int *)SLOT_VA = 1;
    CHECK(load(argv[1]), "the DLL loads with its Documents redirected");
    if (failures) return 1;
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    /* A fresh village's file goes in the save's own folder (native/shared/per_save.h). */
    _snprintf(file, MAX_PATH, "%s\\LDW\\%s\\Virtual Villagers Fun Patcher\\Save 1\\Data\\Village Masks\\"
              "Virtual Villagers 1 Village Masks - Save 1.dat", harness_redirect_documents_path(), base);

    printf("== village A, slot 1: two masks chosen and saved ==\n");
    put(0, "Alba Bahati", 0, 13);
    put(1, "Bram Bahati", 1, 11);
    put(2, "Cora Bahati", 0, 12);
    g_restore();
    ticks(3);
    table()[0] = 0x21;                        /* Alba 1, Bram 2 */
    *(unsigned char *)DIRTY_VA = 1;           /* any save path */
    ticks(2);
    good_n = read_file(file, good, sizeof good);
    CHECK(good_n > 4 + TABLE_BYTES && good[4] == 0x21, "village A's mask file is written (%lu bytes)", good_n);

    printf("== a new session: the title screen's seeded founders, slot field already 1 ==\n");
    clear_village();
    put(0, "Abebe", 0, 1);
    put(1, "Kanoa", 1, 1);
    put(2, "Mele", 0, 1);
    put(3, "Tavita", 1, 1);
    put(4, "Leilani", 0, 1);
    CHECK(load(argv[1]), "the DLL loads again (a new process)");
    g_restore();
    ticks(60);
    *(unsigned char *)DIRTY_VA = 1;           /* a save attempt during the title screen */
    ticks(60);
    now_n = read_file(file, now, sizeof now);
    CHECK(now_n == good_n && memcmp(now, good, good_n) == 0,
          "the founders never touch village A's mask file");
    CHECK(table()[0] == 0 && table()[1] == 0, "the founders are shown no mask of A's");

    printf("== the village chosen at the title screen loads into slot 1, packed differently ==\n");
    clear_village();
    put(0, "Bram Bahati", 1, 11);
    put(1, "Alba Bahati", 0, 13);
    put(2, "Cora Bahati", 0, 12);
    ticks(5);
    CHECK((table()[0] & 0x0F) == 2 && (table()[0] >> 4) == 1,
          "village A's masks follow Alba and Bram to their new records");
    now_n = read_file(file, now, sizeof now);
    CHECK(now_n > 4 + TABLE_BYTES && now[4] == 0x12, "... and the file holds them");

    FreeLibrary(g_dll);
    printf("== %d failure(s) ==\n", failures);
    exit(failures ? 1 : 0);
}
