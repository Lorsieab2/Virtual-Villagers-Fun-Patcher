/* Pick Island Event: outcomes.  Included by vvfp_story_upgrades.c.

   The owner: "In general I want all possible outcomes for events that have
   them to be possible."  Each offered event can carry settings (the tables
   in story_tables.h, generated from scripts/story_island_outcomes.py): a
   result, an amount, who a per-villager roll hits, which villager the event
   is about, the sex of each baby.  Each setting names the game's own random
   rolls that decide it -- the `call rand` instructions ("sites") -- and the
   value each roll must return for the chosen result.  The game's own code
   then makes the result, exactly as it does when its random generator
   happens to return that value; nothing about the event is emulated.

   HOW A ROLL IS ANSWERED.  Every listed site's `E8 rel32` call to the game's
   rand(bound) is pointed at oc_rand_stub, which hands the registers of the
   call to oc_answer.  oc_answer returns the game's own rand(bound) unless an
   armed pick holds a setting for that site, and the setting's conditions
   hold right now:

   * phase "select": the roll runs before the event is presented (A New
     Home's crate and The Lost Children's sack setup, before the variant
     roll; the condition method of a Secret City / Tree of Life / New
     Believers event, which the selector asks on every pass).  Answered on
     every call from the moment the pick is armed until it is applied,
     refused or lapses, so the last call -- the one the event keeps -- has
     the chosen value.
   * phase "build": after the pick is delivered and before the player's OK
     (the popup's text methods, which the popup calls at build time and again
     at the click).  Answered on every call while the delivered pick waits.
   * phase "apply": inside the event's own resolve, which the OK button runs.
     Answered only while that very event is being applied.
   * a "scope call": a site in a routine that other code reaches too (the
     weather setter, a skill helper, the villager picker, the sweep loop) is
     answered only while the listed call -- in the event's own code -- is in
     progress (oc_scope_stub brackets it).
   * a "branch": a setting for one choice of a two-choice event is used only
     when that choice was clicked (known at the apply).

   The armed outcome ends when the event's apply returns (and it is never
   used again), when the pick is refused or lapses, and when the game starts
   choosing another island event while an old delivered outcome is still
   held.  So no forced value ever reaches a natural event or another event
   that shares a routine. */

#define OC_RANDOM (-1)
#define OC_MAX_CONTROLS 48
#define OC_MAX_SCOPES 96
#define OC_MAX_SITES 640
#define OC_WHO_BYTES 32               /* 256 records */

enum { OC_ENUM = 1, OC_AMOUNT = 2, OC_LOOP = 3, OC_VICTIM = 4 };
enum { OC_SELECT = 1, OC_BUILD = 2, OC_APPLY = 3 };
enum { OC_LOOP_NOBODY = 0, OC_LOOP_EVERYONE = 1, OC_LOOP_CHOOSE = 2 };
enum { OC_IDLE = 0, OC_ARMED = 1, OC_DELIVERED = 2 };
enum { OC_ELEM_PTR = 1, OC_ELEM_INDEX = 2 };
enum { OC_SCOPE_PLAIN = 0, OC_SCOPE_APPLY = 1, OC_SCOPE_GONG = 2 };
#define OC_GONG_SLOT 1000                /* The Lost Children's Gong of Wonder */

/* The player's settings for one pick: per control, OC_RANDOM or the choice
   (an option index, an amount value, an OC_LOOP_* or a record index), the
   chosen villagers of each "choose who" control, and the strength (0 = from
   the population). */
typedef struct {
    int choice[OC_MAX_CONTROLS];
    unsigned char who[OC_MAX_CONTROLS][OC_WHO_BYTES];
    int strength;
    int unlocked;                     /* deliver past a timing condition */
} oc_settings;

typedef struct {
    const oc_site *sites;
    int site_count;
    const oc_scope *scopes;
    int scope_count;
    const oc_force *forces;
    const oc_option *options;
    const oc_control *controls;
    const oc_event *events;
    int event_count;
    unsigned int rand_va;
} oc_game;

static const oc_game OC_GAMES[6] = {
    { 0 },
    { VV1_OC_SITES, VV1_OC_SITE_COUNT, VV1_OC_SCOPES, VV1_OC_SCOPE_COUNT, VV1_OC_FORCES,
      VV1_OC_OPTIONS, VV1_OC_CONTROLS, VV1_OC_EVENTS, VV1_OC_EVENT_COUNT, 0x402F10u },
    { VV2_OC_SITES, VV2_OC_SITE_COUNT, VV2_OC_SCOPES, VV2_OC_SCOPE_COUNT, VV2_OC_FORCES,
      VV2_OC_OPTIONS, VV2_OC_CONTROLS, VV2_OC_EVENTS, VV2_OC_EVENT_COUNT, 0x4031A0u },
    { VV3_OC_SITES, VV3_OC_SITE_COUNT, VV3_OC_SCOPES, VV3_OC_SCOPE_COUNT, VV3_OC_FORCES,
      VV3_OC_OPTIONS, VV3_OC_CONTROLS, VV3_OC_EVENTS, VV3_OC_EVENT_COUNT, 0x4032D0u },
    { VV4_OC_SITES, VV4_OC_SITE_COUNT, VV4_OC_SCOPES, VV4_OC_SCOPE_COUNT, VV4_OC_FORCES,
      VV4_OC_OPTIONS, VV4_OC_CONTROLS, VV4_OC_EVENTS, VV4_OC_EVENT_COUNT, 0x4036D0u },
    { VV5_OC_SITES, VV5_OC_SITE_COUNT, VV5_OC_SCOPES, VV5_OC_SCOPE_COUNT, VV5_OC_FORCES,
      VV5_OC_OPTIONS, VV5_OC_CONTROLS, VV5_OC_EVENTS, VV5_OC_EVENT_COUNT, 0x403660u },
};

/* An armed outcome.  There are two, independent of each other: the Pick
   Island Event's (`oc`, one at a time like the pick) and The Lost
   Children's Pick Gong of Wonder Outcome (`oc_gong`). */
typedef struct {
    int state;                        /* OC_IDLE / OC_ARMED / OC_DELIVERED */
    int game;
    const oc_event *event;
    oc_settings set;
    void *object;                     /* VV3-VV5: the delivered event object */
    int branch;                       /* the clicked choice, -1 while unknown */
    int in_apply;                     /* the event's own apply is running */
    int victim_missed;                /* a chosen villager was not a candidate */
    DWORD tick;                       /* when it was armed (the gong's lapse) */
    unsigned char calls[OC_MAX_SITES];  /* each site's calls during this apply */
    int save_slot;                    /* the save slot it was armed in (the gong) */
} oc_arm_state;

static oc_arm_state oc;
static oc_arm_state oc_gong;
static int oc_scope_depth[OC_MAX_SCOPES];   /* scope calls in progress */

#ifdef VVFP_TEST
struct vvfp_story_outcome_stats {
    int forced;          /* rolls answered with a chosen value */
    int passed;          /* rolls handed to the game's own generator */
    int disarmed;        /* armed outcomes ended */
    int victim_missed;   /* chosen villagers that were not candidates */
};
__declspec(dllexport) struct vvfp_story_outcome_stats VvfpStoryOutcomeStats = { 0 };
#define OC_COUNT(field) (++VvfpStoryOutcomeStats.field)
#else
#define OC_COUNT(field) ((void)0)
#endif

typedef int (__cdecl *oc_rand_fn)(int bound);

static const oc_event *oc_find_event(int game, int slot) {
    const oc_game *g = &OC_GAMES[game];
    int i;
    for (i = 0; i < g->event_count; ++i) {
        if (g->events[i].slot == slot) {
            return &g->events[i];
        }
    }
    return NULL;
}

static void oc_arm_clear(oc_arm_state *a) {
    if (a->state != OC_IDLE) {
        OC_COUNT(disarmed);
    }
    a->state = OC_IDLE;
    a->event = NULL;
    a->object = NULL;
    a->branch = -1;
    a->in_apply = 0;
}

static void oc_disarm(void) {
    oc_arm_clear(&oc);
}

/* Whether any setting is not "Random". */
static int oc_settings_any(const oc_event *e, const oc_settings *s) {
    int i;
    if (e == NULL || s == NULL) {
        return 0;
    }
    if (s->strength != 0 || s->unlocked) {
        return 1;
    }
    for (i = 0; i < e->control_count && i < OC_MAX_CONTROLS; ++i) {
        if (s->choice[i] != OC_RANDOM) {
            return 1;
        }
    }
    return 0;
}

static void oc_arm_set(oc_arm_state *a, int game, int slot, const oc_settings *s) {
    oc_arm_clear(a);
    a->event = oc_find_event(game, slot);
    if (s == NULL || !oc_settings_any(a->event, s)) {
        a->event = NULL;
        return;
    }
    a->set = *s;
    a->game = game;
    a->state = OC_ARMED;
    a->tick = STORY_TICK();
    a->victim_missed = 0;
}

/* Arms the settings for the pick of `slot` (called with the pick). */
static void oc_arm(int game, int slot, const oc_settings *s) {
    oc_arm_set(&oc, game, slot, s);
}

static int oc_armed_for(int game) {
    return oc.state != OC_IDLE && oc.game == game;
}

/* The pick of this game was delivered (the game is running that event). */
static void oc_delivered(int game, void *object) {
    if (oc.state == OC_ARMED && oc.game == game) {
        oc.state = OC_DELIVERED;
        oc.object = object;
        oc.branch = -1;
    }
}

/* The game starts choosing an island event: an outcome delivered earlier
   and still held is stale (its event is over), so it ends here. */
static void oc_new_choice(int game) {
    if (oc.state == OC_DELIVERED && oc.game == game && !oc.in_apply) {
        oc_disarm();
    }
}

/* The pick lapsed (ten minutes undelivered). */
static void oc_lapsed(void) {
    if (oc.state == OC_ARMED) {
        oc_disarm();
    }
}

/* The picked event's own condition did not hold: the game runs another. */
static void oc_refused(int game) {
    if (oc.game == game && oc.state != OC_IDLE) {
        oc_disarm();
    }
}

/* A New Home / The Lost Children: the family's event roll is made again
   after the pick was delivered -- the delivered event's own condition
   failed and the game rolls another, so the outcome ends. */
static void oc_reroll(int game) {
    if (oc.state == OC_DELIVERED && oc.game == game && !oc.in_apply) {
        oc_disarm();
    }
}

/* A New Home / The Lost Children: the single-result island events run
   wholly inside the island event's chooser call (the Custom Island Event's
   delivery site, c1_choose / c2_choose): the pick is delivered by the case
   roll inside it, the event applied, and the outcome ends when it returns. */
static void oc_apply_open(oc_arm_state *a) {
    a->in_apply = 1;
    memset(a->calls, 0, sizeof a->calls);
}

static void oc_island_begin(int game) {
    if (oc.state != OC_IDLE && oc.game == game) {
        oc_apply_open(&oc);
    }
}

static void oc_island_end(int game) {
    if (oc.game == game && oc.in_apply) {
        oc.in_apply = 0;
        if (oc.state == OC_DELIVERED) {
            oc_disarm();
        }
    }
}

/* The strength an armed island-family pick sets (A New Home / The Lost
   Children), or 0 for the game's own (from the population). */
static int oc_strength(int game) {
    if (oc.state == OC_IDLE || oc.game != game || oc.event == NULL || !oc.event->strength) {
        return 0;
    }
    return oc.set.strength;
}

/* A New Home: the strength an armed island-event pick sets, for the island
   chooser call about to run (the case roll inside it delivers the pick) --
   only while that pick's own condition holds, so the forced magnitude can
   never reach another event the chooser would roll instead. */
static int vv1_island_strength(void) {
    if (oc.state != OC_ARMED || oc.game != 1 || oc.event == NULL || pick_slot < 0 || pick_game != 1
        || pick_event == NULL || oc.event->slot != pick_slot
        || VV1_SLOT_FAMILY(pick_slot) != VV1_FAMILY_ISLAND || !vv1_possible(pick_event)) {
        return 0;
    }
    return oc_strength(1);
}

/* Whether `slot` may be picked although its condition fails (a timing or
   story condition proven safe to pass, or a developer-dead event proven to
   work). */
static int oc_event_unlockable(int game, int slot) {
    const oc_event *e = oc_find_event(game, slot);
    return e != NULL && e->unlock;
}

/* Whether the armed pick of `slot` may be delivered past its timing
   condition (the player chose it although it is normally not possible). */
static int oc_unlocked(int game, int slot) {
    return oc.state == OC_ARMED && oc.game == game && oc.event != NULL && oc.event->slot == slot
           && oc.event->unlock && oc.set.unlocked;
}

/* ---- Answering a roll ------------------------------------------------------ */

static int oc_site_index(const oc_game *g, unsigned int va) {
    int lo = 0;
    int hi = g->site_count - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (g->sites[mid].va == va) {
            return mid;
        }
        if (g->sites[mid].va < va) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return -1;
}

/* pushad image: edi, esi, ebp, esp, ebx, edx, ecx, eax; then the return
   address and the stack arguments of the call. */
static unsigned int oc_reg(const unsigned int *regs, int reg) {
    static const int at[8] = { 7, 6, 5, 4, 1, 0, 2, 3 };  /* eax ecx edx ebx esi edi ebp esp */
    if (reg == 7) {
        return regs[3] + 4u;          /* ESP at the call instruction */
    }
    return regs[at[reg]];
}

/* reg + disp, or dword [reg + mem_disp] + disp (mem). */
static unsigned int oc_where(const unsigned int *regs, int reg, int mem, int mem_disp, int disp) {
    unsigned int at = oc_reg(regs, reg);
    if (mem) {
        unsigned int cell = at + (unsigned int)mem_disp;
        if (!mem_readable(cell, 4)) {
            return 0;
        }
        at = read_u32(cell);
    }
    return at + (unsigned int)disp;
}

static int oc_record_index(int game, unsigned int record) {
    return story_record_index(game, (const unsigned char *)(uintptr_t)record);
}

static int oc_who_has(const unsigned char *who, int index) {
    return index >= 0 && index < OC_WHO_BYTES * 8 && (who[index >> 3] & (1u << (index & 7))) != 0;
}

/* Whether control `c` of arm `a` may answer now. */
static int oc_control_live(const oc_arm_state *a, const oc_control *c) {
    if (c->branch >= 0 && a->branch >= 0 && c->branch != a->branch) {
        return 0;
    }
    if (c->scope >= 0) {
        int in_scope = c->scope < OC_MAX_SCOPES && oc_scope_depth[c->scope] > 0;
        if (!in_scope && c->scope2 >= 0) {
            in_scope = c->scope2 < OC_MAX_SCOPES && oc_scope_depth[c->scope2] > 0;
        }
        if (!in_scope) {
            return 0;
        }
    }
    switch (c->phase) {
    case OC_SELECT:
        return a->state == OC_ARMED || a->state == OC_DELIVERED;
    case OC_BUILD:
        return a->state == OC_DELIVERED;
    case OC_APPLY:
        return a->state == OC_DELIVERED && a->in_apply;
    default:
        return 0;
    }
}

/* Whether control `c` answers site index `si` (its site or an extra one,
   and, for a control of the n-th call, only that call of the apply). */
static int oc_control_site(const oc_arm_state *a, const oc_game *g, const oc_control *c, int si) {
    int hit = c->site == si;
    int i;
    for (i = 0; !hit && i < c->xsite_count; ++i) {
        hit = g->forces[c->xsite_first + i].site == si;
    }
    if (!hit) {
        return 0;
    }
    return c->occurrence == 0 || (si < OC_MAX_SITES && a->calls[si] == c->occurrence);
}

/* The value control `c` (setting `choice`) gives the roll at site index
   `si`, or -1 when it has none. */
static int oc_value(oc_arm_state *a, const oc_game *g, int ci, const oc_control *c, int si,
                    int choice, const unsigned int *regs, int bound) {
    int i;
    switch (c->kind) {
    case OC_ENUM: {
        const oc_option *o;
        if (choice < 0 || choice >= c->option_count) {
            return -1;
        }
        if (c->occurrence != 0 && !(si < OC_MAX_SITES && a->calls[si] == c->occurrence)) {
            return -1;
        }
        o = &g->options[c->option_first + choice];
        for (i = 0; i < o->force_count; ++i) {
            const oc_force *f = &g->forces[o->force_first + i];
            if (f->site == si) {
                return f->value;
            }
        }
        return -1;
    }
    case OC_AMOUNT:
        return oc_control_site(a, g, c, si) ? choice : -1;
    case OC_LOOP:
        if (!oc_control_site(a, g, c, si)) {
            return -1;
        }
        if (choice == OC_LOOP_NOBODY) {
            return c->nobody;
        }
        if (choice == OC_LOOP_EVERYONE) {
            return c->everyone;
        }
        if (choice == OC_LOOP_CHOOSE && c->reg >= 0) {
            int index = oc_record_index(a->game, oc_where(regs, c->reg, c->mem, c->mem_disp, c->disp));
            return oc_who_has(a->set.who[ci], index) ? c->everyone : c->nobody;
        }
        return -1;
    case OC_VICTIM: {
        unsigned int base;
        if (!oc_control_site(a, g, c, si) || choice < 0) {
            return -1;
        }
        base = oc_where(regs, c->reg, c->mem, c->mem_disp, c->disp);
        for (i = 0; i < bound; ++i) {
            unsigned int cell = base + (unsigned int)(i * c->elem_size);
            unsigned int element;
            int index;
            if (!mem_readable(cell, 4)) {
                break;
            }
            element = read_u32(cell);
            index = c->elem == OC_ELEM_INDEX ? (int)element
                                             : oc_record_index(a->game, element + (unsigned int)c->elem_disp);
            if (index == choice) {
                return i;
            }
        }
        a->victim_missed = 1;
        OC_COUNT(victim_missed);
        return -1;
    }
    default:
        return -1;
    }
}

/* The value arm `a` gives site `si` of `game`, or -1. */
static int oc_arm_value(oc_arm_state *a, int game, int si, const unsigned int *regs, int bound) {
    const oc_game *g = &OC_GAMES[game];
    int i;
    if (a->state == OC_IDLE || a->game != game || a->event == NULL) {
        return -1;
    }
    if (a->in_apply && si < OC_MAX_SITES && a->calls[si] < 255) {
        ++a->calls[si];               /* this call's place among the apply's calls of the site */
    }
    for (i = 0; i < a->event->control_count && i < OC_MAX_CONTROLS; ++i) {
        const oc_control *c = &g->controls[a->event->control_first + i];
        int choice = a->set.choice[i];
        int value;
        if (choice == OC_RANDOM || !oc_control_live(a, c)) {
            continue;
        }
        value = oc_value(a, g, i, c, si, choice, regs, bound);
        if (value >= 0) {
            return value;
        }
    }
    return -1;
}

static int oc_answer(const unsigned int *regs) {
    unsigned int ret = regs[8];
    int bound = (int)regs[9];
    int game;
    for (game = 1; game <= 5; ++game) {
        const oc_game *g = &OC_GAMES[game];
        int si;
        int value;
        if (g->rand_va == 0 || install_state[game] != 1) {
            continue;
        }
        si = oc_site_index(g, ret - 5u);
        if (si < 0) {
            continue;
        }
        value = oc_arm_value(&oc, game, si, regs, bound);
        if (value < 0) {
            value = oc_arm_value(&oc_gong, game, si, regs, bound);
        }
        if (value >= 0) {
            OC_COUNT(forced);
            if (bound <= 1) {
                return 0;
            }
            return value >= bound ? bound - 1 : value;
        }
        OC_COUNT(passed);
        return ((oc_rand_fn)(uintptr_t)g->rand_va)(bound);
    }
    return 0;   /* never: every redirected site is listed */
}

static int __cdecl oc_answer_cdecl(const unsigned int *regs) {
    return oc_answer(regs);
}

/* Every listed `call rand` comes here: [esp] the return address, [esp+4]
   the bound (cdecl, the caller pops it). */
__declspec(naked) static void oc_rand_stub(void) {
    __asm {
        pushad
        mov eax, esp
        push eax
        call oc_answer_cdecl
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        ret
    }
}

/* ---- Scope calls ----------------------------------------------------------- */

/* A listed call in the event's own code runs bracketed: entering it raises
   its depth (and, for the resolve call of A New Home / The Lost Children,
   opens the event's apply with the clicked choice; for the Gong of Wonder's
   use, opens the armed gong outcome), returning lowers it (and ends the
   armed outcome after the apply / the use).  The original return address is
   kept on a small stack of our own. */
#define OC_RETURN_DEPTH 16
static unsigned int oc_returns[OC_RETURN_DEPTH];
static int oc_return_scope[OC_RETURN_DEPTH];
static int oc_return_top;
static unsigned int oc_jump;

static unsigned int oc_scope_target(const oc_scope *s) {
    int rel;
    memcpy(&rel, s->expect + 1, 4);
    return s->va + 5u + (unsigned int)rel;
}

/* Returns the original callee; regs is the pushad image of the stub (the
   return address at regs[8], the callee's arguments from regs[9]). */
static unsigned int oc_scope_enter(const unsigned int *regs) {
    unsigned int ret = regs[8];
    int game;
    for (game = 1; game <= 5; ++game) {
        const oc_game *g = &OC_GAMES[game];
        int i;
        if (install_state[game] != 1) {
            continue;
        }
        for (i = 0; i < g->scope_count; ++i) {
            const oc_scope *s = &g->scopes[i];
            if (s->va + 5u != ret) {
                continue;
            }
            if (oc_return_top < OC_RETURN_DEPTH) {
                oc_returns[oc_return_top] = ret;
                oc_return_scope[oc_return_top] = game * 1024 + i;
                ++oc_return_top;
            }
            if (i < OC_MAX_SCOPES) {
                ++oc_scope_depth[i];
            }
            if (s->kind == OC_SCOPE_APPLY && oc.state == OC_DELIVERED && oc.game == game) {
                oc_apply_open(&oc);
                if (s->strength_arg >= 0 && oc_strength(game) > 0) {
                    /* the magnitude the body receives (a stack argument of this call) */
                    ((unsigned int *)regs)[9 + s->strength_arg] = (unsigned int)oc_strength(game);
                }
                if (s->choice_arg >= 0) {
                    oc.branch = (int)regs[9 + s->choice_arg] + s->choice_bias;
                } else if (s->choice_arg == -2 && mem_readable(regs[6] + (unsigned int)s->choice_off, 4)) {
                    /* the clicked choice is a field of the object (ECX) */
                    oc.branch = (int)read_u32(regs[6] + (unsigned int)s->choice_off) + s->choice_bias;
                }
            }
            if (s->kind == OC_SCOPE_GONG && oc_gong.state == OC_ARMED && oc_gong.game == game
                && STORY_TICK() - oc_gong.tick <= PICK_TIMEOUT_MS
                && story_current_slot(game) == oc_gong.save_slot) {
                oc_gong.state = OC_DELIVERED;
                oc_apply_open(&oc_gong);
            }
            return oc_scope_target(s);
        }
    }
    return 0;
}

static unsigned int oc_scope_leave(void) {
    unsigned int ret;
    int code;
    int game;
    int i;
    if (oc_return_top <= 0) {
        return 0;
    }
    --oc_return_top;
    ret = oc_returns[oc_return_top];
    code = oc_return_scope[oc_return_top];
    game = code / 1024;
    i = code % 1024;
    if (i < OC_MAX_SCOPES && oc_scope_depth[i] > 0) {
        --oc_scope_depth[i];
    }
    if (game >= 1 && game <= 5 && i < OC_GAMES[game].scope_count) {
        int kind = OC_GAMES[game].scopes[i].kind;
        if (kind == OC_SCOPE_APPLY && oc.game == game && oc.in_apply) {
            oc.in_apply = 0;
            oc_disarm();
        }
        if (kind == OC_SCOPE_GONG && oc_gong.game == game && oc_gong.in_apply) {
            oc_arm_clear(&oc_gong);     /* one use */
        }
    }
    return ret;
}

static unsigned int __cdecl oc_scope_enter_cdecl(const unsigned int *regs) {
    return oc_scope_enter(regs);
}

static unsigned int __cdecl oc_scope_leave_cdecl(void) {
    return oc_scope_leave();
}

__declspec(naked) static void oc_scope_back(void) {
    __asm {
        push eax                      /* the slot for the original return address */
        pushad
        pushfd
        call oc_scope_leave_cdecl
        mov dword ptr [esp + 36], eax
        popfd
        popad
        ret
    }
}

__declspec(naked) static void oc_scope_stub(void) {
    __asm {
        pushad
        pushfd
        lea eax, [esp + 4]
        push eax
        call oc_scope_enter_cdecl
        add esp, 4
        mov oc_jump, eax
        lea eax, oc_scope_back
        mov dword ptr [esp + 36], eax /* the callee returns to oc_scope_back */
        popfd
        popad
        jmp dword ptr [oc_jump]
    }
}

/* ---- Installing -------------------------------------------------------------

   Every outcome site and scope call must hold its stock `E8 rel32` before
   anything is written (VvfpStoryInstall writes nothing otherwise). */
static int oc_verify(int game) {
    const oc_game *g = &OC_GAMES[game];
    int i;
    if (g->scope_count > OC_MAX_SCOPES) {
        return 0;
    }
    for (i = 0; i < g->site_count; ++i) {
        if (!mem_matches(g->sites[i].va, g->sites[i].expect, 5)) {
            return 0;
        }
    }
    for (i = 0; i < g->scope_count; ++i) {
        if (!mem_matches(g->scopes[i].va, g->scopes[i].expect, 5)) {
            return 0;
        }
    }
    return 1;
}

static int oc_write_call(unsigned int va, void *target) {
    unsigned char bytes[5];
    unsigned int rel = (unsigned int)((uintptr_t)target - ((uintptr_t)va + 5));
    bytes[0] = 0xE8;
    memcpy(bytes + 1, &rel, 4);
    return mem_write(va, bytes, 5);
}

static int oc_install(int game) {
    const oc_game *g = &OC_GAMES[game];
    int i;
    for (i = 0; i < g->site_count; ++i) {
        if (!oc_write_call(g->sites[i].va, (void *)oc_rand_stub)) {
            return 0;
        }
    }
    for (i = 0; i < g->scope_count; ++i) {
        if (!oc_write_call(g->scopes[i].va, (void *)oc_scope_stub)) {
            return 0;
        }
    }
    return 1;
}

/* ---- The Secret City, The Tree of Life, New Believers: the apply ----------

   The event popup's OK handler calls the event object's apply (two-choice:
   vtable +0x2C with the clicked choice [dlg+0x830]; single result: +0x30).
   These stubs replace those calls: they open the apply of that object with
   that choice, run it, and end the armed outcome when it returns. */

static void __cdecl oc_apply_begin(void *object, int branch) {
    if (oc.state == OC_DELIVERED && object != NULL && object == oc.object) {
        oc_apply_open(&oc);
        oc.branch = branch;
    }
}

static void __cdecl oc_apply_end(void *object) {
    if (oc.state == OC_DELIVERED && object != NULL && object == oc.object) {
        oc.in_apply = 0;
        oc_disarm();
    }
}

/* The Secret City 0x419A29: mov eax,[esi+0x830]; push eax; call [edx+0x2C];
   mov ecx,esi (12 bytes) -- ECX is the event object, EDX its vtable. */
__declspec(naked) static void oc_vv3_choice_stub(void) {
    __asm {
        pushad
        push dword ptr [esi + 0x830]
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        mov eax, dword ptr [esi + 0x830]
        push eax
        call dword ptr [edx + 0x2C]
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x419A35
        ret
    }
}

/* The Secret City 0x419A41: call [edx+0x30]; mov ecx,esi (5 bytes). */
__declspec(naked) static void oc_vv3_simple_stub(void) {
    __asm {
        pushad
        push -1
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        call dword ptr [edx + 0x30]
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x419A46
        ret
    }
}

/* The Tree of Life 0x417EC9: mov eax,[ecx]; mov edx,[esi+0x830];
   mov eax,[eax+0x2C]; push edx; call eax; mov ecx,esi (16 bytes). */
__declspec(naked) static void oc_vv4_choice_stub(void) {
    __asm {
        pushad
        push dword ptr [esi + 0x830]
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        mov eax, dword ptr [ecx]
        mov edx, dword ptr [esi + 0x830]
        mov eax, dword ptr [eax + 0x2C]
        push edx
        call eax
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x417ED9
        ret
    }
}

/* The Tree of Life 0x417EE5: mov edx,[ecx]; mov eax,[edx+0x30]; call eax;
   mov ecx,esi (9 bytes). */
__declspec(naked) static void oc_vv4_simple_stub(void) {
    __asm {
        pushad
        push -1
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        mov edx, dword ptr [ecx]
        mov eax, dword ptr [edx + 0x30]
        call eax
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x417EEE
        ret
    }
}

/* New Believers 0x418749: the same shape as The Tree of Life's. */
__declspec(naked) static void oc_vv5_choice_stub(void) {
    __asm {
        pushad
        push dword ptr [esi + 0x830]
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        mov eax, dword ptr [ecx]
        mov edx, dword ptr [esi + 0x830]
        mov eax, dword ptr [eax + 0x2C]
        push edx
        call eax
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x418759
        ret
    }
}

__declspec(naked) static void oc_vv5_simple_stub(void) {
    __asm {
        pushad
        push -1
        push ecx
        call oc_apply_begin
        add esp, 8
        popad
        push ecx
        mov edx, dword ptr [ecx]
        mov eax, dword ptr [edx + 0x30]
        call eax
        call oc_apply_end
        add esp, 4
        mov ecx, esi
        push 0x41876E
        ret
    }
}

#ifdef VVFP_TEST
/* ---- Test build only ------------------------------------------------------- */

/* Outcome site `index` of `game` (the rand sites, then the scope calls). */
static int oc_probe_site(int game, int index, unsigned int *va, unsigned char *expect,
                         unsigned char *replace) {
    const oc_game *g = &OC_GAMES[game];
    const unsigned char *bytes;
    void *target;
    unsigned int rel;
    if (index < 0) {
        return 0;
    }
    if (index < g->site_count) {
        *va = g->sites[index].va;
        bytes = g->sites[index].expect;
        target = (void *)oc_rand_stub;
    } else if (index - g->site_count < g->scope_count) {
        index -= g->site_count;
        *va = g->scopes[index].va;
        bytes = g->scopes[index].expect;
        target = (void *)oc_scope_stub;
    } else {
        return 0;
    }
    memcpy(expect, bytes, 5);
    rel = (unsigned int)((uintptr_t)target - ((uintptr_t)*va + 5));
    replace[0] = 0xE8;
    memcpy(replace + 1, &rel, 4);
    return 5;
}

/* Arms the settings for `slot` of `game` as the dialog would: `choices`
   holds `count` control choices (OC_RANDOM = -1), `who` count * 32 bytes of
   chosen villagers (or NULL). */
__declspec(dllexport) int __stdcall VvfpStoryProbeOutcomeArm(int game, int slot, const int *choices,
                                                             int count, const unsigned char *who,
                                                             int strength, int unlocked) {
    oc_settings s;
    int i;
    if (game < 1 || game > 5) {
        return 0;
    }
    memset(&s, 0, sizeof s);
    for (i = 0; i < OC_MAX_CONTROLS; ++i) {
        s.choice[i] = i < count ? choices[i] : OC_RANDOM;
        if (who != NULL && i < count) {
            memcpy(s.who[i], who + (size_t)i * OC_WHO_BYTES, OC_WHO_BYTES);
        }
    }
    s.strength = strength;
    s.unlocked = unlocked;
    if (slot == OC_GONG_SLOT) {
        oc_arm_set(&oc_gong, game, slot, &s);
        oc_gong.save_slot = story_current_slot(game);
        return oc_gong.state;
    }
    oc_arm(game, slot, &s);
    return oc.state;
}

/* Addresses of the armed outcomes' fields, for stubs that read them while
   game code runs: &oc.state, &oc.in_apply, &oc.branch, &oc_gong.state,
   &oc_gong.in_apply. */
__declspec(dllexport) void __stdcall VvfpStoryProbeOutcomeFields(unsigned int *out) {
    out[0] = (unsigned int)(uintptr_t)&oc.state;
    out[1] = (unsigned int)(uintptr_t)&oc.in_apply;
    out[2] = (unsigned int)(uintptr_t)&oc.branch;
    out[3] = (unsigned int)(uintptr_t)&oc_gong.state;
    out[4] = (unsigned int)(uintptr_t)&oc_gong.in_apply;
}

/* state, game, slot (-1), branch, in_apply, victim_missed, object. */
__declspec(dllexport) void __stdcall VvfpStoryProbeOutcomeState(int *out) {
    out[0] = oc.state;
    out[1] = oc.game;
    out[2] = oc.event != NULL ? oc.event->slot : -1;
    out[3] = oc.branch;
    out[4] = oc.in_apply;
    out[5] = oc.victim_missed;
    out[6] = (int)(uintptr_t)oc.object;
}

__declspec(dllexport) void __stdcall VvfpStoryProbeOutcomeDisarm(void) {
    oc_disarm();
}

/* Puts the armed outcome in `state` with `branch`, `in_apply` and `object`
   (the tests then run single rolls). */
__declspec(dllexport) void __stdcall VvfpStoryProbeOutcomeForce(int state, int branch, int in_apply,
                                                               void *object) {
    oc.state = state;
    oc.branch = branch;
    oc.in_apply = in_apply;
    oc.object = object;
    memset(oc.calls, 0, sizeof oc.calls);
}

/* The same for the Gong of Wonder's armed outcome. */
__declspec(dllexport) void __stdcall VvfpStoryProbeGongForce(int state, int in_apply) {
    oc_gong.state = state;
    oc_gong.in_apply = in_apply;
    memset(oc_gong.calls, 0, sizeof oc_gong.calls);
}

/* Sets the depth of the scope call at `va` of `game`; returns its index or -1. */
__declspec(dllexport) int __stdcall VvfpStoryProbeOutcomeScope(int game, unsigned int va, int depth) {
    const oc_game *g = &OC_GAMES[game];
    int i;
    for (i = 0; i < g->scope_count && i < OC_MAX_SCOPES; ++i) {
        if (g->scopes[i].va == va) {
            oc_scope_depth[i] = depth;
            return i;
        }
    }
    return -1;
}

/* The tables as compiled: event `i` of `game` -> slot, control count,
   strength, unlock; returns 0 past the end. */
__declspec(dllexport) int __stdcall VvfpStoryProbeOutcomeEvent(int game, int i, int *out) {
    const oc_game *g = &OC_GAMES[game];
    if (i < 0 || i >= g->event_count) {
        return 0;
    }
    out[0] = g->events[i].slot;
    out[1] = g->events[i].control_count;
    out[2] = g->events[i].strength;
    out[3] = g->events[i].unlock;
    return 1;
}

/* Control `ci` of event `i`: kind, phase, branch, scope VA (0), site VA (0),
   option count, bound, base, step, everyone, nobody, reg, mem, mem_disp,
   disp, elem, elem_size, elem_disp; then for each option (up to 32) its
   force count and first (site VA, value). */
__declspec(dllexport) int __stdcall VvfpStoryProbeOutcomeControl(int game, int i, int ci, int *out) {
    const oc_game *g = &OC_GAMES[game];
    const oc_control *c;
    int k;
    if (i < 0 || i >= g->event_count || ci < 0 || ci >= g->events[i].control_count) {
        return 0;
    }
    c = &g->controls[g->events[i].control_first + ci];
    out[0] = c->kind;
    out[1] = c->phase;
    out[2] = c->branch;
    out[3] = c->scope >= 0 ? (int)g->scopes[c->scope].va : 0;
    out[4] = c->site >= 0 ? (int)g->sites[c->site].va : 0;
    out[5] = c->option_count;
    out[6] = c->bound;
    out[7] = c->base;
    out[8] = c->step;
    out[9] = c->everyone;
    out[10] = c->nobody;
    out[11] = c->reg;
    out[12] = c->mem;
    out[13] = c->mem_disp;
    out[14] = c->disp;
    out[15] = c->elem;
    out[16] = c->elem_size;
    out[17] = c->elem_disp;
    for (k = 0; k < c->option_count && k < 32; ++k) {
        const oc_option *o = &g->options[c->option_first + k];
        out[18 + 3 * k] = o->force_count;
        out[19 + 3 * k] = o->force_count ? (int)g->sites[g->forces[o->force_first].site].va : 0;
        out[20 + 3 * k] = o->force_count ? g->forces[o->force_first].value : 0;
    }
    return 1;
}
#endif
