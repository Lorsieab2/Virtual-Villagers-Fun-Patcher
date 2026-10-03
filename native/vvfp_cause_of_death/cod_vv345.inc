/* The Secret City, The Tree of Life and New Believers: the Deaths log.

   These three games keep a cause of death beside health and route every
   change of health through two sibling arbiters on the record's health
   block (ECX), both `ret 8` with (value, cause) on the stack:

       set  VV3 0x462670  VV4 0x46AF00  VV5 0x4758B0   health = value
       add  VV3 0x4626B0  VV4 0x46AF40  VV5 0x4758F0   health += value

   A result of 0 or less stores health 0 and the caller's cause; above 0 it
   clamps to 100 and stores cause -1 (alive).  So a death is exactly an
   arbiter call that takes health from above 0 to 0 or below -- read before
   the arbiter runs, which is why the detour sits on each one's first two
   instructions (`mov eax,[esp+4]; test eax,eax`, six bytes, no relative
   operand) rather than on the zeroing store, which the statistics row's
   Villagers Died hooks own (VV3 0x46267F/0x4626C6, VV4 0x46AF0F/0x46AF52,
   VV5 0x4758BF/0x475902).

   The cause is the caller's second argument, worded as the game's own grave
   dialog words it (string 0x2E6/0x317/0x314 + cause; -1 is the game's own
   "Unknown causes", which every island event passes).

   One exclusion: New Believers' Reanimate makes a stand-in corpse with
   set(0, -1) at 0x46FE66 on a freshly initialised record -- not a death. */

/* The health block's offset in the record, and the record's age. */
static const unsigned int V345_BLOCK[6] = { 0, 0, 0, 0xE6C, 0x1C34, 0x1C34 };
static const unsigned int V345_AGE[6] = { 0, 0, 0, 0xDC4, 0x1B8C, 0x1B8C };

/* The two arbiters per game. */
static const unsigned int V345_SET[6] = { 0, 0, 0, 0x462670u, 0x46AF00u, 0x4758B0u };
static const unsigned int V345_ADD[6] = { 0, 0, 0, 0x4626B0u, 0x46AF40u, 0x4758F0u };

/* VV5's Reanimate stand-in: the return address of its set(0, -1). */
#define VV5_STAND_IN_RETURN 0x46FE6Bu

/* Both arbiters open with the same six bytes in all three games. */
static const unsigned char V345_SET_STOCK[6] = { 0x8B, 0x44, 0x24, 0x04, 0x85, 0xC0 };
/* The adds differ: VV3 loads health into edx (`mov eax,[esp+4];
   mov edx,[ecx+0xc]`), VV4 and VV5 add in place (`mov eax,[esp+4];
   add [ecx+0xc],eax`).  Seven bytes each. */
static const unsigned char V3_ADD_STOCK[7] = { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0x51, 0x0C };
static const unsigned char V45_ADD_STOCK[7] = { 0x8B, 0x44, 0x24, 0x04, 0x01, 0x41, 0x0C };

static void __cdecl v345_arbiter(int is_add, unsigned char *block, const unsigned int *frame) {
    int old_health = *(const int *)(block + 0xC);
    int value = (int)frame[1];
    int cause = (int)frame[2];
    int result = is_add ? old_health + value : value;
    unsigned char *record;
    if (old_health <= 0 || result > 0) {
        return;                       /* not a death */
    }
    if (g_game == 5 && frame[0] == VV5_STAND_IN_RETURN) {
        return;                       /* Reanimate's stand-in corpse */
    }
    record = block - V345_BLOCK[g_game];
    cod_log_death(record, *(const int *)(record + V345_AGE[g_game]), cod_cause_words(cause));
}

/* Each stub: the arbiter's own frame is at esp on entry ([esp] = return,
   [esp+4] = value, [esp+8] = cause).  pushad saves everything, the call
   sees the frame at esp+32, then the displaced bytes run and the arbiter
   continues where they ended. */
static unsigned int v345_set_resume, v345_add_resume;

static __declspec(naked) void v345_set_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 32]
        push eax
        push ecx
        push 0
        call v345_arbiter
        add esp, 12
        popad
        mov eax, dword ptr [esp + 4]
        test eax, eax
        jmp dword ptr [v345_set_resume]
    }
}

/* VV3: `mov eax,[esp+4]; mov edx,[ecx+0xc]`, seven bytes. */
static __declspec(naked) void v3_add_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 32]
        push eax
        push ecx
        push 1
        call v345_arbiter
        add esp, 12
        popad
        mov eax, dword ptr [esp + 4]
        mov edx, dword ptr [ecx + 0xC]
        jmp dword ptr [v345_add_resume]
    }
}

/* VV4/VV5: `mov eax,[esp+4]; add [ecx+0xc],eax`, seven bytes. */
static __declspec(naked) void v45_add_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 32]
        push eax
        push ecx
        push 1
        call v345_arbiter
        add esp, 12
        popad
        mov eax, dword ptr [esp + 4]
        add dword ptr [ecx + 0xC], eax
        jmp dword ptr [v345_add_resume]
    }
}

static int v345_install(void) {
    struct cod_site set_site, add_site;
    set_site.va = V345_SET[g_game];
    set_site.stock = V345_SET_STOCK;
    set_site.length = 6;
    set_site.stub = v345_set_stub;
    add_site.va = V345_ADD[g_game];
    if (g_game == 3) {
        add_site.stock = V3_ADD_STOCK;
        add_site.length = 7;
        add_site.stub = v3_add_stub;
    } else {
        add_site.stock = V45_ADD_STOCK;
        add_site.length = 7;
        add_site.stub = v45_add_stub;
    }
    if (!cod_site_is_stock(&set_site) || !cod_site_is_stock(&add_site)) {
        return 0;                     /* another build, or already taken: nothing */
    }
    v345_set_resume = set_site.va + (unsigned int)set_site.length;
    v345_add_resume = add_site.va + (unsigned int)add_site.length;
    return cod_install_site(&set_site) && cod_install_site(&add_site);
}
