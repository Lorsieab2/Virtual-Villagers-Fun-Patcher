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
    check(vv_roster_same_villager("3\tMoku\t-", "3\tLani\t-") == 0,
          "two villagers with nothing to fingerprint are not the same by fingerprint");
    check(vv_roster_same_villager("3\tMoku\t-", "3\tMoku\t-") == 1,
          "with nothing to fingerprint, the same name is a weak match");
    check(vv_roster_same_villager("3\tMoku\t5B517625", "3\tMoku\t-") == 1,
          "an older roster's empty fingerprint against no fingerprint is a weak match");
    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 1, "Bea", 0x22); add(was, &was_n, 2, "Cai", 0x33);
    _snprintf_s(was[was_n++], ROW, _TRUNCATE, "3\tDuk\t-");
    add(now, &now_n, 0, "Tui", 0x44); add(now, &now_n, 1, "Rua", 0x55); add(now, &now_n, 2, "Ika", 0x66);
    _snprintf_s(now[now_n++], ROW, _TRUNCATE, "3\tPeni\t-");
    check(!same(), "another village whose villager has nothing to fingerprint is still another village");

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

    /* The games save only their occupied records, packed, and load them into
       records 0, 1, 2, ...: after a reload every villager behind a death sits
       at its RANK in the roster the last save recorded, not its old record.
       (A death during play leaves its record empty until the game is quit;
       the quit's save records the roster with that hole, and the next load
       closes it.) */
    reset();
    {
        static const char *names[] = { "Ata", "Bea", "Cai", "Dov", "Eli", "Fen", "Gil", "Hal", "Ira", "Jon" };
        for (i = 1; i < 10; ++i) {
            add(was, &was_n, i, names[i], 0x3000 + i);                      /* record 0 died before the quit */
        }
        for (i = 1; i < 10; ++i) {
            add(now, &now_n, i - 1, names[i], 0x3000 + i);                  /* the reload moved all down one */
        }
    }
    check(same(), "a death at record 0 and a reload that moves everyone down is still the same village");

    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 4, "Bea", 0x22);    /* records 1-3 died */
    add(now, &now_n, 0, "Ata", 0x44); add(now, &now_n, 1, "Bea", 0x22);    /* Bea reloaded at her rank, 1 */
    check(same(), "a survivor found at her rank in the recorded roster is a shared villager");

    reset();
    for (i = 0; i < 20; ++i) {
        add(was, &was_n, 2 * i, i == 3 ? "Moku" : "Old", 0x2000 + i);
        add(now, &now_n, i, i == 3 ? "Moku" : "New", 0x9000 + i);
    }
    check(!same(), "a new village sharing one founder's name at a recorded rank is still a new village");
    check(vv_roster_same_villager("3\tMoku\t0000ABCD", "1\tMoku\t0000ABCD") == 0,
          "a villager at neither its recorded record nor its rank is not matched by the pair test");

    /* Codex (#516): a saved Kai at record 2 died during the catch-up; the
       other saved Kai (rank 2) survives at record 2 beside two newborns.  A
       name-only match of the dead Kai must not hide the survivor's
       fingerprint match. */
    reset();
    add(was, &was_n, 0, "Ata", 0x11); add(was, &was_n, 2, "Kai", 0x21); add(was, &was_n, 3, "Kai", 0x22);
    add(now, &now_n, 0, "New1", 0x91); add(now, &now_n, 1, "New2", 0x92); add(now, &now_n, 2, "Kai", 0x22);
    check(same(), "a fingerprint match is found even when a same-name row could be taken first");

    /* The owner's The Lost Children village (V7Test, 2026-10-08): an
       occupied record the roster never listed went, so every listed
       villager came back one record lower -- neither at its old record nor
       at its rank -- and Last Names had renamed them all and changed the
       children's fingerprints (their parents' names).  The statistics,
       stews and elders were moved aside as another village's. */
    reset();
    add(was, &was_n, 3, "Mem", 0xFD710198u); add(was, &was_n, 9, "Tapu", 0x8466C8DCu);
    add(was, &was_n, 10, "Sutai", 0xDA5D205Fu); add(was, &was_n, 14, "Tonga", 0x2E85BF95u);
    add(now, &now_n, 2, "Mem", 0xFD710198u); add(now, &now_n, 8, "Tapu Chinaka", 0x8466C8DCu);
    add(now, &now_n, 9, "Sutai Makawee", 0xDA5D205Fu); add(now, &now_n, 13, "Tonga Makawee", 0xC29381B0u);
    check(same(), "villagers moved down a record by a reload and renamed are still the same village");

    reset();
    for (i = 0; i < 20; ++i) {
        add(was, &was_n, i + 5, "Old", 0x2000 + i);
        add(now, &now_n, i, "New", i == 7 ? 0x2000 + 9 : 0x9000 + i);     /* one fingerprint coincides, lower */
    }
    check(!same(), "one fingerprint found at a lower record is not enough for a new village to keep the old files");

    reset();
    add(was, &was_n, 2, "Ata", 0x11); add(was, &was_n, 3, "Bea", 0x22); add(was, &was_n, 9, "Cai", 0x99);
    add(now, &now_n, 5, "Ata", 0x11); add(now, &now_n, 6, "Bea", 0x22); add(now, &now_n, 0, "Dov", 0x77);
    check(!same(), "a villager never moves UP a record: fingerprints at higher records do not count");

    reset();
    add(was, &was_n, 4, "Ata", 0x11);
    add(now, &now_n, 1, "Ata Lani", 0x11); add(now, &now_n, 2, "Kai", 0x33);
    check(same(), "the only recorded villager found moved down is the same village");

    reset();
    _snprintf_s(was[was_n++], ROW, _TRUNCATE, "4\tAta\t-"); _snprintf_s(was[was_n++], ROW, _TRUNCATE, "5\tBea\t-");
    _snprintf_s(now[now_n++], ROW, _TRUNCATE, "1\tTui\t-"); _snprintf_s(now[now_n++], ROW, _TRUNCATE, "2\tRua\t-");
    check(!same(), "villagers with nothing to fingerprint never match as moved down");

    printf("%d failure(s)\n", failures);
    return failures == 0 ? 0 : 1;
}
