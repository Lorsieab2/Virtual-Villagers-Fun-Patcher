/* VVFP Last Names -- babies born in the village and the village's founders
   get a last name (all five games).

   Every Virtual Villagers game, from A New Home on, carries a third list of
   50 names beside its male and female first names -- the list Virtual
   Villagers 6 and 7 later used for villagers' last names.  Each game's
   naming routine copies that list into a buffer and never reads it.  The
   owner: a villager's last name is their family's (the family number 1-50
   the game already keeps on every villager, which a child inherits from its
   mother), given to new villagers only -- and (2026-10-07) "All
   newly-spawned villagers from events will default to no last name
   (because otherwise everyone will have the wrong last name)".  So a baby
   born in the village (a child of one of its mothers' deliveries) and a new
   village's founders get one; a villager an island event brings, a cheat's
   or the Origins page's villager, a Heathen, and every stand-in or ghost the
   game makes and takes away again get none.

   WHERE THE GAMES NAME A VILLAGER, read from the stock executables:

     VV1  0x43B950  thiscall (villager array, index, char *out), ret 8.  The
          record is array + index * 0x3D8, its family at +0x36C (set by both
          callers before the call).  Called by the creator (0x43C68D) and the
          twin path (0x43CA23), each of which then copies `out` (a 28-byte
          local) into the record's 28-byte name at +0x370.
     VV2  0x44B710  the same, stride 0xE48C, family at +0x554; the callers
          (0x44CD36, 0x44D0B5) copy their 28-byte local into the 24-byte
          name at +0x564.
     VV3  0x45C670  thiscall (villager, family or -1), ret 4: the routine
     VV4  0x465DA0  rolls the name (and the family when it is given -1),
     VV5  0x46F680  stores the family at +0xC and writes the name at +0x10:
                    a 25-byte field, of which at most 24 bytes are written
                    here (the count New Believers' own villager copy uses;
                    data/mask_identity_adapters.json).

   The unused list each of those routines copies -- the one read here, from
   the running executable itself -- is pushed by the routine at VV1 0x43B9B1
   (0x481BA0), VV2 0x44B771 (0x48FB98), VV3 0x45C6DA (0x49DFF8), VV4
   0x465E21 (0x4AA930) and VV5 0x46F701 (0x4B8450).

   WHICH NAMING GETS A LAST NAME: the return addresses on the stack, read at
   fixed places, never searched for (the creators' locals are partly
   uninitialised and can hold return addresses left by earlier calls).  Each
   naming routine is called only from the two creators below (every E8 call
   over the whole .text; none through a pointer), and each creator from many
   places -- deliveries, island events, the new-village seeding, cheats --
   classified call by call in
   native/vvfp_cause_of_death/cod_arrival_sites.inc.  A naming gets a last
   name when the routine's own return address `from` is the call in that
   creator AND each listed slot -- a caller's return address at a fixed
   offset from the routine's entry esp, nearest first, each read only once
   the one before it has placed that frame -- holds one of its values.  The
   offsets are each frame's pushes from its entry to the call, by
   control-flow propagation over the stock code; they agree with the
   cause-of-death companion's hook depths plus the pushes from those hooks
   to the naming call.

     VV1  fresh creator 0x43C350 (from 0x43C692; its return at +0x4C):
            births 0x42EF64 the golden-child mother's extra child, 0x42EFD5
            every delivery's first child, 0x4242FD the Golden Child (a
            birth: it spends the mother's pregnancy; family 199, so no last
            name anyway); founders: the seeding in the new-village
            initialiser 0x41C000 (0x41C50E 0x41C54E 0x41C576 0x41C5B6
            0x41C5EB 0x41C613 0x41C648), whose own return at +0x98 is a new
            tribe in an empty slot (0x414020), the first tribe's naming
            (0x415491) or Start Over (0x41C7E5).  None: Barrel of Babies
            (0x427CA0), the crate (0x42B740), the Mysterious Face
            (0x419380), and the seeding the startup scan (0x41D26D) and the
            no-save-yet default (0x41D23A) make for a load to overwrite.
          copy creator 0x43C840 (from 0x43CA28; +0x3C): 0x42F026 twin,
            0x42F072 triplet -- its only callers.
     VV2  fresh creator 0x44C600 (from 0x44CD3B; +0x188): births 0x44F602,
            the birth wrapper 0x44F5C0, whose one caller is the delivery
            (0x43BE8E); founders: the world reset 0x424C80's eight seeding
            calls (0x4252F7 ... 0x42545D), its own return at +0x1D8 a new
            tribe (0x4150B0), the first tribe's naming (0x41AC11) or Start
            Over (0x425605).  None: the event wrapper 0x44F580 (0x44F5B0:
            Barrel of Babies, Old Friends, the Savage Child, the Strange
            Request, the Story upgrades' villagers) and the startup scan's
            and no-save-yet seeding (0x42641D, 0x4263F0).
          copy creator 0x44CEC0 (from 0x44D0BA; +0x3C): 0x43BEE4 twin,
            0x43BF30 triplet.  None: the Silver Mirror (0x4217FE).
     VV3  fresh init 0x456120 (from 0x4565AD): +0x158 0x45F1C9 (0x45F0B0),
            then +0x198 0x45FFD2 (0x45FF90, the delivery's first child; its
            one caller 0x4603B6) -- or the reset 0x427F70's eight seeding
            calls (0x428134 ... 0x4282E6), then +0x1E0 a new tribe
            (0x41B7E4), the first tribe's naming (0x41BA0F) or Start Over
            (0x4283F2): founders.  None: 0x45FF50 (0x45FF80: the canoe, the
            barrels, the Story upgrades' villagers) and the reset's seeding
            before a load (0x428428, 0x4285EA, 0x4285BD).
          copy init 0x4566E0 (from 0x4567D9): +0x18 0x45F2AB (0x45F1D0, the
            delivery's twins and triplets).  None: 0x45F2D0 (0x45F3A8: the
            Crystal of Reflections, the amber vial).
     VV4  fresh init 0x45EF10 (from 0x45F338): +0x15C 0x466302 (0x466270),
            then +0x19C 0x467D92 (0x467D50, the delivery's first child), or
            the founders: 0x43B929 (the adoption scene's founder candidates)
            and 0x420268 (the start-game balancing of the founders).  None:
            0x467D10 (0x467D40: the canoe, Barrel of Babies, the adoption
            scene's stand-in father, the F7 command) and 0x466370 (0x4663E5,
            the ghosts).
          copy init 0x45D9B0 (from 0x45DAA6 or 0x45DAE4): +0x14 0x466361
            (0x466310), then +0x20 0x4688F3 twin or 0x468996 triplet.
     VV5  fresh init 0x4681F0 (from 0x46863D): +0x15C 0x46FB6F (0x46FAD0),
            then +0x1A4 0x471EA2 (0x471E60, the delivery's first child), or
            the founders: 0x43E317 (the choose-your-founders screen) and
            0x425D48 (the village seeding's balancing replacements).  None:
            0x471E20 (0x471E50: Barrel O' Babies, Chutes Without Ladders,
            News From Another Tribe, a founder candidate's stand-in father),
            the Heathens (0x46FB80) and Reanimate's stand-in (0x46FDE0).
          copy init 0x4687F0 (from 0x4688F9 or 0x468937): +0x18 0x46FDCE
            (0x46FD70, the delivery's twins and triplets).
   The Abandoned Infants (VV4, VV5) makes women pregnant; its babies are
   deliveries, so births.  The 256-villager build's delivery guards keep
   every one of these return addresses (they call through to the creators,
   "the creator returning here").

   WHAT THIS COMPANION DOES.  It detours each routine's first instruction
   (`sub esp, imm32`, six bytes) to a wrapper that runs the routine
   unchanged and then, for a birth or a founder only, reads the villager's family and,
   for a family of 1 to 50, appends " " and that family's last name (the
   list's name number family - 1) to the name the routine just wrote --
   only if the whole name fits where it is kept.  Every pairing of the
   games' own lists fits with room to spare (the longest is 17 characters of
   23-27); the bound is kept because the lists are read from the executable
   at run time.  A family outside 1-50 (A New Home's Golden Child is family
   199) gets no last name.  Villagers who already have names keep them;
   nothing in a save changes shape: the last name is part of the name the
   game itself stores.

   INSTALLED by VvfpStartup(game, shipped), which "VVFP Startup.dll" calls as
   the game opens.  The routine's first six bytes, the list push and every
   `from` call (E8 to the routine) are verified first and the list must hold
   exactly 50 names; otherwise nothing is installed and the game names
   villagers as it always has.  Repeated calls do nothing more. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>

#define GAMES 5
#define FAMILIES 50
#define LONGEST_LAST 31

struct game_site {
    unsigned int routine;          /* the naming routine */
    unsigned char prologue[6];     /* its first instruction, sub esp, imm32 */
    unsigned int list_push;        /* the routine's push of the unused list */
    unsigned int list;             /* the list itself */
    unsigned int stride;           /* VV1/VV2: villager record size; else 0 */
    unsigned int family;           /* the family field (record / villager) */
    unsigned int name;             /* VV3-VV5: the name field; else 0 */
    unsigned int room;             /* bytes the finished name may take, with its NUL */
};

static const struct game_site SITES[GAMES + 1] = {
    { 0 },
    { 0x43B950u, { 0x81, 0xEC, 0xC4, 0x06, 0x00, 0x00 }, 0x43B9B1u, 0x481BA0u, 0x3D8u, 0x36Cu, 0, 0x1C },
    { 0x44B710u, { 0x81, 0xEC, 0x24, 0x08, 0x00, 0x00 }, 0x44B771u, 0x48FB98u, 0xE48Cu, 0x554u, 0, 0x18 },
    { 0x45C670u, { 0x81, 0xEC, 0x24, 0x07, 0x00, 0x00 }, 0x45C6DAu, 0x49DFF8u, 0, 0xCu, 0x10u, 0x18 },
    { 0x465DA0u, { 0x81, 0xEC, 0x9C, 0x09, 0x00, 0x00 }, 0x465E21u, 0x4AA930u, 0, 0xCu, 0x10u, 0x18 },
    { 0x46F680u, { 0x81, 0xEC, 0x9C, 0x09, 0x00, 0x00 }, 0x46F701u, 0x4B8450u, 0, 0xCu, 0x10u, 0x18 },
};

/* A naming that gets a last name (see WHICH NAMING GETS A LAST NAME above):
   `from`, then each slot, nearest first, holding one of its values. */
#define PATH_SLOTS 3
#define SLOT_VALUES 9
struct slot_test {
    unsigned int offset;                    /* from the routine's entry esp; 0 ends the path */
    unsigned int values[SLOT_VALUES];       /* a caller's return address; 0 ends the list */
};
struct named_path {
    unsigned int from;                      /* the routine's return address: the creator's call */
    struct slot_test slots[PATH_SLOTS];
};

#define VV1_SEEDING { 0x41C50Eu, 0x41C54Eu, 0x41C576u, 0x41C5B6u, 0x41C5EBu, 0x41C613u, 0x41C648u }
static const struct named_path NAMED_VV1[] = {
    { 0x43C692u, { { 0x4Cu, { 0x42EF64u, 0x42EFD5u, 0x4242FDu } } } },
    { 0x43C692u, { { 0x4Cu, VV1_SEEDING }, { 0x98u, { 0x414020u, 0x415491u, 0x41C7E5u } } } },
    { 0x43CA28u, { { 0x3Cu, { 0x42F026u, 0x42F072u } } } },
    { 0 },
};
#define VV2_SEEDING { 0x4252F7u, 0x42534Cu, 0x425380u, 0x4253B1u, 0x4253E2u, 0x425413u, 0x425439u, 0x42545Du }
static const struct named_path NAMED_VV2[] = {
    { 0x44CD3Bu, { { 0x188u, { 0x44F602u } } } },
    { 0x44CD3Bu, { { 0x188u, VV2_SEEDING }, { 0x1D8u, { 0x4150B0u, 0x41AC11u, 0x425605u } } } },
    { 0x44D0BAu, { { 0x3Cu, { 0x43BEE4u, 0x43BF30u } } } },
    { 0 },
};
#define VV3_SEEDING { 0x428134u, 0x428188u, 0x4281BCu, 0x4281E3u, 0x428215u, 0x428253u, 0x428296u, 0x4282E6u }
static const struct named_path NAMED_VV3[] = {
    { 0x4565ADu, { { 0x158u, { 0x45F1C9u } }, { 0x198u, { 0x45FFD2u } } } },
    { 0x4565ADu, { { 0x158u, { 0x45F1C9u } }, { 0x198u, VV3_SEEDING },
                   { 0x1E0u, { 0x41B7E4u, 0x41BA0Fu, 0x4283F2u } } } },
    { 0x4567D9u, { { 0x18u, { 0x45F2ABu } } } },
    { 0 },
};
static const struct named_path NAMED_VV4[] = {
    { 0x45F338u, { { 0x15Cu, { 0x466302u } }, { 0x19Cu, { 0x467D92u, 0x43B929u, 0x420268u } } } },
    { 0x45DAA6u, { { 0x14u, { 0x466361u } }, { 0x20u, { 0x4688F3u, 0x468996u } } } },
    { 0x45DAE4u, { { 0x14u, { 0x466361u } }, { 0x20u, { 0x4688F3u, 0x468996u } } } },
    { 0 },
};
static const struct named_path NAMED_VV5[] = {
    { 0x46863Du, { { 0x15Cu, { 0x46FB6Fu } }, { 0x1A4u, { 0x471EA2u, 0x43E317u, 0x425D48u } } } },
    { 0x4688F9u, { { 0x18u, { 0x46FDCEu } } } },
    { 0x468937u, { { 0x18u, { 0x46FDCEu } } } },
    { 0 },
};
static const struct named_path *const NAMED[GAMES + 1] = {
    NULL, NAMED_VV1, NAMED_VV2, NAMED_VV3, NAMED_VV4, NAMED_VV5,
};

static int g_game;                                   /* the installed game */
static char g_last[FAMILIES][LONGEST_LAST + 1];      /* the list, by family - 1 */
static unsigned char *g_trampoline;                  /* the routine's own first instruction, then back */
static int install_state;                            /* 0 not tried, 1 installed, -1 refused */

/* Appends " " and family's last name to name (room bytes, NUL included). */
static void give_last_name(char *name, unsigned int room, int family) {
    size_t have, add;
    if (family < 1 || family > FAMILIES) {
        return;
    }
    have = strlen(name);
    add = strlen(g_last[family - 1]);
    if (have + 1 + add + 1 > room) {
        return;
    }
    name[have] = ' ';
    memcpy(name + have + 1, g_last[family - 1], add + 1);
}

/* A New Home's Golden Child is made by its puzzle with family 199, so the
   naming above gives it no last name -- but it is a birth: the owner,
   2026-10-08, "the Golden Child is an exception ... They should take the
   mother or father's last name".  The parentage companion, which knows the
   mother at that birth (the exe's Golden Child splice), asks here for the
   family her children take; nothing is given when the companion is not
   installed (the patch is off) or the family is outside 1-50. */
__declspec(dllexport) int __stdcall VvfpGiveLastName(char *name, unsigned int room, int family) {
    size_t before;
    if (install_state != 1 || name == NULL || family < 1 || family > FAMILIES) {
        return 0;
    }
    before = strlen(name);
    give_last_name(name, room, family);
    return strlen(name) != before;
}

/* THE PLAYER'S RULE AT A BIRTH (the owner, 2026-10-08: babies born after
   "From the father" was chosen were named Tamikai and Wikimak -- their
   mothers' family numbers' names -- not their fathers' last names: "fix
   it").  Repair Saves & Logs keeps the village's rule in
   <save folder>\Virtual Villagers Fun Patcher Data\Last Names\
   Virtual Villagers <game> Last Names - Save <slot>.dat (src/vv_last_names.py
   write_record): a "VVFP LAST NAMES v1 game=<game>" line, then "rule\t<rule>"
   and "whole\t<name>" lines among others.  With "father", "mother" or
   "random" the child takes that parent's last name as the name carries it --
   its last word after the first, a trailing Roman numeral passed over, none
   for a one-word name or one the player said is a single first name -- the
   other parent's when that one has none, and keeps the family's (above) when
   neither has one; exactly as inherited() in src/vv_last_names.py gives it.
   Without the file, or with "list" or "each", nothing changes.

   EACH VILLAGER'S OWN RULE (the owner, 2026-10-09: "so certain villagers can
   pass their last name with different rules from the rest of the village").
   The same file may hold, for a living villager, a line
   "villager\t<name>\t<head>\t<body>\t<M|F>\t<rule>" (rule "father", "mother"
   or "random"; the name in UTF-8): the rule for that villager's children.
   The villager is the parent whose name, head, body and sex at the birth are
   all of those -- as the child's record (or A New Home's parentage entry)
   names the parent, so a father who died before the birth is still found.
   Repair Saves & Logs refuses a line for two living villagers who share all
   four.  At a birth (decide): one parent with a rule of their own -- theirs;
   both with the same -- that one; both, disagreeing -- the village's; neither
   -- the village's.  A parent whose looks are not known has no rule of their
   own.  A reader that does not know these lines (an earlier build) skips
   them. */
#define RULE_FILE_MAX 65536
static char g_rule_file[RULE_FILE_MAX + 1];

static int is_numeral(const char *word, size_t n) {
    size_t i;
    if (n == 0) {
        return 0;
    }
    for (i = 0; i < n; ++i) {
        if (word[i] == '\0' || strchr("IVXLCDM", word[i]) == NULL) {
            return 0;
        }
    }
    return 1;
}

/* "<My Documents>\LDW\<exe name>": the game's save folder, as every companion
   finds it.  0 when it cannot be named. */
static int save_folder(char *out, size_t size) {
    char docs[MAX_PATH], exe[MAX_PATH];
    char *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)
        || GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) {
        return 0;
    }
    exe[MAX_PATH - 1] = '\0';
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';
    }
    if (_snprintf(out, size, "%s\\LDW\\%s", docs, base) <= 0) {
        return 0;
    }
    out[size - 1] = '\0';
    return 1;
}

/* The village's rule ("father", "mother", "random"; "" for none or anything
   else) and the file, kept in g_rule_file for the "whole" and "villager"
   lines.  0 when there is no file of this game to use. */
static DWORD g_rule_size;                /* the bytes read; RULE_FILE_MAX: perhaps not all */

/* The slot's record: "<save folder>\Virtual Villagers Fun Patcher Data\Last
   Names\Virtual Villagers <game> Last Names - Save <slot>.dat". */
static int record_path(int slot, char *path, size_t size) {
    char folder[MAX_PATH];
    if (slot < 1 || slot > 9 || g_game < 1 || !save_folder(folder, sizeof folder)) {
        return 0;
    }
    if (_snprintf(path, size, "%s\\Virtual Villagers Fun Patcher Data\\Last Names\\"
                  "Virtual Villagers %d Last Names - Save %d.dat", folder, g_game, slot) <= 0) {
        return 0;
    }
    path[size - 1] = '\0';
    return 1;
}

static int read_record(int slot, char *rule, size_t rule_size) {
    char path[MAX_PATH * 2];
    char header[48];
    char *line;
    HANDLE h;
    DWORD got = 0;
    rule[0] = '\0';
    g_rule_size = 0;
    g_rule_file[0] = '\0';
    if (!record_path(slot, path, sizeof path)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(h, g_rule_file, RULE_FILE_MAX, &got, NULL)) {
        got = 0;
    }
    CloseHandle(h);
    g_rule_file[got] = '\0';
    g_rule_size = got;
    _snprintf(header, sizeof header, "VVFP LAST NAMES v1 game=%d", g_game);
    header[sizeof header - 1] = '\0';
    if (strncmp(g_rule_file, header, strlen(header)) != 0
        || (g_rule_file[strlen(header)] != '\n' && g_rule_file[strlen(header)] != '\r')) {
        return 0;
    }
    for (line = g_rule_file; line != NULL; line = strchr(line, '\n') ? strchr(line, '\n') + 1 : NULL) {
        if (strncmp(line, "rule\t", 5) == 0) {
            const char *v = line + 5;
            size_t n = strcspn(v, "\r\n");
            if ((n == 6 && strncmp(v, "father", 6) == 0) || (n == 6 && strncmp(v, "mother", 6) == 0)
                || (n == 6 && strncmp(v, "random", 6) == 0)) {
                if (n + 1 > rule_size) {
                    return 0;
                }
                memcpy(rule, v, n);
                rule[n] = '\0';
            }
        }
    }
    return 1;
}

/* The village's rule, as above; 0 when there is none to use. */
static int read_rule(int slot, char *rule, size_t rule_size) {
    return read_record(slot, rule, rule_size) && rule[0] != '\0';
}

/* `n` bytes of UTF-8 (the file's) as the games' Latin-1, into out[size];
   0 for a character Latin-1 has not, or a name too long. */
static int latin1_of(const char *text, size_t n, char *out, size_t size) {
    size_t i, k = 0;
    for (i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)text[i];
        if (k + 1 >= size) {
            return 0;
        }
        if (c < 0x80) {
            out[k++] = (char)c;
        } else if ((c == 0xC2 || c == 0xC3) && i + 1 < n && ((unsigned char)text[i + 1] & 0xC0) == 0x80) {
            out[k++] = (char)(((c & 0x03) << 6) | ((unsigned char)text[i + 1] & 0x3F));
            ++i;
        } else {
            return 0;
        }
    }
    out[k] = '\0';
    return 1;
}

/* A whole decimal number of `n` bytes (a leading '-' allowed) into *value. */
static int number_of(const char *text, size_t n, int *value) {
    size_t i = 0;
    long v = 0;
    int minus = 0;
    if (n > 0 && text[0] == '-') {
        minus = 1;
        i = 1;
    }
    if (i == n || n - i > 9) {
        return 0;
    }
    for (; i < n; ++i) {
        if (text[i] < '0' || text[i] > '9') {
            return 0;
        }
        v = v * 10 + (text[i] - '0');
    }
    *value = minus ? (int)-v : (int)v;
    return 1;
}

/* One "villager" line (from `line` to its end): its name, head, body, sex
   ('M' / 'F') and rule ('f', 'm', 'r'), and where the head and body are, for
   a re-key.  0 for any other line, or a malformed one. */
struct own_line {
    char name[LONGEST_LAST + 1];
    int head, body;
    char sex, rule;
    const char *looks;            /* the head field's first byte */
    const char *looks_end;        /* the tab after the body field */
};

static int own_line_of(const char *line, struct own_line *o) {
    const char *field[5];
    size_t len[5], end = strcspn(line, "\r\n");
    const char *p = line + 9, *stop = line + end;
    int k;
    if (strncmp(line, "villager\t", 9) != 0 || end < 9) {
        return 0;
    }
    for (k = 0; k < 5; ++k) {           /* name, head, body, sex, rule */
        const char *tab = (const char *)memchr(p, '\t', (size_t)(stop - p));
        field[k] = p;
        len[k] = (size_t)((k < 4 ? (tab ? tab : stop) : stop) - p);
        if (k < 4) {
            if (tab == NULL) {
                break;
            }
            p = tab + 1;
        }
    }
    if (k < 5 || memchr(field[4], '\t', len[4]) != NULL
        || !latin1_of(field[0], len[0], o->name, sizeof o->name)
        || !number_of(field[1], len[1], &o->head) || !number_of(field[2], len[2], &o->body)
        || len[3] != 1 || (field[3][0] != 'M' && field[3][0] != 'F') || len[4] != 6) {
        return 0;
    }
    if (strncmp(field[4], "father", 6) == 0) {
        o->rule = 'f';
    } else if (strncmp(field[4], "mother", 6) == 0) {
        o->rule = 'm';
    } else if (strncmp(field[4], "random", 6) == 0) {
        o->rule = 'r';
    } else {
        return 0;
    }
    o->sex = field[3][0];
    o->looks = field[1];
    o->looks_end = field[2] + len[2];
    return 1;
}

/* The rule of the parent `name` with these looks and sex ('M' / 'F') from
   the record's "villager" lines: 'f', 'm' or 'r'; 0 for none -- no line, the
   looks unknown (negative; a head or body 0 is a real look), or two lines for
   the same villager that disagree. */
static char own_rule(const char *name, int head, int body, char sex) {
    const char *line;
    char found = 0;
    if (name == NULL || name[0] == '\0' || head < 0 || body < 0) {
        return 0;
    }
    for (line = g_rule_file; line != NULL; line = strchr(line, '\n') ? strchr(line, '\n') + 1 : NULL) {
        struct own_line o;
        if (!own_line_of(line, &o) || strcmp(o.name, name) != 0 || o.head != head || o.body != body
            || o.sex != sex) {
            continue;
        }
        if (found != 0 && found != o.rule) {
            return 0;
        }
        found = o.rule;
    }
    return found;
}
/* The rule a birth uses (the owner, 2026-10-09): one parent's own; both
   parents' when they agree; else the village's (0: none). */
static char decide(char father_rule, char mother_rule, char village) {
    if (father_rule != 0 && mother_rule != 0) {
        return father_rule == mother_rule ? father_rule : village;
    }
    return father_rule != 0 ? father_rule : mother_rule != 0 ? mother_rule : village;
}

/* Each game's slot saves: "<stem><slot>.ldw" in the save folder (the checker's
   SAVE_STEMS). */
static const char *const SAVE_STEMS[GAMES + 1] = {
    NULL, "Virtual Villagers", "Virtual Villagers - The Lost Children",
    "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
    "Virtual Villagers - New Believers",
};
#define SAVE_MAX (16u * 1024u * 1024u)

/* Whether `data` holds `name` as a whole name field: the bytes, then a NUL,
   after a NUL or at the start. */
static int holds_name(const unsigned char *data, DWORD size, const char *name) {
    size_t n = strlen(name);
    DWORD i;
    if (n == 0 || n + 1 > size) {
        return 0;
    }
    for (i = 0; i + n < size; ++i) {
        if (data[i + n] == 0 && memcmp(data + i, name, n) == 0 && (i == 0 || data[i - 1] == 0)) {
            return 1;
        }
    }
    return 0;
}

/* The village's slot when the caller cannot know it -- a birth in the catch-up
   as a village loads, before its first save names it (the live test,
   2026-10-08): the one slot save holding both parents' names, else, when
   several do, the first of them when they all keep the same rule.  0 when no
   slot can be told. */
static int slot_of_parents(const char *father, const char *mother) {
    char folder[MAX_PATH], path[MAX_PATH * 2], rule[8], first_rule[8];
    unsigned char *data;
    int slot, found = 0;
    if (g_game < 1 || g_game > GAMES || !save_folder(folder, sizeof folder)
        || ((father == NULL || father[0] == '\0') && (mother == NULL || mother[0] == '\0'))) {
        return 0;
    }
    data = (unsigned char *)VirtualAlloc(NULL, SAVE_MAX, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (data == NULL) {
        return 0;
    }
    first_rule[0] = '\0';
    for (slot = 1; slot <= 5; ++slot) {
        HANDLE h;
        DWORD got = 0;
        if (_snprintf(path, sizeof path, "%s\\%s%d.ldw", folder, SAVE_STEMS[g_game], slot) <= 0) {
            continue;
        }
        path[sizeof path - 1] = '\0';
        h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h == INVALID_HANDLE_VALUE) {
            continue;
        }
        if (!ReadFile(h, data, SAVE_MAX, &got, NULL)) {
            got = 0;
        }
        CloseHandle(h);
        if ((father != NULL && father[0] != '\0' && !holds_name(data, got, father))
            || (mother != NULL && mother[0] != '\0' && !holds_name(data, got, mother))) {
            continue;
        }
        if (!read_rule(slot, rule, sizeof rule)) {
            rule[0] = '\0';
        }
        if (found == 0) {
            found = slot;
            memcpy(first_rule, rule, sizeof rule);
        } else if (strcmp(rule, first_rule) != 0) {
            found = -1;                     /* two villages, two rules: no telling */
        }
    }
    VirtualFree(data, 0, MEM_RELEASE);
    return found > 0 ? found : 0;
}

/* Whether the record file says `base` (n bytes) is one first name. */
static int is_whole(const char *base, size_t n) {
    const char *line;
    for (line = g_rule_file; line != NULL; line = strchr(line, '\n') ? strchr(line, '\n') + 1 : NULL) {
        if (strncmp(line, "whole\t", 6) == 0 && strcspn(line + 6, "\r\n") == n
            && strncmp(line + 6, base, n) == 0) {
            return 1;
        }
    }
    return 0;
}

/* The last name `name` carries (split_name's own fallback): its last word that
   is not a numeral, never its first; "" for none.  `out` holds LONGEST_LAST. */
static void carried_last(const char *name, char *out) {
    char words[8][LONGEST_LAST + 1];
    int count = 0, k;
    const char *p = name;
    size_t base_len;
    out[0] = '\0';
    if (name == NULL) {
        return;
    }
    while (*p != '\0' && count < 8) {
        size_t n = strcspn(p, " ");
        if (n == 0 || n > LONGEST_LAST) {
            return;                         /* two spaces, or a word no name has */
        }
        memcpy(words[count], p, n);
        words[count][n] = '\0';
        ++count;
        p += n;
        if (*p == ' ') {
            ++p;
        }
    }
    if (*p != '\0') {
        return;
    }
    k = count - 1;
    while (k > 0 && is_numeral(words[k], strlen(words[k]))) {
        --k;
    }
    if (k < 1) {
        return;
    }
    base_len = 0;
    {
        int i;
        for (i = 0; i <= k; ++i) {
            base_len += strlen(words[i]) + (i ? 1 : 0);
        }
    }
    if (is_whole(name, base_len)) {
        return;
    }
    memcpy(out, words[k], strlen(words[k]) + 1);
}

/* From the parentage companions at a birth, before its Birth record is
   written: the child's name (its first name, and the family's last name this
   DLL gave it) made its first name and the last name the player's rule gives
   (above).  `father` / `mother`: the parents' names as the game holds them
   (NULL or "" unknown), with each one's head and body as the child's record
   (A New Home: the parentage entry) keeps them (negative: unknown) -- what
   tells which villager's own rule is theirs.  `slot`: the village's save
   slot, or 0 when the caller cannot know it yet (slot_of_parents).  Returns 1
   when the name changed. */
__declspec(dllexport) int __stdcall VvfpRuleLastName2(char *name, unsigned int room,
                                                      const char *father, int father_head, int father_body,
                                                      const char *mother, int mother_head, int mother_body,
                                                      int slot) {
    char rule[8], dad[LONGEST_LAST + 1], mum[LONGEST_LAST + 1], first[LONGEST_LAST + 1];
    const char *last;
    char use;
    size_t n;
    if (install_state != 1 || name == NULL || room < 2 || memchr(name, '\0', room) == NULL) {
        return 0;
    }
    if (slot <= 0) {
        slot = slot_of_parents(father, mother);
    }
    if (!read_record(slot, rule, sizeof rule)) {
        return 0;
    }
    use = decide(own_rule(father, father_head, father_body, 'M'),
                 own_rule(mother, mother_head, mother_body, 'F'), rule[0]);
    if (use == 0) {
        return 0;                           /* no rule decides: the family's stays */
    }
    n = strcspn(name, " ");
    if (n == 0 || n > LONGEST_LAST) {
        return 0;
    }
    memcpy(first, name, n);
    first[n] = '\0';
    carried_last(father, dad);
    carried_last(mother, mum);
    if (use == 'f') {
        last = dad[0] ? dad : mum;
    } else if (use == 'm') {
        last = mum[0] ? mum : dad;
    } else {                                /* "random": 50:50 for each child (the owner) */
        last = dad[0] && mum[0] ? ((GetTickCount() ^ (DWORD)(uintptr_t)name) & 1 ? dad : mum)
                                : (dad[0] ? dad : mum);
    }
    if (last[0] == '\0' || n + 1 + strlen(last) + 1 > room) {
        return 0;                           /* none to give, or too long: the family's stays */
    }
    if (strncmp(name + n, " ", 1) == 0 && strcmp(name + n + 1, last) == 0) {
        return 0;                           /* already so */
    }
    name[n] = ' ';
    memcpy(name + n + 1, last, strlen(last) + 1);
    return 1;
}

/* A villager's looks changed (the coordinator, 2026-10-09: the rule must
   follow the villager at the moment the look changes -- an island event
   changed Papu's head in the owner's A New Home).  From the Parentage Export
   DLL, as it is handed each "Appearance changed" record (Change Appearance,
   the Island Events log, a Custom Island Event the Island Events log sees):
   each "villager" line for `name` and this sex with the old looks gets a
   copy with the new looks right after it.  The old line stays: a child
   already conceived keeps the father's looks of its conception on its record
   (Repair drops it once no pregnancy names him).  Nothing else in the record
   changes; a line the new looks already have is not doubled.  `slot` 0: the slot save
   holding the name (slot_of_parents).  Written through a temporary file
   swapped in whole.  Returns the lines re-keyed. */
__declspec(dllexport) int __stdcall VvfpRelookLastName(const char *name, int male, int old_head, int old_body,
                                                       int new_head, int new_body, int slot) {
    static char out[RULE_FILE_MAX + 64 * 64];
    char rule[8], path[MAX_PATH * 2], temporary[MAX_PATH * 2 + 16];
    const char *line;
    size_t used = 0;
    int moved = 0, has_new;
    HANDLE h;
    DWORD wrote = 0;
    if (install_state != 1 || name == NULL || name[0] == '\0' || old_head < 0 || old_body < 0 || new_head < 0
        || new_body < 0 || (old_head == new_head && old_body == new_body)) {
        return 0;
    }
    if (slot <= 0) {
        slot = male ? slot_of_parents(name, NULL) : slot_of_parents(NULL, name);
    }
    if (!read_record(slot, rule, sizeof rule) || g_rule_size >= RULE_FILE_MAX || !record_path(slot, path, sizeof path)) {
        return 0;
    }
    has_new = own_rule(name, new_head, new_body, male ? 'M' : 'F') != 0;
    for (line = g_rule_file; line != NULL && *line != '\0';
         line = strchr(line, '\n') ? strchr(line, '\n') + 1 : NULL) {
        size_t n = strchr(line, '\n') ? (size_t)(strchr(line, '\n') + 1 - line) : strlen(line);
        struct own_line o;
        if (n >= sizeof out - used) {
            return 0;
        }
        memcpy(out + used, line, n);
        used += n;
        if (own_line_of(line, &o) && strcmp(o.name, name) == 0 && o.sex == (male ? 'M' : 'F')
            && o.head == old_head && o.body == old_body && !has_new) {
            int k;
            if (line[n - 1] != '\n') {          /* a last line without its newline */
                if (used + 1 >= sizeof out) {
                    return 0;
                }
                out[used++] = '\n';
            }
            k = _snprintf(out + used, sizeof out - used, "%.*s%d\t%d%.*s", (int)(o.looks - line), line,
                          new_head, new_body, (int)(line + strcspn(line, "\r\n") - o.looks_end), o.looks_end);
            if (k <= 0 || (size_t)k + 1 >= sizeof out - used) {
                return 0;
            }
            used += (size_t)k;
            out[used++] = '\n';
            ++moved;
        }
    }
    if (moved == 0 || _snprintf(temporary, sizeof temporary, "%s.relook-tmp", path) <= 0) {
        return 0;
    }
    temporary[sizeof temporary - 1] = '\0';
    h = CreateFileA(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!WriteFile(h, out, (DWORD)used, &wrote, NULL) || wrote != used || !FlushFileBuffers(h)) {
        CloseHandle(h);
        DeleteFileA(temporary);
        return 0;
    }
    CloseHandle(h);
    if (!MoveFileExA(temporary, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(temporary);
        return 0;
    }
    return moved;
}

static int one_of(unsigned int value, const unsigned int *values) {
    int i;
    for (i = 0; i < SLOT_VALUES && values[i] != 0; ++i) {
        if (values[i] == value) {
            return 1;
        }
    }
    return 0;
}

/* entry: the stack as the routine was entered, entry[0] its return
   address.  A slot is read only once the nearer ones have placed its frame. */
static int gets_a_last_name(const unsigned int *entry) {
    const struct named_path *p;
    int k;
    for (p = NAMED[g_game]; p->from != 0; ++p) {
        if (entry[0] != p->from) {
            continue;
        }
        for (k = 0; k < PATH_SLOTS && p->slots[k].offset != 0; ++k) {
            if (!one_of(entry[p->slots[k].offset / 4], p->slots[k].values)) {
                break;
            }
        }
        if (k == PATH_SLOTS || p->slots[k].offset == 0) {
            return 1;
        }
    }
    return 0;
}

/* VV1/VV2: after the routine, `out` holds the first name; the record is
   array + index * stride. */
static void __cdecl after_out(const unsigned int *entry, unsigned char *array, unsigned int index, char *out) {
    const struct game_site *s = &SITES[g_game];
    if (gets_a_last_name(entry)) {
        give_last_name(out, s->room, *(int *)(array + index * s->stride + s->family));
    }
}

/* VV3-VV5: the routine wrote the name and the family into the villager. */
static void __cdecl after_villager(const unsigned int *entry, unsigned char *villager) {
    const struct game_site *s = &SITES[g_game];
    if (gets_a_last_name(entry)) {
        give_last_name((char *)(villager + s->name), s->room, *(int *)(villager + s->family));
    }
}

/* thiscall (array, index, out), ret 8: the routine, then the last name.
   Every register but eax is the routine's own on return; eax is too. */
static __declspec(naked) void wrap_out(void) {
    __asm {
        push ebp
        mov ebp, esp
        push ecx
        push dword ptr [ebp + 12]
        push dword ptr [ebp + 8]
        call dword ptr [g_trampoline]       /* ecx is still the array */
        pop ecx
        pushad
        push dword ptr [ebp + 12]
        push dword ptr [ebp + 8]
        push ecx
        lea eax, [ebp + 4]                  /* the routine's entry esp */
        push eax
        call after_out
        add esp, 16
        popad
        pop ebp
        ret 8
    }
}

/* thiscall (villager, family), ret 4. */
static __declspec(naked) void wrap_villager(void) {
    __asm {
        push ebp
        mov ebp, esp
        push ecx
        push dword ptr [ebp + 8]
        call dword ptr [g_trampoline]
        pop ecx
        pushad
        push ecx
        lea eax, [ebp + 4]                  /* the routine's entry esp */
        push eax
        call after_villager
        add esp, 8
        popad
        pop ebp
        ret 4
    }
}

static int readable(const void *at, size_t size) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return 0;
    }
    return (const unsigned char *)at + size <= (const unsigned char *)info.BaseAddress + info.RegionSize;
}

/* The list as the game writes it: names separated (and ended) by commas.
   Exactly 50 names, none empty or longer than LONGEST_LAST. */
static int read_list(const char *list) {
    int count = 0;
    size_t length = 0;
    const char *p;
    if (!readable(list, 1)) {
        return 0;
    }
    for (p = list; ; ++p) {
        if (!readable(p, 1)) {
            return 0;
        }
        if (*p == ',' || *p == '\0') {
            if (length == 0) {
                if (*p == '\0') {
                    break;
                }
                return 0;
            }
            if (count == FAMILIES) {
                return 0;
            }
            memcpy(g_last[count], p - length, length);
            g_last[count][length] = '\0';
            ++count;
            length = 0;
            if (*p == '\0') {
                break;
            }
        } else if (++length > LONGEST_LAST) {
            return 0;
        }
    }
    return count == FAMILIES;
}

static int site_is_the_routine(const struct game_site *s) {
    const unsigned char *at = (const unsigned char *)(uintptr_t)s->routine;
    const unsigned char *push = (const unsigned char *)(uintptr_t)s->list_push;
    unsigned int pushed;
    if (!readable(at, sizeof s->prologue) || !readable(push, 5)) {
        return 0;
    }
    if (memcmp(at, s->prologue, sizeof s->prologue) != 0 || push[0] != 0x68) {
        return 0;
    }
    memcpy(&pushed, push + 1, 4);
    return pushed == s->list;
}

/* Every path's `from` follows an E8 call to the routine: the frames the
   offsets were worked out on. */
static int calls_are_the_creators(int game) {
    const struct named_path *p;
    for (p = NAMED[game]; p->from != 0; ++p) {
        const unsigned char *call = (const unsigned char *)(uintptr_t)(p->from - 5);
        unsigned int rel;
        if (!readable(call, 5) || call[0] != 0xE8) {
            return 0;
        }
        memcpy(&rel, call + 1, 4);
        if (p->from + rel != SITES[game].routine) {
            return 0;
        }
    }
    return 1;
}

static void site_bytes(const struct game_site *s, void (*wrapper)(void), unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)wrapper
                                      - ((const unsigned char *)(uintptr_t)s->routine + 5));
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    out[5] = 0x90;
}

static int install(int game) {
    const struct game_site *s;
    unsigned char bytes[6];
    unsigned char *at;
    unsigned int back;
    DWORD old;
    if (game < 1 || game > GAMES) {
        return 0;
    }
    if (install_state != 0) {
        return install_state == 1;
    }
    install_state = -1;
    s = &SITES[game];
    if (!site_is_the_routine(s) || !calls_are_the_creators(game)
        || !read_list((const char *)(uintptr_t)s->list)) {
        return 0;
    }
    /* The trampoline: the routine's own `sub esp, imm32`, then jmp back. */
    g_trampoline = (unsigned char *)VirtualAlloc(NULL, 16, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (g_trampoline == NULL) {
        return 0;
    }
    memcpy(g_trampoline, s->prologue, sizeof s->prologue);
    g_trampoline[6] = 0xE9;
    back = (unsigned int)((s->routine + 6) - ((unsigned int)(uintptr_t)g_trampoline + 11));
    memcpy(g_trampoline + 7, &back, 4);
    FlushInstructionCache(GetCurrentProcess(), g_trampoline, 16);

    g_game = game;
    site_bytes(s, s->stride != 0 ? wrap_out : wrap_villager, bytes);
    at = (unsigned char *)(uintptr_t)s->routine;
    if (!VirtualProtect(at, sizeof bytes, PAGE_EXECUTE_READWRITE, &old)) {
        VirtualFree(g_trampoline, 0, MEM_RELEASE);
        g_trampoline = NULL;
        return 0;
    }
    memcpy(at, bytes, sizeof bytes);
    VirtualProtect(at, sizeof bytes, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, sizeof bytes);
    install_state = 1;
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    (void)install(game);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
