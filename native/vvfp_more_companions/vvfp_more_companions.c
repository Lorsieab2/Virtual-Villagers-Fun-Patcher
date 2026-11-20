/* VVFP More Companions -- the third word of companions (native/shared/startup_companions_3.h).

   WHY.  VVFP Startup.dll starts the companions a build ships by the bits the executable's startup stub hands it,
   two words of 32 (native/shared/startup_companions.h, startup_companions_2.h), and both are nearly full (the owner,
   2026-11-17: every new multiplier slider needs a companion of its own).  Rather than change the stub in every
   executable, this second-word companion starts a third word.

   WHAT.  Its VvfpStartup(game, shipped), called by VVFP Startup.dll before WinMain, reads "VVFP More
   Companions.txt" beside it (one decimal number, the bits of the third-word companions THIS build ships, written by
   the patcher when it publishes the build) and starts each named companion exactly as VVFP Startup.dll starts its
   own: loaded by its full path in the patcher's folder (native/shared/patcher_files.h, never the search order), its
   VvfpStartup(game, shipped) called with the first word, a fault inside it abandoned (structured exception
   handling) and the rest still started.

   SAFETY.  A missing or unreadable file, or no digit, is 0: nothing is started.  A companion that is not shipped is
   skipped; one that fails to load, or lacks VvfpStartup, is skipped.  Only the file's first 15 bytes are read;
   nothing is written to a save, a villager record or a file; no text is shown; no game routine is called (at this
   point the game has initialised nothing).  No debug output. */
#include <windows.h>
#include "../shared/patcher_files.h"
#include "../shared/startup_companions_3.h"

#define MC_CHOICE_FILE "VVFP More Companions.txt"

typedef void (__stdcall *vvfp_startup_fn)(int game, unsigned int shipped);

static unsigned int g_word;
static int g_started;

/* The third word from "VVFP More Companions.txt": its leading decimal digits (spaces first are skipped), else 0. */
static unsigned int read_word(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char text[16];
    DWORD got = 0, i = 0;
    HANDLE file;
    unsigned long long value = 0;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, MC_CHOICE_FILE) == 0) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(file, text, (DWORD)(sizeof text - 1), &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    while (i < got && (text[i] == ' ' || text[i] == '\t')) {
        ++i;
    }
    for (; i < got && text[i] >= '0' && text[i] <= '9'; ++i) {
        value = value * 10u + (unsigned int)(text[i] - '0');
        if (value > 0xFFFFFFFFull) {
            return 0;                    /* not a word the patcher writes: start nothing */
        }
    }
    return (unsigned int)value;
}

static void start(int game, unsigned int shipped, const char *name) {
    HMODULE module = vvfp_load_patcher_dll(name);
    vvfp_startup_fn startup;
    if (module == NULL) {
        return;
    }
    startup = (vvfp_startup_fn)(void *)GetProcAddress(module, "VvfpStartup");
    if (startup != NULL) {
        __try {
            startup(game, shipped);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
}

/* The third word read at start (for the tests' emulation). */
unsigned int __stdcall VvfpMoreCompanionsWord(void) {
    return g_word;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    size_t i;
    if (g_started) {
        return;
    }
    g_started = 1;
    g_word = read_word();
    for (i = 0; i < VVFP_STARTUP_COMPANION_COUNT_3 && i < 32; ++i) {
        if (g_word & (1u << i)) {
            start(game, shipped, VVFP_STARTUP_COMPANIONS_3[i]);
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
