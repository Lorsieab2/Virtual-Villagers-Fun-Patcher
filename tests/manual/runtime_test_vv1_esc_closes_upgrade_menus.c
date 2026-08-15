/* Real runtime test: confirms ESC closes both the Tech-screen ("Origins
   Upgrades") and Villager Details ("Villager Upgrades") menus, the same
   way Cancel already does, in case either dialog is ever stuck with no
   other way out. Both dialog templates give their Cancel button control
   ID 2 (IDCANCEL), which is what lets the standard Windows modal dialog
   loop's own IsDialogMessage translate ESC into WM_COMMAND(IDCANCEL)
   automatically -- this test proves that translation actually reaches
   the real compiled dialog rather than trusting that the .rc template
   still wires it correctly.

   Uses PostMessage, not SendMessage: SendMessage delivers directly to
   the window procedure and bypasses the modal loop's own
   GetMessage/IsDialogMessage/DispatchMessage cycle entirely, so it
   would not actually exercise the same path a real ESC keypress does.
   PostMessage queues the key event the same way real input does, so
   IsDialogMessage genuinely gets to intercept and translate it. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

typedef int (__stdcall *MenuFn)(int, int);

static int g_failures = 0;

#define CHECK(cond, msg, ...) do { \
    if (!(cond)) { \
        printf("  FAIL: " msg "\n", ##__VA_ARGS__); \
        g_failures++; \
    } else { \
        printf("  ok:   " msg "\n", ##__VA_ARGS__); \
    } \
} while (0)

static MenuFn g_fn;
static int g_arg1, g_arg2;
static int g_result;

DWORD WINAPI call_thread(LPVOID param) {
    (void)param;
    g_result = g_fn(g_arg1, g_arg2);
    return 0;
}

static void run_scenario(HMODULE dll, const char *export_name, int villager_menu, const char *title) {
    printf("\n=== %s (villager_menu=%d) ===\n", title, villager_menu);
    g_fn = (MenuFn)GetProcAddress(dll, export_name);
    if (!g_fn) { printf("  FAIL: export %s not found\n", export_name); g_failures++; return; }
    g_arg1 = villager_menu;
    g_arg2 = 0;
    g_result = -999;

    HANDLE thread = CreateThread(NULL, 0, call_thread, NULL, 0, NULL);
    HWND dlg = NULL;
    for (int i = 0; i < 150 && !dlg; ++i) { dlg = FindWindowA(NULL, title); Sleep(20); }
    CHECK(dlg != NULL, "dialog window appeared");
    if (!dlg) { WaitForSingleObject(thread, 3000); CloseHandle(thread); return; }

    SetForegroundWindow(dlg);
    Sleep(200);
    PostMessageA(dlg, WM_KEYDOWN, VK_ESCAPE, 0);
    PostMessageA(dlg, WM_KEYUP, VK_ESCAPE, 0);

    DWORD wait = WaitForSingleObject(thread, 3000);
    if (wait == WAIT_TIMEOUT) {
        CHECK(0, "dialog closed within 3s of ESC (it did not)");
        HWND still = FindWindowA(NULL, title);
        if (still) { PostMessageA(still, WM_CLOSE, 0, 0); }
        CloseHandle(thread);
        return;
    }
    CloseHandle(thread);
    CHECK(g_result == -1, "ESC produced the same result as Cancel (-1), got %d", g_result);
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "assets\\origins\\VVFP VV1 Origins Icons.dll";
    HMODULE dll = LoadLibraryA(path);
    if (!dll) {
        printf("FAIL: could not load DLL, GetLastError=%lu\n", GetLastError());
        return 1;
    }
    printf("DLL loaded OK: %s\n", path);

    run_scenario(dll, "ShowOriginsUpgradeMenuState", 0, "Origins Upgrades");
    run_scenario(dll, "ShowOriginsUpgradeMenuState", 1, "Villager Upgrades");

    printf("\n=====================================\n");
    if (g_failures == 0) {
        printf("ALL RUNTIME SCENARIOS PASSED\n");
    } else {
        printf("%d CHECK(S) FAILED\n", g_failures);
    }
    return g_failures == 0 ? 0 : 1;
}
