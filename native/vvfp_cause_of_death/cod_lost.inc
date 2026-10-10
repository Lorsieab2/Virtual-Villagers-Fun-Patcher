/* Babies lost with their mother, every game.  Included by
   vvfp_cause_of_death.c.

   The owner (2026-10-09): "Nursing mothers who die will only produce a grave
   for the mother (nursing child just disappears - child villager is never
   born as a full fledged villager)", and "Only full fledged villagers produce
   skeletons and graves".  So when a mother dies or disappears while she
   carries babies:

     - her Death or Disappeared record says so, in the game's own word for
       the state (below):  "  Nursing: yes, N babies (never born: lost with
       their mother)";
     - the Births and Conceptions log closes her open Conception with a
       "Lost before birth" record (the mother, the expected father, the
       babies), since no Birth will ever follow it.  The babies get no Death
       record, grave or skeleton.

   ONE STATE, NOT TWO.  In all five games one field holds the whole time from
   the conception to the child's creation: the mother's own age counter at
   the conception (A New Home +0x358 from +0x34C at 0x43BBFA; The Lost
   Children +0x540 from +0x534 at 0x44BA06; The Secret City +0xE8C from +0xE74
   at 0x455B2F; The Tree of Life and New Believers +0x1C4C from +0x1C3C at
   0x45E830 / 0x465E80), and the child is created, at 40 age units, once the
   counter is 40 past it (A New Home 0x42EF2E, The Lost Children 0x43BE1E,
   The Tree of Life 0x447C1D).  The baby is in her arms all that time: the
   later games' status word for the field is "Nursing" (string ePregnant),
   and A New Home's and The Lost Children's Villager Details panel draws
   "Nursing for:" exactly while it is set (A New Home 0x449419: string 0xE9
   when +0x358 is not 0; The Lost Children 0x4657AC: string 0x158 when +0x540
   is not 0).  Their "Pregnant" status string (0x228, 0x31B) is fetched by
   no code: developer-dead.  So every game's own word is "Nursing" (the
   owner, 2026-10-10: "Each game's own word"), and there is no separate
   phase to tell apart.

   WHEN THE FIELD IS READ.  At the Death or Disappeared record: the burial,
   the removal of an unburied body, the disappearance.  No death path in A
   New Home or The Lost Children writes the field (every store was
   enumerated: the conception, the deliveries, the record initialisers, the
   Mysterious Vial); in the later three its only direct store is the
   conception's.  Should a death still have cleared it by then, the per-frame
   tick's copy, taken while she was alive, is used -- but only while her age
   counter shows the delivery cannot have come yet, so a mother who delivered
   and then died between two frames (the load-time catch-up) is never said
   to have lost babies she gave birth to. */

struct lost_layout {
    unsigned int counter;        /* i32: the age counter the conception copies */
    unsigned int father;         /* the expected father's name (0: kept by VVFP VV1 Parentage) */
    unsigned int father_capacity;
    unsigned int father_head;    /* i32 */
    unsigned int father_body;    /* i32 */
};

static const struct lost_layout LOST[6] = {
    { 0 },
    { 0x34Cu, 0u, 0u, 0u, 0u },
    /* The Lost Children: the conception 0x44B980 copies the father's name,
       head and body here; The Gong of Wonder's fatherless pregnancy is "?",
       head 0, body 0, as the game writes it. */
    { 0x534u, 0x5C0u, 0x18u, 0x5E0u, 0x5DCu },
    { 0xE74u, 0xE48u, 0x18u, 0xE68u, 0xE64u },
    { 0x1C3Cu, 0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu },
    { 0x1C3Cu, 0x1C10u, 0x18u, 0x1C30u, 0x1C2Cu },
};

/* The delivery comes once the counter is this far past the conception
   (40, and The Tree of Life's compare is one past it). */
#define LOST_DELIVERY_UNITS 41

/* What the tick last saw of each living villager: the pregnancy field, the
   babies field, and whose they were (the name hash; 0 = nobody). */
static int lost_due[RECORDS_MAX];
static int lost_litter[RECORDS_MAX];
static unsigned int lost_name[RECORDS_MAX];
static int lost_slot = -1;

static void lost_forget(void) {
    memset(lost_due, 0, sizeof lost_due);
    memset(lost_litter, 0, sizeof lost_litter);
    memset(lost_name, 0, sizeof lost_name);
}

static void lost_tick(void) {
    unsigned char *records = cod_records();
    const struct game_records *r = &REC[g_game];
    int slot = cod_slot();
    int i;
    if (slot != lost_slot) {
        lost_slot = slot;
        lost_forget();
    }
    if (records == NULL || r->pregnant == 0u) {
        return;
    }
    for (i = 0; i < (int)r->slots && i < RECORDS_MAX; ++i) {
        const unsigned char *record = records + (size_t)i * r->stride;
        if (rec_present(record) && rec_health(record) > 0 && cod_is_villager(record)) {
            lost_due[i] = *(const int *)(record + r->pregnant);
            lost_litter[i] = *(const int *)(record + r->litter);
            lost_name[i] = cod_name_hash(record);
        }
    }
}

/* How many babies `record`'s villager carries now (1-3), or 0.  A New Home
   and The Lost Children leave the babies field 0 for one baby. */
static int lost_babies(const unsigned char *record) {
    const struct game_records *r = &REC[g_game];
    int due, litter, index;
    if (r->pregnant == 0u) {
        return 0;
    }
    due = *(const int *)(record + r->pregnant);
    litter = *(const int *)(record + r->litter);
    if (due == 0) {
        index = cod_index_of(record);
        if (index < 0 || index >= RECORDS_MAX || lost_due[index] == 0 || lost_name[index] == 0
            || lost_name[index] != cod_name_hash(record)
            || *(const int *)(record + LOST[g_game].counter) > lost_due[index] + LOST_DELIVERY_UNITS) {
            return 0;
        }
        litter = lost_litter[index];
    }
    return litter == 2 || litter == 3 ? litter : 1;
}

/* The Death / Disappeared record's line (empty when she carried none). */
static void lost_line(char *out, int babies) {
    out[0] = '\0';
    if (babies > 0) {
        wsprintfA(out, "  Nursing: yes, %d %s (never born: lost with their mother)\n", babies,
                  babies > 1 ? "babies" : "baby");
    }
}

typedef int (__stdcall *vv1_stash_fn)(int index, char *father, int capacity, int *head, int *body);
static int vv1_stash_state;      /* 0 = not tried, 1 = resolved, -1 = unavailable */
static vv1_stash_fn vv1_stash;

/* A New Home: the father "VVFP VV1 Parentage.dll" stashed at the conception
   (the game keeps none on the mother).  0 when it is not shipped or holds
   none for her. */
static int lost_vv1_father(int index, char *name, int capacity, int *head, int *body) {
    if (vv1_stash_state == 0) {
        HMODULE module = vvfp_load_patcher_dll("VVFP VV1 Parentage.dll");
        vv1_stash = module != NULL ? (vv1_stash_fn)GetProcAddress(module, "Vv1ParentageQueryStash") : NULL;
        vv1_stash_state = vv1_stash != NULL ? 1 : -1;
    }
    return vv1_stash_state == 1 && index >= 0 && vv1_stash(index, name, capacity, head, body);
}

/* "Lost before birth": her `babies`, never born, `how` she was lost ("died",
   "disappeared").  Not for New Believers' Heathens, whose pregnancies the
   Births and Conceptions log never opened. */
static void lost_record(const unsigned char *record, int babies, const char *how) {
    const struct game_records *r = &REC[g_game];
    const struct lost_layout *l = &LOST[g_game];
    char before[512];
    char mother[64], father[64], fh[16], fb[16];
    int head = -1, body = -1, known = 0;
    if (babies <= 0 || (r->heathen != 0u && record[r->heathen] != 0)) {
        return;
    }
    cod_printable(mother, sizeof mother, (const char *)record + r->name, (int)r->name_capacity);
    father[0] = '\0';
    if (l->father != 0u) {
        cod_printable(father, sizeof father, (const char *)record + l->father, (int)l->father_capacity);
        if (father[0] != '\0') {
            head = *(const int *)(record + l->father_head);
            body = *(const int *)(record + l->father_body);
            known = 1;
        }
    } else {
        char stash[64];
        stash[0] = '\0';
        if (lost_vv1_father(cod_index_of(record), stash, (int)sizeof stash, &head, &body)) {
            cod_printable(father, sizeof father, stash, (int)sizeof stash - 1);
            known = 1;
        }
    }
    if (father[0] == '\0') {
        lstrcpyA(father, "(unknown)");
    }
    /* 0 is a real head and body: only a value nobody recorded is unknown. */
    if (known && head >= 0) {
        wsprintfA(fh, "%d", head);
    } else {
        lstrcpyA(fh, "(unknown)");
    }
    if (known && body >= 0) {
        wsprintfA(fb, "%d", body);
    } else {
        lstrcpyA(fb, "(unknown)");
    }
    wsprintfA(before,
              "  Mother: %s\n    Head: %d\n    Body: %d\n"
              "  Father: %s\n    Head: %s\n    Body: %s\n"
              "  Babies in pregnancy: %d\n"
              "  What happened: the mother %s while nursing; never born\n",
              mother, *(const int *)(record + r->head), *(const int *)(record + r->body),
              father, fh, fb, babies, how);
    COD_COUNT(lost);
    (void)cod_write(LOG_LOST_BIRTH, record, cod_index_of(record) >= 0, before, NULL, 0);
}
