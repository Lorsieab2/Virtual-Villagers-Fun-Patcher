/* Runtime harness for native/shared/equal_division.h: Equal Division of
   Labor keeps each job's seat count per sex and gives each seat to the
   villager with the most progress in that job, random for the rest.  Also
   drives native/shared/skill_repair.h: out-of-range int skills are reset
   (below 0 -> 0, above 100 -> 100) and valid ones never touched.

   Usage: equal_division_harness.exe   (exit 0 when every check passes) */
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "equal_division.h"
#include "skill_repair.h"

static int g_checks, g_failures;

static void check(int ok, const char *what) {
    ++g_checks;
    if (ok) {
        printf("  ok %s\n", what);
    } else {
        ++g_failures;
        printf("  FAIL %s\n", what);
    }
}

static int group[VVED_MAX_VILLAGERS];
static float skill[VVED_MAX_VILLAGERS * VVED_MAX_SEATS];
static int seat_of[VVED_MAX_VILLAGERS];

static void clear_village(void) {
    memset(group, 0, sizeof group);
    memset(skill, 0, sizeof skill);
    memset(seat_of, 0, sizeof seat_of);
}

/* Seat counts per sex after an assignment. */
static void count_seats(int n, int seats, int out[2][VVED_MAX_SEATS]) {
    int v;
    memset(out, 0, sizeof(int) * 2 * VVED_MAX_SEATS);
    for (v = 0; v < n; ++v) {
        if (seat_of[v] >= 0 && seat_of[v] < seats) {
            ++out[group[v] ? 1 : 0][seat_of[v]];
        }
    }
}

int main(void) {
    int quota[2 * VVED_MAX_SEATS], want[2 * VVED_MAX_SEATS];
    int got[2][VVED_MAX_SEATS];
    unsigned int rng;
    int v, s, ok, run;

    /* 1. Equal counts are kept, per sex, exactly as the round-robin made them. */
    clear_village();
    for (v = 0; v < 23; ++v) {
        group[v] = v % 3 == 0;
        for (s = 0; s < 5; ++s) {
            skill[v * VVED_MAX_SEATS + s] = (float)((v * 7 + s * 13) % 50);
        }
    }
    {
        int males = 0, females = 0;
        for (v = 0; v < 23; ++v) { if (group[v]) ++females; else ++males; }
        vved_cycle_quota(males, 5, 0, quota);
        vved_cycle_quota(females, 5, males % 5, quota + VVED_MAX_SEATS);
    }
    memcpy(want, quota, sizeof quota);
    rng = 12345u;
    vved_assign(23, 5, group, skill, quota, seat_of, &rng);
    count_seats(23, 5, got);
    ok = 1;
    for (s = 0; s < 5; ++s) {
        ok &= got[0][s] == want[s] && got[1][s] == want[VVED_MAX_SEATS + s];
    }
    for (v = 0; v < 23; ++v) {
        ok &= seat_of[v] >= 0;
    }
    check(ok, "every villager is placed and each job keeps its per-sex seat count");

    /* 2. The round-robin counts themselves: 7 over 5 jobs -> 2,2,1,1,1; VV2's
          female cycle continuing at the male total. */
    vved_cycle_quota(7, 5, 0, quota);
    check(quota[0] == 2 && quota[1] == 2 && quota[2] == 1 && quota[3] == 1 && quota[4] == 1,
          "7 villagers over 5 jobs deal 2,2,1,1,1");
    vved_cycle_quota(3, 4, 2, quota);
    check(quota[0] == 1 && quota[1] == 0 && quota[2] == 1 && quota[3] == 1,
          "a cycle starting at job 2 deals 3 over 4 jobs as 1,0,1,1");

    /* 3. Skilled villagers go to their most-progressed job. Four males, four
          jobs, one seat each; each is best at a different job. */
    clear_village();
    skill[0 * VVED_MAX_SEATS + 2] = 80.0f; skill[0 * VVED_MAX_SEATS + 0] = 10.0f;
    skill[1 * VVED_MAX_SEATS + 0] = 60.0f; skill[1 * VVED_MAX_SEATS + 3] = 5.0f;
    skill[2 * VVED_MAX_SEATS + 3] = 40.0f;
    skill[3 * VVED_MAX_SEATS + 1] = 20.0f; skill[3 * VVED_MAX_SEATS + 2] = 15.0f;
    vved_cycle_quota(4, 4, 0, quota);
    vved_cycle_quota(0, 4, 0, quota + VVED_MAX_SEATS);
    rng = 7u;
    check(vved_assign(4, 4, group, skill, quota, seat_of, &rng) == 4,
          "all four skilled villagers are placed by skill");
    check(seat_of[0] == 2 && seat_of[1] == 0 && seat_of[2] == 3 && seat_of[3] == 1,
          "each villager gets the job they have made the most progress in");

    /* 4. Conflicts: the strongest claim wins; the other gets their next job. */
    clear_village();
    skill[0 * VVED_MAX_SEATS + 0] = 90.0f; skill[0 * VVED_MAX_SEATS + 1] = 50.0f;
    skill[1 * VVED_MAX_SEATS + 0] = 70.0f; skill[1 * VVED_MAX_SEATS + 1] = 60.0f;
    vved_cycle_quota(2, 2, 0, quota);
    vved_cycle_quota(0, 2, 0, quota + VVED_MAX_SEATS);
    rng = 99u;
    vved_assign(2, 2, group, skill, quota, seat_of, &rng);
    check(seat_of[0] == 0 && seat_of[1] == 1,
          "the higher claim on a full job wins; the other takes their next-best job");

    /* 5. Mastered skills count like any other value (most progress first). */
    clear_village();
    skill[0 * VVED_MAX_SEATS + 1] = 100.0f; skill[0 * VVED_MAX_SEATS + 0] = 30.0f;
    vved_cycle_quota(1, 2, 0, quota);  /* one seat, job 0 */
    quota[1] = 1; quota[0] = 0;        /* the seat is job 1 */
    memset(quota + VVED_MAX_SEATS, 0, sizeof(int) * VVED_MAX_SEATS);
    rng = 5u;
    vved_assign(1, 2, group, skill, quota, seat_of, &rng);
    check(seat_of[0] == 1, "a mastered skill is the villager's most-progressed job");

    /* 6. Sexes never trade seats. */
    clear_village();
    group[0] = 0; group[1] = 1;
    skill[0 * VVED_MAX_SEATS + 1] = 50.0f;  /* the male wants job 1 ... */
    quota[0] = 1; quota[1] = 0;             /* ... but the male seat is job 0 */
    quota[VVED_MAX_SEATS + 0] = 0; quota[VVED_MAX_SEATS + 1] = 1;
    rng = 3u;
    vved_assign(2, 2, group, skill, quota, seat_of, &rng);
    check(seat_of[0] == 0 && seat_of[1] == 1, "a female seat is never given to a male");

    /* 7. Fallback is random: villagers with no progress (all 0, unreadable
          NaN or negative values) are spread over the free seats differently
          on different runs, and always within the counts. */
    {
        int differs = 0, first[8], r;
        float nan_value;
        memset(&nan_value, 0xFF, sizeof nan_value);
        for (run = 0; run < 40; ++run) {
            clear_village();
            skill[2 * VVED_MAX_SEATS + 0] = nan_value;
            skill[3 * VVED_MAX_SEATS + 1] = -4.0f;
            vved_cycle_quota(8, 4, 0, quota);
            vved_cycle_quota(0, 4, 0, quota + VVED_MAX_SEATS);
            rng = 1000u + (unsigned int)run * 7919u;
            r = vved_assign(8, 4, group, skill, quota, seat_of, &rng);
            count_seats(8, 4, got);
            if (r != 0 || got[0][0] != 2 || got[0][1] != 2 || got[0][2] != 2 || got[0][3] != 2) {
                differs = -1000;
                break;
            }
            if (run == 0) {
                memcpy(first, seat_of, sizeof first);
            } else if (memcmp(first, seat_of, sizeof first) != 0) {
                ++differs;
            }
        }
        check(differs > 0, "no-progress and unreadable villagers are placed at random, counts kept");
    }

    /* 8. Ties are random: two villagers with the same skill for one seat. */
    {
        int zero_won = 0, one_won = 0;
        for (run = 0; run < 60; ++run) {
            clear_village();
            skill[0 * VVED_MAX_SEATS + 0] = 25.0f;
            skill[1 * VVED_MAX_SEATS + 0] = 25.0f;
            quota[0] = 1; quota[1] = 1;
            memset(quota + VVED_MAX_SEATS, 0, sizeof(int) * VVED_MAX_SEATS);
            rng = 77u + (unsigned int)run * 104729u;
            vved_assign(2, 2, group, skill, quota, seat_of, &rng);
            if (seat_of[0] == 0) ++zero_won;
            if (seat_of[1] == 0) ++one_won;
        }
        check(zero_won > 0 && one_won > 0 && zero_won + one_won == 60,
              "a tie for one seat goes either way at random");
    }

    /* 9. No Parenting: with only four seats, a Parenting skill (seat 4) is
          never a claim and nobody is given seat 4. */
    clear_village();
    for (v = 0; v < 6; ++v) {
        skill[v * VVED_MAX_SEATS + 4] = 99.0f;   /* everyone a master parent */
        skill[v * VVED_MAX_SEATS + (v % 4)] = 10.0f;
    }
    vved_cycle_quota(6, 4, 0, quota);
    vved_cycle_quota(0, 4, 0, quota + VVED_MAX_SEATS);
    rng = 11u;
    vved_assign(6, 4, group, skill, quota, seat_of, &rng);
    ok = 1;
    for (v = 0; v < 6; ++v) {
        ok &= seat_of[v] >= 0 && seat_of[v] < 4;
    }
    check(ok, "the No Parenting variant never seats anyone in Parenting");

    /* 10. Corrupted int skills: below 0 -> 0, above 100 -> 100; 0..100 kept. */
    {
        int rec_skills[8] = { -5, 150, 0, 100, 57, (int)0x80000000, 0x7FFFFFFF, 42 };
        int reset = vv_repair_int_skills((unsigned char *)rec_skills, 0, 7);
        check(reset == 4, "four out-of-range skills are reset");
        check(rec_skills[0] == 0 && rec_skills[1] == 100 && rec_skills[5] == 0
              && rec_skills[6] == 100, "below 0 becomes 0 and above 100 becomes 100");
        check(rec_skills[2] == 0 && rec_skills[3] == 100 && rec_skills[4] == 57
              && rec_skills[7] == 42, "valid skills (0, 100, in between) are untouched");
    }
    {
        char message[128] = "Done.";
        vv_append_skill_repairs(message, 0);
        check(strcmp(message, "Done.") == 0, "nothing reset adds no line");
        vv_append_skill_repairs(message, 1);
        check(strcmp(message, "Done.\r\n\r\nReset 1 corrupted skill value.") == 0,
              "one reset reads 'value'");
        strcpy(message, "Done.");
        vv_append_skill_repairs(message, 3);
        check(strcmp(message, "Done.\r\n\r\nReset 3 corrupted skill values.") == 0,
              "several read 'values'");
    }

    printf("== %d check(s), %d failure(s) ==\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
