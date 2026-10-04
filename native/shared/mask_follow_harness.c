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

static void check(int ok, const char *what) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    failures += !ok;
}

static void reset(void) {
    memset(value, 0, sizeof value);
    memset(stored, 0, sizeof stored);
    memset(live, 0, sizeof live);
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
    return vv_mask_follow(N, value, stored, live, down_only, new_value, new_stored);
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

    printf("%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
