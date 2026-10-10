/* VVFP VV1 Storytelling -- dropping an adult on a child tells a story
   (A New Home).

   The owner: "Like VV3-VV5 dropping an adult on a child causes the adult to
   tell stories to the child, which trains parenting skill for the adult.
   (manual drop only) The child does the action "listening to a story" which
   essentially just makes them wait in place."  In A New Home it replaces the
   embrace the drop otherwise starts (Parenting is called Breeding there).

   From the stock executable:

     * The village input handler drops the held villager on another
       (0x4251FF..0x4252B9).  A healthy target gets "Waiting for someone"
       (0x4454B0) and the held villager "Embracing" (0x445510), which queues
       step 9 and starts it at once (0x43DEF0 -> 0x43DAD0), inside the drop's
       call: 0x4252BE, the drop's return address, sits at [esp+0x30] in the
       pairing handler 0x43DAD0 (the same depth Manual Drop-Breeding tests).
     * 0x43DAD0 refuses a pair with either villager under 360 (18 years); on
       its refusal path, for the selected villager (+0x29) it shows a reason
       and clears both villagers' steps (0x43DD9E..0x43DEA2).  So in stock an
       adult dropped on a child only ever gets a refusal.
     * The Lost Children, the same engine, already does what the owner asks
       on that very path (its 0x44F610 at 0x44F963..0x44FA7F): when the
       selected initiator is 18+ and the partner is alive and under 18, it
       clears both, gives the child "Listening to a story" (0x44A0E0) and the
       adult "Telling a story" (0x449F40: talk, wait, one Parenting practice
       roll -- op 6 type 2 -- talk, wait).  The Secret City (0x466760 ->
       actions 0x5F/0x60, 0x446930/0x446A60) does the same with one Parenting
       practice per story; The Tree of Life and New Believers practise three
       times.  A New Home's own steps are the same as The Lost Children's: op
       2 (wait, 0x439550 = VV2 0x4493E0), op 7 (gesture, 0x439650 = VV2
       0x4494E0), op 15 (pose, runner 0x4488D2 = VV2 op 18 0x464F69) and op 6
       (practice, 0x43D440 type 2 = Breeding, as the embrace itself uses).

   So the companion detours the refusal path's selected-villager test
   (0x43DDC7, after the stock tutorial tip) and, ONLY when the drop's call is
   on the stack, the teller is 18 or older, and the partner is alive and
   under 18 (age 0 included), replaces the refusal with The Lost Children's
   storytelling translated to A New Home's steps -- in place, because A New
   Home has no storytelling spot and the owner wants the child to wait where
   it is, like the listener of a joke or an argument (0x4454B0's standing
   wait).  The teller's label is the game's own "Telling a story" (string
   0xA7, every language); "Listening to a story" is not in A New Home, so it
   is written here in the game's four languages.  Every other case -- adult
   on adult, a teenager on a child, a child on anyone, autonomous pairing --
   runs the stock code unchanged.

   Installed by VvfpStartup(game, shipped), which "VVFP Startup.dll" calls as
   the game opens; it verifies the site and the handler, drop and dispatcher
   bytes it relies on first and installs nothing on any other build.  Missing
   DLL: the stock game. */
#include <windows.h>
#include <string.h>

#define SITE_VA          0x43DDC7u   /* mov al,[ebp+0x29]; test al,al; je 0x43DE88 */
#define SITE_LENGTH      11
#define RESUME_VA        0x43DDD2u   /* the stock path when +0x29 is set */
#define REFUSE_VA        0x43DE88u   /* ...and when it is not */
#define HANDLER_VA       0x43DAD0u   /* the pairing handler (step 9) */
#define DROP_RETURN      0x4252BEu   /* after the drop's call 0x4252B9 -> 0x445510 */

#define CLEAR_STEPS_VA   0x439470u   /* thiscall(array, index), ret 4 */
#define PUSH_STEP_VA     0x4399F0u   /* thiscall(array, index, type, a, b, c, mode, d), ret 0x1C */
#define START_STEP_VA    0x43DEF0u   /* thiscall(array, index), ret 4 */
#define STRING_VA        0x433970u   /* thiscall(strings, id) -> char *, ret 4 */
#define RAND_VA          0x402F10u   /* cdecl rand() % n */

#define STRIDE           0x3D8
#define OFF_SELECTED     0x29
#define OFF_LABEL        0x314
#define LABEL_SIZE       0x30        /* +0x314 .. +0x343: health follows */
#define OFF_HEALTH       0x344
#define OFF_AGE          0x348
#define ARRAY_STRINGS    0x3E02C
#define AGE_ADULT        360         /* 18 years: the handler's own limit */
#define STRING_TELLING   0xA7        /* "Telling a story" */
#define SKILL_BREEDING   2

static const unsigned char SITE_STOCK[SITE_LENGTH] = {
    0x8A, 0x45, 0x29,                       /* mov al, [ebp+0x29] */
    0x84, 0xC0,                             /* test al, al */
    0x0F, 0x84, 0xB6, 0x00, 0x00, 0x00      /* je 0x43DE88 */
};
/* The handler's frame (sub esp,0xC; push ebx,ebp,esi,edi), which the stub's
   own return and the [esp+0x20]/[esp+0x30] reads rely on. */
static const unsigned char HANDLER_STOCK[9] = {
    0x83, 0xEC, 0x0C, 0x53, 0x55, 0x56, 0x8B, 0xF1, 0x57
};
/* Its epilogue, which the stub's return reproduces. */
static const unsigned char EPILOGUE_STOCK[] = {
    0x5F, 0x5E, 0x4A, 0x83, 0xE2, 0x03, 0x89, 0x55, 0x34, 0x5D, 0x5B, 0x83, 0xC4, 0x0C, 0xC2, 0x04
};
#define EPILOGUE_VA      0x43DEC7u

/* "Listening to a story" in the game's languages, in its own code page.  The
   game's language is the value its string getter reads (0x433880): 1 German,
   2 Spanish, 3 French, anything else English. */
static const char LISTEN_EN[] = "Listening to a story";
static const char LISTEN_DE[] = "H\xF6rt eine Geschichte zu";
static const char LISTEN_ES[] = "Escucha un cuento";
static const char LISTEN_FR[] = "\xC9" "coute une histoire";

typedef void (__fastcall *index_fn)(void *array, void *unused, int index);
typedef void (__fastcall *push_fn)(void *array, void *unused, int index, int type,
                                   int a, int b, int c, int mode, int d);
typedef const char *(__fastcall *string_fn)(void *strings, void *unused, int id);
typedef int (__cdecl *rand_fn)(int n);

static const unsigned int resume_va = RESUME_VA;
static const unsigned int refuse_va = REFUSE_VA;

#ifdef VVFP_TEST
struct vv1_storytelling_stats {
    int refusals_seen;      /* the refusal path reached the detour */
    int stories_started;    /* ...and a story replaced the refusal */
};
__declspec(dllexport) struct vv1_storytelling_stats VvfpVv1StorytellingStats = { 0 };
#endif

static int rnd(int n) {
    return ((rand_fn)(uintptr_t)RAND_VA)(n);
}

static void clear_steps(unsigned char *array, int index) {
    ((index_fn)(uintptr_t)CLEAR_STEPS_VA)(array, NULL, index);
}

static void start_step(unsigned char *array, int index) {
    ((index_fn)(uintptr_t)START_STEP_VA)(array, NULL, index);
}

/* Append one step (mode 0), as every stock job does. */
static void step(unsigned char *array, int index, int type, int a, int b, int c, int d) {
    ((push_fn)(uintptr_t)PUSH_STEP_VA)(array, NULL, index, type, a, b, c, 0, d);
}

static void set_label(unsigned char *record, const char *text) {
    char *label = (char *)(record + OFF_LABEL);
    int i = 0;
    if (text != NULL) {
        for (; i < LABEL_SIZE - 1 && text[i] != '\0'; ++i) {
            label[i] = text[i];
        }
    }
    label[i] = '\0';
}

static const char *listening_text(unsigned char *array) {
    const unsigned char *strings = *(const unsigned char **)(array + ARRAY_STRINGS);
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

/* The refusal path, for the selected villager `teller` and the partner the
   handler found.  Returns 1 when a story replaced the refusal. */
static int __stdcall story_try(unsigned char *array, int listener, int teller, unsigned int caller) {
    unsigned char *t;
    unsigned char *l;
    const char *telling;
#ifdef VVFP_TEST
    ++VvfpVv1StorytellingStats.refusals_seen;
#endif
    if (caller != DROP_RETURN || listener < 0 || teller < 0 || listener == teller) {
        return 0;                                   /* not the player's drop */
    }
    t = array + teller * STRIDE;
    l = array + listener * STRIDE;
    if (t[OFF_SELECTED] == 0                        /* the stock test, kept */
        || *(int *)(l + OFF_HEALTH) <= 0            /* the child must be alive */
        || *(int *)(l + OFF_AGE) >= AGE_ADULT       /* ...and under 18; 0 is a real age */
        || *(int *)(t + OFF_AGE) < AGE_ADULT) {     /* the teller 18 or older */
        return 0;
    }

    /* The child: "Listening to a story", standing where it is, for as long as
       The Lost Children's listener waits (10-19, then 13-22). */
    clear_steps(array, listener);
    set_label(l, listening_text(array));
    step(array, listener, 2, 0, 0, rnd(10) + 10, 0);
    step(array, listener, 2, 0, 0, rnd(10) + 13, 0);
    start_step(array, listener);

    /* The adult: "Telling a story" -- The Lost Children's 0x449F40 without its
       walks to that game's storytelling spot. */
    clear_steps(array, teller);
    telling = ((string_fn)(uintptr_t)STRING_VA)(*(void **)(array + ARRAY_STRINGS), NULL, STRING_TELLING);
    set_label(t, telling);
    step(array, teller, 15, 3, 3, 0, 0);                 /* talking pose */
    step(array, teller, 2, 0, 0, 3, 0);                  /* wait */
    step(array, teller, 7, 0, 0, rnd(8) + 3, 0);         /* gesture */
    step(array, teller, 15, 3, 0, 0, 0);                 /* pose */
    step(array, teller, 2, 0, 0, rnd(3) + 3, 0);         /* wait */
    step(array, teller, 6, 0, 0, 0, SKILL_BREEDING);     /* one Breeding practice roll */
    step(array, teller, 7, 0, 0, rnd(8) + 3, 0);         /* gesture */
    step(array, teller, 2, 0, 0, rnd(5) + 3, 0);         /* wait */
    start_step(array, teller);
#ifdef VVFP_TEST
    ++VvfpVv1StorytellingStats.stories_started;
#endif
    return 1;
}

/* At 0x43DDC7, inside 0x43DAD0: esi = the villager array, ebp = the teller's
   record, ebx = the partner's index, [esp+0x20] = the teller's index (the
   handler's argument), [esp+0x30] = the drop's return address when this is
   the player's drop.  pushfd and pushad add 0x24. */
static __declspec(naked) void story_stub(void) {
    __asm {
        pushfd
        pushad
        mov eax, dword ptr [esp + 0x24 + 0x30]  ; the caller two frames up
        mov ecx, dword ptr [esp + 0x24 + 0x20]  ; the teller's index
        push eax
        push ecx
        push ebx                                ; the partner's index
        push esi                                ; the villager array
        call story_try                          ; stdcall, 16 bytes
        test eax, eax
        jnz told
        popad
        popfd
        mov al, byte ptr [ebp + 0x29]           ; the displaced stock bytes
        test al, al
        jz refuse
        jmp dword ptr [resume_va]
    refuse:
        jmp dword ptr [refuse_va]
    told:
        popad
        popfd
        pop edi                                 ; the handler's own return
        pop esi
        pop ebp
        pop ebx
        add esp, 0xC
        ret 4
    }
}

static int code_is(unsigned int va, const unsigned char *bytes, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, bytes, length) == 0;
}

/* `call target` at `va`. */
static int calls(unsigned int va, unsigned int target) {
    unsigned char bytes[5];
    unsigned int rel = target - (va + 5);
    bytes[0] = 0xE8;
    memcpy(bytes + 1, &rel, 4);
    return code_is(va, bytes, sizeof bytes);
}

static int build_is_stock(void) {
    return code_is(SITE_VA, SITE_STOCK, SITE_LENGTH)
        && code_is(HANDLER_VA, HANDLER_STOCK, sizeof HANDLER_STOCK)
        && code_is(EPILOGUE_VA, EPILOGUE_STOCK, sizeof EPILOGUE_STOCK)
        && calls(0x4252B9u, 0x445510u)                 /* the drop's call */
        && calls(0x445570u, START_STEP_VA);            /* ...which starts step 9 at once */
}

/* The bytes the site is overwritten with: a jmp to the stub, then nops. */
static void site_bytes(unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)story_stub
                                      - ((const unsigned char *)(uintptr_t)SITE_VA + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < SITE_LENGTH; ++i) {
        out[i] = 0x90;
    }
}

static int install_state;   /* 0 untried, 1 installed, -1 refused */

static int install(void) {
    unsigned char bytes[SITE_LENGTH];
    unsigned char *site = (unsigned char *)(uintptr_t)SITE_VA;
    DWORD old;
    if (install_state != 0) {
        return install_state == 1;
    }
    install_state = -1;
    if (!build_is_stock()) {
        return 0;
    }
    site_bytes(bytes);
    if (!VirtualProtect(site, SITE_LENGTH, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(site, bytes, SITE_LENGTH);
    VirtualProtect(site, SITE_LENGTH, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, SITE_LENGTH);
    install_state = 1;
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens.  A New Home only. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game == 1) {
        (void)install();
    }
}

#ifdef VVFP_TEST
/* For the test build only: the site, its stock bytes, what it becomes, and
   the stub. */
__declspec(dllexport) int __stdcall VvfpVv1StorytellingProbe(unsigned int *site_va,
                                                              unsigned char *stock,
                                                              unsigned char *patched,
                                                              unsigned int *stub_va) {
    *site_va = SITE_VA;
    memcpy(stock, SITE_STOCK, SITE_LENGTH);
    site_bytes(patched);
    *stub_va = (unsigned int)(uintptr_t)story_stub;
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
