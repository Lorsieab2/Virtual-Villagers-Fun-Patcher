/* Standalone unit test for vv1_mask_distribute.h. Compiled and run by
 * tests/test_vv1_mask_distribution.py. Prints "FAIL: ..." and returns non-zero
 * on any failure; returns 0 when every case passes. */
#include <stdio.h>
#include "vv1_mask_distribute.h"

static int failures = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); failures++; } } while (0)

static void counts(const unsigned char *out, int count, int tally[6]) {
    int i;
    for (i = 0; i < 6; i++) tally[i] = 0;
    for (i = 0; i < count; i++) {
        if (out[i] <= 5) tally[out[i]]++;
    }
}

int main(void) {
    unsigned char out[512];
    int order[512];
    unsigned char is_male[512];
    int tally[6];
    unsigned int rng;
    int count, i, seed;

    /* --- single --- */
    for (count = 0; count <= 300; count += 37) {
        vv1_dist_single(count, VVM_PURPLE, out);
        for (i = 0; i < count; i++) CHECK(out[i] == VVM_PURPLE, "single not uniform");
        vv1_dist_single(count, VVM_NONE, out);
        for (i = 0; i < count; i++) CHECK(out[i] == VVM_NONE, "single none not uniform");
    }

    /* --- random (All 5): everyone gets a real mask 1..5, never none --- */
    for (seed = 1; seed <= 5; seed++) {
        rng = (unsigned int)seed * 2654435761u;
        count = 227;
        vv1_dist_random(count, &rng, out);
        for (i = 0; i < count; i++) CHECK(out[i] >= VVM_BLUE && out[i] <= VVM_CHIEF, "random out of range");
    }

    /* --- random (All 5 + No Mask): 0..5, and some ARE none over enough draws --- */
    {
        int none_seen = 0;
        for (seed = 1; seed <= 5; seed++) {
            rng = (unsigned int)seed * 40503u + 7u;
            count = 300;
            vv1_dist_random_with_none(count, &rng, out);
            for (i = 0; i < count; i++) {
                CHECK(out[i] <= VVM_CHIEF, "random+none out of range");
                if (out[i] == VVM_NONE) none_seen = 1;
            }
        }
        CHECK(none_seen, "random+none never left anyone unmasked");
    }

    /* --- vv5: exactly one chief, caps respected, rest blue --- */
    for (seed = 1; seed <= 8; seed++) {
        int golden;
        for (golden = -1; golden < 4; golden += 2) {  /* -1 (none) and a valid idx */
            for (count = 1; count <= 300; count += 41) {
                rng = 0xABCDEF01u ^ ((unsigned int)seed << 8) ^ (unsigned int)count;
                int g = (golden >= 0 && golden < count) ? golden : -1;
                vv1_dist_vv5(count, g, &rng, order, out);
                counts(out, count, tally);
                CHECK(tally[VVM_CHIEF] == 1, "vv5 chief count != 1");
                if (g >= 0) CHECK(out[g] == VVM_CHIEF, "vv5 chief not on golden child");
                CHECK(tally[VVM_PURPLE] <= VVM_VV5_PURPLE_MAX, "vv5 purple over cap");
                CHECK(tally[VVM_RED] <= VVM_VV5_RED_MAX, "vv5 red over cap");
                CHECK(tally[VVM_ORANGE] <= VVM_VV5_ORANGE_MAX, "vv5 orange over cap");
                CHECK(tally[VVM_NONE] == 0, "vv5 left someone with no mask");
                CHECK(tally[VVM_BLUE] + tally[VVM_ORANGE] + tally[VVM_RED] +
                      tally[VVM_PURPLE] + tally[VVM_CHIEF] == count, "vv5 total mismatch");
                /* on a big village blue must dominate */
                if (count >= 100) CHECK(tally[VVM_BLUE] >= tally[VVM_ORANGE], "vv5 blue not most common");
            }
        }
    }

    /* --- equal: each mask ~count/5, sexes balanced within each mask --- */
    for (seed = 1; seed <= 6; seed++) {
        for (count = 5; count <= 300; count += 43) {
            rng = 0x13579BDFu ^ ((unsigned int)seed << 4) ^ (unsigned int)count;
            /* alternate-ish gender assignment */
            for (i = 0; i < count; i++) is_male[i] = (unsigned char)(((i * 7 + seed) % 3) != 0);
            vv1_dist_equal(count, is_male, &rng, order, out);
            counts(out, count, tally);
            int base = count / 5;
            for (i = VVM_BLUE; i <= VVM_CHIEF; i++) {
                CHECK(tally[i] >= base && tally[i] <= base + 1, "equal mask count not near count/5");
            }
            CHECK(tally[VVM_NONE] == 0, "equal left someone with no mask");
            CHECK(tally[VVM_BLUE]+tally[VVM_ORANGE]+tally[VVM_RED]+tally[VVM_PURPLE]+tally[VVM_CHIEF]==count, "equal total mismatch");
            /* Sex balance WITHIN each mask: each sex is spread as evenly as
               possible across the five mask buckets (the scarce sex isn't
               piled onto a few masks), so no mask's per-sex count is off from
               another mask's by more than 1. */
            {
                int mmale[6], mfem[6], k;
                int fmin = count + 1, fmax = -1, mmin = count + 1, mmax = -1;
                for (k = 0; k < 6; k++) { mmale[k] = 0; mfem[k] = 0; }
                for (i = 0; i < count; i++) {
                    if (is_male[i]) mmale[out[i]]++; else mfem[out[i]]++;
                }
                for (k = VVM_BLUE; k <= VVM_CHIEF; k++) {
                    if (mfem[k] < fmin) fmin = mfem[k];
                    if (mfem[k] > fmax) fmax = mfem[k];
                    if (mmale[k] < mmin) mmin = mmale[k];
                    if (mmale[k] > mmax) mmax = mmale[k];
                }
                CHECK(fmax - fmin <= 1, "equal: females not spread evenly across masks");
                CHECK(mmax - mmin <= 1, "equal: males not spread evenly across masks");
            }
        }
    }

    if (failures == 0) printf("ALL PASS\n");
    return failures == 0 ? 0 : 1;
}
