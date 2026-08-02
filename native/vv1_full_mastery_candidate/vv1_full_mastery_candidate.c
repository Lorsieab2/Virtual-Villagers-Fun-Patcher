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

__declspec(dllexport) int __stdcall ShowVV1FullMasteryMenu(void) {
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_FULL_MASTERY),
        GetForegroundWindow(),
        full_mastery_dialog,
        0
    );
}

__declspec(dllexport) int __stdcall ShowVV1FullMasteryResult(
    unsigned int status,
    unsigned int changed
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
    } else if (status == 3) {
        lstrcpyA(
            message,
            "Full Mastery cannot be applied because an eligible villager has "
            "an out-of-range skill.\r\n"
            "No tech points have been deducted."
        );
    } else if (status == 4) {
        lstrcpyA(
            message,
            "Full Mastery could not be verified after native writes.\r\n"
            "No tech points have been deducted."
        );
    } else {
        wsprintfA(
            message,
            "Fully mastered %u villagers.",
            changed
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
