/* The companion the games call when a tribe is deleted.
 *
 * WHY THIS DLL EXISTS AT ALL. vv_reset_slot_state has been correct for a long
 * time and has never once run: save_reset.c was not compiled into any shipped
 * companion, so nothing in a released build could call it. The symptom the
 * owner reported -- masks bleeding onto villagers in a brand-new village --
 * is exactly what a reset that never happens looks like. This DLL is the
 * missing link between the hook in the executable and the sweep that was
 * already written.
 *
 * WHAT CALLS IT. Each game's save-slot menu deletes a tribe through a small
 * deleteSave(slot) function. That function has two callers and only one of
 * them is a reset: the other is a save routine rotating backup generations,
 * which passes slot + 0x14 rather than the slot. The patch hooks the menu
 * handler's own `push edi; call <thunk>`, where edi is the raw slot the
 * player chose, so the backup path is never reached from here. The main
 * menu's Start Over never calls deleteSave; its own hook calls this with the
 * village's current slot just before the game re-creates the village there
 * (docs/start-over-reset-hook.md).
 *
 * THE VILLAGE NAME. The reset matches parentage logs by the header line the
 * exporters wrote, because those files roll over by count and cannot be
 * addressed by slot. The name has to be resolved BEFORE the save is deleted;
 * afterwards there is nothing left to read it from.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>   /* strstr, for the header's (Save N) check */

#include "save_reset.h"
#include "save_folder.h"
#include "village_identity.h"

/* Erase this patcher's state for one deleted tribe.
 *
 * `game` is 1..5 and `slot` is the slot the player chose. Returns the number
 * of files removed, or -1 when the save folder could not be resolved and
 * nothing was attempted.
 *
 * FAILING IS SAFE AND SILENT. The game is mid-delete and has no way to show
 * an error, so every failure path leaves files alone rather than guessing.
 * A stale sidecar is a far smaller harm than a wrong deletion. */
/* Does this header belong to the slot being deleted?
 *
 * THE PUBLISHED HEADER IS THE LAST VILLAGE SAVED, NOT NECESSARILY THIS ONE.
 * A player can save one village, return to the save-slot menu, and delete a
 * different slot. The header still names the village they were playing, and
 * handing that to the sweep would delete THAT village's parentage logs --
 * which are matched by header -- while leaving the deleted village's logs
 * untouched. Exactly backwards, and unrecoverable. Found in review.
 *
 * The exporters write "Village: <name> (Save <n>)", so the slot is in the
 * header and can be checked against the one being erased. A header that does
 * not match, or one whose shape is unexpected, is refused: the sweep then
 * leaves parentage alone rather than deleting on a guess, while the
 * slot-addressed files -- roster, statistics, sidecars -- still go, because
 * those the slot identifies on its own. */
static int header_is_for_slot(const char *header, int slot) {
    const char *marker = " (Save ";
    const char *found;
    int value = 0;
    int digits = 0;

    if (header == NULL || slot < 1 || slot > 9) {
        return 0;
    }
    /* The LAST occurrence, so a village whose own name contains the marker
       cannot shadow the real one. */
    found = NULL;
    {
        const char *scan = header;
        for (;;) {
            const char *hit = strstr(scan, marker);
            if (hit == NULL) {
                break;
            }
            found = hit;
            scan = hit + 1;
        }
    }
    if (found == NULL) {
        return 0;
    }
    found += lstrlenA(marker);
    while (*found >= '0' && *found <= '9') {
        value = value * 10 + (*found - '0');
        ++found;
        ++digits;
        if (digits > 2) {
            return 0;       /* not a save number this game can produce */
        }
    }
    if (digits == 0 || *found != ')') {
        return 0;
    }
    return value == slot;
}

/* THE VILLAGE IN THE SLOT'S OWN SAVE FILE.
 *
 * Live, VV2: launch the game, Start Over at once, and the old village's Births
 * and Conceptions log survived -- nothing had been saved in that process, so
 * nothing had been published for vv_village_recall to return, and the new
 * village then wrote into the old one's log. Launch-then-Start-Over is the
 * common case, so the village has to be identified without a prior save.
 *
 * Both reset hooks run BEFORE the game touches the slot's save: the tribe
 * delete before deleteSave removes it, Start Over before Restart overwrites
 * it. So "<base><slot>.ldw" still holds the village being erased, and its
 * name is read from it exactly as the statistics companion reads it for the
 * header: the file is the save buffer behind a small file header, and the
 * buffer is handed to vv_village_name, the same function, at the same buffer
 * offset. vv_village_header then formats it. The header is therefore the
 * one the exporters wrote, byte for byte.
 *
 * Measured on the owner's saves (read-only) and the five save routines:
 *
 *     game  file header  length field  buffer length
 *     VV1       12           +8          0x0ABDC
 *     VV2       12           +8          0x30370
 *     VV3       12           +8          0x12F1C
 *     VV4       24          +16          0x1710C
 *     VV5       24          +16          0x17D78
 *
 * every file opening with "ldwg", sized exactly header + buffer.
 *
 * The base name before the slot number comes from the game, not from a string
 * here, so it is found: exactly one file named "<something><slot>.ldw" whose
 * something does not end in a digit (so slot 1 never picks up the backup
 * generations 21 and 41), which is this game's save by magic, length field
 * and size. None, or more than one, and nothing is returned -- the caller
 * then falls back to the published header, and failing that leaves the
 * parentage logs alone, exactly as before. The save is only read. */
static const DWORD SAVE_FILE_HEADER[5] = { 12u, 12u, 12u, 24u, 24u };
static const DWORD SAVE_LENGTH_AT[5] = { 8u, 8u, 8u, 16u, 16u };
static const DWORD SAVE_BUFFER_BYTES[5] = {
    0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u
};

/* Is `name` "<prefix><slot>.ldw" with a non-empty prefix not ending in a digit? */
static int is_slot_save_name(const wchar_t *name, int slot) {
    int length = lstrlenW(name);
    const wchar_t *tail;

    if (length < 6) {
        return 0;
    }
    tail = name + length - 5;
    if (tail[0] != (wchar_t)(L'0' + slot) || lstrcmpiW(tail + 1, L".ldw") != 0) {
        return 0;
    }
    return !(tail[-1] >= L'0' && tail[-1] <= L'9');
}

/* "\\*<slot>.ldw" + NUL: all the reader appends to the folder itself. */
#define SAVE_FILTER_RESERVE 8

/* Write the header of the village saved in `slot` under `folder` into `out`.
   Returns 1 only when exactly one valid save for this game and slot exists
   and holds a readable name. */
int vv_saved_village_header(int game, int slot, const wchar_t *folder,
                            char *out, size_t size) {
    WIN32_FIND_DATAW found;
    HANDLE search;
    wchar_t filter[MAX_PATH];
    wchar_t path[MAX_PATH];
    char name[VV_VILLAGE_NAME_MAX];
    char header[256];
    int valid = 0;
    DWORD expected;

    if (out == NULL || size == 0) {
        return 0;
    }
    out[0] = '\0';
    if (folder == NULL || game < 1 || game > 5 || slot < 1 || slot > 5
        || lstrlenW(folder) + SAVE_FILTER_RESERVE >= MAX_PATH) {
        return 0;
    }
    expected = SAVE_FILE_HEADER[game - 1] + SAVE_BUFFER_BYTES[game - 1];
    wsprintfW(filter, L"%ls\\*%d.ldw", folder, slot);
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    header[0] = '\0';
    do {
        HANDLE file;
        unsigned char *data;
        DWORD got = 0;
        DWORD length;

        if ((found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            || !is_slot_save_name(found.cFileName, slot)
            || found.nFileSizeHigh != 0 || found.nFileSizeLow != expected
            || lstrlenW(folder) + 1 + lstrlenW(found.cFileName) >= MAX_PATH) {
            continue;
        }
        wsprintfW(path, L"%ls\\%ls", folder, found.cFileName);
        file = CreateFileW(path, GENERIC_READ,
                           FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file == INVALID_HANDLE_VALUE) {
            continue;
        }
        /* Zero padding past the end, so the name reader's fixed span never
           leaves the allocation even when the name sits near the end. */
        data = (unsigned char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                          expected + VV_VILLAGE_NAME_MAX);
        if (data == NULL) {
            CloseHandle(file);
            continue;
        }
        if (ReadFile(file, data, expected, &got, NULL) && got == expected
            && data[0] == 'l' && data[1] == 'd' && data[2] == 'w' && data[3] == 'g') {
            CopyMemory(&length, data + SAVE_LENGTH_AT[game - 1], sizeof length);
            if (length == SAVE_BUFFER_BYTES[game - 1]) {
                ++valid;
                /* The companion reads the name at manager + 8 + offset; the
                   save buffer is what sits at manager + 8. */
                if (vv_village_name(game,
                                    data + SAVE_FILE_HEADER[game - 1] - 8,
                                    name)) {
                    if (!vv_village_header(header, sizeof header, name, slot)) {
                        header[0] = '\0';
                    }
                } else {
                    header[0] = '\0';
                }
            }
        }
        HeapFree(GetProcessHeap(), 0, data);
        CloseHandle(file);
    } while (FindNextFileW(search, &found));
    FindClose(search);
    if (valid != 1 || header[0] == '\0') {
        return 0;
    }
    lstrcpynA(out, header, (int)size);
    return 1;
}

/* Story / Cheat Upgrades: a pick or custom island event queued in the village
 * being left must never be delivered into the next one, so the story
 * companion is told the village is gone. Only when it is already loaded
 * (GetModuleHandle never loads a DLL); without the row it is not there and
 * nothing happens. */
typedef void (__stdcall *story_village_reset_fn)(int game, int slot);

static void notify_story_upgrades(int game, int slot) {
    HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
    story_village_reset_fn reset;
    if (story == NULL) {
        return;
    }
    reset = (story_village_reset_fn)(void *)GetProcAddress(story, "VvfpStoryVillageReset");
    if (reset != NULL) {
        reset(game, slot);
    }
}

__declspec(dllexport) int __stdcall ResetDeletedTribe(int game, int slot) {
    char village[256];
    wchar_t folder[MAX_PATH];
    const char *header = NULL;

    if (game < 1 || game > 5 || slot < 1 || slot > 5) {
        return -1;
    }
    notify_story_upgrades(game, slot);
    /* The village in the slot's own save, which both hooks reach before the
     * game removes or overwrites it (see vv_saved_village_header). The
     * reserve is the reader's own "\\*<slot>.ldw" filter; it bounds each full
     * save filename separately, so a longer reserve would only refuse
     * folders whose saves still fit. */
    if (vv_save_folder_w(folder, SAVE_FILTER_RESERVE)
        && vv_saved_village_header(game, slot, folder, village, sizeof(village))) {
        header = village;
    }
    /* Otherwise the header the statistics companion published while this
     * village was being played, when it names this slot.
     *
     * With neither, vv_reset_slot_state leaves the parentage logs alone
     * rather than deleting on a guess. The slot-addressed files -- roster,
     * statistics, sidecars -- are removed either way, because those the slot
     * does identify. */
    else if (vv_village_recall(village, sizeof(village))
             && header_is_for_slot(village, slot)) {
        header = village;
    }
    return vv_reset_slot_state(game, slot, header);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
