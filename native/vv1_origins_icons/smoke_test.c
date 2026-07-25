#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef int (__stdcall *show_menu_fn)(int villager_menu, int state);

static DWORD WINAPI close_dialog(LPVOID parameter) {
    const char *title = (const char *)parameter;
    int attempt;
    for (attempt = 0; attempt < 100; ++attempt) {
        HWND window = FindWindowA(NULL, title);
        if (window != NULL) {
            PostMessageA(window, WM_COMMAND, MAKEWPARAM(IDCANCEL, BN_CLICKED), 0);
            return 0;
        }
        Sleep(20);
    }
    return 1;
}

static int exercise(show_menu_fn show_menu, int villager_menu, int state) {
    const char *title = villager_menu ? "Villager Upgrades" : "Origins Upgrades";
    HANDLE closer = CreateThread(NULL, 0, close_dialog, (LPVOID)title, 0, NULL);
    int result;
    if (closer == NULL) {
        return 10;
    }
    result = show_menu(villager_menu, state);
    WaitForSingleObject(closer, 3000);
    CloseHandle(closer);
    return result == -1 ? 0 : 11;
}

int main(int argc, char **argv) {
    unsigned char villager[0x3D8];
    HMODULE module;
    show_menu_fn show_menu;
    int result;
    const char *path = argc > 1 ? argv[1] : "VVFP Origins Icons.dll";

    module = LoadLibraryA(path);
    if (module == NULL) {
        fprintf(stderr, "LoadLibraryA failed: %lu\n", GetLastError());
        return 1;
    }
    show_menu = (show_menu_fn)GetProcAddress(module, "ShowOriginsUpgradeMenu");
    if (show_menu == NULL) {
        fprintf(stderr, "GetProcAddress failed: %lu\n", GetLastError());
        FreeLibrary(module);
        return 2;
    }

    result = exercise(show_menu, 0, 3);
    if (result != 0) {
        FreeLibrary(module);
        return result;
    }

    memset(villager, 0, sizeof(villager));
    *(int *)(villager + 0x348) = 100;
    *(int *)(villager + 0x398) = -1;
    *(int *)(villager + 0x39C) = -1;
    *(int *)(villager + 0x3A0) = -1;
    result = exercise(show_menu, 1, (int)(UINT_PTR)villager);
    FreeLibrary(module);
    return result;
}
