/* EQUAL DIVISION OF LABOR: WHO GETS WHICH JOB (all five games).

   The owner (2026-10-11): "Equal Division of Labor should try and prioritize
   villagers' skill progress, otherwise fallback to random equal division",
   and, choosing the rule: "Prioritize skills in order of most progress."

   The number of villagers each job gets is NOT changed by this file.  Each
   game still works out, per sex, how many seats each job has exactly as it
   always has (its own fixed job order, cycled; see vved_cycle_quota), so the
   totals and the male/female split per job are the same as before.  This
   file only decides WHICH villager fills WHICH seat:

     1. Every (villager, job) pair where the villager has some progress in
        that job's skill (skill value above 0) is a claim.  All claims are
        ranked by skill value, highest first.  Equal values are put in a
        random order (they are shuffled before a stable sort).
     2. Claims are granted in that order: a villager who is not placed yet
        gets the job if that job still has a free seat for their sex.  So
        each villager is placed in the job they have made the most progress
        in; if that job is already full, their next-most-progressed job; and
        so on.  Mastered skills count like any other value: a master farmer
        has the most progress in Farming and is placed there first.
     3. Anyone left over -- no progress in any job that still has room (for
        example a newborn, whose skills are all 0), or whose skill values
        could not be read -- is placed at random in the free seats that
        remain for their sex (the "random equal division" fallback).

   The Parenting rule of each variant is untouched: "(No Parenting)" simply
   has no Parenting seats, so the Parenting skill is never a claim.

   Pure code: no Windows calls, no game memory.  The game companions read
   the records and write the chosen job back; native/shared/
   equal_division_harness.c drives this file directly. */
#ifndef VV_EQUAL_DIVISION_H
#define VV_EQUAL_DIVISION_H

#define VVED_MAX_VILLAGERS 256
#define VVED_MAX_SEATS 6

/* A small private generator (xorshift32), so the game's own random number
   sequence is never consumed or disturbed.  state must not be 0. */
static unsigned int vved_next(unsigned int *state) {
    unsigned int x = *state;
    if (x == 0u) {
        x = 0x9E3779B9u;
    }
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

static unsigned int vved_below(unsigned int *state, unsigned int bound) {
    return bound == 0u ? 0u : vved_next(state) % bound;
}

/* The seats per job for one sex: `count` villagers dealt round-robin over
   `seats` jobs starting at job `start` (VV2's female cycle starts where the
   male cycle stopped; every other cycle starts at 0).  This is the same
   count the old per-record round-robin produced. */
static void vved_cycle_quota(int count, int seats, int start, int *quota) {
    int k;
    for (k = 0; k < seats; ++k) {
        quota[k] = 0;
    }
    if (seats <= 0) {
        return;
    }
    for (k = 0; k < count; ++k) {
        ++quota[(start + k) % seats];
    }
}

/* A skill value is a claim only when it is a real, positive progress value.
   NaN, negatives and absurd values (a record that could not be read sensibly)
   are no claim: that villager falls through to the random fallback. */
static int vved_is_claim(float value) {
    return value == value && value > 0.0f && value < 100000.0f;
}

/* count villagers; group[v] is 0 or 1 (the sex the quota is kept for);
   skill[v * VVED_MAX_SEATS + s] is villager v's skill for seat s;
   quota[g * VVED_MAX_SEATS + s] is how many seats job s has for group g and
   is consumed.  seat_out[v] receives the chosen seat (0..seats-1), or -1 only
   when the quotas did not cover every villager (a caller error).  Returns how
   many villagers were placed by skill (the rest were placed at random). */
static int vved_assign(
    int count,
    int seats,
    const int *group,
    const float *skill,
    int *quota,
    int *seat_out,
    unsigned int *rng
) {
    static int claim_v[VVED_MAX_VILLAGERS * VVED_MAX_SEATS];
    static int claim_s[VVED_MAX_VILLAGERS * VVED_MAX_SEATS];
    static float claim_k[VVED_MAX_VILLAGERS * VVED_MAX_SEATS];
    static int order[VVED_MAX_VILLAGERS];
    static int free_seat[VVED_MAX_VILLAGERS];
    int claims = 0;
    int by_skill = 0;
    int v, s, i, j, g;
    if (count > VVED_MAX_VILLAGERS) {
        count = VVED_MAX_VILLAGERS;
    }
    if (seats > VVED_MAX_SEATS) {
        seats = VVED_MAX_SEATS;
    }
    for (v = 0; v < count; ++v) {
        seat_out[v] = -1;
        for (s = 0; s < seats; ++s) {
            float value = skill[v * VVED_MAX_SEATS + s];
            if (vved_is_claim(value)) {
                claim_v[claims] = v;
                claim_s[claims] = s;
                claim_k[claims] = value;
                ++claims;
            }
        }
    }
    /* Shuffle, then a stable insertion sort by skill (highest first): equal
       values keep their shuffled, random order. */
    for (i = claims - 1; i > 0; --i) {
        int r = (int)vved_below(rng, (unsigned int)(i + 1));
        int tv = claim_v[i], ts = claim_s[i];
        float tk = claim_k[i];
        claim_v[i] = claim_v[r]; claim_s[i] = claim_s[r]; claim_k[i] = claim_k[r];
        claim_v[r] = tv; claim_s[r] = ts; claim_k[r] = tk;
    }
    for (i = 1; i < claims; ++i) {
        int tv = claim_v[i], ts = claim_s[i];
        float tk = claim_k[i];
        j = i - 1;
        while (j >= 0 && claim_k[j] < tk) {
            claim_v[j + 1] = claim_v[j];
            claim_s[j + 1] = claim_s[j];
            claim_k[j + 1] = claim_k[j];
            --j;
        }
        claim_v[j + 1] = tv; claim_s[j + 1] = ts; claim_k[j + 1] = tk;
    }
    for (i = 0; i < claims; ++i) {
        v = claim_v[i];
        s = claim_s[i];
        g = group[v] ? 1 : 0;
        if (seat_out[v] >= 0 || quota[g * VVED_MAX_SEATS + s] <= 0) {
            continue;
        }
        seat_out[v] = s;
        --quota[g * VVED_MAX_SEATS + s];
        ++by_skill;
    }
    /* The random fallback, per sex: the leftover villagers in a random order
       take the leftover seats in a random order. */
    for (g = 0; g < 2; ++g) {
        int left = 0, seats_left = 0;
        for (v = 0; v < count; ++v) {
            if (seat_out[v] < 0 && (group[v] ? 1 : 0) == g) {
                order[left++] = v;
            }
        }
        for (s = 0; s < seats; ++s) {
            int n = quota[g * VVED_MAX_SEATS + s];
            while (n-- > 0 && seats_left < VVED_MAX_VILLAGERS) {
                free_seat[seats_left++] = s;
            }
        }
        for (i = seats_left - 1; i > 0; --i) {
            int r = (int)vved_below(rng, (unsigned int)(i + 1));
            int t = free_seat[i];
            free_seat[i] = free_seat[r];
            free_seat[r] = t;
        }
        for (i = 0; i < left && i < seats_left; ++i) {
            seat_out[order[i]] = free_seat[i];
            --quota[g * VVED_MAX_SEATS + free_seat[i]];
        }
    }
    return by_skill;
}

#endif
