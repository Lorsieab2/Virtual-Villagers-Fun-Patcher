/* VVFP Golden Mushroom -- draws the golden mushroom's own image.

   The row's executable bytes (data/builds.json, *_super_secret_golden_mushroom)
   add the mushroom and its pickup; this companion only draws it, from a NEW
   image file, Images\golden_mushroom.png (29x22, the art from The Lost
   Children's files).  No stock sprite sheet is edited.  The Lost Children
   needs no companion: its own sheet already holds this art.

   WHERE THE GAMES DRAW IT, read from the stock executables:

     VV1  The mushroom is frame 15 of carrying.png, a 15x1 sheet (so frame 15
          does not exist in the file), both on the ground and carried (the
          villager's carry pose 0xF is pushed as the frame).  Frames of that
          sheet are drawn through the frame-draw thunk 0x4093D0 (`mov ecx,
          [ecx]; jmp 0x4087B0`; thiscall (sprite, x, y, frame), ret 0x10) and,
          for a dropped item fading out, through the call at 0x41ABA0 to the
          5-argument thunk 0x4093E0 ((sprite, x, y, frame, float alpha), ret
          0x14).  0x4093E0 itself is spliced by the Origins row, so the call
          site is hooked rather than the thunk, and the golden path still
          enters 0x4093E0.
     VV3  Collectable frame 50 (item 0x66 - 0x34) of the collectables sheet,
     VV4  whose pointer is the collectables manager's own field (VV3/VV4
     VV5  [0x58F428 + 0x1B0], VV5 [0x4DBFC8 + 0x840]; the manager is a static
          object, so the field is a fixed address).  Everything in the world
          is drawn through one entry, VV3 0x42E510, VV4 0x44C640, VV5 0x44F380
          (thiscall (sprite, x, y, frame, float scale), ret 0x14), whose first
          five bytes are `fild dword [esp+8]; push esi`.

   WHAT THIS COMPANION DOES.  In each of those places it asks one question:
   is this the golden frame of that sheet (VV1: a 15x1 sheet and frame 15;
   VV3-VV5: the collectables sheet and frame 50)?  If so it draws the golden
   image instead -- frame 0 of a 1x1 sprite, placed by a fixed offset so it
   sits where the sheet frame sat -- through the same stock draw call with the
   same registers and the same stack.  Anything else is passed through
   untouched.  The golden sprite is built on first use by the game's own
   allocator and sprite constructor with the bare name "golden_mushroom.png"
   (resolved by the game to its Images folder, like every stock sheet).  If
   the image is missing or does not load, the golden frame is simply not
   drawn -- the stock frame is never shown in its place.

   It also answers the spawn's kind roll (see "The spawn's kind roll"), so
   without this companion that roll always answers no.

   INSTALLED by the export whose ordinal is the game number (1, 3, 4, 5),
   stdcall, no arguments.  The row's executable-side loader stub calls it:
   LoadLibraryA("VVFP Golden Mushroom.dll") then GetProcAddress(module,
   ordinal) at a call the game makes while loading its images.  Every site's
   stock bytes are verified first, all of a game's sites or none are written,
   and repeated calls do nothing more. */
#include <windows.h>
#include <string.h>

/* ---- The golden sprite ----------------------------------------------------- */
struct game_calls {
    unsigned int alloc;            /* cdecl operator new(size) */
    unsigned int ctor;             /* thiscall sprite(name, cols, rows), ret 0xC */
};

static const struct game_calls CALLS[6] = {
    { 0, 0 },
    { 0x44AF03u, 0x40A070u },      /* A New Home */
    { 0, 0 },                      /* The Lost Children: no companion */
    { 0x46EC93u, 0x40AF10u },      /* The Secret City */
    { 0x470C5Cu, 0x40AB10u },      /* The Tree of Life */
    { 0x47BBDCu, 0x40B010u },      /* New Believers */
};

#define SPRITE_SIZE   0x34
#define SPRITE_COLS   0x08
#define SPRITE_ROWS   0x0C
#define SPRITE_FRAMEW 0x10
#define SPRITE_FRAMEH 0x14

/* The game keeps the name pointer it is given, so it lives as long as the
   module (which is never unloaded: the loader stub never frees it). */
static const char IMAGE_NAME[] = "golden_mushroom.png";
static const char IMAGE_RELATIVE[] = "Images\\golden_mushroom.png";

static int active_game;            /* the game whose sites are installed */
static int sprite_state;           /* 0 = not built, 1 = built, -1 = failed */
static unsigned char *sprite;

/* Counters the tests read.  Compiled only into the TEST build (VVFP_TEST,
   tests/test_dlls/): the shipped DLL carries no counters and no probe. */
#ifdef VVFP_TEST
struct vvfp_golden_stats {
    int golden_draws;              /* golden frames drawn with the new image */
    int skipped_draws;             /* golden frames not drawn (image failed) */
    int builds;                    /* sprite construction attempts */
};
__declspec(dllexport) struct vvfp_golden_stats VvfpGoldenMushroomStats = { 0, 0, 0 };
#define GOLDEN_COUNT_BUILD ++VvfpGoldenMushroomStats.builds
#define GOLDEN_COUNT_DRAW __asm inc dword ptr [VvfpGoldenMushroomStats]
#define GOLDEN_COUNT_SKIP __asm inc dword ptr [VvfpGoldenMushroomStats + 4]
#else
#define GOLDEN_COUNT_BUILD ((void)0)
#define GOLDEN_COUNT_DRAW
#define GOLDEN_COUNT_SKIP
#endif

typedef void *(__cdecl *alloc_t)(unsigned int);
/* thiscall through fastcall: ecx = this, edx unused, callee pops the rest. */
typedef void *(__fastcall *ctor_t)(void *self, void *unused, const char *name, int cols, int rows);

/* Is the image beside the game?  Checked before the game's own loader is
   asked, so a missing file never reaches it. */
static int image_present(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n = GetModuleFileNameA(NULL, path, MAX_PATH);
    DWORD attributes;
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    slash = strrchr(path, '\\');
    if (slash == NULL
        || (size_t)(slash + 1 - path) + sizeof(IMAGE_RELATIVE) > sizeof(path)) {
        return 0;
    }
    memcpy(slash + 1, IMAGE_RELATIVE, sizeof(IMAGE_RELATIVE));
    attributes = GetFileAttributesA(path);
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

/* The golden sprite, built on first use; NULL when it cannot be drawn. */
static unsigned char *__cdecl golden_sprite(void) {
    if (sprite_state == 0) {
        const struct game_calls *c = &CALLS[active_game];
        unsigned char *mem;
        sprite_state = -1;
        GOLDEN_COUNT_BUILD;
        if (c->alloc == 0 || !image_present()) {
            return NULL;
        }
        mem = (unsigned char *)((alloc_t)(uintptr_t)c->alloc)(SPRITE_SIZE);
        if (mem == NULL) {
            return NULL;
        }
        ((ctor_t)(uintptr_t)c->ctor)(mem, NULL, IMAGE_NAME, 1, 1);
        if (*(const int *)(mem + SPRITE_FRAMEW) <= 0 || *(const int *)(mem + SPRITE_FRAMEH) <= 0) {
            return NULL;               /* did not load: never drawn (the object is kept) */
        }
        sprite = mem;
        sprite_state = 1;
    }
    return sprite_state == 1 ? sprite : NULL;
}

/* ---- A New Home ------------------------------------------------------------ */
#define VV1_FRAME_SITE   0x4093D0u     /* mov ecx, [ecx]; jmp 0x4087B0 */
#define VV1_FADE_SITE    0x41ABA0u     /* call 0x4093E0 */
#define VV1_SHEET_COLS   15
#define VV1_SHEET_ROWS   1
#define VV1_FRAME        15
#define VV1_DX           6
#define VV1_DY           2
static const unsigned char VV1_FRAME_STOCK[7] = { 0x8B, 0x09, 0xE9, 0xD9, 0xF3, 0xFF, 0xFF };
static const unsigned char VV1_FADE_STOCK[5] = { 0xE8, 0x3B, 0xE8, 0xFE, 0xFF };
static const unsigned int vv1_frame_draw = 0x4087B0u;
static const unsigned int vv1_fade_thunk = 0x4093E0u;

/* Entered from the thunk site: ecx = the renderer holder, [esp] = return,
   [esp+4] sprite, [esp+8] x, [esp+0xC] y, [esp+0x10] frame.  Every register
   but ecx (which the thunk itself loads) reaches the stock draw unchanged. */
static __declspec(naked) void vv1_frame_stub(void) {
    __asm {
        mov ecx, dword ptr [ecx]           ; the displaced thunk instruction
        push eax
        mov eax, dword ptr [esp + 8]       ; the sprite
        cmp dword ptr [eax + SPRITE_COLS], VV1_SHEET_COLS
        jne stock
        cmp dword ptr [eax + SPRITE_ROWS], VV1_SHEET_ROWS
        jne stock
        cmp dword ptr [esp + 0x14], VV1_FRAME
        jne stock
        pushad
        call golden_sprite
        mov [esp + 0x1C], eax              ; pushad's eax slot
        popad
        test eax, eax
        jz skip
        mov dword ptr [esp + 8], eax       ; the golden sprite
        add dword ptr [esp + 0xC], VV1_DX
        add dword ptr [esp + 0x10], VV1_DY
        mov dword ptr [esp + 0x14], 0      ; its only frame
        GOLDEN_COUNT_DRAW
    stock:
        pop eax
        jmp dword ptr [vv1_frame_draw]
    skip:
        GOLDEN_COUNT_SKIP
        pop eax
        ret 0x10                           ; the draw's own cleanup
    }
}

/* Entered from the call at 0x41ABA0: [esp] = 0x41ABA5, then (sprite, x, y,
   frame, alpha).  The golden frame goes on into 0x4093E0 like any other. */
static __declspec(naked) void vv1_fade_stub(void) {
    __asm {
        push eax
        mov eax, dword ptr [esp + 8]
        cmp dword ptr [eax + SPRITE_COLS], VV1_SHEET_COLS
        jne stock
        cmp dword ptr [eax + SPRITE_ROWS], VV1_SHEET_ROWS
        jne stock
        cmp dword ptr [esp + 0x14], VV1_FRAME
        jne stock
        pushad
        call golden_sprite
        mov [esp + 0x1C], eax
        popad
        test eax, eax
        jz skip
        mov dword ptr [esp + 8], eax
        add dword ptr [esp + 0xC], VV1_DX
        add dword ptr [esp + 0x10], VV1_DY
        mov dword ptr [esp + 0x14], 0
        GOLDEN_COUNT_DRAW
    stock:
        pop eax
        jmp dword ptr [vv1_fade_thunk]
    skip:
        GOLDEN_COUNT_SKIP
        pop eax
        ret 0x14
    }
}

/* ---- The Secret City / The Tree of Life / New Believers ---------------------- */
#define LATER_FRAME 50
static const unsigned char LATER_STOCK[5] = { 0xDB, 0x44, 0x24, 0x08, 0x56 };

/* One stub per game.  At the draw entry: [esp] = return, [esp+4] sprite,
   [esp+8] x, [esp+0xC] y, [esp+0x10] frame, [esp+0x14] scale.  The stock
   path replays the displaced `fild dword [esp+8]; push esi` and resumes at
   entry+5 with every register and the stack as the caller left them. */
#define LATER_STUB(NAME, SLOT, RESUME, DX, DY)                                  \
    static const unsigned int NAME##_resume = RESUME;                          \
    static __declspec(naked) void NAME##_stub(void) {                          \
        __asm {                                                                \
            __asm push eax                                                     \
            __asm mov eax, dword ptr [esp + 8]                                 \
            __asm test eax, eax                                                \
            __asm jz stock                                                     \
            __asm cmp eax, dword ptr ds:[SLOT]                                 \
            __asm jne stock                                                    \
            __asm cmp dword ptr [esp + 0x14], LATER_FRAME                      \
            __asm jne stock                                                    \
            __asm pushad                                                       \
            __asm call golden_sprite                                           \
            __asm mov [esp + 0x1C], eax                                        \
            __asm popad                                                        \
            __asm test eax, eax                                                \
            __asm jz skip                                                      \
            __asm mov dword ptr [esp + 8], eax                                 \
            __asm add dword ptr [esp + 0xC], DX                                \
            __asm add dword ptr [esp + 0x10], DY                               \
            __asm mov dword ptr [esp + 0x14], 0                                \
            GOLDEN_COUNT_DRAW                                                  \
            __asm stock:                                                       \
            __asm pop eax                                                      \
            __asm fild dword ptr [esp + 8]                                     \
            __asm push esi                                                     \
            __asm jmp dword ptr [NAME##_resume]                                \
            __asm skip:                                                        \
            GOLDEN_COUNT_SKIP                                                  \
            __asm pop eax                                                      \
            __asm ret 0x14                                                     \
        }                                                                      \
    }

/* The collectables sheet pointer: the manager's field at a fixed address. */
LATER_STUB(vv3, 0x58F5D8, 0x42E515u, 7, 0)
LATER_STUB(vv4, 0x4CC9E8, 0x44C645u, 7, 0)
LATER_STUB(vv5, 0x4DC808, 0x44F385u, 7, 1)

/* ---- The spawn's kind roll -------------------------------------------------- */
/* The row puts a 5-byte stub in its own spawn code, `test esp, esp; ret`
   (ZF = 0: the plain kinds), that the spawn calls.  Installing turns it into
   a jmp to roll_stub.  The roll draws from the game's own C rand() (0..32767,
   the same generator every other roll uses); the tests pin its exact rule. */
static const unsigned int RAW_RAND[6] = { 0, 0x44B648u, 0, 0x46F3D8u, 0x471CF8u, 0x47CFD8u };
static const unsigned char ROLL_STUB[5] = { 0x85, 0xE4, 0xC3, 0x90, 0x90 };
typedef int (__cdecl *rand_t)(void);

static int __cdecl kind_roll(void) {
    rand_t raw = (rand_t)(uintptr_t)RAW_RAND[active_game];
    int draw, tries, v;
    for (draw = 0; draw < 2; ++draw) {
        v = 32000;
        for (tries = 0; tries < 16 && v >= 32000; ++tries) {
            v = raw();
        }
        if (v >= 32000 || v % 1000 != 0) {
            return 0;
        }
    }
    return 1;
}

/* Every register preserved; the answer is the zero flag (ZF = 1: yes). */
static __declspec(naked) void roll_stub(void) {
    __asm {
        pushad
        call kind_roll
        cmp eax, 1
        popad
        ret
    }
}

/* ---- Installing ------------------------------------------------------------ */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    unsigned char opcode;          /* 0xE9 jmp (entry/thunk) or 0xE8 call (call site) */
    void (*stub)(void);
};

#define MAX_SITES 3
static const struct site SITES[6][MAX_SITES] = {
    { { 0 } },
    { { VV1_FRAME_SITE, VV1_FRAME_STOCK, sizeof VV1_FRAME_STOCK, 0xE9, vv1_frame_stub },
      { VV1_FADE_SITE, VV1_FADE_STOCK, sizeof VV1_FADE_STOCK, 0xE8, vv1_fade_stub },
      { 0x4236EDu, ROLL_STUB, sizeof ROLL_STUB, 0xE9, roll_stub } },
    { { 0 } },
    { { 0x42E510u, LATER_STOCK, sizeof LATER_STOCK, 0xE9, vv3_stub },
      { 0x42FAD9u, ROLL_STUB, sizeof ROLL_STUB, 0xE9, roll_stub } },
    { { 0x44C640u, LATER_STOCK, sizeof LATER_STOCK, 0xE9, vv4_stub },
      { 0x489140u, ROLL_STUB, sizeof ROLL_STUB, 0xE9, roll_stub } },
    { { 0x44F380u, LATER_STOCK, sizeof LATER_STOCK, 0xE9, vv5_stub },
      { 0x4947B0u, ROLL_STUB, sizeof ROLL_STUB, 0xE9, roll_stub } },
};
static int install_state[6];       /* 0 = not tried, 1 = installed, -1 = refused */

static int site_is_stock(const struct site *s) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)s->va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, s->stock, (size_t)s->length) == 0;
}

static void site_bytes(const struct site *s, unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)s->stub
                                      - ((const unsigned char *)(uintptr_t)s->va + 5));
    int i;
    out[0] = s->opcode;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        out[i] = 0x90;
    }
}

/* All of a game's sites, or none: each is verified as stock and made
   writable before any is written, so a VirtualProtect failure at a later site
   leaves every site stock (the loader ignores the export's result). */
static int install(int game_id) {
    DWORD old[MAX_SITES];
    unsigned char bytes[16];
    int i, unlocked = 0;
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    if (active_game != 0) {
        return 0;                  /* one game per process */
    }
    for (i = 0; i < MAX_SITES; ++i) {
        if (SITES[game_id][i].va != 0 && !site_is_stock(&SITES[game_id][i])) {
            return 0;
        }
    }
    for (; unlocked < MAX_SITES && SITES[game_id][unlocked].va != 0; ++unlocked) {
        const struct site *s = &SITES[game_id][unlocked];
        if (!VirtualProtect((void *)(uintptr_t)s->va, (SIZE_T)s->length, PAGE_EXECUTE_READWRITE,
                            &old[unlocked])) {
            while (unlocked-- > 0) {
                const struct site *r = &SITES[game_id][unlocked];
                DWORD ignored;
                VirtualProtect((void *)(uintptr_t)r->va, (SIZE_T)r->length, old[unlocked], &ignored);
            }
            return 0;
        }
    }
    active_game = game_id;
    for (i = 0; i < unlocked; ++i) {
        const struct site *s = &SITES[game_id][i];
        unsigned char *at = (unsigned char *)(uintptr_t)s->va;
        DWORD ignored;
        site_bytes(s, bytes);
        memcpy(at, bytes, (size_t)s->length);
        VirtualProtect(at, (SIZE_T)s->length, old[i], &ignored);
        FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)s->length);
    }
    install_state[game_id] = 1;
    return 1;
}

/* Exported by ordinal = game number (see the .def file). */
int __stdcall VvfpGoldenMushroomVv1(void) { return install(1); }
int __stdcall VvfpGoldenMushroomVv3(void) { return install(3); }
int __stdcall VvfpGoldenMushroomVv4(void) { return install(4); }
int __stdcall VvfpGoldenMushroomVv5(void) { return install(5); }

#ifdef VVFP_TEST
/* For the test build only: site `index` of a game -- its address, stock
   bytes, the bytes the install writes and the stub it enters.  Returns the
   length, or 0 when there is no such site. */
int __stdcall VvfpGoldenMushroomProbeSite(int game_id, int index, unsigned int *va,
                                          unsigned char *stock, unsigned char *patched,
                                          unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5 || index < 0 || index >= MAX_SITES) {
        return 0;
    }
    s = &SITES[game_id][index];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

/* For the test build only: which game the stubs serve (as an install would
   set it), with the sprite not yet built. */
void __stdcall VvfpGoldenMushroomProbeSelect(int game_id) {
    active_game = game_id;
    sprite_state = 0;
    sprite = NULL;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
