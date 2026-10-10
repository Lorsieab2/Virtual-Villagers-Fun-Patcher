/* A New Home and The Lost Children: the cause recorded at each death, the
   graves file, the burial and the removal of an unburied body (the Death
   records), the grave popup's cause line, and A New Home's epitaph.  The
   epitaph's editing is in cod_epitaph_edit.inc.  Included by
   vvfp_cause_of_death.c. */

/* ---- The graves ------------------------------------------------------------

   A grave keeps only a name, a best skill and the age (VV1 manager+0xA31C,
   50 x 0x2C: name char[0x1C], best value +0x1C, job +0x20, age +0x24;
   VV2 world+0x2EB0C, 50 x 0x7C: name char[0x19], epitaph char[0x41] +0x19,
   best value +0x6C, job +0x70, age +0x74).  The games' own code calls a
   grave with age 0 free (VV1's recount 0x41CF10 and its popup 0x436D62, which
   closes itself; VV2's allocator 0x464CD0), so the popup and the epitaph box
   follow that (cod_grave_entry).  Everything else here never reads a 0 age
   as "no grave": 0 is a real age (the owner, 2026-10-09), and a villager
   buried at age 0 still has a grave until the game's next burial reuses its
   slot.  A grave that was never dug has no name (cod_backfill.inc).  The
   burial always takes the lowest free grave and nothing in either game
   removes or moves one, so a grave's slot is its order of burial. */
struct grave_geometry {
    unsigned int owner;          /* the graves' owner, read from the villager table */
    unsigned int graves;         /* the table's offset in its owner */
    unsigned int stride;
    /* How much of the grave's name the fingerprint reads: never more than
       the villager's own name field, because the burial copies that field
       (with sprintf, to its terminator), so a name filling the record's
       field could carry stray bytes into a longer grave field. */
    unsigned int name_capacity;
    unsigned int value;          /* the best skill's value */
    unsigned int job;
    unsigned int age;
    unsigned int epitaph;        /* the game's own epitaph; 0 = none (A New Home) */
    unsigned int epitaph_capacity;
    unsigned int master;         /* the best-skill value from which the rank is Master */
};

#define GRAVES 50

static const struct grave_geometry GRV[3] = {
    { 0 },
    { 0x3E010u, 0xA31Cu, 0x2Cu, 0x1Cu, 0x1Cu, 0x20u, 0x24u, 0u, 0u, 90u },
    { 0xE574D4u, 0x2EB0Cu, 0x7Cu, 0x18u, 0x6Cu, 0x70u, 0x74u, 0x19u, 0x41u, 88u },
};

/* The grave's own job words, by its job value (the popups' switches: VV1
   0x43670C, VV2 0x444834). */
static const char *const JOB_WORDS[3][6] = {
    { 0 },
    { NULL, "Farmer", "Parent", "Scientist", "Builder", "Doctor" },
    { NULL, "Farmer", "Parent", "Doctor", "Scientist", "Builder" },
};

/* A New Home's epitaph lines by the grave's job: the later games' lines for
   that skill (the first of each pair). */
static const int JOB_EPITAPH[3][6] = {
    { 0 },
    { 0, EPITAPH_FARMER1, EPITAPH_PARENT1, EPITAPH_RESEARCH1, EPITAPH_BUILDER1, EPITAPH_HEALER1 },
    { 0 },
};

static unsigned char *cod_grave_owner(void) {
    unsigned char *records = cod_records();
    return records != NULL ? *(unsigned char **)(records + GRV[g_game].owner) : NULL;
}

static unsigned char *cod_grave(int slot) {
    unsigned char *owner = cod_grave_owner();
    if (owner == NULL || slot < 0 || slot >= GRAVES) {
        return NULL;
    }
    return owner + GRV[g_game].graves + (size_t)slot * GRV[g_game].stride;
}

static unsigned int cod_grave_fingerprint(const unsigned char *grave) {
    const struct grave_geometry *g = &GRV[g_game];
    return cod_fingerprint(grave, g->name_capacity, *(const int *)(grave + g->age));
}

/* A child's grave (the owner: "Children = less than 14 years old"): the age
   at death the grave keeps is under 14 years, 280 age units -- the boundary
   both games' own Villager Detail panel uses for "Apprentice" (VV1
   0x41FC06, VV2 0x429C46: `cmp [villager+age], 0x118`), and the one The
   Tree of Life's grave dialog uses (0x41BE43). */
#define CHILD_AGE 280

/* Does the grave's skill line name a job (a best skill of 20 or more, a job
   the popup words), and is that grave a child's?  Then the line is
   "Apprentice <job>", as The Tree of Life words a child's grave. */
static int cod_grave_apprentice(const unsigned char *grave) {
    const struct grave_geometry *g = &GRV[g_game];
    int job = *(const int *)(grave + g->job);
    return job >= 1 && job <= 5 && *(const int *)(grave + g->value) >= 20
        && *(const int *)(grave + g->age) < CHILD_AGE;
}

/* The skill line the grave shows under "Job", as the popup builds it:
   "Untrained" below 20 (or with no job), otherwise the rank and the job --
   "Apprentice" for a child (cod_grave_apprentice), else "Trainee", "Adept",
   "Master" (VV1 from 90, VV2 from 88). */
static void cod_grave_title(const unsigned char *grave, char *out) {
    const struct grave_geometry *g = &GRV[g_game];
    int value = *(const int *)(grave + g->value);
    int job = *(const int *)(grave + g->job);
    if (job < 1 || job > 5 || value < 20) {
        lstrcpyA(out, "Untrained");
        return;
    }
    wsprintfA(out, "%s %s",
              cod_grave_apprentice(grave) ? "Apprentice"
              : value < 50 ? "Trainee" : (unsigned int)value < g->master ? "Adept" : "Master",
              JOB_WORDS[g_game][job]);
}

/* ---- The epitaph (A New Home) ----------------------------------------------

   The later games' burial rule, decided once, when the grave is made, from
   what the grave itself holds -- so it always agrees with the grave's own
   skill line: under 18 years (360 age units) one of "Curious and Playful" /
   "Loving and Special"; otherwise the line pair for the skill the grave
   shows; no skill at all, "Respected Citizen".  The later games' Chief,
   Esteemed Elder and Scholar lines have no counterpart in A New Home.  The
   two-way choice uses this companion's own random numbers, never the
   game's. */
static unsigned int roll_state;

static int cod_roll_half(void) {
#ifdef VVFP_TEST
    if (VvfpCauseRollTest == 0 || VvfpCauseRollTest == 1) {
        return VvfpCauseRollTest;
    }
#endif
    if (roll_state == 0) {
        roll_state = GetTickCount() | 1u;
    }
    roll_state ^= roll_state << 13;
    roll_state ^= roll_state >> 17;
    roll_state ^= roll_state << 5;
    return (int)(roll_state >> 31);
}

static int cod_epitaph_for(const unsigned char *grave) {
    const struct grave_geometry *g = &GRV[g_game];
    int value = *(const int *)(grave + g->value);
    int job = *(const int *)(grave + g->job);
    if (*(const int *)(grave + g->age) < 360) {
        return cod_roll_half() ? EPITAPH_CHILD2 : EPITAPH_CHILD1;
    }
    if (job >= 1 && job <= 5 && value > 0) {
        return JOB_EPITAPH[g_game][job] + cod_roll_half();
    }
    return EPITAPH_CITIZEN;
}

/* ---- The tables and their file ------------------------------------------- */

struct cod_entry {
    unsigned int fingerprint;
    signed char cause;            /* CAUSE_*, or CAUSE_NONE */
    unsigned char epitaph;        /* EPITAPH_*; graves only */
    unsigned char valid;
    unsigned char custom;         /* text holds the player's own epitaph */
    char text[EPITAPH_TEXT];
};

/* A body lying in record i, and grave k. */
static struct cod_entry bodies[RECORDS_MAX];
static struct cod_entry graves[GRAVES];

/* What the hooks did since the last tick.  Applied to the tables at once;
   replayed onto the new village's tables when the tick finds the slot has
   changed -- the load-time catch-up of a village runs before the first tick
   that sees its slot. */
enum { EVENT_DEATH = 1, EVENT_GRAVE = 2, EVENT_GONE = 3 };
struct cod_event {
    int type;
    int index;
    struct cod_entry entry;
};
#define JOURNAL 512
static struct cod_event journal[JOURNAL];
static int journal_count;

static struct {
    int slot;                 /* the slot the tables belong to, 0 = none */
    int loaded;
    int dirty;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} store;

/* FORMAT (little-endian), exactly 16 + 44 * count bytes:
       u32 magic 'VCD1', u32 version 1, u32 game (1 or 2), u32 count,
       count x { u16 kind (0 grave, 1 lying body), u16 index (grave 0..49,
                 record 0..255), u32 fingerprint, i8 cause (-1..4, or 0x7F
                 none), u8 epitaph (0..13), u8 flags (1 = the text is the
                 player's own epitaph), u8 0, char text[32] (bytes 0x20-0xFF,
                 as the game's text box takes them, NUL-terminated and
                 NUL-filled, at most 31; empty when the player cleared it;
                 all 0 without flag 1) }
   The fingerprint is FNV-1a of the name (to its terminator, at most 0x1C
   bytes in A New Home, 0x18 in The Lost Children), a 0xFF byte, and the age
   in age units as four little-endian bytes; never 0.  It names the body and
   its grave alike, and an entry whose fingerprint no longer matches what the
   game holds is ignored. */
#define COD_MAGIC 0x31444356u
#define COD_VERSION 1u
#define COD_HEADER 16u
#define COD_ENTRY 44u
#define COD_MAX_ENTRIES (RECORDS_MAX + GRAVES)
static unsigned char file_buffer[COD_HEADER + COD_MAX_ENTRIES * COD_ENTRY];

/* The player's text: what the game's text box accepts (0x20-0xFF), at most
   31 characters, NUL-filled after; empty is allowed (an epitaph cleared). */
static int cod_text_ok(const unsigned char *text, int custom) {
    int i;
    int ended = 0;
    for (i = 0; i < EPITAPH_TEXT; ++i) {
        if (text[i] == 0) {
            ended = 1;
        } else if (ended || !custom || text[i] < 0x20) {
            return 0;                 /* bytes after the end, or a control byte */
        }
    }
    return ended;
}

static int cod_entry_ok(const unsigned char *e) {
    unsigned int kind = (unsigned int)(e[0] | e[1] << 8);
    unsigned int index = (unsigned int)(e[2] | e[3] << 8);
    signed char cause = (signed char)e[8];
    if (kind > 1u || index >= (kind == 0u ? (unsigned)GRAVES : (unsigned)RECORDS_MAX)) {
        return 0;
    }
    if (!((cause >= -1 && cause <= 4) || cause == CAUSE_NONE)) {
        return 0;
    }
    if (e[9] >= EPITAPH_COUNT || e[10] > 1u || e[11] != 0 || (kind == 1u && (e[9] != 0 || e[10] != 0))) {
        return 0;
    }
    return *(const unsigned int *)(e + 4) != 0u && cod_text_ok(e + 12, e[10]);
}

static int cod_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    (void)context;
    if (length < COD_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != COD_MAGIC
        || *(const unsigned int *)(data + 4) != COD_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || count > COD_MAX_ENTRIES
        || length != COD_HEADER + count * COD_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (!cod_entry_ok(data + COD_HEADER + i * COD_ENTRY)) {
            return 0;
        }
    }
    return 1;
}

static void cod_parse(const unsigned char *data) {
    unsigned int count = *(const unsigned int *)(data + 12);
    unsigned int i;
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + COD_HEADER + i * COD_ENTRY;
        unsigned int kind = (unsigned int)(e[0] | e[1] << 8);
        unsigned int index = (unsigned int)(e[2] | e[3] << 8);
        struct cod_entry *to = kind == 0u ? &graves[index] : &bodies[index];
        to->fingerprint = *(const unsigned int *)(e + 4);
        to->cause = (signed char)e[8];
        to->epitaph = e[9];
        to->custom = e[10];
        memcpy(to->text, e + 12, EPITAPH_TEXT);
        to->valid = 1;
    }
}

static DWORD cod_serialise(void) {
    unsigned int count = 0;
    int pass;
    for (pass = 0; pass < 2; ++pass) {
        int n = pass == 0 ? GRAVES : RECORDS_MAX;
        const struct cod_entry *table = pass == 0 ? graves : bodies;
        int i;
        for (i = 0; i < n; ++i) {
            unsigned char *e;
            if (!table[i].valid) {
                continue;
            }
            e = file_buffer + COD_HEADER + count * COD_ENTRY;
            e[0] = (unsigned char)pass;
            e[1] = 0;
            e[2] = (unsigned char)(i & 0xFF);
            e[3] = (unsigned char)(i >> 8);
            *(unsigned int *)(e + 4) = table[i].fingerprint;
            e[8] = (unsigned char)table[i].cause;
            e[9] = pass == 0 ? table[i].epitaph : 0;
            e[10] = pass == 0 ? table[i].custom : 0;
            e[11] = 0;
            memset(e + 12, 0, EPITAPH_TEXT);
            if (pass == 0 && table[i].custom) {
                memcpy(e + 12, table[i].text, EPITAPH_TEXT - 1);
            }
            ++count;
        }
    }
    *(unsigned int *)file_buffer = COD_MAGIC;
    *(unsigned int *)(file_buffer + 4) = COD_VERSION;
    *(unsigned int *)(file_buffer + 8) = (unsigned int)g_game;
    *(unsigned int *)(file_buffer + 12) = count;
    return COD_HEADER + count * COD_ENTRY;
}

static int cod_build_path(int slot, char *out) {
    char name[64];
    /* "Virtual Villagers Fun Patcher Data\Graves\": a file an older build
       left loose in the Data folder is moved in on the way, and if it will
       not move the loose file is the one read and written
       (native/shared/data_subfolder.h). */
    if (!vv_save_subfolder(out, VV_DATA_FOLDER,
                           (int)sizeof(
                                       "\\Virtual Villagers 1 Graves - Save 0.dat"))) {
        return 0;
    }
    wsprintfA(name, "Virtual Villagers %d Graves - Save %d.dat", g_game, slot);
    return vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_GRAVES, name, VV_DATA_RESERVE) != 0;
}

static void cod_forget(void) {
    memset(bodies, 0, sizeof bodies);
    memset(graves, 0, sizeof graves);
}

static void cod_apply(const struct cod_event *e) {
    if (e->type == EVENT_DEATH) {
        bodies[e->index] = e->entry;
    } else if (e->type == EVENT_GRAVE) {
        graves[e->index] = e->entry;
    } else if (e->type == EVENT_GONE) {
        bodies[e->index].valid = 0;
    }
}

static void cod_event(const struct cod_event *e) {
    cod_apply(e);
    store.dirty = 1;
    if (journal_count < JOURNAL) {
        journal[journal_count++] = *e;
    }
}

/* Bind the tables to `slot`, loading its file (again after a blocked load's
   retry window).  The events since the last tick are replayed on top. */
static void cod_bind(int slot) {
    DWORD length = 0;
    int result;
    int i;
    if (slot != store.slot) {
        store.slot = slot;
        store.loaded = 0;
        store.dirty = 0;
        store.path[0] = '\0';
        memset(seen_alive, 0, sizeof seen_alive);
        vv_sidecar_gate_bind(&store.gate, g_game * 16 + slot);
        cod_forget();
    }
    if (slot <= 0 || store.loaded || vv_sidecar_gate_throttled(&store.gate)) {
        return;
    }
    if (store.path[0] == '\0' && !cod_build_path(slot, store.path)) {
        vv_sidecar_gate_block(&store.gate);
        return;
    }
    result = vv_sidecar_load(&store.gate, store.path, file_buffer, sizeof file_buffer,
                             &length, cod_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    cod_forget();
    if (result == VV_SIDECAR_LOAD_VALID) {
        cod_parse(file_buffer);
    }
    store.loaded = 1;
    for (i = 0; i < journal_count; ++i) {
        cod_apply(&journal[i]);
    }
    if (journal_count > 0) {
        store.dirty = 1;
    }
}

static void cod_publish(void) {
    const void *parts[1];
    DWORD sizes[1];
    if (!store.loaded || store.slot <= 0 || !store.dirty) {
        return;
    }
    parts[0] = file_buffer;
    sizes[0] = cod_serialise();
    if (vv_sidecar_publish(&store.gate, store.path, parts, sizes, 1)) {
        store.dirty = 0;
        COD_COUNT(published);
    }
}

/* ---- A death -------------------------------------------------------------

   Called from a hooked site BEFORE the store that kills, or from the tick or
   the burial for a death no site reported.  The record still holds the
   villager.  Only the cause is kept here; the Death record waits until the
   death is final. */
static void cod_died(const unsigned char *record, int cause) {
    struct cod_event e;
    int index = cod_index_of(record);
    if (index < 0) {
        return;
    }
    memset(&e, 0, sizeof e);
    e.type = EVENT_DEATH;
    e.index = index;
    e.entry.fingerprint = cod_record_fingerprint(record);
    e.entry.cause = (signed char)cause;
    e.entry.valid = 1;
    seen_alive[index] = 0;
    cod_event(&e);
    COD_COUNT(deaths);
}

/* The cause kept for the body in `record`: the recorded one, "Unknown
   causes" for a villager the tick saw alive whose death no site reported
   (buried or removed before a tick saw the body), otherwise none -- a body
   that was already lying when this was installed. */
static int cod_cause_of(const unsigned char *record, int index) {
    if (bodies[index].valid && bodies[index].fingerprint == cod_record_fingerprint(record)) {
        return bodies[index].cause;
    }
    if (seen_alive[index] != 0 && seen_alive[index] == cod_name_hash(record)) {
        COD_COUNT(unhooked);
        return CAUSE_UNKNOWN;
    }
    return CAUSE_NONE;
}

/* ---- The hooked death sites ----------------------------------------------

   Each site's displaced instructions run unchanged after a check made BEFORE
   them, against the health they are about to change:

     STORE0  `mov [reg+health], 0`              alive -> dies
     DEC1    the load / lea before `dec`        health 1 -> dies
     SUB     `sub [ptr], eax` (or the load       health - eax <= 0 -> dies
             before `sub ecx, eax`)                                          */
enum { K_STORE0 = 1, K_DEC1 = 2, K_SUB = 3 };

static void site_death(int site, const unsigned int *regs) {
    const struct hook_site *s = &sites[site];
    const int *health;
    if (s->kind == K_STORE0) {
        health = (const int *)(uintptr_t)(regs[s->ra] + REC[g_game].health);
        if (*health > 0) {
            cod_died((const unsigned char *)health - REC[g_game].health, s->cause);
        }
    } else if (s->kind == K_DEC1) {
        health = (const int *)(uintptr_t)(regs[s->ra] + regs[s->rb] + REC[g_game].health);
        if (*health == 1) {
            cod_died((const unsigned char *)health - REC[g_game].health, s->cause);
        }
    } else if (s->kind == K_SUB) {
        int amount = (int)regs[R_EAX];
        health = (const int *)(uintptr_t)regs[s->ra];
        if (*health > 0 && *health - amount <= 0) {
            cod_died((const unsigned char *)health - REC[g_game].health, s->cause);
        }
    }
}

static void add_death(unsigned int va, const char *stock, int cause, int kind, int ra, int rb) {
    cod_add(va, stock, site_death);
    sites[site_count - 1].cause = (signed char)cause;
    sites[site_count - 1].kind = (unsigned char)kind;
    sites[site_count - 1].ra = (unsigned char)ra;
    sites[site_count - 1].rb = (unsigned char)rb;
}

/* ---- The burial ------------------------------------------------------------

   Right after the burial's grave loop, which runs only for a body (the
   game's own present-and-dead guard) and has already freed its record and
   written the grave in full (VV2: the epitaph too) -- or found no empty
   grave:

     VV1 0x449008  ebx = the loop counter (0x34 after a grave was written at
                   slot ebp / 0x2C, 0x32 when the graveyard was full),
                   [esi-0x2EC] = the body's index, edi = the villager array
     VV2 0x465334  ecx = the same counter, slot ebp / 0x7C, [edi+0x60] =
                   the body's index, esi = the pool

   The Statistics row's Villagers Buried hooks sit on the record-freeing
   store before both (VV1 0x448F65, VV2 0x46503B) and are not touched. */
static void cod_buried(int index, int found, int slot) {
    unsigned char *record = cod_record(index);
    const unsigned char *grave;
    char title[64];
    char epitaph[80];
    struct cod_event e;
    int cause;
    if (record == NULL || index < 0 || (unsigned int)index >= REC[g_game].slots) {
        return;
    }
    COD_COUNT(burials);
    cause = cod_cause_of(record, index);
    seen_alive[index] = 0;
    memset(&e, 0, sizeof e);
    e.type = EVENT_GONE;
    e.index = index;
    cod_event(&e);
    roster_departed(index, record);
    /* `found` is the game's own word that the loop wrote a grave at `slot`.
       Its age is never asked: a villager buried at age 0 has a grave with
       age 0, and 0 is a real age (the owner, 2026-10-09: "0 is a valid value
       for head, body and age") -- never "the graveyard was full". */
    grave = found ? cod_grave(slot) : NULL;
    if (grave == NULL) {
        cod_log_death(record, cause, NO_GRAVE_FULL, NULL);
        return;
    }
    memset(&e, 0, sizeof e);
    e.type = EVENT_GRAVE;
    e.index = slot;
    e.entry.fingerprint = cod_grave_fingerprint(grave);
    e.entry.cause = (signed char)cause;
    e.entry.epitaph = (unsigned char)(g_game == 1 ? cod_epitaph_for(grave) : EPITAPH_NONE);
    e.entry.valid = 1;
    cod_event(&e);
    if (cause != CAUSE_NONE) {
        COD_COUNT(graves_set);
    }
    cod_grave_title(grave, title);
    if (g_game == 1) {
        lstrcpyA(epitaph, EPITAPHS[e.entry.epitaph]);
    } else {
        cod_printable(epitaph, sizeof epitaph, (const char *)grave + GRV[2].epitaph,
                      (int)GRV[2].epitaph_capacity);
    }
    cod_log_death(record, cause, title, epitaph);
}

static void vv1_buried(int site, const unsigned int *regs) {
    (void)site;
    cod_buried((int)*(const unsigned int *)(uintptr_t)(regs[R_ESI] - 0x2ECu),
               regs[R_EBX] == 0x34u, (int)(regs[R_EBP] / 0x2Cu));
}

static void vv2_buried(int site, const unsigned int *regs) {
    (void)site;
    cod_buried((int)*(const unsigned int *)(uintptr_t)(regs[R_EDI] + 0x60u),
               regs[R_ECX] == 0x34u, (int)(regs[R_EBP] / 0x7Cu));
}

/* ---- An unburied body is removed (240 minutes; no grave) ------------------

     VV1 0x42E9C3  `mov byte [edi+eax+0x28], 0`
     VV2 0x43B78D  `mov byte [eax+edi+0x30], 0` */
static void cod_decayed(unsigned char *record) {
    struct cod_event e;
    int index = cod_index_of(record);
    int cause;
    if (index < 0) {
        return;
    }
    cause = cod_cause_of(record, index);
    seen_alive[index] = 0;
    memset(&e, 0, sizeof e);
    e.type = EVENT_GONE;
    e.index = index;
    cod_event(&e);
    roster_departed(index, record);
    cod_log_death(record, cause, NO_GRAVE_NEVER_BURIED, NULL);
}

static void vv1_decayed(int site, const unsigned int *regs) {
    (void)site;
    cod_decayed((unsigned char *)(uintptr_t)(regs[R_EDI] + regs[R_EAX]));
}

static void vv2_decayed(int site, const unsigned int *regs) {
    (void)site;
    cod_decayed((unsigned char *)(uintptr_t)(regs[R_EAX] + regs[R_EDI]));
}

/* ---- The grave popup -------------------------------------------------------

   The later games' grave dialog, top to bottom: "Here Lies <name>" (+0x23),
   the epitaph in quotes, in the box the player edits (+0x46), "Job"
   (+0x6E), the skill line (+0x8C), "Age <n>" (+0xB4), the cause (+0xD7).
   A New Home's popup and The Lost Children's panel already draw "Here
   Lies", "Job", the skill line and "Age" at those same heights, and The
   Lost Children its quoted epitaph box; this adds the cause at +0xD7 to
   both, and to A New Home the epitaph box (cod_epitaph_edit.inc) and its
   quotes, drawn as The Lost Children draws them (0x4447A0: a `"` at left +
   0x1C and at right - 0x1C, +0x46).  Same text routine, font and centre as
   the popup's own lines. */
typedef void (__fastcall *text_fn)(void *renderer, int unused_edx, const char *text, int x,
                                   int y, void *font, int zero);

/* The games' text routine is __thiscall (ecx = renderer, five stack
   arguments, `ret 0x14`).  C has no __thiscall, but __fastcall puts its
   first argument in ecx, its second in edx (unused by the routine) and the
   rest on the stack for the callee to pop -- the same call. */
static const struct cod_entry *cod_grave_entry(int slot, const unsigned char *grave) {
    struct cod_event e;
    /* The age test is the GAME's: A New Home's popup closes itself for a
       grave whose age is 0 (0x436D62) and both games' graveyards call it
       free, so it gets no cause line and no epitaph box.  Its Death record was still written at the
       burial (cod_buried) and by the backfill (cod_backfill.inc). */
    if (grave == NULL || slot < 0 || slot >= GRAVES || *(const int *)(grave + GRV[g_game].age) == 0) {
        return NULL;
    }
    if (graves[slot].valid && graves[slot].fingerprint == cod_grave_fingerprint(grave)) {
        return &graves[slot];
    }
    if (g_game != 1 || !store.loaded) {
        return NULL;                  /* a grave from before: no cause known */
    }
    /* A New Home grave made before this patch: it gets its epitaph by the
       same rule the first time it is shown, and keeps it. */
    memset(&e, 0, sizeof e);
    e.type = EVENT_GRAVE;
    e.index = slot;
    e.entry.fingerprint = cod_grave_fingerprint(grave);
    e.entry.cause = CAUSE_NONE;
    e.entry.epitaph = (unsigned char)cod_epitaph_for(grave);
    e.entry.valid = 1;
    cod_event(&e);
    return &graves[slot];
}

static const char *cod_entry_epitaph(const struct cod_entry *entry) {
    if (entry->custom) {
        return entry->text;
    }
    return entry->epitaph > EPITAPH_NONE && entry->epitaph < EPITAPH_COUNT
        ? EPITAPHS[entry->epitaph] : NULL;
}

static void cod_grave_lines(int slot, const unsigned char *grave, const unsigned char *popup,
                            void *renderer, int x, unsigned int draw, unsigned int font_global) {
    const struct cod_entry *entry = cod_grave_entry(slot, grave);
    void *font = *(void **)(uintptr_t)font_global;
    int left = *(const int *)(popup + 0x14);
    int top = *(const int *)(popup + 0x18);
    int right = *(const int *)(popup + 0x1C);
    if (entry == NULL) {
        return;
    }
    if (g_game == 1) {
        ((text_fn)(uintptr_t)draw)(renderer, 0, "\"", left + 0x1C, top + 0x46, font, 0);
        ((text_fn)(uintptr_t)draw)(renderer, 0, "\"", right - 0x1C, top + 0x46, font, 0);
    }
    if (entry->cause != CAUSE_NONE) {
        ((text_fn)(uintptr_t)draw)(renderer, 0, cod_cause_words(entry->cause), x, top + 0xD7, font, 0);
        COD_COUNT(draws);
    }
}

/* VV1 0x436700, the popup Draw's epilogue: ebx = popup ([+0x60] slot,
   [+0x74] manager, [+0x18] top), esi = renderer, ebp = centre x; text
   0x4094C0, font [0x48B608]. */
static void vv1_draw(int site, const unsigned int *regs) {
    const unsigned char *popup = (const unsigned char *)(uintptr_t)regs[R_EBX];
    int slot = *(const int *)(popup + 0x60);
    unsigned char *manager = *(unsigned char **)(popup + 0x74);
    (void)site;
    if (manager == NULL || slot < 0 || slot >= GRAVES) {
        return;
    }
    cod_grave_lines(slot, manager + GRV[1].graves + (size_t)slot * GRV[1].stride, popup,
                    (void *)(uintptr_t)regs[R_ESI], (int)regs[R_EBP], 0x4094C0u, 0x48B608u);
}

/* VV2 0x444790, after the panel's Age line: ebp = panel ([+0x60] slot,
   [+0x78] world, [+0x18] top), esi = renderer, ebx = centre x; text
   0x4096B0, font [0x499F18]. */
static void vv2_draw(int site, const unsigned int *regs) {
    const unsigned char *panel = (const unsigned char *)(uintptr_t)regs[R_EBP];
    int slot = *(const int *)(panel + 0x60);
    unsigned char *world = *(unsigned char **)(panel + 0x78);
    (void)site;
    if (world == NULL || slot < 0 || slot >= GRAVES) {
        return;
    }
    cod_grave_lines(slot, world + GRV[2].graves + (size_t)slot * GRV[2].stride, panel,
                    (void *)(uintptr_t)regs[R_ESI], (int)regs[R_EBX], 0x4096B0u, 0x499F18u);
}

/* ---- A child's skill line --------------------------------------------------

   The popup builds the skill line by printing the rank's string (the game's
   string table: VV1 "Trainee  " 0x57, "Adept " 0x58, "Master " 0x59; VV2
   0x84-0x86) into its line buffer and then appending the job's word.  Right
   after that print, the line buffer is still the print's first argument,
   [esp]; for a child's grave the hook puts the game's own "Apprentice "
   (VV1 0x56, VV2 0x83 -- the string its Villager Detail panel gives a
   child, in the game's language) there instead, and the game appends the
   job as before:

     VV1 0x436565  after the print 0x436560; ebx = popup ([+0x60] slot,
                   [+0x74] manager, [+0x7C] the string table, read by
                   0x433970)
     VV2 0x4445CB  after the print 0x4445C6; ebp = panel ([+0x60] slot,
                   [+0x78] world, [+0x80] the string table, read by
                   0x441680) */
typedef const char *(__fastcall *string_fn)(void *table, int unused_edx, int id);

static void cod_apprentice_line(const unsigned char *grave, const unsigned int *regs, void *table,
                                unsigned int string_va, int id) {
    if (cod_grave_apprentice(grave)) {
        lstrcpyA((char *)(uintptr_t)reg_stack(regs, 0), ((string_fn)(uintptr_t)string_va)(table, 0, id));
    }
}

static void vv1_rank(int site, const unsigned int *regs) {
    const unsigned char *popup = (const unsigned char *)(uintptr_t)regs[R_EBX];
    const unsigned char *manager = *(const unsigned char *const *)(popup + 0x74);
    (void)site;
    cod_apprentice_line(manager + GRV[1].graves + (size_t)*(const int *)(popup + 0x60) * GRV[1].stride,
                        regs, *(void *const *)(popup + 0x7C), 0x433970u, 0x56);
}

static void vv2_rank(int site, const unsigned int *regs) {
    const unsigned char *panel = (const unsigned char *)(uintptr_t)regs[R_EBP];
    const unsigned char *world = *(const unsigned char *const *)(panel + 0x78);
    (void)site;
    cod_apprentice_line(world + GRV[2].graves + (size_t)*(const int *)(panel + 0x60) * GRV[2].stride,
                        regs, *(void *const *)(panel + 0x80), 0x441680u, 0x83);
}

/* ---- The sites ------------------------------------------------------------ */

static void vv12_sites(void) {
    if (g_game == 1) {
        /* The aging step (tick 0x42E900, once per age unit). */
        add_death(0x42EF05u, "C78344030000" "00000000", CAUSE_OLD_AGE, K_STORE0, R_EBX, 0);
        add_death(0x42ECB7u, "8B8C0744030000", CAUSE_STARVATION, K_DEC1, R_EDI, R_EAX);  /* food <= 200 */
        add_death(0x42ED37u, "8B8C1744030000", CAUSE_STARVATION, K_DEC1, R_EDI, R_EDX);  /* no food */
        add_death(0x42EDA3u, "8B8C1744030000", CAUSE_DISEASE, K_DEC1, R_EDI, R_EDX);     /* sick */
        /* Work injuries: the job callbacks' 2% rand(15) / rand(10). */
        add_death(0x43A5B4u, "29038B8610E00300", CAUSE_WORK, K_SUB, R_EBX, 0);
        add_death(0x43A793u, "29078B8610E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43A8BAu, "29078B9610E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43A9E1u, "29078B9610E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43AAE7u, "29078B8E10E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43AC9Bu, "29078B8610E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43B112u, "29078B8E10E00300", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x43B2D4u, "8B0B83C404", CAUSE_WORK, K_SUB, R_EBX, 0);
        add_death(0x43B393u, "8B0B83C404", CAUSE_WORK, K_SUB, R_EBX, 0);
        cod_add(0x449008u, "8B5C2410" "C7860CFDFFFF01000000", vv1_buried);
        cod_add(0x42E9C3u, "C644072800", vv1_decayed);
        cod_add(0x436700u, "5F5E5D5B81C4CC000000", vv1_draw);
        cod_add(0x436565u, "8B4360" "8B4B74", vv1_rank);
    } else {
        add_death(0x43BDEEu, "C7832C050000" "00000000", CAUSE_OLD_AGE, K_STORE0, R_EBX, 0);
        add_death(0x43BAEBu, "8D84382C050000", CAUSE_STARVATION, K_DEC1, R_EAX, R_EDI);  /* food <= 150 */
        add_death(0x43BB7Eu, "8D843A2C050000", CAUSE_STARVATION, K_DEC1, R_EDX, R_EDI);  /* no food */
        add_death(0x43BC43u, "8D843A2C050000", CAUSE_DISEASE, K_DEC1, R_EDX, R_EDI);     /* sick */
        /* Work injuries: building projects' rand(15); research and the
           restorations' rand(10). */
        add_death(0x46299Cu, "2945008B86D474E500", CAUSE_WORK, K_SUB, R_EBP, 0);
        add_death(0x462AD9u, "29078B8ED474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x462C11u, "29078B86D474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x462D48u, "29078B96D474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x462E84u, "29078B96D474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x462F96u, "29078B96D474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x463099u, "29078B96D474E500", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x463644u, "8B4D0083C404", CAUSE_WORK, K_SUB, R_EBP, 0);
        add_death(0x4638E6u, "8B0F83C404", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x46404Au, "8B0F83C404", CAUSE_WORK, K_SUB, R_EDI, 0);
        add_death(0x4641B3u, "8B4D0083C404", CAUSE_WORK, K_SUB, R_EBP, 0);
        cod_add(0x465334u, "C7475801000000", vv2_buried);
        cod_add(0x43B78Du, "C644383000", vv2_decayed);
        cod_add(0x444790u, "8B8D84000000", vv2_draw);
        cod_add(0x4445CBu, "8B5560" "8B4578", vv2_rank);
    }
}

/* ---- The tick ------------------------------------------------------------- */

/* A body's cause follows the body, not its record.  The games save only
   their occupied records and the load packs them into records 0, 1, 2, ...
   (seen live: a body in record 15 is in record 14 after a reload when 14
   was freed), so after a load a body's kept cause can sit at another
   record: it is moved to the body with its fingerprint.  A cause whose
   record holds no such body afterwards -- the body was brought back to
   life, or the record now holds someone else, or the file is a replaced
   save's -- is dropped. */
static int cod_body_holds(const unsigned char *records, int i, unsigned int fingerprint) {
    const unsigned char *record = records + (size_t)i * REC[g_game].stride;
    return rec_present(record) && !rec_lookalike(record) && rec_health(record) <= 0
        && cod_record_fingerprint(record) == fingerprint;
}

static void cod_rehome_bodies(const unsigned char *records) {
    int i, k;
    for (i = 0; i < (int)REC[g_game].slots; ++i) {
        const unsigned char *record = records + (size_t)i * REC[g_game].stride;
        unsigned int fingerprint;
        if (!rec_present(record) || rec_lookalike(record) || rec_health(record) > 0) {
            continue;
        }
        fingerprint = cod_record_fingerprint(record);
        if (bodies[i].valid && bodies[i].fingerprint == fingerprint) {
            continue;
        }
        for (k = 0; k < (int)REC[g_game].slots; ++k) {
            if (k != i && bodies[k].valid && bodies[k].fingerprint == fingerprint
                && !cod_body_holds(records, k, fingerprint)) {
                bodies[i] = bodies[k];
                bodies[k].valid = 0;
                store.dirty = 1;
                break;
            }
        }
    }
    for (i = 0; i < (int)REC[g_game].slots; ++i) {
        if (bodies[i].valid && !cod_body_holds(records, i, bodies[i].fingerprint)) {
            bodies[i].valid = 0;
            store.dirty = 1;
        }
    }
}

static void vv12_tick(void) {
    unsigned char *records;
    int i;
    cod_bind(cod_slot());
    records = cod_records();
    if (records != NULL) {
        if (store.loaded) {
            cod_rehome_bodies(records);
        }
        for (i = 0; i < (int)REC[g_game].slots; ++i) {
            unsigned char *record = records + (size_t)i * REC[g_game].stride;
            if (!rec_present(record) || rec_lookalike(record) || rec_health(record) > 0) {
                continue;             /* seen_tick keeps seen_alive for these */
            }
            /* A body.  Seen alive on an earlier frame, with no site having
               reported it: an island event, the Gong, the Custom Island
               Event, an edit.  A body never seen alive is one the village
               was loaded with. */
            if (seen_alive[i] != 0 && seen_alive[i] == cod_name_hash(record)) {
                COD_COUNT(unhooked);
                cod_died(record, CAUSE_UNKNOWN);
            }
            seen_alive[i] = 0;
        }
    }
    if (store.loaded) {
        journal_count = 0;
        cod_publish();
    }
}

/* A save of `slot` (cod_save_done): the tables go to that slot's file now.
   The causes live only here and in the file until the body is buried, and
   the tick publishes only to the slot the host reports -- which was none
   for a whole session after The Lost Children's Change Tribe, so a death
   seen and recorded then never reached the file and the burial a session
   later had no cause.  Binding to another slot replays the events the tick
   has not yet put into a loaded file (the journal), as the tick does. */
static void vv12_saved(int slot) {
    unsigned char *records;
    cod_bind(slot);
    if (!store.loaded) {
        return;                       /* blocked: the journal keeps the events for later */
    }
    records = cod_records();
    if (records != NULL) {
        cod_rehome_bodies(records);
    }
    journal_count = 0;
    cod_publish();
}

static void vv12_reset(int slot) {
    if (slot == store.slot) {
        cod_forget();
        store.dirty = 0;
        store.loaded = 0;
        journal_count = 0;
        /* The reset deletes the file next; a fresh load then finds it
           missing and the new village starts empty. */
        vv_sidecar_gate_bind(&store.gate, -1);
        store.slot = 0;
    }
}
