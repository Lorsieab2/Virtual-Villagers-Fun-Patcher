/* Make a per-villager table follow its villagers when the game renumbers
   them.

   Every game saves only its occupied villager records, packed in record
   order, and loads them into records 0, 1, 2, ... (seen live in A New Home
   and The Lost Children; emulated for The Secret City, The Tree of Life and
   New Believers).  So after a death and a reload everyone behind the dead
   villager is in a lower record, and a table kept by record index -- the
   Origins mask tables -- attaches each entry to whoever now sits at its old
   index.

   vv_mask_follow re-keys such a table by the identity stored beside each
   entry.  It is pure (arrays in, arrays out: no game memory, no files), so
   tests/test_mask_follow.py drives it through native/shared/mask_follow_harness.c.

   Inputs, n records each:
     value[i]   the entry at record i (0 = none)
     stored[i]  the identity stored with that entry (0 = unknown)
     live[i]    the identity of the villager in record i now (0 = empty record)
   Rules, the same as the VV1 parentage sidecar's:
     - an entry whose identity is held by exactly one entry and exactly one
       living villager goes to that villager's record, wherever it is;
     - an entry whose identity is NOT unique is never guessed at: it stays at
       its own record only when nothing moved at all and the villager there
       still carries it, and is otherwise dropped;
     - an entry whose villager is in no record stays where it was while that
       record is empty (dead or away: the game's own death sweep decides),
       and is dropped as soon as anyone else holds that record;
     - with down_only, a move to a HIGHER record is refused (a packed load
       only ever moves villagers down) -- for files that hold only a weak
       identity, such as a name hash.
   Outputs new_value[n] and new_stored[n] (an entry keeps its stored
   identity).  n is at most VV_MASK_FOLLOW_MAX (every game has 150 or 256
   records).  Returns 1 when anything changed. */
#ifndef VV_MASK_FOLLOW_H
#define VV_MASK_FOLLOW_H

#define VV_MASK_FOLLOW_MAX 256

static int vv_mask_follow_count(const unsigned int *ids, const unsigned char *only_where,
                                int n, unsigned int id, int *where) {
    int i, c = 0;
    for (i = 0; i < n; ++i) {
        if (ids[i] == id && (only_where == 0 || only_where[i] != 0)) {
            ++c;
            if (where != 0) {
                *where = i;
            }
        }
    }
    return c;
}

static int vv_mask_follow(int n, const unsigned char *value, const unsigned int *stored,
                          const unsigned int *live, int down_only,
                          unsigned char *new_value, unsigned int *new_stored) {
    int target[VV_MASK_FOLLOW_MAX];
    int i;
    int repacked = 0;
    int changed = 0;
    for (i = 0; i < n; ++i) {
        int where = -1;
        target[i] = -1;
        if (value[i] == 0 || stored[i] == 0) {
            continue;
        }
        if (vv_mask_follow_count(stored, value, n, stored[i], 0) == 1
            && vv_mask_follow_count(live, 0, n, stored[i], &where) == 1
            && !(down_only && where > i)) {
            target[i] = where;
            if (where != i) {
                repacked = 1;
            }
        }
    }
    for (i = 0; i < n; ++i) {
        if (value[i] != 0 && stored[i] != 0 && target[i] < 0 && !repacked && live[i] == stored[i]) {
            target[i] = i;            /* an ambiguous identity, where nothing moved */
        }
    }
    for (i = 0; i < n; ++i) {
        new_value[i] = 0;
        new_stored[i] = 0;
    }
    for (i = 0; i < n; ++i) {
        if (value[i] != 0 && target[i] >= 0) {
            new_value[target[i]] = value[i];
            new_stored[target[i]] = stored[i];
        }
    }
    /* An entry nobody holds stays only while its record is empty -- and an
       empty record is never another entry's target, since every target is
       where a living villager is. */
    for (i = 0; i < n; ++i) {
        if (value[i] != 0 && target[i] < 0 && live[i] == 0) {
            new_value[i] = value[i];  /* away or dead, its record still empty: kept */
            new_stored[i] = stored[i];
        }
    }
    for (i = 0; i < n; ++i) {
        changed |= new_value[i] != value[i] || (new_value[i] != 0 && new_stored[i] != stored[i]);
    }
    return changed;
}

#endif
