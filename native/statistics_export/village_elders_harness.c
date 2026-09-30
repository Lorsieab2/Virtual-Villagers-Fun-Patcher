/* Harness for village_elders.c: runs the owner's mandatory Village Elder
   tests (docs/village-statistics-directive.md XIV, A-F) and the .dat safety
   cases against the real code, on synthetic villager and memorial arrays,
   writing only inside the temp folder given on the command line.

   Built and run by tests/test_village_elders.py. Prints one PASS/FAIL line
   per check and exits non-zero on any failure. */
#include <windows.h>
#include <sddl.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

#include "village_elders.h"

#define STRIDE 0x40u
#define SLOTS 8u
#define GRAVE_STRIDE 0x30u
#define GRAVES 16u
/* record layout used by the synthetic arrays */
#define ACTIVE 0x00u
#define NAME 0x04u            /* 16 bytes, +0x04..+0x13 */
#define SKILLS 0x20u          /* 5 floats, +0x20..+0x33 */
#define AGE 0x34u
#define TRIBE 0x38u           /* u8, 0 = the player's villager */

static unsigned char villagers[SLOTS * STRIDE];
static unsigned char graves[GRAVES * GRAVE_STRIDE];
static int failures;

static void check(int ok, const char *what) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) {
        ++failures;
    }
}

static unsigned char *rec(unsigned int slot) {
    return villagers + slot * STRIDE;
}

static void set_villager(unsigned int slot, const char *name, const char *father, const char *mother,
                         int mastered, int age) {
    unsigned char *r = rec(slot);
    int i;
    memset(r, 0, STRIDE);
    r[ACTIVE] = 1;
    (void)father;
    (void)mother;
    strncpy_s((char *)r + NAME, 0x10, name, _TRUNCATE);
    memcpy(r + AGE, &age, 4);
    for (i = 0; i < 5; ++i) {
        float value = i < mastered ? 88.0f + (float)i : 87.9f;
        memcpy(r + SKILLS + (unsigned int)i * 4u, &value, 4);
    }
}

static void set_skill(unsigned int slot, int index, float value) {
    memcpy(rec(slot) + SKILLS + (unsigned int)index * 4u, &value, 4);
}

static void bury(unsigned int grave, const char *name, int elder_flag) {
    unsigned char *g = graves + grave * GRAVE_STRIDE;
    int age = 500;
    memset(g, 0, GRAVE_STRIDE);
    strncpy_s((char *)g, 0x19, name, _TRUNCATE);
    memcpy(g + 0x1C, &age, 4);
    g[0x29] = (unsigned char)(elder_flag ? 1 : 0);
}

static struct elders_layout layout(int with_graves) {
    struct elders_layout l;
    memset(&l, 0, sizeof(l));
    l.villagers = villagers; l.record_base = 0; l.stride = STRIDE; l.slots = SLOTS;
    l.active = ACTIVE; l.name = NAME; l.name_capacity = 0x10;
    l.father_name = 0; l.mother_name = 0; l.parent_name_capacity = 0x0C;
    l.skills = SKILLS; l.skill_count = 5; l.skills_are_float = 1; l.master_float = 88.0f;
    if (with_graves) {
        l.graves = graves; l.grave_stride = GRAVE_STRIDE; l.grave_capacity = GRAVES;
        l.grave_occupied = 0x1C; l.grave_name = 0; l.grave_name_capacity = 0x19;
        l.grave_elder_flag = 0x29;
    }
    return l;
}

static int file_contains(const wchar_t *path, const char *needle) {
    FILE *f;
    char buffer[8192];
    size_t n;
    if (_wfopen_s(&f, path, L"rb") != 0 || f == NULL) {
        return 0;
    }
    n = fread(buffer, 1, sizeof(buffer) - 1, f);
    fclose(f);
    buffer[n] = 0;
    return strstr(buffer, needle) != NULL;
}

int wmain(int argc, wchar_t **argv) {
    wchar_t dat[MAX_PATH], tmp[MAX_PATH], pattern[MAX_PATH];
    struct elders_layout l;
    int n;
    WIN32_FIND_DATAW found;
    HANDLE h;
    if (argc < 2) {
        return 2;
    }
    _snwprintf_s(dat, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save 1.dat", argv[1]);
    _snwprintf_s(tmp, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save 1.tmp", argv[1]);
    DeleteFileW(dat);
    memset(villagers, 0, sizeof(villagers));
    memset(graves, 0, sizeof(graves));
    l = layout(1);

    /* Missing file = empty history. */
    check(vv_village_elders_file(4, dat, tmp, &l) == 0, "missing file is an empty history (0 elders)");

    /* A: two mastered skills -> not an elder. */
    set_villager(0, "Tana", "", "", 2, 300);
    check(vv_village_elders_file(4, dat, tmp, &l) == 0, "A: master in exactly two skills is not an elder");

    /* B: the same villager masters a third -> one elder. */
    set_skill(0, 2, 88.0f);
    check(vv_village_elders_file(4, dat, tmp, &l) == 1, "B: a third mastered skill makes one elder");

    /* C: a fourth -> still one. */
    set_skill(0, 3, 95.0f);
    check(vv_village_elders_file(4, dat, tmp, &l) == 1, "C: a fourth mastered skill adds no elder");
    set_skill(0, 4, 99.0f);
    check(vv_village_elders_file(4, dat, tmp, &l) == 1, "C: a fifth mastered skill adds no elder");

    /* D: a different villager, a different three skills -> two. */
    set_villager(1, "Kiri", "", "", 0, 300);
    set_skill(1, 1, 88.0f); set_skill(1, 3, 90.0f); set_skill(1, 4, 100.0f);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "D: any three distinct skills qualify (another villager)");

    /* E: age alone never qualifies. */
    set_villager(2, "Oldo", "", "", 0, 999999);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "E: great age alone is not an elder");
    set_villager(3, "Bibi", "", "", 2, 999999);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "E: great age with two masteries is not an elder");

    /* F: reload -- every call re-reads the .dat, as a restart would. */
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "F: the count survives a reload of the .dat");
    check(file_contains(dat, "E\t0\tTana") && file_contains(dat, "E\t1\tKiri"),
          "F: both elders are stored in the .dat by identity");

    /* Renaming is normal play: a renamed elder is the same elder. */
    strncpy_s((char *)rec(1) + NAME, 0x10, "Kirra", _TRUNCATE);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "a renamed elder is not counted again");
    check(file_contains(dat, "E\t1\tKirra"), "the elder's line follows the new name");
    strncpy_s((char *)rec(0) + NAME, 0x10, "Tanu", _TRUNCATE);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "a second rename adds nothing either");

    /* Lifetime: an elder dies and is buried (under the latest name) with the
       game's flag -> still 2. */
    rec(0)[ACTIVE] = 0;
    bury(0, "Tanu", 1);
    check(vv_village_elders_file(4, dat, tmp, &l) == 2, "a buried elder is matched to their line, not counted twice");
    check(file_contains(dat, "E\t0\tTanu\t\t\t1\t0"), "the matched line is marked gone and closed");

    /* An elder who qualified and died between two saves: known only by the
       game's grave flag -> counted once. */
    bury(1, "Moku", 1);
    check(vv_village_elders_file(4, dat, tmp, &l) == 3, "an elder found only on a new flagged grave counts once");
    check(vv_village_elders_file(4, dat, tmp, &l) == 3, "... and not again on the next save");

    /* A non-elder grave counts nothing. */
    bury(2, "Pala", 0);
    check(vv_village_elders_file(4, dat, tmp, &l) == 3, "an unflagged grave counts nothing");

    /* A living villager sharing a dead elder's name is not their grave:
       name collisions are routine. */
    set_villager(4, "Moku", "", "", 3, 400);
    check(vv_village_elders_file(4, dat, tmp, &l) == 4, "a living namesake of a dead elder is their own elder");

    /* Slot reuse: a different villager (different name) in a dead elder's slot. */
    set_villager(0, "Sefa", "", "", 3, 100);
    check(vv_village_elders_file(4, dat, tmp, &l) == 5, "a new elder in a reused slot counts");

    /* New Believers: a heathen (tribe byte != 0) is not one of the player's
       villagers, however skilled -- the Heathen Chief has every skill at 100.
       Converted, the same villager is in the tribe and counts. */
    l.tribe = TRIBE;
    set_villager(7, "Chief", "", "", 5, 900);
    rec(7)[TRIBE] = 1;
    check(vv_village_elders_file(4, dat, tmp, &l) == 5, "a heathen with every skill mastered is not a Village Elder");
    rec(7)[TRIBE] = 0;
    check(vv_village_elders_file(4, dat, tmp, &l) == 6, "the same villager, converted, is one Village Elder");
    memset(rec(7), 0, STRIDE);
    l.tribe = 0;

    /* Retroactive baseline: a brand-new .dat over a memorial that already
       holds flagged graves counts them, and nothing else is invented. */
    DeleteFileW(dat);
    memset(villagers, 0, sizeof(villagers));
    memset(graves, 0, sizeof(graves));
    bury(0, "Ata", 1); bury(1, "Bea", 0); bury(2, "Cai", 1);
    check(vv_village_elders_file(3, dat, tmp, &l) == 2, "a new .dat counts the elders the game flagged on existing graves");

    /* Locked file (a sync client, scanner or permission problem): not
       treated as missing -- nothing is read, nothing replaces it, and the
       history is intact once it can be read again. Modelled with an ACL that
       denies only reading the data while still allowing the file to be
       replaced: exactly the case that used to lose the history (open failed
       -> empty history -> the real file replaced). A handle held open cannot
       model it, because Windows refuses to replace any file with an open
       handle. */
    {
        HANDLE h2;
        PSECURITY_DESCRIPTOR deny = NULL, allow = NULL;
        char before[4096], after[4096];
        DWORD before_n = 0, after_n = 0;
        h2 = CreateFileW(dat, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        ReadFile(h2, before, sizeof(before), &before_n, NULL);
        CloseHandle(h2);
        check(ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:(D;;0x1;;;WD)(A;;FA;;;WD)", SDDL_REVISION_1,
                                                                   &deny, NULL)
              && ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:(A;;FA;;;WD)", SDDL_REVISION_1, &allow, NULL)
              && SetFileSecurityW(dat, DACL_SECURITY_INFORMATION, deny),
              "the harness can make the elders file unreadable");
        bury(3, "Dov", 1);
        check(vv_village_elders_file(3, dat, tmp, &l) == -1, "a locked elders file reports nothing");
        SetFileSecurityW(dat, DACL_SECURITY_INFORMATION, allow);
        LocalFree(deny);
        LocalFree(allow);
        h2 = CreateFileW(dat, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        ReadFile(h2, after, sizeof(after), &after_n, NULL);
        CloseHandle(h2);
        check(before_n > 0 && before_n == after_n && memcmp(before, after, before_n) == 0,
              "... and the locked file is left byte-for-byte unchanged");
        check(vv_village_elders_file(3, dat, tmp, &l) == 3, "once readable, the history continues from the file");
    }

    /* Corrupt / foreign file: preserved, never overwritten, nothing taken. */
    {
        FILE *f;
        _wfopen_s(&f, dat, L"wb");
        fputs("VVFP VILLAGE ELDERS v2 game=5\r\ngraves_seen=0\r\nE\t0\tX\t\t\t0\t1\r\n", f);   /* wrong game */
        fclose(f);
    }
    memset(graves, 0, sizeof(graves));
    n = vv_village_elders_file(3, dat, tmp, &l);
    check(n == 0, "a file for another game is not read (no invented elders)");
    _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save 1.dat.unreadable-*.dat", argv[1]);
    h = FindFirstFileW(pattern, &found);
    check(h != INVALID_HANDLE_VALUE, "... and it is kept aside, not overwritten");
    if (h != INVALID_HANDLE_VALUE) {
        FindClose(h);
    }
    check(GetFileAttributesW(tmp) == INVALID_FILE_ATTRIBUTES, "no temporary file is left behind");

    /* The earlier v1 format (no "open" field) is never read as v2: kept
       aside, never overwritten, nothing taken from it. */
    {
        FILE *f;
        int aside = 0;
        _wfopen_s(&f, dat, L"wb");
        fputs("VVFP VILLAGE ELDERS v1 game=3\r\ngraves_seen=0\r\nE\t0\tX\t\t\t0\r\n", f);
        fclose(f);
        memset(graves, 0, sizeof(graves));
        check(vv_village_elders_file(3, dat, tmp, &l) == 0, "a v1 elders file is not read as v2");
        h = FindFirstFileW(pattern, &found);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                ++aside;
            } while (FindNextFileW(h, &found));
            FindClose(h);
        }
        check(aside == 2, "... and it is kept aside beside the earlier one");
    }

    printf("%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
