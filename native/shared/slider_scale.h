/* slider_scale.h -- the shared arithmetic and call-site rewiring of the 0.1x-10x sliders (the owner, 2026-11-17):
   Collectible and Mushroom Frequency, Food Gained per Food Source, Tech Point Gain Rate, Skill Practice Success
   Chance and Age and Nursing Timer Speed.  Each is its own companion (native/vvfp_<name>), a third-word companion
   started by "VVFP More Companions.dll"; each includes this header once.

   THE NUMBER.  The slider's N, written by the patcher beside the companion (native/shared/multiplier_choice.h), read
   once at start as TENTHS within 1..100 (0.1 to 10); a missing or unreadable file is 10, 1x.  At 1x a companion
   installs nothing at all: the game is exactly the normal game.

   THE CHANCES.  Every chance a companion adds is drawn from its own xorshift32 numbers, seeded at start: the game's
   rand is never drawn more or less often than in the normal game, so every other roll of the game is unchanged.

     ss_scale(x)        x times N ON AVERAGE: x x tenths / 10, and one more with the chance of the rest in ten
                        (3 food at 0.5x: 1 food half the time, else 2; 1 tech point at 0.1x: 1 point one time in
                        ten).  Capped at 0x7FFFFFFF.
     ss_roll_low(r)     a roll r of the game's rand(M) for a test that passes when the roll is LOW (r < T or r <= T):
                        (10 r + u) / tenths, u one of 0..9 at random.  10 r + u is spread evenly over 0..10M - 1, so
                        the roll is below T exactly T x tenths times in 10M, N times the normal chance (all of the
                        time once that reaches it).  At 1x it is r itself.
     ss_roll_high(r, m) the same for a test that passes when the roll is HIGH (r > T): the distance from the top,
                        m - 1 - r, is scaled as above and turned back (it can go below 0: never high enough).

   THE CALL SITES.  vvfp_call_retarget() points `call target` (E8 rel32) sites at a companion's stub after checking
   each: a REQUIRED site must hold exactly that call or nothing is installed at all; an OPTIONAL site (one another
   patch may own) is left alone when it does not.  The writes go through vvfp_install_sites (all of them, or none). */
#ifndef VVFP_SLIDER_SCALE_H
#define VVFP_SLIDER_SCALE_H

#include <windows.h>
#include <string.h>
#include "install_sites.h"
#include "multiplier_choice.h"

#define SS_ONE 10u                       /* 1x, in tenths */
#define SS_MINIMUM 1u                    /* 0.1x */
#define SS_MAXIMUM 100u                  /* 10x */
#define SS_MAX_SITES 16

static unsigned int g_ss_tenths = SS_ONE;
static unsigned int g_ss_seed = 0x9E3779B9u;

/* xorshift32: the companion's own numbers, never the game's rand. */
static unsigned int ss_next(void) {
    unsigned int x = g_ss_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_ss_seed = x;
    return x;
}

/* Read the slider's number (tenths, 1..100; none is 10) and seed the numbers; 1 when it is not 1x. */
static int ss_start(const char *choice_file) {
    g_ss_tenths = vvfp_read_tenths(choice_file, SS_ONE, SS_MINIMUM, SS_MAXIMUM);
    g_ss_seed ^= GetTickCount() ^ (GetCurrentProcessId() << 16);
    if (g_ss_seed == 0u) {
        g_ss_seed = 0x9E3779B9u;
    }
    return g_ss_tenths != SS_ONE;
}

static unsigned int __cdecl ss_scale(unsigned int x) {
    unsigned long long product = (unsigned long long)x * g_ss_tenths;
    unsigned long long whole = product / 10u;
    if (ss_next() % 10u < (unsigned int)(product % 10u)) {
        ++whole;
    }
    return whole > 0x7FFFFFFFull ? 0x7FFFFFFFu : (unsigned int)whole;
}

static int __cdecl ss_roll_low(unsigned int r) {
    return (int)((r * 10u + ss_next() % 10u) / g_ss_tenths);
}

static int __cdecl ss_roll_high(unsigned int r, unsigned int m) {
    unsigned int distance = m - 1u - r;
    return (int)(m - 1u) - (int)((distance * 10u + ss_next() % 10u) / g_ss_tenths);
}

typedef struct {
    unsigned int va;
    int optional;                        /* 1: another patch may own it; then it is left alone */
} vvfp_call_site;

/* Point every `call target` site of `sites` at `stub`.  1 when every chosen site was written, 0 when nothing was
   (a required site not holding the call, or a failed write).  `chosen` (optional) receives which were written. */
static int vvfp_call_retarget(const vvfp_call_site *sites, int count, unsigned int target, const void *stub,
                              int *chosen) {
    static vvfp_site_write w[SS_MAX_SITES];
    static unsigned char expect[SS_MAX_SITES][5];
    int i, n = 0;
    if (count > SS_MAX_SITES) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        unsigned int rel = target - (sites[i].va + 5u);
        if (chosen != NULL) {
            chosen[i] = 0;
        }
        expect[i][0] = 0xE8;
        memcpy(&expect[i][1], &rel, 4);
        if (!vvfp_site_holds(sites[i].va, expect[i], 5)) {
            if (sites[i].optional) {
                continue;
            }
            return 0;
        }
        vvfp_site_branch(&w[n], sites[i].va, 5, expect[i], 0xE8, stub);
        ++n;
        if (chosen != NULL) {
            chosen[i] = 1;
        }
    }
    return n > 0 && vvfp_install_sites(w, n);
}

#endif /* VVFP_SLIDER_SCALE_H */
