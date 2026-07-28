#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static HINSTANCE module_instance;

enum {
    IDD_FULL_MASTERY = 301,
    ID_BUY = 1007
};

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
}

static INT_PTR CALLBACK full_mastery_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command == ID_BUY) {
            EndDialog(window, 7);
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowVV2FullMasteryMenu(void) {
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_FULL_MASTERY),
        GetForegroundWindow(),
        full_mastery_dialog,
        0
    );
}

__declspec(dllexport) int __stdcall ShowVV2FullMasteryResult(
    unsigned int status,
    unsigned int changed,
    unsigned int new_elder_markers,
    unsigned int changed_but_unmarked
) {
    char message[256];
    if (status == 0) {
        lstrcpyA(
            message,
            "Everyone is already fully mastered.\r\n"
            "No tech points have been deducted."
        );
    } else if (status == 2) {
        lstrcpyA(
            message,
            "Not enough tech points.\r\n"
            "No tech points have been deducted."
        );
    } else {
        wsprintfA(
            message,
            "Fully mastered %u villagers.\r\n"
            "%u villagers became Esteemed Elders.\r\n"
            "%u fully mastered villagers remain without the Elder marker "
            "because the native 50-totem limit was reached.",
            changed,
            new_elder_markers,
            changed_but_unmarked
        );
    }
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION
    );
    return 0;
}
