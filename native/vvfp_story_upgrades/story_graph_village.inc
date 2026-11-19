/* ---- Traders and the village effects (cie-v6-binary.md 39-43; the owner's spec of 2026-11-16/17) --------------

   Included by story_graph.inc before cg_effect.  docs/event-collection/traders-and-effects-research.md lists every
   address below with its evidence.

   - Goods (33): the counts a trader may give or take, by one word in every game: "supply" (code 25, PR #806's
     effect, widened from The Tree of Life's three supplies to every game's goods), "trade" (code 41: give n of one,
     get m of another, all or nothing) and the condition "has_supply" (op 19).  Never below 0; a gain stops at the
     game's own ceiling; a word the game does not keep is story only there.
   - Group behaviours (34, code 42): every living, listed villager (New Believers: its believers) of an age group,
     or one role's villager, takes the game's closest real action; group sickness and cure.
   - The village (35, code 43): the next island event sooner or later, a tech level up or down, a construction
     sped, the game's own weather. */

#ifdef VVFP_TEST
static int test_graph_goods = -1;         /* has_supply: -1 the village's own, else forced 0 / 1 */
static int test_graph_weather = -1;       /* the last weather type started */
static int test_graph_weather_call = 1;   /* 0: record the type without calling the game */
#endif

/* The owner (2026-11-18): "if an effect happens, it should say at the end of the event popup", with the amount.
   These effects know their amount only once made (a store's ceiling, the timer's cap, the level the game's own
   routine gives), so their lines are written as each is made, for the page's popup (cg_show), only on a page with
   automatic lines (cie-v6-binary.md 25).  The words are CG_AUTO_LINES' (story_graph.inc): <N> a number, <W> a word. */
static char cg_after[1024];
static int cg_after_on;
static const char *cg_auto_text(const char *key);   /* story_graph.inc */

static void cg_after_line(const char *key, const char *word, int number) {
    char line[160], digits[16];
    const char *t = cg_auto_text(key);
    int n = 0;
    if (!cg_after_on || t == NULL) {
        return;
    }
    if (word != NULL && lstrcmpA(word, "tech") == 0) {
        word = "tech points";      /* the owner: a good's words as the game says them */
    }
    for (; *t != '\0' && n < (int)sizeof line - 1; ++t) {
        const char *put = NULL;
        if (t[0] == '<' && (t[1] == 'N' || t[1] == 'W') && t[2] == '>') {
            wsprintfA(digits, "%d", number < 0 ? -number : number);
            put = t[1] == 'N' ? digits : word;
        }
        if (put == NULL) {
            line[n++] = *t;
            continue;
        }
        for (; *put != '\0' && n < (int)sizeof line - 1; ++put) {
            line[n++] = *put == '_' ? ' ' : *put;      /* cutting_tools: "cutting tools" */
        }
        t += 2;
    }
    line[n] = '\0';
    if (lstrlenA(cg_after) + n + 2 < (int)sizeof cg_after) {
        if (cg_after[0] != '\0') {
            lstrcatA(cg_after, "\n");
        }
        lstrcatA(cg_after, line);
    }
}

static int cg_prefix(const char *s, const char *prefix) {
    while (*prefix != '\0' && *s == *prefix) {
        ++s;
        ++prefix;
    }
    return *prefix == '\0';
}
/* ---- 39. Goods ------------------------------------------------------------------------------------------------ */

enum { CGG_FOOD = 1, CGG_TECH, CGG_VALUE, CGG_FRUIT, CGG_COLLECTIBLE, CGG_SUPPLY4, CGG_YELLOW_FRUIT };

#ifdef VVFP_TEST
static int test_graph_yellow = -2;        /* yellow fruit: -2 the real companion, -1 none, else its count */
#endif

/* The Tree of Life's yellow fruit tree (with "Yellow Fruit Trees are No Longer Unlimited"): "VVFP VV4 Fruit
   Supply.dll"'s own count through its export VvfpYellowFruitAdd (0..1,000; `delta` 0 only reads it), -1 when the
   companion is not loaded or has no village (the stock tree never runs out: no count). */
static int cg_yellow_fruit(int delta) {
    typedef int (__stdcall *add_fn)(int);
    HMODULE module;
    add_fn add;
#ifdef VVFP_TEST
    if (test_graph_yellow >= -1) {
        if (test_graph_yellow >= 0) {
            long long v = (long long)test_graph_yellow + delta;
            test_graph_yellow = v < 0 ? 0 : v > 1000 ? 1000 : (int)v;
        }
        return test_graph_yellow;
    }
#endif
    module = GetModuleHandleA("VVFP VV4 Fruit Supply.dll");
    add = module != NULL ? (add_fn)GetProcAddress(module, "VvfpYellowFruitAdd") : NULL;
    return add != NULL ? add(delta) : -1;
}

typedef struct {
    const char *word;
    unsigned char game;
    unsigned char kind;
    unsigned char which;           /* CGG_VALUE: the adapter's value; CGG_SUPPLY4: C4_SUPPLY_* */
    const char *name;              /* the log's word */
} cg_good_def;

static const cg_good_def CG_GOODS[] = {
    { "food", 1, CGG_FOOD, 0, "Food" }, { "tech", 1, CGG_TECH, 0, "Tech points" },
    { "berries", 1, CGG_VALUE, 0, "Berry bushes" },
    { "food", 2, CGG_FOOD, 0, "Food" }, { "tech", 2, CGG_TECH, 0, "Tech points" },
    { "coconuts", 2, CGG_VALUE, 0, "Coconut trees" }, { "fish", 2, CGG_VALUE, 1, "Fish" },
    { "collectible", 2, CGG_COLLECTIBLE, 0, "Collectibles" },
    { "food", 3, CGG_FOOD, 0, "Food" }, { "tech", 3, CGG_TECH, 0, "Tech points" },
    { "honey", 3, CGG_VALUE, 6, "Honey" }, { "fruit", 3, CGG_FRUIT, 0, "Fruit on the trees" },
    { "collectible", 3, CGG_COLLECTIBLE, 0, "Collectibles" },
    { "food", 4, CGG_FOOD, 0, "Food" }, { "tech", 4, CGG_TECH, 0, "Tech points" },
    { "blackberries", 4, CGG_VALUE, 0, "Blackberries" },
    { "yellow_fruit", 4, CGG_YELLOW_FRUIT, 0, "Yellow fruit" },
    { "cutting_tools", 4, CGG_SUPPLY4, 0, "Cutting tools" }, { "soap", 4, CGG_SUPPLY4, 1, "Bars of soap" },
    { "cloth", 4, CGG_SUPPLY4, 2, "Cloth bolts" },
    { "collectible", 4, CGG_COLLECTIBLE, 0, "Collectibles" },
    { "food", 5, CGG_FOOD, 0, "Food" }, { "tech", 5, CGG_TECH, 0, "Tech points" },
    { "noni", 5, CGG_VALUE, 0, "Noni bushes" },
    { "collectible", 5, CGG_COLLECTIBLE, 0, "Collectibles" },
};
#define CG_GOOD_COUNT ((int)(sizeof CG_GOODS / sizeof CG_GOODS[0]))
#define CG_GOOD_MAX 9999           /* one effect's change, either way (the VV4 supplies keep PR #806's 99) */
#define CG_COLLECTIBLE_PIECES 48

/* Whether `word` is a good in any game (the loader's check). */
static int cg_good_word(const char *word) {
    int i;
    for (i = 0; word != NULL && i < CG_GOOD_COUNT; ++i) {
        if (lstrcmpA(word, CG_GOODS[i].word) == 0) {
            return 1;
        }
    }
    return 0;
}

static const cg_good_def *cg_good(int game, const char *word) {
    int i;
    for (i = 0; word != NULL && i < CG_GOOD_COUNT; ++i) {
        if (CG_GOODS[i].game == game && lstrcmpA(word, CG_GOODS[i].word) == 0) {
            return &CG_GOODS[i];
        }
    }
    return NULL;
}

/* Collectible piece k's count (VV3-VV5) or found byte (VV2); NULL without a village. */
static void *cg_piece(int game, int k) {
    unsigned char *world;
    switch (game) {
    case 2:
        world = VV2_WORLD();
        return world != NULL ? (void *)(world + 0x2E720u + (unsigned int)k) : NULL;
    case 3: return (void *)(uintptr_t)(0x58F438u + 4u * (0x34u + (unsigned int)k));
    case 4: return (void *)(uintptr_t)(0x4CC918u + 4u * (unsigned int)k);
    case 5: return (void *)(uintptr_t)(0x4DBFC8u + 0x630u + 4u * (0x50u + (unsigned int)k));
    default: return NULL;
    }
}

static int cg_piece_count(int game, int k) {
    void *p = cg_piece(game, k);
    if (p == NULL) {
        return 0;
    }
    return game == 2 ? (*(unsigned char *)p != 0) : *(int *)p;
}

/* The pieces owned (a count above 0), and the duplicates a trader may take (each count above 1). */
static void cg_pieces(int game, int *owned, int *spare) {
    int k, n;
    *owned = *spare = 0;
    for (k = 0; k < CG_COLLECTIBLE_PIECES; ++k) {
        n = cg_piece_count(game, k);
        if (n > 0) {
            ++*owned;
            if (game != 2) {
                *spare += n - 1;
            }
        }
    }
}

/* How many collectibles a gain may still add, by cg_piece_step's own rules (cg_piece_gain_ok): never a set's last
   piece, never a VV3 Tablet piece; in VV3-VV5 an owned piece may count once more (a duplicate). */
static int cg_piece_room(int game) {
    int set, k, owned, room = 0;
    for (set = 0; set < CG_COLLECTIBLE_PIECES; set += 12) {
        if (game == 3 && set == 24) {
            continue;                  /* the Tablet */
        }
        for (owned = 0, k = set; k < set + 12; ++k) {
            owned += cg_piece_count(game, k) > 0;
        }
        if (game != 2 && owned > 0) {
            return CG_GOOD_MAX;        /* a duplicate is always allowed */
        }
        room += owned < 11 ? 11 - owned : 0;
    }
    /* VV3-VV5: once one new piece is given, it may take duplicates without end (Codex P2) */
    return game != 2 && room > 0 ? CG_GOOD_MAX : room;
}

/* VV3's planted trees (0x594844), 0..3. */
static int cg_trees(void) {
    int n = *(int *)(uintptr_t)0x594844u;
    return n < 0 ? 0 : n > 3 ? 3 : n;
}

/* The amount of good `d` the village has now, what a trader may take (collectibles: the duplicates; VV2: none),
   and *room: how much a gain may still add.  -1 when the game does not keep it now (a value not there yet, The
   Tree of Life's supply before its puzzle, VV3 with no tree planted). */
static int cg_good_have(const ce_adapter *a, int game, const cg_good_def *d, int *room) {
    int now = 0, i, owned, spare;
    *room = 0;
    switch (d->kind) {
    case CGG_FOOD: case CGG_TECH:
        now = d->kind == CGG_FOOD ? a->food() : a->tech();
        now = now < 0 ? 0 : now;
        *room = now < CE_MAX_AMOUNT ? CE_MAX_AMOUNT - now : 0;   /* never negative: a gain never takes away */
        return now;
    case CGG_VALUE:
        if (a->value_get == NULL || d->which >= a->value_count || !a->value_get(d->which, &now)) {
            return -1;
        }
        now = now < 0 ? 0 : now;
        *room = a->values[d->which].max > now ? a->values[d->which].max - now : 0;
        return now;
    case CGG_FRUIT:
        if (cg_trees() == 0) {
            return -1;
        }
        for (i = 0; i < cg_trees(); ++i) {
            int t = 0;
            if (a->value_get(i, &t)) {
                t = t < 0 ? 0 : t;
                now += t;
                *room += t < a->values[i].max ? a->values[i].max - t : 0;
            }
        }
        return now;
    case CGG_COLLECTIBLE:
        cg_pieces(game, &owned, &spare);
        *room = cg_piece_room(game);   /* only the gains cg_piece_step may make (Codex P2) */
        return spare;
    case CGG_YELLOW_FRUIT:
        now = cg_yellow_fruit(0);
        *room = now >= 0 && now < 1000 ? 1000 - now : 0;
        return now;
    case CGG_SUPPLY4: {
        int big = c4_supply_cap_installed(), cap;
#ifdef VVFP_TEST
        if (test_graph_supply_cap >= 0) {
            big = test_graph_supply_cap;
        }
#endif
        if (!cg_puzzle_solved(game, C4_SUPPLY_PUZZLES[d->which])) {
            return -1;
        }
        now = *(int *)(uintptr_t)C4_SUPPLY_AT[d->which];
        cap = c4_supply_cap(d->which, big);
        *room = cap > now ? cap - now : 0;
        return now < 0 ? 0 : now;
    }
    default:
        return -1;
    }
}

/* The total a log line shows for good `d` (collectibles: the pieces owned). */
static int cg_good_shown(const ce_adapter *a, int game, const cg_good_def *d) {
    int room, owned, spare;
    if (d->kind == CGG_COLLECTIBLE) {
        cg_pieces(game, &owned, &spare);
        return d->game == 2 ? owned : owned + spare;
    }
    return cg_good_have(a, game, d, &room);
}

/* One unit of a VV3 tree's fruit: a gain to the emptiest planted tree, a loss from the fullest; 0 when none can. */
static int cg_fruit_step(const ce_adapter *a, int gain) {
    int i, best = -1, best_n = 0, t;
    for (i = 0; i < cg_trees(); ++i) {
        if (!a->value_get(i, &t)) {
            continue;
        }
        if (gain ? (t < a->values[i].max && (best < 0 || t < best_n)) : (t > 0 && (best < 0 || t > best_n))) {
            best = i;
            best_n = t;
        }
    }
    return best >= 0 && a->value_set(best, best_n + (gain ? 1 : -1));
}

/* Whether a gain of piece k (count c) keeps clear of every puzzle (the owner, 2026-11-18): it never completes a set (a
   new piece that would make its 12 whole is left out) and never gives The Secret City's Tablet pieces (The Ruins). */
static int cg_piece_gain_ok(int game, int k, int c) {
    int first = k - k % 12, j, owned = 0;
    if (game == 3 && k >= 24 && k < 36) {
        return 0;
    }
    if (c > 0) {
        return 1;              /* a duplicate: the set is as it was */
    }
    for (j = first; j < first + 12; ++j) {
        owned += cg_piece_count(game, j) > 0;
    }
    return owned < 11;
}

/* One collectible: a gain is +1 to a random piece (VV2: a piece not found yet); a loss -1 from a random
   duplicate.  0 when none can change. */
static int cg_piece_step(const ce_adapter *a, int game, int gain) {
    int pick[CG_COLLECTIBLE_PIECES], n = 0, k;
    for (k = 0; k < CG_COLLECTIBLE_PIECES; ++k) {
        int c = cg_piece_count(game, k);
        if (gain ? ((game != 2 || c == 0) && cg_piece_gain_ok(game, k, c)) : (game != 2 && c > 1)) {
            pick[n++] = k;
        }
    }
    if (n == 0 || cg_piece(game, 0) == NULL) {
        return 0;
    }
    k = pick[ce_random_below(a, n)];
    if (game == 2) {
        *(unsigned char *)cg_piece(game, k) = 1;
    } else {
        *(int *)cg_piece(game, k) += gain ? 1 : -1;
    }
    return 1;
}

/* Good `d` changed by `delta` within 0..its ceiling (a gain never lowers a count above it); the change made. */
static int cg_good_change(const ce_adapter *a, int game, const cg_good_def *d, int delta) {
    int room, have = cg_good_have(a, game, d, &room), done = 0, before, after, step;
    ce_result scratch;
    char line[96];
    memset(&scratch, 0, sizeof scratch);
    if (have < 0 || delta == 0) {
        return 0;
    }
    if (delta < 0 && -delta > have) {
        delta = -have;
    }
    if (delta > 0 && delta > room) {
        delta = room;
    }
    if (delta == 0) {
        return 0;
    }
    before = cg_good_shown(a, game, d);
    __try {
        switch (d->kind) {
        case CGG_FOOD: case CGG_TECH:
            cg_amount(a, d->kind == CGG_FOOD, delta, &scratch);
            done = delta;
            break;
        case CGG_VALUE:
            done = a->value_set(d->which, have + delta) ? delta : 0;
            break;
        case CGG_SUPPLY4:
            *(int *)(uintptr_t)C4_SUPPLY_AT[d->which] = have + delta;
            done = delta;
            break;
        case CGG_YELLOW_FRUIT:
            done = cg_yellow_fruit(delta) >= 0 ? delta : 0;
            break;
        default:
            for (step = 0; step < (delta > 0 ? delta : -delta); ++step) {
                if (!(d->kind == CGG_FRUIT ? cg_fruit_step(a, delta > 0) : cg_piece_step(a, game, delta > 0))) {
                    break;
                }
                done += delta > 0 ? 1 : -1;
            }
            break;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return done;
    }
    after = cg_good_shown(a, game, d);
    if (done != 0 && d->kind != CGG_FOOD && d->kind != CGG_TECH && after != before) {
        wsprintfA(line, "  %s: %d -> %d\n", d->name, before, after);
        if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
            lstrcatA(cg_extra_lines, line);
        }
    }
    return done;
}

/* "has_supply" (op 19): the village has at least `n` of `word` to give now. */
static int cg_has_good(int game, const char *word, int n) {
    const ce_adapter *a = ce_adapter_for(game);
    const cg_good_def *d = cg_good(game, word);
    int room;
#ifdef VVFP_TEST
    if (test_graph_goods >= 0) {
        return test_graph_goods;
    }
#endif
    return a != NULL && d != NULL && cg_good_have(a, game, d, &room) >= n;
}

/* "supply" (code 25): `word` changed by `delta` (the walk's roll).  Nothing where the game does not keep it. */
static void cg_supply_any(const ce_adapter *a, int game, const char *word, int delta) {
    const cg_good_def *d = cg_good(game, word);
    if (d != NULL) {
        int done = cg_good_change(a, game, d, delta);
        if (done != 0) {
            cg_after_line(done > 0 ? "supply+" : "supply-", word, done);
        }
    }
}

/* "trade" (code 41): `give` n and get m of `get` ("give,get"), all or nothing: nothing when the village has less
   than n, when the game keeps either good not, or when the village has no room for any of what it gets. */
static void cg_trade(const ce_adapter *a, int game, const char *words, int n, int m) {
    char give[32], *comma;
    const cg_good_def *dg, *dt;
    int room_g, room_t;
    lstrcpynA(give, words, sizeof give);
    comma = give;
    while (*comma != '\0' && *comma != ',') {
        ++comma;
    }
    if (*comma != ',') {
        return;
    }
    *comma = '\0';
    dg = cg_good(game, give);
    dt = cg_good(game, comma + 1);
    if (dg == NULL || dt == NULL || dg == dt || cg_good_have(a, game, dg, &room_g) < n
        || cg_good_have(a, game, dt, &room_t) < 0 || room_t <= 0) {
        return;
    }
    if (cg_good_change(a, game, dg, -n) == -n) {
        int got = cg_good_change(a, game, dt, m);
        cg_after_line("trade_give", give, n);
        if (got > 0) {
            cg_after_line("trade_get", comma + 1, got);
        }
    }
}

/* ---- 40. Group behaviours ------------------------------------------------------------------------------------ */

enum { CGA_ALL = 0, CGA_CHILDREN, CGA_ADULTS, CGA_ELDERS };

typedef struct {
    const char *kind;
    const char *words[6];          /* each game's own action (story_c1.inc .. story_c5.inc labels); "" = none */
    unsigned char ages;            /* who takes part when the whole village is asked */
    const char *listen[6];         /* stories: the children's action (the elders tell) */
} cg_group_def;

static const cg_group_def CG_GROUPS[] = {
    { "relax", { "", "Relaxing", "Relaxing", "Relaxing", "Relaxing", "Relaxing" }, CGA_ALL, { 0 } },
    { "swim", { "", "Going swimming", "Going swimming", "Going swimming", "Going swimming", "Going swimming" },
      CGA_ALL, { 0 } },
    { "dance", { "", "Dancing", "Dancing", "Dancing", "Dancing (another dance)", "Dancing" }, CGA_ALL, { 0 } },
    { "pray", { "", "Honoring the Dead", "Reflecting", "Honoring the guiding hand", "Honoring the guiding hand",
                "Praising" }, CGA_ALL, { 0 } },
    { "celebrate", { "", "Celebrating", "Celebrating (a new hut, first hut place) [Old Friends]", "Celebrating",
                     "Celebrating", "Celebrating" }, CGA_ALL, { 0 } },
    { "pond", { "", "Enjoying the lagoon", "Enjoying the pond", "Cooling feet in stream", "Enjoying the pond",
                "Enjoying the lake" }, CGA_ALL, { 0 } },
    { "play", { "", "Chasing butterflies", "Playing in the very narrow stream (children)", "Playing (children)",
                "Playing in puddles (children)", "Playing with butterflies!" }, CGA_CHILDREN, { 0 } },
    { "stories", { "", "Sitting", "Telling a story (Parenting practice)", "Telling a story (Parenting practice)",
                   "Telling a story", "Telling a story" }, CGA_ELDERS,
      { "", "Sitting", "Listening to a story", "Listening to a story (children)", "Listening to a story (children)",
        "Listening to a story (children)" } },
    /* Songs, chants and speeches (the owner: the song itself is the event's words; the villagers visibly take part
       through each game's closest real action). */
    { "song", { "", "Celebrating", "Celebrating (a new hut, first hut place) [Old Friends]", "Celebrating",
                "Celebrating", "Praising" }, CGA_ALL, { 0 } },
    { "chant", { "", "Dancing", "Dancing (a long dance in a circle)", "Performing ceremonial dance",
                 "Dancing [The Phosphorescent Fungi]", "Honoring" }, CGA_ALL, { 0 } },
    { "speech", { "", "Celebrating", "Celebrating (a new hut, first hut place) [Old Friends]",
                  "Attending lecture (no lesson) [The Chief's Address]", "Celebrating", "Honoring the guiding hand" },
      CGA_ALL, { 0 } },
    { "sick", { 0 }, CGA_ALL, { 0 } },
    { "cure", { 0 }, CGA_ALL, { 0 } },
};
#define CG_GROUP_COUNT ((int)(sizeof CG_GROUPS / sizeof CG_GROUPS[0]))
#define CG_ELDER_YEARS 55

static const cg_group_def *cg_group_def_of(const char *kind) {
    int i;
    for (i = 0; kind != NULL && i < CG_GROUP_COUNT; ++i) {
        if (lstrcmpA(kind, CG_GROUPS[i].kind) == 0) {
            return &CG_GROUPS[i];
        }
    }
    return NULL;
}

static int cg_in_ages(const ce_adapter *a, const unsigned char *r, int ages);

/* ---- 42. Work rush and temporary effects (the owner, 2026-11-18) ------------------------------------------------- */

/* The work rush: each game's own job action for a skill (the adapter's labels, story_c1.inc .. story_c5.inc; ""
   none: that game's workers are left as they are), and the busy state with no skill for everyone else. */
static const char *const CG_WORK_SKILLS[6] = { "Farming", "Building", "Research", "Healing", "Parenting", "Devotion" };
static const char *const CG_WORK[6][6] = {
    /* Farming */ { "", "Foraging (Farming practice, food)", "Harvesting coconuts (Farming practice, food)",
                    "Fishing (Farming practice, food)", "Harvesting blackberries (Farming practice, food) [The Lie]",
                    "Harvesting noni (Farming practice, food)" },
    /* Building */ { "", "Fixing hut (Building practice)", "Exercising (Building practice)",
                     "Doing exercise (Building practice)", "Doing exercise (Building practice)", "" },
    /* Research */ { "", "Researching (Research practice, tech points)", "Researching (Research practice, tech points)",
                     "Researching (Research practice, tech points)", "Researching (Research practice, tech points)",
                     "Researching (Research practice, tech points)" },
    /* Healing */ { "", "Healing someone (Healing practice, cures nobody)",
                    "Healing someone (Healing practice, cures nobody)", "Studying medicine (Healing practice)", "",
                    "Health chanting (Healing practice)" },
    /* Parenting */ { "", "", "Telling a story (Parenting practice)", "Telling a story (Parenting practice)", "", "" },
    /* Devotion */ { "", "", "", "", "", "Praising" },
};
/* VV3's own "Working 'til he/she drops!" (action 0x3A); the other games' closest stock busy state, a rest. */
static const char *const CG_WORK_REST[6] = { "", "Sitting", "Sitting", "Working 'til he drops! / Working 'til she drops!",
                                             "Needs to sit down", "Needs to sit down" };

static int cg_work_skill(const char *kind) {
    int k;
    if (!cg_prefix(kind, "work:")) {
        return -1;
    }
    for (k = 0; k < 6; ++k) {
        if (lstrcmpA(kind + 5, CG_WORK_SKILLS[k]) == 0) {
            return k;
        }
    }
    return -1;
}

/* Whether `kind` is a group's word: sickness, cure and a work rush are the whole village's only. */
static int cg_group_kind_ok(const char *kind, int whole_village) {
    const cg_group_def *d = cg_group_def_of(kind);
    if (cg_work_skill(kind) >= 0) {
        return whole_village;
    }
    return d != NULL && (whole_village || d->words[1] != NULL);
}

/* The job ticked on record `r`'s Details screen (CG_WORK_SKILLS index), -1 none: the preference the game's own job
   picker gives 86 times in 100 (rand(100) <= 85): A New Home [+0x3D0] 1..5 (0x439C40: 1 Farming, 2 Parenting,
   3 Research, 4 Healing, 5 Building), The Lost Children [+0x7F8] 1..5 (0x449DCD: 1 Farming, 2 Parenting, 3 Healing,
   4 Research, 5 Building), The Secret City [+0xEC0], The Tree of Life [+0x1C70], New Believers [+0x1C74] a skill
   index, -1 none (0x45985B, 0x461E4A, 0x46A575: Farming, Parenting, Healing, Research, Building, Devotion). */
static int cg_job_ticked(int game, const unsigned char *r) {
    static const signed char OLD1[6] = { -1, 0, 4, 2, 3, 1 };      /* value -> CG_WORK_SKILLS */
    static const signed char OLD2[6] = { -1, 0, 4, 3, 2, 1 };
    static const signed char LATER[6] = { 0, 4, 3, 2, 1, 5 };      /* skill index -> CG_WORK_SKILLS */
    int v;
    switch (game) {
    case 1: v = *(const int *)(r + 0x3D0); return v >= 1 && v <= 5 ? OLD1[v] : -1;
    case 2: v = *(const int *)(r + 0x7F8); return v >= 1 && v <= 5 ? OLD2[v] : -1;
    case 3: v = *(const int *)(r + 0xEC0); return v >= 0 && v <= 4 ? LATER[v] : -1;
    case 4: v = *(const int *)(r + 0x1C70); return v >= 0 && v <= 4 ? LATER[v] : -1;
    case 5: v = *(const int *)(r + 0x1C74); return v >= 0 && v <= 5 ? LATER[v] : -1;
    default: return -1;
    }
}

/* Record `r`'s highest skill (CG_WORK_SKILLS index), -1 when every skill is 0: the skill the Village screen's Action
   bar shows under "Skill" when no job is ticked (the owner, 2026-11-18: the highest number on the Details screen, a
   tie the Action bar's own pick).  The Action bar's routine, each game: A New Home 0x43B520 (from 0x41FB34) and The
   Lost Children 0x44B4D0 (from 0x429B75) read Parenting, Building, Healing, Farming, Research and keep the earlier on
   a tie (`jle`), none when all are 0; The Secret City 0x462460 (from 0x468DDE) reads Farming, Parenting, Healing,
   Research, Building, the earlier kept on a tie, none unless one is above 0; The Tree of Life 0x46AC20 (from
   0x4402EA) and New Believers 0x4755C0 (from 0x442E8B; Devotion sixth) read the same order of float skills against
   the best so far CUT TO A WHOLE NUMBER (_ftol): a skill wins when it is above that whole number, so 40.2 after 40.7
   takes over (the best is 40), while 40.0 after 40.7 does not. */
static int cg_highest_skill(const ce_adapter *a, int game, const unsigned char *r) {
    static const signed char OLD_ORDER[5] = { 4, 1, 3, 0, 2 };     /* CG_WORK_SKILLS in 0x43B520's reading order */
    static const signed char LATER_ORDER[6] = { 0, 4, 3, 2, 1, 5 };
    const signed char *order = game <= 2 ? OLD_ORDER : LATER_ORDER;
    int n = game <= 2 ? 5 : (game == 5 ? 6 : 5), i, k, best = -1, best_whole = 0;
    double best_v = 0.0;
    for (i = 0; i < n; ++i) {
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            if (lstrcmpiA(a->skill_names[k], CG_WORK_SKILLS[order[i]]) == 0) {
                const unsigned char *at = r + a->off_skills + 4u * (unsigned int)k;
                if (a->skills_float) {
                    float v = *(const float *)at;
                    if ((double)v > (double)best_whole) {
                        best_whole = (int)v;
                        best = order[i];
                    }
                } else if ((double)*(const int *)at > best_v) {
                    best_v = (double)*(const int *)at;
                    best = order[i];
                }
            }
        }
    }
    return best;
}

/* "That skill's worker" (the owner, 2026-11-18): the job ticked for it; or, with no job ticked at all, that skill
   is the villager's highest (the title the village lists it by).  Another job ticked: never, whatever its skills. */
static int cg_skill_worker(const ce_adapter *a, int game, const unsigned char *r, int skill) {
    int ticked = -1, best = -1;
    __try {
        ticked = cg_job_ticked(game, r);
        if (ticked < 0) {
            best = cg_highest_skill(a, game, r);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return ticked == skill || (ticked < 0 && best == skill);
}

/* "group" kind "work:<Skill>": every listed adult who is that skill's worker does the game's own job action for it;
   every other listed adult takes the busy state with no skill (VV3: "Working 'til he/she drops!") at the job's own
   site: the game's own job starter picks the place for each one (its first walk), as it does for each worker, and
   the busy steps are done there (the adapters' behave_at; nothing of the job is run).  Children are
   left as they are; no worker is made of anyone.  Nothing in a game with no action for the skill. */
static void cg_work_rush(const ce_adapter *a, int game, int skill, ce_result *r) {
    int work = cg_behaviour_by_words(a, CG_WORK[skill][game]), rest = cg_behaviour_by_words(a, CG_WORK_REST[game]);
    int i, pass;
    ce_result one;
    if (work < 0) {
        return;
    }
    if (!(a->caps & CAP_BEHAVIOUR)) {
        ce_refuse(r, CE_WHY_OTHER);
        return;
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    /* the workers first, so every worker's spot is taken before a busy villager's is picked (ce_site_pick) */
    for (pass = 0; pass < 2; ++pass) {
        for (i = 0; i < a->record_count && i < CE_MAX_RECORDS && cg_one.change_count < CE_MAX_CHANGES; ++i) {
            unsigned char *record = a->record(i);
            int use;
            ce_change *c;
            if (record == NULL || !a->listed(record) || cg_heathen(game, record)
                || (game == 3 && record[0xE94] != 0) || !cg_in_ages(a, record, CGA_ADULTS)) {
                continue;
            }
            use = cg_skill_worker(a, game, record, skill) ? work : rest;
            if (use < 0 || (use == work) != (pass == 0)) {
                continue;
            }
            c = &cg_one.changes[cg_one.change_count++];
            ce_change_init(c);
            c->index = i;
            c->fingerprint = ce_identity(a, record);
            c->behaviour = use;
        }
    }
    if (cg_one.change_count > 0) {
        ce_site_count = 0;
        ce_site_job = work;             /* everyone else takes the busy state at the job's own site (behave_at) */
        ce_apply(a, &cg_one, &one);
        ce_site_job = -1;
        cg_merge_result(r, &one);
    }
}

/* The sickness field each game's own sickness writes (sc_sick's). */
static void cg_set_sick(int game, unsigned char *r, int sick) {
    switch (game) {
    case 1: *(int *)(r + 0x354) = sick; break;
    case 2: *(int *)(r + 0x53C) = sick; break;
    case 3: r[0xE89] = (unsigned char)sick; break;
    default: r[0x1C48] = (unsigned char)sick; break;
    }
}

static int cg_is_sick(int game, const unsigned char *r) {
    switch (game) {
    case 1: return *(const int *)(r + 0x354) != 0;
    case 2: return *(const int *)(r + 0x53C) != 0;
    case 3: return r[0xE89] != 0;
    default: return r[0x1C48] != 0;
    }
}

/* Whether record `r` is in age group `ages`. */
static int cg_in_ages(const ce_adapter *a, const unsigned char *r, int ages) {
    int years = ce_age(a, r) / 20;
    switch (ages) {
    case CGA_CHILDREN: return years < 14;
    case CGA_ADULTS: return years >= 14;
    case CGA_ELDERS: return years >= CG_ELDER_YEARS;
    default: return 1;
    }
}

/* "group" (code 42): the kind's action for every living, listed villager of its ages (`only` >= 0: that record
   alone, any age), or the sickness: `percent` of the villagers no harm may reach not (rounded up, at least one),
   or every one cured. */
static void cg_group_fx(const ce_adapter *a, int game, const char *kind, int only, int percent, ce_result *r) {
    const cg_group_def *d = cg_group_def_of(kind);
    int i, behaviour = -1, listen = -1, sick = d != NULL && lstrcmpA(d->kind, "sick") == 0;
    int cure = d != NULL && lstrcmpA(d->kind, "cure") == 0, want = 0, n = 0;
    int pool[CE_MAX_RECORDS];
    ce_result one;
    if (game < 1 || game > 5) {
        return;
    }
    if (cg_work_skill(kind) >= 0) {
        cg_work_rush(a, game, cg_work_skill(kind), r);
        cg_after_line("group_work", kind + 5, 0);      /* "work:Building" */
        return;
    }
    if (d == NULL) {
        return;
    }
    if (!sick && !cure) {
        behaviour = cg_behaviour_by_words(a, d->words[game]);
        listen = d->listen[game] != NULL ? cg_behaviour_by_words(a, d->listen[game]) : -1;
        if (behaviour < 0 && listen < 0) {
            return;
        }
        if (!(a->caps & CAP_BEHAVIOUR)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
    }
    memset(&cg_one, 0, sizeof cg_one);
    cg_one.game = game;
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        unsigned char *record = a->record(i);
        int use = behaviour;
        if (record == NULL || !a->listed(record) || cg_heathen(game, record) || (game == 3 && record[0xE94] != 0)
            || (only >= 0 && i != only)) {
            continue;
        }
        if (cure) {
            __try {
                cg_set_sick(game, record, 0);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
            ++want;                    /* counted: the line says the village is cured */
            continue;
        }
        if (sick) {
            if (!cg_is_sick(game, record) && !cg_protected(a, game, record) && !cg_never_harmed(game, record)) {
                pool[n++] = i;
            }
            continue;
        }
        if (only < 0 && !cg_in_ages(a, record, d->ages)) {
            use = listen >= 0 && cg_in_ages(a, record, CGA_CHILDREN) ? listen : -1;
        }
        if (use < 0 || cg_one.change_count >= CE_MAX_CHANGES) {
            continue;
        }
        {
            ce_change *c = &cg_one.changes[cg_one.change_count++];
            ce_change_init(c);
            c->index = i;
            c->fingerprint = ce_identity(a, record);
            c->behaviour = use;
        }
    }
    if (sick && n > 0) {
        if (!(a->caps & CAP_SICK)) {
            ce_refuse(r, CE_WHY_OTHER);
            return;
        }
        int made = 0;
        want = (n * percent + 99) / 100;
        while (want-- > 0 && n > 0) {
            int k = ce_random_below(a, n);
            a->sicken(pool[k]);
            pool[k] = pool[--n];
            ++made;
        }
        cg_after_line(made == 1 ? "group_sick1" : "group_sick", "", made);
        return;
    }
    if (cure) {
        if (want > 0) {
            cg_after_line("group_cure", "", 0);
        }
        return;
    }
    if (cg_one.change_count > 0) {
        char key[32];
        ce_apply(a, &cg_one, &one);
        cg_merge_result(r, &one);
        wsprintfA(key, only < 0 ? "group_%s" : "group1_%s", d->kind);
        cg_after_line(key, only >= 0 ? (const char *)a->record(only) + a->off_name : "", 0);
    }
}

/* ---- 41. The village ----------------------------------------------------------------------------------------- */

static int sc_clock(int game, unsigned int *now, unsigned int **timer);   /* story_collection.inc */

/* The next island event sooner (`hours` below 0) or later, on each game's own island timer (sc_clock).  Sooner is
   The Lost Children's Gong of Wonder "luck" (0x44ECE1: the timer set to now + 0x3C): the next event a minute from
   now, never later than it was.  Later: `hours` more, never beyond now + the game's own longest gap after an event
   (A New Home 23 h, rand(12) + 12; The Lost Children 19 h, rand(10) + 10; the later three 15 h, rand(8) + 8).
   Which event comes and its odds are never touched: only when. */
#define CG_GONG_SOONER 60u
/* The change the last event_timer effect made, for the outcome line (story_graph's automatic text): 0 none, -1 "soon"
   (the Gong's minute), else the hours it came later after the cap. */
static int cg_timer_applied_hours;
static void cg_event_timer(int game, int hours) {
    static const int LONGEST[6] = { 0, 23, 19, 15, 15, 15 };
    unsigned int now = 0, *timer = NULL;
    long long due;
    char line[96];
    cg_timer_applied_hours = 0;
    if (hours == 0 || game < 1 || game > 5 || !sc_clock(game, &now, &timer) || timer == NULL) {
        return;
    }
    __try {
        if (hours < 0) {
            due = (long long)now + CG_GONG_SOONER;
            if (due > (long long)*timer) {
                due = *timer;                       /* already sooner than that: unchanged */
            }
        } else {
            due = (long long)*timer + (long long)hours * 3600;
            if (due > (long long)now + (long long)LONGEST[game] * 3600) {
                due = (long long)now + (long long)LONGEST[game] * 3600;
            }
            if (due < (long long)*timer) {
                due = *timer;                       /* a later never brings it sooner */
            }
        }
        if (due < (long long)now) {
            due = now;
        }
        if (due > 0xFFFFFFFFll) {
            due = 0xFFFFFFFFll;
        }
        if ((unsigned int)due == *timer) {
            return;
        }
        cg_timer_applied_hours = hours < 0 ? -1 : (int)((due - (long long)*timer) / 3600);
        *timer = (unsigned int)due;
        if (cg_timer_applied_hours < 0) {
            cg_after_line("timer_soon", "", 0);
        } else if (cg_timer_applied_hours > 0) {
            cg_after_line(cg_timer_applied_hours == 1 ? "timer_later1" : "timer_later", "", cg_timer_applied_hours);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    wsprintfA(line, "  The next island event: %s\n", hours < 0 ? "soon" : "later");
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}

/* Each game's tech areas: the level's address (VV1/VV2 a world offset), and the lowest level an event leaves. */
typedef struct {
    const char *name;
    unsigned int at;
    unsigned char least;
} cg_area_def;

static const cg_area_def CG_AREAS1[] = { { "Spirituality", 0xA2BC, 1 }, { "Science", 0xA2C4, 1 },
    { "Construction", 0xA2CC, 1 }, { "Medicine", 0xA2D4, 1 }, { "Fertility", 0xA2DC, 1 }, { "Farming", 0xA2E4, 1 } };
static const cg_area_def CG_AREAS2[] = { { "Culture", 0x2EA74, 1 }, { "Science", 0x2EA7C, 1 },
    { "Engineering", 0x2EA84, 1 }, { "Medicine", 0x2EA8C, 1 }, { "Exploration", 0x2EA94, 1 },
    { "Farming", 0x2EA9C, 1 } };
/* VV3: Nature and Magic start at 0 and the village picks one; an event never moves either from 0 (it would choose
   the faction) nor back to 0. */
static const cg_area_def CG_AREAS3[] = { { "Science", 0x582618, 1 }, { "Medicine", 0x58261C, 1 },
    { "Alchemy", 0x582620, 1 }, { "Restoration", 0x582624, 1 }, { "Leadership", 0x582628, 1 },
    { "Nature", 0x58262C, 1 }, { "Magic", 0x582630, 1 } };
static const cg_area_def CG_AREAS4[] = { { "Science", 0x4D6F5C, 1 }, { "Medicine", 0x4D6F60, 1 },
    { "Learning", 0x4D6F64, 1 }, { "Construction", 0x4D6F68, 1 }, { "Food Mastery", 0x4D6F6C, 1 },
    { "Dendrology", 0x4D6F70, 1 } };
static const cg_area_def CG_AREAS5[] = { { "Science", 0x51D5CC, 1 }, { "Medicine", 0x51D5D0, 1 },
    { "Learning", 0x51D5D4, 1 }, { "Construction", 0x51D5D8, 1 }, { "Food Mastery", 0x51D5DC, 1 },
    { "Spirituality", 0x51D5E0, 1 } };
#define CG_LEVEL_TOP 3

static const cg_area_def *cg_areas(int game, int *n) {
    switch (game) {
    case 1: *n = 6; return CG_AREAS1;
    case 2: *n = 6; return CG_AREAS2;
    case 3: *n = 7; return CG_AREAS3;
    case 4: *n = 6; return CG_AREAS4;
    case 5: *n = 6; return CG_AREAS5;
    default: *n = 0; return NULL;
    }
}

static int *cg_level_at(int game, const cg_area_def *d) {
    unsigned char *world = game == 1 ? VV1_WORLD() : game == 2 ? VV2_WORLD() : NULL;
    if (game <= 2) {
        return world != NULL ? (int *)(world + d->at) : NULL;
    }
    return (int *)(uintptr_t)d->at;
}

/* Tech area `which` ("" = any that can move) up (+1) or down (-1), within least..3: up by the game's own raise
   (The Secret City 0x426FD0, The Tree of Life 0x41E1D0, New Believers 0x423610 with no trophy), as the game's own
   island events and purchases do; A New Home and The Lost Children by a plain write, as their island events do.
   Down is a plain write (no game lowers a level; every reader reads it live). */
static void cg_tech_level(const ce_adapter *a, int game, const char *which, int step) {
    const cg_area_def *areas;
    int n, i, pick[8], m = 0, k, *level, before;
    char line[96];
    areas = cg_areas(game, &n);
    if (areas == NULL || (step != 1 && step != -1)) {
        return;
    }
    __try {
        for (i = 0; i < n; ++i) {
            int *at = cg_level_at(game, &areas[i]);
            int now = at != NULL ? *at : 0;
            if ((which[0] == '\0' || lstrcmpiA(which, areas[i].name) == 0) && at != NULL && now >= areas[i].least
                && (step > 0 ? now < CG_LEVEL_TOP : now > areas[i].least)) {
                pick[m++] = i;
            }
        }
        if (m == 0) {
            return;
        }
        k = pick[ce_random_below(a, m)];
        level = cg_level_at(game, &areas[k]);
        before = *level;
        if (step < 0 || game <= 2) {
            *level = before + step;
        } else if (game == 3) {
            TC1(0x426FD0u, 0x582618u, k);
        } else if (game == 4) {
            TC1(0x41E1D0u, 0x4D6F5Cu, k);
        } else {
            TC2(0x423610u, 0x51D5CCu, k, 0);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if (*level != before) {
        cg_after_line(*level > before ? "level_up" : "level_down", areas[k].name, *level);
        wsprintfA(line, "  Tech level (%s): %d -> %d\n", areas[k].name, before, *level);
        if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
            lstrcatA(cg_extra_lines, line);
        }
    }
}

/* The weather words and each game's type for them (-1: the game has none).  A New Home and The Lost Children have
   no weather at all. */
static const char *const CG_WEATHER_WORDS[5] = { "clear", "sun", "rain", "storm", "fog" };
static const signed char CG_WEATHER_TYPE[6][5] = {
    { -1, -1, -1, -1, -1 }, { -1, -1, -1, -1, -1 }, { -1, -1, -1, -1, -1 },
    { 0, -1, 2, 3, 4 },            /* The Secret City 0x41FB40 (type 1 is only the rain's particles) */
    { 0, 1, 2, 3, 4 },             /* The Tree of Life 0x46BC30 */
    { 0, 1, 2, 5, 4 },             /* New Believers 0x477060 (3 is a light rain) */
};

static int cg_weather_word(const char *word) {
    int i;
    for (i = 0; word != NULL && i < 5; ++i) {
        if (lstrcmpA(word, CG_WEATHER_WORDS[i]) == 0) {
            return i;
        }
    }
    return -1;
}

/* The game's own weather starter, as its island events call it (the type, 0). */
static void cg_weather(int game, const char *word) {
    int w = cg_weather_word(word), type;
    char line[64];
    if (w < 0 || game < 1 || game > 5 || (type = CG_WEATHER_TYPE[game][w]) < 0) {
        return;
    }
    __try {
#ifdef VVFP_TEST
        test_graph_weather = type;
        if (test_graph_weather_call == 0) {
            goto logged;
        }
#endif
        if (game == 3) {
            TC2(0x41FB40u, 0x4B86C4u, type, 0);
        } else if (game == 4) {
            TC2(0x46BC30u, 0x6C461Cu, type, 0);
        } else {
            TC2(0x477060u, 0x718EA0u, type, 0);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
#ifdef VVFP_TEST
logged:
#endif
    {
        char key[24];
        wsprintfA(key, "weather_%s", CG_WEATHER_WORDS[w]);
        cg_after_line(key, "", 0);
    }
    wsprintfA(line, "  Weather: %s\n", CG_WEATHER_WORDS[w]);
    if (lstrlenA(cg_extra_lines) + lstrlenA(line) < (int)sizeof cg_extra_lines) {
        lstrcatA(cg_extra_lines, line);
    }
}


/* Whether `s` is a "village" effect's word ("event_timer", "tech_level" or "tech_level:<area>", "construction",
   "weather:<word>"), and the a..b it allows. */
static int cg_village_ok(const char *s, int a, int b) {
    if (lstrcmpA(s, "event_timer") == 0) {
        return a <= b && a >= -72 && b <= 72 && (b < 0 || a > 0);
    }
    /* "construction" and "spawn": words only (the owner's final list, 2026-11-18): refused. */
    if (lstrcmpA(s, "tech_level") == 0 || (cg_prefix(s, "tech_level:") && s[11] != '\0')) {
        return (a == 1 || a == -1) && b == a;
    }
    if (cg_prefix(s, "weather:")) {
        return cg_weather_word(s + 8) >= 0 && a == 0 && b == 0;
    }
    return 0;
}

/* "village" (code 43) with its roll `va`.  Only the words cg_village_ok lets load do anything: "construction" and
   "spawn" (words only) and any other word change nothing here, whatever reaches this. */
static void cg_village_fx(const ce_adapter *a, int game, const char *s, int va) {
    if (lstrcmpA(s, "event_timer") == 0) {
        cg_event_timer(game, va);
    } else if (lstrcmpA(s, "tech_level") == 0 || (cg_prefix(s, "tech_level:") && s[11] != '\0')) {
        cg_tech_level(a, game, s[10] == ':' ? s + 11 : "", va);
    } else if (cg_prefix(s, "weather:")) {
        cg_weather(game, s + 8);
    }
}
