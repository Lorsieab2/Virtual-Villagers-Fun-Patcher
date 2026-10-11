/* native/shared/foreign_sidecar.h against real files in a scratch folder
   given on the command line (nothing else is touched).
   Built and run by tests/test_foreign_sidecar.py. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static DWORD g_ticks = 4242u;
#define VV_FOREIGN_TICKS() g_ticks
#include "foreign_sidecar.h"

static int failures;

static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) {
        ++failures;
    }
}

static int write_bytes(const char *p, const char *text) {
    HANDLE h = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    DWORD wrote = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(h, text, (DWORD)lstrlenA(text), &wrote, NULL);
    CloseHandle(h);
    return ok && wrote == (DWORD)lstrlenA(text);
}

static int holds(const char *p, const char *text) {
    char buf[256];
    DWORD got = 0;
    HANDLE h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ReadFile(h, buf, sizeof buf - 1, &got, NULL);
    CloseHandle(h);
    buf[got] = 0;
    return lstrcmpA(buf, text) == 0;
}

static int exists(const char *p) {
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

int main(int argc, char **argv) {
    char path[MAX_PATH], aside0[MAX_PATH], aside1[MAX_PATH];
    unsigned int a[6] = { 11, 12, 13, 0, 0, 0 };
    unsigned int founders[6] = { 91, 92, 93, 94, 95, 0 };
    unsigned int packed[6] = { 12, 13, 0, 0, 0, 0 };
    unsigned int none[6] = { 0 };
    unsigned char empty[8] = { 0 }, masked[8] = { 0, 0, 0x21, 0 };
    int foreign, nothing;
    if (argc < 2) {
        printf("usage: harness <scratch folder>\n");
        return 2;
    }
    wsprintfA(path, "%s\\Village Masks - Save 1.dat", argv[1]);
    wsprintfA(aside0, "%s.another-village-4242-0", path);
    wsprintfA(aside1, "%s.another-village-4242-1", path);

    check(vv_roster_shares(6, a, founders) == 0, "the title screen's founders share nobody with the village");
    check(vv_roster_shares(6, a, packed) == 1, "the same village packed into other records shares its villagers");
    check(vv_roster_shares(6, a, none) == -1 && vv_roster_shares(6, none, a) == -1,
          "a roster that names nobody gives no verdict");
    check(!vv_table_any(empty, 8) && vv_table_any(masked, 8), "an empty table is told from one with a mask");

    write_bytes(path, "village A");
    foreign = 1;
    check(!vv_foreign_before_write(&foreign, path, 0, &nothing) && nothing && foreign
              && holds(path, "village A") && !exists(aside0),
          "an empty table is never written over another village's file");
    check(vv_foreign_before_write(&foreign, path, 1, &nothing) && !nothing && !foreign
              && !exists(path) && holds(aside0, "village A"),
          "a table with a mask moves the other village's file aside first, byte for byte");
    write_bytes(path, "village B");
    foreign = 1;
    check(vv_foreign_before_write(&foreign, path, 1, &nothing) && holds(aside0, "village A")
              && holds(aside1, "village B"),
          "a second set-aside never replaces the first");
    foreign = 0;
    check(vv_foreign_before_write(&foreign, path, 0, &nothing) && !nothing,
          "a village's own file is written as before");
    foreign = 1;
    check(vv_foreign_before_write(&foreign, path, 1, &nothing) && !foreign,
          "with no file there, there is nothing to move aside");
    DeleteFileA(aside0);
    DeleteFileA(aside1);
    DeleteFileA(path);
    printf("%d failure(s)\n", failures);
    return failures ? 1 : 0;
}
