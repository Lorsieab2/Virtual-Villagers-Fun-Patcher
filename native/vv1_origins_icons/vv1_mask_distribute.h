/* Change Appearance for All -- mask distribution algorithms.
 *
 * Pure, dependency-free (no Windows, no CRT beyond memset via a loop, no live
 * game memory), so it can be unit-tested with a plain C harness. The DLL
 * #includes this header and calls these on a compact array of the currently
 * occupied villagers; the caller then writes each result into the .data mask
 * table by the villager's record index.
 *
 * Mask ids match vv1_mask_name(): 0=none, 1=blue, 2=orange, 3=red, 4=purple,
 * 5=chief (tribal). "out[i]" is the mask assigned to occupied villager i.
 */
#ifndef VV1_MASK_DISTRIBUTE_H
#define VV1_MASK_DISTRIBUTE_H

#define VVM_NONE   0
#define VVM_BLUE   1
#define VVM_ORANGE 2
#define VVM_RED    3
#define VVM_PURPLE 4
#define VVM_CHIEF  5

/* VV5-style caps (the tribal chief is exactly one; see vv1_dist_vv5). */
#define VVM_VV5_ORANGE_MAX 10
#define VVM_VV5_RED_MAX     7
#define VVM_VV5_PURPLE_MAX  4

/* Deterministic, seedable xorshift32 -- no CRT rand(), so the DLL stays
 * CRT-less and the tests are reproducible. Never returns the same stream for
 * two different non-zero seeds; seed is forced non-zero. */
static unsigned int vvm_rng_next(unsigned int *state) {
    unsigned int x = *state ? *state : 0x9E3779B9u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

/* Fisher-Yates shuffle of an index array [0,count) using the given rng. */
static void vvm_shuffle(int *order, int count, unsigned int *rng) {
    int i;
    for (i = count - 1; i > 0; i--) {
        int j = (int)(vvm_rng_next(rng) % (unsigned int)(i + 1));
        int t = order[i];
        order[i] = order[j];
        order[j] = t;
    }
}

/* Village-wide single mask (including 0=none): everyone gets the same. */
static void vv1_dist_single(int count, unsigned char mask, unsigned char *out) {
    int i;
    for (i = 0; i < count; i++) {
        out[i] = mask;
    }
}

/* Random (All 5): every villager gets one of the five colours, uniformly at
 * random. No villager is left unmasked. */
static void vv1_dist_random(int count, unsigned int *rng, unsigned char *out) {
    int i;
    for (i = 0; i < count; i++) {
        out[i] = (unsigned char)(VVM_BLUE + vvm_rng_next(rng) % 5u);
    }
}

/* Random (All 5 + No Mask): every villager gets one of the five colours OR no
 * mask, uniformly at random over 0..5 -- so some villagers end up unmasked. */
static void vv1_dist_random_with_none(int count, unsigned int *rng,
                                      unsigned char *out) {
    int i;
    for (i = 0; i < count; i++) {
        out[i] = (unsigned char)(vvm_rng_next(rng) % 6u);  /* 0..5 incl. none */
    }
}

/* VV5-style: exactly one chief, up to VVM_VV5_PURPLE_MAX purple, up to
 * VVM_VV5_RED_MAX red, up to VVM_VV5_ORANGE_MAX orange, and everyone else blue.
 * The chief goes to golden_idx when it is a valid occupied index (0..count-1);
 * otherwise to a random villager. All other colours are handed to distinct
 * random villagers. Small villages simply run out of villagers before the caps
 * are hit, which is fine.
 *
 * order[] must be a scratch buffer of at least `count` ints (caller-provided so
 * this stays allocation-free).
 */
static void vv1_dist_vv5(int count, int golden_idx, unsigned int *rng,
                         int *order, unsigned char *out) {
    int i, pos = 0;
    int chief_slot;
    for (i = 0; i < count; i++) {
        out[i] = VVM_BLUE;   /* default; overwritten below for the rarer masks */
        order[i] = i;
    }
    if (count <= 0) {
        return;
    }
    /* Chief first, so it can't be overwritten and is excluded from the rest. */
    if (golden_idx >= 0 && golden_idx < count) {
        chief_slot = golden_idx;
    } else {
        chief_slot = (int)(vvm_rng_next(rng) % (unsigned int)count);
    }
    out[chief_slot] = VVM_CHIEF;

    /* Shuffle the remaining villagers (all except the chief) and deal out the
     * capped colours in order: purple, red, orange; the rest stay blue. */
    /* Move the chief to the front of order[] and shuffle the tail. */
    for (i = 0; i < count; i++) {
        if (order[i] == chief_slot) {
            order[i] = order[0];
            order[0] = chief_slot;
            break;
        }
    }
    vvm_shuffle(order + 1, count - 1, rng);

    pos = 1;
    {
        int want[3];
        unsigned char colour[3];
        int c;
        want[0] = VVM_VV5_PURPLE_MAX; colour[0] = VVM_PURPLE;
        want[1] = VVM_VV5_RED_MAX;    colour[1] = VVM_RED;
        want[2] = VVM_VV5_ORANGE_MAX; colour[2] = VVM_ORANGE;
        for (c = 0; c < 3; c++) {
            int n;
            for (n = 0; n < want[c] && pos < count; n++, pos++) {
                out[order[pos]] = colour[c];
            }
        }
    }
    /* Anyone left in order[pos..] keeps the default blue. */
}

/* Equal: each of the five masks assigned to as close to count/5 villagers as
 * possible, and within each mask, split as evenly as possible between the two
 * sexes. is_male[i] != 0 marks a male villager. order[] is caller scratch of
 * at least `count` ints.
 *
 * Strategy: build two shuffled queues (males, females) and deal masks
 * round-robin, alternating which sex is served first each mask so the leftover
 * (count % 5) villagers -- and any sex imbalance -- spread out instead of
 * piling onto one mask or one sex.
 */
static void vv1_dist_equal(int count, const unsigned char *is_male,
                           unsigned int *rng, int *order, unsigned char *out) {
    int i, m = 0, f = 0;
    int *males, *females;
    int mi, fi, mask;
    int male_of[5], female_of[5];   /* per-mask sex tally, mask index 0..4 */
    if (count <= 0) {
        return;
    }
    for (i = 0; i < 5; i++) {
        male_of[i] = 0;
        female_of[i] = 0;
    }
    /* Partition indices into the front (males) and back (females) of order[]. */
    males = order;
    for (i = 0; i < count; i++) {
        if (is_male[i]) {
            males[m++] = i;
        }
    }
    females = order + m;
    for (i = 0; i < count; i++) {
        if (!is_male[i]) {
            females[f] = i;
            f++;
        }
    }
    vvm_shuffle(males, m, rng);
    vvm_shuffle(females, f, rng);

    /* Deal round-robin over the 5 masks; for each assignment prefer whichever
     * sex is currently UNDER-represented in THIS mask's bucket, so every mask
     * colour ends up split as evenly as its own count allows between the sexes
     * (not just the village overall). Ties fall back to the sex with more
     * villagers left, then to mask parity so leftovers alternate. Availability
     * guards keep either sex from being over-drawn. */
    mi = 0; fi = 0;
    for (i = 0; i < count; i++) {
        int take_male;
        int mk = i % 5;               /* mask bucket index 0..4 */
        mask = VVM_BLUE + mk;
        if (mi >= m) {
            take_male = 0;            /* no males left */
        } else if (fi >= f) {
            take_male = 1;            /* no females left */
        } else if (male_of[mk] != female_of[mk]) {
            take_male = male_of[mk] < female_of[mk];   /* even out THIS mask */
        } else {
            int rem_m = m - mi, rem_f = f - fi;
            if (rem_m != rem_f) {
                take_male = rem_m > rem_f;
            } else {
                take_male = (mask % 2) == 0;
            }
        }
        if (take_male) {
            out[males[mi++]] = (unsigned char)mask;
            male_of[mk]++;
        } else {
            out[females[fi++]] = (unsigned char)mask;
            female_of[mk]++;
        }
    }
}

#endif /* VV1_MASK_DISTRIBUTE_H */
