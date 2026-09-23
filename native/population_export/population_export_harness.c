/* Runtime harness for "VVFP Population Export.dll".  32-bit only.

   Calls the real WriteVillagePopulation -- the export the save hook calls --
   for each of VV2..VV5 over a synthetic villager array laid out exactly like
   that game's, then reads back the log the DLL wrote and checks the Parents
   block against the villagers it was given.

   WHY THIS EXISTS

   Every other guard on this feature reads the SOURCE: that a row declares an
   offset, that the guard checks it, that the tables agree. None of them runs
   the code. A layout can be internally consistent, pass every source test,
   and still print nothing -- an offset past the data the caller supplied, a
   name-emptiness test that rejects every record, a block guarded by the wrong
   field. This loads the shipped DLL and reads the text it actually writes.

   WHAT IS CHECKED, per game:

     the child's own name, head and body appear;
     the Parents block appears, naming BOTH parents;
     each parent's head and body are the values planted in the record;
     a villager with no recorded parents gets NO Parents block, rather than
       one naming "" or a pair of zeros.

   VV1 is not covered here and cannot be: it stores no parents on the record
   at all, and its block comes from a sidecar bound to a live village. That is
   the whole reason its row is zeros. Its own tests cover that path.

   It reads the HISTORY rather than the roster. Both are written by the same
   write_villager, so either proves the block; the history is the one that
   survives here, because publishing a roster renames a temporary over a
   destination and that rename is not what this harness is testing.

   The DLL writes under Documents\LDW\<this exe's basename>\, exactly where a
   game of that name would keep its saves. The harness removes what it wrote
   when done, so nothing is left behind and no player's folder is touched.

   Usage:  population_export_harness.exe "<path to VVFP Population Export.dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int g_failures;

#define CHECK(cond, ...) do { \
        if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
        else { printf("  FAIL " __VA_ARGS__); printf("\n"); ++g_failures; } \
    } while (0)

typedef int (__stdcall *write_population_t)(int game_id, const void *module,
                                            const char *village);

/* One game's geometry: only what this harness has to plant and read back.
   Values are the population exporter's own, restated so a drift between the
   two shows up here as a failed read rather than as a silent pass. */
struct game {
    int id;
    const char *title;
    unsigned int rva;            /* where the exporter looks for the array */
    int rva_is_pointer;
    unsigned int base;
    unsigned int stride;
    unsigned int slots;
    unsigned int active;
    unsigned int age;
    unsigned int head;
    unsigned int body;
    unsigned int name;
    unsigned int name_cap;
    unsigned int parent_father_name;
    unsigned int parent_mother_name;
    unsigned int parent_name_cap;
    unsigned int parent_father_head;
    unsigned int parent_father_body;
    unsigned int parent_mother_head;
    unsigned int parent_mother_body;
};

static const struct game GAMES[] = {
    { 2, "Virtual Villagers 2", 0x99F24u, 1, 0u, 0xE48Cu, 256u,
      0x30u, 0x530u, 0x548u, 0x54Cu, 0x564u, 0x18u,
      0x57Du, 0x596u, 0x18u, 0x5B0u, 0x5B4u, 0x5B8u, 0x5BCu },
    { 3, "Virtual Villagers 3", 0x19E110u, 0, 0x14u, 0x1F8Cu, 150u,
      0xF10u, 0xDC4u, 0xDF0u, 0xDF4u, 0xDD4u, 0x19u,
      0xDF8u, 0xE11u, 0x19u, 0xE2Cu, 0xE30u, 0xE34u, 0xE38u },
    { 4, "Virtual Villagers 4", 0x10E568u, 0, 0x44u, 0x2E3Cu, 150u,
      0x1CC4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu, 0x1B9Cu, 0x19u,
      0x1BC0u, 0x1BD9u, 0x19u, 0x1BF4u, 0x1BF8u, 0x1BFCu, 0x1C00u },
    { 5, "Virtual Villagers 5", 0x154148u, 0, 0x48u, 0x2F44u, 150u,
      0x1CD4u, 0x1B8Cu, 0x1BB8u, 0x1BBCu, 0x1B9Cu, 0x19u,
      0x1BC0u, 0x1BD9u, 0x19u, 0x1BF4u, 0x1BF8u, 0x1BFCu, 0x1C00u }
};

static void put_int(unsigned char *rec, unsigned int off, int v) {
    *(int *)(rec + off) = v;
}

static void put_name(unsigned char *rec, unsigned int off, const char *s,
                     unsigned int cap) {
    memset(rec + off, 0, cap);
    if (s != NULL && *s != '\0') {
        size_t n = strlen(s);
        if (n > cap - 1) { n = cap - 1; }
        memcpy(rec + off, s, n);
    }
}

/* Read the whole history the DLL wrote, or NULL. Caller frees. */
static char *read_log(void) {
    wchar_t folder[MAX_PATH];
    wchar_t path[MAX_PATH];
    wchar_t exe[MAX_PATH];
    wchar_t *slash;
    FILE *file;
    char *text;
    long size;
    if (!SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, 0, folder))) {
        return NULL;
    }
    if (GetModuleFileNameW(NULL, exe, MAX_PATH) == 0) { return NULL; }
    slash = wcsrchr(exe, L'\\');
    slash = slash ? slash + 1 : exe;
    { wchar_t *dot = wcsrchr(slash, L'.'); if (dot) { *dot = L'\0'; } }
    _snwprintf(path, MAX_PATH,
               L"%ls\\LDW\\%ls\\VVFP Logs\\Tribe History\\Village History 1.txt",
               folder, slash);
    path[MAX_PATH - 1] = L'\0';
    file = _wfopen(path, L"rb");
    if (file == NULL) { return NULL; }
    fseek(file, 0, SEEK_END);
    size = ftell(file);
    fseek(file, 0, SEEK_SET);
    if (size <= 0) { fclose(file); return NULL; }
    text = (char *)malloc((size_t)size + 1);
    if (text == NULL) { fclose(file); return NULL; }
    size = (long)fread(text, 1, (size_t)size, file);
    text[size] = '\0';
    fclose(file);
    return text;
}

static void remove_log(void) {
    wchar_t folder[MAX_PATH];
    wchar_t path[MAX_PATH];
    wchar_t exe[MAX_PATH];
    wchar_t *slash;
    if (!SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, 0, folder))) {
        return;
    }
    if (GetModuleFileNameW(NULL, exe, MAX_PATH) == 0) { return; }
    slash = wcsrchr(exe, L'\\');
    slash = slash ? slash + 1 : exe;
    { wchar_t *dot = wcsrchr(slash, L'.'); if (dot) { *dot = L'\0'; } }
    _snwprintf(path, MAX_PATH,
               L"%ls\\LDW\\%ls\\VVFP Logs\\Tribe History\\Village History 1.txt",
               folder, slash);
    path[MAX_PATH - 1] = L'\0';
    DeleteFileW(path);
}

/* The text between "Villager <n>" and the next "Villager" (or the end).

   The needle stops at the number and does NOT include the line ending: these
   logs are written with CRLF (test_exported_logs_use_windows_line_endings
   pins that), so a needle ending "\n" matches nothing at all -- which looks
   exactly like the DLL having written no such villager. The following byte is
   checked instead, so "Villager 1" does not match "Villager 12". */
static const char *villager_block(const char *log, int number, size_t *length) {
    char needle[32];
    const char *start;
    const char *next;
    size_t n;
    _snprintf(needle, sizeof needle, "Villager %d", number);
    needle[sizeof needle - 1] = '\0';
    n = strlen(needle);
    start = log;
    for (;;) {
        start = strstr(start, needle);
        if (start == NULL) { return NULL; }
        if (start[n] == '\r' || start[n] == '\n') { break; }
        start += n;
    }
    next = strstr(start + 1, "Villager ");
    *length = next ? (size_t)(next - start) : strlen(start);
    return start;
}

static int block_has(const char *block, size_t length, const char *needle) {
    size_t n = strlen(needle);
    size_t i;
    if (block == NULL || n > length) { return 0; }
    for (i = 0; i + n <= length; ++i) {
        if (memcmp(block + i, needle, n) == 0) { return 1; }
    }
    return 0;
}

static void run_game(const struct game *g, write_population_t write) {
    unsigned char *image;
    unsigned char *array;
    unsigned char *rec;
    char *log;
    const char *block;
    size_t length;
    size_t bytes = (size_t)g->base + (size_t)g->stride * g->slots;

    printf("== %s ==\n", g->title);
    /* A fake module: the array sits at the game's own RVA, so the exporter
       finds it exactly as it would in the real image. */
    image = (unsigned char *)VirtualAlloc(
        NULL, g->rva + 8 + bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (image == NULL) { CHECK(0, "allocate a fake module"); return; }
    array = image + g->rva + 8;
    if (g->rva_is_pointer) {
        *(unsigned char **)(image + g->rva) = array;
    } else {
        array = image + g->rva;
    }

    /* Villager 1: a child with both parents recorded. */
    rec = array + g->base;
    rec[g->active] = 1;
    put_name(rec, g->name, "Kiwi", g->name_cap);
    put_int(rec, g->age, 240);
    put_int(rec, g->head, 7);
    put_int(rec, g->body, 3);
    put_name(rec, g->parent_father_name, "Budi", g->parent_name_cap);
    put_name(rec, g->parent_mother_name, "Iriatai", g->parent_name_cap);
    put_int(rec, g->parent_father_head, 11);
    put_int(rec, g->parent_father_body, 23);
    put_int(rec, g->parent_mother_head, 27);
    put_int(rec, g->parent_mother_body, 24);

    /* Villager 2: a founder, with no recorded parents at all. */
    rec = array + g->base + g->stride;
    rec[g->active] = 1;
    put_name(rec, g->name, "Budi", g->name_cap);
    put_int(rec, g->age, 900);
    put_int(rec, g->head, 11);
    put_int(rec, g->body, 23);
    put_name(rec, g->parent_father_name, "", g->parent_name_cap);
    put_name(rec, g->parent_mother_name, "", g->parent_name_cap);

    remove_log();
    CHECK(write(g->id, image, "Village: Harness (Save 1)\n") == 2,
          "the export writes both villagers");
    log = read_log();
    if (log == NULL) { CHECK(0, "the roster file was written"); VirtualFree(image, 0, MEM_RELEASE); return; }

    block = villager_block(log, 1, &length);
    CHECK(block != NULL, "the child's block is present");
    CHECK(block_has(block, length, "Name: Kiwi"), "the child's name");
    CHECK(block_has(block, length, "  Parents:"), "a Parents block is printed");
    CHECK(block_has(block, length, "    Father: Budi"), "the father is NAMED");
    CHECK(block_has(block, length, "    Mother: Iriatai"), "the mother is NAMED");
    CHECK(block_has(block, length, "      Head: 11"), "the father's head");
    CHECK(block_has(block, length, "      Body: 23"), "the father's body");
    CHECK(block_has(block, length, "      Head: 27"), "the mother's head");
    CHECK(block_has(block, length, "      Body: 24"), "the mother's body");

    block = villager_block(log, 2, &length);
    CHECK(block != NULL, "the founder's block is present");
    CHECK(block_has(block, length, "Name: Budi"), "the founder's name");
    CHECK(!block_has(block, length, "Parents:"),
          "a villager with no recorded parents gets NO Parents block");

    free(log);
    remove_log();
    VirtualFree(image, 0, MEM_RELEASE);
}

int main(int argc, char **argv) {
    HMODULE dll;
    write_population_t write;
    size_t i;
    if (argc < 2) {
        printf("usage: %s \"<path to VVFP Population Export.dll>\"\n", argv[0]);
        return 2;
    }
    dll = LoadLibraryA(argv[1]);
    if (dll == NULL) {
        printf("could not load %s (error %lu)\n", argv[1], GetLastError());
        return 2;
    }
    write = (write_population_t)GetProcAddress(dll, "WriteVillagePopulation");
    if (write == NULL) {
        printf("WriteVillagePopulation is not exported\n");
        return 2;
    }
    for (i = 0; i < sizeof GAMES / sizeof GAMES[0]; ++i) {
        run_game(&GAMES[i], write);
    }
    printf("\n%d failure(s)\n", g_failures);
    return g_failures ? 1 : 0;
}
