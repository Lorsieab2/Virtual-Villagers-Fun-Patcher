/* VILLAGE SOLIDARITY (the owner, 2026-11-17): the branching engine's side of "VVFP Village Solidarity.dll".

   A page (node) may carry a "solidarity" tag in its flags byte (byte 3, bits 1-2: 1 raise, 2 lower, 3 neutral;
   src/vv_cie_graph.py SOLIDARITY_CODES).  With that companion started for this game:

     * when a page's effects are made (cg_make_effects), its tag moves the village's score (VvfpVillageScoreTag);
     * at a weighted chance split (cg_draw), a child whose next page is tagged "raise" (a cooperative ending) is
       weighted by the companion's factor for a high score, one tagged "lower" (a tense ending) by the factor for a
       low score; the other children keep their weights;
     * in the rare collection draw (story_collection.inc), an event the manifest marks "cooperative" or "repair" is
       weighted the same way.

   Without the companion (the row not ticked) every factor is 1000 and nothing is called: the tags stay words in the
   files, and every draw is made exactly as before, with the same numbers.  The game's own island events are never
   drawn here, so their odds never change. */

#define CG_NODE_SOL_SHIFT 2u
#define CG_NODE_SOL_MASK 12u            /* a node's flags (byte 3): its Village Solidarity tag */
#define CG_SOL_RAISE 1
#define CG_SOL_LOWER 2
#define CG_SOL_FAVOUR_HIGH 1
#define CG_SOL_FAVOUR_LOW 2

typedef int (__stdcall *cg_sol_tag_fn)(int game, int score_id, int tag, const char *title);
typedef int (__stdcall *cg_sol_factor_fn)(int game, int score_id, int favour);

static FARPROC cg_sol_proc(const char *name) {
    HMODULE m = GetModuleHandleA("VVFP Village Solidarity.dll");
    return m != NULL ? GetProcAddress(m, name) : NULL;
}

/* A node's tag: 0 none, 1 raise, 2 lower, 3 neutral. */
static int cg_sol_tag(const unsigned char *n) {
    return (int)((n[3] & CG_NODE_SOL_MASK) >> CG_NODE_SOL_SHIFT);
}

/* The factor (per mille) of an item favoured by `favour`; 1000 without the companion. */
static int cg_sol_factor(int game, int favour) {
    cg_sol_factor_fn f;
    int k;
    if (favour != CG_SOL_FAVOUR_HIGH && favour != CG_SOL_FAVOUR_LOW) {
        return 1000;
    }
    f = (cg_sol_factor_fn)(void *)cg_sol_proc("VvfpVillageScoreFactor");
    if (f == NULL) {
        return 1000;
    }
    k = f(game, 0, favour);
    return k >= 1000 && k <= 1000000 ? k : 1000;
}

typedef int (__stdcall *cg_sol_tag_once_fn)(int game, int score_id, int tag, const char *title, unsigned int when_lo,
                                            unsigned int when_hi, unsigned int pos);

/* A page reached with its effects made: its tag, if any, passed on EXACTLY ONCE for this run (`when`, its purchase)
   and this page (`pos`: its display and its place on the path) -- a page shown again after a restart, because the
   save lacks it, is not counted twice. */
static void cg_sol_reached(int game, const unsigned char *n, const char *title, unsigned __int64 when,
                           unsigned int pos) {
    cg_sol_tag_once_fn once;
    cg_sol_tag_fn f;
    int tag = cg_sol_tag(n);
    if (tag == 0) {
        return;
    }
    {
        /* the owner (2026-11-18): the popup says the change, after the 0..100 clamp (none: no line) */
        typedef int (__stdcall *get_fn)(int game, int score_id);
        get_fn get = (get_fn)(void *)cg_sol_proc("VvfpVillageScoreGet");
        int before = get != NULL ? get(game, 0) : -1, after = -1;
        once = (cg_sol_tag_once_fn)(void *)cg_sol_proc("VvfpVillageScoreTagOnce");
        if (once != NULL) {
            after = once(game, 0, tag, title, (unsigned int)when, (unsigned int)(when >> 32), pos);
        } else {
            f = (cg_sol_tag_fn)(void *)cg_sol_proc("VvfpVillageScoreTag");
            if (f != NULL) {
                after = f(game, 0, tag, title);
            }
        }
        if (before >= 0 && after >= 0 && after != before) {
            int on = cg_after_on;
            cg_after_on = 1;               /* #824: told on every tagged page, automatic lines or not */
            cg_after_line(after > before ? "solidarity+" : "solidarity-", "", after - before);
            cg_after_on = on;
        }
    }
}

/* A random number 0..n-1 for a draw Village Solidarity scaled: the game's own routine is exact only up to 0x7FFF
   (above, it stretches one 15-bit number), so a scaled total takes two of its numbers (30 bits), then the
   remainder.  An unscaled draw never comes here. */
static int cg_sol_random_below(const ce_adapter *a, int n) {
    unsigned int hi, lo;
    if (a == NULL || n <= 1) {
        return 0;
    }
    if (n <= 0x7FFF) {
        return ce_random_below(a, n);
    }
    hi = (unsigned int)ce_random_below(a, 0x8000);
    lo = (unsigned int)ce_random_below(a, 0x8000);
    return (int)(((hi << 15) | lo) % (unsigned int)n);
}

/* The children's weights at a split, each favoured child's multiplied by its factor (the others x 1000), when any
   factor is not 1000 and the totals stay small; else unchanged (the same draw, the same numbers, as before). */
static int cg_sol_weights(int game, const int *targets, int *weights, int count, int *total) {
    int factors[256], k, any = 0;
    __int64 sum = 0;
    for (k = 0; k < count && k < 256; ++k) {
        int tag = cg_sol_tag(cg_node_at(&cg_g, targets[k]));
        factors[k] = cg_sol_factor(game, tag == CG_SOL_RAISE ? CG_SOL_FAVOUR_HIGH
                                         : tag == CG_SOL_LOWER ? CG_SOL_FAVOUR_LOW : 0);
        any |= factors[k] != 1000;
        sum += (__int64)weights[k] * factors[k];
    }
    if (!any || sum <= 0 || sum > 0x3FFFFFFF) {
        return 0;
    }
    for (k = 0; k < count; ++k) {
        weights[k] *= factors[k];
    }
    *total = (int)sum;
    return 1;
}
