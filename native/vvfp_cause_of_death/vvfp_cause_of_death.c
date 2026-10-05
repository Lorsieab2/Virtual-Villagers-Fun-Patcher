/* VVFP Cause of Death -- every death, disappearance and unexplained arrival
   or departure in the logs (all five games), and each grave's cause of death
   and epitaph on the game's own grave screen (A New Home, The Lost Children).

   The owner asked, in turn:
     - "for the games that don't write a cause of death like VV1-VV2, can you
       add them please?" -- in the game, the way The Secret City, The Tree of
       Life and New Believers show it;
     - "can you also put the epitaphs for VV1-VV2 too?" -- "the player can
       edit them, but the game has pregenerated ones";
     - "VV1-VV5 should keep track of all deaths (that leave a skeleton) along
       with the age, cause, epitaph and skill (whatever the game has assigned
       to them on their grave) in a log, like how Births are logged!", the age
       in the game's own units;
     - disappearances (no skeleton) in records of their own, and "for
       villagers who somehow can't be reconciled by the logs or loggers,
       please put their data and details in a separate log. No villager gets
       unaccounted for!".

   THE WORDS.  The three later games keep a cause beside health and their
   grave dialog shows the game's own words for it (VV3 string 0x2E6 + cause,
   VV4 0x317, VV5 0x314; identical text in all three):

       -1 Unknown causes   (every island event passes -1)
        0 Disease          1 Starvation       2 Old age
        3 Work accident    4 Act of Nature    (4: no caller in any game)

   A New Home and The Lost Children keep no cause, so this companion records
   it the moment a villager dies, from the place that killed them, in those
   same words: the aging step's old-age store (Old age), its sickness drain
   (Disease), its hunger and no-food drains (Starvation), every work injury
   (Work accident), and -- noticed by the per-frame tick, for a villager seen
   alive on an earlier frame who is now a body with no site having reported
   it -- "Unknown causes", which is how the later games word every island
   event death.  It is kept per record, in the patcher's own file beside the
   saves, until the body is buried or removed:

       <save folder>\Virtual Villagers Fun Patcher Data\Graves\
           Virtual Villagers N Graves - Save S.dat

   WHEN A DEATH IS LOGGED.  A death is final, and its record written, when
   the body is buried -- the grave, its skill line and its epitaph are made in
   that same step -- or when the game removes an unburied body (240 minutes;
   "no grave (never buried)"), or when a burial finds the graveyard full.  A
   body that is revived (Story / Cheat Upgrades) is never buried as dead and
   gets no record for that death.  Everything else a body does before then
   cannot change what its record will say.

   See the parts for the sites: cod_vv12.inc (A New Home, The Lost
   Children), cod_vv345.inc (the later three), cod_epitaph_edit.inc (the
   epitaph's editing, every game), cod_gone.inc (disappearances),
   cod_roster.inc (the save-time reconciliation and arrivals).

   THE LOG.  The records are filed by "VVFP Parentage Export.dll"
   (WriteVillageRecord) -- the same village header, held records, numbered
   roll and Start Over as the Births and Conceptions log.  Without that DLL
   (the Births and Conceptions row off) no log is written; the graves work
   regardless.  The header names the village the statistics companion
   publishes at each save; without Village Statistics nothing did, so the
   logs were unlabelled and shared by every village (Codex, #504 review).
   This companion's own hook on the save call now hands that DLL the save
   buffer and slot first (PublishVillageAtSave), so the logs are headed and
   created at a village's first save either way (cod_roster.inc).

   Installed at run time by VvfpCauseInstall(game, host) from the Origins
   companion; every site's stock bytes are checked first, all or nothing.
   VvfpCauseTick(game) runs every frame after that.  Two companions tell
   it what it cannot see for itself: the Story / Cheat Upgrades companion
   the Custom Island Event's "Disappears" (VvfpCauseVanished) and its new
   villagers (VvfpCauseArrivedBy), and the Births and Conceptions log's every
   birth (VvfpCauseNoteArrival).  Every other villager who joins the village
   gets an "Arrived" record (cod_arrivals.inc). */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include "sidecar_io.h"
#include "save_folder.h"
#include "grave_backfill.h"
#include "arrival_backfill.h"
#include "data_subfolder.h"   /* each kind of data file in its own folder */
#include "vv3_villager_table.h"
#include "vv4_villager_table.h"
#include "vv5_villager_table.h"

/* ---- Counters the tests read (TEST build only) ---------------------------- */
#ifdef VVFP_TEST
struct vvfp_cause_stats {
    int deaths;          /* causes recorded (A New Home, The Lost Children) */
    int unhooked;        /* of those, found by the tick */
    int burials;         /* burials seen */
    int graves_set;      /* graves given a recorded cause */
    int draws;           /* grave lines drawn */
    int logged;          /* WriteVillageRecord calls */
    int published;       /* .dat files written */
    int departed;        /* departures accounted (deaths, disappearances) */
    int arrived;         /* arrivals accounted */
    int unaccounted;     /* Unaccounted records */
    int armed;           /* save hook armed ahead of the install */
    int backfilled;      /* Death records written from a grave no hook saw */
    int arrivals;        /* Arrived records written for an arrival seen live */
    int arrivals_backfilled;  /* Arrived records written by the backfill */
    int births_backfilled;    /* Birth records written by the backfill (VV2-VV5) */
};
__declspec(dllexport) struct vvfp_cause_stats VvfpCauseStats = { 0 };
#define COD_COUNT(field) (++VvfpCauseStats.field)
/* The tests force the next epitaph roll (0 or 1) by writing here; -1 = draw. */
__declspec(dllexport) int VvfpCauseRollTest = -1;
#else
#define COD_COUNT(field) ((void)0)
#endif

/* ---- The game and its host ----------------------------------------------- */

/* The Origins companion's host table (native/shared/story_bridge.h): only
   the slot is used here. */
typedef struct {
    int size;
    int (__stdcall *slot)(void);
} cod_host;

static int g_game;
static const cod_host *g_host;

static int cod_slot(void) {
    int slot = g_host != NULL && g_host->slot != NULL ? g_host->slot() : 0;
    return slot >= 1 && slot <= 5 ? slot : 0;
}

/* ---- Words ------------------------------------------------------------- */

enum {
    CAUSE_UNKNOWN = -1, CAUSE_DISEASE = 0, CAUSE_STARVATION = 1, CAUSE_OLD_AGE = 2,
    CAUSE_WORK = 3, CAUSE_NATURE = 4,
    /* No cause known: the villager died before this patch was installed. */
    CAUSE_NONE = 0x7F
};

static const char *const CAUSE_WORDS[6] = {
    "Unknown causes", "Disease", "Starvation", "Old age", "Work accident", "Act of Nature"
};

static char cause_scratch[64];

static const char *cod_cause_words(int cause) {
    if (cause >= -1 && cause <= 4) {
        return CAUSE_WORDS[cause + 1];
    }
    if (cause == CAUSE_NONE) {
        return "(not recorded: the villager died while this patch was not watching -- before it was installed, or while the village was loading)";
    }
    /* No caller in any game passes anything else; should one, the log says
       what the game stored rather than guessing at words for it. */
    wsprintfA(cause_scratch, "(cause %d)", cause);
    return cause_scratch;
}

/* 0 = none.  New Believers' spelling of each line. */
enum {
    EPITAPH_NONE = 0, EPITAPH_CITIZEN, EPITAPH_FARMER1, EPITAPH_FARMER2,
    EPITAPH_PARENT1, EPITAPH_PARENT2, EPITAPH_HEALER1, EPITAPH_HEALER2,
    EPITAPH_RESEARCH1, EPITAPH_RESEARCH2, EPITAPH_BUILDER1, EPITAPH_BUILDER2,
    EPITAPH_CHILD1, EPITAPH_CHILD2, EPITAPH_COUNT
};
static const char *const EPITAPHS[EPITAPH_COUNT] = {
    NULL, "Respected Citizen", "Child of the Earth", "Nature's Friend",
    "Parent, Teacher, Friend", "Dedicated to Children", "Guardian of Health",
    "Dedicated to Others", "Dedicated Student", "Inspired Inventor",
    "Inspired Architect", "Strong Arms, Big Heart", "Curious and Playful",
    "Loving and Special"
};

/* The longest epitaph the later games keep: char[0x20] in the grave. */
#define EPITAPH_TEXT 32

#define NO_GRAVE_NEVER_BURIED "no grave (never buried: the game removed the body)"
#define NO_GRAVE_FULL "no grave (the graveyard was full)"

/* ---- Villager records, every game --------------------------------------- */

struct game_records {
    unsigned int table;          /* the table's address, or the address of a pointer to it */
    int table_is_pointer;
    unsigned int record_base;    /* the first record's offset in the table */
    unsigned int stride;
    unsigned int slots;
    unsigned int present;        /* u8 */
    unsigned int health;         /* i32 */
    unsigned int age;            /* i32, age units */
    unsigned int name;
    unsigned int name_capacity;
    unsigned int sex;            /* i32 */
    unsigned int pregnant;       /* i32, nonzero while carrying */
    unsigned int litter;         /* i32 */
    unsigned int heathen;        /* u8, New Believers' faction; 0 = none */
    unsigned int snapshot_lo;    /* the bytes kept of a villager for the roster */
    unsigned int snapshot_hi;
};

#define RECORDS_MAX 256

/* The Secret City's, The Tree of Life's and New Believers' table and slot
   count are the stock ones below until the installer reads them from the
   running executable (cod_locate_table): 256 Villagers (Experimental) moves
   each table to 0x800000 and gives it 256 slots. */
static struct game_records REC[6] = {
    { 0 },
    /* A New Home: array [0x48B614] */
    { 0x48B614u, 1, 0u, 0x3D8u, 256u, 0x28u, 0x344u, 0x348u, 0x370u, 0x1Cu, 0x350u,
      0x358u, 0x35Cu, 0u, 0x000u, 0x3D8u },
    /* The Lost Children: pool [0x499F24] */
    { 0x499F24u, 1, 0u, 0xE48Cu, 256u, 0x30u, 0x52Cu, 0x530u, 0x564u, 0x18u, 0x538u,
      0x540u, 0x544u, 0u, 0x500u, 0x800u },
    /* The Secret City: village 0x59E110, records from +0x14 */
    { 0x59E110u, 0, 0x14u, 0x1F8Cu, 150u, 0xF10u, 0xE78u, 0xDC4u, 0xDD4u, 0x19u, 0xDC8u,
      0xE8Cu, 0xE90u, 0u, 0xDC0u, 0xFD0u },
    /* The Tree of Life: manager 0x50E568, records from +0x44 */
    { 0x50E568u, 0, 0x44u, 0x2E3Cu, 150u, 0x1CC4u, 0x1C40u, 0x1B8Cu, 0x1B9Cu, 0x19u, 0x1B90u,
      0x1C4Cu, 0x1C50u, 0u, 0x1B80u, 0x1E80u },
    /* New Believers: manager 0x554148, records from +0x48 */
    { 0x554148u, 0, 0x48u, 0x2F44u, 150u, 0x1CD4u, 0x1C40u, 0x1B8Cu, 0x1B9Cu, 0x19u, 0x1B90u,
      0x1C4Cu, 0x1C50u, 0x1CECu, 0x1B80u, 0x1F80u },
};

#ifdef VVFP_TEST
/* The native harnesses have no game image at the games' addresses: they hand
   their own villager table here. */
static unsigned char *test_table;
/* ...and say whether arming the save hook succeeds: 1 yes, -1 no, 0 try. */
static int test_arm;
/* ...and whether A New Home's Birth records are written (Show Parents in
   Details Screen): 1 yes, -1 no, 0 look beside the executable. */
static int test_vv1_births;
#endif

/* The Secret City, The Tree of Life, New Believers: the villager table and
   its slot count where the executable itself says they are -- the
   `mov ecx, MANAGER` and the slot-count immediate the other companions read
   (native/shared/vvN_villager_table.h) -- so one DLL serves the 150-slot
   build and the 256 one.  Anything unrecognised keeps the stock table. */
static void cod_locate_table(void) {
    const unsigned char *module = (const unsigned char *)(uintptr_t)0x400000u;
    unsigned int rva;
    unsigned int slots;
    switch (g_game) {
    case 3: vv3_villager_table(module, &rva, &slots); break;
    case 4: vv4_villager_table(module, &rva, &slots); break;
    case 5: vv5_villager_table(module, &rva, &slots); break;
    default: return;
    }
    REC[g_game].table = 0x400000u + rva;
    REC[g_game].slots = slots;
}

/* The first record, or NULL while the game has not built the table. */
static unsigned char *cod_records(void) {
    const struct game_records *r = &REC[g_game];
    unsigned char *table;
#ifdef VVFP_TEST
    if (test_table != NULL) {
        return test_table + r->record_base;
    }
#endif
    table = r->table_is_pointer ? *(unsigned char *volatile *)(uintptr_t)r->table
                                : (unsigned char *)(uintptr_t)r->table;
    return table != NULL ? table + r->record_base : NULL;
}

static unsigned char *cod_record(int index) {
    unsigned char *records = cod_records();
    return records != NULL && index >= 0 && (unsigned int)index < REC[g_game].slots
        ? records + (size_t)index * REC[g_game].stride : NULL;
}

static int cod_index_of(const unsigned char *record) {
    unsigned char *records = cod_records();
    size_t span;
    if (records == NULL || record < records) {
        return -1;
    }
    span = (size_t)(record - records);
    if (span % REC[g_game].stride != 0 || span / REC[g_game].stride >= REC[g_game].slots) {
        return -1;
    }
    return (int)(span / REC[g_game].stride);
}

static int rec_present(const unsigned char *record) {
    return record[REC[g_game].present] != 0;
}

static int rec_health(const unsigned char *record) {
    return *(const int *)(record + REC[g_game].health);
}

static int rec_age(const unsigned char *record) {
    return *(const int *)(record + REC[g_game].age);
}

/* Records that look like villagers and are not: The Lost Children's Esteemed
   Elder statue (+0x558), The Secret City's +0xE94 records, The Tree of
   Life's ghosts (+0x1CC7), and New Believers' Reanimate in progress (+0x1CE1
   on the villager; its stand-in corpse is made in the first free record). */
static int rec_lookalike(const unsigned char *record) {
    switch (g_game) {
    case 2: return record[0x558] != 0;
    case 3: return record[0xE94] != 0;
    case 4: return record[0x1CC7] != 0;
    case 5: return record[0x1CE1] != 0;
    default: return 0;
    }
}

/* FNV-1a over a name (to its terminator, at most `capacity` bytes) and an
   age.  A villager's age never changes after death, and the burial copies
   both into the grave, so the same value names the body and its grave.
   Never 0. */
static unsigned int cod_fingerprint(const unsigned char *name, unsigned int capacity, int age) {
    unsigned int h = 2166136261u;
    unsigned int i;
    for (i = 0; i < capacity && name[i] != 0; ++i) {
        h = (h ^ name[i]) * 16777619u;
    }
    h = (h ^ 0xFFu) * 16777619u;
    for (i = 0; i < 4; ++i) {
        h = (h ^ ((unsigned int)age >> (8 * i) & 0xFFu)) * 16777619u;
    }
    return h != 0 ? h : 1u;
}

static unsigned int cod_record_fingerprint(const unsigned char *record) {
    return cod_fingerprint(record + REC[g_game].name, REC[g_game].name_capacity, rec_age(record));
}

/* The name alone, for "this record still holds the villager I saw alive". */
static unsigned int cod_name_hash(const unsigned char *record) {
    return cod_fingerprint(record + REC[g_game].name, REC[g_game].name_capacity, 0);
}

/* ---- The log -------------------------------------------------------------- */

enum { LOG_DEATH = 2, LOG_DISAPPEARED = 3, LOG_EPITAPH = 4, LOG_UNACCOUNTED = 5, LOG_ARRIVED = 6 };

typedef int (__stdcall *write_record_fn)(int game, int kind, const void *record, int check,
                                         const char *before, const char *after, int detail);
typedef int (__stdcall *publish_village_fn)(int game, const void *save_buffer, int slot);
typedef int (__stdcall *release_held_fn)(int game);
static int log_state;            /* 0 = not tried, 1 = resolved, -1 = unavailable */
static write_record_fn write_record;
static publish_village_fn publish_village;
static release_held_fn release_held;
/* RecordGravesMissingFromLog (cod_backfill.inc). */
static vv_record_graves_fn record_graves;
/* RecordArrivalsMissingFromLog (cod_arrivals.inc). */
static vv_record_arrivals_fn record_arrivals;
/* RecordBirthsMissingFromLog (cod_arrivals.inc). */
static vv_record_births_fn record_births;

/* "VVFP Parentage Export.dll", loaded by full path from the executable's
   folder the first time; absent (the Births and Conceptions row off), no
   log is written. */
static int cod_log_ready(void) {
    if (log_state == 0) {
        char path[MAX_PATH];
        char *slash;
        DWORD n;
        HMODULE module;
        log_state = -1;
        n = GetModuleFileNameA(NULL, path, MAX_PATH);
        slash = n != 0 && n < MAX_PATH ? strrchr(path, '\\') : NULL;
        if (slash != NULL
            && (size_t)(slash + 1 - path) + sizeof("VVFP Parentage Export.dll") <= sizeof(path)) {
            lstrcpyA(slash + 1, "VVFP Parentage Export.dll");
            module = LoadLibraryA(path);
            if (module != NULL) {
                write_record = (write_record_fn)GetProcAddress(module, "WriteVillageRecord");
                publish_village = (publish_village_fn)GetProcAddress(module, "PublishVillageAtSave");
                release_held = (release_held_fn)GetProcAddress(module, "ReleaseHeldRecords");
                record_graves = (vv_record_graves_fn)GetProcAddress(module, "RecordGravesMissingFromLog");
                record_arrivals = (vv_record_arrivals_fn)GetProcAddress(module,
                                                                        "RecordArrivalsMissingFromLog");
                record_births = (vv_record_births_fn)GetProcAddress(module, "RecordBirthsMissingFromLog");
                if (write_record != NULL) {
                    log_state = 1;
                }
            }
        }
    }
    return log_state == 1;
}

/* At a save, before anything is reconciled: name the village for the logs
   from the block being saved (the parentage DLL does nothing when the
   statistics companion has already done it at this same save). */
static void cod_publish_village(const void *save_buffer, int slot) {
    if (save_buffer != NULL && cod_log_ready() && publish_village != NULL) {
        (void)publish_village(g_game, save_buffer, slot);
    }
}

/* Hand one record to the parentage DLL. */
static int cod_write(int kind, const void *record, int check, const char *before,
                     const char *after, int detail) {
    if (!cod_log_ready()) {
        return 0;
    }
    COD_COUNT(logged);
    return write_record(g_game, kind, record, check, before, after, detail);
}

/* A printable copy of an epitaph or grave line for a log record. */
static void cod_printable(char *out, int size, const char *text, int capacity) {
    int i;
    for (i = 0; i + 1 < size && i < capacity && text[i] != 0; ++i) {
        unsigned char c = (unsigned char)text[i];
        out[i] = c >= 0x20 && c < 0x7F ? (char)c : '?';
    }
    out[i] = '\0';
}

/* The lines a Death record carries before the villager's identity. */
static int cod_log_death(const unsigned char *record, int cause, const char *grave,
                         const char *epitaph) {
    char before[512];
    wsprintfA(before, "  Age at death: %d\n  Cause of death: %s\n  Grave: %s\n  Epitaph: %s\n",
              rec_age(record), cod_cause_words(cause), grave,
              epitaph != NULL && epitaph[0] != 0 ? epitaph : "(none)");
    return cod_write(LOG_DEATH, record, 1, before, NULL, 1);
}

/* ---- The site machinery ----------------------------------------------------

   Every hook is the same shape: a `jmp` over a run of whole instructions
   with no relative operand and no branch landing inside, to a stub generated
   once into a page written while read/write and then made read/execute
   (never both at once):

       pushad; pushfd; push esp; push <site>; call [cod_site_hit_ptr];
       add esp, 8; popfd; popad; <the displaced bytes>; jmp <site + length>

   The handler runs BEFORE the displaced instructions, with every register
   readable (and the original esp at pushad's slot), and the flags restored
   for them. */
enum { R_FLAGS = 0, R_EDI, R_ESI, R_EBP, R_ESP, R_EBX, R_EDX, R_ECX, R_EAX };
typedef void (*site_fn)(int site, const unsigned int *regs);

struct hook_site {
    unsigned int va;
    unsigned char length;
    unsigned char stock[14];
    site_fn fn;
    /* Free for the handler: a death site's cause and its operands. */
    signed char cause;
    unsigned char kind;
    unsigned char ra;
    unsigned char rb;
};

#define SITES_MAX 48
static struct hook_site sites[SITES_MAX];
static int site_count;

static void __cdecl cod_site_hit(int site, const unsigned int *regs) {
    if (site >= 0 && site < site_count && sites[site].fn != NULL) {
        sites[site].fn(site, regs);
    }
}

static void (__cdecl *const cod_site_hit_ptr)(int, const unsigned int *) = cod_site_hit;
static unsigned char *stub_page;
#define STUB_BYTES 48

static unsigned int reg_stack(const unsigned int *regs, unsigned int offset) {
    return *(const unsigned int *)(uintptr_t)(regs[R_ESP] + offset);
}

static int cod_bytes_are(unsigned int va, const unsigned char *stock, int length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, stock, (size_t)length) == 0;
}

static unsigned char *cod_build_stubs(void) {
    unsigned char *page = (unsigned char *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE,
                                                        PAGE_READWRITE);
    DWORD old;
    int i;
    if (page == NULL || site_count * STUB_BYTES > 4096) {
        return NULL;
    }
    for (i = 0; i < site_count; ++i) {
        unsigned char *p = page + i * STUB_BYTES;
        unsigned int target = (unsigned int)(uintptr_t)&cod_site_hit_ptr;
        int back;
        *p++ = 0x60;                                  /* pushad */
        *p++ = 0x9C;                                  /* pushfd */
        *p++ = 0x54;                                  /* push esp */
        *p++ = 0x68; memcpy(p, &i, 4); p += 4;        /* push site */
        *p++ = 0xFF; *p++ = 0x15; memcpy(p, &target, 4); p += 4;   /* call [ptr] */
        *p++ = 0x83; *p++ = 0xC4; *p++ = 0x08;        /* add esp, 8 */
        *p++ = 0x9D;                                  /* popfd */
        *p++ = 0x61;                                  /* popad */
        memcpy(p, sites[i].stock, sites[i].length);
        p += sites[i].length;
        *p++ = 0xE9;
        back = (int)(sites[i].va + sites[i].length) - (int)((uintptr_t)p + 4);
        memcpy(p, &back, 4);
    }
    if (!VirtualProtect(page, 4096, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return NULL;
    }
    FlushInstructionCache(GetCurrentProcess(), page, 4096);
    return page;
}

/* A `jmp stub` and nops over the displaced bytes. */
static int cod_write_jmp(unsigned int va, int length, const void *stub) {
    unsigned char bytes[16];
    unsigned char *at = (unsigned char *)(uintptr_t)va;
    unsigned int rel = (unsigned int)((const unsigned char *)stub - (at + 5));
    DWORD old;
    int i;
    bytes[0] = 0xE9;
    memcpy(bytes + 1, &rel, 4);
    for (i = 5; i < length; ++i) {
        bytes[i] = 0x90;
    }
    if (!VirtualProtect(at, (SIZE_T)length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)length);
    VirtualProtect(at, (SIZE_T)length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)length);
    return 1;
}

/* Add a site to the table being assembled for this game. */
static void cod_add(unsigned int va, const char *stock_hex, site_fn fn) {
    struct hook_site *s;
    int n = 0;
    if (site_count >= SITES_MAX) {
        return;
    }
    s = &sites[site_count++];
    memset(s, 0, sizeof *s);
    s->va = va;
    while (stock_hex[0] && stock_hex[1] && n < (int)sizeof s->stock) {
        unsigned int hi = (unsigned int)(stock_hex[0] <= '9' ? stock_hex[0] - '0' : (stock_hex[0] | 0x20) - 'a' + 10);
        unsigned int lo = (unsigned int)(stock_hex[1] <= '9' ? stock_hex[1] - '0' : (stock_hex[1] | 0x20) - 'a' + 10);
        s->stock[n++] = (unsigned char)(hi << 4 | lo);
        stock_hex += 2;
    }
    s->length = (unsigned char)n;
    s->fn = fn;
}

/* All or nothing: every site must hold its stock bytes before any is
   written, so a build where another patch took one of them is left alone
   entirely rather than half-recorded. */
static int cod_install_sites(int first) {
    int i;
    for (i = first; i < site_count; ++i) {
        if (sites[i].length < 5 || !cod_bytes_are(sites[i].va, sites[i].stock, sites[i].length)) {
            return 0;
        }
    }
    stub_page = cod_build_stubs();
    if (stub_page == NULL) {
        return 0;
    }
    for (i = first; i < site_count; ++i) {
        if (!cod_write_jmp(sites[i].va, sites[i].length, stub_page + i * STUB_BYTES)) {
            return 0;
        }
    }
    return 1;
}

/* ---- Whom the tick saw alive, and the records that are not the tribe's -- */

static unsigned int seen_alive[RECORDS_MAX];   /* name hash, 0 = not seen alive */
/* A record the game filled for something other than a member of the tribe
   (cod_roster_sites.inc), while it holds it -- and whom it holds: the name
   hash of the stranger or stand-in (0 until it is named).  A load refills
   every record in one call, with no creator and no tick between (New
   Believers 0x46FA20 resets and reads them all; its tick runs only at
   buildSavePath, before the load), so the mark alone outlived its holder
   and the villager the load put in that record was taken for him: never
   one of the tribe, her death or disappearance never logged. */
static unsigned char temporary[RECORDS_MAX];
static unsigned int temporary_name[RECORDS_MAX];

/* Is `record` (index `index`) still the temporary record it was marked as?
   A record that now holds someone else is the tribe's: the mark goes. */
static int cod_temporary(int index, const unsigned char *record) {
    if (!temporary[index]) {
        return 0;
    }
    if (temporary_name[index] != 0 && temporary_name[index] != cod_name_hash(record)) {
        temporary[index] = 0;
        temporary_name[index] = 0;
        return 0;
    }
    return 1;
}
static int install_state;   /* 0 = not tried, 1 = installed, -1 = refused */
/* The save hook alone, armed ahead of the install (VvfpCauseArmSave): it
   is sites[0] from then on, and the install adds every other site after
   it. */
static int save_armed;

/* cod_backfill.inc: the graves no hook saw, at each save. */
static void backfill_at_save(int slot, const void *save_buffer);
static int backfill_accounts_for(const unsigned char *kept);
static void backfill_reset(int slot);

/* cod_arrivals.inc: the Arrived records. */
static void arrival_created(int index, unsigned int site_va, const unsigned int *regs);
static void arrival_tick(void);
static void arrival_departed(int index);
static void arrival_save(int slot, int same_village);
static void arrival_reset(int slot);
static void arrival_noted_birth(int index);
static void arrival_backfill_at_save(int slot, const void *save_buffer);
static void births_backfill_at_save(int slot, const void *save_buffer);

#include "cod_roster.inc"
#include "cod_gone.inc"
#include "cod_vv12.inc"
#include "cod_vv345.inc"
#include "cod_epitaph_edit.inc"
#include "cod_backfill.inc"
#include "cod_arrivals.inc"

/* ---- Exports --------------------------------------------------------------- */

__declspec(dllexport) int __stdcall VvfpCauseInstall(int game, const void *host) {
    if (install_state != 0) {
        return install_state == 1 && game == g_game;
    }
    install_state = -1;
    if (game < 1 || game > 5) {
        return 0;
    }
    g_game = game;
    if (host != NULL && ((const cod_host *)host)->size >= (int)sizeof(cod_host)) {
        g_host = (const cod_host *)host;
    }
    cod_locate_table();
    /* An armed save hook stays sites[0], already written; the rest follow. */
    site_count = save_armed ? 1 : 0;
    if (game <= 2) {
        vv12_sites();
        epitaph_edit_sites();
    } else {
        v345_sites();
        v345_edit_sites();
    }
    gone_sites();
    roster_sites();
    if (!save_armed) {
        roster_save_site();
    }
    if (cod_install_sites(save_armed ? 1 : 0)) {
        install_state = 1;
    } else if (cod_log_ready() && release_held != NULL) {
        /* Refused: this companion will never name a village at a save, so
           the parentage DLL must not keep holding records for it (#512
           review) -- they are written now, unlabelled, in order. */
        (void)release_held(game);
    }
    return install_state == 1;
}

/* Every frame: whom the tick sees alive, the temporary records still held,
   and A New Home's and The Lost Children's graves file and the deaths no
   site reported. */
static int temporary_slot = -1;  /* the village the temporary marks belong to */

__declspec(dllexport) void __stdcall VvfpCauseTick(int game) {
    unsigned char *records;
    int i;
    if (install_state != 1 || game != g_game) {
        return;
    }
    standin_pending = 0;
    records = cod_records();
    if (cod_slot() != temporary_slot) {
        /* Another village: nothing of the last one's is temporary here.
           (The first tick only learns the slot: nothing came before it.) */
        if (temporary_slot >= 0) {
            memset(temporary, 0, sizeof temporary);
            memset(temporary_name, 0, sizeof temporary_name);
        }
        temporary_slot = cod_slot();
    }
    for (i = 0; i < RECORDS_MAX; ++i) {
        const unsigned char *record;
        if (!temporary[i]) {
            continue;
        }
        if (records == NULL || (unsigned int)i >= REC[g_game].slots
            || !rec_present(record = records + (size_t)i * REC[g_game].stride)) {
            temporary[i] = 0;
            temporary_name[i] = 0;
        } else if (temporary_name[i] == 0) {
            temporary_name[i] = cod_name_hash(record);   /* named by now (New Believers' 0x420015) */
        }
    }
    if (g_game <= 2) {
        vv12_tick();
    }
    seen_tick();
    arrival_tick();
}

/* Arm the save hook alone, before the install (Codex, #512 review).

   "VVFP Startup.dll" installs this companion at game start, before any
   village loads.  Without that loader (its file missing), the Origins
   companion installs it once a village is shown -- in The Secret City only
   when a villager is first drawn or the Origins menu opens -- but records
   from the load-time catch-up are held for this
   companion's save hook to name the village. A save made before the
   install would leave them held, and lost at exit. So the parentage DLL,
   the first time it holds a record for this companion, arms the save hook
   here: at a save it then names the village (cod_save_done), and nothing
   else runs until the install, which keeps it as sites[0]. Only the save
   hook's own stock bytes are checked and written. Returns 1 when armed or
   installed. */
__declspec(dllexport) int __stdcall VvfpCauseArmSave(int game) {
    if (install_state == 1 || save_armed) {
        return 1;
    }
    if (install_state != 0 || game < 1 || game > 5 || (g_game != 0 && game != g_game)) {
        return 0;
    }
    g_game = game;
#ifdef VVFP_TEST
    /* The harnesses map no game: they say whether arming succeeds. */
    if (test_arm != 0) {
        save_armed = test_arm > 0;
        if (save_armed) {
            COD_COUNT(armed);
        }
        return save_armed;
    }
#endif
    cod_locate_table();
    site_count = 0;
    roster_save_site();
    if (cod_install_sites(0)) {
        save_armed = 1;
        COD_COUNT(armed);
    } else {
        site_count = 0;
    }
    return save_armed;
}

/* Whether this companion names the village at each save for the logs
   (cod_roster.inc): 1 installed, 0 not installed yet, -1 refused -- in
   which case its save hook never runs and the parentage DLL must not wait
   for it. */
__declspec(dllexport) int __stdcall VvfpCauseNamesVillage(void) {
    return install_state;
}

/* Start Over erased `slot`: forget everything held for it before the reset
   deletes its files, so nothing held in memory is written back into the new
   village. */
__declspec(dllexport) void __stdcall VvfpCauseVillageReset(int game, int slot) {
    if (install_state != 1 || game != g_game) {
        return;
    }
    if (g_game <= 2) {
        vv12_reset(slot);
    }
    roster_reset(slot);
    backfill_reset(slot);
    arrival_reset(slot);
    memset(seen_alive, 0, sizeof seen_alive);
    memset(temporary, 0, sizeof temporary);
    memset(temporary_name, 0, sizeof temporary_name);
}

#ifdef VVFP_TEST
#include "cod_test.inc"
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
