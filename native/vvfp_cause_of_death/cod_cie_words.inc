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

   FORMAT (little-endian), exactly 16 + 68 * count bytes:
       u32 magic 'VCW1', u32 version 1, u32 game (1..5), u32 count (at most CW_MAX),
       count x { u32 fingerprint (never 0), char words[64] (bytes 0x20-0x7E, NUL-terminated and NUL-filled, at
                 least one character) }
   each fingerprint once.  A file that is not exactly this is set aside unread (sidecar_io.h), never misread. */

#define CW_MAGIC 0x31574356u           /* 'VCW1' */
#define CW_VERSION 1u
#define CW_HEADER 16u
#define CW_WORDS 64
#define CW_ENTRY (4u + CW_WORDS)
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

static unsigned char cw_buffer[CW_HEADER + CW_MAX * CW_ENTRY];

static int cw_words_ok(const unsigned char *w) {
    int i, ended = 0;
    if (w[0] == 0) {
        return 0;
    }
    for (i = 0; i < CW_WORDS; ++i) {
        if (w[i] == 0) {
            ended = 1;
        } else if (ended || w[i] < 0x20 || w[i] > 0x7E) {
            return 0;
        }
    }
    return ended;
}

static int cw_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count, i, k;
    (void)context;
    if (length < CW_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != CW_MAGIC || *(const unsigned int *)(data + 4) != CW_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game || count > CW_MAX
        || length != CW_HEADER + count * CW_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + CW_HEADER + i * CW_ENTRY;
        unsigned int fingerprint = *(const unsigned int *)e;
        if (fingerprint == 0u || !cw_words_ok(e + 4)) {
            return 0;
        }
        for (k = 0; k < i; ++k) {
            if (*(const unsigned int *)(data + CW_HEADER + k * CW_ENTRY) == fingerprint) {
                return 0;
            }
        }
    }
    return 1;
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
        unsigned int count = *(const unsigned int *)(cw_buffer + 12), i;
        for (i = 0; i < count && cw.count < CW_MAX; ++i) {
            const unsigned char *e = cw_buffer + CW_HEADER + i * CW_ENTRY;
            if (cw_find(*(const unsigned int *)e) < 0) {
                cw.fingerprint[cw.count] = *(const unsigned int *)e;
                memcpy(cw.words[cw.count], e + 4, CW_WORDS);
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

/* Keep `words` for the body with `fingerprint` (printable ASCII, at most CW_WORDS - 1 = 63 kept, the editor's limit; the oldest entry
   gives way when the table is full). */
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
    for (i = 0; i < cw.count; ++i) {
        unsigned char *e = cw_buffer + CW_HEADER + (unsigned int)i * CW_ENTRY;
        *(unsigned int *)e = cw.fingerprint[i];
        memcpy(e + 4, cw.words[i], CW_WORDS);
    }
    ((unsigned int *)cw_buffer)[0] = CW_MAGIC;
    ((unsigned int *)cw_buffer)[1] = CW_VERSION;
    ((unsigned int *)cw_buffer)[2] = (unsigned int)g_game;
    ((unsigned int *)cw_buffer)[3] = (unsigned int)cw.count;
    parts[0] = cw_buffer;
    sizes[0] = CW_HEADER + (unsigned int)cw.count * CW_ENTRY;
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
   body).  As VvfpCauseKilled, with the words kept for the Death record and the grave (`words`, at most 63
   characters are kept). */
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
