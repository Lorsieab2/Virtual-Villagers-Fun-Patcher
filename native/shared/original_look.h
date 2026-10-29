/* original_look.h -- what "VVFP Original Look.dll" (native/vvfp_original_look) offers the Change Appearance
   windows.

   Change Appearance (the per-villager window and Change Appearance for All) has a "Reset to original" button
   (the owner, 2026-10-28): it puts a villager back to the head, body and mask they had before any Change
   Appearance or island event changed them, with the head look on Auto (native/shared/head_look.h).  This DLL
   keeps those originals: it records each villager's look the first time it sees them (at birth or arrival,
   or on the first run over an existing save), never over an original already kept, in the patcher's own
   per-save file, following the villager (native/vvfp_original_look/original_look_store.inc); Repair Saves &
   Logs adds the originals the patcher's logs prove for villagers changed before it existed
   (src/vv_original_look.py).  The windows find the DLL with GetModuleHandleA (VVFP Startup.dll loads it at
   game start); the DLL writes nothing to the game, and the windows log a Reset themselves.

   THE MASK is the value the game's Origins companion keeps for the villager -- 0 none, 1 Blue, 2 Orange,
   3 Red, 4 Purple, 5 the Tribal Chief's -- exactly what its VvfpMaskOf export answers and what its store
   is set with:
     A New Home       VVFP VV1 Origins Icons.dll  (vv1_mask_get / vv1_mask_set, "Virtual Villagers 1 Village
                      Masks - Save S.dat")
     The Lost Children VVFP VV2 Origins Icons.dll (VV2_MASK_TABLE, "Virtual Villagers 2 Village Masks")
     The Secret City  VVFP Origins Icons.dll      (VV3_GetMaskForRecord / VV3_SetMaskForRecord, "Village Masks")
     The Tree of Life VVFP VV4 Origins Icons.dll  (vv_peek_mask / vv_set_mask, "Village Masks")
     New Believers    VVFP Origins Icons.dll      (caf_get_mask / caf_set_mask, "Village Masks") -- the
                      patcher's cosmetic mask only: a Heathen's own mask is the game's (its faction, the
                      game's mask draw 0x4728C6) and is never part of the original look. */
#ifndef VVFP_ORIGINAL_LOOK_H
#define VVFP_ORIGINAL_LOOK_H

#define VVFP_ORIGINAL_LOOK_DLL "VVFP Original Look.dll"

/* int __stdcall VvfpOriginalLookGet(int game, const void *record, int *head, int *body, int *mask):
   1 and the three filled when the original look of the villager in `record` is known; 0, with the
   three untouched, when it is not (never seen, an original the logs cannot prove, the DLL started in
   another game, or the village not known yet). */
#define VVFP_ORIGINAL_LOOK_GET "VvfpOriginalLookGet"

#ifndef RC_INVOKED
typedef int (__stdcall *vvfp_original_look_get_fn)(int game, const void *record, int *head, int *body, int *mask);

/* The export, or NULL when the DLL is not in the game.  Asked each time a Change Appearance window opens
   (the DLL is never unloaded). */
static vvfp_original_look_get_fn vvfp_original_look_find(void) {
    HMODULE dll = GetModuleHandleA(VVFP_ORIGINAL_LOOK_DLL);
    return dll != NULL ? (vvfp_original_look_get_fn)GetProcAddress(dll, VVFP_ORIGINAL_LOOK_GET) : NULL;
}
#endif

/* The button every Change Appearance window adds. */
#define VVFP_ORIGINAL_LOOK_LABEL "Reset to original"

#endif /* VVFP_ORIGINAL_LOOK_H */
