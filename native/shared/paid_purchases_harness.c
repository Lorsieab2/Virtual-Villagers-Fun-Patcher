/* Runtime harness for native/shared/paid_purchases.h: a bought Barrel of
   Babies not delivered yet survives a quit.  The token and counter are the
   harness's own bytes, the save folder a throwaway one under %TEMP%, and a
   "session" ends by forgetting everything the header keeps in memory (what a
   quit does to the process).  Never touches Documents.

     1. Bought: the slot's file is written; delivered: deleted.
     2. Quit with it pending, the save written after the purchase: the next
        session re-arms the token as "Tech screen closed" with the counter at
        0, once; delivered then, the file goes.
     3. The save on disk is older than the purchase (a crash lost the save
        that charged it): nothing is re-armed and the file is deleted.
     4. Another village in the slot (no roster majority): nothing re-armed,
        the file is kept (it may be a frame of the last village).
     5. Switching to another slot while pending keeps the first slot's file;
        switching back re-arms it.
     6. A malformed file is deleted; a locked one is left alone.
     7. A held barrel waiting a long time: births and deaths refresh the
        roster in the file, so the village is still recognised.
     8. No village (an empty roster) is no frame at all.

   Usage: paid_purchases_harness.exe   (exit 0 when every check passes) */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static char g_folder[MAX_PATH];
static int vv_paid_test_folder(char *out) {
    lstrcpyA(out, g_folder);
    return 1;
}
#define VV_PAID_TEST_FOLDER
#include "paid_purchases.h"

static int failures, checks;
#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); ++failures; } } while (0)

static volatile unsigned char g_token;
static volatile unsigned int g_counter;
static int g_restored;
static void restored(void) { ++g_restored; }
static const vv_paid_game G = { &g_token, &g_counter, 2, "Harness Save", restored };
static unsigned int roster_a[VV_PAID_RECORDS], roster_b[VV_PAID_RECORDS], empty[VV_PAID_RECORDS];

static void quit(void) {                       /* the process ends: memory forgotten */
    vv_paid_slot = 0;
    memset(vv_paid_roster, 0, sizeof vv_paid_roster);
    vv_paid_have = 0;
    vv_paid_last = 0;
    vv_paid_dirty = 0;
    vv_paid_written = 0;
    g_token = 0;
    g_counter = 0;
}

static int file_exists(int slot) {
    char path[MAX_PATH];
    return vv_paid_path(2, slot, path, 0) && GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

static void save_now(int slot) {               /* the game's save of the slot, now */
    char path[MAX_PATH];
    HANDLE h;
    wsprintfA(path, "%s\\Harness Save%d.ldw", g_folder, slot);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        DWORD w;
        WriteFile(h, "save", 4, &w, NULL);
        CloseHandle(h);
    }
}

static void save_at(int slot, const FILETIME *when) {
    char path[MAX_PATH];
    HANDLE h;
    save_now(slot);
    wsprintfA(path, "%s\\Harness Save%d.ldw", g_folder, slot);
    h = CreateFileA(path, FILE_WRITE_ATTRIBUTES, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        SetFileTime(h, NULL, NULL, when);
        CloseHandle(h);
    }
}

int main(void) {
    char tmp[MAX_PATH];
    char path[MAX_PATH];
    int i, rearmed;
    GetTempPathA(MAX_PATH, tmp);
    wsprintfA(g_folder, "%svvfp_paid_harness_%lu", tmp, GetCurrentProcessId());
    CreateDirectoryA(g_folder, NULL);
    for (i = 0; i < 10; ++i) {
        roster_a[i] = 0x1000u + (unsigned)i;
        roster_b[i] = 0x2000u + (unsigned)i;
    }

    printf("Paid purchases\n");
    /* 8 */
    CHECK(vv_paid_tick(2, 1, empty, &G) == 0 && !vv_paid_have, "no village on screen is no frame");
    /* 1 */
    vv_paid_tick(2, 1, roster_a, &G);
    CHECK(!file_exists(1), "a village with nothing bought has no file");
    g_token = 1;                                /* bought; the Tech screen open */
    vv_paid_tick(2, 1, roster_a, &G);
    CHECK(file_exists(1), "bought: the slot's file is written");
    {
        /* ...in the save's own folder (native/shared/per_save.h), nothing in the older layout's. */
        char own[MAX_PATH], old_dir[MAX_PATH];
        wsprintfA(own, "%s\\Virtual Villagers Fun Patcher\\Save 1\\Data\\" VV_PAID_SUB
                       "\\Virtual Villagers 2 Paid Purchases - Save 1.dat", g_folder);
        wsprintfA(old_dir, "%s\\" VV_PAID_FOLDER, g_folder);
        CHECK(vv_paid_path(2, 1, path, 0) && lstrcmpiA(path, own) == 0
              && GetFileAttributesA(own) != INVALID_FILE_ATTRIBUTES
              && GetFileAttributesA(old_dir) == INVALID_FILE_ATTRIBUTES,
              "...in the save's own folder, nothing made in the older layout's");
    }
    g_token = 3;
    vv_paid_tick(2, 1, roster_a, &G);
    g_token = 0;                                /* delivered */
    vv_paid_tick(2, 1, roster_a, &G);
    CHECK(!file_exists(1), "delivered: the file is deleted");

    /* 2 */
    g_token = 1;
    vv_paid_tick(2, 1, roster_a, &G);
    Sleep(20);
    save_now(1);                                /* the quit save, after the purchase */
    quit();
    rearmed = vv_paid_tick(2, 1, roster_a, &G);
    CHECK(rearmed == 1 && g_token == 2 && g_counter == 0,
          "relaunch: the barrel is re-armed as 'Tech screen closed', the counter at 0");
    CHECK(g_restored == 1, "...and the game's own extra re-arming runs once");
    CHECK(vv_paid_tick(2, 1, roster_a, &G) == 0 && g_token == 2, "...once");
    CHECK(file_exists(1), "...and the file stays until it is delivered");
    g_token = 0;
    vv_paid_tick(2, 1, roster_a, &G);
    CHECK(!file_exists(1), "delivered after the relaunch: the file is deleted");
    quit();
    CHECK(vv_paid_tick(2, 1, roster_a, &G) == 0 && g_token == 0, "...and the next relaunch re-arms nothing");

    /* 3 */
    {
        FILETIME old;
        g_token = 2;
        vv_paid_tick(2, 1, roster_a, &G);
        old = vv_paid_bought;
        old.dwHighDateTime -= 1;                /* long before the purchase */
        save_at(1, &old);
        quit();
        CHECK(vv_paid_tick(2, 1, roster_a, &G) == 0 && g_token == 0 && !file_exists(1),
              "a save older than the purchase never paid: nothing re-armed, the file deleted");
    }

    /* 4 */
    quit();
    g_token = 2;
    vv_paid_tick(2, 1, roster_a, &G);
    Sleep(20);
    save_now(1);
    quit();
    CHECK(vv_paid_tick(2, 1, roster_b, &G) == 0 && g_token == 0 && file_exists(1),
          "another village in the slot: nothing re-armed, the file kept");
    CHECK(vv_paid_tick(2, 1, roster_a, &G) == 1 && g_token == 2,
          "...and its own village, on a later frame, gets it back");

    /* 5 */
    quit();
    g_token = 2;
    vv_paid_tick(2, 1, roster_a, &G);           /* pending in slot 1 */
    Sleep(20);
    save_now(1);
    g_token = 0;                                /* the slot stub clears it on the switch */
    vv_paid_tick(2, 2, roster_b, &G);           /* slot 2's village */
    CHECK(file_exists(1) && !file_exists(2), "switching villages keeps the first slot's file");
    vv_paid_tick(2, 1, roster_a, &G);           /* back to slot 1 */
    CHECK(g_token == 2, "...and switching back re-arms its barrel");
    g_token = 0;
    vv_paid_tick(2, 1, roster_a, &G);

    /* 6 */
    quit();
    vv_paid_path(2, 3, path, 1);
    {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        DWORD w;
        WriteFile(h, "junk", 4, &w, NULL);
        CloseHandle(h);
    }
    vv_paid_tick(2, 3, roster_a, &G);
    CHECK(!file_exists(3) && g_token == 0, "a malformed file is deleted, nothing re-armed");
    quit();
    {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
        DWORD w;
        WriteFile(h, "junk", 4, &w, NULL);
        /* held open, no sharing: unreadable */
        vv_paid_tick(2, 3, roster_a, &G);
        CloseHandle(h);
    }
    CHECK(file_exists(3) && g_token == 0, "a file that cannot be read is left alone");
    DeleteFileA(path);

    /* 7 */
    quit();
    g_token = 2;
    vv_paid_tick(2, 4, roster_a, &G);
    {
        static unsigned int drift[VV_PAID_RECORDS];
        memcpy(drift, roster_a, sizeof drift);
        for (i = 0; i < 8; ++i) {               /* most of the village replaced, one at a time */
            drift[i] = 0x3000u + (unsigned)i;
            vv_paid_written -= VV_PAID_REFRESH_MS;   /* time passes */
            vv_paid_tick(2, 4, drift, &G);
        }
        Sleep(20);
        save_now(4);
        quit();
        CHECK(vv_paid_tick(2, 4, drift, &G) == 1 && g_token == 2,
              "a barrel held for a long time: the file follows the village, which is still recognised");
    }
    g_token = 0;
    vv_paid_tick(2, 4, roster_a, &G);

    /* 8. A quit to the menu with the barrel still in memory: the title
          screen's seeded founders show in the records, the slot unchanged.
          Village A's file is never rewritten for them (the owner's v1.35.67
          parents loss, native/shared/foreign_sidecar.h). */
    quit();
    g_token = 2;
    vv_paid_tick(2, 5, roster_a, &G);           /* bought in village A, slot 5 */
    Sleep(20);
    save_now(5);
    vv_paid_tick(2, 5, roster_b, &G);           /* the title screen's founders, token still set */
    quit();
    g_token = 0;
    CHECK(vv_paid_tick(2, 5, roster_a, &G) == 1 && g_token == 2,
          "the title screen's founders never take village A's barrel: relaunched, A gets it back");
    g_token = 0;
    vv_paid_tick(2, 5, roster_a, &G);

    /* 9. A file of the older layout (a barrel bought before the save folders): read, re-armed and
          deleted where it is, nothing made in the save's own folder (per_save.h). */
    quit();
    {
        char old_file[MAX_PATH], own_file[MAX_PATH];
        wsprintfA(path, "%s\\" VV_PAID_FOLDER, g_folder);
        CreateDirectoryA(path, NULL);
        wsprintfA(path, "%s\\" VV_PAID_FOLDER "\\" VV_PAID_SUB, g_folder);
        CreateDirectoryA(path, NULL);
        wsprintfA(old_file, "%s\\Virtual Villagers 2 Paid Purchases - Save 2.dat", path);
        wsprintfA(own_file, "%s\\Virtual Villagers Fun Patcher\\Save 2\\Data\\" VV_PAID_SUB
                            "\\Virtual Villagers 2 Paid Purchases - Save 2.dat", g_folder);
        g_token = 2;
        vv_paid_tick(2, 2, roster_a, &G);       /* written fresh: the save's own folder */
        CHECK(GetFileAttributesA(own_file) != INVALID_FILE_ATTRIBUTES, "slot 2's barrel is written in the save's own folder");
        MoveFileA(own_file, old_file);          /* ...as an older build would have left it */
        Sleep(20);
        save_now(2);
        quit();
        CHECK(vv_paid_tick(2, 2, roster_a, &G) == 1 && g_token == 2
              && vv_paid_path(2, 2, path, 0) && lstrcmpiA(path, old_file) == 0
              && GetFileAttributesA(own_file) == INVALID_FILE_ATTRIBUTES,
              "an older-layout barrel file is read and re-armed where it is, never moved");
        g_token = 0;
        vv_paid_tick(2, 2, roster_a, &G);
        CHECK(GetFileAttributesA(old_file) == INVALID_FILE_ATTRIBUTES
              && GetFileAttributesA(own_file) == INVALID_FILE_ATTRIBUTES,
              "...and delivered, it is deleted there");
    }

    for (i = 1; i <= 5; ++i) {
        char p[MAX_PATH];
        if (vv_paid_path(2, i, p, 0)) DeleteFileA(p);
        wsprintfA(p, "%s\\Harness Save%d.ldw", g_folder, i);
        DeleteFileA(p);
    }
    wsprintfA(path, "%s\\" VV_PAID_FOLDER "\\" VV_PAID_SUB, g_folder);
    RemoveDirectoryA(path);
    wsprintfA(path, "%s\\" VV_PAID_FOLDER, g_folder);
    RemoveDirectoryA(path);
    for (i = 1; i <= 5; ++i) {
        /* The save's own folders, if empty. */
        wsprintfA(path, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\" VV_PAID_SUB, g_folder, i);
        RemoveDirectoryA(path);
        wsprintfA(path, "%s\\Virtual Villagers Fun Patcher\\Save %d\\Data", g_folder, i);
        RemoveDirectoryA(path);
        wsprintfA(path, "%s\\Virtual Villagers Fun Patcher\\Save %d", g_folder, i);
        RemoveDirectoryA(path);
    }
    wsprintfA(path, "%s\\Virtual Villagers Fun Patcher", g_folder);
    RemoveDirectoryA(path);
    RemoveDirectoryA(g_folder);
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
