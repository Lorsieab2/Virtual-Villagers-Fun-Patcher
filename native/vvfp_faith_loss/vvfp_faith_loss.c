/* VVFP Faith Loss -- the per-villager rule of "Faith Loss is Doubled/Gains Halved", New Believers.

   WHAT.  The owner (2026-11-08): "villagers should preferentially die if their faith decrease-turn heathen is due
   to starvation or disease ... so most starving villagers die / most sick people die instead of them all turning
   heathen" -- decided once per villager per crisis, not on every roll (a roll each age unit would still convert
   nearly everyone over a long famine), and 1 in 10.  A Heathen is skipped by the life tick (0x472CB7): it never
   eats, starves, falls ill or loses health, so a believer the drift turns Heathen escapes hunger and sickness.

   THE RULE.  The row's exe bytes count the drift 0x468040's food and sickness losses in ebp and send its final
   FAITH_ADD through a cave that first calls a rule (scripts/build_apprentice_faith_puddles_features.py: the call
   at 0x494F14, whose own target 0x494F28 is the rule without this companion).  This companion takes that call:
     * a marked believer whose crisis is over -- food above 250 ([0x51D34C], so no food roll can apply) and not
       sick (+0x1C48) -- is unmarked first;
     * a fall (the sum esi < 0) with food or sickness losses in it (ebp > 0) that takes Faith to 0 or less, where
       the drift's other changes alone (esi + ebp) would leave Faith above 0, is the low food or sickness taking the
       last Faith: a marked believer stays at Faith 1 (the sum becomes 1 - Faith); an unmarked one is decided now,
       once -- rand(10) < 1 (the game's own rand, 0x403660) the fall is made and the believer becomes a Heathen
       as before; otherwise the believer is marked and stays at Faith 1;
     * anything else is the drift's own sum: rises, falls that leave Faith above 0, and falls the other changes
       ("too few believers") make on their own.
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
   (sidecar_io.h: atomic writes, an unreadable file never replaced, an invalid one set aside).  It is read when the
   game's save slot (the save manager's own field, set before the slot's village is created or loaded:
   native/shared/game_save_slot.h) is first seen, so the load-time catch-up already has them; it is written each
   time a mark is made or cleared, with only the marks of villagers who are living believers then (matched as
   above, so a renamed villager's mark is carried, never pruned).  Start Over deletes
   the save's folder, and the file with it (native/shared/save_reset.c).  The save itself is never written.

   FORMAT (little-endian): u32 magic 'VFK1', u32 version 1, u32 game 5, u32 slot, u32 count (0..FL_MARKS_MAX),
   then `count` entries of 5 u32: identity, record (0..255), keep, stable, age.  Exactly 20 + 20 * count bytes.

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
#define FL_DECIDE 10                    /* rand(10) < 1: the believer becomes a Heathen */
#define FL_CONVERTS 1

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
#define FL_VERSION 1u
#define FL_HEADER 20u
#define FL_RESERVE ((int)sizeof(".unreadable-4294967295-999"))   /* sidecar_io.h's set-aside name */

typedef int (__cdecl *rand_fn)(int);

typedef struct {
    unsigned int identity;
    unsigned int record;                /* the record the villager was last seen in */
    unsigned int keep;                  /* the name and sex (what a likes / dislikes change leaves) */
    unsigned int stable;                /* the likes, dislikes and sex (what a rename leaves) */
    int age;                            /* the age last seen */
} fl_mark;

static int g_installed;
static fl_mark g_marks[FL_MARKS_MAX];
static int g_count;
static int g_slot;                      /* the slot whose file the marks are (0: none read yet) */
static vv_sidecar_gate g_gate;
static unsigned char g_buffer[FL_HEADER + sizeof(fl_mark) * FL_MARKS_MAX];

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
    return m;
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
            g_marks[i] = now;
            return i;
        }
    }
    for (i = 0; i < g_count; ++i) {
        if (mark_is(&g_marks[i], &now)) {
            g_marks[i] = now;              /* renamed or re-liked: the mark follows them */
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
    char docs[MAX_PATH], exe[MAX_PATH], part[64];
    char *base = exe, *p, *dot = NULL;
    DWORD n;
    int i;
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
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH - FL_RESERVE) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; i < 4; ++i) {
        wsprintfA(part, LEVELS[i], slot);
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    wsprintfA(part, "\\Believers Kept - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    if (len < FL_HEADER || u[0] != FL_MAGIC || u[1] != FL_VERSION || u[2] != FL_GAME
        || u[3] != (unsigned int)*(const int *)ctx || u[4] > FL_MARKS_MAX) {
        return 0;
    }
    return len == FL_HEADER + sizeof(fl_mark) * u[4];
}

/* The marks of `slot`'s file (none when it is missing, set aside or blocked). */
static void read_marks(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    g_count = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!marks_path(slot, path, 0)) {
        return;
    }
    if (vv_sidecar_load(&g_gate, path, g_buffer, sizeof g_buffer, &got, valid_file, &slot) == VV_SIDECAR_LOAD_VALID) {
        g_count = (int)((const unsigned int *)g_buffer)[4];
        memcpy(g_marks, g_buffer + FL_HEADER, sizeof(fl_mark) * (unsigned int)g_count);
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
        if (found >= 0) {
            g_marks[kept++] = now[found];
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
    (void)vv_sidecar_publish(&g_gate, path, parts, sizes, g_count > 0 ? 2 : 1);
}

/* The marks are the slot's: read when the game's slot is first seen (it is set before the slot's village is
   made or loaded, so before the load-time catch-up). */
static void bind_slot(void) {
    int slot = vv_game_save_slot(FL_GAME);
    if (slot != 0 && slot != g_slot) {
        read_marks(slot);
        g_slot = slot;
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

static int __cdecl faith_rule(unsigned char *rec, int sum, int losses) {
    int result = sum;
    __try {
        int at, faith, index;
        bind_slot();
        index = record_index(rec);
        at = marked_at(rec, index);
        if (at >= 0 && *(const volatile int *)(UINT_PTR)FL_FOOD > FL_CRISIS_FOOD && rec[REC_SICK] == 0) {
            g_marks[at] = g_marks[--g_count];      /* the crisis is over: the next one is decided afresh */
            at = -1;
            write_marks();
        }
        faith = *(const int *)(rec + REC_FAITH);
        if (sum >= 0 || losses <= 0 || faith + sum > 0 || faith + sum + losses <= 0) {
            return sum;                            /* not the low food or sickness taking the last Faith */
        }
        if (at < 0) {
            if (((rand_fn)(UINT_PTR)FL_RAND)(FL_DECIDE) < FL_CONVERTS) {
                return sum;                        /* 1 in 10: a Heathen, as before */
            }
            if (g_count < FL_MARKS_MAX) {
                g_marks[g_count++] = mark_of(rec, index);
                write_marks();
            }
        }
        result = 1 - faith;                        /* stays a believer, at Faith 1 */
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

/* How many believers are marked to stay, for the save slot now. */
int __stdcall VvfpFaithLossMarked(void) {
    return g_count;
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
