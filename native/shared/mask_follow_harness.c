/* Behaviour tests for mask_follow.h (run by tests/test_mask_follow.py).
   Pure: no game, no files.  Prints "PASS <case>" / "FAIL <case>" and
   "<n> failure(s)". */
#include <stdio.h>
#include <string.h>

#include "mask_follow.h"

#define N 16

static int failures;
static unsigned char value[N], new_value[N];
static unsigned int stored[N], live[N], new_stored[N];
static unsigned int roster[N], was_stable[N], now_stable[N];

static void check(int ok, const char *what) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    failures += !ok;
}

static void reset(void) {
    memset(value, 0, sizeof value);
    memset(stored, 0, sizeof stored);
    memset(live, 0, sizeof live);
    memset(roster, 0, sizeof roster);
    memset(was_stable, 0, sizeof was_stable);
    memset(now_stable, 0, sizeof now_stable);
}

/* A village laid out in records 0.. with identities 100+k; `dead` (or -1)
   is left out, the way a packed load leaves out a villager who died. */
static void village(unsigned int *ids, int count, int dead) {
    int k, at = 0;
    for (k = 0; k < count; ++k) {
        if (k != dead) {
            ids[at++] = 100u + (unsigned int)k;
        }
    }
}

static int follow(int down_only) {
    /* in these cases the stored identities ARE the whole roster */
    return vv_mask_follow(N, value, stored, stored, live, down_only, new_value, new_stored);
}

int main(void) {
    int changed;

    /* 1. The owner's shape: a death at record 1, then a reload. */
    reset();
    village(stored, 8, -1);
    value[3] = 2; value[5] = 4;                 /* masks on villagers 103 and 105 */
    village(live, 8, 1);                        /* 101 died: everyone after moves down */
    changed = follow(0);
    check(changed && new_value[2] == 2 && new_stored[2] == 103 && new_value[4] == 4 && new_stored[4] == 105,
          "a death below two masked villagers and a reload: both masks move down with them");
    check(new_value[3] == 0 && new_value[5] == 0, "... and nothing is left on their old records");

    /* 2. Nothing moved: nothing changes. */
    reset();
    village(stored, 8, -1);
    value[3] = 2;
    village(live, 8, -1);
    check(follow(0) == 0 && new_value[3] == 2 && new_stored[3] == 103, "nothing moved: the table is unchanged");

    /* 3. The masked villager herself died before the reload. */
    reset();
    village(stored, 8, -1);
    value[1] = 3;
    village(live, 8, 1);
    changed = follow(0);
    check(changed && new_value[1] == 0, "a masked villager who died: her mask is not given to whoever now holds her record");

    /* 4. Away (her record still empty, no one holds her identity): kept. */
    reset();
    village(stored, 8, -1);
    value[6] = 1;
    village(live, 8, -1);
    live[6] = 0;
    follow(0);
    check(new_value[6] == 1 && new_stored[6] == 106, "a masked villager away from an empty record keeps it there");

    /* 5. ...but not once someone else's mask has moved into that record. */
    reset();
    stored[2] = 200; value[2] = 1;              /* away */
    stored[4] = 300; value[4] = 2;
    live[2] = 300;                              /* 300 moved down into record 2 */
    follow(0);
    check(new_value[2] == 2 && new_stored[2] == 300, "a record taken by a moved villager carries that villager's mask");

    /* 5b. A record someone else simply lives in: the away entry is dropped. */
    reset();
    stored[2] = 200; value[2] = 1;
    live[2] = 999;
    follow(0);
    check(new_value[2] == 0, "a record now held by an unmasked stranger drops the old entry");

    /* 6. Two masked villagers of one identity, after a repack: never guessed. */
    reset();
    village(stored, 8, -1);
    stored[6] = 103; value[3] = 1; value[6] = 2;
    village(live, 8, 0);                        /* everyone moves down one */
    live[5] = 103;
    follow(0);
    check(new_value[2] == 0 && new_value[5] == 0 && new_value[3] == 0 && new_value[6] == 0,
          "two villagers sharing an identity are left unmasked after a repack");

    /* 6b. ...even when both happen to sit at their old records while someone
           else moved: a repack happened, so their records prove nothing. */
    reset();
    stored[1] = 101; value[1] = 3;
    stored[3] = 103; value[3] = 1;
    stored[6] = 103; value[6] = 2;
    live[0] = 101; live[3] = 103; live[6] = 103;
    follow(0);
    check(new_value[0] == 3 && new_value[3] == 0 && new_value[6] == 0,
          "a shared identity is not kept in place once anyone else has moved");

    /* 6c. Two masked entries of one identity and only one such villager
           alive: either entry could be hers, so neither is given. */
    reset();
    stored[2] = 400; value[2] = 1;
    stored[5] = 400; value[5] = 2;
    live[0] = 400;
    follow(0);
    check(new_value[0] == 0, "two masked entries of one identity and one such villager left: neither is guessed");
    vv_mask_follow(N, value, stored, NULL, live, 0, new_value, new_stored);
    check(new_value[0] == 0, "... nor with no roster known");

    /* 7. The same two when nothing moved: kept in place. */
    reset();
    village(stored, 8, -1);
    stored[6] = 103; value[3] = 1; value[6] = 2;
    village(live, 8, -1);
    live[6] = 103;
    follow(0);
    check(new_value[3] == 1 && new_value[6] == 2, "... but kept at their own records when nothing moved");

    /* 8. One masked, one unmasked villager of the same identity alive. */
    reset();
    village(stored, 8, -1);
    value[3] = 1;
    village(live, 8, 0);
    live[6] = 103;                              /* an unmasked double appears */
    follow(0);
    check(new_value[2] == 0 && new_value[6] == 0, "a masked identity held by two living villagers is not guessed");

    /* 9. down_only (weak, name-only identities): an upward move is refused. */
    reset();
    stored[2] = 500; value[2] = 1;
    live[7] = 500;
    follow(1);
    check(new_value[7] == 0, "with only a weak identity, a move UP a record is refused");
    follow(0);
    check(new_value[7] == 1, "... while a strong identity may move either way");

    /* 10. The value and its identity travel together. */
    reset();
    stored[9] = 777; value[9] = 4;
    live[0] = 777;
    follow(0);
    check(new_value[0] == 4 && new_stored[0] == 777, "an entry keeps its own identity when it moves");

    /* 11. An entry with no stored identity at an occupied record is dropped. */
    reset();
    value[4] = 2;
    live[4] = 104;
    follow(0);
    check(new_value[4] == 0, "an entry with no identity on someone's record is dropped");

    /* 12. Codex (#516): twins of one identity at records 5 and 6, only the
           one at 5 masked; a death below moves both down to 4 and 5.  No
           UNIQUE masked entry moved, but the roster did: record 5 now holds
           the OTHER twin, so the mask is not kept there. */
    reset();
    village(stored, 8, -1);
    stored[5] = 900; stored[6] = 900;
    value[5] = 2;
    village(live, 8, 0);
    live[4] = 900; live[5] = 900;
    changed = follow(0);
    check(changed && new_value[4] == 0 && new_value[5] == 0,
          "a repack of nothing but duplicates is still a repack: the twin's mask is not kept in place");

    /* 13. A birth into an empty record is not a repack: twins kept. */
    reset();
    village(stored, 8, -1);
    stored[5] = 900; stored[6] = 900; value[5] = 2;
    village(live, 8, -1);
    live[5] = 900; live[6] = 900; live[9] = 555;
    follow(0);
    check(new_value[5] == 2, "a birth into an empty record does not unseat an ambiguous identity");

    /* 14. No roster known (NULL): counted as moved -- an ambiguous identity is
           never kept, a unique one still follows. */
    reset();
    stored[5] = 900; stored[6] = 900; value[5] = 2;
    stored[3] = 300; value[3] = 1;
    live[5] = 900; live[6] = 900; live[3] = 300;
    vv_mask_follow(N, value, stored, NULL, live, 0, new_value, new_stored);
    check(new_value[5] == 0 && new_value[3] == 1, "with no roster, an ambiguous identity is dropped and a unique one kept");

    /* 15. A villager who left a record and is now in another (an empty one)
           is a move too, even when no record changed holder. */
    reset();
    stored[3] = 900; stored[4] = 900; stored[7] = 777; value[3] = 2;
    live[3] = 900; live[4] = 900; live[1] = 777;
    follow(0);
    check(new_value[3] == 0, "a villager found in another record counts as a move: the twin's mask is not kept");

    /* 16. Codex (#516): twins of one identity at 3 (masked) and 4 (not).
           The masked twin died; on the reload the unmasked one moves down to
           3.  Only ONE masked entry has the identity, but the whole roster
           has two: whose mask it is cannot be told, so it is not given. */
    reset();
    village(roster, 8, -1);
    roster[3] = 900; roster[4] = 900;
    memcpy(stored, roster, sizeof stored);
    value[3] = 2;
    village(live, 8, 3);
    live[3] = 900;                              /* the unmasked twin, moved down */
    vv_mask_follow(N, value, stored, roster, live, 0, new_value, new_stored);
    check(new_value[3] == 0 && new_value[2] == 0 && new_value[4] == 0,
          "a masked twin who died does not hand her mask to the unmasked twin");

    /* 17. The rename rule.  A village of one: Kai renamed. */
    reset();
    roster[0] = 111; was_stable[0] = 7;
    live[0] = 222;   now_stable[0] = 7;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == 0,
          "a rename: one record, same stable fields, old identity gone, new one new");

    /* 18. Several villagers, one renamed. */
    reset();
    village(roster, 8, -1); village(live, 8, -1);
    for (changed = 0; changed < 8; ++changed) {
        was_stable[changed] = now_stable[changed] = 50u + (unsigned int)changed;
    }
    live[5] = 999;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == 5, "one of eight villagers renamed is found");

    /* 19. Not a rename: the stable fields changed (a death and a birth into
           the same record between two looks). */
    now_stable[5] = 51;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1,
          "a new occupant with other stable fields is not a rename");

    /* 20. Not a rename: two records changed. */
    now_stable[5] = 55;
    live[6] = 998;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1, "two records changed at once is not a rename");

    /* 21. One of two identical twins renamed: still a rename (the other
           twin keeps the old identity). */
    reset();
    roster[4] = 104; roster[7] = 104; was_stable[4] = was_stable[7] = 9;
    live[4] = 333;   live[7] = 104;   now_stable[4] = now_stable[7] = 9;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == 4,
          "one of two identical twins renamed is a rename");

    /* 22. A repack of same-stable siblings changes two records: not a rename. */
    reset();
    roster[4] = 104; roster[5] = 105; was_stable[4] = was_stable[5] = 9;
    live[4] = 105;                    now_stable[4] = 9;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1,
          "a sibling moving down into a dead sibling's record is not a rename");

    /* 23. Not a rename: a death (the record empty now), a birth into an
           empty record, or nothing changed. */
    reset();
    roster[2] = 102; was_stable[2] = 4;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1, "a death is not a rename");
    reset();
    live[2] = 102; now_stable[2] = 4;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1, "a birth is not a rename");
    roster[2] = 102; was_stable[2] = 4;
    live[2] = 102; now_stable[2] = 4;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1, "no change is not a rename");

    /* 24. Unknown stable fields (0) never make a rename. */
    reset();
    roster[0] = 111; live[0] = 222;
    check(vv_roster_renamed(N, roster, was_stable, live, now_stable) == -1, "unknown stable fields are never a rename");

    printf("%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
