/* Diving for Treasure in The Secret City: the game's side.  Included by vvfp_more_island_events.c after
   troubling_vv3.inc (its vv3_age) and adv_vv345.inc, whose two-choice dialog, object methods, slot and draw it
   shares (t_register: its own entry in the draw).  No site of its own: the executable is not touched for it.

   "Dislikes swimming": The Secret City's likes +0xFB4 and dislikes +0xFC0, three ints each (-1 empty), as every
   like / dislike of the game (adv_vv345.inc t_injure); swimming is entry 37 of the game's own preference list --
   the comma list the game splits at file offset 0x97488 ("ants, crowds, ..., fish, fruit, papaya, flies, swimming,
   running, ..."; running is 38, as Grant Running proves for the same list). */

#define DV_VV3_LIKES 0xFB4u
#define DV_VV3_DISLIKES 0xFC0u
#define DV_VV3_SWIMMING 37

static void vv3_dislike_swimming(int index) {
    unsigned char *r = t_record(index);
    if (r != NULL) {
        adv_dislike((int *)(r + DV_VV3_LIKES), (int *)(r + DV_VV3_DISLIKES), 3, DV_VV3_SWIMMING);
    }
}

static const dv_game DV_VV3 = { &ADV_VV3, vv3_age, vv3_dislike_swimming };

static adv_object g_dv_object;
static const dv_game *g_dv;            /* the installed game's (The Secret City), NULL when not installed */

static int dv_listable(void) {
    int possible = 0;
    __try {
        possible = g_dv != NULL && dv_possible(g_dv);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

static int dv_begin_now(void) {
    return g_dv != NULL && dv_begin(g_dv, g_table_adv);
}

static void dv_install(void) {
    g_dv = &DV_VV3;
    t_new_object(&g_dv_object);
    t_register(&g_dv_object, &DV_FLOW, dv_listable, dv_begin_now);
}
