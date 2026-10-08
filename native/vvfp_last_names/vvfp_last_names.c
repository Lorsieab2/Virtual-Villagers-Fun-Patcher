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
#include <windows.h>
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
