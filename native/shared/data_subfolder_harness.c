/* native/shared/data_subfolder.h against real files: where a data file is
   read and written, and how a copy an older build left loose in
   "Virtual Villagers Fun Patcher Data" is moved into its kind's folder.

   Works only inside the scratch folder given on the command line (a folder
   under %TEMP% made by scripts/build_data_subfolder_harness.ps1); it never
   resolves Documents, so it cannot touch Documents\LDW or any save.

   Two seams, both off in shipped builds: VV_DATA_MOVE_FILE is wrapped to
   count moves and to make one fail on demand (a locked file is ALSO used,
   for the real failure), and GetFileAttributesA is wrapped so one path can
   report "access denied" (a file that may exist but cannot be examined).

   Usage:  data_subfolder_harness.exe <scratch folder>
   Exit code 0 when every check passes. */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static int g_moves;            /* MoveFileEx calls the resolver made */
static int g_fail_move;        /* 1: the next move fails (ERROR_ACCESS_DENIED) */
static int g_race_move;        /* 1: the next move finds a file appeared in the folder */
static char g_deny[MAX_PATH];  /* GetFileAttributesA on this path: access denied */

static BOOL harness_move(const char *from, const char *to) {
    ++g_moves;
    if (g_fail_move) {
        g_fail_move = 0;
        SetLastError(ERROR_ACCESS_DENIED);
        return FALSE;
    }
    if (g_race_move) {
        HANDLE h;
        DWORD wrote;
        g_race_move = 0;
        h = CreateFileA(to, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
        if (h != INVALID_HANDLE_VALUE) {
            WriteFile(h, "RACE", 4, &wrote, NULL);
            CloseHandle(h);
        }
        /* the real call, which must now refuse to replace it */
        return MoveFileExA(from, to, MOVEFILE_WRITE_THROUGH);
    }
    return MoveFileExA(from, to, MOVEFILE_WRITE_THROUGH);
}

static DWORD WINAPI harness_attributes(LPCSTR path) {
    if (g_deny[0] != '\0' && lstrcmpiA(path, g_deny) == 0) {
        SetLastError(ERROR_ACCESS_DENIED);
        return INVALID_FILE_ATTRIBUTES;
    }
    return GetFileAttributesA(path);
}

#define VV_DATA_MOVE_FILE(from, to) harness_move((from), (to))
#define GetFileAttributesA harness_attributes
#include "data_subfolder.h"
#undef GetFileAttributesA
#include "sidecar_io.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static char g_data[MAX_PATH];     /* <scratch>\Virtual Villagers Fun Patcher Data */
static char g_sub[MAX_PATH];      /* ...\Village Masks */
static char g_loose[MAX_PATH];    /* ...\Data\<name> */
static char g_moved[MAX_PATH];    /* ...\Data\Village Masks\<name> */
#define NAME "Village Masks - Save 1.dat"

static int write_bytes(const char *path, const char *text) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD wrote = 0;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    WriteFile(h, text, (DWORD)lstrlenA(text), &wrote, NULL);
    CloseHandle(h);
    return wrote == (DWORD)lstrlenA(text);
}

/* The file's whole content, or "" when it cannot be read; "<none>" when absent. */
static const char *read_text(const char *path) {
    static char buf[256];
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) {
        return GetLastError() == ERROR_FILE_NOT_FOUND ? "<none>" : "";
    }
    ReadFile(h, buf, sizeof(buf) - 1, &got, NULL);
    CloseHandle(h);
    buf[got] = '\0';
    return buf;
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

static void wipe(void) {
    char tmp[MAX_PATH];
    DeleteFileA(g_loose);
    DeleteFileA(g_moved);
    wsprintfA(tmp, "%s.tmp", g_moved);
    DeleteFileA(tmp);
    wsprintfA(tmp, "%s.tmp", g_loose);
    DeleteFileA(tmp);
    RemoveDirectoryA(g_sub);
    DeleteFileA(g_sub);           /* the "folder is a file" case */
    g_moves = 0;
    g_fail_move = 0;
    g_race_move = 0;
    g_deny[0] = '\0';
}

/* Resolve the masks file for slot 1 from a fresh Data-folder buffer. */
static int resolve(char *out) {
    lstrcpyA(out, g_data);
    return vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_MASKS, NAME, VV_DATA_RESERVE);
}

static int accept_all(const unsigned char *data, DWORD len, void *ctx) {
    (void)data; (void)ctx;
    return len > 0;
}

int main(int argc, char **argv) {
    char out[MAX_PATH];
    int r;
    if (argc < 2 || lstrlenA(argv[1]) > MAX_PATH - 120) {
        printf("usage: data_subfolder_harness <scratch folder>\n");
        return 2;
    }
    wsprintfA(g_data, "%s\\%s", argv[1], VV_DATA_FOLDER);
    CreateDirectoryA(argv[1], NULL);
    CreateDirectoryA(g_data, NULL);
    wsprintfA(g_sub, "%s\\%s", g_data, VV_DATA_SUB_MASKS);
    wsprintfA(g_loose, "%s\\%s", g_data, NAME);
    wsprintfA(g_moved, "%s\\%s\\%s", g_data, VV_DATA_SUB_MASKS, NAME);

    printf("1. nothing on disk: the file goes in its folder\n");
    wipe();
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpiA(out, g_moved) == 0, "the path is <Data>\\Village Masks\\<name>");
    CHECK(GetFileAttributesA(g_sub) != INVALID_FILE_ATTRIBUTES
          && (GetFileAttributesA(g_sub) & FILE_ATTRIBUTE_DIRECTORY), "the folder was made");
    CHECK(!exists(g_moved) && !exists(g_loose) && g_moves == 0, "no file was made and nothing moved");

    printf("2. only the loose copy: it is moved in, whole\n");
    wipe();
    write_bytes(g_loose, "LOOSE-1");
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpiA(out, g_moved) == 0, "the path is the folder's");
    CHECK(lstrcmpA(read_text(g_moved), "LOOSE-1") == 0, "the folder's file holds the loose bytes");
    CHECK(!exists(g_loose), "the loose copy is gone (moved, not copied)");
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && g_moves == 1, "a second resolve finds it in place and moves nothing");

    printf("3. both: the folder's file is used, the loose copy left exactly as it was\n");
    wipe();
    CreateDirectoryA(g_sub, NULL);
    write_bytes(g_moved, "NEW");
    write_bytes(g_loose, "OLD");
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpiA(out, g_moved) == 0, "the path is the folder's");
    CHECK(lstrcmpA(read_text(g_moved), "NEW") == 0, "the folder's file is unchanged");
    CHECK(lstrcmpA(read_text(g_loose), "OLD") == 0, "the loose copy is unchanged and still there");
    CHECK(g_moves == 0, "no move was attempted");

    printf("4. the move fails (injected): the loose copy is read and written in place\n");
    wipe();
    write_bytes(g_loose, "KEEP-ME");
    g_fail_move = 1;
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0, "the path is the loose file");
    CHECK(lstrcmpA(read_text(g_loose), "KEEP-ME") == 0 && !exists(g_moved), "the loose copy is untouched; nothing in the folder");
    {
        vv_sidecar_gate gate;
        unsigned char buf[64];
        DWORD len = 0;
        const void *parts[1];
        DWORD sizes[1];
        char tmp[MAX_PATH];
        memset(&gate, 0, sizeof gate);
        vv_sidecar_gate_bind(&gate, 1);
        CHECK(vv_sidecar_load(&gate, out, buf, sizeof buf, &len, accept_all, NULL) == VV_SIDECAR_LOAD_VALID
              && len == 7 && memcmp(buf, "KEEP-ME", 7) == 0, "the companion's load reads the loose bytes");
        parts[0] = "UPDATED";
        sizes[0] = 7;
        CHECK(vv_sidecar_publish(&gate, out, parts, sizes, 1), "the companion's atomic write succeeds");
        wsprintfA(tmp, "%s.tmp", g_loose);
        CHECK(lstrcmpA(read_text(g_loose), "UPDATED") == 0 && !exists(tmp) && !exists(g_moved),
              "it replaced the loose file through a .tmp beside it; nothing in the folder");
    }
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpA(read_text(g_moved), "UPDATED") == 0 && !exists(g_loose),
          "the next launch moves it in, with what was written meanwhile");

    printf("5. the move fails for real (the loose file is open without delete sharing)\n");
    wipe();
    write_bytes(g_loose, "LOCKED");
    {
        HANDLE hold = CreateFileA(g_loose, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                  FILE_ATTRIBUTE_NORMAL, NULL);
        r = resolve(out);
        CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0, "the path is the loose file");
        CHECK(g_moves == 1 && !exists(g_moved), "the move was tried, and nothing appeared in the folder");
        CloseHandle(hold);
    }
    CHECK(lstrcmpA(read_text(g_loose), "LOCKED") == 0, "the loose copy is intact");

    printf("6. a file appears in the folder while the loose one is being moved\n");
    wipe();
    write_bytes(g_loose, "LOOSE");
    g_race_move = 1;
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpiA(out, g_moved) == 0, "the folder's file wins");
    CHECK(lstrcmpA(read_text(g_moved), "RACE") == 0, "it was not overwritten");
    CHECK(lstrcmpA(read_text(g_loose), "LOOSE") == 0, "the loose copy is untouched");

    printf("7. the loose file cannot be examined (access denied): use it, never guess it away\n");
    wipe();
    write_bytes(g_loose, "MAYBE");
    lstrcpyA(g_deny, g_loose);
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0, "the path is the loose file");
    CHECK(g_moves == 0 && !exists(g_moved), "no move, nothing in the folder");
    g_deny[0] = '\0';
    CHECK(lstrcmpA(read_text(g_loose), "MAYBE") == 0, "the loose copy is intact");

    printf("8. the folder cannot be made (a file has its name)\n");
    wipe();
    write_bytes(g_sub, "NOT A FOLDER");
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0, "nothing loose: the loose path, so the data is still kept");
    write_bytes(g_loose, "LOOSE");
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0 && g_moves == 0, "loose present: used in place, no move tried");
    CHECK(lstrcmpA(read_text(g_sub), "NOT A FOLDER") == 0 && lstrcmpA(read_text(g_loose), "LOOSE") == 0,
          "neither file was touched");

    printf("9. a directory with the file's loose name is not ours\n");
    wipe();
    CreateDirectoryA(g_loose, NULL);
    r = resolve(out);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpiA(out, g_moved) == 0 && g_moves == 0, "the folder's path; nothing moved");
    RemoveDirectoryA(g_loose);

    printf("10. lengths: room for the longest set-aside name, else the loose file, else nothing\n");
    CHECK(VV_DATA_RESERVE == (int)sizeof(".unreadable-4294967295-999"),
          "the reserve is sidecar_io's longest suffix, \".unreadable-<ticks>-<n>\", and the NUL");
    wipe();
    lstrcpyA(out, g_data);
    r = vv_data_file_path(out, lstrlenA(g_loose) + VV_DATA_RESERVE - 1, VV_DATA_SUB_MASKS, NAME, VV_DATA_RESERVE);
    CHECK(r == VV_DATA_PATH_FAILED && lstrcmpA(out, g_data) == 0,
          "even the loose path is one char short: refused, buffer left as it was");
    write_bytes(g_loose, "LONG");
    lstrcpyA(out, g_data);
    r = vv_data_file_path(out, lstrlenA(g_moved) + VV_DATA_RESERVE - 1, VV_DATA_SUB_MASKS, NAME, VV_DATA_RESERVE);
    CHECK(r == VV_DATA_PATH_LOOSE && lstrcmpiA(out, g_loose) == 0,
          "only the folder's path is too long: the loose file, in place");
    CHECK(g_moves == 0 && GetFileAttributesA(g_sub) == INVALID_FILE_ATTRIBUTES
          && lstrcmpA(read_text(g_loose), "LONG") == 0, "nothing moved, no folder made, the file intact");
    lstrcpyA(out, g_data);
    r = vv_data_file_path(out, lstrlenA(g_moved) + VV_DATA_RESERVE, VV_DATA_SUB_MASKS, NAME, VV_DATA_RESERVE);
    CHECK(r == VV_DATA_PATH_FOLDER && lstrcmpA(read_text(g_moved), "LONG") == 0,
          "exactly enough for the folder's path: moved in");

    wipe();
    RemoveDirectoryA(g_data);
    RemoveDirectoryA(argv[1]);
    printf(failures ? "FAILURES: %d\n" : "all checks passed\n", failures);
    return failures ? 1 : 0;
}
