/* VVFP Work First -- Builders and Healers Work First (all five games).

   An addendum to Builders Fix Huts When Idle.  The owner: "in both low and
   high food situations, builders and healers still should prioritize fixing
   huts over other stuff for all 5 games" -- builders their building work,
   healers their healing and study, first, only while not every population
   hut is built -- and "make the work patches an addendum to the preexisting
   ones".

   HOW.  Every game's adult idle scheduler asks one work dispatcher to start
   a job for the villager ("dispatch job N; true if something started").  When
   the adult scheduler makes that call for a villager whose selected job is
   Building or Healing, while a population hut is unbuilt, this companion
   first asks the dispatcher for the villager's own job; if that starts
   something, the scheduler sees "started".  If it starts nothing -- no
   project, no hut to fix, no one sick, nothing to study -- the scheduler's own
   request runs exactly as it would have.  So builders and healers work first
   when there is work of theirs to do, and otherwise do whatever the stock
   game would have them do (farming, research, ...).  At low food in VV3-VV5
   the scheduler's farming attempt is one of these calls, so a builder or
   healer tries their own work before farming.

     game  dispatcher  displaced                      adult-scheduler returns         selected job             Bld Heal
     VV1   0x4472C0    mov eax,[esp+8]; test eax,eax  0x448355 0x448382               village+i*0x3D8+0x3D0     4   5
     VV2   0x45FBF0    the same                       0x461A08 0x461A35               village+i*0xE48C+0x7F8    5   3
     VV3   0x45AF00    mov eax,[esp+8]; sub esp,0xA0  0x45C23C 0x45C27A 0x45C28F      record+0xEC0              4   2
     VV4   0x4639B0    mov eax,[esp+4]; sub esp,0x98  0x4659D2 0x465A17 0x465A2A      [obj+0x1B88]+0x1C70       4   2
     VV5   0x46C540    sub esp,0x94                   0x46F291 0x46F2D6 0x46F2EA      [obj+0x1B88]+0x1C74       4   2

   VV1/VV2: thiscall(index, job), ret 8, ecx = village.  VV3: thiscall(record,
   job), ret 8.  VV4/VV5: thiscall(job), ret 4, ecx = the villager object.
   The result is in al.  Every other caller of a dispatcher is untouched.

   Loaded by "VVFP Fix Huts.dll" (VvfpFixHutsInstall, from a companion that
   runs every frame) by full path; The Secret City's hook is a stub in the
   fix-huts page that resolves VvfpWorkFirstFirst.  Not shipped: nothing is
   loaded, and every hook falls through to the stock code. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

/* ---- Population huts ------------------------------------------------------ */
/* The same tests the fix-huts companion makes (native/vvfp_fix_huts). */
static int vv1_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    return !(state[0x9FE8] == 1 && state[0x9FF0] == 1 && state[0x9FF8] == 1);
}

static int vv2_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    return !(state[0x2E818] == 1 && state[0x2E820] == 1 && state[0x2E828] == 1);
}

struct later_game {
    unsigned int complete_fn;      /* __stdcall(int) -> al, ecx = complete_obj */
    unsigned int complete_obj;
    int project_base;
};
static const struct later_game VV3 = { 0x4321F0u, 0x594620u, 0 };
static const struct later_game VV4 = { 0x438960u, 0x4D8BF8u, 19 };
static const struct later_game VV5 = { 0x43AE80u, 0x51E008u, 19 };

typedef unsigned char (__stdcall *complete_t)(int);

static int later_complete(const struct later_game *g, int hut) {
    complete_t fn = (complete_t)(uintptr_t)g->complete_fn;
    unsigned char r;
    unsigned int obj = g->complete_obj;
    int arg = g->project_base + hut;
    __asm {
        mov ecx, obj
        push arg
        call fn
        mov r, al
    }
    return r != 0;
}

static int later_huts_incomplete(const struct later_game *g) {
    int i;
    for (i = 0; i < 4; ++i) {
        if (!later_complete(g, i)) {
            return 1;
        }
    }
    return 0;
}

/* ---- The decision ---------------------------------------------------------- */
/* Counters a test can read from the running game.  Diagnostic only. */
struct vvfp_work_first_stats {
    int tried;          /* the villager's own job was tried first */
    int started;        /* ... and started something */
};
__declspec(dllexport) struct vvfp_work_first_stats VvfpWorkFirstStats = { 0 };

/* The villager's own job to try first, or -1: the stock request alone. */
static int own_first(int selected, int requested, int building, int healing, int huts_incomplete) {
    if ((selected != building && selected != healing) || selected == requested || !huts_incomplete) {
        return -1;
    }
    ++VvfpWorkFirstStats.tried;
    return selected;
}

static int is_one_of(unsigned int ret, const unsigned int *sites, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        if (ret == sites[i]) return 1;
    }
    return 0;
}

static const unsigned int VV1_CALLS[] = { 0x448355u, 0x448382u };
static const unsigned int VV2_CALLS[] = { 0x461A08u, 0x461A35u };
static const unsigned int VV3_CALLS[] = { 0x45C23Cu, 0x45C27Au, 0x45C28Fu };
static const unsigned int VV4_CALLS[] = { 0x4659D2u, 0x465A17u, 0x465A2Au };
static const unsigned int VV5_CALLS[] = { 0x46F291u, 0x46F2D6u, 0x46F2EAu };

static int __cdecl vv1_first(unsigned int ret, const unsigned char *village, unsigned int index, int job) {
    if (!is_one_of(ret, VV1_CALLS, 2)) return -1;
    return own_first(*(const int *)(village + index * 0x3D8u + 0x3D0u), job, 4, 5,
                     vv1_huts_incomplete(village));
}

static int __cdecl vv2_first(unsigned int ret, const unsigned char *village, unsigned int index, int job) {
    if (!is_one_of(ret, VV2_CALLS, 2)) return -1;
    return own_first(*(const int *)(village + index * 0xE48Cu + 0x7F8u), job, 5, 3,
                     vv2_huts_incomplete(village));
}

static int __cdecl vv4_first(unsigned int ret, const unsigned char *object, int job) {
    const unsigned char *record;
    if (!is_one_of(ret, VV4_CALLS, 3)) return -1;
    record = *(const unsigned char *const *)(object + 0x1B88u);
    return own_first(*(const int *)(record + 0x1C70u), job, 4, 2, later_huts_incomplete(&VV4));
}

static int __cdecl vv5_first(unsigned int ret, const unsigned char *object, int job) {
    const unsigned char *record;
    if (!is_one_of(ret, VV5_CALLS, 3)) return -1;
    record = *(const unsigned char *const *)(object + 0x1B88u);
    return own_first(*(const int *)(record + 0x1C74u), job, 4, 2, later_huts_incomplete(&VV5));
}

/* For The Secret City's executable-side stub at the dispatcher's entry: the
   scheduler's return address, the record and the requested job.  The job to
   try first, or -1.  A started job is counted by the stub's caller. */
__declspec(dllexport) int __cdecl VvfpWorkFirstFirst(int game_id, unsigned int ret,
                                                     const unsigned char *record, int job) {
    if (game_id != 3 || record == NULL) return -1;
    if (!is_one_of(ret, VV3_CALLS, 3)) return -1;
    return own_first(*(const int *)(record + 0xEC0u), job, 4, 2, later_huts_incomplete(&VV3));
}

/* ---- The stubs ------------------------------------------------------------ */
#define VV1_DISPATCHER 0x4472C0u
#define VV2_DISPATCHER 0x45FBF0u
#define VV4_DISPATCHER 0x4639B0u
#define VV5_DISPATCHER 0x46C540u
static const unsigned char VV1_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV2_STOCK[6] = { 0x8B, 0x44, 0x24, 0x08, 0x85, 0xC0 };
static const unsigned char VV4_STOCK[10] = { 0x8B, 0x44, 0x24, 0x04, 0x81, 0xEC, 0x98, 0x00, 0x00, 0x00 };
static const unsigned char VV5_STOCK[6] = { 0x81, 0xEC, 0x94, 0x00, 0x00, 0x00 };
static const unsigned int vv1_body = VV1_DISPATCHER + 6, vv2_body = VV2_DISPATCHER + 6;
static const unsigned int vv4_body = VV4_DISPATCHER + 10, vv5_body = VV5_DISPATCHER + 6;

/* The stock dispatcher, callable: the displaced bytes, then its body.  Also
   the target when the stock request should simply run. */
static __declspec(naked) void vv1_original(void) {
    __asm {
        mov eax, dword ptr [esp + 8]
        test eax, eax
        jmp dword ptr [vv1_body]
    }
}
static __declspec(naked) void vv2_original(void) {
    __asm {
        mov eax, dword ptr [esp + 8]
        test eax, eax
        jmp dword ptr [vv2_body]
    }
}
static __declspec(naked) void vv4_original(void) {
    __asm {
        mov eax, dword ptr [esp + 4]
        sub esp, 0x98
        jmp dword ptr [vv4_body]
    }
}
static __declspec(naked) void vv5_original(void) {
    __asm {
        sub esp, 0x94
        jmp dword ptr [vv5_body]
    }
}

/* VV1/VV2: [esp] = the caller, [esp+4] = index, [esp+8] = job; after
   pushad, +0x20.  Try the own job with the same ecx; al != 0 -> "started"
   (ret 8); else the stock request with the stack untouched. */
#define VV12_STUB(NAME)                                                       \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x28]      /* job */                  \
            __asm push dword ptr [esp + 0x28]      /* index */                \
            __asm push ecx                         /* village */              \
            __asm push dword ptr [esp + 0x2C]      /* the caller */           \
            __asm call NAME##_first                                          \
            __asm add esp, 16                                                \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm push ecx                                                   \
            __asm push eax                         /* the own job */          \
            __asm push dword ptr [esp + 0x0C]      /* index */                \
            __asm call NAME##_original                                       \
            __asm pop ecx                                                    \
            __asm test al, al                                                \
            __asm jz stock_request                                           \
            __asm inc dword ptr [VvfpWorkFirstStats + 4]                     \
            __asm ret 8                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

/* VV4/VV5: [esp] = the caller, [esp+4] = job; ecx = the villager object. */
#define LATER_STUB(NAME)                                                      \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x24]      /* job */                  \
            __asm push ecx                         /* the object */           \
            __asm push dword ptr [esp + 0x28]      /* the caller */           \
            __asm call NAME##_first                                          \
            __asm add esp, 12                                                \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm cmp eax, -1                                                \
            __asm je stock_request                                           \
            __asm push ecx                                                   \
            __asm push eax                         /* the own job */          \
            __asm call NAME##_original                                       \
            __asm pop ecx                                                    \
            __asm test al, al                                                \
            __asm jz stock_request                                           \
            __asm inc dword ptr [VvfpWorkFirstStats + 4]                     \
            __asm ret 4                                                      \
            __asm stock_request:                                             \
            __asm jmp NAME##_original                                        \
        }                                                                    \
    }

VV12_STUB(vv1)
VV12_STUB(vv2)
LATER_STUB(vv4)
LATER_STUB(vv5)

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

static const struct site SITES[6] = {
    { 0 },
    { VV1_DISPATCHER, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { VV2_DISPATCHER, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
    { 0 },
    { VV4_DISPATCHER, VV4_STOCK, sizeof VV4_STOCK, vv4_stub },
    { VV5_DISPATCHER, VV5_STOCK, sizeof VV5_STOCK, vv5_stub },
};
static int install_state[6];

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
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        out[i] = 0x90;
    }
}

/* Called by the fix-huts companion from its per-frame install.  Idempotent. */
__declspec(dllexport) int __stdcall VvfpWorkFirstInstall(int game_id) {
    const struct site *s;
    unsigned char bytes[16];
    unsigned char *at;
    DWORD old;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    s = &SITES[game_id];
    if (s->va == 0 || !site_is_stock(s)) {
        return 0;
    }
    at = (unsigned char *)(uintptr_t)s->va;
    site_bytes(s, bytes);
    if (!VirtualProtect(at, (SIZE_T)s->length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)s->length);
    VirtualProtect(at, (SIZE_T)s->length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)s->length);
    install_state[game_id] = 1;
    return 1;
}

/* For the test: the site, its stock bytes, what it becomes, the stub. */
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSite(int game_id, unsigned int *va,
                                                            unsigned char *stock,
                                                            unsigned char *patched,
                                                            unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
