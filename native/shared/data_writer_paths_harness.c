/* Every companion that writes a per-save data file, asked for its path.

   Compiled once per writer with /DVV_WRITER=<n>; each build includes that
   companion's real source and calls its real path builder:

       1  A New Home masks          vv1_origins_icons.c   vv1_mask_sidecar_path
       2  The Lost Children masks   vv2_origins_icons.c   vv2_mask_sidecar_path_slot
       3  The Secret City masks     vv3_full_mastery_candidate.c  vv3_mask_sidecar_path
       4  The Tree of Life masks    vv4_origins_icons.c   vv_build_sidecar_path
       5  New Believers masks       vv5_task9_origins.c   build_mask_sidecar_path
       6  A New Home parentage      vv1_parentage.c       vv1_parents_path
       7  Cause of Death graves     vvfp_cause_of_death.c cod_build_path
       8  Cause of Death roster     vvfp_cause_of_death.c roster_build_path

   The Documents folder is redirected (the shell calls are macros over this
   harness's own functions) to the scratch folder on the command line, so
   every file touched is inside it -- never Documents\LDW or a save.

   For each writer it checks, against real files:
     a. nothing on disk: the path is "<Data>\<kind folder>\<name>";
     b. a copy left loose in the Data folder is moved in, whole;
     c. a file already in the folder is used, and the loose copy beside it is
        left byte-for-byte;
     d. a loose copy that will not move (held open without delete sharing)
        is the path returned, and nothing appears in the folder;
     e. where the writer had one, the older root-level name still migrates.

   Usage:  data_writer_paths_harness_<n>.exe <scratch folder>
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>

static char g_docs[MAX_PATH];

static HRESULT WINAPI harness_folder_path(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

static BOOL WINAPI harness_special_a(HWND owner, LPSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    lstrcpyA(out, g_docs);
    return TRUE;
}

static BOOL WINAPI harness_special_w(HWND owner, LPWSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    return MultiByteToWideChar(CP_ACP, 0, g_docs, -1, out, MAX_PATH) > 0;
}

#define SHGetFolderPathA harness_folder_path
#define SHGetSpecialFolderPathA harness_special_a
#define SHGetSpecialFolderPathW harness_special_w

#if VV_WRITER >= 1 && VV_WRITER <= 5
/* The Origins companions link save_folder.c for the Repairs log
   (native/shared/orphan_masks.h, v1.35.59); with Documents redirected
   above, its folder resolves under the harness's scratch folder. */
#include "save_folder.c"
#endif
#if VV_WRITER == 1
#include "../vv1_origins_icons/vv1_origins_icons.c"
#define KIND VV_DATA_SUB_MASKS
#define NAME_FMT "Virtual Villagers 1 Village Masks - Save %d.dat"
#define LEGACY_FMT "vv1_masks_%d.dat"
static int writer_path(char *out, int slot) { return vv1_mask_sidecar_path(out, MAX_PATH, slot); }
#elif VV_WRITER == 2
#include "../vv2_origins_icons/vv2_origins_icons.c"
#define KIND VV_DATA_SUB_MASKS
#define NAME_FMT "Virtual Villagers 2 Village Masks - Save %d.dat"
#define LEGACY_FMT "vv2_masks_%d.dat"
static int writer_path(char *out, int slot) { return vv2_mask_sidecar_path_slot(out, slot); }
#elif VV_WRITER == 3
#include "../vv3_full_mastery_candidate/vv3_full_mastery_candidate.c"
#define KIND VV_DATA_SUB_MASKS
#define NAME_FMT "Village Masks - Save %d.dat"
#define LEGACY_FMT "vvfp_masks_%d.dat"
static int writer_path(char *out, int slot) { return vv3_mask_sidecar_path(out, MAX_PATH, slot); }
#elif VV_WRITER == 4
/* The Tree of Life declares its one shell32 import itself, dllimport and
   all; with the redirect that declaration names this harness's function,
   so the storage class is dropped for the length of the include (an
   exported function in a console program needs none).  <wchar.h> (which
   native/shared/save_layout.h includes) is read first, so its own
   __declspec(selectany) keeps its storage class. */
#include <wchar.h>
#define __declspec(x)
#include "../vv4_origins_icons/vv4_origins_icons.c"
#undef __declspec
#define KIND VV_DATA_SUB_MASKS
#define NAME_FMT "Village Masks - Save %d.dat"
#define LEGACY_FMT "vvfp_masks_%d.dat"
static int writer_path(char *out, int slot) { return vv_build_sidecar_path(out, slot); }
#elif VV_WRITER == 5
#include "../vv5_task9_origins/vv5_task9_origins.c"
#define KIND VV_DATA_SUB_MASKS
#define NAME_FMT "Village Masks - Save %d.dat"
#define LEGACY_FMT "vvfp_masks_%d.dat"
/* New Believers reads the slot from the game's own scratch word. This
   harness is linked at the game's base with a writable block that covers
   that address (scripts/build_data_writer_paths_harness.ps1), so the word is
   ordinary memory here; main() refuses to run if it is not. */
static unsigned char g_backing[0x600000];
static int writer_path(char *out, int slot) {
    *(volatile int *)VV5_SLOT_SCRATCH = slot;
    return build_mask_sidecar_path(out);
}
#elif VV_WRITER == 6
#include "../vv1_parentage/vv1_parentage.c"
#define KIND VV_DATA_SUB_PARENTAGE
#define NAME_FMT "Virtual Villagers 1 Parentage Records - Save %d.dat"
#define LEGACY_FMT "vv1_parents_%d.dat"
static int writer_path(char *out, int slot) { return vv1_parents_path(out, MAX_PATH, slot); }
#elif VV_WRITER == 7 || VV_WRITER == 8
#include "save_folder.c"
#include "../vvfp_cause_of_death/vvfp_cause_of_death.c"
#if VV_WRITER == 7
#define KIND VV_DATA_SUB_GRAVES
#define NAME_FMT "Virtual Villagers 2 Graves - Save %d.dat"
static int writer_path(char *out, int slot) { g_game = 2; return cod_build_path(slot, out); }
#else
#define KIND VV_DATA_SUB_UNACCOUNTED
#define NAME_FMT "Virtual Villagers 4 Villagers at Last Save - Save %d.dat"   /* "Village Roster" before */
static int writer_path(char *out, int slot) { g_game = 4; return roster_build_path(slot, out); }
#endif
#else
#error "VV_WRITER must be 1..8"
#endif

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

static char g_save[MAX_PATH];    /* <docs>\LDW\<this exe's basename> */
static char g_data[MAX_PATH];    /* ...\Virtual Villagers Fun Patcher Data */

static void put(const char *path, const char *text) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD wrote;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, text, (DWORD)lstrlenA(text), &wrote, NULL);
        CloseHandle(h);
    }
}

static const char *text_of(const char *path) {
    static char buf[128];
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) {
        return "<none>";
    }
    ReadFile(h, buf, sizeof(buf) - 1, &got, NULL);
    CloseHandle(h);
    buf[got] = '\0';
    return buf;
}

static void remove_tree(const char *dir) {
    char pattern[MAX_PATH], child[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE s;
    wsprintfA(pattern, "%s\\*", dir);
    s = FindFirstFileA(pattern, &f);
    if (s != INVALID_HANDLE_VALUE) {
        do {
            if (lstrcmpA(f.cFileName, ".") == 0 || lstrcmpA(f.cFileName, "..") == 0) continue;
            wsprintfA(child, "%s\\%s", dir, f.cFileName);
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) remove_tree(child);
            else DeleteFileA(child);
        } while (FindNextFileA(s, &f));
        FindClose(s);
    }
    RemoveDirectoryA(dir);
    /* Every step starts from a cleared tree as a new launch would: the
       resolver's per-session memory of loose paths (data_subfolder.h,
       rule 7) is that launch's, not this process's. */
    vv_data_kept_count = 0;
}

static void scenario(int slot) {
    char name[96], moved[MAX_PATH], loose[MAX_PATH], out[MAX_PATH];
    wsprintfA(name, NAME_FMT, slot);
    wsprintfA(moved, "%s\\%s\\%s", g_data, KIND, name);
    wsprintfA(loose, "%s\\%s", g_data, name);

    printf("slot %d -- %s\n", slot, name);
    remove_tree(g_save);
    CHECK(writer_path(out, slot) && lstrcmpiA(out, moved) == 0,
          "a. nothing on disk: <Data>\\%s\\<name> (got %s)", KIND, out);
    CHECK(text_of(moved)[0] == '<', "a. no file was made by asking");

    remove_tree(g_save);
    CreateDirectoryA(g_save, NULL);
    CreateDirectoryA(g_data, NULL);
    put(loose, "OLD-LOOSE");
    CHECK(writer_path(out, slot) && lstrcmpiA(out, moved) == 0, "b. a loose copy: the folder's path");
    CHECK(lstrcmpA(text_of(moved), "OLD-LOOSE") == 0 && lstrcmpA(text_of(loose), "<none>") == 0,
          "b. it was moved in whole");

    remove_tree(g_save);
    CreateDirectoryA(g_save, NULL);
    CreateDirectoryA(g_data, NULL);
    {
        char sub[MAX_PATH];
        wsprintfA(sub, "%s\\%s", g_data, KIND);
        CreateDirectoryA(sub, NULL);
    }
    put(moved, "NEW");
    put(loose, "OLD");
    CHECK(writer_path(out, slot) && lstrcmpiA(out, moved) == 0, "c. both: the folder's file");
    CHECK(lstrcmpA(text_of(moved), "NEW") == 0 && lstrcmpA(text_of(loose), "OLD") == 0,
          "c. neither file changed");

    remove_tree(g_save);
    CreateDirectoryA(g_save, NULL);
    CreateDirectoryA(g_data, NULL);
    put(loose, "HELD");
    {
        HANDLE hold = CreateFileA(loose, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                                  FILE_ATTRIBUTE_NORMAL, NULL);
        CHECK(writer_path(out, slot) && lstrcmpiA(out, loose) == 0, "d. will not move: the loose path");
        CHECK(lstrcmpA(text_of(moved), "<none>") == 0, "d. nothing appeared in the folder");
        CloseHandle(hold);
    }
    CHECK(lstrcmpA(text_of(loose), "HELD") == 0, "d. the loose copy is intact");

#ifdef LEGACY_FMT
    remove_tree(g_save);
    CreateDirectoryA(g_save, NULL);
    {
        char legacy[MAX_PATH];
        char legacy_name[64];
        wsprintfA(legacy_name, LEGACY_FMT, slot);
        wsprintfA(legacy, "%s\\%s", g_save, legacy_name);
        put(legacy, "ROOT-LEGACY");
        CHECK(writer_path(out, slot) && lstrcmpiA(out, moved) == 0, "e. a root-level %s: the folder's path", legacy_name);
        CHECK(lstrcmpA(text_of(moved), "ROOT-LEGACY") == 0 && lstrcmpA(text_of(legacy), "<none>") == 0,
              "e. it was moved straight into the folder");
    }
#endif
}

int main(int argc, char **argv) {
    char exe[MAX_PATH], *base, *dot;
    if (argc < 2 || lstrlenA(argv[1]) > 100) {
        printf("usage: data_writer_paths_harness <scratch folder (short)>\n");
        return 2;
    }
#if VV_WRITER == 5
    {
        unsigned int b = (unsigned int)(UINT_PTR)g_backing;
        if (!(VV5_SLOT_SCRATCH >= b && VV5_SLOT_SCRATCH + 4 <= b + sizeof g_backing)) {
            printf("the slot scratch %#x is outside the backing block %#x..%#x (link fixed at 0x400000)\n",
                   VV5_SLOT_SCRATCH, b, b + (unsigned int)sizeof g_backing);
            return 2;
        }
    }
#endif
    lstrcpyA(g_docs, argv[1]);
    CreateDirectoryA(g_docs, NULL);
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot) *dot = '\0';
    wsprintfA(g_save, "%s\\LDW", g_docs);
    CreateDirectoryA(g_save, NULL);
    wsprintfA(g_save, "%s\\LDW\\%s", g_docs, base);
    wsprintfA(g_data, "%s\\%s", g_save, VV_DATA_FOLDER);

    scenario(1);
    scenario(5);

    remove_tree(g_docs);
    printf(failures ? "FAILURES: %d\n" : "all checks passed\n", failures);
    return failures ? 1 : 0;
}
