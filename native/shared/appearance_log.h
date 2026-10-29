/* "Appearance changed" records (the owner, 2026-10-07: appearance changes "sure. Log those.").

   Origins' Change Appearance (and Change Appearance for All) gives a villager a new head and body.
   Nothing else records it, so the Family Tree Maker could not tell that a record carrying the old
   look -- a child's parent fields, a Birth record -- is the same villager as the living one with the
   new look.  Each change is logged in the Births and Conceptions log through the Parentage Export
   DLL's WriteVillageRecord, the same way "Epitaph changed" is: under the village's header, held
   until the next save (so the log never runs ahead of the save), unnumbered, never rolling:

       Appearance changed
         Name: Ann
         Old head: 3
         Old body: 4
         New head: 7
         New body: 8
         Old mask: none
         New mask: Red Mask

   The two mask lines (the owner, 2026-10-28: mask-only changes "Log them") name the Heathen mask
   Change Appearance keeps on the villager before and after, by the names every log uses
   (native/shared/mask_line.h: "none", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal
   Chief Mask"); they are written whenever the caller knows the masks (vv_log_appearance_mask), so a
   change of the mask alone is logged too, its head and body lines old = new.  Records written before
   carry no mask lines, and every reader takes them as they are (the mask not recorded).  The lines
   after "New body" keep the four look lines first, as parentage_export.c relook_last_name reads them.

   Nothing is written when the Births and Conceptions log is not part of the game (the DLL is not
   there), or when the look did not change.  It never changes the villager or the game. */
#ifndef VVFP_APPEARANCE_LOG_H
#define VVFP_APPEARANCE_LOG_H

#include <windows.h>

#include "patcher_files.h"

#define VV_KIND_APPEARANCE 7      /* parentage_export.c's KIND_APPEARANCE */

typedef int (__stdcall *vv_write_village_record_fn)(int, int, const void *, int, const char *, const char *,
                                                    int);

typedef int (__stdcall *vv_story_appearance_fn)(int, const void *, int, int);

/* The masks Change Appearance keeps, by the names every log uses (mask_line.h VV_MASK_NAMES; "none"). */
static const char *const VV_APPEARANCE_MASK_NAMES[6] = {
    "none", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask"
};

/* Log one villager's change of look: head, body and -- when the caller knows them, 0..5 each -- the mask
   before and after (-1 for either: not known, no mask lines).  Nothing when nothing changed. */
static void vv_log_appearance_mask(int game, const void *record, int old_head, int old_body, int old_mask,
                                   int new_head, int new_body, int new_mask) {
    static vv_write_village_record_fn write_record;
    static int looked;
    char before[220];
    int masks = old_mask >= 0 && old_mask <= 5 && new_mask >= 0 && new_mask <= 5;
    if (record == NULL || (old_head == new_head && old_body == new_body && (!masks || old_mask == new_mask))) {
        return;
    }
    /* The Story / Cheat Upgrades companion keeps a custom title by the villager's
       looks: told FIRST, so a log written in this very frame (a Death, a
       Disappeared record) compares against the new head and body, not the
       old ones the file still holds until its next tick.  Only when it is
       already loaded (GetModuleHandle never loads a DLL). */
    {
        HMODULE story = GetModuleHandleA("VVFP Story Upgrades.dll");
        vv_story_appearance_fn changed = story != NULL
            ? (vv_story_appearance_fn)GetProcAddress(story, "VvfpStoryAppearanceChanged") : NULL;
        if (changed != NULL) {
            (void)changed(game, record, new_head, new_body);
        }
    }
    if (!looked) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        looked = 1;
        if (module != NULL) {
            write_record = (vv_write_village_record_fn)GetProcAddress(module, "WriteVillageRecord");
        }
    }
    if (write_record == NULL) {
        return;
    }
    if (masks) {
        wsprintfA(before, "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d\n  Old mask: %s\n"
                  "  New mask: %s\n", old_head, old_body, new_head, new_body, VV_APPEARANCE_MASK_NAMES[old_mask],
                  VV_APPEARANCE_MASK_NAMES[new_mask]);
    } else {
        wsprintfA(before, "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d\n",
                  old_head, old_body, new_head, new_body);
    }
    (void)write_record(game, VV_KIND_APPEARANCE, record, 1, before, NULL, 0);
}

/* The head and body alone (the masks not known: no mask lines), as every caller logged before the
   masks were.  Nothing when old_head == new_head && old_body == new_body. */
static void vv_log_appearance(int game, const void *record, int old_head, int old_body, int new_head,
                              int new_body) {
    vv_log_appearance_mask(game, record, old_head, old_body, -1, new_head, new_body, -1);
}
#endif
