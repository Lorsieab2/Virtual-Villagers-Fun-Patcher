/* Does the reset read the erased village from the slot's own save, exactly?
 *
 * Launching a game and pressing Start Over at once used to leave the old
 * village's Births and Conceptions log behind: nothing had been saved in that
 * process, so there was no published header to match it by. The reset now
 * reads the name from "<base><slot>.ldw", which both hooks reach before the
 * game removes or overwrites it, and builds the header with the exporters'
 * own functions.
 *
 * This compiles the SHIPPED source (save_reset_export.c is included, not
 * copied) and runs vv_saved_village_header against synthetic saves in a
 * throwaway folder under %TEMP%: never the player's save folder, and it never
 * calls the reset itself.
 *
 * Build and run: scripts/build_saved_village_harness.ps1
 * An optional argument names a real save folder to READ (nothing is written
 * there); the headers found for slots 1..5 of each game are printed.
 */
#include "save_reset_export.c"

#include <stdio.h>

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

static const DWORD NAME_AT[5] = { 0x00008u, 0x00008u, 0x12ECCu, 0x170B8u, 0x17D14u };
/* The save layout as measured on real saves, kept HERE rather than taken
   from the source under test, so a wrong table there cannot agree with
   itself. */
static const DWORD FILE_HEADER_AT[5] = { 12u, 12u, 12u, 24u, 24u };
static const DWORD LENGTH_FIELD_AT[5] = { 8u, 8u, 8u, 16u, 16u };
static const DWORD BUFFER_BYTES[5] = { 0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u };

/* Write a save the way the game does: file header, then the buffer. */
static void write_save(const wchar_t *folder, const wchar_t *file, int game,
                       const char *name, DWORD size_delta, const char *magic,
                       DWORD length_delta) {
    wchar_t path[MAX_PATH];
    DWORD header = FILE_HEADER_AT[game - 1];
    DWORD buffer = BUFFER_BYTES[game - 1];
    DWORD total = header + buffer + size_delta;
    DWORD length = buffer + length_delta;
    unsigned char *data = (unsigned char *)HeapAlloc(GetProcessHeap(),
                                                     HEAP_ZERO_MEMORY, total + 64);
    HANDLE h;
    DWORD written = 0;

    CopyMemory(data, magic, 4);
    CopyMemory(data + LENGTH_FIELD_AT[game - 1], &length, sizeof length);
    if (name != NULL) {
        CopyMemory(data + header + NAME_AT[game - 1], name, lstrlenA(name) + 1);
    }
    /* Something that is not a name right after it, as in a real buffer. */
    data[header + NAME_AT[game - 1] + 40] = 0x7F;
    wsprintfW(path, L"%ls\\%ls", folder, file);
    h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, data, total, &written, NULL);
        CloseHandle(h);
    }
    HeapFree(GetProcessHeap(), 0, data);
}

static void remove_all(const wchar_t *folder) {
    WIN32_FIND_DATAW found;
    wchar_t filter[MAX_PATH];
    wchar_t path[MAX_PATH];
    HANDLE search;

    wsprintfW(filter, L"%ls\\*.ldw", folder);
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return;
    }
    do {
        wsprintfW(path, L"%ls\\%ls", folder, found.cFileName);
        DeleteFileW(path);
    } while (FindNextFileW(search, &found));
    FindClose(search);
}

static const wchar_t *const BASE[5] = {
    L"Virtual Villagers",
    L"Virtual Villagers - The Lost Children",
    L"Virtual Villagers - The Secret City",
    L"Virtual Villagers - The Tree of Life",
    L"Virtual Villagers - New Believers",
};

static void read_real_folder(const wchar_t *folder) {
    int game;
    int slot;
    char out[256];

    printf("reading (only) %ls\n", folder);
    for (game = 1; game <= 5; ++game) {
        for (slot = 1; slot <= 5; ++slot) {
            if (vv_saved_village_header(game, slot, folder, out, sizeof out)) {
                printf("  game %d slot %d: %s", game, slot, out);
            }
        }
    }
}

int main(int argc, char **argv) {
    wchar_t temp[MAX_PATH];
    wchar_t folder[MAX_PATH];
    wchar_t file[MAX_PATH];
    char out[256];
    char expected[256];
    int game;

    if (argc > 1) {
        wchar_t real[MAX_PATH];
        MultiByteToWideChar(CP_ACP, 0, argv[1], -1, real, MAX_PATH);
        read_real_folder(real);
        return 0;
    }

    GetTempPathW(MAX_PATH, temp);
    wsprintfW(folder, L"%lsvvfp_saved_village_harness_%lu", temp,
              (unsigned long)GetCurrentProcessId());
    CreateDirectoryW(folder, NULL);

    for (game = 1; game <= 5; ++game) {
        printf("game %d\n", game);
        remove_all(folder);

        /* THE EXPORTERS' HEADER, BYTE FOR BYTE */
        wsprintfW(file, L"%ls2.ldw", BASE[game - 1]);
        write_save(folder, file, game, "audit", 0, "ldwg", 0);
        check(vv_saved_village_header(game, 2, folder, out, sizeof out),
              "the slot's own save is read");
        check(lstrcmpA(out, "Village: audit (Save 2)\n") == 0,
              "the header is exactly the exporters' \"Village: <name> (Save <n>)\\n\"");
        vv_village_header(expected, sizeof expected, "audit", 2);
        check(lstrcmpA(out, expected) == 0, "and equal to vv_village_header's own output");

        /* ANOTHER SLOT, ANOTHER VILLAGE: never confused */
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "slot 1 with no save of its own returns nothing (no guess from slot 2)");
        wsprintfW(file, L"%ls1.ldw", BASE[game - 1]);
        write_save(folder, file, game, "Another Tribe", 0, "ldwg", 0);
        check(vv_saved_village_header(game, 1, folder, out, sizeof out)
              && lstrcmpA(out, "Village: Another Tribe (Save 1)\n") == 0,
              "slot 1 names its own village, not slot 2's");
        check(vv_saved_village_header(game, 2, folder, out, sizeof out)
              && lstrcmpA(out, "Village: audit (Save 2)\n") == 0,
              "slot 2 still names audit");

        /* BACKUP GENERATIONS ARE NOT THE SLOT */
        remove_all(folder);
        wsprintfW(file, L"%ls21.ldw", BASE[game - 1]);
        write_save(folder, file, game, "old backup", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "a lone backup 21 is never read as slot 1");
        remove_all(folder);
        wsprintfW(file, L"%ls21.ldw", BASE[game - 1]);
        write_save(folder, file, game, "old backup", 0, "ldwg", 0);
        wsprintfW(file, L"%ls41.ldw", BASE[game - 1]);
        write_save(folder, file, game, "older backup", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "backups 21 and 41 are never read as slot 1");

        /* AMBIGUITY IS REFUSED */
        wsprintfW(file, L"%ls1.ldw", BASE[game - 1]);
        write_save(folder, file, game, "one", 0, "ldwg", 0);
        write_save(folder, L"Some Other Base1.ldw", game, "two", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "two valid saves for one slot: nothing is returned");

        /* NOT THIS GAME'S SAVE */
        remove_all(folder);
        write_save(folder, L"x1.ldw", game, "bad", 1, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "a file one byte too long is refused");
        remove_all(folder);
        write_save(folder, L"x1.ldw", game, "bad", 0, "LDWG", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "a file without the ldwg magic is refused");
        remove_all(folder);
        write_save(folder, L"x1.ldw", game, "bad", 0, "ldwg", 4);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "a file whose length field is not this game's buffer is refused");
        remove_all(folder);
        write_save(folder, L"x1.ldw", game == 5 ? 1 : game + 1, "bad", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "another game's save is refused");

        /* A NAME THAT IS NOT A NAME */
        remove_all(folder);
        write_save(folder, L"x1.ldw", game, "bad\x01name", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "a control byte in the name returns nothing rather than a garbled header");
        remove_all(folder);
        write_save(folder, L"x1.ldw", game, "", 0, "ldwg", 0);
        check(!vv_saved_village_header(game, 1, folder, out, sizeof out),
              "an empty name returns nothing");

        /* ANY BASE NAME THE GAME USES */
        remove_all(folder);
        write_save(folder, L"Renamed Build3.ldw", game, "Kalahuna Tribe 9: N", 0, "ldwg", 0);
        check(vv_saved_village_header(game, 3, folder, out, sizeof out)
              && lstrcmpA(out, "Village: Kalahuna Tribe 9: N (Save 3)\n") == 0,
              "the base name is found, not assumed");
    }
    /* Refusals with a valid file present, so they test the guard, not an
       empty folder. */
    remove_all(folder);
    wsprintfW(file, L"%ls0.ldw", BASE[0]);
    write_save(folder, file, 1, "meta", 0, "ldwg", 0);
    check(!vv_saved_village_header(1, 0, folder, out, sizeof out), "slot 0 (the meta file) is refused");
    wsprintfW(file, L"%ls6.ldw", BASE[0]);
    write_save(folder, file, 1, "six", 0, "ldwg", 0);
    check(!vv_saved_village_header(1, 6, folder, out, sizeof out), "slot 6 is refused");
    wsprintfW(file, L"%ls1.ldw", BASE[0]);
    write_save(folder, file, 1, "one", 0, "ldwg", 0);
    check(vv_saved_village_header(1, 1, folder, out, sizeof out), "(control: slot 1 is read)");
    check(!vv_saved_village_header(0, 1, folder, out, sizeof out)
          && !vv_saved_village_header(6, 1, folder, out, sizeof out), "an unknown game is refused");
    remove_all(folder);
    RemoveDirectoryW(folder);

    printf("%s: %d failure(s)\n", failures ? "FAILED" : "ALL PASSED", failures);
    return failures ? 1 : 0;
}
