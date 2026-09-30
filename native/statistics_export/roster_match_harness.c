/* Behaviour tests for roster_match.c (run by tests/test_roster_match.py).
   Prints "PASS <case>" / "FAIL <case>" and "<n> failure(s)". */

#include <stdio.h>
#include <string.h>

#include "roster_match.h"

#define ROW 56

static int failures;
static char was[VV_ROSTER_MAX][ROW];
static char now[VV_ROSTER_MAX][ROW];
static int was_n, now_n;

static void check(int ok, const char *what) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    failures += !ok;
}

static void reset(void) {
    memset(was, 0, sizeof(was));
    memset(now, 0, sizeof(now));
    was_n = now_n = 0;
}

static void add(char rows[][ROW], int *n, int slot, const char *name, unsigned int fingerprint) {
    _snprintf_s(rows[*n], ROW, _TRUNCATE, "%d\t%s\t%08X", slot, name, fingerprint);
    ++*n;
}

static int same(void) {
    return vv_roster_same_village(&was[0][0], was_n, &now[0][0], now_n, ROW);
}

int main(void) {
    int i;

    check(vv_roster_same_villager("3\tMoku\t0000ABCD", "3\tMoku\t0000ABCD") == 2, "same slot, name and fingerprint is a strong match");
    check(vv_roster_same_villager("3\tMoku\t0000ABCD", "3\tLani\t0000ABCD") == 2, "a renamed villager still matches by fingerprint");
    check(vv_roster_same_villager("3\tMoku\t0000ABCD", "3\tMoku\t00001234") == 1, "same slot and name only is a weak match");
    check(vv_roster_same_villager("3\tMoku\t0000ABCD", "4\tMoku\t0000ABCD") == 0, "a different slot is never the same villager");
    check(vv_roster_same_villager("13\tMoku\t0000ABCD", "1\tMoku\t0000ABCD") == 0, "slot 13 is not slot 1");

    /* The owner's rule: any shared villager is the same village. */
    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Bea", 0x22);
    add(now, &now_n, 0, "Ata", 0x11); add(now, &now_n, 2, "Kai", 0x33);   /* Bea died, Kai born */
    check(same(), "two villagers, one died and one born: still the same village");

    reset();
    for (i = 0; i < 40; ++i) {
        add(was, &was_n, i, "Old", 0x1000 + i);
    }
    add(now, &now_n, 7, "Old", 0x1007);                                     /* 39 of 40 gone */
    check(same(), "one surviving villager keeps a large village the same");

    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Bea", 0x22);
    add(now, &now_n, 0, "Tui", 0x11); add(now, &now_n, 1, "Rua", 0x22);    /* everyone renamed */
    check(same(), "renaming every villager is not a new village");

    /* Codex (PR #467): one coincidental same-slot name must not preserve
       the old village's statistics. */
    reset();
    for (i = 0; i < 20; ++i) {
        add(was, &was_n, i, i == 0 ? "Moku" : "Old", 0x2000 + i);
        add(now, &now_n, i, i == 0 ? "Moku" : "New", 0x9000 + i);
    }
    check(!same(), "a new village sharing one founder's name and slot is a new village");

    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Bea", 0x22); add(was, &was_n, 2, "Cai", 0x33);
    add(now, &now_n, 0, "Ata", 0x44); add(now, &now_n, 1, "Bea", 0x55); add(now, &now_n, 2, "Dov", 0x66);
    check(same(), "survivors whose likes changed still match as a name majority");

    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Bea", 0x22);
    add(now, &now_n, 0, "Ata", 0x44); add(now, &now_n, 1, "Rua", 0x55);
    check(!same(), "one name-only match in two is not a majority");

    reset();
    add(was, &was_n, 0, "Ata", 0x11);
    add(now, &now_n, 1, "Kai", 0x22);
    check(!same(), "no shared villager is a new village");

    reset();
    add(now, &now_n, 0, "Ata", 0x11);
    check(same(), "nothing recorded yet: nothing to compare");

    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Ata", 0x11);
    add(now, &now_n, 0, "Ata", 0x11);
    check(same(), "each recorded row is used at most once and a match still counts");

    printf("%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
