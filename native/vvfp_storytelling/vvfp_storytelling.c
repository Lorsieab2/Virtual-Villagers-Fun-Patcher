/* VVFP Storytelling -- dropping an adult on a child tells a story
   (A New Home and The Lost Children).

   The owner: "Like VV3-VV5 dropping an adult on a child causes the adult to
   tell stories to the child, which trains parenting skill for the adult.
   (manual drop only) The child does the action "listening to a story" which
   essentially just makes them wait in place."  It replaces the embrace the
   drop starts (Parenting is called Breeding in A New Home).

   WHY THE DROP ITSELF.  In both games the drop handler picks the villager
   under the mouse (hit test: A New Home 0x4392D0, The Lost Children
   0x4490C0), gives it "Waiting for someone" and the dropped villager
   "Embracing", whose pairing step (0x43DAD0 / 0x44F610) then looks for its
   partner AGAIN, by proximity (0x439350 / 0x449160): the highest-numbered
   villager whose current step is a wait, in a box around the DROPPED
   villager's own position.  The dragged villager is drawn at the mouse
   minus (0x19, 0x13) (0x439410 / 0x449220 with the mouse -5/+13), so the
   two boxes do not coincide: drop on the left or top part of a child, or
   near anyone else who is waiting, and the pairing step finds nobody (the
   "Embracing" label stays and nothing happens) or someone else (a real
   embrace).  The Lost Children's own storytelling sits behind that second
   search (0x44F963..0x44FA7F) -- which is why the owner sees embracing.

   So the companion acts at the drop, on the villager the player dropped on:
   it replaces the drop handler's "Waiting for someone" + "Embracing" calls
   (A New Home 0x425291, The Lost Children 0x430F2D) when the dropped
   villager is 18 or older and the villager under the mouse is alive and
   under 18 (age 0 included).  Every other drop runs the stock calls.

     * The Lost Children: exactly what its pairing step does for that pair
       (0x44F9B0..0x44FA7F), with the game's own routines: the child gets
       "Listening to a story" (0x44A0E0), the adult "Telling a story"
       (0x449F40: talk, wait, one Parenting practice roll) -- or, from
       Parenting 50, "Teaching children" (0x44A4E0) -- the first-story tip
       (0x1C2) and a 25% chance for each playing child nearby to listen too.
     * A New Home has neither routine nor "Listening to a story": the same
       storyteller steps (0x449F40) in A New Home's own step types (op 2
       wait 0x439550, op 7 gesture 0x439650 -- the same code as The Lost
       Children's -- op 15 pose, op 6 practice with skill 2, Breeding), in
       place, because A New Home has no storytelling spot and the owner wants
       the child to wait where it is, like the listener of a joke
       (0x4454B0's standing wait).  The teller's label is the game's own
       "Telling a story" (string 0xA7, every language); the child's is
       written here in the game's four languages.

   Installed by VvfpStartup(game, shipped), which "VVFP Startup.dll" calls as
   the game opens; it verifies the site and every routine it calls first and
   installs nothing on any other build.  Missing DLL: the stock game. */
#include <windows.h>
#include <string.h>

#ifdef VVFP_TEST
struct storytelling_stats {
    int drops_seen;         /* a drop on a healthy villager reached the detour */
    int stories_started;    /* ...and a story replaced the embrace */
};
__declspec(dllexport) struct storytelling_stats VvfpStorytellingStats = { 0 };
#endif

typedef void (__fastcall *index_fn)(void *array, void *unused, int index);
typedef void (__fastcall *push_fn)(void *array, void *unused, int index, int type,
                                   int a, int b, int c, int mode, int d);
typedef const char *(__fastcall *string_fn)(void *strings, void *unused, int id);
typedef void (__fastcall *tip_fn)(void *state, void *unused, int id, int show);
typedef int (__cdecl *rand_fn)(int n);

/* ---- A New Home ------------------------------------------------------- */

#define V1_SITE          0x425291u   /* mov ecx,[esi+0x20]; push edi; call 0x4454B0 */
#define V1_RESUME        0x42529Au
#define V1_DONE          0x4252BEu   /* the drop handler after its villager-on-villager case */
#define V1_WAITING       0x4454B0u   /* "Waiting for someone" (displaced call) */
#define V1_CLEAR         0x439470u
#define V1_PUSH          0x4399F0u
#define V1_START         0x43DEF0u
#define V1_STRING        0x433970u
#define V1_RAND          0x402F10u
#define V1_STRIDE        0x3D8
#define V1_LABEL         0x314
#define V1_LABEL_SIZE    0x30
#define V1_HEALTH        0x344
#define V1_AGE           0x348
#define V1_STRINGS       0x3E02C
#define V1_HELD          0xAD34      /* village state: the held villager */
#define V1_TELLING       0xA7        /* "Telling a story" */

/* ---- The Lost Children ---------------------------------------------- */

#define V2_SITE          0x430F2Du   /* mov ecx,[esi+0x20]; push ebx; call 0x4492A0 */
#define V2_RESUME        0x430F36u
#define V2_DONE          0x430F63u
#define V2_CLEAR         0x4492A0u
#define V2_LISTEN        0x44A0E0u   /* "Listening to a story" */
#define V2_TELL          0x449F40u   /* "Telling a story" */
#define V2_TEACH         0x44A4E0u   /* "Teaching children" */
#define V2_TIP           0x4257A0u
#define V2_RAND          0x4031A0u
#define V2_STRIDE        0xE48C
#define V2_ACTIVE        0x30
#define V2_ACTIVITY      0x44
#define V2_HEALTH        0x52C
#define V2_AGE           0x530
#define V2_SICK          0x53C
#define V2_PARENTING     0x7E4
#define V2_STATE         0xE574D4
#define V2_TIP_FLAG      0x1F3
#define V2_TIP_ID        0x1C2
#define V2_PLAYING       0x1A

#define AGE_ADULT        360         /* 18 years: the pairing steps' own limit */
#define AGE_CHILD        280         /* 14 years */
#define SITE_LENGTH      9

static const unsigned char V1_SITE_STOCK[SITE_LENGTH] = {
    0x8B, 0x4E, 0x20, 0x57, 0xE8, 0x16, 0x02, 0x02, 0x00
};
static const unsigned char V2_SITE_STOCK[SITE_LENGTH] = {
    0x8B, 0x4E, 0x20, 0x53, 0xE8, 0x6A, 0x83, 0x01, 0x00
};

struct prologue {
    unsigned int va;
    unsigned char bytes[8];
};
/* Every routine a story calls, by its first bytes. */
static const struct prologue V1_CALLS[] = {
    { V1_CLEAR,  { 0x8B, 0x44, 0x24, 0x04, 0x69, 0xC0, 0xD8, 0x03 } },
    { V1_PUSH,   { 0x83, 0xEC, 0x18, 0x8B, 0x44, 0x24, 0x20, 0x8B } },
    { V1_START,  { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0xD0, 0x69, 0xD2 } },
    { V1_STRING, { 0x8B, 0x49, 0x04, 0xE9, 0x08, 0xFF, 0xFF, 0xFF } },
    { V1_RAND,   { 0x56, 0x8B, 0x74, 0x24, 0x08, 0x85, 0xF6, 0x7E } },
};
static const struct prologue V2_CALLS[] = {
    { V2_CLEAR,  { 0x8B, 0x44, 0x24, 0x04, 0x69, 0xC0, 0x8C, 0xE4 } },
    { V2_LISTEN, { 0x53, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x10, 0x8B } },
    { V2_TELL,   { 0x53, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x10, 0x8B } },
    { V2_TEACH,  { 0x83, 0xEC, 0x0C, 0x53, 0x55, 0x56, 0x33, 0xC0 } },
    { V2_TIP,    { 0x33, 0xC0, 0x8D, 0x91, 0x7C, 0x04, 0x03, 0x00 } },
    { V2_RAND,   { 0x56, 0x8B, 0x74, 0x24, 0x08, 0x85, 0xF6, 0x7E } },
};

/* "Listening to a story" in A New Home's languages, in its own code page.
   The game's language is the value its string getter reads (0x433880): 1
   German, 2 Spanish, 3 French, anything else English. */
static const char LISTEN_EN[] = "Listening to a story";
static const char LISTEN_DE[] = "H\xF6rt eine Geschichte zu";
static const char LISTEN_ES[] = "Escucha un cuento";
static const char LISTEN_FR[] = "\xC9" "coute une histoire";

static const unsigned int v1_waiting = V1_WAITING;
static const unsigned int v1_resume = V1_RESUME;
static const unsigned int v1_done = V1_DONE;
static const unsigned int v2_clear = V2_CLEAR;
static const unsigned int v2_resume = V2_RESUME;
static const unsigned int v2_done = V2_DONE;

static int at(const unsigned char *record, int offset) {
    return *(const int *)(record + offset);
}

/* ---- A New Home's story ---------------------------------------------- */

static void v1_step(unsigned char *array, int index, int type, int a, int b, int c, int d) {
    ((push_fn)(uintptr_t)V1_PUSH)(array, NULL, index, type, a, b, c, 0, d);   /* append */
}

static int v1_rand(int n) {
    return ((rand_fn)(uintptr_t)V1_RAND)(n);
}

static void v1_label(unsigned char *record, const char *text) {
    char *label = (char *)(record + V1_LABEL);
    int i = 0;
    if (text != NULL) {
        for (; i < V1_LABEL_SIZE - 1 && text[i] != '\0'; ++i) {
            label[i] = text[i];
        }
    }
    label[i] = '\0';
}

static const char *v1_listening(unsigned char *array) {
    const unsigned char *strings = *(const unsigned char **)(array + V1_STRINGS);
    const int *language;
    if (strings == NULL) {
        return LISTEN_EN;
    }
    language = *(const int *const *)(strings + 4);
    if (language == NULL) {
        return LISTEN_EN;
    }
    switch (*language) {
    case 1: return LISTEN_DE;
    case 2: return LISTEN_ES;
    case 3: return LISTEN_FR;
    default: return LISTEN_EN;
    }
}

/* The drop of `teller` on `listener`; 1 when a story replaced the embrace. */
static int __stdcall v1_story(unsigned char *array, int listener, int teller) {
    unsigned char *t;
    unsigned char *l;
#ifdef VVFP_TEST
    ++VvfpStorytellingStats.drops_seen;
#endif
    if (listener < 0 || listener > 255 || teller < 0 || teller > 255 || listener == teller) {
        return 0;
    }
    t = array + teller * V1_STRIDE;
    l = array + listener * V1_STRIDE;
    if (at(t, V1_AGE) < AGE_ADULT || at(l, V1_HEALTH) <= 0 || at(l, V1_AGE) >= AGE_ADULT) {
        return 0;                                   /* 0 is a real age */
    }
    /* The child: standing waits as long as The Lost Children's listener's
       (10-19, then 13-22). */
    ((index_fn)(uintptr_t)V1_CLEAR)(array, NULL, listener);
    v1_label(l, v1_listening(array));
    v1_step(array, listener, 2, 0, 0, v1_rand(10) + 10, 0);
    v1_step(array, listener, 2, 0, 0, v1_rand(10) + 13, 0);
    ((index_fn)(uintptr_t)V1_START)(array, NULL, listener);

    /* The adult: The Lost Children's 0x449F40 without its walks. */
    ((index_fn)(uintptr_t)V1_CLEAR)(array, NULL, teller);
    v1_label(t, ((string_fn)(uintptr_t)V1_STRING)(*(void **)(array + V1_STRINGS), NULL, V1_TELLING));
    v1_step(array, teller, 15, 3, 3, 0, 0);                 /* talking pose */
    v1_step(array, teller, 2, 0, 0, 3, 0);                  /* wait */
    v1_step(array, teller, 7, 0, 0, v1_rand(8) + 3, 0);     /* gesture */
    v1_step(array, teller, 15, 3, 0, 0, 0);                 /* pose */
    v1_step(array, teller, 2, 0, 0, v1_rand(3) + 3, 0);     /* wait */
    v1_step(array, teller, 6, 0, 0, 0, 2);                  /* one Breeding practice roll */
    v1_step(array, teller, 7, 0, 0, v1_rand(8) + 3, 0);     /* gesture */
    v1_step(array, teller, 2, 0, 0, v1_rand(5) + 3, 0);     /* wait */
    ((index_fn)(uintptr_t)V1_START)(array, NULL, teller);
#ifdef VVFP_TEST
    ++VvfpStorytellingStats.stories_started;
#endif
    return 1;
}

/* At 0x425291: esi = the village scene, edi = the villager under the mouse
   (its steps already cleared, 0x42528C); the held villager is
   [[esi+0x10]+0xAD34] and the villager array [esi+0x20]. */
static __declspec(naked) void v1_stub(void) {
    __asm {
        pushfd
        pushad
        mov eax, dword ptr [esi + 0x10]
        push dword ptr [eax + 0xAD34]           ; the dropped villager
        push edi                                ; the villager under the mouse
        push dword ptr [esi + 0x20]             ; the villager array
        call v1_story
        test eax, eax
        jnz told
        popad
        popfd
        mov ecx, dword ptr [esi + 0x20]         ; the displaced stock call
        push edi
        call dword ptr [v1_waiting]
        jmp dword ptr [v1_resume]
    told:
        popad
        popfd
        jmp dword ptr [v1_done]
    }
}

/* ---- The Lost Children's story --------------------------------------- */

static int __stdcall v2_story(unsigned char *array, int listener, int teller) {
    unsigned char *t;
    unsigned char *l;
    unsigned char *state;
    int i;
#ifdef VVFP_TEST
    ++VvfpStorytellingStats.drops_seen;
#endif
    if (listener < 0 || listener > 255 || teller < 0 || teller > 255 || listener == teller) {
        return 0;
    }
    t = array + teller * V2_STRIDE;
    l = array + listener * V2_STRIDE;
    if (at(t, V2_AGE) < AGE_ADULT || at(l, V2_HEALTH) <= 0 || at(l, V2_AGE) >= AGE_ADULT) {
        return 0;
    }
    /* 0x44F9B0..0x44FA7F, for the villager the player dropped on. */
    ((index_fn)(uintptr_t)V2_CLEAR)(array, NULL, listener);
    ((index_fn)(uintptr_t)V2_LISTEN)(array, NULL, listener);
    ((index_fn)(uintptr_t)V2_CLEAR)(array, NULL, teller);
    if (at(t, V2_PARENTING) >= 50) {
        ((index_fn)(uintptr_t)V2_TEACH)(array, NULL, teller);
    } else {
        ((index_fn)(uintptr_t)V2_TELL)(array, NULL, teller);
        state = *(unsigned char **)(array + V2_STATE);
        if (state != NULL && state[V2_TIP_FLAG] != 0) {
            ((tip_fn)(uintptr_t)V2_TIP)(state, NULL, V2_TIP_ID, 1);
            state = *(unsigned char **)(array + V2_STATE);
            state[V2_TIP_FLAG] = 0;
        }
        for (i = 0; i < 256; ++i) {
            unsigned char *r = array + i * V2_STRIDE;
            if (r[V2_ACTIVE] != 0 && at(r, V2_HEALTH) > 0 && at(r, V2_SICK) == 0
                && at(r, V2_ACTIVITY) == V2_PLAYING && at(r, V2_AGE) < AGE_CHILD
                && ((rand_fn)(uintptr_t)V2_RAND)(100) < 25) {
                ((index_fn)(uintptr_t)V2_CLEAR)(array, NULL, i);
                ((index_fn)(uintptr_t)V2_LISTEN)(array, NULL, i);
            }
        }
    }
#ifdef VVFP_TEST
    ++VvfpStorytellingStats.stories_started;
#endif
    return 1;
}

/* At 0x430F2D: esi = the village scene, ebx = the villager under the mouse;
   the held villager is [[esi+0x10]+0x304F0] and the array [esi+0x20]. */
static __declspec(naked) void v2_stub(void) {
    __asm {
        pushfd
        pushad
        mov eax, dword ptr [esi + 0x10]
        push dword ptr [eax + 0x304F0]          ; the dropped villager
        push ebx                                ; the villager under the mouse
        push dword ptr [esi + 0x20]             ; the villager array
        call v2_story
        test eax, eax
        jnz told
        popad
        popfd
        mov ecx, dword ptr [esi + 0x20]         ; the displaced stock call
        push ebx
        call dword ptr [v2_clear]
        jmp dword ptr [v2_resume]
    told:
        popad
        popfd
        jmp dword ptr [v2_done]
    }
}

/* ---- Installing ------------------------------------------------------- */

static int code_is(unsigned int va, const unsigned char *bytes, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *where = (const void *)(uintptr_t)va;
    if (VirtualQuery(where, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(where, bytes, length) == 0;
}

static void site_bytes(unsigned int site, void (*stub)(void), unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)stub
                                      - ((const unsigned char *)(uintptr_t)site + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < SITE_LENGTH; ++i) {
        out[i] = 0x90;
    }
}

static int install_state;   /* 0 untried, 1 installed, -1 refused */

static int install(int game) {
    const unsigned char *stock;
    const struct prologue *calls;
    size_t count, i;
    unsigned int site;
    void (*stub)(void);
    unsigned char bytes[SITE_LENGTH];
    DWORD old;
    if (install_state != 0) {
        return install_state == 1;
    }
    install_state = -1;
    if (game == 1) {
        site = V1_SITE, stock = V1_SITE_STOCK, stub = v1_stub;
        calls = V1_CALLS, count = sizeof V1_CALLS / sizeof V1_CALLS[0];
    } else if (game == 2) {
        site = V2_SITE, stock = V2_SITE_STOCK, stub = v2_stub;
        calls = V2_CALLS, count = sizeof V2_CALLS / sizeof V2_CALLS[0];
    } else {
        return 0;
    }
    if (!code_is(site, stock, SITE_LENGTH)) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (!code_is(calls[i].va, calls[i].bytes, sizeof calls[i].bytes)) {
            return 0;
        }
    }
    site_bytes(site, stub, bytes);
    if (!VirtualProtect((void *)(uintptr_t)site, SITE_LENGTH, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy((void *)(uintptr_t)site, bytes, SITE_LENGTH);
    VirtualProtect((void *)(uintptr_t)site, SITE_LENGTH, old, &old);
    FlushInstructionCache(GetCurrentProcess(), (void *)(uintptr_t)site, SITE_LENGTH);
    install_state = 1;
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    (void)install(game);
}

#ifdef VVFP_TEST
/* For the test build only: a game's site, its stock bytes, what it becomes,
   and the stub. */
__declspec(dllexport) int __stdcall VvfpStorytellingProbe(int game, unsigned int *site_va,
                                                          unsigned char *stock, unsigned char *patched,
                                                          unsigned int *stub_va) {
    unsigned int site = game == 1 ? V1_SITE : V2_SITE;
    void (*stub)(void) = game == 1 ? v1_stub : v2_stub;
    *site_va = site;
    memcpy(stock, game == 1 ? V1_SITE_STOCK : V2_SITE_STOCK, SITE_LENGTH);
    site_bytes(site, stub, patched);
    *stub_va = (unsigned int)(uintptr_t)stub;
    return SITE_LENGTH;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
