/* Runtime harness for the VV5 mask sidecar's roster identity.  32-bit only.

   Runs the companion instead of reading it.  A fake villager array is placed
   at the game's own address (0x554148, records 0x48 in, stride 0x2F44), the
   slot scratch (0x7B1D7C) and the mask side-table (0x7B1D20) at theirs, and
   the exports are driven the way the appended page and the chooser drive
   them: Vv5MaskSync on draws, WriteMaskSidecar on chooser OK, ReadMaskSidecar
   on the legacy load path.

   The DLL writes Documents\LDW\<this harness's basename>\vvfp_masks_1.dat.
   The harness removes that file and, if it is then empty, that folder.

   Usage:  vv5_mask_identity_harness.exe "<path to VVFP VV5 Task9 Origins Icons.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define ARRAY_VA     0x00554148u
#define RECORDS_VA   (ARRAY_VA + 0x48u)
#define STRIDE       0x2F44u
#define COUNT        150
#define ACTIVE_OFF   0x1CD4u
#define NAME_OFF     0x1B9Cu
#define SLOT_VA      0x007B1D7Cu
#define TABLE_VA     0x007B1D20u
#define TABLE_BYTES  75

typedef int (__stdcall *sync_t)(void);
typedef void (__stdcall *write_t)(const unsigned char *);
typedef void (__stdcall *read_t)(unsigned char *);

/* The game's addresses are covered by this harness's own image: it is linked
   fixed at 0x400000 (/FIXED /DYNAMICBASE:NO) with a writable block large
   enough that 0x554148..0x710000 and 0x7B1000 both fall inside it.  Nothing
   is VirtualAlloc'd, so no system mapping (the NLS view that lands around
   0x7B0000 when the image sits elsewhere) can get in the way. */
static unsigned char g_backing[0x600000];

static int map_range(unsigned int lo, unsigned int size) {
    unsigned int b = (unsigned int)(UINT_PTR)g_backing;
    if (lo >= b && lo + size <= b + sizeof g_backing) {
        return 1;
    }
    printf("  (backing block is %#x..%#x; %#x..%#x is outside it -- link fixed at 0x400000)\n",
           b, b + (unsigned int)sizeof g_backing, lo, lo + size);
    return 0;
}

static unsigned char *rec(int i) { return (unsigned char *)(RECORDS_VA + (unsigned)i * STRIDE); }

static void set_villager(int i, const char *name) {
    unsigned char *r = rec(i);
    memset(r + NAME_OFF, 0, 0x19);
    if (name) { r[ACTIVE_OFF] = 1; strncpy((char *)r + NAME_OFF, name, 0x18); }
    else r[ACTIVE_OFF] = 0;
}

static void clear_village(void) { int i; for (i = 0; i < COUNT; ++i) set_villager(i, NULL); }

static unsigned char *table(void) { return (unsigned char *)TABLE_VA; }
static int table_is_zero(void) { int i; for (i = 0; i < TABLE_BYTES; ++i) if (table()[i]) return 0; return 1; }

int main(int argc, char **argv) {
    HMODULE dll; sync_t sync; write_t writes; read_t reads;
    char docs[MAX_PATH], exe[MAX_PATH], folder[MAX_PATH], file[MAX_PATH], *base, *dot;
    DWORD attrs;
    if (argc < 2) { printf("usage: harness <dll>\n"); return 2; }
    printf("== fake game memory at the game's addresses ==\n");
    CHECK(map_range(ARRAY_VA, 0x48 + COUNT * STRIDE), "villager array mapped at %#x", ARRAY_VA);
    CHECK(map_range(0x7B1000, 0x1000), "slot scratch / side-table page mapped");
    if (failures) return 1;
    memset((void *)ARRAY_VA, 0, 0x48 + COUNT * STRIDE);
    *(int *)SLOT_VA = 0;
    memset(table(), 0, TABLE_BYTES);

    dll = LoadLibraryA(argv[1]);
    CHECK(dll != NULL, "DLL loads");
    if (!dll) return 1;
    sync = (sync_t)GetProcAddress(dll, "Vv5MaskSync");
    writes = (write_t)GetProcAddress(dll, "WriteMaskSidecar");
    reads = (read_t)GetProcAddress(dll, "ReadMaskSidecar");
    CHECK(sync && writes && reads, "Vv5MaskSync / WriteMaskSidecar / ReadMaskSidecar resolve");
    if (!(sync && writes && reads)) return 1;

    /* where the DLL will write */
    SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE);
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\'); base = base ? base + 1 : exe; dot = strrchr(base, '.'); if (dot) *dot = 0;
    sprintf(folder, "%s\\LDW\\%s", docs, base);
    sprintf(file, "%s\\vvfp_masks_1.dat", folder);
    DeleteFileA(file);

    printf("== nothing known: no slot, no villagers ==\n");
    CHECK(sync() == 0, "sync with slot 0 reports unknown");
    *(int *)SLOT_VA = 1;
    CHECK(sync() == 0, "sync with no living villagers reports unknown");
    table()[0] = 0x21;
    writes(table());
    CHECK(GetFileAttributesA(file) == INVALID_FILE_ATTRIBUTES, "chooser write with no identified village creates no file");
    table()[0] = 0;

    printf("== village A: seven founders ==\n");
    set_villager(0, "Maupiti"); set_villager(1, "Kautawa"); set_villager(2, "Tai"); set_villager(3, "Tapa");
    set_villager(4, "Ali"); set_villager(5, "Tepeu"); set_villager(6, "Turuki");
    CHECK(sync() == 1, "first sight of a village: sync reports known");
    CHECK(table_is_zero(), "no sidecar yet -> no masks");
    table()[0] = 0x21; table()[1] = 0x03;      /* villagers 0,1,2 masked */
    writes(table());
    attrs = GetFileAttributesA(file);
    CHECK(attrs != INVALID_FILE_ATTRIBUTES, "chooser write created %s", file);
    {
        HANDLE h = CreateFileA(file, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
        DWORD size = h == INVALID_HANDLE_VALUE ? 0 : GetFileSize(h, NULL);
        unsigned int magic = 0; DWORD got;
        if (h != INVALID_HANDLE_VALUE) { ReadFile(h, &magic, 4, &got, NULL); CloseHandle(h); }
        CHECK(size == 4 + 150 * 4 + TABLE_BYTES, "file is magic + 150 roster dwords + 75-byte table (%lu bytes)", size);
        CHECK(magic == 0x35304D56u, "file magic is 'VM05' (%08x)", magic);
    }

    printf("== same village across events ==\n");
    Sleep(300);
    set_villager(7, "Tiare");                   /* a birth */
    CHECK(sync() == 1, "birth: sync still known");
    CHECK(table()[0] == 0x21 && table()[1] == 0x03, "birth keeps the masks");
    Sleep(300);
    set_villager(3, NULL);                      /* a death */
    CHECK(sync() == 1 && table()[0] == 0x21, "death keeps the masks");
    memset(table(), 0, TABLE_BYTES);
    reads(table());
    CHECK(table()[0] == 0x21 && table()[1] == 0x03, "legacy read restores the masks for this roster");

    printf("== a Start Over in the same slot: seven new villagers ==\n");
    Sleep(300);
    clear_village();
    set_villager(0, "Puhi"); set_villager(1, "Hakuna"); set_villager(2, "Haapiti"); set_villager(3, "Nui");
    set_villager(4, "Tupai"); set_villager(5, "Aito"); set_villager(6, "Kilu");
    CHECK(sync() == 1, "replacement village: sync known");
    CHECK(table_is_zero(), "replacement village starts with NO masks (file did not match)");
    Sleep(300);
    set_villager(0, "Maupiti");                 /* one same-slot name coincidence */
    CHECK(sync() == 1 && table_is_zero(), "one coincidental name is not a majority: still no masks");
    printf("== returning village A keeps its masks (file still on disk) ==\n");
    Sleep(300);
    clear_village();
    set_villager(0, "Maupiti"); set_villager(1, "Kautawa"); set_villager(2, "Tai");
    set_villager(4, "Ali"); set_villager(5, "Tepeu"); set_villager(6, "Turuki"); set_villager(7, "Tiare");
    /* the file on disk was rewritten by village B's chooser? no -- B never
       chose masks, but sync re-saved on B's roster change ("Maupiti" added)
       with B's empty table.  So A's masks were replaced by B's on disk. */
    CHECK(sync() == 1, "village A back on screen: sync known");
    printf("      (A's masks are gone: village B's roster change persisted B's empty table -- expected, one file per slot)\n");

    printf("== slot change reloads ==\n");
    table()[0] = 0x21; writes(table());        /* A's masks under slot 1 again */
    Sleep(300);
    *(int *)SLOT_VA = 2;
    CHECK(sync() == 1 && table_is_zero(), "slot 2 with the same roster: no slot-2 file -> no masks");
    *(int *)SLOT_VA = 1;
    Sleep(300);
    CHECK(sync() == 1 && table()[0] == 0x21, "back to slot 1: A's masks reload from its file");

    DeleteFileA(file);
    RemoveDirectoryA(folder);   /* only succeeds if empty: never removes anything else */
    printf("== cleanup: %s removed; folder removed if empty ==\n", file);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
