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
 * player chose, so the backup path is never reached from here.
 *
 * THE VILLAGE NAME. The reset matches parentage logs by the header line the
 * exporters wrote, because those files roll over by count and cannot be
 * addressed by slot. The name has to be resolved BEFORE the save is deleted;
 * afterwards there is nothing left to read it from.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

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
__declspec(dllexport) int __stdcall ResetDeletedTribe(int game, int slot) {
    char village[256];
    const char *header = NULL;

    if (game < 1 || game > 5 || slot < 1 || slot > 5) {
        return -1;
    }
    /* The header the statistics companion published while this village was
     * being played. It is the only way to identify that village's parentage
     * logs, which roll over by count and cannot be addressed by slot.
     *
     * Best-effort by design: a village deleted without ever being saved in
     * this session has published nothing, and vv_reset_slot_state then leaves
     * the parentage logs alone rather than deleting on a guess. The
     * slot-addressed files -- roster, statistics, sidecars -- are removed
     * either way, because those the slot does identify. */
    if (vv_village_recall(village, sizeof(village))) {
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
