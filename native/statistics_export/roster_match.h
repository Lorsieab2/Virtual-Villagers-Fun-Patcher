#ifndef VVFP_ROSTER_MATCH_H
#define VVFP_ROSTER_MATCH_H

/* Is the living roster recorded at the last save the same village as the
   living roster now? Pure: no game memory, no files, so it is tested by
   native/statistics_export/roster_match_harness.c.

   Rows are "slot<TAB>name<TAB>fingerprint" (fingerprint = FNV-1a of likes,
   dislikes and parents' names), row_size bytes apart. */

#define VV_ROSTER_MAX 256

/* 2 = same slot and same fingerprint, 1 = same slot and same name only,
   0 = not the same villager. */
int vv_roster_same_villager(const char *a, const char *b);

/* 1 = the same village, 0 = a different village. */
int vv_roster_same_village(const char *was, int was_count, const char *now, int now_count, int row_size);

#endif
