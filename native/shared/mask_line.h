/* The logs' "Mask:" line: the mask a villager wears (the owner, 2026-10-06:
   "Mask type" in every villager record and snapshot).

   Two kinds of mask, by the names every Origins companion and the Story
   companion use (story_common.inc STORY_MASK_NAMES):

     - New Believers' own Heathen masks: a current Heathen (faction byte
       +0x1CEC) wears the one the game's mask draw picks (0x4728C6,
       native/shared/former_heathens.h vv_former_kind_of);
     - the patcher's cosmetic Heathen masks (Change Appearance, the Custom
       Island Event), kept by each game's Origins companion and answered by
       its VvfpMaskOf export (native/shared/story_bridge.h).  The companion
       is found loaded by name (GetModuleHandleA, never a search); not
       loaded, or no export: no cosmetic mask is known.

   NULL when the villager wears none.  Header-only and static. */
#ifndef VV_MASK_LINE_H
#define VV_MASK_LINE_H

#include <windows.h>
#include "former_heathens.h"

static const char *const VV_MASK_NAMES[6] = {
    NULL, "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask"
};

/* Each game's Origins companion (vvfp_startup.c ORIGINS). */
static const char *const VV_MASK_ORIGINS[6] = {
    NULL, "VVFP VV1 Origins Icons.dll", "VVFP VV2 Origins Icons.dll", "VVFP Origins Icons.dll",
    "VVFP VV4 Origins Icons.dll", "VVFP Origins Icons.dll",
};

typedef int (__stdcall *vv_mask_of_fn)(void *record);

static const char *vv_mask_name(int game, const unsigned char *record) {
    static const int FROM_KIND[5] = { 1, 2, 3, 4, 5 };   /* blue, orange, red, purple, chief */
    HMODULE origins;
    vv_mask_of_fn mask_of;
    int mask;
    if (record == NULL || game < 1 || game > 5) {
        return NULL;
    }
    if (game == 5 && record[VV5_FACTION] != 0) {
        return VV_MASK_NAMES[FROM_KIND[vv_former_kind_of(record)]];
    }
    origins = GetModuleHandleA(VV_MASK_ORIGINS[game]);
    if (origins == NULL) {
        return NULL;
    }
    mask_of = (vv_mask_of_fn)GetProcAddress(origins, "VvfpMaskOf");
    if (mask_of == NULL) {
        return NULL;
    }
    mask = mask_of((void *)record);
    return mask >= 1 && mask <= 5 ? VV_MASK_NAMES[mask] : NULL;
}

#endif /* VV_MASK_LINE_H */
