/* VVFP Faith Loss -- the per-villager rule of "Faith Loss is Doubled/Gains Halved", New Believers.

   WHAT.  The owner (2026-11-08): "villagers should preferentially die if their faith decrease-turn heathen is due
   to starvation or disease ... so most starving villagers die / most sick people die instead of them all turning
   heathen" -- decided once per villager per crisis, not on every roll (a roll each age unit would still convert
   nearly everyone over a long famine), and 1 in 10.  A Heathen is skipped by the life tick (0x472CB7): it never
   eats, starves, falls ill or loses health, so a believer the drift turns Heathen escapes hunger and sickness.

   The owner (2026-11-20, after a small village's believers left far more than they died): once per villager PER
   CAUSE per crisis, with "too few believers" a crisis too.  Four causes: starvation (food under 10), hunger (food
   10 to 250), sickness, too few believers (fewer than 12, carried babies counted).

   THE RULE.  The row's exe bytes say in ebp which losses the drift 0x468040 made (bit 0 a food loss, bit 1 the
   sickness loss; too few believers' loss, the last, complements ebp: scripts/build_apprentice_faith_puddles_
   features.py FAITH_LOSS_MARKS) and send its final FAITH_ADD through a cave that first calls a rule (the call at
   0x494F14, whose own target 0x494F28 is the rule without this companion).  This companion takes that call:
     * each cause a believer is marked for whose crisis is over is unmarked first, on its own: starvation and
       hunger when food ([0x51D34C]) is above 250, sickness when not sick (+0x1C48), too few believers when the
       game's own count (0x4713F0 on the manager the drift names at 0x46815F) is 12 or more;
     * a fall (the sum esi < 0) that takes Faith to 0 or less: the gains are taken first, then the losses one by
       one in the drift's order (the food loss -- starvation or hunger by the food now -- sickness, too few
       believers).  The loss that would take the last Faith is its cause's: a cause the believer is marked for
       holds them at Faith 1 (that loss is not made); an unmarked one is decided now, once -- rand(N) < 1 (the
       game's own rand, 0x403660; N the cause's FL_ODDS_*, 10 for each today) the drift's own sum is made and the believer becomes a Heathen as before;
       otherwise the believer is marked for that cause and held at Faith 1.  A later loss of another cause in
       the same drift is decided the same way;
     * anything else is the drift's own sum: rises and falls that leave Faith above 0.
   A marked believer keeps eating, starving, falling ill and losing health in the life tick like any believer, so
   starvation or sickness kills them as usual.  It is the one place all of it runs -- live, in the load-time
   catch-up, a Time Warp and Choose Time Skip Amount -- since the life tick (0x472D17) is the drift's only caller.

   THE FILE.  A mark is a villager's identity (the name, likes and dislikes: native/shared/custom_titles.h's
   vv_title_identity, as the Former Heathens file keys them) with what follows it through a change of one part
   of it (Codex, #732: a rename, or the Custom Island Event's likes and dislikes, must not lose the mark and give
   a second roll): the record the villager was last seen in, what a likes / dislikes change leaves (the name and
   the sex, identity_in_place.h's vv_identity_keep), what a rename leaves (the likes, dislikes and sex, as the
   Former Heathens' rename rule, cod_former.inc former_stable) and the age last seen.  A villager is the mark's
   when the identity is the same, or -- in the same record, not younger -- one of the two parts is (and the mark
   then takes the new identity), so a renamed or re-liked villager keeps it, and a newborn or newcomer put in a
   dead villager's record (younger, or neither part the same) never inherits it.  The marks are kept per save in
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Faith Loss\Believers Kept - Save <S>.dat
   (sidecar_io.h: atomic writes, an unreadable file never replaced, an invalid one set aside; refused only when the
   whole path, with the set-aside name's room, would not fit in MAX_PATH).  It is read when the
   game's save slot (the save manager's own field, set before the slot's village is created or loaded:
   native/shared/game_save_slot.h) is first seen, so the load-time catch-up already has them; it is written each
   time a mark is made or cleared, with only the marks of villagers who are living believers then (matched as
   above, so a renamed villager's mark is carried, never pruned).  Start Over deletes
   the save's folder, and the file with it (native/shared/save_reset.c).  The save itself is never written.

   FORMAT (little-endian): u32 magic 'VFK1', u32 version 2, u32 game 5, u32 slot, u32 count (0..FL_MARKS_MAX),
   then `count` entries of 6 u32: identity, record (0..255), keep, stable, age, causes (FL_STARVATION ..
   FL_TOO_FEW, 1 or more).  Exactly 20 + 24 * count bytes.  A version 1 file (entries of 5 u32, one mark for food
   and sickness together) is read with its marks for starvation, hunger and sickness, and written as version 2.

   SAFETY.  One call site, in the row's own cave, checked to hold the row's bytes before it is written (all or
   none, native/shared/install_sites.h).  Our steps run under structured exception handling: a fault gives the
   drift's own sum.  No debug output. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/custom_titles.h"
#include "../shared/identity_in_place.h"   /* vv_identity_keep */

#define FL_GAME 5
#define FL_RULE_CALL 0x494F14u          /* the tail cave's call of the rule */
#define FL_RULE_CAVE 0x494F28u          /* its own target: the rule without this companion */
#define FL_RAND 0x403660u
#define FL_FOOD 0x51D34Cu
#define FL_CRISIS_FOOD 250              /* food above this: no food roll applies */
#define FL_STARVING 10                  /* food under this: starvation (the drift's own boundary, 0x468044) */
/* Each cause's odds of a Heathen when it is decided: 1 in FL_ODDS_<cause>, as rand(N) < 1 (the game's own rand).
   The owner picks these (2026-11-22: all 1 in 10 until then). */
#define FL_ODDS_STARVATION 10
#define FL_ODDS_HUNGER 10
#define FL_ODDS_SICKNESS 10
#define FL_ODDS_TOO_FEW 10
#define FL_FEW 12                       /* fewer believers than this: too few (0x468174) */
#define FL_BELIEVERS 0x4713F0u          /* the game's believer count (thiscall on the villager manager) */
#define FL_BELIEVERS_MANAGER 0x46815Fu  /* the drift's `mov ecx, <manager>` immediate */

/* The causes (a mark's bits). */
#define FL_STARVATION 1u
#define FL_HUNGER 2u
#define FL_SICKNESS 4u
#define FL_TOO_FEW 8u
#define FL_CAUSES 15u
/* ebp from the drift: bit 0 a food loss, bit 1 the sickness loss; complemented (< 0) for too few believers. */
#define FL_LOST_FOOD 1
#define FL_LOST_SICK 2

/* New Believers' villager record. */
#define REC_FIRST 0x48u
#define REC_STRIDE 0x2F44u
#define REC_AGE 0x1B8Cu
#define REC_SEX 0x1B90u
#define REC_NAME 0x1B9Cu
#define REC_NAME_CAP 0x19u
#define REC_HEALTH 0x1C40u
#define REC_SICK 0x1C48u
#define REC_PRESENT 0x1CD4u             /* 0x466170: a villager */
#define REC_STAND_IN 0x1CE1u            /* 0x466170(0): not a stand-in */
#define REC_HEATHEN 0x1CECu
#define REC_FAITH 0x1CF0u
#define REC_LIKES 0x1F5Cu
#define REC_DISLIKES 0x1F68u
#define REC_SLOTS 3u

#define FL_MARKS_MAX 256
#define FL_MAGIC 0x314B4656u            /* 'VFK1' */
#define FL_VERSION 2u
#define FL_VERSION_1 1u                 /* entries of 5 u32, one mark for food and sickness */
#define FL_ENTRY_1 20u
#define FL_HEADER 20u
#define FL_RESERVE ((int)sizeof(".unreadable-4294967295-999"))   /* sidecar_io.h's set-aside name */

typedef int (__cdecl *rand_fn)(int);

typedef struct {
    unsigned int identity;
    unsigned int record;                /* the record the villager was last seen in */
    unsigned int keep;                  /* the name and sex (what a likes / dislikes change leaves) */
    unsigned int stable;                /* the likes, dislikes and sex (what a rename leaves) */
    int age;                            /* the age last seen */
    unsigned int causes;                /* the crises the villager was decided to stay through */
} fl_mark;

static int g_installed;
static fl_mark g_marks[FL_MARKS_MAX];
static int g_count;
static int g_slot;                      /* the slot whose file the marks are (0: none read yet) */
static vv_sidecar_gate g_gate;
static unsigned char g_buffer[FL_HEADER + sizeof(fl_mark) * FL_MARKS_MAX];
static int g_file_seen;                 /* the file was read or written for g_slot */
static DWORD g_reset_checked;

static unsigned int identity(const unsigned char *rec) {
    return vv_title_identity(rec, REC_NAME, REC_NAME_CAP, REC_LIKES, REC_DISLIKES, REC_SLOTS);
}

static unsigned int keep_of(const unsigned char *rec) {
    return vv_identity_keep(rec, REC_NAME, REC_NAME_CAP, REC_SEX);
}

static unsigned int stable_of(const unsigned char *rec) {
    unsigned int h = vv_title_identity(rec, REC_NAME, 0u, REC_LIKES, REC_DISLIKES, REC_SLOTS);
    h = (h ^ (unsigned int)*(const int *)(rec + REC_SEX)) * 16777619u;
    return h ? h : 1u;
}

/* The villager in record `index` now, as a mark keeps it. */
static fl_mark mark_of(const unsigned char *rec, int index) {
    fl_mark m;
    m.identity = identity(rec);
    m.record = (unsigned int)index;
    m.keep = keep_of(rec);
    m.stable = stable_of(rec);
    m.age = *(const int *)(rec + REC_AGE);
    m.causes = 0;
    return m;
}

/* Carry mark `m` to who its villager is `now`, keeping its causes. */
static void carry(fl_mark *m, const fl_mark *now) {
    unsigned int causes = m->causes;
    *m = *now;
    m->causes = causes;
}

/* Whether mark `m` is the villager `now` (see THE FILE): the same identity, or in the same record, not younger,
   with the part a rename or a likes / dislikes change leaves. */
static int mark_is(const fl_mark *m, const fl_mark *now) {
    if (m->identity == now->identity) {
        return 1;
    }
    return m->record == now->record && now->age >= m->age && (m->keep == now->keep || m->stable == now->stable);
}

/* The mark of the villager in record `index` (`rec`), carried to who they are now; -1 when none. */
static int marked_at(const unsigned char *rec, int index) {
    fl_mark now = mark_of(rec, index);
    int i;
    for (i = 0; i < g_count; ++i) {
        if (g_marks[i].identity == now.identity) {
            carry(&g_marks[i], &now);
            return i;
        }
    }
    for (i = 0; i < g_count; ++i) {
        if (mark_is(&g_marks[i], &now)) {
            carry(&g_marks[i], &now);      /* renamed or re-liked: the mark follows them */
            return i;
        }
    }
    return -1;
}

/* ---- the file --------------------------------------------------------------------------------------------- */

/* "<Documents>\LDW\<executable's name>\Virtual Villagers Fun Patcher\Save <S>\Data\Faith Loss\
   Believers Kept - Save <S>.dat"; `make` creates the folders. */
static int marks_path(int slot, char *out, int make) {
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\Faith Loss"
    };
    char docs[MAX_PATH], exe[MAX_PATH], part[64], level[64];
    char *base = exe, *p, *dot = NULL;
    DWORD n;
    int i, length;
    if (slot < 1 || slot > 5 || !SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    for (p = exe; *p != '\0'; ++p) {
        if (*p == '\\') {
            base = p + 1;
            dot = NULL;
        } else if (*p == '.') {
            dot = p;
        }
    }
    if (dot != NULL) {
        *dot = '\0';
    }
    /* The whole path's own length, with room for sidecar_io.h's set-aside name.  It was a fixed guess (160 for
       the rest) that refused a long executable name -- "Virtual Villagers - New Believers - Modded 256" under
       OneDrive\Documents -- though the path is far under MAX_PATH: no mark was ever read or written there, so
       every game start rolled every held believer again. */
    wsprintfA(part, "\\Believers Kept - Save %d.dat", slot);
    length = lstrlenA(docs) + 5 + lstrlenA(base) + lstrlenA(part);
    for (i = 0; i < 4; ++i) {
        length += lstrlenA(LEVELS[i]);             /* "%d" is 2 wide, the slot's digit 1: never short */
    }
    if (base[0] == '\0' || length >= MAX_PATH - FL_RESERVE) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; i < 4; ++i) {
        wsprintfA(level, LEVELS[i], slot);
        lstrcatA(out, level);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    if (len < FL_HEADER || u[0] != FL_MAGIC || (u[1] != FL_VERSION && u[1] != FL_VERSION_1) || u[2] != FL_GAME
        || u[3] != (unsigned int)*(const int *)ctx || u[4] > FL_MARKS_MAX) {
        return 0;
    }
    return len == FL_HEADER + (u[1] == FL_VERSION ? sizeof(fl_mark) : FL_ENTRY_1) * u[4];
}

/* The file's marks (`data`, checked by valid_file) into g_marks: a version 1 mark (food and sickness together)
   is marked for starvation, hunger and sickness. */
static void take_file(const unsigned char *data) {
    const unsigned int *u = (const unsigned int *)data;
    int i;
    g_count = (int)u[4];
    if (u[1] == FL_VERSION) {
        memcpy(g_marks, data + FL_HEADER, sizeof(fl_mark) * (unsigned int)g_count);
        return;
    }
    for (i = 0; i < g_count; ++i) {
        memcpy(&g_marks[i], data + FL_HEADER + FL_ENTRY_1 * (unsigned int)i, FL_ENTRY_1);
        g_marks[i].causes = FL_STARVATION | FL_HUNGER | FL_SICKNESS;
    }
}

/* 1 while the slot's file could not be read (locked, a read failed, its folder not known yet): the load is
   retried on the gate's own throttle until it settles (Codex, #732) -- the gate refuses every write meanwhile. */
static int g_load_blocked;

/* The marks of `slot`'s file (none when it is missing, set aside or blocked).  `merge`: a retry after a blocked
   load -- the marks made since (kept only in memory, as the gate refused to write them) are kept beside the
   file's, never duplicated (the same identity is one mark). */
static void read_marks(int slot, int merge) {
    static fl_mark pending[FL_MARKS_MAX];
    char path[MAX_PATH];
    DWORD got = 0;
    int kept = merge ? g_count : 0, i, k, status;
    if (kept > 0) {
        memcpy(pending, g_marks, sizeof(fl_mark) * (unsigned int)kept);
    }
    g_count = 0;
    g_load_blocked = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!marks_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_gate);            /* retried on the gate's throttle */
        g_load_blocked = 1;
    } else {
        status = vv_sidecar_load(&g_gate, path, g_buffer, sizeof g_buffer, &got, valid_file, &slot);
        if (status == VV_SIDECAR_LOAD_VALID) {
            take_file(g_buffer);
        }
        g_load_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    }
    for (i = 0; i < kept; ++i) {
        for (k = 0; k < g_count && g_marks[k].identity != pending[i].identity; ++k) {
        }
        if (k < g_count) {
            g_marks[k].causes |= pending[i].causes;
        } else if (g_count < FL_MARKS_MAX) {
            g_marks[g_count++] = pending[i];
        }
    }
}

/* The villager table, as the executable says it is (150 or 256 slots). */
static const unsigned char *g_records;
static int g_slots;

static void locate(void) {
    unsigned int rva = 0, slots = 0;
    const unsigned char *module;
    if (g_records != NULL) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleW(NULL);
    if (module == NULL) {
        return;
    }
    vv5_villager_table(module, &rva, &slots);
    g_records = module + rva + REC_FIRST;
    g_slots = (int)slots;
}

static int living_believer(const unsigned char *rec) {
    return rec[REC_PRESENT] != 0 && rec[REC_STAND_IN] == 0 && *(const int *)(rec + REC_HEALTH) > 0
           && rec[REC_HEATHEN] == 0;
}

/* Only the marks of living believers are kept (a mark is a believer's: one who died or left has none), each
   carried to who its villager is now -- a renamed or re-liked villager's mark is never pruned. */
static void keep_living(void) {
    static fl_mark now[FL_MARKS_MAX];
    static unsigned char living[FL_MARKS_MAX];
    int i, k, kept = 0, n;
    locate();
    if (g_records == NULL || g_slots <= 0) {
        return;
    }
    n = g_slots < FL_MARKS_MAX ? g_slots : FL_MARKS_MAX;
    for (k = 0; k < n; ++k) {                       /* one look at the village */
        const unsigned char *rec = g_records + (unsigned int)k * REC_STRIDE;
        living[k] = (unsigned char)living_believer(rec);
        if (living[k]) {
            now[k] = mark_of(rec, k);
        }
    }
    for (i = 0; i < g_count; ++i) {
        int found = -1;
        for (k = 0; k < n && found < 0; ++k) {
            if (living[k] && now[k].identity == g_marks[i].identity) {
                found = k;
            }
        }
        for (k = 0; k < n && found < 0; ++k) {
            if (living[k] && mark_is(&g_marks[i], &now[k])) {
                found = k;
            }
        }
        if (found >= 0 && (g_marks[i].causes & FL_CAUSES) != 0) {
            carry(&g_marks[i], &now[found]);
            g_marks[kept++] = g_marks[i];
        }
    }
    g_count = kept;
}

static void write_marks(void) {
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2];
    char path[MAX_PATH];
    if (g_slot == 0) {
        return;
    }
    keep_living();
    header[0] = FL_MAGIC;
    header[1] = FL_VERSION;
    header[2] = FL_GAME;
    header[3] = (unsigned int)g_slot;
    header[4] = (unsigned int)g_count;
    if (!marks_path(g_slot, path, 1)) {
        return;
    }
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_marks;
    sizes[1] = (DWORD)(sizeof(fl_mark) * (unsigned int)g_count);
    if (vv_sidecar_publish(&g_gate, path, parts, sizes, g_count > 0 ? 2 : 1)) {
        g_file_seen = 1;
    }
}

/* Forget the marks and the file's state: the next drift reads the slot's file afresh (Codex, #732: Start Over in
   the same slot deleted the file, and a new founder in a marked record could otherwise take the old mark). */
static void forget_marks(void) {
    g_count = 0;
    g_slot = 0;
    g_load_blocked = 0;
    memset(&g_gate, 0, sizeof g_gate);
}

/* Whether the slot's file is gone while marks were read from it or written to it: Start Over or a deleted tribe
   (native/shared/save_reset.c deletes the save's folder), seen even when VVFP Story Upgrades.dll is not there to
   say so.  Looked at once in FL_RESET_CHECK_MS. */
#define FL_RESET_CHECK_MS 2000u

static int file_was_deleted(void) {
    char path[MAX_PATH];
    DWORD now = GetTickCount();
    if (!g_file_seen || g_slot == 0 || now - g_reset_checked < FL_RESET_CHECK_MS) {
        return 0;
    }
    g_reset_checked = now;
    return marks_path(g_slot, path, 0) && GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES
           && (GetLastError() == ERROR_FILE_NOT_FOUND || GetLastError() == ERROR_PATH_NOT_FOUND);
}

/* The marks are the slot's: read when the game's slot is first seen (it is set before the slot's village is
   made or loaded, so before the load-time catch-up), and again after a reset. */
static void bind_slot(void) {
    int slot = vv_game_save_slot(FL_GAME);
    if (slot != 0 && slot == g_slot && file_was_deleted()) {
        forget_marks();
    }
    if (slot != 0 && slot != g_slot) {
        read_marks(slot, 0);
        g_slot = slot;
        g_file_seen = g_count > 0;
    } else if (slot != 0 && g_load_blocked && !vv_sidecar_gate_throttled(&g_gate)) {
        int had = g_count;
        read_marks(slot, 1);                       /* the lock may have cleared: load it now */
        if (!g_load_blocked) {
            g_file_seen = g_file_seen || g_count > 0;
            if (had > 0) {
                write_marks();                     /* the marks made while blocked reach the file */
            }
        }
    }
}

/* ---- the rule --------------------------------------------------------------------------------------------- */

/* The record's place in the villager table (-1 outside it). */
static int record_index(const unsigned char *rec) {
    UINT_PTR offset;
    locate();
    if (g_records == NULL || rec < g_records) {
        return -1;
    }
    offset = (UINT_PTR)(rec - g_records);
    return offset % REC_STRIDE == 0 && offset / REC_STRIDE < (UINT_PTR)g_slots ? (int)(offset / REC_STRIDE) : -1;
}

/* 0x4713F0 is a thiscall with no stack arguments (the drift: mov ecx, <manager>; call): a fastcall's ecx, with edx
   unused, is the same call. */
typedef int (__fastcall *believers_fn)(void *manager, int unused);

/* The game's own believer count (the drift's, 0x4713F0 on the manager it names). */
static int believers_now(void) {
    void *manager = *(void *const *)(UINT_PTR)FL_BELIEVERS_MANAGER;
    return ((believers_fn)(UINT_PTR)FL_BELIEVERS)(manager, 0);
}

/* The causes of the marked villager `at` whose crises are over. */
static unsigned int crises_over(int at, const unsigned char *rec) {
    unsigned int causes = g_marks[at].causes, over = 0;
    if ((causes & (FL_STARVATION | FL_HUNGER)) && *(const volatile int *)(UINT_PTR)FL_FOOD > FL_CRISIS_FOOD) {
        over |= FL_STARVATION | FL_HUNGER;
    }
    if ((causes & FL_SICKNESS) && rec[REC_SICK] == 0) {
        over |= FL_SICKNESS;
    }
    if ((causes & FL_TOO_FEW) && believers_now() >= FL_FEW) {
        over |= FL_TOO_FEW;
    }
    return causes & over;
}

/* The odds of cause `cause` (one FL_ cause bit): the N of its 1 in N. */
static int odds_of(unsigned int cause) {
    switch (cause) {
    case FL_STARVATION:
        return FL_ODDS_STARVATION;
    case FL_HUNGER:
        return FL_ODDS_HUNGER;
    case FL_SICKNESS:
        return FL_ODDS_SICKNESS;
    default:
        return FL_ODDS_TOO_FEW;
    }
}

static int __cdecl faith_rule(unsigned char *rec, int sum, int lost) {
    int result = sum;
    __try {
        unsigned int order[3], held, made_marks = 0;
        int at, faith, index, losses = 0, level, i, too_few;
        bind_slot();
        index = record_index(rec);
        at = marked_at(rec, index);
        if (at >= 0) {
            unsigned int over = crises_over(at, rec);
            if (over != 0) {                       /* each crisis over on its own: the next is decided afresh */
                g_marks[at].causes &= ~over;
                if (g_marks[at].causes == 0) {
                    g_marks[at] = g_marks[--g_count];
                    at = -1;
                }
                write_marks();
                if (at >= 0) {
                    at = marked_at(rec, index);    /* write_marks may have moved it */
                }
            }
        }
        faith = *(const int *)(rec + REC_FAITH);
        if (sum >= 0 || faith + sum > 0) {
            return sum;                            /* no loss takes the last Faith */
        }
        /* The losses, in the drift's order. */
        too_few = lost < 0;
        if (too_few) {
            lost = ~lost;
        }
        if (lost & FL_LOST_FOOD) {
            order[losses++] = *(const volatile int *)(UINT_PTR)FL_FOOD < FL_STARVING ? FL_STARVATION : FL_HUNGER;
        }
        if (lost & FL_LOST_SICK) {
            order[losses++] = FL_SICKNESS;
        }
        if (too_few) {
            order[losses++] = FL_TOO_FEW;
        }
        level = faith + sum + losses;              /* the Faith after the gains alone */
        if (losses == 0 || faith <= 0 || level <= 0) {
            return sum;
        }
        held = at >= 0 ? g_marks[at].causes : 0;
        for (i = 0; i < losses; ++i) {
            if (level > 1) {
                --level;                           /* not the last Faith: the loss is made */
            } else if ((held & order[i]) == 0) {
                if (((rand_fn)(UINT_PTR)FL_RAND)(odds_of(order[i])) < 1) {
                    return sum;                    /* 1 in N: a Heathen, as before (no mark needed) */
                }
                held |= order[i];                  /* otherwise: marked for this cause, held at Faith 1 */
                made_marks |= order[i];
            }
        }
        if (made_marks) {
            if (at < 0) {
                if (g_count >= FL_MARKS_MAX) {
                    keep_living();                 /* a dead or replaced villager's mark frees its place (Codex, #732) */
                }
                if (g_count < FL_MARKS_MAX) {
                    g_marks[g_count] = mark_of(rec, index);
                    g_marks[g_count++].causes = made_marks;
                }
            } else {
                g_marks[at].causes |= made_marks;
            }
            write_marks();
        }
        result = level - faith;                    /* stays a believer, at Faith `level` (1 or more) */
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = sum;
    }
    return result;
}

/* In place of the tail cave's `call 0x494F28`: esi the sum, ebp the food and sickness losses, ebx the record;
   the sum to apply comes back in esi, every other register as it was. */
__declspec(naked) static void rule_call(void) {
    __asm {
        pushad
        push ebp
        push esi
        push ebx
        call faith_rule
        add esp, 12
        mov dword ptr [esp + 4], eax       /* pushad's esi */
        popad
        ret
    }
}

/* 1 when the rule is installed, else 0. */
int __stdcall VvfpFaithLossInstalled(void) {
    return g_installed;
}

/* Start Over or a deleted tribe (VVFP Story Upgrades.dll's VvfpStoryVillageReset forwards it): the village the
   marks were for is gone; the next drift reads the slot's file afresh. */
void __stdcall VvfpFaithLossVillageReset(int game) {
    if (game == FL_GAME) {
        forget_marks();
    }
}

/* How many believers are marked to stay, for the save slot now. */
int __stdcall VvfpFaithLossMarked(void) {
    return g_count;
}

/* A VILLAGER'S SEX CHANGED (native/shared/sex_change.h): `record` live, `before` as it was.  A mark's identity
   holds no sex, so the mark is still theirs; its keep and stable parts (which do hold it) are taken from the record
   now and written, so a rename after the change is still told as one.  1 when a mark was carried. */
int __stdcall VvfpVillagerSexChanged(int game, int slot, const void *record, const void *before) {
    int carried = 0;
    if (game != FL_GAME || record == NULL || before == NULL || slot <= 0 || slot != g_slot) {
        return 0;
    }
    __try {
        const unsigned char *rec = (const unsigned char *)record;
        int index = record_index(rec), i;
        fl_mark was = mark_of((const unsigned char *)before, index);
        for (i = 0; i < g_count && !carried; ++i) {
            if (g_marks[i].identity == was.identity || mark_is(&g_marks[i], &was)) {
                fl_mark now = mark_of(rec, index);
                carry(&g_marks[i], &now);
                carried = 1;
            }
        }
        if (carried) {
            write_marks();
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        carried = 0;
    }
    return carried;
}

static unsigned char g_call_stock[5];

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site[1];
    unsigned int rel = FL_RULE_CAVE - (FL_RULE_CALL + 5u);
    (void)shipped;
    if (g_installed || game != FL_GAME) {
        return;
    }
    g_call_stock[0] = 0xE8;
    memcpy(g_call_stock + 1, &rel, 4);
    vvfp_site_branch(&site[0], FL_RULE_CALL, 5, g_call_stock, 0xE8, (const void *)rule_call);
    if (vvfp_install_sites(site, 1)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
