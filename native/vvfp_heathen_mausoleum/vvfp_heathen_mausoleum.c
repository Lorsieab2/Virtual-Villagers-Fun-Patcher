/* VVFP Heathen Mausoleum -- New Believers: the Heathens' own graves at the mud hut (workstream W-C of
   docs/heathen-tribe-expansion-design.md, section 6, and the owner's decisions 11-14 in
   docs/heathen-tribe-expansion-decisions.md, which override the design).

   Shipped with "Heathen Tribe Expansion and Evolution" (flag "VVFP Heathen Tribe Evolution.txt") and with "Former
   Villagers Among the Heathens Leave Skeletons" on its own (flag "VVFP Heathen Skeletons Former.txt"; decision 14:
   "the mud-hut memorial also works when only ... is on"), and, until W-D migrates old patch sets, with the old "All
   Heathens Leave Skeletons" (flag "VVFP Heathen Skeletons All.txt").  With none of the three it installs nothing.
   Which Heathens leave a body at all stays with those rows ("VVFP Heathen Aging.dll").

   THE STOCK GAME (every address read from the stock executable; docs/heathen-tribe-expansion-design.md section 6).
   A body is buried by the believers' "Burying the dead" (chooser 0x46F130, only once the Buried Mausoleum, project 6,
   is restored; its body finder 0x470940 has no faction test), behaviour 0x30 (script 0x45B5D0): walk to the body,
   pick it up, op 0x1D (0x473F50) writes the grave into the Roster of the Dead 0x5481A8 at the pick-up (the writer
   0x464C70 at 0x473FA9, the dead one's faction byte still intact), then the carry walk to the mausoleum door
   (0x7D + rand(20), 0x6BD), the drop.  The Mausoleum screen (scene 0x14, opened by 0x43CC00 from the mausoleum's
   area handler 0x43CDE0) reads the roster at four `mov ecx, 0x5481A8`.  The mud hut has no area handler: hotspot id
   0x0B has no handler and no lcmap.dat cells.

   WHAT THIS DOES (run-time sites, all or none, stock bytes checked first: native/shared/install_sites.h):

     0x473FA9  the burial's roster write: a Heathen's body (faction byte +0x1CEC set at death -- a camp Heathen, an
               arrival, a puzzle Heathen or a former villager who died a Heathen) is written by the game's own writer
               into the Heathens' table here (an object laid out as the stock roster) instead; a believer's,
               a converted former villager's included, into the Roster of the Dead as before (decision 14).  A full
               Heathen table: the stock rule (no grave, the body gone; Cause of Death says "the mud hut memorial was
               full").
     0x45B650  the burial script's carry walk: a Heathen's body is carried to the mud hut (2176 + 5 x rand(20),
               1588: the hovel memorial's walk points), whoever carries it; a believer's to the mausoleum door as
               before.  The game's rand(20) is drawn as in the stock script either way.
     0x46E9E0  the Heathen AI's entry (decision 11, "heathens should bury heathens (believers can be a fallback)"):
               an adult Heathen who is able (living, 14 or older, not sick, not expecting, no puzzle role 12-17)
               and finds a Heathen's body nobody is burying starts the game's own "Burying the dead" on it, half the
               times it is asked, as the believers' chooser starts it (0x473440, then 0x465580(0x30) with the body
               in 0x547D54).  No project 6 is needed: the Heathens bury at their own hut.
     0x46F146  the believers' chooser's body finder: a believer's body as before; a Heathen's body only when no
               Heathen is able to bury it (no able Heathen lives) or it has lain unburied HM_FALLBACK_UNITS (120 of
               the game's 240) -- the believers' fallback, still into the mud hut -- and nobody is burying it.
     0x43F4F1, 0x43F735, 0x43FDC0, 0x43FED6   the Mausoleum screen's four roster reads: `call view` (`mov ecx,
               [g_view]; ret`), the believers' roster unless the mud hut opened the screen (decision 13: the game's
               own screen and art, unchanged).  The table contents are never swapped.
     0x43F1DF  the screen's title widget, made once in the scene's constructor from string 0x4D: kept, and its
               text is "Shrine to the Ancestors" (the owner, 2026-11-26) while the Heathens' graves are shown and
               the game's own title otherwise.  The background art is the game's own, unchanged.
     0x46B116  the everyday "Honoring the dead" chooser's grave count: the believers' graves and the Heathens'
               (the owner, 2026-11-26: the same grave behaviour), so the honoring -- at the graves, or at the hovel
               with Memorial Actions Can Also Occur at the Heathen Hovel -- still happens in a village whose only
               graves are Heathens'.  (The Day of Honor, the Remembrance Ceremony and the Story graph's grave
               condition still count the Roster of the Dead: their ceremonies are at the Buried Mausoleum.)
     0x43CE24  the mausoleum's own opener: the believers' roster again, then 0x43CC00.  (The area-0x0C handler
               0x47A3F0 also switches to scene 0x14, but no lcmap.dat cell carries id 0x0C: dead code.)
     0x423E2B, 0x4246E1   after each lcmap load (0x4775B0): hotspot 0x0B registered in the area-handler table
               0x77DC80 ({handler, highlight 6, permission 1}: a child or an expecting villager may be dropped) and
               stamped into the hotspot field (bits 15..24) of the mud hut's cells, x 2152..2287 and y 1464..1599
               (the hovel hover line's own rectangle), only where no other hotspot is.  The handler: a click (2) or
               a drop (0) opens the Heathen Mausoleum Screen when the Heathens' table holds a grave; a held villager
               over the hut (1) returns 0, so the point-hover routine 0x444310 still shows Fix Vanilla Bugs' hovel
               hover lines (hook 0x444568) as before.
     0x424569  the save's roster copy, in 0x4244F0 (slot in edi): for a slot save (1..5; never the meta, slot 0, or
               the backup generation, slot + 20) the save's own return is followed, and once it reports the save
               written (al = 1) the Heathens' table is published to the slot's file.  A quit without saving never
               writes it, so the file always matches the save.
     0x424733  the new village's roster clear (0x4246A0): the Heathens' table is cleared too.
     0x425849  the load's roster read (0x425640): once the game has loaded the slot's roster, the slot's file is read
               into the Heathens' table (a Change Tribe switches files).

   EXISTING HEATHEN GRAVES in the believers' Roster of the Dead stay where they are (decision 12); "VVFP Heathen
   Aging.dll"'s VvfpHeathenAgingGrave keeps them out of the statistics.

   THE FILE AND THE EXPORTS: native/shared/heathen_mausoleum.h.

   SAFETY.  Our steps run under structured exception handling; a fault leaves the stock behaviour.  No debug output;
   no text is shown. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/heathen_evo.h"
#include "../shared/heathen_mausoleum.h"
#include "../shared/vvfp_translate.h"   /* the screen's title in the player's language */

#define HM_GAME 5
#define HM_FLAG_FORMER "VVFP Heathen Skeletons Former.txt"
#define HM_FLAG_ALL "VVFP Heathen Skeletons All.txt"

/* The villager record (vv5). */
#define R_STRIDE 0x2F44u
#define R_AGE 0x1B8Cu
#define R_SELF 0x1B88u               /* the AI object's record */
#define R_STAMP 0x1C38u              /* a body's time of death (the game clock) */
#define R_HEALTH 0x1C40u
#define R_SICK 0x1C48u
#define R_PREGNANT 0x1C4Cu
#define R_PRESENT 0x1CD4u
#define R_LOOKALIKE 0x1CE1u
#define R_FACTION 0x1CECu
#define R_BEHAVIOUR 0x1D10u          /* the action 0x465580 started */
#define R_ROLE 0x1CFCu
#define ADULT 280                    /* 14 years: the believers' chooser runs only past 0x118 */
#define BURY 0x30                    /* "Burying the dead" */

/* The game. */
#define G_RAND 0x403660u             /* cdecl rand(n) */
#define G_WRITER 0x464C70u           /* the roster writer, thiscall (record, burier id); ret 8 */
#define G_COPY 0x464BA0u             /* the roster's save copy, thiscall (buffer); ret 4 */
#define G_CLEAR 0x464BD0u            /* the roster clear, ecx = the roster */
#define G_LOAD 0x464EF0u             /* the roster's load, thiscall (buffer); ret 4 */
#define G_WALK 0x4745A0u             /* a walk step to a point, thiscall on the record (x, y, 100, 0) */
#define G_STOP 0x473440u             /* the activity stop, thiscall on the AI object */
#define G_START 0x465580u            /* start an action, thiscall on the record (id, &byte) */
#define G_OPEN 0x43CC00u             /* the Mausoleum screen */
#define G_LCMAP 0x4775B0u            /* the lcmap load, ecx = the grid */
#define G_GAME_OBJECT 0x425950u      /* the game object (cdecl, no arguments) */
#define G_CLOCK 0x4036E0u            /* its clock, thiscall */
#define G_SPEED 0x17D7Cu             /* the game object's minutes per unit */
#define G_ROSTER 0x5481A8u
#define G_BODY 0x547D54u             /* the body the burier carries */
#define G_GRID 0x718EE8u             /* 320 x 320 cells of 8 pixels, cell (y / 8) * 320 + x / 8 */
#define G_AREAS 0x77DC80u            /* 12-byte entries {handler, highlight, permission} by hotspot id */
#define GRID_SIDE 320
#define HOTSPOT_SHIFT 15
#define HOTSPOT_MASK (0x3FFu << HOTSPOT_SHIFT)

#define HUT_HOTSPOT 0x0Bu
#define HUT_X0 2152
#define HUT_X1 2287
#define HUT_Y0 1464
#define HUT_Y1 1599
#define HUT_WALK_X 2176              /* + 5 x rand(20): 2176..2271 */
#define HUT_WALK_Y 1588
#define DOOR_X 0x7D
#define DOOR_Y 0x6BD
#define HM_FALLBACK_UNITS 120        /* believers may bury a Heathen's body that has lain this long */
#define HM_BURY_PERCENT 50           /* how often an able Heathen asked takes the burial */

typedef int (__fastcall *tc0_fn)(void *self, void *unused_edx);
typedef int (__fastcall *tc2_fn)(void *self, void *unused_edx, int a, int b);
typedef int (__cdecl *rand_fn)(int n);
typedef void *(__cdecl *object_fn)(void);
typedef void (__cdecl *open_fn)(void);

static int g_installed;
static unsigned char *g_records;
static unsigned int g_slots;

/* The Heathens' table: the stock roster's layout (heathen_mausoleum.h). */
static __declspec(align(16)) unsigned char g_heathen[HM_TABLE_BYTES];
static unsigned int g_view = G_ROSTER;

/* ---- the table ------------------------------------------------------------------------------------------- */

static unsigned char *entry_at(int place) {
    return g_heathen + (size_t)place * HE_ROSTER_ENTRY;
}

static int entry_age(int place) {
    return *(const int *)(entry_at(place) + 0x1C);
}

static int table_count(void) {
    int n = 0;
    while (n < HE_ROSTER_MAX && entry_age(n) != 0) {
        ++n;
    }
    return n;
}

static void table_clear(void) {
    memset(g_heathen, 0, sizeof g_heathen);
}

/* The game's own load rules for one entry (0x464EF0): the name printable (0x464B70: no byte 0x01..0x1F before its
   NUL) and ended within 0x19 bytes, age above 0 (an age of 0 ends the roster), profession -1..5, cause -1..4. */
static int entry_valid(const unsigned char *e) {
    int i, job = *(const int *)(e + 0x28), cause = *(const int *)(e + 0x34), age = *(const int *)(e + 0x1C);
    for (i = 0; i < 0x19; ++i) {
        if (e[i] == 0) {
            break;
        }
        if (e[i] < 0x20) {
            return 0;
        }
    }
    return i < 0x19 && age > 0 && job >= -1 && job <= 5 && cause >= -1 && cause <= 4;
}

/* ---- the file -------------------------------------------------------------------------------------------- */

#define HM_RESERVE ((int)sizeof(".unreadable-4294967295-999"))
static vv_sidecar_gate g_gate;
static int g_table_slot;          /* the village whose graves are in the table (0: none known) */
static int g_table_partial;       /* its file could not be read at the load: merge it before the next write */
static unsigned int g_buffer[(HE_MAUSOLEUM_HEADER + HE_ROSTER_MAX * HE_ROSTER_ENTRY) / 4u + 1u];

static int file_path(int slot, char *out, int make) {
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\" HE_MAUSOLEUM_FOLDER
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
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH - HM_RESERVE) {
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
    wsprintfA(part, "\\" HE_MAUSOLEUM_FILE, slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    unsigned int count, i;
    if (len < HE_MAUSOLEUM_HEADER || u[0] != HE_MAUSOLEUM_MAGIC || u[1] != HE_MAUSOLEUM_VERSION || u[2] != HM_GAME
        || u[4] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    count = u[3];
    if (count > (unsigned int)HE_ROSTER_MAX || len != HE_MAUSOLEUM_HEADER + count * HE_ROSTER_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (!entry_valid(data + HE_MAUSOLEUM_HEADER + i * HE_ROSTER_ENTRY)) {
            return 0;
        }
    }
    return 1;
}

/* Read `slot`'s file into g_buffer: the load's status (sidecar_io.h). */
static int read_file(int slot, DWORD *got) {
    char path[MAX_PATH];
    vv_sidecar_gate_bind(&g_gate, slot);
    *got = 0;
    if (!file_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_gate);
        return VV_SIDECAR_LOAD_BLOCKED;
    }
    return vv_sidecar_load(&g_gate, path, (unsigned char *)g_buffer, sizeof g_buffer, got, valid_file, &slot);
}

/* The game has loaded `slot`: its Heathen graves, from its file. */
static void load_slot(int slot) {
    DWORD got;
    int status;
    table_clear();
    g_table_slot = slot;
    g_table_partial = 0;
    if (slot == 0) {
        return;
    }
    status = read_file(slot, &got);
    if (status == VV_SIDECAR_LOAD_VALID) {
        memcpy(g_heathen, (const unsigned char *)g_buffer + HE_MAUSOLEUM_HEADER, (size_t)g_buffer[3] * HE_ROSTER_ENTRY);
    } else if (status == VV_SIDECAR_LOAD_BLOCKED) {
        g_table_partial = 1;      /* the file is there but locked: never replaced; merged once it can be read */
    }
}

/* The game has just saved `slot`: the table to its file.  The file is read first when this gate has not settled for
   it (a new village in the slot, or a load whose file was locked): a locked file is never written; a file of a load
   that was locked is merged (its graves first, then the ones buried since), so nothing it held is lost. */
static void publish(int slot) {
    char path[MAX_PATH];
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2], got;
    int count;
    if (slot < 1 || slot > 5 || !file_path(slot, path, 1)) {
        return;
    }
    if (!vv_sidecar_gate_ready(&g_gate, slot) || lstrcmpiA(g_gate.path, path) != 0) {
        int status = read_file(slot, &got);
        if (status == VV_SIDECAR_LOAD_BLOCKED) {
            return;
        }
        if (status == VV_SIDECAR_LOAD_VALID && g_table_partial && g_table_slot == slot) {
            int have = (int)g_buffer[3], mine = table_count(), keep = mine;
            if (have + keep > HE_ROSTER_MAX) {
                keep = HE_ROSTER_MAX - have;
            }
            memmove(g_heathen + (size_t)have * HE_ROSTER_ENTRY, g_heathen, (size_t)keep * HE_ROSTER_ENTRY);
            memcpy(g_heathen, (const unsigned char *)g_buffer + HE_MAUSOLEUM_HEADER, (size_t)have * HE_ROSTER_ENTRY);
            if (have + keep < HE_ROSTER_MAX) {
                memset(g_heathen + (size_t)(have + keep) * HE_ROSTER_ENTRY, 0,
                       (size_t)(HE_ROSTER_MAX - have - keep) * HE_ROSTER_ENTRY);
            }
        }
    }
    count = table_count();
    header[0] = HE_MAUSOLEUM_MAGIC;
    header[1] = HE_MAUSOLEUM_VERSION;
    header[2] = HM_GAME;
    header[3] = (unsigned int)count;
    header[4] = (unsigned int)slot;
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_heathen;
    sizes[1] = (DWORD)count * HE_ROSTER_ENTRY;
    if (vv_sidecar_publish(&g_gate, path, parts, sizes, count > 0 ? 2 : 1)) {
        g_table_slot = slot;
        g_table_partial = 0;
    }
}

/* ---- the villagers --------------------------------------------------------------------------------------- */

static unsigned char *rec_at(int index) {
    return g_records + (size_t)index * R_STRIDE;
}

static int rec_index(const unsigned char *record) {
    UINT_PTR at = (UINT_PTR)record, base = (UINT_PTR)g_records;
    if (at < base || (at - base) % R_STRIDE != 0 || (at - base) / R_STRIDE >= g_slots) {
        return -1;
    }
    return (int)((at - base) / R_STRIDE);
}

static int i32(const unsigned char *record, unsigned int at) {
    return *(const int *)(record + at);
}

static int living(const unsigned char *r) {
    return r[R_PRESENT] != 0 && r[R_LOOKALIKE] == 0 && i32(r, R_HEALTH) > 0;
}

/* A body lying unburied (what the stock finder 0x470940 takes: present, no look-alike, health 0 or less). */
static int body(const unsigned char *r) {
    return r[R_PRESENT] != 0 && r[R_LOOKALIKE] == 0 && i32(r, R_HEALTH) <= 0;
}

/* An able Heathen burier (decision 11): living, 14 or older, not sick, not expecting, no puzzle role. */
static int able_heathen(const unsigned char *r) {
    int role = i32(r, R_ROLE);
    return r[R_FACTION] != 0 && living(r) && i32(r, R_AGE) >= ADULT && r[R_SICK] == 0 && i32(r, R_PREGNANT) == 0
        && (role < 12 || role > 17);
}

static int any_able_heathen(void) {
    unsigned int i;
    for (i = 0; i < g_slots; ++i) {
        if (able_heathen(rec_at((int)i))) {
            return 1;
        }
    }
    return 0;
}

/* Who carries which body: written when a burier's carry walk is queued (any burier, any body), good while the
   burier lives and is still "Burying the dead" and the body still lies there. */
static struct { int burier, body; } g_claims[256];

static int claimed(int index) {
    unsigned int i;
    for (i = 0; i < 256u && i < g_slots; ++i) {
        if (g_claims[i].body == index + 1) {
            const unsigned char *burier = rec_at((int)i);
            if (living(burier) && i32(burier, R_BEHAVIOUR) == BURY && body(rec_at(index))) {
                return 1;
            }
            g_claims[i].body = 0;
        }
    }
    return 0;
}

static void claim(int burier, int index) {
    if (burier >= 0 && burier < 256) {
        g_claims[burier].body = index + 1;
    }
}

/* How long a body has lain, in age units, as the game's removal reckons it (0x46FEB6..0x46FEE9). */
static unsigned int lain_units(const unsigned char *r) {
    void *game = ((object_fn)(UINT_PTR)G_GAME_OBJECT)();
    unsigned int now, speed;
    if (game == NULL) {
        return 0;
    }
    now = (unsigned int)((tc0_fn)(UINT_PTR)G_CLOCK)(game, NULL);
    speed = *(const unsigned int *)((const unsigned char *)game + G_SPEED);
    return (now - (unsigned int)i32(r, R_STAMP)) / 60u / (speed != 0 ? speed : 1u);
}

/* The companion's own draws (never the game's rand: slider_scale.h's rule). */
static unsigned int g_xs;
static unsigned int xs_rand(unsigned int n) {
    if (g_xs == 0) {
        g_xs = GetTickCount() | 1u;
    }
    g_xs ^= g_xs << 13;
    g_xs ^= g_xs >> 17;
    g_xs ^= g_xs << 5;
    return n != 0 ? g_xs % n : 0;
}

/* ---- the hooks' work ------------------------------------------------------------------------------------- */

/* The believers' finder (0x470940's place): the first body as before, a Heathen's only for the fallback. */
static int __cdecl believer_finder(void) {
    int answer = -1;
    __try {
        unsigned int i;
        int able = -1;
        for (i = 0; i < g_slots; ++i) {
            const unsigned char *r = rec_at((int)i);
            if (!body(r)) {
                continue;
            }
            if (r[R_FACTION] == 0) {
                answer = (int)i;
                break;
            }
            if (claimed((int)i)) {
                continue;
            }
            if (able < 0) {
                able = any_able_heathen();
            }
            if (!able || lain_units(r) >= HM_FALLBACK_UNITS) {
                answer = (int)i;
                break;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = -1;
    }
    return answer;
}

/* The Heathen AI (0x46E9E0, ecx = the AI object): 1 when this Heathen went to bury a Heathen's body. */
static int __cdecl heathen_ai(unsigned char *self) {
    int answer = 0;
    __try {
        unsigned char *record = *(unsigned char **)(self + R_SELF);
        unsigned int i;
        int found = -1;
        if (rec_index(record) < 0 || !able_heathen(record)) {
            return 0;
        }
        claim(rec_index(record), -1);      /* asked anew: whatever it carried before is over */
        for (i = 0; i < g_slots; ++i) {
            const unsigned char *r = rec_at((int)i);
            if (body(r) && r[R_FACTION] != 0 && !claimed((int)i)) {
                found = (int)i;
                break;
            }
        }
        if (found < 0 || xs_rand(100) >= HM_BURY_PERCENT) {
            return 0;
        }
        {
            unsigned char started = 0;
            ((tc0_fn)(UINT_PTR)G_STOP)(self, NULL);
            *(volatile int *)(UINT_PTR)G_BODY = found;
            claim(rec_index(record), found);
            ((tc2_fn)(UINT_PTR)G_START)(record, NULL, BURY, (int)(UINT_PTR)&started);
        }
        answer = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = 0;
    }
    return answer;
}

/* The carry walk (0x45B650, esi = the burier): where to; the game's rand(20) drawn as in the stock script. */
static int g_walk_x, g_walk_y;
static void __cdecl carry_point(unsigned char *burier) {
    int r = ((rand_fn)(UINT_PTR)G_RAND)(20);
    g_walk_x = DOOR_X + r;
    g_walk_y = DOOR_Y;
    __try {
        int index = *(volatile int *)(UINT_PTR)G_BODY;
        if (index >= 0 && (unsigned int)index < g_slots) {
            claim(rec_index(burier), index);
            if (rec_at(index)[R_FACTION] != 0) {
                g_walk_x = HUT_WALK_X + 5 * r;
                g_walk_y = HUT_WALK_Y;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The screen's title (the owner, 2026-11-26: "in-game it should be called shrine to the ancestors").  The
   Mausoleum scene (a singleton made at its first opening, 0x43F130) draws its title as a text widget made at
   0x43F1DF from string 0x4D eString_Mausoleum; the widget is kept when it is made, and its text set (the widget's
   own setter 0x40D8D0, thiscall (text), ret 4) to "Shrine to the Ancestors" while the screen shows the Heathens'
   graves and back to the game's own string when it shows the believers'.  Only the text: the art is unchanged. */
#define G_SET_TEXT 0x40D8D0u
#define HM_TITLE "Shrine to the Ancestors"
typedef void (__fastcall *set_text_fn)(void *widget, void *unused_edx, const char *text);
static void *g_title;
static const char *g_stock_title;

static void __cdecl apply_title(void) {
    __try {
        const char *text = g_view == G_ROSTER ? g_stock_title
            : vvfp_tr("vvfp.heathen_mausoleum/vvfp_heathen_mausoleum.HM_TITLE.s0", HM_TITLE, 0);
        if (g_title != NULL && text != NULL) {
            ((set_text_fn)(UINT_PTR)G_SET_TEXT)(g_title, NULL, text);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

static void __cdecl stock_opening(void) {
    g_view = G_ROSTER;
    apply_title();
}

/* The mud hut's area handler: event 0 a drop, 1 a held villager over it, 2 a click. */
static unsigned char __cdecl hut_handler(int event, void *villager) {
    (void)villager;
    if (event == 1 || !g_installed) {
        return 0;                 /* the point-hover routine keeps the hovel hover lines */
    }
    __try {
        if (table_count() == 0) {
            return 0;
        }
        g_view = (unsigned int)(UINT_PTR)g_heathen;
        apply_title();
        ((open_fn)(UINT_PTR)G_OPEN)();
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
    return 1;
}

/* After each lcmap load: the hotspot registered and stamped. */
static void __cdecl after_lcmap(void) {
    __try {
        unsigned int *area = (unsigned int *)(UINT_PTR)(G_AREAS + HUT_HOTSPOT * 12u);
        unsigned int *grid = (unsigned int *)(UINT_PTR)G_GRID;
        int x, y;
        area[0] = (unsigned int)(UINT_PTR)hut_handler;
        area[1] = 6;
        area[2] = 1;
        for (y = HUT_Y0 / 8; y <= HUT_Y1 / 8; ++y) {
            for (x = HUT_X0 / 8; x <= HUT_X1 / 8; ++x) {
                unsigned int *cell = grid + y * GRID_SIDE + x;
                if ((*cell & HOTSPOT_MASK) == 0) {
                    *cell |= HUT_HOTSPOT << HOTSPOT_SHIFT;
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The save (0x424569 in 0x4244F0): a slot save's own return is followed to its answer. */
static void *g_save_return;
static int g_save_slot;
static void save_return_stub(void);

static void __cdecl save_seen(void **return_slot, int slot) {
    if (!g_installed || slot < 1 || slot > 5 || g_save_return != NULL) {
        return;
    }
    g_save_slot = slot;
    g_save_return = *return_slot;
    *return_slot = (void *)save_return_stub;
}

static void __cdecl save_done(int result) {
    int slot = g_save_slot;
    g_save_slot = 0;
    if ((result & 0xFF) == 0) {
        return;
    }
    __try {
        publish(slot);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

static void __cdecl new_village(void) {
    table_clear();
    g_table_slot = vv_game_save_slot(HM_GAME);
    g_table_partial = 0;
    memset(g_claims, 0, sizeof g_claims);
    g_view = G_ROSTER;
}

static void __cdecl village_loaded(int result) {
    memset(g_claims, 0, sizeof g_claims);
    g_view = G_ROSTER;
    __try {
        load_slot((result & 0xFF) != 0 ? vv_game_save_slot(HM_GAME) : 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        table_clear();
    }
}

/* ---- the stubs ------------------------------------------------------------------------------------------- */

static const unsigned int g_writer = G_WRITER;
static const unsigned int g_walk = G_WALK;
static const unsigned int g_open = G_OPEN;
static const unsigned int g_lcmap = G_LCMAP;
static const unsigned int g_copy = G_COPY;
static const unsigned int g_clear = G_CLEAR;
static const unsigned int g_load = G_LOAD;
static const unsigned int g_carry_resume = 0x45B66Fu;
static const unsigned int g_ai_resume = 0x46E9E7u;
static unsigned int g_heathen_base;
static int g_ai_result;

/* 0x473FA9 `call 0x464C70` (ecx = the Roster of the Dead; [esp+4] the body, [esp+8] the burier's id). */
__declspec(naked) static void bury_stub(void) {
    __asm {
        mov eax, dword ptr [esp + 4]
        cmp byte ptr [eax + 0x1CEC], 0
        je believer
        mov ecx, dword ptr [g_heathen_base]
    believer:
        jmp dword ptr [g_writer]
    }
}

/* 0x45B650..0x45B66F: the carry walk's rand(20) and point, then the walk step. */
__declspec(naked) static void carry_stub(void) {
    __asm {
        pushad
        push esi
        call carry_point
        add esp, 4
        popad
        push 0
        push 0x64
        push dword ptr [g_walk_y]
        push dword ptr [g_walk_x]
        mov ecx, esi
        call dword ptr [g_walk]
        jmp dword ptr [g_carry_resume]
    }
}

/* 0x46E9E0 `sub esp, 0x20; push ebx; push esi; mov esi, ecx`. */
__declspec(naked) static void ai_stub(void) {
    __asm {
        pushad
        push ecx
        call heathen_ai
        add esp, 4
        mov dword ptr [g_ai_result], eax
        popad
        cmp dword ptr [g_ai_result], 0
        jne buried
        sub esp, 0x20
        push ebx
        push esi
        mov esi, ecx
        jmp dword ptr [g_ai_resume]
    buried:
        ret
    }
}

/* 0x46F146 `call 0x470940`. */
__declspec(naked) static void finder_stub(void) {
    __asm {
        pushad
        call believer_finder
        mov dword ptr [esp + 0x1C], eax
        popad
        ret
    }
}

/* The four screen reads `mov ecx, 0x5481A8`. */
__declspec(naked) static void view_stub(void) {
    __asm {
        mov ecx, dword ptr [g_view]
        ret
    }
}

/* 0x43F1DF `call 0x40DD90` in the Mausoleum scene's constructor: the title widget made (ecx = the widget, its
   text the 4th stack argument), kept, and titled for the roster on show. */
static void *g_title_return;
static const unsigned int g_widget_ctor = 0x40DD90u;
__declspec(naked) static void title_stub(void) {
    __asm {
        pop dword ptr [g_title_return]
        mov eax, dword ptr [esp + 0xC]
        mov dword ptr [g_stock_title], eax
        call dword ptr [g_widget_ctor]
        mov dword ptr [g_title], eax
        pushad
        call apply_title
        popad
        jmp dword ptr [g_title_return]
    }
}

/* 0x46B116 `mov ecx, 0x5481A8; call 0x464E90` in the everyday "Honoring the dead" chooser 0x46B0F0: the graves it
   asks for are the believers' and the Heathens' at the Shrine to the Ancestors (the owner, 2026-11-26: Heathen graves
   get the same grave behaviour), so a village whose only graves are Heathens' still honors its dead -- as it did when
   their graves were in the Roster of the Dead.  The chooser only tests the number (> 0). */
static const unsigned int g_roster_count = 0x464E90u;
static int g_shrine_count;
__declspec(naked) static void honor_count_stub(void) {
    __asm {
        mov ecx, 0x5481A8
        call dword ptr [g_roster_count]
        push eax
        pushad
        call table_count
        mov dword ptr [g_shrine_count], eax
        popad
        pop eax
        add eax, dword ptr [g_shrine_count]
        ret
    }
}

/* 0x43CE24 `call 0x43CC00`: the mausoleum's own opener shows the believers, under the game's own title. */
__declspec(naked) static void stock_open_stub(void) {
    __asm {
        pushad
        call stock_opening
        popad
        jmp dword ptr [g_open]
    }
}

/* 0x423E2B / 0x4246E1 `call 0x4775B0` (ecx = the grid). */
__declspec(naked) static void lcmap_stub(void) {
    __asm {
        call dword ptr [g_lcmap]
        pushad
        call after_lcmap
        popad
        ret
    }
}

/* 0x424569 `call 0x464BA0` in the save 0x4244F0 (edi = the slot; 0x4244F0's return 0x10 above this call's). */
__declspec(naked) static void save_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 0x30]
        push edi
        push eax
        call save_seen
        add esp, 8
        popad
        jmp dword ptr [g_copy]
    }
}

/* Where 0x4244F0 returns for a slot save (al = saved), then on to its caller. */
__declspec(naked) static void save_return_stub(void) {
    __asm {
        push dword ptr [g_save_return]
        pushad
        mov dword ptr [g_save_return], 0
        push eax
        call save_done
        add esp, 4
        popad
        ret
    }
}

/* 0x424733 `call 0x464BD0` (ecx = the roster): a new village. */
__declspec(naked) static void clear_stub(void) {
    __asm {
        call dword ptr [g_clear]
        pushad
        call new_village
        popad
        ret
    }
}

/* 0x425849 `call 0x464EF0` (ecx = the roster, [esp+4] the save buffer; ret 4). */
__declspec(naked) static void load_stub(void) {
    __asm {
        push dword ptr [esp + 4]
        call dword ptr [g_load]
        pushad
        push eax
        call village_loaded
        add esp, 4
        popad
        ret 4
    }
}

/* ---- the exports ----------------------------------------------------------------------------------------- */

int __stdcall VvfpHeathenMausoleumInstalled(void) {
    return g_installed;
}

int __stdcall VvfpHeathenMausoleumCount(void) {
    return g_installed ? table_count() : 0;
}

const unsigned char *__stdcall VvfpHeathenMausoleumEntry(int place) {
    if (!g_installed || place < 0 || place >= table_count()) {
        return NULL;
    }
    return entry_at(place);
}

const unsigned char *__stdcall VvfpHeathenMausoleumTable(void) {
    return g_installed ? g_heathen : NULL;
}

int __stdcall VvfpHeathenMausoleumRemove(int place) {
    int n;
    unsigned int *buriers = (unsigned int *)(g_heathen + HM_BURIERS);
    if (!g_installed || place < 0) {
        return 0;
    }
    n = table_count();
    if (place >= n) {
        return 0;
    }
    memmove(entry_at(place), entry_at(place + 1), (size_t)(n - 1 - place) * HE_ROSTER_ENTRY);
    memset(entry_at(n - 1), 0, HE_ROSTER_ENTRY);
    memmove(buriers + place, buriers + place + 1, sizeof(unsigned int) * (size_t)(n - 1 - place));
    buriers[n - 1] = 0;
    if (*(int *)(g_heathen + HM_COUNT) > 0) {
        --*(int *)(g_heathen + HM_COUNT);
    }
    return 1;
}

int __stdcall VvfpHeathenMausoleumIsHeathenGrave(int entry) {
    UINT_PTR at = (UINT_PTR)(unsigned int)entry, base = (UINT_PTR)g_heathen;
    return g_installed && at >= base && at < base + (UINT_PTR)HE_ROSTER_MAX * HE_ROSTER_ENTRY
        && (at - base) % HE_ROSTER_ENTRY == 0;
}

void __stdcall VvfpHeathenMausoleumVillageReset(int game, int slot) {
    if (game != HM_GAME || slot < 1 || slot > 5) {
        return;
    }
    if (g_table_slot != 0 && slot != g_table_slot) {
        return;
    }
    table_clear();
    g_table_slot = 0;
    g_table_partial = 0;
    vv_sidecar_gate_bind(&g_gate, 0);      /* the slot's file is read afresh before it is ever written again */
    memset(g_claims, 0, sizeof g_claims);
    g_view = G_ROSTER;
}

/* ---- the install ----------------------------------------------------------------------------------------- */

static const unsigned char BURY_STOCK[5] = { 0xE8, 0xC2, 0x0C, 0xFF, 0xFF };
static const unsigned char CARRY_STOCK[31] = {
    0x6A, 0x14, 0xE8, 0x09, 0x80, 0xFA, 0xFF, 0x83, 0xC4, 0x04, 0x6A, 0x00, 0x6A, 0x64, 0xB9, 0xBD,
    0x06, 0x00, 0x00, 0x51, 0x83, 0xC0, 0x7D, 0x50, 0x8B, 0xCE, 0xE8, 0x31, 0x8F, 0x01, 0x00
};
static const unsigned char AI_STOCK[7] = { 0x83, 0xEC, 0x20, 0x53, 0x56, 0x8B, 0xF1 };
static const unsigned char FINDER_STOCK[5] = { 0xE8, 0xF5, 0x17, 0x00, 0x00 };
static const unsigned char VIEW_STOCK[5] = { 0xB9, 0xA8, 0x81, 0x54, 0x00 };
static const unsigned char OPEN_STOCK[5] = { 0xE8, 0xD7, 0xFD, 0xFF, 0xFF };
static const unsigned char LCMAP_A_STOCK[5] = { 0xE8, 0x80, 0x37, 0x05, 0x00 };
static const unsigned char LCMAP_B_STOCK[5] = { 0xE8, 0xCA, 0x2E, 0x05, 0x00 };
static const unsigned char SAVE_STOCK[5] = { 0xE8, 0x32, 0x06, 0x04, 0x00 };
static const unsigned char CLEAR_STOCK[5] = { 0xE8, 0x98, 0x04, 0x04, 0x00 };
static const unsigned char LOAD_STOCK[5] = { 0xE8, 0xA2, 0xF6, 0x03, 0x00 };
static const unsigned char TITLE_STOCK[5] = { 0xE8, 0xAC, 0xEB, 0xFC, 0xFF };
static const unsigned char HONOR_STOCK[10] = { 0xB9, 0xA8, 0x81, 0x54, 0x00, 0xE8, 0x70, 0x9D, 0xFF, 0xFF };
static const unsigned int VIEW_SITES[4] = { 0x43F4F1u, 0x43F735u, 0x43FDC0u, 0x43FED6u };
#define HM_SITES 16

void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[HM_SITES];
    unsigned int manager_rva;
    int i;
    (void)shipped;
    if (g_installed || game != HM_GAME) {
        return;
    }
    if (!vvfp_patcher_file_exists(HE_FLAG_ROW) && !vvfp_patcher_file_exists(HM_FLAG_FORMER)
        && !vvfp_patcher_file_exists(HM_FLAG_ALL)) {
        return;
    }
    vv5_villager_table((const unsigned char *)GetModuleHandleA(NULL), &manager_rva, &g_slots);
    g_records = (unsigned char *)GetModuleHandleA(NULL) + manager_rva + 0x48;
    if (g_slots > 256u) {
        return;
    }
    g_heathen_base = (unsigned int)(UINT_PTR)g_heathen;
    vvfp_site_branch(&sites[0], 0x473FA9u, 5, BURY_STOCK, 0xE8, (const void *)bury_stub);
    vvfp_site_branch(&sites[1], 0x45B650u, 31, CARRY_STOCK, 0xE9, (const void *)carry_stub);
    vvfp_site_branch(&sites[2], 0x46E9E0u, 7, AI_STOCK, 0xE9, (const void *)ai_stub);
    vvfp_site_branch(&sites[3], 0x46F146u, 5, FINDER_STOCK, 0xE8, (const void *)finder_stub);
    for (i = 0; i < 4; ++i) {
        vvfp_site_branch(&sites[4 + i], VIEW_SITES[i], 5, VIEW_STOCK, 0xE8, (const void *)view_stub);
    }
    vvfp_site_branch(&sites[8], 0x43CE24u, 5, OPEN_STOCK, 0xE8, (const void *)stock_open_stub);
    vvfp_site_branch(&sites[9], 0x423E2Bu, 5, LCMAP_A_STOCK, 0xE8, (const void *)lcmap_stub);
    vvfp_site_branch(&sites[10], 0x4246E1u, 5, LCMAP_B_STOCK, 0xE8, (const void *)lcmap_stub);
    vvfp_site_branch(&sites[11], 0x424569u, 5, SAVE_STOCK, 0xE8, (const void *)save_stub);
    vvfp_site_branch(&sites[12], 0x424733u, 5, CLEAR_STOCK, 0xE8, (const void *)clear_stub);
    vvfp_site_branch(&sites[14], 0x43F1DFu, 5, TITLE_STOCK, 0xE8, (const void *)title_stub);
    vvfp_site_branch(&sites[15], 0x46B116u, 10, HONOR_STOCK, 0xE8, (const void *)honor_count_stub);
    vvfp_site_branch(&sites[13], 0x425849u, 5, LOAD_STOCK, 0xE8, (const void *)load_stub);
    if (vvfp_install_sites(sites, HM_SITES)) {
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
