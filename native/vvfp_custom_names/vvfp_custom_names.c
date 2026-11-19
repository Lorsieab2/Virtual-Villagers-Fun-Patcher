/* VVFP Custom Names -- the player's own first names and last names, added to
   each game's own (Custom Stuff, all five games; the owner, 2026-11-19).

   THE OWNER'S RULE.  "normal vanilla stuff = fallback. custom stuff = additions
   that should be treated like normal game additions, no special treatment."
   So a custom first name is one more name in the game's pool for its sex, and
   every name -- the game's and the player's -- is equally likely (Q1); a custom
   last name is one more name wherever "VVFP Last Names.dll" draws from its list
   of 50, founders included (Q2).  Nothing is replaced: the game's own names
   stay, and without this companion (or with empty lists) the game names
   villagers exactly as it always has.

   THE LISTS are the patcher's files in the game folder, written by the
   patcher's Custom Stuff window (src/vv_custom_stuff.py):
       Virtual Villagers Fun Patcher Files\Custom Stuff\First Names - Male.txt
       Virtual Villagers Fun Patcher Files\Custom Stuff\First Names - Female.txt
       Virtual Villagers Fun Patcher Files\Custom Stuff\Last Names.txt
   UTF-8, one name per line; a line starting with '#' and an empty line are
   skipped.  Read once, as the game opens.  A name is kept only when it is one
   word (no space, tab or comma), holds no '%' (an unpatched game reads it as a
   formatting instruction) and no control byte, is not all Roman-numeral letters
   (Number Duplicate Names' numerals), and is at most FIRST_MAX / LAST_MAX bytes
   as the game keeps it.  It is written as Windows-1252 (Latin-1) when every
   letter fits; a name with any other letter is kept as UTF-8 only when the
   game draws UTF-8 (the Unicode text or Unicode font companion is loaded),
   and skipped otherwise.  A name already in the list is not added twice.

   FIRST NAMES.  Each game's naming routine (VV1 0x43B950, VV2 0x44B710, VV3
   0x45C670, VV4 0x465DA0, VV5 0x46F680) writes a first name it drew from S of
   its own names for the villager's sex, each 1 in S: S is the rand bound the
   game pushes (VV1 0x43C645 push imm8, VV2 0x44CCF1, VV3 0x45C677 push imm8,
   VV4 0x465DB5, VV5 0x46F695 push imm32), read from the running executable so
   Fix Vanilla Bugs' whole-list bound counts (A New Home 100 -> 101, The Lost
   Children and The Secret City 123 -> 125, The Tree of Life and New Believers
   183 -> 185).  After the routine, with C custom names for that sex, the name
   becomes a custom one with chance C / (S + C), each custom name equally
   likely: every one of the S + C names then comes up 1 in (S + C).  The sex is
   the one the routine read: VV1 the record's +0x350 (2 female), VV2 +0x538
   (2 female), VV3-VV5 the villager's +4 (1 female).  A custom name that would
   not fit the routine's name room is never given.

   WHO CALLS IT.  "VVFP Last Names.dll" already detours each naming routine's
   first instruction; two detours cannot share it.  So when Last Names is in
   the game (started first, from the loader's first word), its wrapper calls
   VvfpCustomFirstName right after the routine, before it adds a last name.
   When the routine still holds its stock first instruction as this companion
   starts (Last Names not shipped, or it refused to install), this companion
   detours it itself, the same way: the routine runs unchanged, then the name
   is drawn as above.  The routine's first six bytes and the rand bound's push
   are verified first; any difference and nothing is installed.

   LAST NAMES.  VvfpCustomLastNameCount / VvfpCustomLastName hand Last Names
   the player's last names, which it adds to its own list of 50 wherever it
   draws (vvfp_last_names.c).  This companion never gives a last name itself.

   Nothing in a save changes shape: a name is the text the game stores anyway. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include "../shared/install_sites.h"     /* every site written, or none */
#include "../shared/patcher_files.h"     /* the patcher's own folder */

#define GAMES 5
#define LIST_MAX 1000                    /* names kept per list */
#define FIRST_MAX 10                     /* bytes of a custom first name, as kept */
#define LAST_MAX 12                      /* bytes of a custom last name, as kept */
#define FILE_MAX 65536

struct naming_site {
    unsigned int routine;                /* the naming routine */
    unsigned char prologue[6];           /* its first instruction, sub esp, imm32 */
    unsigned int bound;                  /* the push of the first-name roll's bound */
    int bound_wide;                      /* 1: push imm32 (68), 0: push imm8 (6A) */
    unsigned int stride;                 /* VV1/VV2: the record size (thiscall array, index, out) */
    unsigned int sex;                    /* the sex field: record (VV1/VV2) or villager (VV3-VV5) */
    int female;                          /* its value for a woman */
    unsigned int name;                   /* VV3-VV5: the name in the villager; 0: `out` */
    unsigned int room;                   /* bytes the name may take, its NUL included */
};

static const struct naming_site SITES[GAMES + 1] = {
    { 0 },
    { 0x43B950u, { 0x81, 0xEC, 0xC4, 0x06, 0x00, 0x00 }, 0x43C645u, 0, 0x3D8u, 0x350u, 2, 0, 0x1Cu },
    { 0x44B710u, { 0x81, 0xEC, 0x24, 0x08, 0x00, 0x00 }, 0x44CCF1u, 0, 0xE48Cu, 0x538u, 2, 0, 0x18u },
    { 0x45C670u, { 0x81, 0xEC, 0x24, 0x07, 0x00, 0x00 }, 0x45C677u, 0, 0, 4u, 1, 0x10u, 0x18u },
    { 0x465DA0u, { 0x81, 0xEC, 0x9C, 0x09, 0x00, 0x00 }, 0x465DB5u, 1, 0, 4u, 1, 0x10u, 0x18u },
    { 0x46F680u, { 0x81, 0xEC, 0x9C, 0x09, 0x00, 0x00 }, 0x46F695u, 1, 0, 4u, 1, 0x10u, 0x18u },
};

static const char *const FILES[3] = {
    "Custom Stuff\\First Names - Male.txt",
    "Custom Stuff\\First Names - Female.txt",
    "Custom Stuff\\Last Names.txt",
};
#define LIST_MALE 0
#define LIST_FEMALE 1
#define LIST_LAST 2

static char g_names[3][LIST_MAX][LAST_MAX + 1];
static int g_count[3];
static int g_loaded;
static int g_game;
static unsigned int g_stock_pool;            /* S: the names the game's own roll draws from */
static unsigned char *g_trampoline;          /* our own detour's: the routine's first instruction, then back */
static int g_detour_state;                   /* 0 not tried, 1 our detour, -1 none of ours */

/* ---- the random draw -------------------------------------------------------------------------------- */

static uint64_t g_random;
static int g_random_seeded;

static uint32_t next_random(void) {
    uint64_t z;
    if (!g_random_seeded) {
        LARGE_INTEGER counter;
        counter.QuadPart = 0;
        (void)QueryPerformanceCounter(&counter);
        g_random = (uint64_t)counter.QuadPart ^ ((uint64_t)GetTickCount() << 32)
                   ^ ((uint64_t)GetCurrentProcessId() << 16) ^ ((uint64_t)GetCurrentThreadId() << 40)
                   ^ (uint64_t)(uintptr_t)&counter;
        g_random_seeded = 1;
    }
    g_random += 0x9E3779B97F4A7C15ull;
    z = g_random;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return (uint32_t)((z ^ (z >> 31)) >> 32);
}

/* Unbiased: every value below n equally likely. */
static unsigned int random_below(unsigned int n) {
    uint32_t limit, r;
    if (n <= 1) {
        return 0;
    }
    limit = 0xFFFFFFFFu - (0xFFFFFFFFu % n);
    do {
        r = next_random();
    } while (r >= limit);
    return r % n;
}

/* ---- the lists -------------------------------------------------------------------------------------- */

/* Whether the game draws UTF-8 text: the Unicode text or Unicode font companion is in the game. */
static int game_draws_utf8(void) {
    return GetModuleHandleA("VVFP Unicode Text.dll") != NULL || GetModuleHandleA("VVFP Unicode Font.dll") != NULL;
}

/* One UTF-8 letter at `p` (`n` bytes left): its code point and length, or 0 for a malformed one. */
static int utf8_letter(const unsigned char *p, size_t n, unsigned int *cp) {
    if (p[0] < 0x80) {
        *cp = p[0];
        return 1;
    }
    if ((p[0] & 0xE0) == 0xC0 && n >= 2 && (p[1] & 0xC0) == 0x80) {
        *cp = ((p[0] & 0x1Fu) << 6) | (p[1] & 0x3Fu);
        return *cp >= 0x80 ? 2 : 0;
    }
    if ((p[0] & 0xF0) == 0xE0 && n >= 3 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80) {
        *cp = ((p[0] & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu);
        return *cp >= 0x800 && (*cp < 0xD800 || *cp > 0xDFFF) ? 3 : 0;
    }
    if ((p[0] & 0xF8) == 0xF0 && n >= 4 && (p[1] & 0xC0) == 0x80 && (p[2] & 0xC0) == 0x80
        && (p[3] & 0xC0) == 0x80) {
        *cp = ((p[0] & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu);
        return *cp >= 0x10000 && *cp <= 0x10FFFF ? 4 : 0;
    }
    return 0;
}

/* The name on one line (`text`, `n` bytes of UTF-8) as the game keeps it, into out[max + 1]: 1 when it is a
   name this companion gives (see THE LISTS above), 0 otherwise. */
static int name_of(const char *text, size_t n, char *out, size_t max, int utf8_ok) {
    const unsigned char *p = (const unsigned char *)text;
    size_t i = 0, used = 0;
    int latin = 1, numeral = 1;
    unsigned int cp;
    if (n == 0) {
        return 0;
    }
    /* Pass 1: every letter allowed; is every one Latin-1? */
    while (i < n) {
        int len = utf8_letter(p + i, n - i, &cp);
        if (len == 0 || cp < 0x20 || cp == 0x7F || (cp >= 0x80 && cp < 0xA0) || cp == ' ' || cp == ',' || cp == '%'
            || cp == '\t' || cp == 0xA0) {
            return 0;
        }
        if (cp > 0xFF) {
            latin = 0;
        }
        if (strchr("IVXLCDM", (int)cp) == NULL || cp == 0) {
            numeral = 0;
        }
        i += (size_t)len;
    }
    if (numeral) {
        return 0;                                   /* "II", "IV": Number Duplicate Names' numerals */
    }
    if (latin) {
        for (i = 0; i < n; ) {
            int len = utf8_letter(p + i, n - i, &cp);
            if (used >= max) {
                return 0;
            }
            out[used++] = (char)(unsigned char)cp;
            i += (size_t)len;
        }
    } else {
        if (!utf8_ok || n > max) {
            return 0;
        }
        memcpy(out, text, n);
        used = n;
    }
    out[used] = '\0';
    return 1;
}

/* Read list `which` from its file (a missing file: no names). */
static void read_list(int which, int utf8_ok) {
    static char data[FILE_MAX + 1];
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    HANDLE file;
    DWORD got = 0;
    size_t max = which == LIST_LAST ? LAST_MAX : FIRST_MAX;
    const char *line, *end;
    g_count[which] = 0;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, FILES[which]) == 0) {
        return;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    if (!ReadFile(file, data, FILE_MAX, &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    data[got] = '\0';
    line = data;
    if (got >= 3 && (unsigned char)data[0] == 0xEF && (unsigned char)data[1] == 0xBB && (unsigned char)data[2] == 0xBF) {
        line += 3;                                  /* a byte-order mark */
    }
    for (; *line != '\0' && g_count[which] < LIST_MAX; line = *end != '\0' ? end + 1 : end) {
        char name[LAST_MAX + 1];
        size_t n;
        int k, seen = 0;
        end = line + strcspn(line, "\n");
        n = (size_t)(end - line);
        while (n > 0 && (line[n - 1] == '\r' || line[n - 1] == ' ')) {
            --n;
        }
        while (n > 0 && *line == ' ') {
            ++line;
            --n;
        }
        if (n == 0 || *line == '#' || !name_of(line, n, name, max, utf8_ok)) {
            continue;
        }
        for (k = 0; k < g_count[which] && !seen; ++k) {
            seen = strcmp(g_names[which][k], name) == 0;
        }
        if (!seen) {
            memcpy(g_names[which][g_count[which]++], name, strlen(name) + 1);
        }
    }
}

static void load_lists(void) {
    int utf8_ok, which;
    if (g_loaded) {
        return;
    }
    g_loaded = 1;
    utf8_ok = game_draws_utf8();
    for (which = 0; which < 3; ++which) {
        read_list(which, utf8_ok);
    }
}

/* ---- the exports ------------------------------------------------------------------------------------ */

/* After the game's naming routine wrote a first name into `name` (room bytes, NUL included): with C custom
   names for the sex, a custom one instead with chance C / (S + C), each equally likely.  1 when the name was
   changed.  Nothing happens before VvfpStartup ran, or with no custom names. */
__declspec(dllexport) int __stdcall VvfpCustomFirstName(char *name, unsigned int room, int female) {
    int which = female ? LIST_FEMALE : LIST_MALE;
    unsigned int count, pick;
    const char *chosen;
    size_t n;
    if (g_game == 0 || name == NULL || g_stock_pool == 0) {
        return 0;
    }
    count = (unsigned int)g_count[which];
    if (count == 0) {
        return 0;
    }
    pick = random_below(g_stock_pool + count);
    if (pick < g_stock_pool) {
        return 0;                                   /* the game's own pick stays */
    }
    chosen = g_names[which][pick - g_stock_pool];
    n = strlen(chosen);
    if (n + 1 > room) {
        return 0;
    }
    memcpy(name, chosen, n + 1);
    return 1;
}

/* The player's last names, for "VVFP Last Names.dll" (vvfp_last_names.c adds them to its list). */
__declspec(dllexport) int __stdcall VvfpCustomLastNameCount(void) {
    return g_game != 0 ? g_count[LIST_LAST] : 0;
}

__declspec(dllexport) const char *__stdcall VvfpCustomLastName(int index) {
    if (g_game == 0 || index < 0 || index >= g_count[LIST_LAST]) {
        return NULL;
    }
    return g_names[LIST_LAST][index];
}

/* For the tests: 1 when this companion detoured the naming routine itself, 2 when Last Names calls it, 0 when
   it is not armed. */
__declspec(dllexport) int __stdcall VvfpCustomNamesInstalled(void) {
    if (g_game == 0) {
        return 0;
    }
    return g_detour_state == 1 ? 1 : 2;
}

/* ---- our own detour (only when Last Names has none) ------------------------------------------------- */

static int female_of(const unsigned char *at) {
    const struct naming_site *s = &SITES[g_game];
    return *(const int *)(at + s->sex) == s->female;
}

/* VV1/VV2: the record is array + index * stride; the name is in `out`. */
static void __cdecl after_out(unsigned char *array, unsigned int index, char *out) {
    const struct naming_site *s = &SITES[g_game];
    (void)VvfpCustomFirstName(out, s->room, female_of(array + index * s->stride));
}

/* VV3-VV5: the routine wrote the name into the villager. */
static void __cdecl after_villager(unsigned char *villager) {
    const struct naming_site *s = &SITES[g_game];
    (void)VvfpCustomFirstName((char *)(villager + s->name), s->room, female_of(villager));
}

/* thiscall (array, index, out), ret 8: the routine, then the name.  Every register is the routine's own. */
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

/* S, the bound of the game's own first-name roll; 0 when the push is not there. */
static unsigned int stock_pool(const struct naming_site *s) {
    const unsigned char *at = (const unsigned char *)(uintptr_t)s->bound;
    unsigned int value = 0;
    if (!readable(at, 5)) {
        return 0;
    }
    if (s->bound_wide) {
        if (at[0] != 0x68) {
            return 0;
        }
        memcpy(&value, at + 1, 4);
    } else {
        if (at[0] != 0x6A) {
            return 0;
        }
        value = at[1];
    }
    return value >= 50 && value <= 400 ? value : 0;
}

static int own_detour(const struct naming_site *s) {
    unsigned char bytes[6];
    unsigned char *page;
    unsigned int back, rel;
    vvfp_site_write w;
    void (*wrapper)(void) = s->stride != 0 ? wrap_out : wrap_villager;
    page = vvfp_code_page_alloc(16);
    if (page == NULL) {
        return 0;
    }
    memcpy(page, s->prologue, sizeof s->prologue);
    page[6] = 0xE9;
    back = (unsigned int)((s->routine + 6) - ((unsigned int)(uintptr_t)page + 11));
    memcpy(page + 7, &back, 4);
    if (!vvfp_code_page_seal(page, 16)) {
        return 0;
    }
    g_trampoline = page;
    rel = (unsigned int)((const unsigned char *)wrapper - ((const unsigned char *)(uintptr_t)s->routine + 5));
    bytes[0] = 0xE9;
    memcpy(bytes + 1, &rel, 4);
    bytes[5] = 0x90;
    vvfp_site_bytes(&w, s->routine, sizeof bytes, s->prologue, bytes);
    if (!vvfp_install_sites(&w, 1)) {
        g_trampoline = NULL;
        VirtualFree(page, 0, MEM_RELEASE);
        return 0;
    }
    return 1;
}

/* The routine's first instruction is Last Names' jump into its own code (vvfp_last_names.c site_bytes). */
static int last_names_detour(const struct naming_site *s) {
    const unsigned char *at = (const unsigned char *)(uintptr_t)s->routine;
    HMODULE last_names = GetModuleHandleA("VVFP Last Names.dll"), holder = NULL;
    unsigned int rel;
    if (last_names == NULL || at[0] != 0xE9) {
        return 0;
    }
    memcpy(&rel, at + 1, 4);
    return GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                              (LPCSTR)(uintptr_t)(s->routine + 5 + rel), &holder)
        && holder == last_names;
}

static int install(int game) {
    const struct naming_site *s;
    const unsigned char *at;
    unsigned int pool;
    if (game < 1 || game > GAMES) {
        return 0;
    }
    if (g_detour_state != 0) {
        return g_game != 0;
    }
    g_detour_state = -1;
    s = &SITES[game];
    pool = stock_pool(s);
    at = (const unsigned char *)(uintptr_t)s->routine;
    if (pool == 0 || !readable(at, sizeof s->prologue)) {
        return 0;
    }
    load_lists();
    if (memcmp(at, s->prologue, sizeof s->prologue) == 0) {
        /* Last Names is not in the game (or refused): the detour is ours. */
        g_stock_pool = pool;
        g_game = game;                      /* the wrappers read it */
        if (!own_detour(s)) {
            g_game = 0;
            g_stock_pool = 0;
            return 0;
        }
        g_detour_state = 1;
        return 1;
    }
    if (!last_names_detour(s)) {
        return 0;                           /* someone else's bytes: never guessed at */
    }
    g_stock_pool = pool;
    g_game = game;                          /* Last Names' wrapper calls VvfpCustomFirstName */
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens (after Last Names, which the loader starts first). */
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
