/* Revive Buried/Disappeared Villagers (the owner, 2026-11-22), all five games.
   Included by vvfp_story_upgrades.c after story_time_skip.inc.

   The owner: an upgrade in the Tech screen's upgrades menu, costing 100,000
   tech points, that lists every buried villager AND every villager who
   vanished ("allow vanished people too"), with what the logs and graves
   record about them.  The player picks one; they come back as the SAME
   PERSON -- name (last name included), sex, parents, likes and dislikes,
   head, body, mask, custom title, skills -- reset to age 5 ("reset them to
   age.... 5? same person").  Their grave is removed.  Refused, with nothing
   charged, while the village is at its maximum population.  Repeatable: it
   can be bought again and again.

   Offered only with the row "Revive Buried/Disappeared Villagers", which
   ships the flag file RV_FLAG_FILE beside the companions (the Story / Cheat
   Upgrades row ships this DLL); the Origins companion's Tech menu shows the
   button while VvfpStoryReviveOffered says so (native/shared/story_bridge.h).

   WHO IS LISTED.  The village's own Deaths and Disappearances log (its save
   slot's folders, both layouts: native/shared/per_save.h; Start Over wipes
   them with the village, so every record there is this village's): every
   "Death <n>" and "Disappeared" record, the newest record of each person
   (name, sex, head, body, likes, dislikes) -- a villager revived before and
   dead again is one entry.  Not listed: anyone who is in the village now (a
   living villager or an unburied body with that whole identity: revived
   already, or Custom Island Event's Revive is the way for a body).  Listed but
   refused, with the reason: a record whose sex or looks the log does not
   hold, A New Home's Golden Child (only his puzzle makes one: the creator's
   family 0xC7), New Believers' puzzle Heathens (their role is the puzzle's),
   and New Believers' believers who "Left the tribe: became a Heathen" (or "an Isolan") (they
   are alive, among the Heathens).

   SKILLS.  A Death or Disappeared record has no skills; the Village History
   snapshots (written at every save) do.  The newest snapshot of the same
   name, sex, head and body no older than the age at death gives them; with
   none they are "unknown" and the game's own creator picks them.

   THE REVIVAL.  The game's own creator through the Custom Island Event's
   spawn (each adapter's `spawn`: the game's own room predicate and a free
   record first), at age 100 (five years: 20 age units a year), then the
   name, looks, likes, dislikes and skills written as the Custom Island
   Event's new villagers are, the parents as its Parents (A New Home: the Show
   Parents sidecar), the custom title and the mask.  The Births and
   Conceptions log gets an "Arrived" record at the next save with "How:
   Returned from the dead" (Cause of Death's VvfpCauseArrivedBy, as a Custom
   Island Event's villager), so the logs match the save: a quit without saving
   leaves neither the villager nor the record, and the grave is still in the
   save.  Nothing is counted as a birth or a death; the game's own statistics
   are not touched.

   THE GRAVE.  Matched by name and age at death (The Tree of Life and New
   Believers: head and body too), each grave to one record in log order:
     A New Home       world +0xA31C, 50 x 0x2C (name +0, age +0x24; age 0 is
                      empty): the slot zeroed in place.  Every reader goes by
                      the slot's own place (the 10 x 5 cemetery) and treats age
                      0 as empty; the burial takes the first empty slot.
     The Lost Children  world +0x2EB0C, 50 x 0x7C (name +0, epitaph +0x19, age
                      +0x74): the same.
     The Secret City  the Roster of the Dead 0x5973F0 +0x974, 500 x 0x30 (age
                      +0x1C), and the first 50 entries' gravestones 0x5973F0,
                      0x2C each (+0 its entry, -1 none; +4 value; +8 epitaph):
                      every count and the save's loader stop at the first
                      empty entry, so the later entries move down one place,
                      their stones with them (+0 renumbered), the last entry is
                      zeroed; a 51st entry moving to place 49 gets the stone
                      the writer 0x454FF0 would give it (its epitaph by the
                      writer's own rule).  Refused while a burial is under way
                      (0x5973F0 +0x6810).
     The Tree of Life / New Believers  0x5025C8 / 0x5481A8, 500 x 0x5C (age
                      +0x1C, head +0x20, body +0x24, epitaph +0x38): later
                      entries move down one place, the last zeroed.
   A record whose grave is not found (the game removed the body, the
   graveyard was full, a Disappeared record) has no grave to remove.

   PRICE (the owner, 2026-11-23).  As the other story upgrades: 100,000 tech points while Story / Cheat
   Upgrades cost Tech Points is ticked (the Story companion's `charges`), free while it is not.  Taken
   only once the villager is back; never more than the village has (with fewer it is refused). */

#define RV_PRICE 100000               /* with Story / Cheat Upgrades cost Tech Points ticked; else 0 (rv_price) */
#define RV_AGE 100                    /* five years */
#define RV_MAX 4096                   /* people kept: past it the OLDEST record goes (the newest always show) */
#define RV_PREFS 64                   /* likes (or dislikes) kept per person (The Secret City holds 62) */
#define RV_NAME 32
#define RV_FLAG_FILE "VVFP Revive From Graves.txt"
/* New Believers: a Heathen whose Death or Disappeared record says "Faction: Heathen" / "Isolan" (every log records
   the Heathens since PR #850) comes back as a Heathen in the camp -- the same person, their own faction -- through
   the game's own Heathen creator 0x46FD20 as the Custom Island Event makes a Heathen (an ordinary Heathen, faith
   -55).  0: they come back as believers.  The owner decides (2026-11-23 question). */
#define RV_HEATHENS_STAY_HEATHENS 1

enum { RV_DEATH = 1, RV_GONE = 2 };

/* What a purchase came to (the probes' answer). */
enum {
    RV_DONE = 1,
    RV_NO_ROOM = -1,
    RV_NO_TECH = -2,
    RV_NOT_REVIVABLE = -3,
    RV_IN_VILLAGE = -4,
    RV_NO_VILLAGE = -5,
    RV_BUSY = -6,
    RV_NOT_MADE = -7
};

typedef struct {
    int kind;                         /* RV_DEATH / RV_GONE */
    int number;                       /* "Death <n>"; 0 for Disappeared */
    char name[RV_NAME];
    int age;                          /* at death, age units; -1 unknown */
    int sex;                          /* STORY_SEX_*; 0 unknown */
    int head, body;                   /* -1 unknown */
    char *cause;                      /* Cause of death / What happened, whole (process heap; NULL unknown) */
    char grave_line[48];              /* the Death record's "Grave:" */
    char epitaph[96];                 /* the longest a grave or the epitaphs file keeps: 80 (grave_backfill.h) */
    char title[32];                   /* Custom title */
    char special[48];                 /* Special villager */
    int mask;                         /* 0 none, 1..5 (story_common.inc STORY_MASK_NAMES) */
    int heathen;                      /* New Believers: the record says "Faction: Heathen" (or "Isolan") */
    short like_count, dislike_count;
    unsigned char likes[RV_PREFS], dislikes[RV_PREFS];
    int prefs_known;                  /* both lists were in the record */
    char father[RV_NAME], mother[RV_NAME];
    int father_head, father_body, mother_head, mother_body;   /* CE_KEEP unknown */
    int skills_known;
    int skills[CE_SKILLS];
    int grave;                        /* the grave's place, -1 none */
    const char *refusal;              /* why this person can not come back; NULL can */
    int listed;                       /* 0: in the village (not shown) or replaced by a newer record */
} rv_person;

static rv_person *rv_people;         /* grown on the process heap (rv_room), up to RV_MAX */
static int rv_people_cap;
static int *rv_order;                 /* the list's rows: listed people, the newest first (rv_people_cap) */
static int rv_count;

/* Every buffer wsprintfA writes here holds RV_LINE bytes: wsprintfA never writes more than 1,024, so no format
   (a translation included, each at most a few hundred bytes with its values) can overflow it (Codex, #851).  A
   list that can be longer -- a villager's likes or dislikes: The Lost Children keeps 62 of each -- is never
   formatted: its words are appended (rv_add_s), whole. */
#define RV_LINE 1100
#define RV_DETAILS 16384             /* a whole details text: 2 x 62 words and every other line, with room */

/* What a revival costs in `game` now: RV_PRICE with "cost Tech Points" ticked, else 0. */
static int rv_price(int game) {
    return game >= 1 && game <= 5 && charges[game] ? RV_PRICE : 0;
}

/* That price as the boxes print it ("100,000" or "0"). */
static const char *rv_price_text(int game) {
    static char text[16];
    int price = rv_price(game);
    if (price >= 1000) {
        wsprintfA(text, "%d,%03d", price / 1000, price % 1000);
    } else {
        wsprintfA(text, "%d", price);
    }
    return text;
}

/* Room for one more person: the arrays grown (doubling, up to RV_MAX); at RV_MAX the oldest record goes, so the
   newest deaths are always listed (Codex, #851).  The new person's place, or NULL with no memory at all. */
/* `p`'s cause given back to the heap. */
static void rv_forget(rv_person *p) {
    if (p->cause != NULL) {
        HeapFree(GetProcessHeap(), 0, p->cause);
        p->cause = NULL;
    }
}

/* Everyone forgotten (a new list). */
static void rv_clear(void) {
    int i;
    for (i = 0; i < rv_count; ++i) {
        rv_forget(&rv_people[i]);
    }
    rv_count = 0;
}

/* A copy of `text` on the process heap, whole (NULL with no memory). */
static char *rv_dup(const char *text) {
    int n = lstrlenA(text);
    char *copy = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)n + 1);
    if (copy != NULL) {
        memcpy(copy, text, (size_t)n + 1);
    }
    return copy;
}

static rv_person *rv_room(void) {
    if (rv_count >= rv_people_cap && rv_people_cap < RV_MAX) {
        int cap = rv_people_cap > 0 ? rv_people_cap * 2 : 64;
        void *people, *order;
        if (cap > RV_MAX) {
            cap = RV_MAX;
        }
        people = rv_people != NULL
                     ? HeapReAlloc(GetProcessHeap(), 0, rv_people, (SIZE_T)cap * sizeof(rv_person))
                     : HeapAlloc(GetProcessHeap(), 0, (SIZE_T)cap * sizeof(rv_person));
        if (people != NULL) {
            rv_people = (rv_person *)people;
            order = rv_order != NULL ? HeapReAlloc(GetProcessHeap(), 0, rv_order, (SIZE_T)cap * sizeof(int))
                                     : HeapAlloc(GetProcessHeap(), 0, (SIZE_T)cap * sizeof(int));
            if (order != NULL) {
                rv_order = (int *)order;
                rv_people_cap = cap;
            }
        }
    }
    if (rv_people == NULL || rv_people_cap == 0) {
        return NULL;
    }
    if (rv_count >= rv_people_cap) {
        rv_forget(&rv_people[0]);
        memmove(rv_people, rv_people + 1, (size_t)(rv_count - 1) * sizeof(rv_person));
        --rv_count;
    }
    return &rv_people[rv_count++];
}
static int rv_game;
#ifdef VVFP_TEST
static int rv_test_offered = -1;      /* TEST build: -1 the flag file decides, else this */
#endif

/* ---- Text helpers ------------------------------------------------------------ */

/* The next line of `*cursor` (up to `end`) without its CR/LF in `out` (cut to `size`). 0 at the end. */
static int rv_line(const char **cursor, const char *end, char *out, int size) {
    const char *p = *cursor;
    int n = 0;
    if (p >= end) {
        return 0;
    }
    while (p < end && *p != '\n') {
        if (*p != '\r' && n < size - 1) {
            out[n++] = *p;
        }
        ++p;
    }
    out[n] = '\0';
    *cursor = p < end ? p + 1 : p;
    return 1;
}

/* "  Key: value" -> value when `line` starts with `prefix` ("  Key: "). */
static const char *rv_field(const char *line, const char *prefix) {
    int n = lstrlenA(prefix);
    return strncmp(line, prefix, (size_t)n) == 0 ? line + n : NULL;
}

static int rv_number(const char *text, int *out) {
    int value = 0, digits = 0, negative = 0;
    while (*text == ' ') {
        ++text;
    }
    if (*text == '-') {
        negative = 1;
        ++text;
    }
    while (*text >= '0' && *text <= '9' && digits < 9) {
        value = value * 10 + (*text - '0');
        ++text;
        ++digits;
    }
    if (digits == 0) {
        return 0;
    }
    *out = negative ? -value : value;
    return 1;
}

/* The game's own index of preference word `word` (its own list, comma separated), -1 when none. */
static int rv_pref_index(const ce_adapter *a, const char *word, int length) {
    const char *list = a->pref_list;
    int index = 0;
    while (*list != '\0') {
        const char *stop = list;
        while (*stop != '\0' && *stop != ',') {
            ++stop;
        }
        if ((int)(stop - list) == length && strncmp(list, word, (size_t)length) == 0) {
            return index;
        }
        ++index;
        list = *stop == ',' ? stop + 1 : stop;
    }
    return -1;
}

/* A "Likes:" / "Dislikes:" value ("(none)", or the words joined with ", ") as the game's indices.  0 when a word
   is not the game's (the record is then not trusted for them). */
static int rv_prefs(const ce_adapter *a, const char *text, unsigned char *out, short *count) {
    *count = 0;
    if (lstrcmpA(text, "(none)") == 0 || text[0] == '\0') {
        return 1;
    }
    while (*text != '\0') {
        const char *stop = strstr(text, ", ");
        int length = stop != NULL ? (int)(stop - text) : lstrlenA(text);
        int index = rv_pref_index(a, text, length);
        if (index < 0 || index > 255) {
            return 0;
        }
        if (*count < RV_PREFS) {
            out[(*count)++] = (unsigned char)index;
        }
        text += length;
        if (stop != NULL) {
            text += 2;
        }
    }
    return 1;
}

static int rv_mask_value(const char *text) {
    int k;
    for (k = 1; k <= 5; ++k) {
        if (lstrcmpA(text, STORY_MASK_NAMES[k]) == 0) {
            return k;
        }
    }
    return 0;
}

static void rv_copy(char *out, int size, const char *text) {
    lstrcpynA(out, text, size);
}

/* ---- The Deaths and Disappearances log ----------------------------------------- */

static void rv_begin(rv_person *p, int kind, int number) {
    memset(p, 0, sizeof *p);
    p->kind = kind;
    p->number = number;
    p->age = -1;
    p->head = p->body = -1;
    p->father_head = p->father_body = p->mother_head = p->mother_body = CE_KEEP;
    p->grave = -1;
    p->listed = 1;
}

static int rv_same_person(const rv_person *x, const rv_person *y);

/* The record just read (the last one) closed: an older record of the same person is dropped, so each person is
   one entry -- their newest record -- however long the log (Codex, #851). */
static void rv_close(rv_person *p, int prefs_known) {
    int i;
    p->prefs_known = prefs_known;
    for (i = 0; i < rv_count - 1; ++i) {
        if (rv_same_person(&rv_people[i], p)) {
            rv_forget(&rv_people[i]);
            memmove(&rv_people[i], &rv_people[i + 1], (size_t)(rv_count - 1 - i) * sizeof(rv_person));
            --rv_count;
            return;
        }
    }
}

/* Every Death and Disappeared record of `text` (a whole log file, NUL-terminated), appended in order. */
static void rv_parse_deaths(const ce_adapter *a, const char *text, int length) {
    const char *cursor = text, *end = text + length;
    static char line[8192];          /* a Custom Island Event's cause is up to 4,095 characters */
    rv_person *p = NULL;
    int parent = 0;                   /* 1 father, 2 mother: the "Head:" / "Body:" under it */
    int likes_seen = 0, dislikes_seen = 0, likes_ok = 1;
    while (rv_line(&cursor, end, line, (int)sizeof line)) {
        const char *v;
        if (line[0] != ' ') {
            if (p != NULL) {
                rv_close(p, likes_seen && dislikes_seen && likes_ok);
                p = NULL;
            }
            parent = 0;
            likes_seen = dislikes_seen = 0;
            likes_ok = 1;
            if (strncmp(line, "Death ", 6) == 0 && line[6] >= '0' && line[6] <= '9') {
                int number = 0;
                (void)rv_number(line + 6, &number);
                p = rv_room();
                if (p != NULL) {
                    rv_begin(p, RV_DEATH, number);
                }
            } else if (strncmp(line, "Disappeared", 11) == 0) {
                p = rv_room();
                if (p != NULL) {
                    rv_begin(p, RV_GONE, 0);
                }
            }
            continue;
        }
        if (p == NULL) {
            continue;
        }
        if ((v = rv_field(line, "  Name: ")) != NULL) {
            rv_copy(p->name, RV_NAME, v);
        } else if ((v = rv_field(line, "  Age at death: ")) != NULL || (v = rv_field(line, "  Age: ")) != NULL) {
            (void)rv_number(v, &p->age);
        } else if ((v = rv_field(line, "  Sex: ")) != NULL) {
            p->sex = lstrcmpA(v, "Male") == 0 ? STORY_SEX_MALE : lstrcmpA(v, "Female") == 0 ? STORY_SEX_FEMALE : 0;
        } else if ((v = rv_field(line, "  Cause of death: ")) != NULL || (v = rv_field(line, "  What happened: ")) != NULL) {
            rv_forget(p);
            p->cause = rv_dup(v);
        } else if ((v = rv_field(line, "  Grave: ")) != NULL) {
            rv_copy(p->grave_line, (int)sizeof p->grave_line, v);
        } else if ((v = rv_field(line, "  Epitaph: ")) != NULL) {
            rv_copy(p->epitaph, (int)sizeof p->epitaph, v);
        } else if ((v = rv_field(line, "  Custom title: ")) != NULL) {
            rv_copy(p->title, (int)sizeof p->title, v);
        } else if ((v = rv_field(line, "  Faction: ")) != NULL) {
            p->heathen = lstrcmpA(v, "Heathen") == 0 || lstrcmpA(v, "Isolan") == 0;
        } else if ((v = rv_field(line, "  Special villager: ")) != NULL) {
            rv_copy(p->special, (int)sizeof p->special, v);
        } else if ((v = rv_field(line, "  Mask: ")) != NULL) {
            p->mask = rv_mask_value(v);
        } else if ((v = rv_field(line, "  Head: ")) != NULL) {
            if (!rv_number(v, &p->head)) p->head = -1;
        } else if ((v = rv_field(line, "  Body: ")) != NULL) {
            if (!rv_number(v, &p->body)) p->body = -1;
        } else if ((v = rv_field(line, "  Likes: ")) != NULL) {
            likes_seen = 1;
            likes_ok &= rv_prefs(a, v, p->likes, &p->like_count);
        } else if ((v = rv_field(line, "  Dislikes: ")) != NULL) {
            dislikes_seen = 1;
            likes_ok &= rv_prefs(a, v, p->dislikes, &p->dislike_count);
        } else if ((v = rv_field(line, "    Father: ")) != NULL) {
            parent = 1;
            rv_copy(p->father, RV_NAME, v);
        } else if ((v = rv_field(line, "    Mother: ")) != NULL) {
            parent = 2;
            rv_copy(p->mother, RV_NAME, v);
        } else if ((v = rv_field(line, "      Head: ")) != NULL && parent != 0) {
            (void)rv_number(v, parent == 1 ? &p->father_head : &p->mother_head);
        } else if ((v = rv_field(line, "      Body: ")) != NULL && parent != 0) {
            (void)rv_number(v, parent == 1 ? &p->father_body : &p->mother_body);
        }
    }
    if (p != NULL) {
        rv_close(p, likes_seen && dislikes_seen && likes_ok);
    }
}

/* ---- The Village History: the skills ------------------------------------------- */

static int rv_skill_index(const ce_adapter *a, const char *word, int length) {
    /* The Village History's own labels (population_export.c SKILL_NAMES_VV1): A New Home's Parenting is printed
       "Breeding" (Codex, #851). */
    if (length == 8 && strncmp(word, "Breeding", 8) == 0) {
        word = "Parenting";
        length = 9;
    }
    int k;
    for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
        if (lstrlenA(a->skill_names[k]) == length && strncmp(a->skill_names[k], word, (size_t)length) == 0) {
            return k;
        }
    }
    return -1;
}

/* One snapshot entry read: every listed person it may be (same name, sex, head and body, no older than at death)
   takes its skills -- the files are read oldest first, so the newest such entry is what stays. */
static void rv_history_entry(const ce_adapter *a, const char *name, int age, int sex, int head, int body,
                             const int *skills, int skills_seen) {
    int i, k;
    if (name[0] == '\0' || skills_seen != (1 << (a->skill_count < CE_SKILLS ? a->skill_count : CE_SKILLS)) - 1) {
        return;
    }
    for (i = 0; i < rv_count; ++i) {
        rv_person *p = &rv_people[i];
        if (p->sex == sex && p->head == head && p->body == body && p->age >= 0 && age <= p->age
            && lstrcmpA(p->name, name) == 0) {
            for (k = 0; k < CE_SKILLS; ++k) {
                p->skills[k] = skills[k];
            }
            p->skills_known = 1;
        }
    }
}

static void rv_parse_history(const ce_adapter *a, const char *text, int length) {
    const char *cursor = text, *end = text + length;
    char line[300], name[RV_NAME];
    int open = 0, age = -1, sex = 0, head = -1, body = -1, skills_seen = 0, in_skills = 0;
    int skills[CE_SKILLS];
    memset(skills, 0, sizeof skills);
    name[0] = '\0';
    for (;;) {
        int more = rv_line(&cursor, end, line, (int)sizeof line);
        const char *v;
        if (!more || line[0] != ' ') {
            if (open) {
                rv_history_entry(a, name, age, sex, head, body, skills, skills_seen);
            }
            if (!more) {
                break;
            }
            open = strncmp(line, "Villager ", 9) == 0;
            name[0] = '\0';
            age = -1;
            sex = 0;
            head = body = -1;
            skills_seen = in_skills = 0;
            memset(skills, 0, sizeof skills);
            continue;
        }
        if (!open) {
            continue;
        }
        if ((v = rv_field(line, "  Name: ")) != NULL) {
            rv_copy(name, RV_NAME, v);
        } else if ((v = rv_field(line, "  Age: ")) != NULL) {
            (void)rv_number(v, &age);
        } else if ((v = rv_field(line, "  Sex: ")) != NULL) {
            sex = lstrcmpA(v, "Male") == 0 ? STORY_SEX_MALE : lstrcmpA(v, "Female") == 0 ? STORY_SEX_FEMALE : 0;
        } else if ((v = rv_field(line, "  Head: ")) != NULL) {
            (void)rv_number(v, &head);
        } else if ((v = rv_field(line, "  Body: ")) != NULL) {
            (void)rv_number(v, &body);
        } else if (lstrcmpA(line, "  Skills:") == 0) {
            in_skills = 1;
        } else if (in_skills && strncmp(line, "    ", 4) == 0) {
            const char *word = line + 4;
            int word_length = 0, k, value;
            while (word[word_length] != '\0' && word[word_length] != ' ') {
                ++word_length;
            }
            k = rv_skill_index(a, word, word_length);
            if (k >= 0 && rv_number(word + word_length, &value)) {
                skills[k] = value;
                skills_seen |= 1 << k;
            }
        } else {
            in_skills = 0;
        }
    }
}

/* ---- The graves ----------------------------------------------------------------- */

typedef struct {
    unsigned char *entries;           /* the first entry */
    unsigned int stride;
    int count;
    unsigned int name_bytes;
    unsigned int age;                 /* the age field (0 = an empty place) */
    unsigned int head, body;          /* 0: not kept */
    unsigned int epitaph, epitaph_bytes;
    int contiguous;                   /* 1: every reader stops at the first empty place (VV3-VV5) */
} rv_yard;

#define RV_VV3_DEAD 0x5973F0u

static int rv_graveyard(int game, rv_yard *y) {
    memset(y, 0, sizeof *y);
    switch (game) {
    case 1: {
        unsigned char *world = VV1_WORLD();
        if (world == NULL) return 0;
        y->entries = world + 0xA31C; y->stride = 0x2C; y->count = 50; y->name_bytes = 0x1C; y->age = 0x24;
        return 1;
    }
    case 2: {
        unsigned char *world = VV2_WORLD();
        if (world == NULL) return 0;
        y->entries = world + 0x2EB0C; y->stride = 0x7C; y->count = 50; y->name_bytes = 0x19; y->age = 0x74;
        y->epitaph = 0x19; y->epitaph_bytes = 0x41;
        return 1;
    }
    case 3:
        y->entries = (unsigned char *)(uintptr_t)(RV_VV3_DEAD + 0x974u); y->stride = 0x30; y->count = 500;
        y->name_bytes = 0x19; y->age = 0x1C; y->contiguous = 1;
        return 1;
    case 4:
    case 5:
        y->entries = (unsigned char *)(uintptr_t)(game == 4 ? 0x5025C8u : 0x5481A8u); y->stride = 0x5C;
        y->count = 500; y->name_bytes = 0x19; y->age = 0x1C; y->head = 0x20; y->body = 0x24;
        y->epitaph = 0x38; y->epitaph_bytes = 0x20; y->contiguous = 1;
        return 1;
    default:
        return 0;
    }
}

static unsigned char *rv_place(const rv_yard *y, int place) {
    return y->entries + (size_t)place * y->stride;
}

static int rv_grave_age(const rv_yard *y, int place) {
    return *(const int *)(rv_place(y, place) + y->age);
}

/* Whether grave `place` is `p`'s: the name, the age at death (and the looks where the grave keeps them). */
static int rv_grave_is(const rv_yard *y, int place, const rv_person *p) {
    const unsigned char *g = rv_place(y, place);
    char name[RV_NAME];
    unsigned int k;
    if (rv_grave_age(y, place) == 0 || p->age <= 0 || rv_grave_age(y, place) != p->age) {
        return 0;
    }
    for (k = 0; k + 1 < sizeof name && k < y->name_bytes && g[k] != 0; ++k) {
        name[k] = (char)g[k];
    }
    name[k] = '\0';
    if (lstrcmpA(name, p->name) != 0) {
        return 0;
    }
    if (y->head != 0u && (*(const int *)(g + y->head) != p->head || *(const int *)(g + y->body) != p->body)) {
        return 0;
    }
    return 1;
}

/* The epitaph the grave shows now (an edited one included). */
static void rv_grave_epitaph(int game, const rv_yard *y, int place, char *out, int size) {
    const unsigned char *text = NULL;
    unsigned int cap = 0, k;
    if (game == 3) {
        if (place < 50) {
            text = (const unsigned char *)(uintptr_t)(RV_VV3_DEAD + (unsigned int)place * 0x2Cu + 8u);
            cap = 0x20;
        }
    } else if (y->epitaph != 0u) {
        text = rv_place(y, place) + y->epitaph;
        cap = y->epitaph_bytes;
    }
    if (text == NULL) {
        return;
    }
    for (k = 0; (int)k + 1 < size && k < cap && text[k] != 0; ++k) {
        out[k] = (char)(text[k] >= 0x20 ? text[k] : '?');
    }
    out[k] = '\0';
}

/* The Secret City: the writer's own epitaph for the entry now at `place` (0x454FF0: 0x4550AC .. 0x4551AF), into its
   stone.  The text table 0x42F740(), its string 0x42F190(id); the coin 0x4032D0(100) >= 50. */
typedef int (__cdecl *rv_cdecl1)(int);
typedef void *(__cdecl *rv_cdecl0)(void);
static void rv_vv3_stone(int place) {
    unsigned char *entry = (unsigned char *)(uintptr_t)(RV_VV3_DEAD + 0x974u + (unsigned int)place * 0x30u);
    unsigned char *stone = (unsigned char *)(uintptr_t)(RV_VV3_DEAD + (unsigned int)place * 0x2Cu);
    static const int BY_JOB[5] = { 0x2D7, 0x2DB, 0x2DD, 0x2D9, 0x2DF };
    int job = *(const int *)(entry + 0x20);
    int id;
    const char *text;
    void *table;
    int coin = ((rv_cdecl1)(uintptr_t)0x4032D0u)(100) >= 50;
    if (*(const int *)(entry + 0x1C) < 0x168) {
        id = 0x2E1 + coin;
    } else if (entry[0x28] != 0) {
        id = 0x2E4;
    } else if (entry[0x29] != 0) {
        id = 0x2E3;
    } else if (job >= 0 && job <= 4) {
        id = BY_JOB[job] + coin;
    } else {
        id = 0x2D6;
    }
    memset(stone, 0, 0x2C);
    *(int *)stone = place;
    *(int *)(stone + 4) = *(const int *)(entry + 0x24);
    table = ((rv_cdecl0)(uintptr_t)0x42F740u)();
    text = table != NULL ? (const char *)(uintptr_t)TC1(0x42F190u, table, id) : NULL;
    if (text != NULL) {
        lstrcpynA((char *)stone + 8, text, 0x20);
    }
    *(int *)(uintptr_t)(RV_VV3_DEAD + 0x6734u + (unsigned int)place * 4u) = -1;
}

/* The grave at `place` taken away the way each game's readers stay right (see the top of this file).  1 done. */
static int rv_grave_remove(int game, int place) {
    rv_yard y;
    int n, i;
    if (!rv_graveyard(game, &y) || place < 0 || place >= y.count || rv_grave_age(&y, place) == 0) {
        return 0;
    }
    if (!y.contiguous) {
        memset(rv_place(&y, place), 0, y.stride);
        return 1;
    }
    for (n = 0; n < y.count && rv_grave_age(&y, n) != 0; ++n) {
    }
    if (place >= n) {
        return 0;                     /* past the run: no reader sees it (never so in a game's own data) */
    }
    if (game == 3) {
        unsigned char *base = (unsigned char *)(uintptr_t)RV_VV3_DEAD;
        int *transient = (int *)(base + 0x6734);
        int stones = 0;
        while (stones < 50 && *(const int *)(base + (unsigned int)stones * 0x2Cu) >= 0) {
            ++stones;
        }
        if (place < stones) {
            if (transient[place] != -1 && *(int *)(base + 0x6810) > 0) {
                --*(int *)(base + 0x6810);
            }
            for (i = place; i < stones - 1; ++i) {
                memcpy(base + (unsigned int)i * 0x2Cu, base + (unsigned int)(i + 1) * 0x2Cu, 0x2C);
                *(int *)(base + (unsigned int)i * 0x2Cu) = i;
                transient[i] = transient[i + 1];
            }
        }
        memmove(rv_place(&y, place), rv_place(&y, place + 1), (size_t)(n - 1 - place) * y.stride);
        memset(rv_place(&y, n - 1), 0, y.stride);
        if (place < stones) {
            int last = stones - 1;
            if (n > 50 && last == 49) {
                rv_vv3_stone(49);     /* the 51st entry is the 50th now: its stone, as the writer gives one */
            } else {
                if (transient[last] != -1 && *(int *)(base + 0x6810) > 0) {
                    --*(int *)(base + 0x6810);
                }
                memset(base + (unsigned int)last * 0x2Cu, 0, 0x2C);
                *(int *)(base + (unsigned int)last * 0x2Cu) = -1;
                transient[last] = -1;
            }
        }
        return 1;
    }
    memmove(rv_place(&y, place), rv_place(&y, place + 1), (size_t)(n - 1 - place) * y.stride);
    memset(rv_place(&y, n - 1), 0, y.stride);
    return 1;
}

/* ---- Who is listed ----------------------------------------------------------------- */

/* Whether a record in the village now (alive, or a body awaiting burial) is this person. */
static int rv_in_village(const ce_adapter *a, const rv_person *p) {
    int i, k;
    for (i = 0; i < a->record_count; ++i) {
        const unsigned char *r = a->record(i);
        char name[RV_NAME];
        int like_count = 0, dislike_count = 0;
        const int *likes, *dislikes;
        if (r == NULL || !(a->listed(r) || ((a->caps & CAP_REVIVE) && a->skeleton(r)))) {
            continue;
        }
        if (ce_sex(a, r) != p->sex || *(const int *)(r + a->off_head) != p->head
            || *(const int *)(r + a->off_body) != p->body) {
            continue;
        }
        ce_copy_name(name, RV_NAME, r + a->off_name, a->name_bytes);
        if (lstrcmpA(name, p->name) != 0) {
            continue;
        }
        if (!p->prefs_known) {
            return 1;
        }
        likes = (const int *)(r + a->off_likes);
        dislikes = (const int *)(r + a->off_dislikes);
        for (k = 0; k < a->pref_slots; ++k) {
            like_count += likes[k] >= 0;
            dislike_count += dislikes[k] >= 0;
        }
        if (like_count == (p->like_count < a->pref_slots ? p->like_count : a->pref_slots)
            && dislike_count == (p->dislike_count < a->pref_slots ? p->dislike_count : a->pref_slots)) {
            int same = 1;
            for (k = 0; k < p->like_count && k < a->pref_slots && same; ++k) {
                int j, found = 0;
                for (j = 0; j < a->pref_slots; ++j) found |= likes[j] == p->likes[k];
                same = found;
            }
            for (k = 0; k < p->dislike_count && k < a->pref_slots && same; ++k) {
                int j, found = 0;
                for (j = 0; j < a->pref_slots; ++j) found |= dislikes[j] == p->dislikes[k];
                same = found;
            }
            if (same) {
                return 1;
            }
        }
    }
    return 0;
}

static int rv_same_person(const rv_person *x, const rv_person *y) {
    return x->sex == y->sex && x->head == y->head && x->body == y->body && lstrcmpA(x->name, y->name) == 0
        && x->like_count == y->like_count && x->dislike_count == y->dislike_count
        && memcmp(x->likes, y->likes, (size_t)x->like_count) == 0
        && memcmp(x->dislikes, y->dislikes, (size_t)x->dislike_count) == 0;
}

/* Why a person can not come back, each its own row of the translations template (the English is what
   rv_person.refusal points at; rv_why shows it in the player's language). */
static const char *const RV_WHY[][2] = {
    { "vvfp.story/story_revive.RV_WHY.s0", "the log does not say who they were (name or sex)" },
    { "vvfp.story/story_revive.RV_WHY.s1", "the log does not hold their looks" },
    { "vvfp.story/story_revive.RV_WHY.s2", "the log does not hold their likes and dislikes" },
    { "vvfp.story/story_revive.RV_WHY.s3", "their name is longer than the game holds" },
    { "vvfp.story/story_revive.RV_WHY.s4", "only the Golden Child puzzle makes the Golden Child" },
    { "vvfp.story/story_revive.RV_WHY.s5", "a Heathen of the puzzles keeps the puzzle's role" },
    { "vvfp.story/story_revive.RV_WHY.s6", "they did not die: they live among the Heathens" },
};
enum { RV_WHY_WHO, RV_WHY_LOOKS, RV_WHY_PREFS, RV_WHY_NAME, RV_WHY_GOLDEN, RV_WHY_PUZZLE_HEATHEN, RV_WHY_HEATHEN };

static const char *rv_why(const char *refusal) {
    int k;
    for (k = 0; k < (int)(sizeof RV_WHY / sizeof RV_WHY[0]); ++k) {
        if (refusal == RV_WHY[k][1]) {
            return vvfp_tr(RV_WHY[k][0], RV_WHY[k][1], 200);
        }
    }
    return refusal;
}

/* New Believers: a believer's Disappeared record for leaving the tribe for the Heathens, in either wording
   the logs use (src/vv_log_additions.py LEFT_RECORDS): "Left the tribe: became a Heathen", or "... became an
   Isolan" with Guardians of Isola (Codex, #851).  They are alive among the Heathens: never listed as one who
   can come back, whatever their record says now. */
static int rv_left_for_the_heathens(const char *what) {
    return what != NULL && (strstr(what, "Left the tribe: became a Heathen") != NULL
                            || strstr(what, "Left the tribe: became an Isolan") != NULL);
}

/* After the logs are read: the graves matched, the refusals and who is shown. */
static void rv_settle(int game, const ce_adapter *a) {
    rv_yard y;
    unsigned char claimed[500];
    int have_yard = rv_graveyard(game, &y);
    int i, j, place;
    memset(claimed, 0, sizeof claimed);
    for (i = 0; i < rv_count; ++i) {
        rv_person *p = &rv_people[i];
        /* each grave to one Death record, in log order */
        if (have_yard && p->kind == RV_DEATH && strncmp(p->grave_line, "no grave", 8) != 0) {
            for (place = 0; place < y.count; ++place) {
                if (!claimed[place] && rv_grave_is(&y, place, p)) {
                    claimed[place] = 1;
                    p->grave = place;
                    rv_grave_epitaph(game, &y, place, p->epitaph, (int)sizeof p->epitaph);
                    break;
                }
            }
        }
    }
    for (i = 0; i < rv_count; ++i) {
        rv_person *p = &rv_people[i];
        for (j = i + 1; j < rv_count && p->listed; ++j) {
            if (rv_same_person(p, &rv_people[j])) {
                p->listed = 0;            /* a newer record of the same person (revived, then gone again) */
            }
        }
        if (p->listed && p->sex != 0 && p->head >= 0 && rv_in_village(a, p)) {
            p->listed = 0;                /* here now */
        }
        if (p->name[0] == '\0' || p->sex == 0) {
            p->refusal = RV_WHY[RV_WHY_WHO][1];
        } else if (p->head < 0 || p->head >= a->head_count || p->body < 0 || p->body >= a->body_count) {
            p->refusal = RV_WHY[RV_WHY_LOOKS][1];
        } else if (!p->prefs_known) {
            p->refusal = RV_WHY[RV_WHY_PREFS][1];
        } else if (lstrlenA(p->name) > a->name_room) {
            p->refusal = RV_WHY[RV_WHY_NAME][1];
        } else if (game == 1 && lstrcmpA(p->special, "Golden Child") == 0) {
            p->refusal = RV_WHY[RV_WHY_GOLDEN][1];
        } else if (game == 5 && strncmp(p->special, "Heathen ", 8) == 0) {
            p->refusal = RV_WHY[RV_WHY_PUZZLE_HEATHEN][1];
        } else if (game == 5 && p->kind == RV_GONE && rv_left_for_the_heathens(p->cause)) {
            p->refusal = RV_WHY[RV_WHY_HEATHEN][1];
        }
    }
}

/* ---- Reading the logs ------------------------------------------------------------- */

static char *rv_text;
static unsigned int rv_text_cap;

/* A whole file, NUL-terminated, into rv_text (grown).  Its length, -1 when it can not be read. */
static int rv_read(const wchar_t *path) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD high = 0, size, got = 0;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return -1;
    }
    size = GetFileSize(h, &high);
    if (high != 0 || size == INVALID_FILE_SIZE || size > 0x10000000u) {
        CloseHandle(h);
        return -1;
    }
    if (size + 1 > rv_text_cap) {
        char *more = (char *)(rv_text != NULL ? HeapReAlloc(GetProcessHeap(), 0, rv_text, size + 1)
                                              : HeapAlloc(GetProcessHeap(), 0, size + 1));
        if (more == NULL) {
            CloseHandle(h);
            return -1;
        }
        rv_text = more;
        rv_text_cap = size + 1;
    }
    ok = ReadFile(h, rv_text, size, &got, NULL) && got == size;
    CloseHandle(h);
    if (!ok) {
        return -1;
    }
    rv_text[size] = '\0';
    return (int)size;
}

/* The number a log file's name ends with ("... Log 12.txt" -> 12), 0 without one. */
static int rv_file_number(const wchar_t *name) {
    int n = lstrlenW(name), value = 0, scale = 1;
    if (n > 4) {
        n -= 4;                       /* ".txt" */
    }
    while (n > 0 && name[n - 1] >= L'0' && name[n - 1] <= L'9' && scale < 100000000) {
        value += (name[n - 1] - L'0') * scale;
        scale *= 10;
        --n;
    }
    return value;
}

#define RV_FILES 256
/* Every "*.txt" of `folder`, by the number its name ends with (oldest first), each handed to `visit`. */
static void rv_each_file(const ce_adapter *a, const wchar_t *folder, void (*visit)(const ce_adapter *, const char *, int)) {
    static wchar_t names[RV_FILES][MAX_PATH];
    static int numbers[RV_FILES];
    wchar_t pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAW found;
    HANDLE find;
    int count = 0, i, j;
    if (lstrlenW(folder) + 8 >= MAX_PATH) {
        return;
    }
    lstrcpyW(pattern, folder);
    lstrcatW(pattern, L"\\*.txt");
    find = FindFirstFileW(pattern, &found);
    if (find == INVALID_HANDLE_VALUE) {
        return;
    }
    do {
        if (!(found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && count < RV_FILES
            && lstrlenW(folder) + lstrlenW(found.cFileName) + 2 < MAX_PATH) {
            lstrcpyW(names[count], found.cFileName);
            numbers[count] = rv_file_number(found.cFileName);
            ++count;
        }
    } while (FindNextFileW(find, &found));
    FindClose(find);
    for (i = 1; i < count; ++i) {     /* insertion sort by number */
        for (j = i; j > 0 && numbers[j - 1] > numbers[j]; --j) {
            wchar_t t[MAX_PATH];
            int tn = numbers[j];
            lstrcpyW(t, names[j]);
            lstrcpyW(names[j], names[j - 1]);
            lstrcpyW(names[j - 1], t);
            numbers[j] = numbers[j - 1];
            numbers[j - 1] = tn;
        }
    }
    for (i = 0; i < count; ++i) {
        int length;
        lstrcpyW(path, folder);
        lstrcatW(path, L"\\");
        lstrcatW(path, names[i]);
        length = rv_read(path);
        if (length >= 0) {
            visit(a, rv_text, length);
        }
    }
}

/* This save slot's folders of the log `sub`, older layout first ("...Logs\Save <S>\<sub>", then the save's own
   "Virtual Villagers Fun Patcher\Save <S>\Logs\<sub>"). */
static void rv_each_slot_log(const ce_adapter *a, int slot, const wchar_t *sub,
                             void (*visit)(const ce_adapter *, const char *, int)) {
    wchar_t root[MAX_PATH], older[MAX_PATH], newer[MAX_PATH];
    if (slot < 1 || slot > 5 || !vv_save_folder_w(root, 120)) {
        return;
    }
    /* the save folder leaves 120 characters: these tails (at most 75) always fit */
    wsprintfW(older, L"%s\\Virtual Villagers Fun Patcher Logs\\Save %d\\%s", root, slot, sub);
    rv_each_file(a, older, visit);
    wsprintfW(newer, L"%s\\Virtual Villagers Fun Patcher\\Save %d\\Logs\\%s", root, slot, sub);
    rv_each_file(a, newer, visit);
}

static int rv_slot(int game) {
    return game >= 1 && game <= 5 && story_hosts[game] != NULL && story_hosts[game]->slot != NULL
        ? story_hosts[game]->slot() : 0;
}

/* Everyone listed for `game` now, from the logs on disk. */
static void rv_load(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    int slot = rv_slot(game);
    rv_clear();
    rv_game = game;
    if (a == NULL || slot <= 0) {
        return;
    }
    rv_each_slot_log(a, slot, L"Deaths", rv_parse_deaths);
    rv_each_slot_log(a, slot, L"Deaths and Disappearances", rv_parse_deaths);
    if (rv_count > 0) {
        rv_each_slot_log(a, slot, L"Tribe History", rv_parse_history);
    }
    rv_settle(game, a);
}

/* ---- The purchase ------------------------------------------------------------------ */

/* Why nothing can be revived in `game` right now (an RV_* code), or 0. */
static int rv_village_refusal(int game, const ce_adapter *a) {
    if (a == NULL || a->record(0) == NULL) {
        return RV_NO_VILLAGE;
    }
    if (game == 5 && c5_reanimating()) {
        return RV_BUSY;
    }
    if (game == 3 && *(const int *)(uintptr_t)(RV_VV3_DEAD + 0x6810u) != 0) {
        return RV_BUSY;
    }
    if (!a->room()) {
        return RV_NO_ROOM;
    }
    if (a->tech() < rv_price(game)) {
        return RV_NO_TECH;
    }
    return 0;
}

/* Person `which` brought back.  RV_DONE, or why not (nothing changed, nothing charged). */
static int rv_buy(int game, int which, int *made) {
    const ce_adapter *a = ce_adapter_for(game);
    rv_person *p;
    ce_spawn s;
    unsigned char *r;
    int why, index, k;
    *made = -1;
    if (game != rv_game || which < 0 || which >= rv_count) {
        return RV_NOT_REVIVABLE;
    }
    p = &rv_people[which];
    if (!p->listed || p->refusal != NULL) {
        return RV_NOT_REVIVABLE;
    }
    why = rv_village_refusal(game, a);
    if (why != 0) {
        return why;
    }
    if (rv_in_village(a, p)) {
        return RV_IN_VILLAGE;
    }
    if (p->grave >= 0) {
        rv_yard y;
        if (!rv_graveyard(game, &y) || !rv_grave_is(&y, p->grave, p)) {
            return RV_IN_VILLAGE;     /* the graveyard changed since the list was made: look again */
        }
    }
    memset(&s, 0, sizeof s);
    s.count = 1;
    s.sex = p->sex;
    s.age = RV_AGE;
    rv_copy(s.name, CE_NAME_BYTES, p->name);
    s.head = p->head;
    s.body = p->body;
    s.prefs_set = 0;                  /* written below, every one the game holds */
    for (k = 0; k < CE_SKILLS; ++k) {
        s.skills[k] = p->skills_known ? p->skills[k] : CE_KEEP;
    }
    rv_copy(s.title, (int)sizeof s.title, p->title);
    /* A Heathen comes back a Heathen (RV_HEATHENS_STAY_HEATHENS): the game's own Heathen creator, its own mask
       (the game draws a Heathen's); a believer through the believer creator, with their cosmetic mask. */
    s.faction = game == 5 && p->heathen && RV_HEATHENS_STAY_HEATHENS ? 1 : CE_KEEP;
    s.mask = p->mask > 0 && s.faction != 1 ? p->mask : CE_KEEP;
    s.health = CE_KEEP;
    s.father_record = s.mother_record = -1;
    s.father_head = p->father_head;
    s.father_body = p->father_body;
    s.mother_head = p->mother_head;
    s.mother_body = p->mother_body;
    if (p->father[0] != '\0' && p->father_head != CE_KEEP && p->father_body != CE_KEEP) {
        rv_copy(s.father_name, CE_NAME_BYTES, p->father);
        s.father_kind = CE_PARENT_CUSTOM;
        s.parents_set = 1;
    }
    if (p->mother[0] != '\0' && p->mother_head != CE_KEEP && p->mother_body != CE_KEEP) {
        rv_copy(s.mother_name, CE_NAME_BYTES, p->mother);
        s.mother_kind = CE_PARENT_CUSTOM;
        s.parents_set = 1;
    }
    index = a->spawn(&s);
    r = index >= 0 ? a->record(index) : NULL;
    if (r == NULL) {
        return RV_NOT_MADE;
    }
    *made = index;
    /* The likes and dislikes, every one the record holds room for. */
    {
        int *likes = (int *)(r + a->off_likes);
        int *dislikes = (int *)(r + a->off_dislikes);
        story_preferences_changing(game, 0);
        for (k = 0; k < a->pref_slots; ++k) {
            likes[k] = -1;
            dislikes[k] = -1;
        }
        for (k = 0; k < p->like_count; ++k) {
            if (ce_valid_pref(a, p->likes[k])) (void)ce_pref_add(likes, a->pref_slots, p->likes[k]);
        }
        for (k = 0; k < p->dislike_count; ++k) {
            if (ce_valid_pref(a, p->dislikes[k])) (void)ce_pref_add(dislikes, a->pref_slots, p->dislikes[k]);
        }
        story_preferences_changing(game, 1);
    }
    ce_arrival_how = "Returned from the dead";
    ce_tell_arrival(game, index, &s);
    ce_arrival_how = CE_ARRIVAL_HOW;
    if ((a->caps & CAP_PARENTS) && s.parents_set && a->parents_supported()) {
        ce_change parents;
        ce_spawn_parents(&s, &parents);
        (void)a->set_parents(index, &parents);
    }
    if ((a->caps & CAP_TITLE) && s.title[0] != '\0') {
        (void)titles_set(game, index, s.title);
    }
    if ((a->caps & CAP_MASK) && s.mask != CE_KEEP) {
        (void)story_set_mask(game, r, s.mask);
    }
    if (p->grave >= 0) {
        (void)rv_grave_remove(game, p->grave);
    }
    if (rv_price(game) > 0) {
        a->change_tech(CE_AMOUNT_SUBTRACT, rv_price(game));
    }
    p->listed = 0;
    return RV_DONE;
}

static const char *rv_refusal_text(int why) {
    switch (why) {
    case RV_NO_ROOM:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s0", "Your village is at its maximum population, so nobody can come back now. Make room first (more huts, or wait). Nothing was bought.", 400);
    case RV_NO_TECH:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s1", "Reviving a villager costs 100,000 tech points, and your village has fewer. Nothing was bought.", 400);
    case RV_BUSY:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s2", "Not right now: the game is busy with a burial or a Reanimate. Try again in a moment. Nothing was bought.", 400);
    case RV_IN_VILLAGE:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s3", "That villager is no longer where the list said (they are in the village, or their grave changed). Open the list again. Nothing was bought.", 400);
    case RV_NO_VILLAGE:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s4", "There is no village to bring anyone back to. Nothing was bought.", 400);
    case RV_NOT_MADE:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s5", "The game could not make the villager now. Nothing was bought.", 400);
    default:
        return vvfp_tr("vvfp.story/story_revive.rv_refusal_text.s6", "That villager can not be brought back. Nothing was bought.", 400);
    }
}

/* ---- The list ------------------------------------------------------------------------- */

static void rv_years(int age, char *out) {
    if (age < 0) {
        lstrcpyA(out, "unknown");
    } else {
        wsprintfA(out, vvfp_tr("vvfp.story/story_revive.rv_years.s0", "%d years (%d age units)", 80), age / 20, age);
    }
}

/* The row of person `i` in the list. */
static void rv_row_text(const rv_person *p, char *out, int size) {
    char years[128], row[RV_LINE];
    wsprintfA(years, "%d", p->age >= 0 ? p->age / 20 : 0);
    wsprintfA(row, "%s, %s, %s %s%s",
                p->name[0] ? p->name : vvfp_tr("vvfp.story/story_revive.rv_row_text.s0", "(no name)", 60),
                p->sex == STORY_SEX_MALE ? "male"
                : p->sex == STORY_SEX_FEMALE ? "female"
                                             : vvfp_tr("vvfp.story/story_revive.rv_row_text.s1", "sex unknown", 40),
                p->kind == RV_DEATH ? vvfp_tr("vvfp.story/story_revive.rv_row_text.s2", "died at", 40)
                                    : vvfp_tr("vvfp.story/story_revive.rv_row_text.s3", "vanished at", 40),
                p->age >= 0 ? years : vvfp_tr("vvfp.story/story_revive.rv_row_text.s4", "an unknown age", 60),
                p->refusal != NULL ? vvfp_tr("vvfp.story/story_revive.rv_row_text.s5", " - can not come back", 60)
                : p->heathen ? vvfp_tr("vvfp.story/story_revive.rv_row_text.s6", " - a Heathen", 40)
                : p->grave >= 0 ? vvfp_tr("vvfp.story/story_revive.rv_row_text.s7", " - buried", 40) : "");
    lstrcpynA(out, row, size);
}

static void rv_add(char *out, int size, const char *text) {
    int n = lstrlenA(out);
    if (n < size - 1) {
        lstrcpynA(out + n, text, size - n);
    }
}

/* `fmt` (a row's English or translation with one %s) with `arg` in its place, appended to `out` whole: no
   formatting, so a list of any length is never cut or written past a buffer. */
static void rv_add_s(char *out, int size, const char *fmt, const char *arg) {
    const char *at = strstr(fmt, "%s");
    int n = lstrlenA(out);
    if (at == NULL) {
        rv_add(out, size, fmt);
        return;
    }
    if (n < size - 1) {
        int k = (int)(at - fmt);
        if (k > size - 1 - n) {
            k = size - 1 - n;
        }
        memcpy(out + n, fmt, (size_t)k);
        out[n + k] = '\0';
    }
    rv_add(out, size, arg);
    rv_add(out, size, at + 2);
}

/* The same with one %d before the %s (formatted: a number and a row's words fit RV_LINE). */
static void rv_add_ds(char *out, int size, const char *fmt, int number, const char *arg) {
    char head[RV_LINE];
    const char *at = strstr(fmt, "%s");
    int k = at != NULL ? (int)(at - fmt) : lstrlenA(fmt);
    char line[RV_LINE];
    if (k > RV_LINE - 1) {
        k = RV_LINE - 1;
    }
    memcpy(head, fmt, (size_t)k);
    head[k] = '\0';
    wsprintfA(line, head, number);
    rv_add(out, size, line);
    if (at != NULL) {
        rv_add(out, size, arg);
        rv_add(out, size, at + 2);
    }
}

static void rv_pref_words(const ce_adapter *a, const unsigned char *values, int count, char *out, int size) {
    int k;
    out[0] = '\0';
    for (k = 0; k < count; ++k) {
        const char *list = a->pref_list;
        int index = 0;
        while (*list != '\0' && index < values[k]) {
            if (*list++ == ',') ++index;
        }
        if (k > 0) rv_add(out, size, ", ");
        {
            int n = lstrlenA(out), j = 0;
            while (list[j] != '\0' && list[j] != ',' && n + j < size - 1) {
                out[n + j] = list[j];
                ++j;
            }
            out[n + j] = '\0';
        }
    }
    if (count == 0) {
        lstrcpynA(out, "(none)", size);
    }
}

/* Everything known about person `p`, as the dialog shows it (CRLF lines). */
static void rv_details(int game, const ce_adapter *a, const rv_person *p, char *out, int size) {
    char line[RV_LINE], words[RV_DETAILS / 4], years[128];
    int k;
    out[0] = '\0';
    wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s0", "Name: %s\r\nSex: %s\r\n", 400), p->name[0] ? p->name : "unknown",
                p->sex == STORY_SEX_MALE ? "Male"
                : p->sex == STORY_SEX_FEMALE ? "Female" : "unknown");
    rv_add(out, size, line);
    rv_years(p->age, years);
    wsprintfA(line, "%s: %s\r\n", p->kind == RV_DEATH ? vvfp_tr("vvfp.story/story_revive.rv_details.s1", "Age at death", 120) : vvfp_tr("vvfp.story/story_revive.rv_details.s2", "Age when they vanished", 120),
                years);
    rv_add(out, size, line);
    if (p->kind == RV_DEATH) {
        rv_add_ds(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s3", "Death record: Death %d\r\nCause of death: %s\r\n", 400), p->number,
                  p->cause != NULL && p->cause[0] ? p->cause : "unknown");
    } else {
        rv_add_s(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s4", "Record: Disappeared\r\nWhat happened: %s\r\n", 400),
                 p->cause != NULL && p->cause[0] ? p->cause : "unknown");
    }
    if (p->kind == RV_DEATH) {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s5", "Grave: %s\r\nEpitaph: %s\r\nWhere: %s\r\n", 400),
                    p->grave_line[0] ? p->grave_line : "unknown", p->epitaph[0] ? p->epitaph : "(none)",
                    p->grave >= 0 ? vvfp_tr("vvfp.story/story_revive.rv_details.s6", "buried here (the grave is removed when they come back)", 120)
                                  : vvfp_tr("vvfp.story/story_revive.rv_details.s7", "no grave in the graveyard now", 120));
        rv_add(out, size, line);
    }
    if (p->special[0] != '\0') {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s8", "Special villager: %s%s\r\n", 400), p->special,
                    p->refusal == NULL ? vvfp_tr("vvfp.story/story_revive.rv_details.s9", " (they come back as an ordinary villager)", 120) : "");
        rv_add(out, size, line);
    }
    if (p->heathen) {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s10", "Faction: Heathen\r\n", 100));
    }
    if (p->title[0] != '\0') {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s11", "Custom title: %s\r\n", 400), p->title);
        rv_add(out, size, line);
    }
    if (p->mask > 0) {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s12", "Mask: %s\r\n", 400), STORY_MASK_NAMES[p->mask]);
        rv_add(out, size, line);
    }
    if (p->head >= 0) {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s13", "Head: %d\r\nBody: %d\r\n", 400), p->head, p->body);
    } else {
        lstrcpyA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s14", "Head: unknown\r\nBody: unknown\r\n", 400));
    }
    rv_add(out, size, line);
    if (p->prefs_known) {
        rv_pref_words(a, p->likes, p->like_count, words, (int)sizeof words);
        rv_add_s(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s15", "Likes: %s\r\n", 400), words);
        rv_pref_words(a, p->dislikes, p->dislike_count, words, (int)sizeof words);
        rv_add_s(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s16", "Dislikes: %s\r\n", 400), words);
    } else {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s17", "Likes and dislikes: unknown\r\n", 400));
    }
    if (p->skills_known) {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s18", "Skills (the last Village History snapshot of them):\r\n", 400));
        for (k = 0; k < a->skill_count && k < CE_SKILLS; ++k) {
            wsprintfA(line, "    %s %d\r\n", a->skill_names[k], p->skills[k]);
            rv_add(out, size, line);
        }
    } else {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s19", "Skills: unknown (no Village History snapshot of them): the game picks a child's\r\n", 400));
    }
    if (p->father[0] != '\0' || p->mother[0] != '\0') {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s20", "Parents:\r\n", 400));
        if (p->father[0] != '\0') {
            wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s21", "    Father: %s\r\n", 400), p->father);
            rv_add(out, size, line);
        }
        if (p->mother[0] != '\0') {
            wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s22", "    Mother: %s\r\n", 400), p->mother);
            rv_add(out, size, line);
        }
    } else {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s23", "Parents: unknown\r\n", 400));
    }
    if (game == 1 && !a->parents_supported() && (p->father[0] != '\0' || p->mother[0] != '\0')) {
        rv_add(out, size, vvfp_tr("vvfp.story/story_revive.rv_details.s24", "(A New Home keeps parents only with Show Parents in Details Screen.)\r\n", 400));
    }
    if (p->refusal != NULL) {
        wsprintfA(line, vvfp_tr("vvfp.story/story_revive.rv_details.s25", "\r\nCan not come back: %s.\r\n", 400), rv_why(p->refusal));
    } else {
        lstrcpyA(line, p->heathen && RV_HEATHENS_STAY_HEATHENS
                           ? vvfp_tr("vvfp.story/story_revive.rv_details.s26", "\r\nComes back as this same person at age 5, a Heathen in the camp.\r\n", 400)
                           : vvfp_tr("vvfp.story/story_revive.rv_details.s27", "\r\nComes back as this same person at age 5.\r\n", 400));
    }
    rv_add(out, size, line);
}

/* ---- The dialog --------------------------------------------------------------------------- */

enum { IDD_RG = 313, IDC_RG_INTRO = 3901, IDC_RG_LIST = 3902, IDC_RG_DETAILS = 3903 };

static int rv_rows;
static int rv_chosen;

static void rv_fill_details(HWND window) {
    static char text[RV_DETAILS];
    const ce_adapter *a = ce_adapter_for(rv_game);
    int sel = (int)SendDlgItemMessageA(window, IDC_RG_LIST, LB_GETCURSEL, 0, 0);
    text[0] = '\0';
    if (a != NULL && sel >= 0 && sel < rv_rows) {
        rv_details(rv_game, a, &rv_people[rv_order[sel]], text, (int)sizeof text);
    }
    SetDlgItemTextA(window, IDC_RG_DETAILS, text);
}

static INT_PTR CALLBACK rv_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    INT_PTR handled;
    if (vk_dialog_hook(window, message, wparam, lparam, &handled)) {
        return handled;
    }
    if (message == WM_INITDIALOG) {
        char row[RV_LINE], intro[RV_LINE];
        const ce_adapter *a = ce_adapter_for(rv_game);
        int i, widest = 0;
        HDC dc = GetDC(window);
        HGDIOBJ old = dc != NULL ? SelectObject(dc, (HGDIOBJ)SendMessageA(window, WM_GETFONT, 0, 0)) : NULL;
        (void)lparam;
        for (i = 0; i < rv_rows; ++i) {
            SIZE extent = { 0, 0 };
            rv_row_text(&rv_people[rv_order[i]], row, (int)sizeof row);
            SendDlgItemMessageA(window, IDC_RG_LIST, LB_ADDSTRING, 0, (LPARAM)row);
            if (dc != NULL && GetTextExtentPoint32A(dc, row, lstrlenA(row), &extent) && extent.cx > widest) {
                widest = extent.cx;
            }
        }
        if (dc != NULL) {
            if (old != NULL) SelectObject(dc, old);
            ReleaseDC(window, dc);
        }
        SendDlgItemMessageA(window, IDC_RG_LIST, LB_SETHORIZONTALEXTENT, (WPARAM)(widest + 8), 0);
        wsprintfA(intro, vvfp_tr("vvfp.story/story_revive.rv_dialog.s0", "Bring back a villager who was buried or vanished: they return as the same person, aged 5, and their grave is removed. Each revival costs %s tech points (your village has %d).", 600), rv_price_text(rv_game),
                  a != NULL ? a->tech() : 0);
        {
            char button[RV_LINE];
            wsprintfA(button, vvfp_tr("vvfp.story/story_revive.rv_dialog.s1", "Revive (%s tech points)", 120),
                      rv_price_text(rv_game));
            SetDlgItemTextA(window, IDOK, button);
        }
        SetDlgItemTextA(window, IDC_RG_INTRO, intro);
        if (rv_rows > 0) {
            SendDlgItemMessageA(window, IDC_RG_LIST, LB_SETCURSEL, 0, 0);
        } else {
            SetDlgItemTextA(window, IDC_RG_DETAILS,
                            vvfp_tr("vvfp.story/story_revive.rv_dialog.s2",
                                    "Nobody to bring back: the village's Deaths and Disappearances log has no villager who is not in the village now. (Deaths are logged with Write Births and Conceptions Log to Text File and Show Cause of Death and Epitaphs on Graves, and Log Every Death ticked.)", 600));
        }
        if (rv_rows > 0) {
            rv_fill_details(window);
        }
        return TRUE;
    }
    if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        if (id == IDC_RG_LIST && HIWORD(wparam) == LBN_SELCHANGE) {
            rv_fill_details(window);
            return TRUE;
        }
        if (id == IDOK || (id == IDC_RG_LIST && HIWORD(wparam) == LBN_DBLCLK)) {
            int sel = (int)SendDlgItemMessageA(window, IDC_RG_LIST, LB_GETCURSEL, 0, 0);
            if (sel < 0 || sel >= rv_rows) {
                MessageBoxA(window, vvfp_tr("vvfp.story/story_revive.rv_dialog.s3", "Choose a villager in the list first.", 200), vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
                return TRUE;
            }
            if (rv_people[rv_order[sel]].refusal != NULL) {
                char text[RV_LINE];
                wsprintfA(text, vvfp_tr("vvfp.story/story_revive.rv_dialog.s4", "%s can not be brought back: %s.", 200),
                          rv_people[rv_order[sel]].name, rv_why(rv_people[rv_order[sel]].refusal));
                MessageBoxA(window, text, vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                            MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
                return TRUE;
            }
            rv_chosen = rv_order[sel];
            EndDialog(window, IDOK);
            return TRUE;
        }
        if (id == IDCANCEL) {
            EndDialog(window, IDCANCEL);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, IDCANCEL);
        return TRUE;
    }
    return FALSE;
}

/* The rows: everyone listed, the newest record first. */
static void rv_make_rows(void) {
    int i;
    rv_rows = 0;
    for (i = rv_count - 1; i >= 0; --i) {
        if (rv_people[i].listed) {
            rv_order[rv_rows++] = i;
        }
    }
}

/* Whether the row is in place for `game`: Story / Cheat Upgrades installed and the row's flag file shipped. */
static int rv_offered(int game) {
    if (!story_installed(game)) {
        return 0;
    }
#ifdef VVFP_TEST
    if (rv_test_offered >= 0) {
        return rv_test_offered;
    }
#endif
    return vvfp_patcher_file_exists(RV_FLAG_FILE);
}

static int story_revive_from_graves(int game, HWND owner) {
    const ce_adapter *a = ce_adapter_for(game);
    char text[RV_LINE];
    int why, made;
    if (!rv_offered(game) || a == NULL) {
        return 0;
    }
    why = rv_village_refusal(game, a);
    if (why != 0) {
        MessageBoxA(owner, rv_refusal_text(why), vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    rv_load(game);
    rv_make_rows();
    rv_chosen = -1;
    if (DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_RG), owner, rv_dialog, 0) != IDOK
        || rv_chosen < 0) {
        return 0;
    }
    wsprintfA(text,
                vvfp_tr("vvfp.story/story_revive.story_revive_from_graves.s0",
                        "Do you want to bring back %s for %s tech points?\r\nThey return as the same person, aged 5%s.\r\n\r\nPress OK to confirm, or Cancel.", 500),
                rv_people[rv_chosen].name, rv_price_text(game),
                rv_people[rv_chosen].grave >= 0
                    ? vvfp_tr("vvfp.story/story_revive.story_revive_from_graves.s1", ", and their grave is removed", 100) : "");
    if (MessageBoxA(owner, text, vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    why = rv_buy(game, rv_chosen, &made);
    if (why != RV_DONE) {
        MessageBoxA(owner, rv_refusal_text(why), vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(text, vvfp_tr("vvfp.story/story_revive.story_revive_from_graves.s2", "%s is back in the village, aged 5.", 200),
              rv_people[rv_chosen].name);
    MessageBoxA(owner, text, vvfp_tr("vvfp.storybridge/story_bridge.vvfp_story_add_revive_button.s0", "Revive Buried/Disappeared Villagers", 128),
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* The Revive Buried/Disappeared Villagers button of the Origins companion's Tech menu (story_bridge.h). 1 when a
   villager came back (the menu then closes). */
__declspec(dllexport) int __stdcall VvfpStoryReviveFromGraves(int game, HWND owner) {
    return story_revive_from_graves(game, owner);
}

/* Whether the button is offered in `game` now. */
__declspec(dllexport) int __stdcall VvfpStoryReviveOffered(int game) {
    return rv_offered(game);
}

/* What it costs now: 100,000, or 0 while the story upgrades are free (rv_price). */
__declspec(dllexport) int __stdcall VvfpStoryRevivePrice(int game) {
    return rv_offered(game) ? rv_price(game) : 0;
}

#ifdef VVFP_TEST
/* TEST build: the list from these texts (a Deaths log and a Village History, NUL-terminated; history may be NULL)
   instead of the files.  The rows listed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveLoad(int game, const char *deaths, const char *history) {
    const ce_adapter *a = ce_adapter_for(game);
    rv_clear();
    rv_game = game;
    if (a == NULL) {
        return -1;
    }
    if (deaths != NULL) {
        rv_parse_deaths(a, deaths, lstrlenA(deaths));
    }
    if (history != NULL && rv_count > 0) {
        rv_parse_history(a, history, lstrlenA(history));
    }
    rv_settle(game, a);
    rv_make_rows();
    return rv_rows;
}

/* Row `row`: its list line and its details; returns the person's index (-1 none). */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveRow(int row, char *line, char *details, int size) {
    const ce_adapter *a = ce_adapter_for(rv_game);
    if (row < 0 || row >= rv_rows || a == NULL) {
        return -1;
    }
    rv_row_text(&rv_people[rv_order[row]], line, size);
    rv_details(rv_game, a, &rv_people[rv_order[row]], details, size);
    return rv_order[row];
}

/* Row `row` bought (no dialog).  The RV_* answer; *made the new record's index. */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveBuy(int row, int *made) {
    if (row < 0 || row >= rv_rows) {
        *made = -1;
        return RV_NOT_REVIVABLE;
    }
    return rv_buy(rv_game, rv_order[row], made);
}

/* The person's grave place (-1 none) and whether they can come back (1). */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveState(int row, int *grave) {
    if (row < 0 || row >= rv_rows) {
        return -1;
    }
    *grave = rv_people[rv_order[row]].grave;
    return rv_people[rv_order[row]].refusal == NULL;
}

/* "Story / Cheat Upgrades cost Tech Points" on (1) or off (0) for `game`. */
__declspec(dllexport) void __stdcall VvfpStoryProbeReviveCharges(int game, int on) {
    if (game >= 1 && game <= 5) {
        charges[game] = on != 0;
    }
}

/* -1 the flag file decides whether the row is in place, else this. */
__declspec(dllexport) void __stdcall VvfpStoryProbeReviveOffered(int offered) {
    rv_test_offered = offered;
}

/* The refusal the village gives now (0 none). */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveRefusal(int game) {
    return rv_village_refusal(game, ce_adapter_for(game));
}

/* Grave `place` removed as the purchase removes it. */
__declspec(dllexport) int __stdcall VvfpStoryProbeReviveRemoveGrave(int game, int place) {
    return rv_grave_remove(game, place);
}
#endif
