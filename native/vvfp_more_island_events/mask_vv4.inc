/* The Mysterious Mask in The Tree of Life: the game's side.  Included by vvfp_more_island_events.c after
   adv_vv345.inc, whose dialog, object methods, four-answer popup (vvfp_multi_answer.h), slot and draw it shares
   (t_register: its own entry in the draw).  No site of its own: the executable is not touched for it.

   The population: as the game's own count 0x467610 counts it (the island-event scaling's people, 150 records from the
   manager +0x44, stride 0x2E3C): each record present (+0x1CC4), not a body or ghost (+0x1CC7), with health (+0x1C40)
   above 0, counts 1, plus its babies (+0x1C50) while it carries (+0x1C4C) -- The Lost Children's "A Dangerous
   Mission" rule (0x425860: the living villagers plus the babies carried).  Age: +0x1B8C, 20 units a year. */

static int vv4_mk_age(const unsigned char *r) {
    return *(const int *)(r + 0x1B8C);
}

static int vv4_mk_alive(const unsigned char *r) {
    return r[0x1CC4] != 0 && r[0x1CC7] == 0 && *(const int *)(r + 0x1C40) > 0;
}

static int vv4_mk_population(void) {
    int i, n = 0;
    for (i = 0; i < g_records; ++i) {
        const unsigned char *r = t_record(i);
        if (r != NULL && vv4_mk_alive(r)) {
            ++n;
            if (*(const int *)(r + 0x1C4C) != 0) {
                n += *(const int *)(r + 0x1C50);
            }
        }
    }
    return n;
}

static const mk_game MK_VV4 = { &ADV_VV4, vv4_mk_age, vv4_mk_alive, vv4_mk_population };

static adv_object g_mk_object;
static const mk_game *g_mk;            /* the installed game's (The Tree of Life), NULL when not installed */
static adv_game g_mk_layout;           /* The Tree of Life's popup, MK_LINES_LESS lines shorter per answer past two */

static int mk_listable(void) {
    int possible = 0;
    __try {
        possible = g_mk != NULL && mk_possible(g_mk);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

static int mk_begin_now(void) {
    return g_mk != NULL && mk_begin(g_mk, &g_mk_layout);
}

static void mk_install(void) {
    g_mk_layout = ADV_VV4;
    g_mk_layout.lines = ADV_VV4.lines - MK_LINES_LESS * (MK_ANSWERS - 2);
    g_mk = &MK_VV4;
    t_new_object(&g_mk_object);
    t_register(&g_mk_object, &MK_FLOW, mk_listable, mk_begin_now);
}
