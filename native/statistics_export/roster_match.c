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
     - otherwise two fingerprint matches
       at LOWER records (moved down by
       a reload; moved_down_matches)    -> the same village
     - otherwise name-only matches      -> the same village only as a strict
                                           majority of the smaller roster
                                           (survivors whose likes changed)
     - otherwise                        -> a different village
   Each recorded row is matched at most once.  A row whose fingerprint is
   "-" -- a villager with no likes, dislikes or parents, which is nothing to
   fingerprint (statistics_export.c) -- matches by name only, whatever the
   other row's fingerprint.

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
    if (fa != NULL && fb != NULL && (strcmp(fa, "\t-") == 0 || strcmp(fb, "\t-") == 0)) {
        return fa - ta == fb - tb && strncmp(ta, tb, (size_t)(fa - ta)) == 0;   /* name only */
    }
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

/* The slot number at the front of a row, or -1. */
static int row_slot(const char *row) {
    int slot = 0;
    const char *p = row;
    if (*p < '0' || *p > '9') {
        return -1;
    }
    for (; *p >= '0' && *p <= '9'; ++p) {
        if (slot > 100000) {
            return -1;
        }
        slot = slot * 10 + (*p - '0');
    }
    return *p == '\t' ? slot : -1;
}

/* The fingerprint field of a row (after the second tab), or NULL. */
static const char *row_fingerprint(const char *row) {
    const char *t = strchr(row, '\t');
    if (t == NULL || (t = strchr(t + 1, '\t')) == NULL || strcmp(t + 1, "-") == 0 || t[1] == '\0') {
        return NULL;
    }
    return t + 1;
}

/* Recorded villagers found LOWER in the living records, by fingerprint.

   A reload packs every OCCUPIED record into records 0, 1, 2, ..., and the
   roster lists only the living, active ones -- so when an occupied record
   the roster never listed (an inactive one) goes, every listed villager
   behind it moves down, and neither its old record nor its rank in the
   roster is where it is now.  The owner's The Lost Children village
   (V7Test, 2026-10-08) lost its statistics, stews and elders this way:
   Mem moved from record 3 to 2, Tapu from 9 to 8, ... and every positional
   comparison missed them.

   A villager only ever moves DOWN (packing), so a recorded row matches a
   living row at the same or a lower record with the same fingerprint (a
   name can change: renames, last names).  Each row on either side is used
   once.  One such match could be chance; TWO distinct villagers found
   moved down with their fingerprints (or the only villager of a
   one-villager roster) are not. */
static int moved_down_matches(const char *was, int was_count, const char *now, int now_count, int row_size) {
    char was_used[VV_ROSTER_MAX];
    char now_used[VV_ROSTER_MAX];
    int i, j, matched = 0;
    memset(was_used, 0, sizeof(was_used));
    memset(now_used, 0, sizeof(now_used));
    if (now_count > VV_ROSTER_MAX) {
        now_count = VV_ROSTER_MAX;
    }
    for (i = 0; i < was_count; ++i) {
        const char *wrow = was + i * row_size;
        const char *wfp = row_fingerprint(wrow);
        int wslot = row_slot(wrow);
        if (wfp == NULL || wslot < 0) {
            continue;
        }
        for (j = 0; j < now_count; ++j) {
            const char *nrow = now + j * row_size;
            const char *nfp;
            int nslot;
            if (now_used[j]) {
                continue;
            }
            nfp = row_fingerprint(nrow);
            nslot = row_slot(nrow);
            if (nfp != NULL && nslot >= 0 && nslot <= wslot && strcmp(nfp, wfp) == 0) {
                was_used[i] = 1;
                now_used[j] = 1;
                ++matched;
                break;
            }
        }
    }
    return matched;
}

int vv_roster_same_village(const char *was, int was_count, const char *now, int now_count, int row_size) {
    char used[VV_ROSTER_MAX];
    int i, j, matched = 0, smaller, moved;
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
    /* Survivors moved down to lower records by a reload (see above). */
    moved = moved_down_matches(was, was_count, now, now_count, row_size);
    smaller = was_count < now_count ? was_count : now_count;
    if (moved >= 2 || (moved >= 1 && smaller == 1)) {
        return 1;
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
