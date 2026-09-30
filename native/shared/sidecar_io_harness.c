/* Runtime harness for native/shared/sidecar_io.h -- the load/publish path every
   game's heathen-mask sidecar now goes through.  32-bit, like the companions.

   Everything happens in a scratch folder under %TEMP% that this harness
   creates and removes; it never touches Documents or any game's saves.

   What it proves, against real files:
     - a write that fails partway (an error, or a short count) leaves the
       published file byte-for-byte intact and no temporary file behind;
     - a present file that fails validation (wrong magic, short) is moved to
       an unused "<name>.unreadable-<ticks>-<n>" before anything is written,
       and a set-aside never replaces an earlier one;
     - a present file that cannot be opened (read denied by its ACL, or held
       without sharing) is neither read, moved nor written, even though the
       replace itself would have succeeded, and is retried only after the
       retry window;
     - only a genuinely missing file starts empty and may be created.

   Usage:  sidecar_io_harness.exe
   Exit code 0 when every check passes. */
#include <windows.h>
#include <sddl.h>
#include <stdio.h>
#include <string.h>

/* The two seams sidecar_io.h leaves for exactly this: a writer that can fail
   partway, and a clock the harness steps by hand. */
static int g_fail_mode;       /* 0 pass-through, 1 error, 2 short count */
static int g_fail_on_call;    /* 1-based WriteFile call to fail */
static int g_write_calls;
static DWORD g_now = 100000u;

static BOOL WINAPI harness_write(HANDLE h, LPCVOID data, DWORD size,
                                 LPDWORD wrote, LPOVERLAPPED ov) {
    ++g_write_calls;
    if (g_fail_mode != 0 && g_write_calls == g_fail_on_call) {
        DWORD half = size / 2, done = 0;
        /* Put real bytes on disk first, as a crash mid-write would. */
        WriteFile(h, data, half, &done, ov);
        *wrote = done;
        if (g_fail_mode == 1) {
            SetLastError(ERROR_DISK_FULL);
            return FALSE;
        }
        return TRUE;          /* "succeeded" with fewer bytes than asked */
    }
    return WriteFile(h, data, size, wrote, ov);
}
#define VV_SIDECAR_WRITE_FILE harness_write
#define VV_SIDECAR_TICKS() (g_now)
#include "sidecar_io.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static char g_dir[MAX_PATH];
static char g_path[MAX_PATH];

#define MAGIC 0x31304D56u
#define TABLE 128
#define FILE_BYTES (4 + TABLE)

static int valid(const unsigned char *d, DWORD len, void *ctx) {
    unsigned int m;
    (void)ctx;
    if (len < FILE_BYTES) return 0;
    memcpy(&m, d, 4);
    return m == MAGIC;
}

static void put_file(const char *path, const void *data, DWORD n) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD w = 0;
    if (h == INVALID_HANDLE_VALUE) { printf("  (cannot create %s)\n", path); failures++; return; }
    WriteFile(h, data, n, &w, NULL);
    CloseHandle(h);
}

/* Whole file, or -1 when it cannot be read. */
static int get_file(const char *path, unsigned char *out, DWORD cap) {
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) return -1;
    if (!ReadFile(h, out, cap, &got, NULL)) got = 0;
    CloseHandle(h);
    return (int)got;
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

static int same_file(const char *path, const unsigned char *want, int n) {
    unsigned char buf[4096];
    int got = get_file(path, buf, sizeof(buf));
    return got == n && memcmp(buf, want, (size_t)n) == 0;
}

/* Names in g_dir matching "<pattern>"; copies the first into first[]. */
static int count_matching(const char *pattern, char *first) {
    char spec[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE f;
    int n = 0;
    wsprintfA(spec, "%s\\%s", g_dir, pattern);
    f = FindFirstFileA(spec, &fd);
    if (f == INVALID_HANDLE_VALUE) return 0;
    do {
        if (n == 0 && first) wsprintfA(first, "%s\\%s", g_dir, fd.cFileName);
        ++n;
    } while (FindNextFileA(f, &fd));
    FindClose(f);
    return n;
}

static void wipe_dir(void) {
    char spec[MAX_PATH], one[MAX_PATH];
    WIN32_FIND_DATAA fd;
    HANDLE f;
    wsprintfA(spec, "%s\\*", g_dir);
    f = FindFirstFileA(spec, &fd);
    if (f == INVALID_HANDLE_VALUE) return;
    do {
        if (fd.cFileName[0] == '.') continue;
        wsprintfA(one, "%s\\%s", g_dir, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) RemoveDirectoryA(one);
        else { SetFileAttributesA(one, FILE_ATTRIBUTE_NORMAL); DeleteFileA(one); }
    } while (FindNextFileA(f, &fd));
    FindClose(f);
}

static int set_dacl(const char *path, const char *sddl) {
    PSECURITY_DESCRIPTOR sd = NULL;
    BOOL ok;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorA(
            sddl, SDDL_REVISION_1, &sd, NULL)) {
        return 0;
    }
    ok = SetFileSecurityA(path, DACL_SECURITY_INFORMATION, sd);
    LocalFree(sd);
    return ok ? 1 : 0;
}

static void payload(unsigned char *out, unsigned char fill) {
    unsigned int m = MAGIC;
    memcpy(out, &m, 4);
    memset(out + 4, fill, TABLE);
}

static int publish(vv_sidecar_gate *g, const unsigned char *file) {
    const void *parts[2];
    DWORD sizes[2];
    parts[0] = file;      sizes[0] = 4;
    parts[1] = file + 4;  sizes[1] = TABLE;
    g_write_calls = 0;
    return vv_sidecar_publish(g, g_path, parts, sizes, 2);
}

static int load(vv_sidecar_gate *g, unsigned char *buf, DWORD *len) {
    return vv_sidecar_load(g, g_path, buf, FILE_BYTES, len, valid, NULL);
}

static void fresh_gate(vv_sidecar_gate *g, int key) {
    memset(g, 0, sizeof(*g));
    g->key = -12345;
    vv_sidecar_gate_bind(g, key);
}

static void test_missing_file_starts_empty(void) {
    vv_sidecar_gate g;
    unsigned char buf[FILE_BYTES], want[FILE_BYTES];
    DWORD len = 99;
    printf("missing file\n");
    wipe_dir();
    fresh_gate(&g, 1);
    CHECK(publish(&g, want) == 0, "nothing is written before the load");
    CHECK(!exists(g_path), "  ...and no file appears");
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_MISSING && len == 0,
          "a missing file loads as MISSING");
    CHECK(vv_sidecar_gate_ready(&g, 1), "a missing file settles the gate");
    payload(want, 3);
    CHECK(publish(&g, want) == 1, "the first write creates it");
    CHECK(same_file(g_path, want, FILE_BYTES), "  ...with exactly the payload");
    CHECK(count_matching("*.tmp", NULL) == 0, "  ...and no temporary file is left");
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_VALID && len == FILE_BYTES
          && memcmp(buf, want, FILE_BYTES) == 0, "it loads back VALID");
}

static void test_failed_write_keeps_the_old_file(void) {
    vv_sidecar_gate g;
    unsigned char old[FILE_BYTES], next[FILE_BYTES], buf[FILE_BYTES];
    DWORD len;
    int mode, call;
    printf("interrupted and failed writes\n");
    for (mode = 1; mode <= 2; ++mode) {
        for (call = 1; call <= 2; ++call) {
            wipe_dir();
            payload(old, 0x11);
            put_file(g_path, old, FILE_BYTES);
            fresh_gate(&g, 1);
            CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_VALID, "the old file loads");
            payload(next, 0x22);
            g_fail_mode = mode;
            g_fail_on_call = call;
            CHECK(publish(&g, next) == 0, "a %s on write %d is reported",
                  mode == 1 ? "write error" : "short write", call);
            g_fail_mode = 0;
            CHECK(same_file(g_path, old, FILE_BYTES),
                  "  ...and the published file is byte-for-byte unchanged");
            CHECK(count_matching("*.tmp", NULL) == 0, "  ...and the temporary file is removed");
        }
    }
    /* The temporary name cannot even be created: a folder occupies it. */
    wipe_dir();
    {
        char tmp[MAX_PATH];
        payload(old, 0x33);
        put_file(g_path, old, FILE_BYTES);
        fresh_gate(&g, 1);
        load(&g, buf, &len);
        wsprintfA(tmp, "%s.tmp", g_path);
        CreateDirectoryA(tmp, NULL);
        payload(next, 0x44);
        CHECK(publish(&g, next) == 0, "an uncreatable temporary file is reported");
        CHECK(same_file(g_path, old, FILE_BYTES), "  ...and the published file is unchanged");
        RemoveDirectoryA(tmp);
    }
    /* And the successful path really does replace it. */
    payload(next, 0x55);
    CHECK(publish(&g, next) == 1 && same_file(g_path, next, FILE_BYTES),
          "a complete write replaces the file");
}

static void check_set_aside(const char *what, const unsigned char *bad, DWORD n) {
    vv_sidecar_gate g;
    unsigned char buf[FILE_BYTES], next[FILE_BYTES];
    char aside[MAX_PATH];
    DWORD len = 99;
    wipe_dir();
    put_file(g_path, bad, n);
    fresh_gate(&g, 2);
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_SET_ASIDE && len == 0,
          "%s: loads as SET_ASIDE, not as data", what);
    CHECK(!exists(g_path), "%s: the original name is freed", what);
    CHECK(count_matching("*.unreadable-*", aside) == 1, "%s: one set-aside copy exists", what);
    CHECK(same_file(aside, bad, (int)n), "%s: it holds the original bytes", what);
    CHECK(vv_sidecar_gate_ready(&g, 2), "%s: the gate settles", what);
    payload(next, 0x66);
    CHECK(publish(&g, next) == 1 && same_file(g_path, next, FILE_BYTES),
          "%s: a fresh file is then written", what);
    CHECK(same_file(aside, bad, (int)n), "%s: and the set-aside copy is untouched", what);
}

static void test_invalid_file_is_set_aside(void) {
    unsigned char bad[FILE_BYTES];
    printf("present but invalid\n");
    payload(bad, 0x07);
    bad[0] ^= 0xFF;                                  /* wrong magic */
    check_set_aside("wrong magic", bad, FILE_BYTES);
    payload(bad, 0x07);
    check_set_aside("short file", bad, FILE_BYTES - 1);
    check_set_aside("empty file", bad, 0);
}

static void test_set_aside_never_replaces(void) {
    vv_sidecar_gate g;
    unsigned char bad[8], buf[FILE_BYTES];
    char aside[MAX_PATH];
    DWORD len;
    int i, ok = 1;
    printf("set-aside names never collide\n");
    wipe_dir();
    /* Same tick for all five, so only the -<n> suffix can tell them apart. */
    for (i = 0; i < 5; ++i) {
        memset(bad, 'a' + i, sizeof(bad));
        put_file(g_path, bad, sizeof(bad));
        fresh_gate(&g, 3);
        if (load(&g, buf, &len) != VV_SIDECAR_LOAD_SET_ASIDE) ok = 0;
    }
    CHECK(ok, "five invalid files in the same tick are each set aside");
    CHECK(count_matching("*.unreadable-*", NULL) == 5, "  ...under five distinct names");
    for (i = 0; i < 5; ++i) {
        memset(bad, 'a' + i, sizeof(bad));
        wsprintfA(aside, "%s.unreadable-%lu-%d", g_path, (unsigned long)g_now, i);
        CHECK(same_file(aside, bad, sizeof(bad)), "  ...%s holds file %d", strrchr(aside, '\\') + 1, i);
    }
}

static void test_unreadable_file_is_left_alone(void) {
    vv_sidecar_gate g;
    unsigned char old[FILE_BYTES], next[FILE_BYTES], buf[FILE_BYTES];
    DWORD len;
    printf("present but unopenable (read denied by ACL)\n");
    wipe_dir();
    payload(old, 0x5A);
    put_file(g_path, old, FILE_BYTES);
    if (!set_dacl(g_path, "D:(D;;0x1;;;WD)(A;;FA;;;WD)")) {
        printf("  FAIL could not apply the deny-read ACL\n");
        failures++;
        return;
    }
    CHECK(get_file(g_path, buf, sizeof(buf)) < 0, "the file really cannot be opened for reading");
    {
        /* The same ACL does NOT stop either old writer, which is the point:
           proven on a sibling so the file under test is not disturbed. */
        char probe[MAX_PATH], probe_tmp[MAX_PATH];
        HANDLE h;
        wsprintfA(probe, "%s\\probe.dat", g_dir);
        wsprintfA(probe_tmp, "%s\\probe.dat.new", g_dir);
        put_file(probe, old, FILE_BYTES);
        set_dacl(probe, "D:(D;;0x1;;;WD)(A;;FA;;;WD)");
        h = CreateFileA(probe, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        CHECK(h != INVALID_HANDLE_VALUE,
              "  (the old in-place CREATE_ALWAYS writer could truncate it)");
        if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
        put_file(probe_tmp, old, FILE_BYTES);
        CHECK(MoveFileExA(probe_tmp, probe, MOVEFILE_REPLACE_EXISTING),
              "  (the old temp-and-replace writer could replace it)");
        SetFileAttributesA(probe, FILE_ATTRIBUTE_NORMAL);
        set_dacl(probe, "D:(A;;FA;;;WD)");
        DeleteFileA(probe);
        DeleteFileA(probe_tmp);
    }
    fresh_gate(&g, 4);
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_BLOCKED && len == 0, "it loads as BLOCKED");
    CHECK(!vv_sidecar_gate_ready(&g, 4), "the gate does not settle");
    CHECK(count_matching("*.unreadable-*", NULL) == 0, "it is not moved aside");
    payload(next, 0x77);
    CHECK(publish(&g, next) == 0, "a write is refused, though the replace would succeed");
    CHECK(count_matching("*.tmp", NULL) == 0, "  ...and not even a temporary file is created");
    /* The lock clears; inside the retry window nothing is retried. */
    set_dacl(g_path, "D:(A;;FA;;;WD)");
    CHECK(same_file(g_path, old, FILE_BYTES), "the file is byte-for-byte what it was");
    CHECK(vv_sidecar_gate_throttled(&g), "the retry is throttled");
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_BLOCKED, "  ...a load inside the window does no I/O");
    g_now += VV_SIDECAR_RETRY_MS - 1;
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_BLOCKED, "  ...even 1 ms before it ends");
    g_now += 1;
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_VALID && memcmp(buf, old, FILE_BYTES) == 0,
          "after the window the retry reads the real masks");
    CHECK(publish(&g, next) == 1, "and only then may it be written");
}

static void test_locked_file_is_left_alone(void) {
    vv_sidecar_gate g;
    unsigned char old[FILE_BYTES], bad[FILE_BYTES], next[FILE_BYTES], buf[FILE_BYTES];
    DWORD len;
    HANDLE lock;
    printf("present but locked by another handle\n");
    wipe_dir();
    payload(old, 0x2C);
    put_file(g_path, old, FILE_BYTES);
    lock = CreateFileA(g_path, GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    fresh_gate(&g, 5);
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_BLOCKED, "a sharing violation loads as BLOCKED");
    payload(next, 0x78);
    g_now += VV_SIDECAR_RETRY_MS;
    CHECK(publish(&g, next) == 0, "a write is refused");
    CloseHandle(lock);
    CHECK(same_file(g_path, old, FILE_BYTES), "the file is unchanged");

    /* Invalid, but held without delete sharing: it cannot be moved aside, so
       it must not be written either. */
    wipe_dir();
    payload(bad, 0x01);
    bad[1] ^= 0xFF;
    put_file(g_path, bad, FILE_BYTES);
    lock = CreateFileA(g_path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    fresh_gate(&g, 6);
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_BLOCKED,
          "an invalid file that will not move aside loads as BLOCKED");
    CloseHandle(lock);
    g_now += VV_SIDECAR_RETRY_MS;
    CHECK(publish(&g, next) == 0, "  ...and is not written");
    CHECK(same_file(g_path, bad, FILE_BYTES), "  ...and is unchanged");
    CHECK(load(&g, buf, &len) == VV_SIDECAR_LOAD_SET_ASIDE, "  ...once released it is set aside");
}

static void test_gate_is_per_slot_and_per_path(void) {
    vv_sidecar_gate g;
    unsigned char old[FILE_BYTES], next[FILE_BYTES], buf[FILE_BYTES];
    char other[MAX_PATH];
    DWORD len;
    const void *parts[2];
    DWORD sizes[2];
    printf("the gate belongs to one slot and one file\n");
    wipe_dir();
    payload(old, 0x3E);
    put_file(g_path, old, FILE_BYTES);
    wsprintfA(other, "%s\\other.dat", g_dir);
    put_file(other, old, FILE_BYTES);
    fresh_gate(&g, 1);
    load(&g, buf, &len);
    payload(next, 0x4F);
    parts[0] = next;     sizes[0] = 4;
    parts[1] = next + 4; sizes[1] = TABLE;
    CHECK(vv_sidecar_publish(&g, other, parts, sizes, 2) == 0,
          "a gate settled for one file does not permit writing another");
    CHECK(same_file(other, old, FILE_BYTES), "  ...which is unchanged");
    vv_sidecar_gate_bind(&g, 2);
    CHECK(!vv_sidecar_gate_ready(&g, 2) && publish(&g, next) == 0,
          "a slot change forgets the earlier load");
    CHECK(same_file(g_path, old, FILE_BYTES), "  ...and nothing was written");
    vv_sidecar_gate_block(&g);
    CHECK(vv_sidecar_gate_throttled(&g), "a blocked path build is throttled too");
    vv_sidecar_gate_bind(&g, 3);
    CHECK(!vv_sidecar_gate_throttled(&g), "  ...but not into the next slot");
}

int main(void) {
    char temp[MAX_PATH];
    if (!GetTempPathA(sizeof(temp), temp)) return 2;
    wsprintfA(g_dir, "%svvfp_sidecar_io_harness_%lu", temp, (unsigned long)GetCurrentProcessId());
    CreateDirectoryA(g_dir, NULL);
    wsprintfA(g_path, "%s\\Village Masks - Save 1.dat", g_dir);

    test_missing_file_starts_empty();
    test_failed_write_keeps_the_old_file();
    test_invalid_file_is_set_aside();
    test_set_aside_never_replaces();
    test_unreadable_file_is_left_alone();
    test_locked_file_is_left_alone();
    test_gate_is_per_slot_and_per_path();

    if (exists(g_path)) set_dacl(g_path, "D:(A;;FA;;;WD)");
    wipe_dir();
    RemoveDirectoryA(g_dir);
    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
