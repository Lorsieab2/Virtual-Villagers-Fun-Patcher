/* Village identity from two living rosters (see roster_match.h).

   The owner's rule: a village is identified by roster OVERLAP -- any shared
   living villager -- never by name or an exact roster hash, because births
   and deaths change the roster between saves and Start Over keeps the tribe
   name.

   "Shared" needs care. A same-slot NAME alone is weak evidence: names come
   from fixed pools, so a new village's founders coincide with the old
   roster's names routinely (Codex, PR #467). A same-slot FINGERPRINT (likes,
   dislikes and parents' names) is not coincidental, and it survives the
   player renaming a villager. So:
     - any fingerprint match            -> the same village
     - otherwise name-only matches      -> the same village only as a strict
                                           majority of the smaller roster
                                           (survivors whose likes changed)
     - otherwise                        -> a different village
   Each recorded row is matched at most once. */

#include <string.h>

#include "roster_match.h"

int vv_roster_same_villager(const char *a, const char *b) {
    const char *ta = strchr(a, '\t');
    const char *tb = strchr(b, '\t');
    const char *fa, *fb;
    if (ta == NULL || tb == NULL || ta - a != tb - b || strncmp(a, b, (size_t)(ta - a)) != 0) {
        return 0;                                  /* different slot */
    }
    fa = strchr(ta + 1, '\t');
    fb = strchr(tb + 1, '\t');
    if (fa != NULL && fb != NULL && strcmp(fa, fb) == 0) {
        return 2;                                  /* same fingerprint */
    }
    if (fa == NULL || fb == NULL) {
        return fa == NULL && fb == NULL ? strcmp(ta, tb) == 0 : 0;
    }
    return fa - ta == fb - tb && strncmp(ta, tb, (size_t)(fa - ta)) == 0;   /* same name only */
}

int vv_roster_same_village(const char *was, int was_count, const char *now, int now_count, int row_size) {
    char used[VV_ROSTER_MAX];
    int i, j, same, strong = 0, matched = 0, smaller;
    if (was_count > VV_ROSTER_MAX) {
        was_count = VV_ROSTER_MAX;
    }
    if (was_count <= 0 || now_count <= 0) {
        return 1;                                  /* nothing to compare */
    }
    memset(used, 0, sizeof(used));
    for (j = 0; j < now_count; ++j) {
        for (i = 0; i < was_count; ++i) {
            if (!used[i] && (same = vv_roster_same_villager(was + i * row_size, now + j * row_size)) != 0) {
                used[i] = 1;
                ++matched;
                strong += same == 2;
                break;
            }
        }
    }
    if (strong > 0) {
        return 1;                                  /* a shared villager */
    }
    smaller = was_count < now_count ? was_count : now_count;
    return matched * 2 > smaller;
}
