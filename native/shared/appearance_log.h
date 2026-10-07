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

   Nothing is written when the Births and Conceptions log is not part of the game (the DLL is not
   there), or when the look did not change.  It never changes the villager or the game. */
#ifndef VVFP_APPEARANCE_LOG_H
#define VVFP_APPEARANCE_LOG_H

#include <windows.h>

#include "patcher_files.h"

#define VV_KIND_APPEARANCE 7      /* parentage_export.c's KIND_APPEARANCE */

typedef int (__stdcall *vv_write_village_record_fn)(int, int, const void *, int, const char *, const char *,
                                                    int);

static void vv_log_appearance(int game, const void *record, int old_head, int old_body, int new_head,
                              int new_body) {
    static vv_write_village_record_fn write_record;
    static int looked;
    char before[160];
    if (record == NULL || (old_head == new_head && old_body == new_body)) {
        return;
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
    wsprintfA(before, "  Old head: %d\n  Old body: %d\n  New head: %d\n  New body: %d\n",
              old_head, old_body, new_head, new_body);
    (void)write_record(game, VV_KIND_APPEARANCE, record, 1, before, NULL, 0);
}

#endif
