/* VVFP Last Names -- new villagers get a last name (all five games).

   Every Virtual Villagers game, from A New Home on, carries a third list of
   50 names beside its male and female first names -- the list Virtual
   Villagers 6 and 7 later used for villagers' last names.  Each game's
   naming routine copies that list into a buffer and never reads it.  The
   owner: a villager's last name is their family's (the family number 1-50
   the game already keeps on every villager, which a child inherits from its
   mother), given to new villagers only.

   WHERE THE GAMES NAME A VILLAGER, read from the stock executables (every
   caller is a new villager or a twin):

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

   WHAT THIS COMPANION DOES.  It detours each routine's first instruction
   (`sub esp, imm32`, six bytes) to a wrapper that runs the routine
   unchanged, then reads the villager's family and, for a family of 1 to 50,
   appends " " and that family's last name (the list's name number
   family - 1) to the name the routine just wrote -- only if the whole name
   fits where it is kept.  Every pairing of the games' own lists fits with
   room to spare (the longest is 17 characters of 23-27); the bound is kept
   because the lists are read from the executable at run time.  A family
   outside 1-50 (A New Home's Golden Child is family 199) gets no last name.
   Villagers who already have names keep them; nothing in a save changes
   shape: the last name is part of the name the game itself stores.

   INSTALLED by VvfpStartup(game, shipped), which "VVFP Startup.dll" calls as
   the game opens.  The routine's first six bytes and the list push are
   verified first and the list must hold exactly 50 names; otherwise nothing
   is installed and the game names villagers as it always has.  Repeated
   calls do nothing more. */
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

/* VV1/VV2: after the routine, `out` holds the first name; the record is
   array + index * stride. */
static void __cdecl after_out(unsigned char *array, unsigned int index, char *out) {
    const struct game_site *s = &SITES[g_game];
    int family = *(int *)(array + index * s->stride + s->family);
    give_last_name(out, s->room, family);
}

/* VV3-VV5: the routine wrote the name and the family into the villager. */
static void __cdecl after_villager(unsigned char *villager) {
    const struct game_site *s = &SITES[g_game];
    give_last_name((char *)(villager + s->name), s->room, *(int *)(villager + s->family));
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
        call after_out
        add esp, 12
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
        call after_villager
        add esp, 4
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
    if (!site_is_the_routine(s) || !read_list((const char *)(uintptr_t)s->list)) {
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
