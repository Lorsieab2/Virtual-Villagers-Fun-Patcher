/* A branching Custom Island Event's own cause words (VvfpCauseKilledBy), every game.  Included by
   vvfp_cause_of_death.c after cod_cie.inc.

   The owner (v1.35.97): a Custom Island Event's death effect may name its cause in the author's words ("Fell from
   the Great Falls").  The Story / Cheat Upgrades companion kills the villager as before and tells this companion
   right after, with those words: VvfpCauseKilledBy(game, index, words) -- as VvfpCauseVanishedBy does for a
   disappearance.  The death is then exactly VvfpCauseKilled's (cause 5 in A New Home and The Lost Children's graves
   file; the body kept for its Death record in the later three, cod_cie.inc), and the words go where "Died in a
   custom island event" would: the Death record's "Cause of death:" line in every game, and the grave's cause line: A New Home's and The Lost
   Children's popup (which this companion draws), and -- the owner, v1.35.97 -- The Secret City's, The Tree of Life's
   and New Believers' too (THE LATER THREE'S GRAVES, below).

   The words are kept by the body's fingerprint (cod_fingerprint: its name and age, frozen at death -- the same that
   names its grave), in their own small file beside the Custom Island Event Deaths file:

       <save folder>\Virtual Villagers Fun Patcher Data\Custom Island Event Deaths\
           Virtual Villagers N Custom Island Event Causes - Save S.dat

   written at each save of the village, so it matches the save: a kill the game never saved is never in it.  At a
   save an entry is kept only while something still needs it -- A New Home / The Lost Children: a body or grave of
   that fingerprint with cause 5 in this companion's tables; the later three: a body the Custom Island Event left
   (cod_cie.inc) -- so a grave the game reused drops what it does not hold.  Start Over deletes the file
   (cw_reset, from VvfpCauseVillageReset).

   FORMAT (little-endian).  Version 1, exactly 16 + 68 * count bytes:
       u32 magic 'VCW1', u32 version 1, u32 game (1..5), u32 count (at most CW_MAX),
       count x { u32 fingerprint (never 0), char words[64] (bytes 0x20-0x7E, NUL-terminated and NUL-filled, at
                 least one character) }
   Version 2 (the owner, 2026-11-17: with Scrolling Popups a death's own words are practically unlimited, up to
   CW_WORDS - 1 = 4,095 characters; the graves' popups scroll), exactly 16 + the entries' bytes:
       u32 magic 'VCW1', u32 version 2, u32 game (1..5), u32 count (at most CW_MAX),
       count x { u32 fingerprint (never 0), u32 length (1 .. CW_WORDS - 1), length bytes 0x20-0x7E (no NUL) }
   each fingerprint once.  Both are read; a save writes version 1 while every entry's words fit its 63 characters
   (so an older companion still reads it) and version 2 once one does not.  A file that is not exactly one of these
   is set aside unread (sidecar_io.h), never misread. */

#define CW_MAGIC 0x31574356u           /* 'VCW1' */
#define CW_VERSION_1 1u
#define CW_VERSION_2 2u
#define CW_HEADER 16u
#define CW_WORDS_V1 64                 /* version 1's words field, NUL included */
#define CW_ENTRY_V1 (4u + CW_WORDS_V1)
#define CW_WORDS 4096                  /* the words kept, NUL included (story_custom.h CE_LONG_LINE_BYTES) */
#define CW_ENTRY_MAX (8u + CW_WORDS - 1u)
#define CW_MAX (RECORDS_MAX + GRAVES)

static struct {
    unsigned int fingerprint[CW_MAX];
    char words[CW_MAX][CW_WORDS];
    int count;
    int slot;
    int loaded;
    int dirty;
    int merge;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} cw;

static unsigned char cw_buffer[CW_HEADER + CW_MAX * CW_ENTRY_MAX];

static int cw_words_ok(const unsigned char *w) {
    int i, ended = 0;
    if (w[0] == 0) {
        return 0;
    }
    for (i = 0; i < CW_WORDS_V1; ++i) {
        if (w[i] == 0) {
            ended = 1;
        } else if (ended || w[i] < 0x20 || w[i] > 0x7E) {
            return 0;
        }
    }
    return ended;
}

/* The entry at `at` of a file of `version` (`length_all` bytes): its fingerprint and its words (`*length` bytes, no
   NUL); the offset of the next entry, or 0 when the entry is not whole or not valid. */
static unsigned int cw_file_entry(const unsigned char *data, DWORD length_all, unsigned int version, unsigned int at,
                             unsigned int *fingerprint, const unsigned char **words, unsigned int *length) {
    unsigned int i;
    if (version == CW_VERSION_1) {
        if (at + CW_ENTRY_V1 > length_all || !cw_words_ok(data + at + 4)) {
            return 0;
        }
        *fingerprint = *(const unsigned int *)(data + at);
        *words = data + at + 4;
        *length = (unsigned int)lstrlenA((const char *)data + at + 4);
        return at + CW_ENTRY_V1;
    }
    if (at + 8u > length_all) {
        return 0;
    }
    *fingerprint = *(const unsigned int *)(data + at);
    *length = *(const unsigned int *)(data + at + 4);
    if (*length == 0u || *length > CW_WORDS - 1u || *length > length_all - at - 8u) {
        return 0;
    }
    *words = data + at + 8;
    for (i = 0; i < *length; ++i) {
        if ((*words)[i] < 0x20 || (*words)[i] > 0x7E) {
            return 0;
        }
    }
    return at + 8u + *length;
}

static int cw_validate(const unsigned char *data, DWORD length, void *context) {
    static unsigned int seen[CW_MAX];
    unsigned int count, version, i, k, at = CW_HEADER;
    (void)context;
    if (length < CW_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    version = *(const unsigned int *)(data + 4);
    if (*(const unsigned int *)data != CW_MAGIC || (version != CW_VERSION_1 && version != CW_VERSION_2)
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game || count > CW_MAX
        || (version == CW_VERSION_1 && length != CW_HEADER + count * CW_ENTRY_V1)) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        unsigned int fingerprint, words_length;
        const unsigned char *words;
        at = cw_file_entry(data, length, version, at, &fingerprint, &words, &words_length);
        if (at == 0u || fingerprint == 0u) {
            return 0;
        }
        for (k = 0; k < i; ++k) {
            if (seen[k] == fingerprint) {
                return 0;
            }
        }
        seen[i] = fingerprint;
    }
    return at == length;                /* exactly the entries, nothing after them */
}

static int cw_find(unsigned int fingerprint) {
    int i;
    for (i = 0; i < cw.count; ++i) {
        if (cw.fingerprint[i] == fingerprint) {
            return i;
        }
    }
    return -1;
}

/* Bind the table to `slot`, reading its file the first time.  Words told while no slot was known stay, over the
   file's (as cod_cie.inc's kills). */
static void cw_bind(int slot) {
    DWORD length = 0;
    int result;
    if (slot != cw.slot) {
        if (cw.slot == 0) {
            cw.merge = cw.count > 0;
        } else {
            cw.count = 0;
            cw.merge = 0;
        }
        cw.slot = slot;
        cw.loaded = 0;
        cw.dirty = cw.merge;
        cw.path[0] = '\0';
        vv_sidecar_gate_bind(&cw.gate, 0x380 + g_game * 16 + slot);
    }
    if (slot <= 0 || cw.loaded || vv_sidecar_gate_throttled(&cw.gate)) {
        return;
    }
    if (cw.path[0] == '\0') {
        char stem[64];
        wsprintfA(stem, "Virtual Villagers %d Custom Island Event Causes", g_game);
        if (!cod_data_path(cw.path, "Custom Island Event Deaths", stem, slot)) {
            cw.path[0] = '\0';
            vv_sidecar_gate_block(&cw.gate);
            return;
        }
    }
    result = vv_sidecar_load(&cw.gate, cw.path, cw_buffer, sizeof cw_buffer, &length, cw_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    if (!cw.merge) {
        cw.count = 0;
    }
    if (result == VV_SIDECAR_LOAD_VALID) {
        unsigned int count = *(const unsigned int *)(cw_buffer + 12), i, at = CW_HEADER;
        unsigned int version = *(const unsigned int *)(cw_buffer + 4);
        for (i = 0; i < count && cw.count < CW_MAX; ++i) {
            unsigned int fingerprint, n;
            const unsigned char *words;
            at = cw_file_entry(cw_buffer, length, version, at, &fingerprint, &words, &n);
            if (at == 0u) {
                break;                  /* (never: the file was checked whole) */
            }
            if (cw_find(fingerprint) < 0) {
                cw.fingerprint[cw.count] = fingerprint;
                memset(cw.words[cw.count], 0, CW_WORDS);
                memcpy(cw.words[cw.count], words, n);
                ++cw.count;
            }
        }
    }
    cw.merge = 0;
    cw.loaded = 1;
}

/* The author's words for the body (or grave) with `fingerprint`, NULL when none. */
static const char *cw_words(unsigned int fingerprint) {
    int i;
    if (fingerprint == 0u) {
        return NULL;
    }
    cw_bind(cod_slot());
    i = cw_find(fingerprint);
    return i >= 0 ? cw.words[i] : NULL;
}

/* Keep `words` for the body with `fingerprint` (printable ASCII, at most CW_WORDS - 1 = 4,095 kept: the event's own
   limit, 63 without Scrolling Popups; the oldest entry gives way when the table is full). */
static void cw_add(unsigned int fingerprint, const char *words) {
    char kept[CW_WORDS];
    int i, n = 0;
    if (fingerprint == 0u || words == NULL) {
        return;
    }
    memset(kept, 0, sizeof kept);
    for (i = 0; words[i] != '\0' && n < CW_WORDS - 1; ++i) {
        unsigned char c = (unsigned char)words[i];
        kept[n++] = c >= 0x20 && c <= 0x7E ? (char)c : ' ';
    }
    if (n == 0) {
        return;
    }
    cw_bind(cod_slot());
    i = cw_find(fingerprint);
    if (i < 0) {
        if (cw.count == CW_MAX) {
            memmove(&cw.fingerprint[0], &cw.fingerprint[1], sizeof cw.fingerprint[0] * (CW_MAX - 1));
            memmove(&cw.words[0], &cw.words[1], sizeof cw.words[0] * (CW_MAX - 1));
            --cw.count;
        }
        i = cw.count++;
    }
    cw.fingerprint[i] = fingerprint;
    memcpy(cw.words[i], kept, CW_WORDS);
    cw.dirty = 1;
}

/* Whether this companion still holds a body or grave (or a Custom Island Event body) with `fingerprint`. */
static int cw_needed(unsigned int fingerprint) {
    int i;
    if (g_game <= 2) {
        for (i = 0; i < RECORDS_MAX; ++i) {
            if (bodies[i].valid && bodies[i].fingerprint == fingerprint && bodies[i].cause == CAUSE_CUSTOM_EVENT) {
                return 1;
            }
        }
        for (i = 0; i < GRAVES; ++i) {
            if (graves[i].valid && graves[i].fingerprint == fingerprint && graves[i].cause == CAUSE_CUSTOM_EVENT) {
                return 1;
            }
        }
        return 0;
    }
    for (i = 0; i < RECORDS_MAX; ++i) {
        if (cie_fp[i] == fingerprint) {
            return 1;
        }
    }
    /* ...and, once buried, its Roster of the Dead entry (cause -1), whose grave shows the words (read under SEH:
       the roster is the game's, at its fixed place). */
    __try {
        for (i = 0; i < V345_ENTRIES; ++i) {
            const unsigned char *entry = v345_entry(i);
            if (entry != NULL && *(const int *)(entry + V345[g_game].e_cause) == CAUSE_UNKNOWN
                && *(const unsigned char *)entry != 0 && v345_fingerprint(entry) == fingerprint) {
                return 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return 0;
}

/* A save of `slot` (after the graves file or the Custom Island Event Deaths file): what is still needed is written
   to match the save. */
static void cw_saved(int slot) {
    const void *parts[1];
    DWORD sizes[1];
    int i, k = 0;
    cw_bind(slot);
    if (!cw.loaded) {
        return;                         /* blocked: kept in memory for the next save */
    }
    for (i = 0; i < cw.count; ++i) {
        if (cw_needed(cw.fingerprint[i])) {
            if (k != i) {
                cw.fingerprint[k] = cw.fingerprint[i];
                memcpy(cw.words[k], cw.words[i], CW_WORDS);
            }
            ++k;
        } else {
            cw.dirty = 1;
        }
    }
    cw.count = k;
    if (!cw.dirty || cw.slot <= 0) {
        return;
    }
    {
        /* Version 1 while every entry's words fit its field (an older companion still reads the file), else 2. */
        unsigned int version = CW_VERSION_1, at = CW_HEADER;
        for (i = 0; i < cw.count; ++i) {
            if (lstrlenA(cw.words[i]) > CW_WORDS_V1 - 1) {
                version = CW_VERSION_2;
            }
        }
        for (i = 0; i < cw.count; ++i) {
            unsigned char *e = cw_buffer + at;
            unsigned int n = (unsigned int)lstrlenA(cw.words[i]);
            *(unsigned int *)e = cw.fingerprint[i];
            if (version == CW_VERSION_1) {
                memset(e + 4, 0, CW_WORDS_V1);
                memcpy(e + 4, cw.words[i], n);
                at += CW_ENTRY_V1;
            } else {
                *(unsigned int *)(e + 4) = n;
                memcpy(e + 8, cw.words[i], n);
                at += 8u + n;
            }
        }
        ((unsigned int *)cw_buffer)[1] = version;
        sizes[0] = at;
    }
    ((unsigned int *)cw_buffer)[0] = CW_MAGIC;
    ((unsigned int *)cw_buffer)[2] = (unsigned int)g_game;
    ((unsigned int *)cw_buffer)[3] = (unsigned int)cw.count;
    parts[0] = cw_buffer;
    if (vv_sidecar_publish(&cw.gate, cw.path, parts, sizes, 1)) {
        cw.dirty = 0;
        COD_COUNT(published);
    }
}

/* Start Over erased `slot` ("VVFP Save Reset.dll" calls VvfpCauseVillageReset before it deletes the village's
   files): nothing of its village is kept, and its words' file is deleted here (it is this companion's own). */
static void cw_reset(int slot) {
    char path[MAX_PATH];
    char stem[64];
    wsprintfA(stem, "Virtual Villagers %d Custom Island Event Causes", g_game);
    if (slot >= 1 && cod_data_path(path, "Custom Island Event Deaths", stem, slot)) {
        DeleteFileA(path);
    }
    if (slot == cw.slot || cw.slot == 0) {
        cw.count = 0;
        cw.loaded = 0;
        cw.dirty = 0;
        cw.merge = 0;
        cw.path[0] = '\0';
        vv_sidecar_gate_bind(&cw.gate, -1);
        cw.slot = 0;
    }
}

/* The cause words a Death record or a grave says for `cause` of the body with `fingerprint`: the author's own for a
   Custom Island Event's death that named them, else the companion's (English for the log). */
static const char *cod_cause_words_of(int cause, unsigned int fingerprint) {
    const char *words = cause == CAUSE_CUSTOM_EVENT ? cw_words(fingerprint) : NULL;
    return words != NULL ? words : cod_cause_words(cause);
}

/* The Story / Cheat Upgrades companion's branching Custom Island Event (story_graph.inc cg_tell_killed): called
   right after its "Dies" with the author's cause words killed the villager in record `index` (the record holds the
   body).  As VvfpCauseKilled, with the words kept for the Death record and the grave (`words`, at most 4,095
   characters are kept: the event's own limit, 63 without Scrolling Popups). */
__declspec(dllexport) void __stdcall VvfpCauseKilledBy(int game, int index, const char *words) {
    unsigned char *record;
    if (install_state != 1 || game != g_game) {
        return;
    }
    record = cod_record(index);
    if (record == NULL || !rec_present(record) || rec_health(record) > 0 || !cod_is_villager(record)) {
        return;
    }
    if (words != NULL && words[0] != '\0') {
        cw_add(cod_record_fingerprint(record), words);
    }
    VvfpCauseKilled(game, index);
}

/* The grave line of a death whose body was never recovered (docs/event-collection/cie-v6-binary.md 22): "no grave",
   so the Village Statistics' reconciliation never counts it as a burial. */
#define NO_GRAVE_NOT_RECOVERED "no grave (the body was not recovered)"

/* The branching Custom Island Event's "died, no body" (story_graph.inc cg_tell_died_unrecovered): called right after
   it took the villager in record `index` with the stock disappearance (no body, no skeleton, no grave: the presence
   byte cleared; The Tree of Life's after the Sealed Box's health 0, as VvfpCauseVanished).  It is a DEATH (the
   owner, V28: "logged as died, counted as a death"): a Death record, "Cause of death: Unknown causes" (ALWAYS: the
   owner's rule for these deaths; `words` is ignored, an author never words it) and the grave line above, with the
   babies a nursing mother carried and their "Lost before birth" record -- written by cod_log_death, as every Death
   record.  The same checks as VvfpCauseVanished. */
__declspec(dllexport) void __stdcall VvfpCauseDiedUnrecovered(int game, int index, const char *words) {
    unsigned char *record;
    (void)words;
    if (install_state != 1 || game != g_game) {
        return;
    }
    record = cod_record(index);
    if (record == NULL || rec_present(record) || (g_game != 4 && rec_health(record) <= 0)
        || !cod_is_villager(record)) {
        return;
    }
    seen_alive[index] = 0;
    roster_departed(index, record);
    (void)cod_log_death(record, CAUSE_UNKNOWN, NO_GRAVE_NOT_RECOVERED, NULL);
}

/* New Believers' "VVFP Heathen Aging.dll": a Heathen it ages died of old age and left no body (no skeleton row
   covers them: the owner, 2026-11-22, "a Heathen who dies just disappears from the camp, logged, no grave").  The
   companion took them as the game's own disappearances do (the activity stopped, the presence byte cleared, health
   untouched) and calls this at once: a Death record with the game's own cause (`cause`: 2, Old age) and the grave
   line below, written by cod_log_death as every Death record.  The same checks as VvfpCauseDiedUnrecovered. */
#define NO_GRAVE_AMONG_HEATHENS "no grave (died among the Heathens: nothing was left)"

__declspec(dllexport) void __stdcall VvfpCauseDiedAmongHeathens(int game, int index, int cause) {
    unsigned char *record;
    if (install_state != 1 || game != g_game || game != 5) {
        return;
    }
    record = cod_record(index);
    if (record == NULL || rec_present(record) || rec_health(record) <= 0 || !cod_is_villager(record)) {
        return;
    }
    seen_alive[index] = 0;
    roster_departed(index, record);
    (void)cod_log_death(record, cause, NO_GRAVE_AMONG_HEATHENS, NULL);
}

/* The branching Custom Island Event's "baby lost" (story_graph.inc cg_tell_baby_lost): called right BEFORE it ends
   the pregnancy of the living villager in record `index` (the record still holds the babies).  The Births and
   Conceptions log closes the open Conception: "Lost before birth", `what` happened (the event's words, at most 120
   characters kept).  The babies get no Death record, grave or skeleton (the owner: a nursing baby is never a
   villager). */
__declspec(dllexport) void __stdcall VvfpCauseBabyLost(int game, int index, const char *what) {
    char words[128];
    unsigned char *record;
    int babies, i;
    if (install_state != 1 || game != g_game || what == NULL) {
        return;
    }
    record = cod_record(index);
    if (record == NULL || !rec_present(record) || rec_health(record) <= 0 || !cod_is_villager(record)) {
        return;
    }
    babies = lost_babies(record);
    for (i = 0; i < 120 && what[i] != '\0'; ++i) {
        words[i] = what[i] == '\n' || what[i] == '\r' ? ' ' : what[i];
    }
    words[i] = '\0';
    lost_record_what(record, babies, words);
}

/* The branching Custom Island Event's "birth, then the parent dies" (story_graph.inc cg_tell_delivered,
   cie-v6-binary.md 23): the game's own delivery has just made the babies of the villager in record `index`, in the
   middle of a frame, and the parent's death follows at once.  The per-frame copy of the parent's nursing state
   (lost_tick) still holds the pregnancy, and a Death record reads it while the field shows the delivery cannot
   have come yet (lost_babies) -- so it is forgotten here: the babies were born, never lost with the parent. */
__declspec(dllexport) void __stdcall VvfpCauseDelivered(int game, int index) {
    if (install_state != 1 || game != g_game || index < 0 || index >= RECORDS_MAX) {
        return;
    }
    lost_due[index] = 0;
    lost_litter[index] = 0;
}

/* ---- THE LATER THREE'S GRAVES (the owner, v1.35.97) ----------------------------------------------------------

   The Secret City, The Tree of Life and New Believers word a grave's cause from their own string table: the grave
   dialog's constructor (VV3 0x41E6D0, VV4 0x41BBA0, VV5 0x41C3F0) looks up "cause + base" with the string lookup
   (thiscall, the id; ret 4) and makes the cause line from the text it returns, and The Secret City's Roster of the
   Dead does the same for each entry it lists:

       site      the call                  the Roster of the Dead entry      base
       VV3 grave 0x41EC65 call 0x42F190    eax                               0x2E6
       VV3 roster 0x41A07F call 0x42F190   ebp                               0x2E6
       VV4 grave 0x41C18A call 0x44D3D0    ebx                               0x317
       VV5 grave 0x41C9DA call 0x4506D0    eax                               0x314

   Each call is pointed here at run time (a 5-byte call redirect, in the companion's own install batch: every one
   of its sites or none, stock bytes checked first;
   nothing is written to the exe file and no string table is touched): the game's own lookup runs as before, and
   only when the entry's cause is the game's -1 ("Unknown causes", every island event's) and this companion holds
   the author's words for that grave's fingerprint (its name and age at death: v345_fingerprint, the same as the
   body's) is the text the line gets the words instead.  Every other grave keeps the game's own words. */

typedef struct {
    unsigned int va;                   /* the `call <lookup>` */
    unsigned int lookup;               /* what it calls */
    int game;
    int reg;                           /* the entry's register: 0 eax, 1 ebx, 2 ebp */
} cw_grave_site;

static const cw_grave_site CW_GRAVE_SITES[] = {
    { 0x41EC65u, 0x42F190u, 3, 0 },
    { 0x41A07Fu, 0x42F190u, 3, 2 },
    { 0x41C18Au, 0x44D3D0u, 4, 1 },
    { 0x41C9DAu, 0x4506D0u, 5, 0 },
};
#define CW_GRAVE_SITE_COUNT ((int)(sizeof CW_GRAVE_SITES / sizeof CW_GRAVE_SITES[0]))

static unsigned int cw_lookup;         /* the game's string lookup */
static unsigned int cw_return;         /* the site's return address (the UI thread only) */
static const unsigned char *cw_entry;  /* the entry the line is for */

/* The text a grave's cause line gets: the author's words for a Custom Island Event's death, else `text`. */
static const char *__cdecl cw_grave_text(const unsigned char *entry, const char *text) {
    const char *words = NULL;
    __try {
        if (entry != NULL && *(const int *)(entry + V345[g_game].e_cause) == CAUSE_UNKNOWN) {
            words = cw_words(v345_fingerprint(entry));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        words = NULL;
    }
    return words != NULL ? words : text;
}

/* The redirected call: the game's lookup (its id on the stack, ecx its table), then the words in its place. */
__declspec(naked) static void cw_grave_common(void) {
    __asm {
        pop dword ptr [cw_return]
        call dword ptr [cw_lookup]
        push eax
        push dword ptr [cw_entry]
        call cw_grave_text
        add esp, 8
        push dword ptr [cw_return]
        ret
    }
}

__declspec(naked) static void cw_grave_eax(void) {
    __asm {
        mov dword ptr [cw_entry], eax
        jmp cw_grave_common
    }
}

__declspec(naked) static void cw_grave_ebx(void) {
    __asm {
        mov dword ptr [cw_entry], ebx
        jmp cw_grave_common
    }
}

__declspec(naked) static void cw_grave_ebp(void) {
    __asm {
        mov dword ptr [cw_entry], ebp
        jmp cw_grave_common
    }
}

/* The game's grave sites into `w`, the companion's own install batch (cod_install_sites: every site of the companion
   written, or none): their count, or -1 when one is not the game's own call (then nothing is installed). */
static int cw_graves_prepare(vvfp_site_write *w) {
    static unsigned char stocks[CW_GRAVE_SITE_COUNT][5];   /* each write keeps a pointer to its own stock bytes */
    int i, n = 0;
    if (g_game < 3) {
        return 0;
    }
    for (i = 0; i < CW_GRAVE_SITE_COUNT; ++i) {
        const cw_grave_site *c = &CW_GRAVE_SITES[i];
        unsigned char *stock = stocks[i];
        unsigned int rel = c->lookup - (c->va + 5u);
        const void *stub = c->reg == 0 ? (const void *)cw_grave_eax
                         : c->reg == 1 ? (const void *)cw_grave_ebx : (const void *)cw_grave_ebp;
        if (c->game != g_game) {
            continue;
        }
        stock[0] = 0xE8;
        memcpy(stock + 1, &rel, 4);
        if (!cod_bytes_are(c->va, stock, 5)) {
            return -1;                  /* another patch has the site: the companion is not installed */
        }
        vvfp_site_branch(&w[n++], c->va, 5, stock, 0xE8, stub);
        cw_lookup = c->lookup;
    }
    return n;
}
