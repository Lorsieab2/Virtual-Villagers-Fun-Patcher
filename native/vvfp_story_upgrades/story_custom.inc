/* Custom Island Event: the engine.  Included by vvfp_story_upgrades.c before
   the per-game adapters (story_c1.inc .. story_c5.inc).

   QUEUE.  The player builds an event in plain dialogs (story_custom_ui.inc).
   Buying it (0 tech points) makes the island event due exactly as the
   Origins Island Event purchase does -- the same fields, so the same pending
   lock as Pick Island Event: one island event, pick or custom event at a
   time -- and remembers the event.

   DELIVERY.  When the game's own scheduler fires the island event, each
   game's delivery hook (its adapter) runs this engine at the point where the
   game builds the event it is about to show: the changes are applied and the
   game's own island-event popup is filled with the custom title and
   description (and the food / tech lines the game's own events print), and
   the game shows it, reschedules the next event and counts it as stock.

   APPLYING.  Every change goes through the adapter, which writes only what
   that game's own code was traced to write for the same effect (see each
   story_c*.inc).  A villager is changed only if its record still holds the
   same villager (living, same name) as when the event was queued; new
   villagers and babies are made only while the game's own room predicate
   says the village has room, one at a time, so the population cap of the
   installed mode is never passed. */

typedef struct {
    unsigned int caps;
    const char *game_name;
    int adult_age;                 /* the game's own adult boundary, age units */
    int min_spawn_age;             /* age units */
    int max_spawn_age;
    int record_count;
    int name_bytes;                /* the record's name field, NUL included */
    unsigned int off_name;
    unsigned int off_sex;
    unsigned int off_age;
    unsigned int off_head;
    unsigned int off_body;
    unsigned int off_likes;
    unsigned int off_dislikes;
    unsigned int off_skills;
    int sex_male;
    int sex_female;
    int pref_slots;                /* the likes / dislikes array length */
    int pref_count;                /* valid preference indices 0..pref_count-1 */
    const char *pref_list;         /* the game's own list, comma separated */
    int head_count;                /* valid heads 0..head_count-1 */
    int body_count;
    int skill_count;
    int skills_float;
    const char *const *skill_names;
    /* This villager's own parents (VV2-VV5), 0 = not on the record. */
    unsigned int off_father_name;
    unsigned int off_mother_name;
    int parent_name_bytes;
    unsigned int off_father_head;
    unsigned int off_father_body;
    unsigned int off_mother_head;
    unsigned int off_mother_body;
    const char *const *statuses;   /* CAP_STATUS: the faction / status choices */
    int status_count;
    const char *const *behaviours; /* CAP_BEHAVIOUR */
    int behaviour_count;
    const char *const *villages;   /* CAP_VILLAGE */
    int village_count;
    const char *omitted;           /* what this game does not offer, and why */
    /* The popup panel (the game's own island-event text box). */
    int text_width;                /* characters per line */
    int text_lines;                /* lines, title included */
    int title_width;               /* the title's characters (one line) */
    int title_separate;            /* 1 = the title is its own string (VV3-VV5) */
    int min_carrier_age;           /* the youngest a pregnancy may be given, age units */
    const char *refill_note;       /* what "Refill the food sources" refills here */
    /* The game's own wording of a food / tech outcome line (%d = amount). */
    const char *food_gain;
    const char *food_loss;
    const char *tech_gain;
    const char *tech_loss;

    unsigned char *(*record)(int index);
    int (*listed)(const unsigned char *record);
    const char *(*arm_refusal)(void);         /* why an event cannot be queued now, or NULL */
    int (*room)(void);                         /* the game's own "room for one more" */
    int (*spawn)(const ce_spawn *spawn);       /* the new record index, or -1 */
    int (*kill)(int index);
    int (*vanish)(int index);
    int (*sicken)(int index);
    int (*conceive)(int index, int litter, int father, ce_result *result);
    int (*set_status)(int index, int status);
    int (*behave)(int index, int behaviour);
    int (*village)(int which);
    int (*food)(void);                          /* the food store, for the result */
    int (*tech)(void);
    void (*change_food)(int op, int amount);
    void (*change_tech)(int op, int amount);
    int (*refill)(void);
    int (*parents_supported)(void);            /* CAP_PARENTS needs the game's / companion's store */
    int (*set_parents)(int index, const ce_change *change);
} ce_adapter;

static const ce_adapter *ce_adapter_for(int game);

/* ---- The armed event ----------------------------------------------------- */

static ce_event ce_armed_event;
static int ce_armed;               /* 1 while an event is queued and not yet delivered */
static DWORD ce_armed_tick;
static ce_result ce_last_result;
static int ce_last_lapsed;         /* the last queued event lapsed before it could happen */

/* An armed event the game has not run within PICK_TIMEOUT_MS is dropped,
   exactly like a pick.  Returns 1 when one was dropped. */
static int ce_drop_lapsed(void) {
    if (ce_armed && STORY_TICK() - ce_armed_tick > PICK_TIMEOUT_MS) {
        ce_armed = 0;
        ce_last_lapsed = 1;
        STORY_COUNT(lapsed);
        return 1;
    }
    return 0;
}

/* Whether a custom event is armed for `game` (not consumed). */
static int ce_pending(int game) {
    ce_drop_lapsed();
    return ce_armed && ce_armed_event.game == game;
}

/* ---- Record helpers ------------------------------------------------------ */

static unsigned int ce_fingerprint(const ce_adapter *a, const unsigned char *record) {
    return vv_title_fingerprint(record + a->off_name, (unsigned int)a->name_bytes);
}

static int ce_sex(const ce_adapter *a, const unsigned char *record) {
    int raw = *(const int *)(record + a->off_sex);
    if (raw == a->sex_male) {
        return STORY_SEX_MALE;
    }
    if (raw == a->sex_female) {
        return STORY_SEX_FEMALE;
    }
    return 0;
}

static int ce_age(const ce_adapter *a, const unsigned char *record) {
    return *(const int *)(record + a->off_age);
}

/* The record `index` if it holds the same living villager as `fingerprint`. */
static unsigned char *ce_same_villager(const ce_adapter *a, int index, unsigned int fingerprint) {
    unsigned char *record;
    if (index < 0 || index >= a->record_count) {
        return NULL;
    }
    record = a->record(index);
    if (record == NULL || !a->listed(record) || ce_fingerprint(a, record) != fingerprint) {
        return NULL;
    }
    return record;
}

/* The roster the target list shows: every listed villager, in record order. */
static int ce_roster(const ce_adapter *a, story_member *out, int cap) {
    int i;
    int n = 0;
    for (i = 0; i < a->record_count && n < cap; ++i) {
        const unsigned char *record = a->record(i);
        if (record == NULL || !a->listed(record)) {
            continue;
        }
        out[n].index = i;
        out[n].sex = ce_sex(a, record);
        out[n].age = ce_age(a, record);
        ++n;
    }
    return n;
}

static void ce_copy_name(char *out, int size, const unsigned char *field, int capacity) {
    int i;
    for (i = 0; i < size - 1 && i < capacity && field[i] != 0; ++i) {
        out[i] = (char)field[i];
    }
    out[i] = '\0';
}

static void ce_write_name(unsigned char *field, int capacity, const char *name) {
    int i;
    for (i = 0; i < capacity - 1 && name[i] != '\0'; ++i) {
        field[i] = (unsigned char)name[i];
    }
    for (; i < capacity; ++i) {
        field[i] = 0;
    }
}

/* ---- Preferences, appearance, skills ------------------------------------- */

/* Add `value` to a preference array: nothing if it is already there, the
   first empty (-1) slot otherwise.  0 when the array is full. */
static int ce_pref_add(int *slots, int count, int value) {
    int i;
    int empty = -1;
    for (i = 0; i < count; ++i) {
        if (slots[i] == value) {
            return 1;
        }
        if (slots[i] == -1 && empty < 0) {
            empty = i;
        }
    }
    if (empty < 0) {
        return 0;
    }
    slots[empty] = value;
    return 1;
}

static void ce_pref_remove(int *slots, int count, int value) {
    int i;
    for (i = 0; i < count; ++i) {
        if (slots[i] == value) {
            slots[i] = -1;
        }
    }
}

static int ce_valid_pref(const ce_adapter *a, int value) {
    return value >= 0 && value < a->pref_count;
}

static void ce_set_skill(const ce_adapter *a, unsigned char *record, int skill, int value) {
    unsigned char *field = record + a->off_skills + 4u * (unsigned int)skill;
    if (value < 0) {
        value = 0;
    }
    if (value > 100) {
        value = 100;
    }
    if (a->skills_float) {
        *(float *)field = (float)value;
    } else {
        *(int *)field = value;
    }
}

/* Every per-villager change that is a plain record write, as the Origins
   upgrades of the same game already write it (Change Appearance: head and
   body; Grant Running: likes; Full Mastery: skills).  Returns the number of
   changes refused (a full preference array). */
static int ce_apply_fields(const ce_adapter *a, unsigned char *record, const ce_change *c) {
    int refused = 0;
    int i;
    if ((a->caps & CAP_APPEARANCE) && c->head != CE_KEEP && c->head >= 0 && c->head < a->head_count) {
        *(int *)(record + a->off_head) = c->head;
    }
    if ((a->caps & CAP_APPEARANCE) && c->body != CE_KEEP && c->body >= 0 && c->body < a->body_count) {
        *(int *)(record + a->off_body) = c->body;
    }
    if (a->caps & CAP_PREFS) {
        int *likes = (int *)(record + a->off_likes);
        int *dislikes = (int *)(record + a->off_dislikes);
        if (ce_valid_pref(a, c->like_remove)) {
            ce_pref_remove(likes, a->pref_slots, c->like_remove);
        }
        if (ce_valid_pref(a, c->dislike_remove)) {
            ce_pref_remove(dislikes, a->pref_slots, c->dislike_remove);
        }
        if (ce_valid_pref(a, c->like_add) && !ce_pref_add(likes, a->pref_slots, c->like_add)) {
            ++refused;
        }
        if (ce_valid_pref(a, c->dislike_add) && !ce_pref_add(dislikes, a->pref_slots, c->dislike_add)) {
            ++refused;
        }
    }
    if (a->caps & CAP_SKILLS) {
        for (i = 0; i < a->skill_count && i < CE_SKILLS; ++i) {
            if (c->skills[i] != CE_KEEP) {
                ce_set_skill(a, record, i, c->skills[i]);
            }
        }
    }
    return refused;
}

/* ---- Text ------------------------------------------------------------------ */

/* The characters a custom title, description, name or villager title may
   hold: what every game's font draws and no game's text routines treat as a
   format or placeholder (VV1 runs event text and names through sprintf and
   expands * ^ & + = $ | ~). */
static int ce_text_char_ok(char c) {
    if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
        return 1;
    }
    /* Only the punctuation A New Home's own strings use outside its
       placeholders (its font is not proven to draw ( ) ; " or %). */
    return c == ' ' || c == '.' || c == ',' || c == '!' || c == '?' || c == ':'
        || c == '-' || c == '\'';
}

/* 1 when every character of `text` is allowed (newlines too when
   `multiline`). */
static int ce_text_ok(const char *text, int multiline) {
    for (; *text != '\0'; ++text) {
        if (multiline && (*text == '\r' || *text == '\n')) {
            continue;
        }
        if (!ce_text_char_ok(*text)) {
            return 0;
        }
    }
    return 1;
}

typedef struct {
    char *out;
    int size;
    int used;
    int lines;
    int width;
    int max_lines;
    int overflow;
} ce_writer;

static void ce_put(ce_writer *w, char c) {
    if (w->used + 1 >= w->size) {
        w->overflow = 1;
        return;
    }
    w->out[w->used++] = c;
    w->out[w->used] = '\0';
}

static void ce_newline(ce_writer *w) {
    if (w->lines >= w->max_lines) {
        w->overflow = 1;
        return;
    }
    ce_put(w, '\n');
    ++w->lines;
}

/* Word-wrap `text` into lines of at most w->width characters (a word longer
   than a line is cut).  The player's own line breaks are kept. */
static void ce_wrap(ce_writer *w, const char *text) {
    int column = 0;
    while (*text != '\0' && !w->overflow) {
        int length = 0;
        if (*text == '\r') {
            ++text;
            continue;
        }
        if (*text == '\n') {
            ce_newline(w);
            column = 0;
            ++text;
            continue;
        }
        if (*text == ' ') {
            if (column > 0 && column < w->width) {
                ce_put(w, ' ');
                ++column;
            }
            ++text;
            continue;
        }
        while (text[length] != '\0' && text[length] != ' ' && text[length] != '\n'
               && text[length] != '\r') {
            ++length;
        }
        if (column > 0 && column + length > w->width) {
            /* drop a trailing space before the break */
            if (w->used > 0 && w->out[w->used - 1] == ' ') {
                w->out[--w->used] = '\0';
            }
            ce_newline(w);
            column = 0;
        }
        while (length > 0 && !w->overflow) {
            if (column >= w->width) {
                ce_newline(w);
                column = 0;
            }
            ce_put(w, *text++);
            ++column;
            --length;
        }
    }
}

static void ce_line(ce_writer *w, const char *text) {
    ce_newline(w);
    ce_wrap(w, text);
}

/* The popup text: the title on the first line, then (as every stock event
   does) three empty lines and the description, then the outcome lines.
   Returns 0 when it does not fit the game's panel. */
static int ce_compose(const ce_adapter *a, const ce_event *e, const ce_result *r,
                      char *out, int size) {
    ce_writer w;
    char line[160];
    memset(&w, 0, sizeof w);
    w.out = out;
    w.size = size;
    w.width = a->text_width;
    w.max_lines = a->text_lines - 1;
    out[0] = '\0';
    if (lstrlenA(e->title) > a->title_width) {
        return 0;                      /* the title is one line */
    }
    if (!a->title_separate) {
        /* As every stock event: the title, then four line breaks. */
        ce_wrap(&w, e->title);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
    }
    ce_wrap(&w, e->text);
    if (r != NULL) {
        /* The outcome lines, after a blank line, as the stock events print
           theirs. */
        int first = 1;
        if (e->food_op != CE_AMOUNT_NONE && (a->caps & CAP_FOOD) && r->food_after != r->food_before) {
            int delta = r->food_after - r->food_before;
            ce_newline(&w);
            first = 0;
            wsprintfA(line, delta < 0 ? a->food_loss : a->food_gain, delta < 0 ? -delta : delta);
            ce_line(&w, line);
        }
        if (e->tech_op != CE_AMOUNT_NONE && (a->caps & CAP_TECH) && r->tech_after != r->tech_before) {
            int delta = r->tech_after - r->tech_before;
            if (first) {
                ce_newline(&w);
                first = 0;
            }
            wsprintfA(line, delta < 0 ? a->tech_loss : a->tech_gain, delta < 0 ? -delta : delta);
            ce_line(&w, line);
        }
        if ((r->no_room_spawns > 0 || r->no_room_babies > 0 || r->skipped > 0 || r->refused > 0)
            && first) {
            ce_newline(&w);
        }
        if (r->no_room_spawns > 0 || r->no_room_babies > 0) {
            wsprintfA(line, "The village had no room for %d of the new villagers.",
                      r->no_room_spawns + r->no_room_babies);
            ce_line(&w, line);
        }
        if (r->skipped > 0) {
            wsprintfA(line, "%d of the chosen villagers were no longer here.", r->skipped);
            ce_line(&w, line);
        }
        if (r->refused > 0) {
            /* What the game's own rules did not allow: a full likes list, a
               villager too young or already expecting, an Esteemed Elder
               who has no totem, ... */
            wsprintfA(line, r->refused == 1 ? "1 change could not be made."
                                            : "%d changes could not be made.", r->refused);
            ce_line(&w, line);
        }
    }
    return !w.overflow;
}

/* ---- Record writes the adapters share ------------------------------------ */

/* This villager's own parents, on the record (VV2-VV5): the names (blank =
   no change) and heads / bodies (CE_KEEP = no change, else within the
   game's own ranges) the game itself writes once at birth and only the
   Details portrait and the patcher's logs read. */
static int ce_set_record_parents(unsigned char *r, unsigned int father_name, unsigned int mother_name,
                                 int name_bytes, unsigned int father_head, unsigned int father_body,
                                 unsigned int mother_head, unsigned int mother_body, int heads,
                                 int bodies, const ce_change *c) {
    if (r == NULL) {
        return 0;
    }
    if ((c->father_head != CE_KEEP && (c->father_head < 0 || c->father_head >= heads))
        || (c->mother_head != CE_KEEP && (c->mother_head < 0 || c->mother_head >= heads))
        || (c->father_body != CE_KEEP && (c->father_body < 0 || c->father_body >= bodies))
        || (c->mother_body != CE_KEEP && (c->mother_body < 0 || c->mother_body >= bodies))) {
        return 0;
    }
    if (c->father_name[0] != '\0') {
        ce_write_name(r + father_name, name_bytes, c->father_name);
    }
    if (c->mother_name[0] != '\0') {
        ce_write_name(r + mother_name, name_bytes, c->mother_name);
    }
    if (c->father_head != CE_KEEP) *(int *)(r + father_head) = c->father_head;
    if (c->father_body != CE_KEEP) *(int *)(r + father_body) = c->father_body;
    if (c->mother_head != CE_KEEP) *(int *)(r + mother_head) = c->mother_head;
    if (c->mother_body != CE_KEEP) *(int *)(r + mother_body) = c->mother_body;
    return 1;
}

/* A new villager's details, written over what the game's own creator chose:
   the name, head and body, the likes and dislikes (replaced as a whole when
   any is given), and the skills -- the fields the Origins upgrades of the
   same game already write. */
static void ce_apply_spawn_record(const ce_adapter *a, unsigned char *r, const ce_spawn *s) {
    int i;
    if (r == NULL) {
        return;
    }
    if ((a->caps & CAP_SPAWN_NAME) && s->name[0] != '\0') {
        ce_write_name(r + a->off_name, a->name_bytes, s->name);
    }
    if ((a->caps & CAP_APPEARANCE) && s->head != CE_KEEP && s->head >= 0 && s->head < a->head_count) {
        *(int *)(r + a->off_head) = s->head;
    }
    if ((a->caps & CAP_APPEARANCE) && s->body != CE_KEEP && s->body >= 0 && s->body < a->body_count) {
        *(int *)(r + a->off_body) = s->body;
    }
    if ((a->caps & CAP_PREFS) && s->prefs_set) {
        int *likes = (int *)(r + a->off_likes);
        int *dislikes = (int *)(r + a->off_dislikes);
        for (i = 0; i < a->pref_slots; ++i) {
            likes[i] = -1;
            dislikes[i] = -1;
        }
        for (i = 0; i < CE_SPAWN_PREFS; ++i) {
            if (ce_valid_pref(a, s->likes[i])) {
                ce_pref_add(likes, a->pref_slots, s->likes[i]);
            }
            if (ce_valid_pref(a, s->dislikes[i]) && s->dislikes[i] != s->likes[0]
                && s->dislikes[i] != s->likes[1] && s->dislikes[i] != s->likes[2]) {
                ce_pref_add(dislikes, a->pref_slots, s->dislikes[i]);
            }
        }
    }
    if (a->caps & CAP_SKILLS) {
        for (i = 0; i < a->skill_count && i < CE_SKILLS; ++i) {
            if (s->skills[i] != CE_KEEP) {
                ce_set_skill(a, r, i, s->skills[i]);
            }
        }
    }
}

/* ---- Applying ---------------------------------------------------------- */

static void ce_amount(int op, int amount, int current, int *out) {
    long long value = current;
    if (op == CE_AMOUNT_ADD) {
        value += amount;
    } else if (op == CE_AMOUNT_SUBTRACT) {
        value -= amount;
    } else if (op == CE_AMOUNT_ZERO) {
        value = 0;
    }
    if (value < 0) {
        value = 0;
    }
    if (value > 0x7FFFFFFF - CE_MAX_AMOUNT) {
        value = 0x7FFFFFFF - CE_MAX_AMOUNT;
    }
    *out = (int)value;
}

/* Apply `e` to the village.  Runs on the game's own thread, inside the
   game's island-event construction, where the stock events make their own
   changes. */
static void ce_apply(const ce_adapter *a, const ce_event *e, ce_result *r) {
    int i;
    int j;
    memset(r, 0, sizeof *r);
    r->food_before = r->food_after = (a->caps & CAP_FOOD) ? a->food() : 0;
    r->tech_before = r->tech_after = (a->caps & CAP_TECH) ? a->tech() : 0;

    /* The village. */
    if ((a->caps & CAP_FOOD) && e->food_op != CE_AMOUNT_NONE) {
        a->change_food(e->food_op, e->food_amount);
    }
    if ((a->caps & CAP_TECH) && e->tech_op != CE_AMOUNT_NONE) {
        a->change_tech(e->tech_op, e->tech_amount);
    }
    if ((a->caps & CAP_REFILL) && e->refill) {
        a->refill();
    }
    if (a->caps & CAP_VILLAGE) {
        for (i = 0; i < a->village_count && i < 32; ++i) {
            if (e->village & (1u << i)) {
                a->village(i);
            }
        }
    }

    /* The villagers, in the order they were added.  A fate is final: a
       villager who dies or disappears gets nothing else. */
    for (i = 0; i < e->change_count && i < CE_MAX_CHANGES; ++i) {
        const ce_change *c = &e->changes[i];
        unsigned char *record = ce_same_villager(a, c->index, c->fingerprint);
        if (record == NULL) {
            ++r->skipped;
            continue;
        }
        ++r->changed;
        if (c->fate == CE_FATE_KILL && (a->caps & CAP_KILL)) {
            if (a->kill(c->index)) {
                ++r->died;
            }
            continue;
        }
        if (c->fate == CE_FATE_VANISH && (a->caps & CAP_VANISH)) {
            if (a->vanish(c->index)) {
                ++r->vanished;
            }
            continue;
        }
        if (c->like_add >= 0 || c->like_remove >= 0 || c->dislike_add >= 0 || c->dislike_remove >= 0) {
            story_preferences_changing(e->game, 0);
            r->refused += ce_apply_fields(a, record, c);
            story_preferences_changing(e->game, 1);
        } else {
            r->refused += ce_apply_fields(a, record, c);
        }
        if ((a->caps & CAP_PARENTS) && c->parents_set
            && (!a->parents_supported() || !a->set_parents(c->index, c))) {
            ++r->refused;
        }
        if ((a->caps & CAP_SICK) && c->sick && !a->sicken(c->index)) {
            ++r->refused;
        }
        if ((a->caps & CAP_STATUS) && c->status != CE_KEEP && !a->set_status(c->index, c->status)) {
            ++r->refused;
        }
        if ((a->caps & CAP_MASK) && c->mask != CE_KEEP && !story_set_mask(e->game, record, c->mask)) {
            ++r->refused;
        }
        if ((a->caps & CAP_TITLE) && c->title_op != CE_TITLE_KEEP
            && !titles_set(e->game, c->index, c->title_op == CE_TITLE_SET ? c->title : NULL)) {
            ++r->refused;
        }
        if ((a->caps & CAP_BEHAVIOUR) && c->behaviour != CE_KEEP && !a->behave(c->index, c->behaviour)) {
            ++r->refused;
        }
    }

    /* Pregnancies, then new villagers: each baby and each villager only
       while the game's own predicate says the village has room. */
    if (a->caps & CAP_PREGNANT) {
        for (i = 0; i < e->change_count && i < CE_MAX_CHANGES; ++i) {
            const ce_change *c = &e->changes[i];
            int father = -1;
            if (c->litter <= 0 || c->fate != CE_FATE_NONE
                || ce_same_villager(a, c->index, c->fingerprint) == NULL) {
                continue;
            }
            if (c->father >= 0 && ce_same_villager(a, c->father, c->father_fingerprint) != NULL) {
                father = c->father;
            }
            r->conceived += a->conceive(c->index, c->litter > 3 ? 3 : c->litter, father, r);
        }
    }
    if (a->caps & CAP_SPAWN) {
        for (i = 0; i < e->spawn_groups && i < CE_MAX_SPAWN_GROUPS; ++i) {
            const ce_spawn *s = &e->spawns[i];
            for (j = 0; j < s->count && j < CE_MAX_SPAWN_COUNT; ++j) {
                /* Each game's spawn asks the game's own room predicate (and
                   for a free record) first and makes nobody without room. */
                int index = a->spawn(s);
                if (index < 0) {
                    r->no_room_spawns += s->count - j;
                    break;
                }
                ++r->born;
                if ((a->caps & CAP_TITLE) && s->title[0] != '\0') {
                    titles_set(e->game, index, s->title);
                }
                if ((a->caps & CAP_MASK) && s->mask != CE_KEEP) {
                    unsigned char *record = a->record(index);
                    if (record != NULL) {
                        story_set_mask(e->game, record, s->mask);
                    }
                }
            }
        }
    }
    if (a->caps & CAP_FOOD) {
        r->food_after = a->food();
    }
    if (a->caps & CAP_TECH) {
        r->tech_after = a->tech();
    }
}

/* Called by a game's delivery hook: if a custom event is armed for `game`,
   take it, apply it and write the popup text into `text` (`size` bytes).
   Returns 1 when the custom event was delivered (the caller must then NOT
   run the game's own event choice), 0 otherwise. */
static int ce_deliver(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !ce_pending(game)) {
        return 0;
    }
    ce_armed = 0;
    ce_apply(a, &ce_armed_event, &ce_last_result);
    if (!ce_compose(a, &ce_armed_event, &ce_last_result, text, size)) {
        /* The outcome lines do not fit: the title and description were
           checked when the event was queued, so show those alone. */
        ce_compose(a, &ce_armed_event, NULL, text, size);
    }
    STORY_COUNT(delivered);
    return 1;
}

/* ---- Queueing ---------------------------------------------------------- */

/* Why `e` cannot be queued in `game` right now, or NULL.  The checks the
   dialogs make, repeated here because the village may have moved on while
   the dialogs were open. */
static const char *ce_refusal(int game, const ce_event *e) {
    const ce_adapter *a = ce_adapter_for(game);
    const char *reason;
    char text[1024];
    int i;
    if (a == NULL) {
        return "Custom Island Event is not available in this game.";
    }
    if (e->title[0] == '\0') {
        return "Give the event a title.";
    }
    if (!ce_text_ok(e->title, 0) || !ce_text_ok(e->text, 1)) {
        return "The title and description may use letters, numbers, spaces and . , ! ? : - ' only.";
    }
    if (!ce_compose(a, e, NULL, text, sizeof text)) {
        return "The title must fit on one line and the description must fit the island event panel. "
               "Shorten them.";
    }
    reason = a->arm_refusal();
    if (reason != NULL) {
        return reason;
    }
    for (i = 0; i < e->spawn_groups; ++i) {
        if (e->spawns[i].count > 0 && !a->room()) {
            return "The village is full: there is no room for new villagers.";
        }
    }
    for (i = 0; i < e->change_count; ++i) {
        if (e->changes[i].litter > 0 && !a->room()) {
            return "The village is full: there is no room for babies.";
        }
    }
    return NULL;
}
