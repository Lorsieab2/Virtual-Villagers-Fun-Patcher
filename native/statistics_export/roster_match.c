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
   Each recorded row is matched at most once.

   "The same slot" means either of the two records a recorded villager can
   be in at the next save: the record it held when the roster was written,
   or its RANK in that roster.  The games save only their occupied records,
   packed in record order, and load them into records 0, 1, 2, ... -- so
   after a reload every villager behind a death is at its rank, not its old
   record (A New Home, seen live: one death at record 2 moved 22 villagers
   down one record).  Compared by old record only, a death at a low record
   left no strong match, the village was taken for a new one, and its
   statistics, stews and Village Elders were moved aside.  The rank is as
   positional as the record -- a coincidence still has to land on one of
   two exact records -- so the Start Over protection is unchanged. */

#include <stdio.h>
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

/* The recorded row with its record replaced by its rank -- where the packed
   save puts that villager on the next load.  Empty when the row has no slot
   field or does not fit. */
static void ranked_row(const char *row, int rank, char *out, size_t size) {
    const char *tab = strchr(row, '\t');
    out[0] = '\0';
    if (tab != NULL && _snprintf_s(out, size, _TRUNCATE, "%d%s", rank, tab) < 0) {
        out[0] = '\0';
    }
}

/* How row i of the recorded roster matches a living row: at its record or
   at its rank (rows are written in record order, so row i is rank i),
   whichever is the stronger. */
static int match_at(const char *was, int i, const char *now_row, int row_size) {
    char ranked[128];
    int same = vv_roster_same_villager(was + i * row_size, now_row);
    if (same < 2) {
        ranked_row(was + i * row_size, i, ranked, sizeof(ranked));
        if (ranked[0] != '\0') {
            int at_rank = vv_roster_same_villager(ranked, now_row);
            if (at_rank > same) {
                same = at_rank;
            }
        }
    }
    return same;
}

int vv_roster_same_village(const char *was, int was_count, const char *now, int now_count, int row_size) {
    char used[VV_ROSTER_MAX];
    int i, j, matched = 0, smaller;
    if (was_count > VV_ROSTER_MAX) {
        was_count = VV_ROSTER_MAX;
    }
    if (was_count <= 0 || now_count <= 0) {
        return 1;                                  /* nothing to compare */
    }
    /* Any fingerprint match decides it -- looked for across the whole roster
       FIRST (Codex, #516): a name-only match consumed earlier could hide a
       later recorded row whose fingerprint is the living villager's. */
    for (j = 0; j < now_count; ++j) {
        for (i = 0; i < was_count; ++i) {
            if (match_at(was, i, now + j * row_size, row_size) == 2) {
                return 1;                          /* a shared villager */
            }
        }
    }
    /* Otherwise name-only matches, each recorded row used once, decide only
       as a strict majority of the smaller roster. */
    memset(used, 0, sizeof(used));
    for (j = 0; j < now_count; ++j) {
        for (i = 0; i < was_count; ++i) {
            if (!used[i] && match_at(was, i, now + j * row_size, row_size) != 0) {
                used[i] = 1;
                ++matched;
                break;
            }
        }
    }
    smaller = was_count < now_count ? was_count : now_count;
    return matched * 2 > smaller;
}
