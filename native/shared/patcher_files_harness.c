/* Runtime harness for native/shared/patcher_files.h: where every companion
   finds the patcher's files, and how it loads one.

   The executable's path is injected (VVFP_PATCHER_FILES_MODULE_PATH), so the
   path builder is driven with folders the ANSI code page cannot spell, with
   paths at and past its buffer, and with names it must refuse; then real
   files are made in a Unicode-named folder under the scratch folder given on
   the command line, and a real DLL (argv[2], copied there) is loaded through
   vvfp_load_patcher_dll by its full path.  Nothing outside that scratch
   folder is touched.  Exit code 0 means every check passed. */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static wchar_t g_module[4096];
static DWORD g_module_result_override = 0;   /* nonzero: report this length */

static DWORD harness_module_path(wchar_t *out, DWORD cap) {
    DWORD n = (DWORD)wcslen(g_module);
    if (g_module_result_override != 0) {
        return g_module_result_override;
    }
    if (n + 1 > cap) {                         /* as Windows: cut short, returns cap */
        wmemcpy(out, g_module, cap - 1);
        out[cap - 1] = L'\0';
        return cap;
    }
    wmemcpy(out, g_module, n + 1);
    return n;
}
#define VVFP_PATCHER_FILES_MODULE_PATH(out, cap) harness_module_path((out), (cap))
#include "patcher_files.h"

static int g_failures;

/* "C:\ddd...\g.exe" whose folder (with its trailing backslash) is `dir` long. */
static void make_module(DWORD dir) {
    DWORD i;
    g_module[0] = L'C'; g_module[1] = L':'; g_module[2] = L'\\';
    for (i = 3; i < dir - 1; ++i) g_module[i] = L'd';
    g_module[dir - 1] = L'\\';
    wcscpy_s(g_module + dir, 4096 - dir, L"g.exe");
}

static void check(int ok, const char *what) {
    if (!ok) {
        ++g_failures;
        printf("FAIL: %s\n", what);
    }
}

static void expect_path(const wchar_t *module, const char *leaf, const wchar_t *want, const char *what) {
    wchar_t out[VVFP_PATCHER_FILES_PATH_CAP];
    DWORD n;
    wcscpy_s(g_module, 4096, module);
    n = vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, leaf);
    if (want == NULL) {
        check(n == 0, what);
        return;
    }
    check(n == wcslen(want) && wcscmp(out, want) == 0, what);
}

int main(int argc, char **argv) {
    wchar_t scratch[MAX_PATH];
    wchar_t folder[1024];
    wchar_t files[1024];
    wchar_t target[1024];
    wchar_t out[VVFP_PATCHER_FILES_PATH_CAP];
    wchar_t dll_source[MAX_PATH];
    HANDLE f;
    HMODULE module;
    DWORD n;
    if (argc < 3) {
        puts("usage: harness <scratch folder> <a DLL to load>");
        return 2;
    }
    MultiByteToWideChar(CP_ACP, 0, argv[1], -1, scratch, MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, argv[2], -1, dll_source, MAX_PATH);

    /* The rule: <exe folder>\Virtual Villagers Fun Patcher Files\<leaf>. */
    expect_path(L"C:\\Games\\VV\\Virtual Villagers - A New Home - Modded.exe", "VVFP Fix Huts.dll",
                L"C:\\Games\\VV\\Virtual Villagers Fun Patcher Files\\VVFP Fix Huts.dll", "plain folder");
    /* Characters outside every ANSI code page survive untouched. */
    expect_path(L"C:\\Jeux vid\x00E9o\\\x6751\x4EBA\x305F\x3061\\game.exe", "VVFP Startup.dll",
                L"C:\\Jeux vid\x00E9o\\\x6751\x4EBA\x305F\x3061\\Virtual Villagers Fun Patcher Files\\VVFP Startup.dll",
                "Unicode folder");
    /* A subfolder leaf; '/' written as '\'. */
    expect_path(L"D:\\g\\x.exe", "Images/vvfp_mask_preview.png",
                L"D:\\g\\Virtual Villagers Fun Patcher Files\\Images\\vvfp_mask_preview.png", "subfolder leaf");
    /* Never the current directory: a module path without a folder is refused. */
    expect_path(L"game.exe", "VVFP Fix Huts.dll", NULL, "no folder in the module path");
    /* Names that could leave the folder, or are not plain ASCII, are refused. */
    expect_path(L"C:\\g\\x.exe", "..\\x.dll", NULL, "parent component");
    expect_path(L"C:\\g\\x.exe", "a\\..\\x.dll", NULL, "inner parent component");
    expect_path(L"C:\\g\\x.exe", "\\x.dll", NULL, "absolute leaf");
    expect_path(L"C:\\g\\x.exe", "C:x.dll", NULL, "drive leaf");
    expect_path(L"C:\\g\\x.exe", "", NULL, "empty leaf");
    expect_path(L"C:\\g\\x.exe", "caf\xE9.dll", NULL, "non-ASCII leaf");
    /* A failed or cut-short module path is refused, never guessed at. */
    wcscpy_s(g_module, 4096, L"C:\\g\\x.exe");
    g_module_result_override = 0xFFFFFFFF;
    check(vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, "VVFP Fix Huts.dll") == 0, "module path error");
    g_module_result_override = 0;

    /* The buffer's edge, for the game folder (the same builder with no
       patcher folder): a result of exactly cap - 1 characters fits, one
       more does not, and the executable's own path cut short is refused. */
    {
        const char *leaf = "VVFP Cause of Death.dll";
        DWORD tail = (DWORD)strlen(VVFP_PATCHER_FILES_FOLDER) + 1 + (DWORD)strlen(leaf);
        DWORD dir = VVFP_PATCHER_FILES_PATH_CAP - 1 - tail;     /* the folder, with its backslash */
        make_module(dir);
        n = vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, leaf);
        check(n == VVFP_PATCHER_FILES_PATH_CAP - 1, "the longest path that fits");
        check(n != 0 && out[n] == 0, "terminated at the edge");
        make_module(dir + 1);                                    /* one character more */
        check(vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, leaf) == 0, "one character past the edge");
        make_module(2000);                                       /* longer than the buffer */
        check(vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, leaf) == 0, "executable path cut short");
    }

    /* The game's own folder (files the game opens in place). */
    wcscpy_s(g_module, 4096, L"C:\\G\x00E9\\x.exe");
    n = vvfp_game_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, "Images\\golden_mushroom.png");
    check(n != 0 && wcscmp(out, L"C:\\G\x00E9\\Images\\golden_mushroom.png") == 0, "game file path");

    /* Real files in a Unicode-named game folder. */
    swprintf_s(folder, 1024, L"%ls\\Villageois \x00E9t\x00E9 \x6751\x4EBA", scratch);
    swprintf_s(files, 1024, L"%ls\\" L"Virtual Villagers Fun Patcher Files", folder);
    check(CreateDirectoryW(scratch, NULL) || GetLastError() == ERROR_ALREADY_EXISTS, "scratch folder");
    check(CreateDirectoryW(folder, NULL) != 0, "Unicode game folder");
    check(CreateDirectoryW(files, NULL) != 0, "patcher folder");
    swprintf_s(g_module, 4096, L"%ls\\Virtual Villagers - A New Home - Modded.exe", folder);
    check(!vvfp_patcher_file_exists("VVFP Fix Huts.dll"), "absent file is absent");
    swprintf_s(target, 1024, L"%ls\\VVFP Fix Huts.dll", files);
    f = CreateFileW(target, GENERIC_WRITE, 0, NULL, CREATE_NEW, 0, NULL);
    check(f != INVALID_HANDLE_VALUE, "make a file there");
    if (f != INVALID_HANDLE_VALUE) CloseHandle(f);
    check(vvfp_patcher_file_exists("VVFP Fix Huts.dll"), "file in the Unicode patcher folder is found");
    /* A loose copy beside the executable is NOT the patcher's file. */
    swprintf_s(target, 1024, L"%ls\\VVFP Lesson Cap.dll", folder);
    f = CreateFileW(target, GENERIC_WRITE, 0, NULL, CREATE_NEW, 0, NULL);
    if (f != INVALID_HANDLE_VALUE) CloseHandle(f);
    check(!vvfp_patcher_file_exists("VVFP Lesson Cap.dll"), "a loose copy beside the executable is ignored");
    /* A directory is not a file. */
    check(!vvfp_patcher_file_exists("..") && !vvfp_patcher_file_exists("Images"), "no directory");
    /* A real DLL, loaded by its full path in the Unicode patcher folder. */
    swprintf_s(target, 1024, L"%ls\\VVFP Harness Load.dll", files);
    check(CopyFileW(dll_source, target, TRUE) != 0, "copy the DLL in");
    module = vvfp_load_patcher_dll("VVFP Harness Load.dll");
    check(module != NULL, "the DLL loads from the Unicode patcher folder");
    if (module != NULL) {
        GetModuleFileNameW(module, out, VVFP_PATCHER_FILES_PATH_CAP);
        check(_wcsicmp(out, target) == 0, "it is that very file");
        check(vvfp_patcher_dll("VVFP Harness Load.dll") == module, "already loaded: the same module");
        FreeLibrary(module);
    }
    /* Not shipped: NULL, and nothing found anywhere else. */
    check(vvfp_load_patcher_dll("VVFP Not Shipped.dll") == NULL, "missing DLL is NULL");
    check(vvfp_patcher_dll("VVFP Not Shipped.dll") == NULL, "missing DLL is NULL (lookup)");
    /* The executable's folder missing altogether: NULL. */
    swprintf_s(g_module, 4096, L"%ls\\gone\\x.exe", folder);
    check(vvfp_load_patcher_dll("VVFP Harness Load.dll") == NULL, "missing game folder is NULL");

    if (g_failures == 0) {
        puts("all patcher_files checks passed");
        return 0;
    }
    printf("%d failures\n", g_failures);
    return 1;
}
