/* The Playful Dolphins in The Tree of Life: the game's side.  Included by vvfp_more_island_events.c after
   adv_vv345.inc, whose two-choice dialog, object methods, slot and draw it shares (t_register: its own entry in the
   draw).  No site of its own: the executable is not touched for it.

   Health: the record's health block +0x1C34 holds the health at +0xC (record +0x1C40, an int 0..100: the game's own
   setter 0x46AF00 -- thiscall on the block, (value, cause) -- stores the value at [ecx+0xC], 0 and the cause when it
   is 0 or less, else at most 0x64 with cause -1; its adder 0x46AF40 clamps the same way).  The slap sets the new
   value through that setter, never below 1, so the game's own death path (value 0) is never reached.

   Farming: the record's skills are floats from +0x1C5C (Farming first; adv_vv345.inc t_skill), capped at 100 as the
   game's own skill adder 0x46AD80 caps them (fcom against the double 100.0 at 0x48A7C0, then fld 100.0 from 0x48CF04;
   below 0.0 it stores 0). */

#define DP_VV4_HEALTH_BLOCK 0x1C34u
#define DP_VV4_HEALTH 0x1C40u
#define DP_VV4_SET_HEALTH 0x46AF00u

static int vv4_health(int index) {
    const unsigned char *r = t_record(index);
    return r != NULL ? *(const int *)(r + DP_VV4_HEALTH) : 0;
}

static void vv4_set_health(int index, int value) {
    unsigned char *r = t_record(index);
    if (r != NULL) {
        ADV_TC2(DP_VV4_SET_HEALTH, r + DP_VV4_HEALTH_BLOCK, value, -1);
    }
}

static const dp_game DP_VV4 = { &ADV_VV4, vv4_health, vv4_set_health };

static adv_object g_dp_object;
static const dp_game *g_dp;            /* the installed game's (The Tree of Life), NULL when not installed */

static int dp_listable(void) {
    int possible = 0;
    __try {
        possible = g_dp != NULL && dp_possible(g_dp);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

static int dp_begin_now(void) {
    return g_dp != NULL && dp_begin(g_dp, g_table_adv);
}

static void dp_install(void) {
    g_dp = &DP_VV4;
    t_new_object(&g_dp_object);
    t_register(&g_dp_object, &DP_FLOW, dp_listable, dp_begin_now);
}
