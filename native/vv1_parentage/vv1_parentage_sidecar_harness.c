/* The VV1 parentage sidecar on disk: a file that is there but cannot be read
   must never be replaced, and one that is not a sidecar is set aside first.

   A New Home keeps no parents on a villager's record, so the sidecar is the
   only copy there is; an empty table written over it is a permanent loss.
   This harness compiles vv1_parentage.c itself into a 32-bit console program
   and drives the real sync, load and save code against synthetic villager
   arrays.  Only the Documents folder is redirected -- to the folder given on
   the command line -- so every file it touches is inside that folder.  The
   open and tick-count calls are wrapped only to count retries and to make
   the set-aside name predictable; both pass straight through.

   Built and run by tests/test_vv1_parentage_sidecar.py. */
#include <windows.h>
#include <shlobj.h>
#include <sddl.h>
#include <stdio.h>
#include <string.h>

static char g_docs[MAX_PATH];
static int g_opens;               /* OPEN_EXISTING opens: the sidecar reads */
static DWORD g_ticks = 12345u;

static HRESULT WINAPI harness_docs(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

static HANDLE WINAPI harness_open(LPCSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                  DWORD disposition, DWORD flags, HANDLE templ) {
    if (disposition == OPEN_EXISTING) {
        ++g_opens;
    }
    return CreateFileA(path, access, share, sa, disposition, flags, templ);
}

static DWORD WINAPI harness_ticks(void) {
    return g_ticks;
}

#define SHGetFolderPathA harness_docs
#define CreateFileA harness_open
#define GetTickCount harness_ticks
#include "vv1_parentage.c"
#undef SHGetFolderPathA
#undef CreateFileA
#undef GetTickCount

#define SLOT 1
#define FRAMES 120

static unsigned char village_a[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char village_b[VV1_RECORD_COUNT * VV1_RECORD_STRIDE];
static unsigned char good[16 + sizeof(g_roster) + sizeof(g_entries)];
static DWORD good_size;
static char path[MAX_PATH];
static int failures;

static void check(int ok, const char *name) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) {
        ++failures;
    }
}

static void put(unsigned char *records, int index, const char *name, int male, int scalar) {
    unsigned char *rec = records + (unsigned int)index * VV1_RECORD_STRIDE;
    rec[VV1_OCCUPIED_OFFSET] = 1;
    *(int *)(rec + VV1_GENDER_OFFSET) = male ? 1 : 2;
    *(int *)(rec + VV1_VARIANT_OFFSET) = scalar;
    *(int *)(rec + VV1_AGE_OFFSET) = 25 * VV1_UNITS_PER_YEAR;
    lstrcpyA((char *)rec + VV1_NAME_OFFSET, name);
}

/* The companion as a fresh process finds it. */
static void fresh(void) {
    memset(g_entries, 0, sizeof(g_entries));
    memset(g_roster, 0, sizeof(g_roster));
    g_loaded_slot = 0;
    g_strikes = 0;
    g_have_prev = 0;
    g_blocked_slot = 0;
    g_blocked_wait = 0;
    g_may_replace = 0;
    g_opens = 0;
}

static int read_all(const char *p, unsigned char *out, DWORD cap, DWORD *size) {
    HANDLE h = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(h, out, cap, size, NULL);
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int write_all(const char *p, const void *data, DWORD n) {
    HANDLE h = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    DWORD wrote = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(h, data, n, &wrote, NULL) && wrote == n;
    CloseHandle(h);
    return ok ? 1 : 0;
}

static int same_as(const char *p, const void *data, DWORD n) {
    static unsigned char buf[sizeof(good) + 64];
    DWORD size = 0;
    return read_all(p, buf, sizeof(buf), &size) && size == n && memcmp(buf, data, n) == 0;
}

static int set_dacl(const char *p, const char *sddl) {
    PSECURITY_DESCRIPTOR sd = NULL;
    BOOL ok;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorA(sddl, SDDL_REVISION_1, &sd, NULL)) {
        return 0;
    }
    ok = SetFileSecurityA(p, DACL_SECURITY_INFORMATION, sd);
    LocalFree(sd);
    return ok ? 1 : 0;
}

/* Readable by nobody, yet replaceable and deletable by anybody: exactly the
   file the old code overwrote.  (An open handle cannot model this, because
   Windows refuses to replace a file that has an open handle.) */
static int deny_read(const char *p) {
    return set_dacl(p, "D:(D;;0x1;;;WD)(A;;FA;;;WD)");
}

static int allow_all(const char *p) {
    return set_dacl(p, "D:(A;;FA;;;WD)");
}

/* Village A's good sidecar: Alba is the daughter of Bram and Cora. */
static void write_good_sidecar(void) {
    DeleteFileA(path);
    fresh();
    vv1_take_roster(village_a, g_roster);
    lstrcpyA(g_entries[5].father_name, "Bram");
    lstrcpyA(g_entries[5].mother_name, "Cora");
    g_entries[5].father_head = 4;
    g_entries[5].father_body = 5;
    g_entries[5].mother_head = 6;
    g_entries[5].mother_body = 7;
    g_may_replace = 1;
    if (!vv1_parents_save(SLOT, village_a) || !read_all(path, good, sizeof(good), &good_size)) {
        printf("FAIL setup: could not write the good sidecar\n");
        ++failures;
    }
    fresh();
}

/* Frames of play: every frame the village is known a conception is saved,
   which is the most any export could write.  Returns how many frames the
   companion said it knew the village. */
static int play(const unsigned char *records, int frames) {
    int known = 0;
    int f;
    for (f = 0; f < frames; ++f) {
        int slot = vv1_parents_sync_core(SLOT, records);
        if (slot) {
            ++known;
            vv1_parents_save(slot, records);
        }
    }
    return known;
}

static int aside_exists(DWORD ticks, int n) {
    char p[MAX_PATH];
    wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

static int aside_same_as(DWORD ticks, int n, const void *data, DWORD size) {
    char p[MAX_PATH];
    wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
    return same_as(p, data, size);
}

static void remove_asides(DWORD ticks) {
    char p[MAX_PATH];
    int n;
    for (n = 0; n < 1000; ++n) {
        wsprintfA(p, "%s.unreadable-%lu-%d", path, (unsigned long)ticks, n);
        DeleteFileA(p);
    }
}

static int loaded_alba(void) {
    return lstrcmpA(g_entries[5].father_name, "Bram") == 0
        && lstrcmpA(g_entries[5].mother_name, "Cora") == 0
        && g_entries[5].father_head == 4 && g_entries[5].mother_body == 7;
}

int main(int argc, char **argv) {
    int known;
    int opens;
    int f;
    HANDLE lock;
    static const char junk[] = "not a parentage sidecar";

    if (argc < 2) {
        printf("usage: harness <scratch folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    put(village_a, 3, "Bram", 1, 11);
    put(village_a, 4, "Cora", 0, 12);
    put(village_a, 5, "Alba", 0, 13);
    put(village_b, 3, "Dax", 1, 21);
    put(village_b, 4, "Eda", 0, 22);
    if (!vv1_parents_path(path, sizeof(path), SLOT)) {
        printf("FAIL setup: no sidecar path\n");
        return 1;
    }

    /* 1. A sidecar nobody may read -- the lock, denial or scanner case. */
    write_good_sidecar();
    check(deny_read(path), "setup: the sidecar is made unreadable");
    known = play(village_a, FRAMES);
    check(known == 0, "an unreadable sidecar leaves the village unknown, never committed empty");
    opens = g_opens;
    check(opens >= 2 && opens <= FRAMES / VV1_NEW_VILLAGE_STRIKES + 1,
          "an unreadable sidecar is retried each strike window, not every frame");
    check(!aside_exists(g_ticks, 0), "an unreadable sidecar is not set aside");
    check(allow_all(path), "setup: the sidecar is readable again");
    check(same_as(path, good, good_size), "... and the unreadable sidecar is left byte-for-byte unchanged");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once readable, the parents are loaded from the file");

    /* 2. The same while the village already on hand turns into strangers
          (the same-slot path) and the file is unreadable. */
    write_good_sidecar();
    play(village_a, 2);
    check(loaded_alba(), "setup: village A is loaded");
    check(deny_read(path), "setup: the sidecar is made unreadable");
    known = play(village_b, FRAMES);
    check(known == 0, "strangers with an unreadable sidecar leave the village unknown");
    check(loaded_alba(), "... and the table on hand is not emptied");
    check(allow_all(path), "setup: the sidecar is readable again");
    check(same_as(path, good, good_size), "... and that sidecar is left byte-for-byte unchanged");

    /* 3. A file held open with no sharing, then released. */
    write_good_sidecar();
    lock = CreateFileA(path, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);
    check(lock != INVALID_HANDLE_VALUE, "setup: the sidecar is held open without sharing");
    known = play(village_a, FRAMES);
    CloseHandle(lock);
    check(known == 0, "a sidecar held open leaves the village unknown");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once released, the parents are loaded from the file");
    check(g_entries[5].father_head == 4, "... and the saves after it keep them");

    /* 3b. A file that opens but whose bytes are locked: the read fails, and
           that is a lock to wait out, not a file to set aside. */
    write_good_sidecar();
    lock = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    check(lock != INVALID_HANDLE_VALUE && LockFile(lock, 0, 0, 0xFFFFFFFFu, 0),
          "setup: the sidecar's bytes are locked");
    known = play(village_a, FRAMES);
    UnlockFile(lock, 0, 0, 0xFFFFFFFFu, 0);
    CloseHandle(lock);
    check(known == 0 && !aside_exists(g_ticks, 0), "a sidecar whose read fails is waited for, not set aside");
    check(same_as(path, good, good_size), "... and it is left byte-for-byte unchanged");
    known = play(village_a, VV1_NEW_VILLAGE_STRIKES + 2);
    check(known > 0 && loaded_alba(), "once unlocked, the parents are loaded from the file");

    /* 4. A file that is not a sidecar is set aside under an unused name. */
    DeleteFileA(path);
    remove_asides(g_ticks);
    fresh();
    check(write_all(path, junk, sizeof(junk)), "setup: a short, foreign file sits at the sidecar's name");
    {
        char taken[MAX_PATH];
        wsprintfA(taken, "%s.unreadable-%lu-0", path, (unsigned long)g_ticks);
        check(write_all(taken, "earlier", 7), "setup: the first set-aside name is already taken");
    }
    known = play(village_a, FRAMES);
    check(aside_same_as(g_ticks, 1, junk, sizeof(junk)), "an invalid sidecar is set aside byte-for-byte");
    check(aside_same_as(g_ticks, 0, "earlier", 7), "... never over a file already set aside");
    check(known > 0, "... and the village then starts a table of its own");
    {
        DWORD size = 0;
        unsigned char *buf = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, sizeof(good));
        int ok = buf && read_all(path, buf, sizeof(good), &size) && size == sizeof(good) - 4
                 && *(unsigned int *)buf == VV1_PARENTS_MAGIC;
        check(ok, "... written as a sound sidecar");
        if (buf) HeapFree(GetProcessHeap(), 0, buf);
    }

    /* 5. A full-length file with a foreign magic (a 'VP01' file). */
    DeleteFileA(path);
    remove_asides(g_ticks);
    write_good_sidecar();
    good[3] = '1';                                   /* 'VP02' -> 'VP01' */
    check(write_all(path, good, good_size), "setup: a full-length 'VP01' file");
    play(village_a, FRAMES);
    check(aside_same_as(g_ticks, 0, good, good_size), "a sidecar with a foreign magic is set aside, not overwritten");
    good[3] = '2';

    /* 6. An invalid file that cannot be set aside is left alone. */
    DeleteFileA(path);
    remove_asides(g_ticks);
    fresh();
    check(write_all(path, junk, sizeof(junk)), "setup: a foreign file at the sidecar's name");
    for (f = 0; f < 1000; ++f) {
        char taken[MAX_PATH];
        wsprintfA(taken, "%s.unreadable-%lu-%d", path, (unsigned long)g_ticks, f);
        write_all(taken, "x", 1);
    }
    known = play(village_a, FRAMES);
    check(known == 0, "an invalid sidecar that cannot be set aside leaves the village unknown");
    check(same_as(path, junk, sizeof(junk)), "... and nothing is written over it");
    remove_asides(g_ticks);

    /* 7. No file at all: the village starts empty and a file is written
          (unchanged behaviour). */
    DeleteFileA(path);
    fresh();
    known = play(village_a, FRAMES);
    check(known > 0 && GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES,
          "with no sidecar the village starts empty and one is written");

    /* 8. A file that appears after an empty start is read, not replaced. */
    write_good_sidecar();
    {
        static unsigned char keep[sizeof(good)];
        DWORD keep_size = good_size;
        memcpy(keep, good, good_size);
        DeleteFileA(path);
        fresh();
        for (f = 0; f < VV1_NEW_VILLAGE_STRIKES + 1 && !vv1_parents_sync_core(SLOT, village_a); ++f) {
        }
        check(g_loaded_slot == SLOT, "setup: committed with no sidecar on disk");
        check(write_all(path, keep, keep_size), "setup: the sidecar reappears (a sync restores it)");
        vv1_parents_save(SLOT, village_a);
        check(same_as(path, keep, keep_size), "a sidecar that appears after an empty start is not replaced");
        known = play(village_a, 3);
        check(known > 0 && loaded_alba(), "... and it is read on the next frame");
    }

    /* 9. Another village's sound file is still superseded after the strike
          window: Start Over keeps the slot (unchanged behaviour). */
    write_good_sidecar();
    known = play(village_b, FRAMES);
    {
        static unsigned char now[sizeof(good)];
        DWORD size = 0;
        int ok = read_all(path, now, sizeof(now), &size) && size == good_size
                 && memcmp(now + 12, good + 12, sizeof(g_roster)) != 0;
        check(known > 0 && ok, "another village's sidecar is superseded after the strike window");
    }

    /* 10. This village's own file loads at once. */
    write_good_sidecar();
    known = play(village_a, 1);
    check(known == 1 && loaded_alba(), "this village's own sidecar loads at once");

    DeleteFileA(path);
    printf("%d failure(s)\n", failures);
    return failures ? 1 : 0;
}
