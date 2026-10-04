/* Runs harness_ldw_tree.h for real, against a throwaway Documents folder.

   The header deletes folders in the player's real LDW folder, so its rules
   are proven on disk, not by reading them: every scenario below runs a child
   copy of this exe (the header works at process start and exit), with
   Documents redirected to a fresh folder under %TEMP%, and then inspects
   what is left.

     absent       no LDW at all: the child's whole tree, and LDW, are removed
     junction     LDW is a junction to another folder: the junction and the
                  folder's own file survive (a relocated save folder must
                  never be disconnected); the run's own folder inside it goes
     tree-link    LDW\<harness> is a junction: the run refuses to start; the
                  junction and its target survive
     pre-tree     LDW\<harness> already holds a .txt log and an empty folder,
                  and the run's first step empties its log folder (as several
                  harnesses do): the run refuses to start before that step,
                  so both survive
     pre-root     LDW holds another game's folder: it survives, the new tree
                  goes, LDW stays
     link-inside  the run itself makes a junction inside its new tree, to a
                  folder outside: the folder's file survives (never entered)
     exit         the child exit()s with a failure code: still cleaned
     crash        the child dies of an access violation: still cleaned
     overlap      a second run starts while the first is still running: it
                  waits, so the first run's exit cannot delete its files
     case         the same, with the first run's exe name in upper case: the
                  folder is the same, so the lock must be too

   Built and run by scripts/build_harness_ldw_tree_harness.ps1. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static int harness_docs(wchar_t *out) {
    DWORD n = GetEnvironmentVariableW(L"VVFP_HARNESS_LDW_DOCS", out, MAX_PATH);
    return n > 0 && n < MAX_PATH;
}
#define HARNESS_LDW_DOCUMENTS(buffer) harness_docs(buffer)
#include "harness_ldw_tree.h"

static int failures;
static wchar_t docs[MAX_PATH], ldw[MAX_PATH], tree[MAX_PATH], base[MAX_PATH];

static void check(int ok, const char *what) {
    printf("  [%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++failures;
}

static void path_of(wchar_t *out, const wchar_t *folder, const wchar_t *rel) {
    _snwprintf(out, MAX_PATH, L"%ls\\%ls", folder, rel);
    out[MAX_PATH - 1] = 0;
}

static void touch(const wchar_t *path) {
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
}

static int exists(const wchar_t *path) {
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

static int is_link(const wchar_t *path) {
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_REPARSE_POINT);
}

static int run(const wchar_t *cmdline, int wait) {
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    wchar_t line[2048];
    DWORD code = 99;
    ZeroMemory(&si, sizeof si);
    si.cb = sizeof si;
    lstrcpynW(line, cmdline, 2048);
    if (!CreateProcessW(NULL, line, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) return -1;
    CloseHandle(pi.hThread);
    if (!wait) { CloseHandle(pi.hProcess); return 0; }
    WaitForSingleObject(pi.hProcess, 60000);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hProcess);
    return (int)code;
}

static int child(const wchar_t *mode) {
    wchar_t exe[MAX_PATH], line[2048];
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    _snwprintf(line, 2048, L"\"%ls\" child %ls", exe, mode);
    line[2047] = 0;
    return run(line, 1);
}

static void junction(const wchar_t *link, const wchar_t *target) {
    wchar_t line[2048];
    _snwprintf(line, 2048, L"cmd.exe /c mklink /J \"%ls\" \"%ls\" >nul", link, target);
    line[2047] = 0;
    run(line, 1);
}

/* Remove a throwaway folder: links are unlinked, never entered. */
static void wipe(const wchar_t *folder) {
    wchar_t pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAW f;
    HANDLE h;
    if (is_link(folder)) { RemoveDirectoryW(folder); return; }
    path_of(pattern, folder, L"*");
    h = FindFirstFileW(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..")) continue;
            path_of(path, folder, f.cFileName);
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) wipe(path);
            else DeleteFileW(path);
        } while (FindNextFileW(h, &f));
        FindClose(h);
    }
    RemoveDirectoryW(folder);
}

/* What a companion would write under LDW\<harness>. */
static void write_tree(void) {
    wchar_t p[MAX_PATH];
    CreateDirectoryW(ldw, NULL);
    CreateDirectoryW(tree, NULL);
    path_of(p, tree, L"Logs"); CreateDirectoryW(p, NULL);
    path_of(p, tree, L"Logs\\Deaths"); CreateDirectoryW(p, NULL);
    path_of(p, tree, L"Logs\\Deaths\\log 1.txt"); touch(p);
    path_of(p, tree, L"Data"); CreateDirectoryW(p, NULL);
}

static int child_main(const wchar_t *mode) {
    wchar_t p[MAX_PATH];
    harness_ldw_tree_begin();
    if (!wcscmp(mode, L"write")) { write_tree(); return 0; }
    if (!wcscmp(mode, L"exit")) { write_tree(); exit(3); }
    if (!wcscmp(mode, L"link-inside")) {
        wchar_t target[MAX_PATH];
        write_tree();
        if (!GetEnvironmentVariableW(L"VVFP_HARNESS_LDW_TARGET", target, MAX_PATH)) return 2;
        path_of(p, tree, L"link");
        junction(p, target);
        return is_link(p) ? 0 : 2;
    }
    if (!wcscmp(mode, L"crash")) {
        SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
        write_tree();
        *(volatile int *)0 = 1;
        return 0;
    }
    if (!wcscmp(mode, L"wipe")) {
        /* What several harnesses do first: empty their log folder. */
        wchar_t pattern[MAX_PATH], one[MAX_PATH];
        WIN32_FIND_DATAW f;
        HANDLE h;
        path_of(pattern, tree, L"Logs\\Deaths\\*.txt");
        h = FindFirstFileW(pattern, &f);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                path_of(p, tree, L"Logs\\Deaths");
                path_of(one, p, f.cFileName);
                DeleteFileW(one);
            } while (FindNextFileW(h, &f));
            FindClose(h);
        }
        write_tree();
        return 0;
    }
    if (!wcscmp(mode, L"hold")) {   /* first run: holds the harness, writes nothing */
        path_of(p, docs, L"hold started"); touch(p);
        Sleep(2000);
        return 0;
    }
    if (!wcscmp(mode, L"late")) {   /* second run: writes, then checks after the first ended */
        write_tree();
        Sleep(3000);
        path_of(p, tree, L"Logs\\Deaths\\log 1.txt");
        if (exists(p)) { path_of(p, docs, L"late kept its file"); touch(p); }
        return 0;
    }
    return 9;
}

static void fresh(void) {
    wipe(docs);
    CreateDirectoryW(docs, NULL);
}

int main(int argc, char **argv) {
    wchar_t temp[MAX_PATH], exe[MAX_PATH], p[MAX_PATH], target[MAX_PATH], *b, *dot;
    int i;

    GetModuleFileNameW(NULL, exe, MAX_PATH);
    b = wcsrchr(exe, L'\\');
    lstrcpynW(base, b ? b + 1 : exe, MAX_PATH);
    dot = wcsrchr(base, L'.');
    if (dot) *dot = 0;

    if (argc >= 3 && !strcmp(argv[1], "child")) {
        wchar_t mode[64];
        if (!harness_docs(docs)) return 2;
        path_of(ldw, docs, L"LDW");
        path_of(tree, ldw, base);
        MultiByteToWideChar(CP_ACP, 0, argv[2], -1, mode, 64);
        return child_main(mode);
    }

    GetTempPathW(MAX_PATH, temp);
    _snwprintf(docs, MAX_PATH, L"%lsvvfp_harness_ldw_docs_%lu", temp, GetCurrentProcessId());
    _snwprintf(target, MAX_PATH, L"%lsvvfp_harness_ldw_target_%lu", temp, GetCurrentProcessId());
    docs[MAX_PATH - 1] = target[MAX_PATH - 1] = 0;
    SetEnvironmentVariableW(L"VVFP_HARNESS_LDW_DOCS", docs);
    path_of(ldw, docs, L"LDW");
    path_of(tree, ldw, base);

    printf("== absent: no LDW before the run ==\n");
    fresh();
    check(child(L"write") == 0, "child ran");
    check(!exists(tree), "the harness folder is removed");
    check(!exists(ldw), "LDW, which the run created, is removed");

    printf("== junction: LDW is a junction to a relocated save folder ==\n");
    fresh();
    wipe(target);
    CreateDirectoryW(target, NULL);
    path_of(p, target, L"player save.ldw"); touch(p);
    junction(ldw, target);
    check(is_link(ldw), "setup: LDW is a junction");
    check(child(L"write") == 0, "child ran");
    check(is_link(ldw), "THE LDW JUNCTION SURVIVES");
    path_of(p, target, L"player save.ldw");
    check(exists(p), "the relocated folder's own file survives");
    path_of(p, target, base);
    check(!exists(p), "the run's own folder inside it is still removed");
    RemoveDirectoryW(ldw);
    wipe(target);

    printf("== tree-link: LDW\\<harness> is a junction ==\n");
    fresh();
    CreateDirectoryW(ldw, NULL);
    CreateDirectoryW(target, NULL);
    path_of(p, target, L"keep.txt"); touch(p);
    junction(tree, target);
    check(is_link(tree), "setup: the harness folder is a junction");
    check(child(L"write") == 2, "the run refuses to start");
    check(is_link(tree), "the junction survives");
    path_of(p, target, L"keep.txt");
    check(exists(p), "its target's file survives");
    check(exists(ldw), "LDW, which existed, survives");
    RemoveDirectoryW(tree);
    wipe(target);

    printf("== pre-tree: the harness folder already holds a log, and the run empties its log folder first ==\n");
    fresh();
    CreateDirectoryW(ldw, NULL);
    CreateDirectoryW(tree, NULL);
    path_of(p, tree, L"Logs"); CreateDirectoryW(p, NULL);
    path_of(p, tree, L"Logs\\Deaths"); CreateDirectoryW(p, NULL);
    path_of(p, tree, L"Logs\\Deaths\\Deaths Log 1.txt"); touch(p);
    path_of(p, tree, L"old empty"); CreateDirectoryW(p, NULL);
    check(child(L"wipe") == 2, "the run refuses to start");
    path_of(p, tree, L"Logs\\Deaths\\Deaths Log 1.txt");
    check(exists(p), "THE PRE-EXISTING .txt SURVIVES the run's own emptying step");
    path_of(p, tree, L"old empty"); check(exists(p), "a pre-existing empty folder survives");
    path_of(p, tree, L"Data"); check(!exists(p), "the run wrote nothing");

    printf("== pre-root: LDW already holds a game's folder ==\n");
    fresh();
    CreateDirectoryW(ldw, NULL);
    path_of(p, ldw, L"A Game"); CreateDirectoryW(p, NULL);
    path_of(p, ldw, L"A Game\\save.ldw"); touch(p);
    check(child(L"write") == 0, "child ran");
    check(!exists(tree), "the new harness folder is removed");
    path_of(p, ldw, L"A Game\\save.ldw"); check(exists(p), "the game's save survives");
    check(exists(ldw), "LDW survives");

    printf("== link-inside: a junction inside the run's own tree ==\n");
    fresh();
    CreateDirectoryW(target, NULL);
    path_of(p, target, L"keep.txt"); touch(p);
    SetEnvironmentVariableW(L"VVFP_HARNESS_LDW_TARGET", target);
    check(child(L"link-inside") == 0, "child ran and made the junction");
    path_of(p, target, L"keep.txt");
    check(exists(p), "THE JUNCTION'S TARGET IS NEVER ENTERED: its file survives");
    path_of(p, tree, L"link");
    check(is_link(p), "the junction itself is left alone");
    path_of(p, tree, L"Logs");
    check(!exists(p), "the rest of the run's tree is removed");
    wipe(docs);
    wipe(target);

    printf("== exit: the run fails through exit() ==\n");
    fresh();
    check(child(L"exit") == 3, "child exited with its failure code");
    check(!exists(ldw), "cleaned up anyway");

    printf("== crash: the run dies of an access violation ==\n");
    fresh();
    check(child(L"crash") != 0, "child crashed");
    check(!exists(ldw), "cleaned up anyway");

    printf("== overlap: a second run starts while the first is running ==\n");
    fresh();
    {
        wchar_t line[2048];
        _snwprintf(line, 2048, L"\"%ls\" child hold", exe);
        line[2047] = 0;
        run(line, 0);
        path_of(p, docs, L"hold started");
        for (i = 0; i < 200 && !exists(p); ++i) Sleep(25);
        check(exists(p), "setup: the first run is under way");
        check(child(L"late") == 0, "the second run finished");
        path_of(p, docs, L"late kept its file");
        check(exists(p), "THE FIRST RUN'S EXIT DID NOT DELETE THE SECOND RUN'S FILE");
        check(!exists(tree), "and the second run cleaned up its own tree");
    }

    printf("== case: the first run's exe name is spelt in other letter case ==\n");
    fresh();
    {
        /* Same folder (names are case-insensitive), so the same lock. */
        wchar_t upper_dir[MAX_PATH], upper_exe[MAX_PATH], upper_base[MAX_PATH], line[2048];
        _snwprintf(upper_dir, MAX_PATH, L"%lsvvfp_harness_ldw_case_%lu", temp, GetCurrentProcessId());
        upper_dir[MAX_PATH - 1] = 0;
        wipe(upper_dir);
        CreateDirectoryW(upper_dir, NULL);
        lstrcpynW(upper_base, base, MAX_PATH);
        CharUpperBuffW(upper_base, (DWORD)wcslen(upper_base));
        _snwprintf(upper_exe, MAX_PATH, L"%ls\\%ls.exe", upper_dir, upper_base);
        upper_exe[MAX_PATH - 1] = 0;
        check(CopyFileW(exe, upper_exe, FALSE) != 0, "setup: an upper-case copy of this exe");
        check(lstrcmpW(upper_base, base) != 0, "setup: the two names differ in case");
        _snwprintf(line, 2048, L"\"%ls\" child hold", upper_exe);
        line[2047] = 0;
        run(line, 0);
        path_of(p, docs, L"hold started");
        for (i = 0; i < 200 && !exists(p); ++i) Sleep(25);
        check(exists(p), "setup: the upper-case run is under way");
        check(child(L"late") == 0, "the lower-case run finished");
        path_of(p, docs, L"late kept its file");
        check(exists(p), "THE OTHER-CASE RUN WAITED: its exit did not delete this run's file");
        check(!exists(tree), "and this run cleaned up its own tree");
        for (i = 0; i < 100 && !DeleteFileW(upper_exe); ++i) Sleep(50);
        wipe(upper_dir);
    }

    wipe(docs);
    wipe(target);
    printf("== %d failure(s) ==\n", failures);
    return failures != 0;
}
