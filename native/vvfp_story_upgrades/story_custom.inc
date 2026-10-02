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
   same villager (living; same name, sex, appearance, likes and dislikes) as
   when the event was queued; new
   villagers and babies are made only while the game's own room predicate
   says the village has room, one at a time, so the population cap of the
   installed mode is never passed. */

/* A food source or store the event can set to an amount (CAP_VALUES):
   its name, the range the game itself keeps it in, and what to know. */
typedef struct {
    const char *name;
    int min;
    int max;
    const char *note;
} ce_value_def;

/* A puzzle the event can mark solved / unsolved (CAP_PUZZLES): which way is
   offered (the other is refused, with the reason in `note`). */
typedef struct {
    const char *name;
    int can_solve;
    int can_unsolve;
    const char *note;
} ce_puzzle_def;

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
    const ce_action *behaviours;   /* CAP_BEHAVIOUR */
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
    /* CAP_VALUES: the current amount (-1 = not there yet, e.g. a farm not
       built) and the write (0 = refused). */
    const ce_value_def *values;
    int value_count;
    int (*value_get)(int which);
    int (*value_set)(int which, int amount);
    /* CAP_PUZZLES. */
    const ce_puzzle_def *puzzles;
    int puzzle_count;
    int (*puzzle_solved)(int which);
    int (*puzzle_set)(int which, int solved);   /* 0 = refused right now */
    /* CAP_CANCEL / CAP_RELITTER / CAP_UNBORN. */
    int (*cancel)(int index);
    int (*relitter)(int index, int litter, ce_result *result);
    int (*unborn)(int index, const ce_change *change);
    /* CAP_REVIVE: a record the game shows as a skeleton that may come back,
       and the revival (0 = refused). */
    int (*skeleton)(const unsigned char *record);
    int (*revive)(int index, int health, int cure);   /* 1 done, -1 no room (the game's
                                                         own predicate), 0 refused */
    int faction_count;             /* CAP_SPAWN_FACTION: statuses[0..n-1] are factions */
    unsigned int off_pregnant;     /* non-zero while expecting (every game's own test) */
    /* Two-choice events (CAP_CHOICE), set by the game's delivery hook.  A
       field left 0 takes the conservative default named. */
    int question_width;            /* the question popup's characters a line (0 = text_width) */
    int question_lines;            /* its lines, title included as text_lines (0 = text_lines) */
    int result_width;              /* the result popup's characters a line (0 = the question's) */
    int result_lines;              /* its lines (0 = the question's) */
    int result_has_title;          /* 1 = the result text starts with the title and four line
                                      breaks, as the plain popup of a one-string game does */
    int label_width;               /* a button label's characters (0 = CE_LABEL_DEFAULT_WIDTH) */
    int (*rand_below)(int n);      /* the game's own random routine, 0..n-1 (NULL = the
                                      companion's own generator) */
    int (*featurable)(const unsigned char *record);   /* a listed villager the question's
                                      picture may show (NULL = any) */
} ce_adapter;

static const ce_adapter *ce_adapter_for(int game);

/* ---- The armed event ----------------------------------------------------- */

static ce_event ce_armed_event;
static int ce_armed;               /* 1 while an event is queued and not yet delivered */
static DWORD ce_armed_tick;
static story_village ce_armed_village;   /* the village it was queued in */
static ce_result ce_last_result;
static int ce_last_lapsed;         /* the last queued event lapsed before it could happen */
/* Two-choice events.  Two stores, so a question the game is showing (asked,
   waiting for a click) is never overwritten by the next event armed: the
   armed choice is ce_choice_store[ce_armed_store] when ce_armed_is_choice,
   the asked one ce_choice_store[ce_asked_store] while ce_asked. */
static ce_choice ce_choice_store[2];
static int ce_armed_is_choice;
static int ce_armed_store;
static int ce_asked;                /* 1 while the question waits for a click */
static int ce_asked_store;
static int ce_asked_game;
static story_village ce_asked_village;
static char ce_asked_title[CE_TITLE_BYTES];
static int ce_last_button = -1;     /* the last resolved button and its rolled outcome */
static int ce_last_outcome = -1;

/* An armed event the game has not run within PICK_TIMEOUT_MS is dropped,
   exactly like a pick.  Returns 1 when one was dropped. */
static int ce_drop_lapsed(void) {
    if (ce_armed && !story_village_is(ce_armed_event.game, &ce_armed_village)) {
        /* Another village: the event was for the one the player left. */
        ce_armed = 0;
        STORY_COUNT(discarded);
        return 1;
    }
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

/* Whether a two-choice event is armed for `game`: its delivery hook asks
   the question (ce_choice_begin) instead of showing the plain popup. */
static int ce_choice_pending(int game) {
    return ce_pending(game) && ce_armed_is_choice;
}

/* Whether a plain (one-popup) custom event is armed for `game`. */
static int ce_plain_pending(int game) {
    return ce_pending(game) && !ce_armed_is_choice;
}

/* ---- Record helpers ------------------------------------------------------ */

/* The name alone: what a custom title is bound to (story_titles.inc). */
static unsigned int ce_fingerprint(const ce_adapter *a, const unsigned char *record) {
    return vv_title_fingerprint(record + a->off_name, (unsigned int)a->name_bytes);
}

static unsigned int ce_mix(unsigned int h, int value) {
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ ((unsigned int)value >> (8 * k) & 0xFFu)) * 16777619u;
    }
    return h;
}

/* Who a queued change is for: the name plus every field the game never
   changes on its own -- sex, head, body, likes and dislikes.  Names repeat
   (they come from a fixed pool), so a record freed and reused by a new
   villager of the same name must not inherit the change. */
static unsigned int ce_identity(const ce_adapter *a, const unsigned char *record) {
    unsigned int h = ce_fingerprint(a, record);
    int k;
    h = ce_mix(h, *(const int *)(record + a->off_sex));
    h = ce_mix(h, *(const int *)(record + a->off_head));
    h = ce_mix(h, *(const int *)(record + a->off_body));
    for (k = 0; k < a->pref_slots; ++k) {
        h = ce_mix(h, ((const int *)(record + a->off_likes))[k]);
        h = ce_mix(h, ((const int *)(record + a->off_dislikes))[k]);
    }
    return h ? h : 1u;
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

/* The record `index` if it holds the same living villager as `identity`
   (ce_identity when the change was queued). */
static unsigned char *ce_same_villager(const ce_adapter *a, int index, unsigned int identity) {
    unsigned char *record;
    if (index < 0 || index >= a->record_count) {
        return NULL;
    }
    record = a->record(index);
    if (record == NULL || !a->listed(record) || ce_identity(a, record) != identity) {
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

/* A popup's text panel: characters a line, lines (title included when it
   shares the text), whether the title leads the text, and whether the title
   must fit its one line. */
typedef struct {
    int width;
    int lines;
    int with_title;
    int check_title;
} ce_layout;

/* The plain island-event popup. */
static ce_layout ce_plain_layout(const ce_adapter *a) {
    ce_layout l;
    l.width = a->text_width;
    l.lines = a->text_lines;
    l.with_title = !a->title_separate;
    l.check_title = 1;
    return l;
}

/* The two-choice question popup: the title and the question. */
static ce_layout ce_question_layout(const ce_adapter *a) {
    ce_layout l = ce_plain_layout(a);
    if (a->question_width > 0) {
        l.width = a->question_width;
    }
    if (a->question_lines > 0) {
        l.lines = a->question_lines;
    }
    return l;
}

/* The popup after a button: the rolled outcome's result text. */
static ce_layout ce_result_layout(const ce_adapter *a) {
    ce_layout l = ce_question_layout(a);
    if (a->result_width > 0) {
        l.width = a->result_width;
    }
    if (a->result_lines > 0) {
        l.lines = a->result_lines;
    }
    l.with_title = a->result_has_title != 0;
    l.check_title = 0;
    return l;
}

/* A button label's characters. */
static int ce_label_width(const ce_adapter *a) {
    return a->label_width > 0 ? a->label_width : CE_LABEL_DEFAULT_WIDTH;
}

/* For the editor's counter: the panel lines the title and text take when
   laid out exactly as ce_compose_in lays them out with `l` (outcome lines
   aside), counted past the panel's limit. */
static int ce_lines_used_in(const ce_layout *l, const char *title, const char *text) {
    static char scratch[4096];
    ce_writer w;
    memset(&w, 0, sizeof w);
    w.out = scratch;
    w.size = sizeof scratch;
    w.width = l->width;
    w.max_lines = 1000;
    scratch[0] = '\0';
    if (text[0] == '\0' && (!l->with_title || title[0] == '\0')) {
        return 0;
    }
    if (l->with_title) {
        ce_wrap(&w, title);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
        ce_newline(&w);
    }
    ce_wrap(&w, text);
    return w.used == 0 ? 0 : w.lines + 1;
}

/* Words in `text`: runs of characters between spaces, tabs and line breaks. */
static int ce_word_count(const char *text) {
    int words = 0;
    int inside = 0;
    for (; *text != '\0'; ++text) {
        int space = *text == ' ' || *text == '\t' || *text == '\r' || *text == '\n';
        if (!space && !inside) {
            ++words;
        }
        inside = !space;
    }
    return words;
}

/* Characters as the panel shows them: the player's line breaks are not
   characters (Windows stores each as CR LF). */
static int ce_char_count(const char *text) {
    int n = 0;
    for (; *text != '\0'; ++text) {
        if (*text != '\r' && *text != '\n') {
            ++n;
        }
    }
    return n;
}

/* The popup text laid out with `l`: the title on the first line (when it
   leads the text), then (as every stock event does) three empty lines and
   the event's text, then the outcome lines.  Returns 0 when it does not fit
   the game's panel. */
static int ce_compose_in(const ce_adapter *a, const ce_layout *l, const char *title,
                         const ce_event *e, const ce_result *r, char *out, int size) {
    ce_writer w;
    char line[160];
    memset(&w, 0, sizeof w);
    w.out = out;
    w.size = size;
    w.width = l->width;
    w.max_lines = l->lines - 1;
    out[0] = '\0';
    if (l->check_title && lstrlenA(title) > a->title_width) {
        return 0;                      /* the title is one line */
    }
    if (l->with_title) {
        /* As every stock event: the title, then four line breaks. */
        ce_wrap(&w, title);
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
        if ((r->no_room_spawns > 0 || r->no_room_babies > 0 || r->no_room_revives > 0
             || r->skipped > 0 || r->refused > 0)
            && first) {
            ce_newline(&w);
        }
        if (r->no_room_spawns > 0 || r->no_room_babies > 0) {
            wsprintfA(line, "The village had no room for %d of the new villagers.",
                      r->no_room_spawns + r->no_room_babies);
            ce_line(&w, line);
        }
        if (r->no_room_revives > 0) {
            wsprintfA(line, "The village had no room for %d of the villagers brought back.",
                      r->no_room_revives);
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

/* The plain popup text. */
static int ce_compose(const ce_adapter *a, const ce_event *e, const ce_result *r,
                      char *out, int size) {
    ce_layout l = ce_plain_layout(a);
    return ce_compose_in(a, &l, e->title, e, r, out, size);
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
    /* Who is still the villager the change was queued for, decided once
       before anything is changed: this event may itself change a target's
       appearance or likes, which would otherwise make it look like someone
       else to the pregnancies below. */
    unsigned char same[CE_MAX_CHANGES];
    unsigned char father_same[CE_MAX_CHANGES];
    for (i = 0; i < e->change_count && i < CE_MAX_CHANGES; ++i) {
        const ce_change *c = &e->changes[i];
        same[i] = ce_same_villager(a, c->index, c->fingerprint) != NULL;
        father_same[i] = c->father >= 0 && ce_same_villager(a, c->father, c->father_fingerprint) != NULL;
    }
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
            if ((e->village & (1u << i)) && !a->village(i)) {
                ++r->refused;
            }
        }
    }
    /* Amounts, after the refill so a chosen amount is what stays. */
    if (a->caps & CAP_VALUES) {
        for (i = 0; i < e->value_count && i < CE_MAX_VALUES; ++i) {
            const ce_value *v = &e->values[i];
            if (v->which < 0 || v->which >= a->value_count || v->amount < a->values[v->which].min
                || v->amount > a->values[v->which].max || !a->value_set(v->which, v->amount)) {
                ++r->refused;
            }
        }
    }
    if (a->caps & CAP_PUZZLES) {
        for (i = 0; i < e->puzzle_count && i < CE_MAX_PUZZLES; ++i) {
            const ce_puzzle *p = &e->puzzles[i];
            const ce_puzzle_def *d = p->which >= 0 && p->which < a->puzzle_count
                ? &a->puzzles[p->which] : NULL;
            if (d == NULL || (p->solved ? !d->can_solve : !d->can_unsolve)) {
                ++r->refused;
                continue;
            }
            /* Already so: nothing to write (a second completion would stamp
               a new solve time and run the puzzle's completion again). */
            if ((a->puzzle_solved(p->which) != 0) == (p->solved != 0)) {
                continue;
            }
            if (!a->puzzle_set(p->which, p->solved ? 1 : 0)) {
                ++r->refused;
            }
        }
    }

    /* Skeletons brought back, each only while the game says there is room
       and the record still holds the same dead villager. */
    if (a->caps & CAP_REVIVE) {
        for (i = 0; i < e->revive_count && i < CE_MAX_REVIVES; ++i) {
            const ce_revive *v = &e->revives[i];
            unsigned char *record = v->index >= 0 && v->index < a->record_count ? a->record(v->index) : NULL;
            if (record == NULL || !a->skeleton(record) || ce_identity(a, record) != v->identity) {
                ++r->skipped;
                continue;
            }
            if (v->health < 1 || v->health > 100) {
                ++r->refused;
                continue;
            }
            switch (a->revive(v->index, v->health, v->cure)) {
            case 1: ++r->revived; break;
            case -1: ++r->no_room_revives; break;
            default: ++r->refused; break;
            }
        }
    }

    /* The villagers, in the order they were added.  A fate is final: a
       villager who dies or disappears gets nothing else. */
    for (i = 0; i < e->change_count && i < CE_MAX_CHANGES; ++i) {
        const ce_change *c = &e->changes[i];
        unsigned char *record = same[i] ? a->record(c->index) : NULL;
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
            unsigned int titled_as = story_title_identity(e->game, record);
            story_preferences_changing(e->game, 0);
            r->refused += ce_apply_fields(a, record, c);
            story_preferences_changing(e->game, 1);
            /* A custom title is bound to the likes and dislikes too: it
               follows its villager through this change. */
            if ((a->caps & CAP_TITLE) && !titles_rebind(e->game, c->index, titled_as)) {
                ++r->refused;
            }
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
            const unsigned char *mother = same[i] ? a->record(c->index) : NULL;
            const unsigned char *sire = father_same[i] ? a->record(c->father) : NULL;
            if (c->litter == 0 || c->fate != CE_FATE_NONE || mother == NULL || !a->listed(mother)) {
                continue;
            }
            if (c->litter == CE_LITTER_CANCEL) {
                /* "0 babies": no pregnancy (a pregnancy always delivers one
                   baby in every game, so this is the only way to 0). */
                if (!(a->caps & CAP_CANCEL) || !a->cancel(c->index)) {
                    ++r->refused;
                }
                continue;
            }
            if (c->litter < 1) {
                ++r->refused;
                continue;
            }
            if (*(const int *)(mother + a->off_pregnant) != 0) {
                /* Already expecting: the number of babies changes. */
                if (!(a->caps & CAP_RELITTER)) {
                    ++r->refused;
                } else {
                    r->conceived += a->relitter(c->index, c->litter > 3 ? 3 : c->litter, r);
                }
                continue;
            }
            if (sire != NULL && a->listed(sire)) {
                father = c->father;
            }
            r->conceived += a->conceive(c->index, c->litter > 3 ? 3 : c->litter, father, r);
        }
    }
    /* The unborn baby's father, on every carrier now expecting. */
    if (a->caps & CAP_UNBORN) {
        for (i = 0; i < e->change_count && i < CE_MAX_CHANGES; ++i) {
            const ce_change *c = &e->changes[i];
            const unsigned char *mother = same[i] ? a->record(c->index) : NULL;
            if (!c->unborn_set || c->fate != CE_FATE_NONE) {
                continue;
            }
            if (mother == NULL || !a->listed(mother)
                || *(const int *)(mother + a->off_pregnant) == 0 || !a->unborn(c->index, c)) {
                ++r->refused;
            }
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
                if ((a->caps & CAP_TITLE) && s->title[0] != '\0'
                    && !titles_set(e->game, index, s->title)) {
                    ++r->refused;
                }
                if ((a->caps & CAP_MASK) && s->mask != CE_KEEP) {
                    unsigned char *record = a->record(index);
                    if (record == NULL || !story_set_mask(e->game, record, s->mask)) {
                        ++r->refused;
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
   run the game's own event choice), 0 otherwise -- also when the armed
   event asks a question: that one is delivered by ce_choice_begin. */
static int ce_deliver(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    if (a == NULL || !ce_plain_pending(game)) {
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

/* Why the changes of `e` cannot be made right now: new villagers or babies
   in a village the game's own predicate says is full.  NULL otherwise. */
static const char *ce_room_refusal(const ce_adapter *a, const ce_event *e) {
    int i;
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

/* Why `e` cannot be queued in `game` right now, or NULL.  The checks the
   dialogs make, repeated here because the village may have moved on while
   the dialogs were open. */
static const char *ce_refusal(int game, const ce_event *e) {
    const ce_adapter *a = ce_adapter_for(game);
    const char *reason;
    char text[1024];
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
    return ce_room_refusal(a, e);
}

/* ---- Two-choice events ------------------------------------------------------

   ARMING.  A two-choice event is armed exactly as a plain one (ce_arm_with
   in story_custom_ui.inc): the same lock, the same 10-minute lapse, bound
   to the same save slot and reset generation.  ce_deliver leaves it alone.

   ASKING.  The game's delivery hook calls ce_choice_begin where it would
   call ce_deliver: the event is taken (so the lock is released as for a
   delivered event), the question popup's text is written and the two labels
   are ce_choice_label(game, 0 / 1).  Nothing in the village changes yet.

   ANSWERING.  When the player clicks a button the hook calls
   ce_choice_resolve(game, button, ...) on the game's own thread: one of
   that button's outcomes is rolled, weighted by the chances, through the
   game's own random routine (ce_adapter.rand_below); its changes are
   applied by ce_apply exactly as a plain event's are, and the result text
   (the outcome's text plus the usual outcome lines) is written for the
   game's result popup. */

/* 1 while ce_choice_refusal asks the adapter's arm_refusal: the event is a
   question (A New Home / The Lost Children then allow the first event). */
static int ce_refusal_for_choice;

#ifdef VVFP_TEST
static int test_choice_cap;        /* TEST build: every game may ask (the hooks are tested apart) */
static int test_roll = -1;         /* TEST build: the next roll, -1 = the real source */
#endif

/* Whether `game` can ask a question: its delivery hook is in place. */
static int ce_choice_available(const ce_adapter *a) {
#ifdef VVFP_TEST
    if (test_choice_cap) {
        return 1;
    }
#endif
    return (a->caps & CAP_CHOICE) != 0;
}

/* Whether `e` changes anything at all. */
static int ce_has_effects(const ce_event *e) {
    return e->food_op != CE_AMOUNT_NONE || e->tech_op != CE_AMOUNT_NONE || e->refill || e->village != 0
        || e->spawn_groups > 0 || e->change_count > 0 || e->value_count > 0 || e->puzzle_count > 0
        || e->revive_count > 0;
}

/* Why `label` cannot be a button's label in this game, or NULL. */
static const char *ce_label_refusal(const ce_adapter *a, const char *label) {
    static char reason[96];
    if (ce_word_count(label) == 0) {
        return "Give both buttons a label.";
    }
    if (!ce_text_ok(label, 0)) {
        return "A button label may use letters, numbers, spaces and . , ! ? : - ' only.";
    }
    if (lstrlenA(label) > ce_label_width(a)) {
        wsprintfA(reason, "A button label is %d characters at most in this game.", ce_label_width(a));
        return reason;
    }
    return NULL;
}

/* Why `e` cannot be an outcome (its result text and changes) of an event
   titled `title`, or NULL. */
static const char *ce_result_refusal(const ce_adapter *a, const ce_event *e, const char *title) {
    static char text[2048];
    ce_layout l = ce_result_layout(a);
    if (ce_word_count(e->text) == 0) {
        return "Give each outcome a result text.";
    }
    if (!ce_text_ok(e->text, 1)) {
        return "The result text may use letters, numbers, spaces and . , ! ? : - ' only.";
    }
    if (!ce_compose_in(a, &l, title, e, NULL, text, sizeof text)) {
        return "The result text must fit the island event panel. Shorten it.";
    }
    return ce_room_refusal(a, e);
}

/* Why outcome `o` cannot be part of an event titled `title`, or NULL. */
static const char *ce_outcome_refusal(const ce_adapter *a, const ce_outcome *o, const char *title) {
    if (o->chance < 1 || o->chance > CE_MAX_CHANCE) {
        return "Each outcome's chance is 1 to 100.";
    }
    return ce_result_refusal(a, &o->effects, title);
}

/* Why the two buttons of `c` (labels and outcomes) cannot be queued with an
   event titled `title`, or NULL; the reason names the button and outcome. */
static const char *ce_buttons_refusal(const ce_adapter *a, const ce_choice *c, const char *title) {
    static const char *const BUTTON[2] = { "First button", "Second button" };
    static char reason[400];
    const char *why;
    int b;
    int k;
    for (b = 0; b < 2; ++b) {
        why = ce_label_refusal(a, c->labels[b]);
        if (why != NULL) {
            wsprintfA(reason, "%s: %s", BUTTON[b], why);
            return reason;
        }
        if (c->outcome_count[b] < 1 || c->outcome_count[b] > CE_MAX_OUTCOMES) {
            wsprintfA(reason, "%s: give it one to %d outcomes.", BUTTON[b], CE_MAX_OUTCOMES);
            return reason;
        }
        for (k = 0; k < c->outcome_count[b]; ++k) {
            why = ce_outcome_refusal(a, &c->outcomes[b][k], title);
            if (why != NULL) {
                wsprintfA(reason, "%s, outcome %d: %s", BUTTON[b], k + 1, why);
                return reason;
            }
        }
    }
    return NULL;
}

/* Why the two-choice event (`e`: the title and the question; `c`: the
   buttons) cannot be queued in `game` right now, or NULL.  A choice that is
   not enabled is a plain event (ce_refusal). */
static const char *ce_choice_refusal(int game, const ce_event *e, const ce_choice *c) {
    const ce_adapter *a = ce_adapter_for(game);
    const char *why;
    char text[1024];
    if (a == NULL || !c->enabled) {
        return ce_refusal(game, e);
    }
    if (!ce_choice_available(a)) {
        return "This game can not ask a question with two choices yet.";
    }
    if (e->title[0] == '\0') {
        return "Give the event a title.";
    }
    if (!ce_text_ok(e->title, 0) || !ce_text_ok(e->text, 1)) {
        return "The title and question may use letters, numbers, spaces and . , ! ? : - ' only.";
    }
    {
        ce_layout l = ce_question_layout(a);
        if (!ce_compose_in(a, &l, e->title, e, NULL, text, sizeof text)) {
            return "The title must fit on one line and the question must fit the island event panel. "
                   "Shorten them.";
        }
    }
    if (ce_has_effects(e)) {
        return "With a question, every change belongs to an outcome. Remove the event's own "
               "changes, or untick \"Ask a question with two choices\".";
    }
    /* A New Home's and The Lost Children's first island event is always
       their two-choice family, which is the one a question is shown by:
       their arm_refusal lets a question be that event (owner, 2026-10-02). */
    ce_refusal_for_choice = 1;
    why = a->arm_refusal();
    ce_refusal_for_choice = 0;
    if (why != NULL) {
        return why;
    }
    return ce_buttons_refusal(a, c, e->title);
}

/* The outcome a roll picks: `roll` is 0..(the chances' sum - 1); outcome i
   takes chances[i] of those values, in order. */
static int ce_roll_index(const int *chances, int count, int roll) {
    int i;
    for (i = 0; i < count - 1; ++i) {
        if (roll < chances[i]) {
            return i;
        }
        roll -= chances[i];
    }
    return count - 1;
}

/* The companion's own generator, for a game whose hook names no random
   routine: xorshift32, seeded once from the clock. */
static unsigned int ce_rng;

/* A random number 0..n-1: the game's own routine when the adapter names
   one.  One outcome is never rolled for (the game's own random sequence is
   left exactly as it was). */
static int ce_random_below(const ce_adapter *a, int n) {
    int r;
    if (n <= 1) {
        return 0;
    }
#ifdef VVFP_TEST
    if (test_roll >= 0) {
        r = test_roll;
        test_roll = -1;
        return r % n;
    }
#endif
    if (a->rand_below != NULL) {
        r = a->rand_below(n) % n;
        return r < 0 ? r + n : r;
    }
    if (ce_rng == 0) {
        ce_rng = (GetTickCount() * 2654435761u) ^ 0xA5A5A5A5u;
        if (ce_rng == 0) {
            ce_rng = 1;
        }
    }
    ce_rng ^= ce_rng << 13;
    ce_rng ^= ce_rng >> 17;
    ce_rng ^= ce_rng << 5;
    return (int)((ce_rng >> 8) % (unsigned int)n);
}

/* Remember the choices of the event being armed for `game` (NULL or not
   enabled: a plain event), never in the store a question still on screen
   is waiting in. */
static void ce_store_choice(int game, const ce_choice *c) {
    int b;
    int k;
    ce_armed_is_choice = c != NULL && c->enabled;
    if (!ce_armed_is_choice) {
        return;
    }
    ce_armed_store = ce_asked && ce_asked_store == 0 ? 1 : 0;
    ce_choice_store[ce_armed_store] = *c;
    for (b = 0; b < 2; ++b) {
        for (k = 0; k < CE_MAX_OUTCOMES; ++k) {
            ce_choice_store[ce_armed_store].outcomes[b][k].effects.game = game;
        }
    }
    {
        /* The picked villager's identity as the event is queued. */
        ce_choice *stored = &ce_choice_store[ce_armed_store];
        const ce_adapter *a = ce_adapter_for(game);
        unsigned char *record = NULL;
        if (a != NULL && stored->featured_record > 0) {
            record = a->record(stored->featured_record - 1);
        }
        if (record != NULL && a->listed(record)) {
            stored->featured_identity = ce_identity(a, record);
        } else {
            stored->featured_record = 0;
            stored->featured_identity = 0;
        }
    }
}

/* The choice of `game` being delivered: the armed one, or the asked one. */
static const ce_choice *ce_choice_current(int game) {
    if (ce_choice_pending(game)) {
        return &ce_choice_store[ce_armed_store];
    }
    if (ce_asked && ce_asked_game == game) {
        return &ce_choice_store[ce_asked_store];
    }
    return NULL;
}

/* A villager the question's picture may show: listed and accepted by the
   game (New Believers: a believer). */
static int ce_choice_may_show(const ce_adapter *a, const unsigned char *record) {
    return record != NULL && a->listed(record) && (a->featurable == NULL || a->featurable(record));
}

/* The record index of the villager the question of `game` shows: the
   player's pick while its record still holds that same villager (the
   identity taken when queued) and the game may show them; otherwise a
   random living one (the game's own random routine); -1 when nobody can be
   shown. */
static int ce_choice_featured(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    const ce_choice *c = ce_choice_current(game);
    int count = 0;
    int pick;
    int i;
    if (a == NULL || c == NULL) {
        return -1;
    }
    if (c->featured_record > 0) {
        unsigned char *record = a->record(c->featured_record - 1);
        if (ce_choice_may_show(a, record) && ce_identity(a, record) == c->featured_identity) {
            return c->featured_record - 1;
        }
    }
    for (i = 0; i < a->record_count; ++i) {
        if (ce_choice_may_show(a, a->record(i))) {
            ++count;
        }
    }
    if (count == 0) {
        return -1;
    }
    pick = ce_random_below(a, count);
    for (i = 0; i < a->record_count; ++i) {
        if (ce_choice_may_show(a, a->record(i)) && pick-- == 0) {
            return i;
        }
    }
    return -1;
}

/* Roll one of `button`'s outcomes of `c`. */
static int ce_choice_roll(const ce_adapter *a, const ce_choice *c, int button) {
    int chances[CE_MAX_OUTCOMES];
    int count = c->outcome_count[button];
    int total = 0;
    int k;
    if (count < 1) {
        return -1;
    }
    if (count > CE_MAX_OUTCOMES) {
        count = CE_MAX_OUTCOMES;
    }
    for (k = 0; k < count; ++k) {
        chances[k] = c->outcomes[button][k].chance;
        if (chances[k] < 1) {
            chances[k] = 1;            /* refused when queued; never a 0 or negative share */
        }
        total += chances[k];
    }
    return ce_roll_index(chances, count, ce_random_below(a, total));
}

/* (a) THE QUESTION.  Called by a game's delivery hook where it calls
   ce_deliver: if a two-choice event is armed for `game`, take it and write
   the question popup's text (laid out with the question layout: the title
   leads it unless the game shows the title on its own, see
   ce_choice_title) into `text` (`size` bytes).  Returns 1 when the question
   is asked (the caller then shows the game's two-button popup with the
   labels ce_choice_label(game, 0) and (game, 1)), 0 otherwise. */
static int ce_choice_begin(int game, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    ce_layout l;
    if (a == NULL || !ce_choice_pending(game)) {
        return 0;
    }
    ce_armed = 0;
    ce_armed_is_choice = 0;
    ce_asked = 1;
    ce_asked_store = ce_armed_store;
    ce_asked_game = game;
    ce_asked_village = ce_armed_village;
    lstrcpynA(ce_asked_title, ce_armed_event.title, sizeof ce_asked_title);
    l = ce_question_layout(a);
    ce_compose_in(a, &l, ce_armed_event.title, &ce_armed_event, NULL, text, size);
    STORY_COUNT(delivered);
    return 1;
}

/* Whether `game`'s question is waiting for a click. */
static int ce_choice_asked(int game) {
    return ce_asked && ce_asked_game == game;
}

/* The asked question's button label (button 0 or 1), or NULL. */
static const char *ce_choice_label(int game, int button) {
    if (!ce_choice_asked(game) || button < 0 || button > 1) {
        return NULL;
    }
    return ce_choice_store[ce_asked_store].labels[button];
}

/* The asked question's title (for a game that shows the title on its own),
   or NULL. */
static const char *ce_choice_title(int game) {
    return ce_choice_asked(game) ? ce_asked_title : NULL;
}

/* (b) THE ANSWER.  Called by the hook, on the game's own thread, when the
   player clicks button 0 or 1 of the asked question: roll that button's
   outcome, apply its changes (ce_apply, as a plain event) and write the
   result popup's text (the result layout: the outcome's result text, then
   the usual outcome lines; when those do not fit, the result text alone)
   into `text`.  Returns 1 when done.  0 (nothing applied, nothing written)
   when no question of `game` is waiting, the button is not 0 / 1, or the
   village is no longer the one the event was queued in.  Answers once. */
static int ce_choice_resolve(int game, int button, char *text, int size) {
    const ce_adapter *a = ce_adapter_for(game);
    const ce_choice *c;
    const ce_outcome *o;
    ce_layout l;
    int k;
    if (a == NULL || !ce_choice_asked(game) || button < 0 || button > 1) {
        return 0;
    }
    ce_asked = 0;
    if (!story_village_is(game, &ce_asked_village)) {
        STORY_COUNT(discarded);
        return 0;
    }
    c = &ce_choice_store[ce_asked_store];
    k = ce_choice_roll(a, c, button);
    if (k < 0) {
        return 0;
    }
    o = &c->outcomes[button][k];
    ce_apply(a, &o->effects, &ce_last_result);
    l = ce_result_layout(a);
    if (!ce_compose_in(a, &l, ce_asked_title, &o->effects, &ce_last_result, text, size)) {
        /* The outcome lines do not fit: the result text was checked when
           the event was queued, so show it alone. */
        ce_compose_in(a, &l, ce_asked_title, &o->effects, NULL, text, size);
    }
    ce_last_button = button;
    ce_last_outcome = k;
    return 1;
}

/* The lines of `text` as a popup shows them. */
static int ce_text_lines(const char *text) {
    int n = 1;
    if (text[0] == '\0') {
        return 0;
    }
    for (; *text != '\0'; ++text) {
        if (*text == '\n') {
            ++n;
        }
    }
    return n;
}

/* The TALLEST result text `button` of `game`'s asked question can show:
   each outcome's result text with every outcome line its changes could
   print (the largest numbers), laid out as ce_choice_resolve lays it out --
   or, when those lines do not fit, the text alone padded to the result
   popup's height.  Written to `out`; returns its lines (0 when nothing is
   asked).  A game that sizes its popup before the click (VV1 / VV2: from
   the question alone; VV3-VV5: from the question and both results) sizes
   it with this, so the result shown after the click always fits. */
static int ce_choice_tallest(int game, int button, char *out, int size) {
    static char scratch[4096];
    const ce_adapter *a = ce_adapter_for(game);
    const ce_choice *c;
    ce_layout l;
    int best = 0;
    int k;
    if (size > 0) {
        out[0] = '\0';
    }
    if (a == NULL || !ce_choice_asked(game) || button < 0 || button > 1 || size <= 0) {
        return 0;
    }
    c = &ce_choice_store[ce_asked_store];
    l = ce_result_layout(a);
    for (k = 0; k < c->outcome_count[button] && k < CE_MAX_OUTCOMES; ++k) {
        const ce_event *e = &c->outcomes[button][k].effects;
        ce_result r;
        int lines;
        int i;
        int babies = 0;
        memset(&r, 0, sizeof r);
        for (i = 0; i < e->change_count; ++i) {
            if (e->changes[i].litter > 0) {
                babies = 1;
            }
        }
        if (e->food_op != CE_AMOUNT_NONE) {
            r.food_after = 9999999;
        }
        if (e->tech_op != CE_AMOUNT_NONE) {
            r.tech_after = 9999999;
        }
        if (e->spawn_groups > 0 || babies) {
            r.no_room_spawns = 999;
        }
        if (e->revive_count > 0) {
            r.no_room_revives = 999;
        }
        if (e->change_count > 0 || e->revive_count > 0) {
            r.skipped = 999;
        }
        if (ce_has_effects(e)) {
            r.refused = 999;
        }
        if (ce_compose_in(a, &l, ce_asked_title, e, &r, scratch, sizeof scratch)) {
            lines = ce_text_lines(scratch);
        } else {
            /* ce_choice_resolve then shows the text alone; the popup must
               still be as tall as the outcome lines would have made it. */
            ce_compose_in(a, &l, ce_asked_title, e, NULL, scratch, sizeof scratch);
            lines = l.lines;
            while (ce_text_lines(scratch) < lines && lstrlenA(scratch) + 2 < (int)sizeof scratch) {
                lstrcatA(scratch, "\n");
            }
        }
        if (lines > best) {
            best = lines;
            lstrcpynA(out, scratch, size);
        }
    }
    return best;
}

/* Pads `text` (`size` bytes) with line breaks to `lines` lines. */
static void ce_pad_lines(char *text, int size, int lines) {
    int n = lstrlenA(text);
    int have = ce_text_lines(text);
    while (have < lines && n + 1 < size) {
        text[n++] = '\n';
        text[n] = '\0';
        ++have;
    }
}
