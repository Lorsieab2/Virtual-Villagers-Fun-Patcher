/* appearance_extras.h -- what both Change Appearance windows share in all five games (the owner,
   2026-10-28: the two windows "just about identical").  Include after <windows.h> and head_look.h.

   THE PER-VILLAGER WINDOW
     * Undo changes        every control back to how the villager looks now: the window's own start, from
                           the head, body, mask and look saved when it opened.  Nothing is written or charged.
     * Reset to original   the villager's original head, body and mask (native/shared/original_look_client.h),
                           with head look Auto; "Original look not known" and nothing changed when it is not.
                           OK then keeps it like any change: same price, same records, sidecars and log.
     * Random head, Random body, Random mask (the pool of Change Appearance for All's "Random (All 5 + No
       Mask)": no mask or any of the five), Random look (Young or Old), and the head by hair colour -- the
       villager's own sex, the colour groups of that game's Change Appearance for All.  Each shows in the
       preview; pressing again rolls again; Cancel keeps nothing.

   CHANGE APPEARANCE FOR ALL
     * A Head look row for the men and one for the women: Leave as is (the default), Auto (old from 55),
       Young, Old, Random (Young or Old, rolled per villager).  Only that sex's covered villagers.
     * Undo changes (every control back to its start) and Reset to original (each covered villager whose
       original look is known; the others are counted and left as they are).

   The control ids are the same in every game (none of the five windows uses 3500..3539). */
#ifndef VVFP_APPEARANCE_EXTRAS_H
#define VVFP_APPEARANCE_EXTRAS_H

#define VVFP_AX_UNDO          3500
#define VVFP_AX_RESET         3501
#define VVFP_AX_RANDOM_HEAD   3502
#define VVFP_AX_RANDOM_BODY   3503
#define VVFP_AX_RANDOM_MASK   3504
#define VVFP_AX_RANDOM_LOOK   3505
#define VVFP_AX_HAIR_FIRST    3510      /* Black, Brown, Red / Ginger, Blonde, Other */
#define VVFP_AX_HAIR_LAST     3514
/* Change Appearance for All's Head look rows: men 3520.., women 3530..; Leave as is, Auto, Young, Old,
   Random; the row's "Head look:" label is +5. */
#define VVFP_AX_LOOK_ROW(sex) (3520 + 10 * (sex))
#define VVFP_AX_LOOK_LABEL(sex) (VVFP_AX_LOOK_ROW(sex) + 5)

#define VVFP_AX_LEAVE   (-1)            /* a row's Leave as is */
#define VVFP_AX_RANDOM  3               /* a row's Random */
#define VVFP_AX_MAX     256

#ifndef RC_INVOKED
/* xorshift32; never 0. */
static unsigned int vvfp_ax_rand(unsigned int *rng) {
    unsigned int x = *rng ? *rng : 0x2545F491u;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *rng = x;
    return x;
}

static int vvfp_ax_pick(unsigned int *rng, int n) {
    return n > 0 ? (int)((vvfp_ax_rand(rng) >> 3) % (unsigned int)n) : 0;
}

/* A row from a colour group, never the one the villager has now when the group holds another (so a
   press always shows a change). */
static int vvfp_ax_pick_from(unsigned int *rng, const unsigned char *rows, int n, int now) {
    int v = rows[vvfp_ax_pick(rng, n)];
    if (v == now && n > 1) {
        v = rows[vvfp_ax_pick(rng, n)];
    }
    return v;
}

/* Random head / body / mask: any of `count`, again preferring a change. */
static int vvfp_ax_pick_other(unsigned int *rng, int count, int now) {
    int v = vvfp_ax_pick(rng, count);
    if (v == now && count > 1) {
        v = (v + 1 + vvfp_ax_pick(rng, count - 1)) % count;
    }
    return v;
}

/* The Random look button: Young or Old, the other one when it is already one of them. */
static int vvfp_ax_random_look(unsigned int *rng, int now) {
    if (now == VVFP_HEAD_LOOK_YOUNG || now == VVFP_HEAD_LOOK_OLD) {
        return now == VVFP_HEAD_LOOK_YOUNG ? VVFP_HEAD_LOOK_OLD : VVFP_HEAD_LOOK_YOUNG;
    }
    return vvfp_head_look_random(rng);
}

/* ---- Change Appearance for All: the Head look rows --------------------------------------------------- */

/* Every row to Leave as is; both rows hidden when the look is not offered (A New Home without Grey Hair at
   55, or no "VVFP Head Look.dll"). */
static void vvfp_ax_look_rows_init(HWND w, int offered, int choice[2]) {
    int sex, k;
    for (sex = 0; sex < 2; ++sex) {
        choice[sex] = VVFP_AX_LEAVE;
        for (k = 0; k <= 5; ++k) {
            ShowWindow(GetDlgItem(w, VVFP_AX_LOOK_ROW(sex) + k), offered ? SW_SHOW : SW_HIDE);
        }
        CheckRadioButton(w, VVFP_AX_LOOK_ROW(sex), VVFP_AX_LOOK_ROW(sex) + 4, VVFP_AX_LOOK_ROW(sex));
    }
}

/* 1 when `id` is a row's radio (and `choice` says what it now is). */
static int vvfp_ax_look_rows_command(unsigned int id, int choice[2]) {
    int sex;
    for (sex = 0; sex < 2; ++sex) {
        if (id >= (unsigned int)VVFP_AX_LOOK_ROW(sex) && id <= (unsigned int)VVFP_AX_LOOK_ROW(sex) + 4) {
            choice[sex] = (int)(id - (unsigned int)VVFP_AX_LOOK_ROW(sex)) - 1;
            return 1;
        }
    }
    return 0;
}

/* The looks Change Appearance for All will keep: one entry per covered villager whose look changes. */
typedef struct {
    const void *record[VVFP_AX_MAX];
    int look[VVFP_AX_MAX];
    int was[VVFP_AX_MAX];
    int count;
} vvfp_ax_look_plan;

/* Plan a covered villager's look: its sex's row (Random rolled here, so the plan is what is kept), else
   Auto when Reset to original reaches it (`reset`: its original look is known).  Only a change is kept. */
static void vvfp_ax_look_plan_add(vvfp_ax_look_plan *plan, const vvfp_head_look_api *api, int game,
                                  const void *record, int choice, int reset, unsigned int *rng) {
    int want, was;
    if (api->get == NULL || plan->count >= VVFP_AX_MAX) {
        return;
    }
    want = choice == VVFP_AX_RANDOM ? vvfp_head_look_random(rng)
         : choice >= 0 ? choice : reset ? VVFP_HEAD_LOOK_AUTO : -1;
    if (want < 0) {
        return;
    }
    was = api->get(game, record);
    if (was == want) {
        return;
    }
    plan->record[plan->count] = record;
    plan->look[plan->count] = want;
    plan->was[plan->count] = was;
    ++plan->count;
}

/* Keep the planned looks in one write: 1 when kept (or nothing to keep). */
static int vvfp_ax_look_plan_commit(const vvfp_ax_look_plan *plan, const vvfp_head_look_api *api, int game) {
    if (plan->count == 0) {
        return 1;
    }
    return api->set_many != NULL && api->set_many(game, plan->record, plan->look, plan->count);
}

/* Put the looks back after a later step of the same OK failed. */
static void vvfp_ax_look_plan_undo(const vvfp_ax_look_plan *plan, const vvfp_head_look_api *api, int game) {
    if (plan->count != 0 && api->set_many != NULL) {
        (void)api->set_many(game, plan->record, plan->was, plan->count);
    }
}

/* "Reset to original" in Change Appearance for All: what OK will do, or that nobody's original is known
   (then nothing is set).  1 when the reset is set. */
static int vvfp_ax_reset_all_ask(HWND w, const char *title, int known, int unknown) {
    char text[320];
    if (known == 0) {
        MessageBoxA(w, "Original look not known for any villager. Nothing was changed.", title,
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(text, "OK will put %d %s back to the original head, body and mask, with head look Auto, and "
              "then apply anything else chosen here.", known, known == 1 ? "villager" : "villagers");
    if (unknown > 0) {
        wsprintfA(text + lstrlenA(text), "\r\n\r\nOriginal look not known for %d %s, left as %s.", unknown,
                  unknown == 1 ? "villager" : "villagers", unknown == 1 ? "it is" : "they are");
    }
    MessageBoxA(w, text, title, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* The closing message of Change Appearance for All (`out`: 320 bytes), with how many originals were not
   known when Reset to original was used. */
static void vvfp_ax_applied_text(char *out, const char *done, int reset, int unknown) {
    lstrcpynA(out, done, 200);
    if (reset && unknown > 0) {
        wsprintfA(out + lstrlenA(out), "\r\n\r\nOriginal look not known for %d %s, left as %s.", unknown,
                  unknown == 1 ? "villager" : "villagers", unknown == 1 ? "it was" : "they were");
    }
}
#endif

#endif /* VVFP_APPEARANCE_EXTRAS_H */
