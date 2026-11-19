/* The Tree of Life's Tech screen counter and its "?" button (the shared helper is in counter_vv3.inc). */

/* 0x43E87E: pop edi / pop esi / pop ebp / pop ebx / add esp, 0x18 / ret -- the Tech screen draw's (0x43E640)
   epilogue, after its bottom label's text is set (0x43E879). */
static const unsigned char SOL4_SITE[8] = { 0x5F, 0x5E, 0x5D, 0x5B, 0x83, 0xC4, 0x18, 0xC3 };
static const unsigned char SOL4_RENDERER[6] = { 0xA1, 0x28, 0xB9, 0x4C, 0x00, 0xC3 };      /* mov eax, [0x4CB928] */
static const unsigned char SOL4_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0x8B, 0x88, 0x48, 0x00 };
static const unsigned char SOL4_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x29, 0xFB, 0xFF, 0xFF };     /* jmp 0x409700 */
static const unsigned char SOL4_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };
/* 0x43E16B: mov dword ptr fs:[0], ecx -- the constructor's end, after its technologies' loop; the Origins
   companion's own splice (0x43E165) returns here too. */
static const unsigned char SOL4_MAKE[7] = { 0x64, 0x89, 0x0D, 0x00, 0x00, 0x00, 0x00 };

/* The counter: the carved strip of the top frame RIGHT of the title's plank (the title, string 0x161, is centred
   at x 400, y 4; left of it the Origins companion's Upgrades button sits in a patched build: seen live 2026-11-18),
   in the colour of the screen's bottom label (its global 0x4BEEC4, white on the dark frame). */
static const sol345_game SOL_VV4 = {
    0x43E87Eu, 8, SOL4_SITE,
    0x408130u, SOL4_RENDERER,
    0x44DA20u, SOL4_RESOURCES,
    0x409BD0u, SOL4_DRAW,
    0x402430u,
    0x402500u, SOL4_HEIGHT,
    0x4BEEC4u, 0,
    535, 785, 20,
    800, 600,
    0x470C5Cu, 0x44CCF0u, 0x44CB70u, 0xEB, 37, 40,
    0x401C20u, 0x401600u, 0x4BEEE0u, 0x48CCC4u, 0x401630u, 0x40C190u,
    0x419F00u, 0x401D40u, 0x419D50u, 0x448E10u, 0x4DA020u, 0x64,
    0x43E16Bu, 7, SOL4_MAKE,
    0x48EC70u, 0x43E9F0u,
};

static void __cdecl sol345_frame_vv4(void) {
    sol345_draw(&SOL_VV4);
}

static void __cdecl sol345_make_vv4(unsigned char *screen) {
    sol345_make_button(&SOL_VV4, screen);
}

static void __cdecl sol345_help_vv4(unsigned char *screen) {
    sol345_help(&SOL_VV4, screen);
}

static __declspec(naked) void sol345_stub_vv4(void) {
    __asm {
        pushad
        call sol345_frame_vv4
        popad
        pop edi
        pop esi
        pop ebp
        pop ebx
        add esp, 0x18
        ret
    }
}

/* At 0x43E16B: esi = the Tech screen being built (eax too). */
static __declspec(naked) void sol345_make_stub_vv4(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol345_make_vv4
        add esp, 4
        popad
        popfd
        /* mov dword ptr fs:[0], ecx -- the stock instruction, as its bytes (the SEH chain the constructor restores) */
        _emit 0x64
        _emit 0x89
        _emit 0x0D
        _emit 0x00
        _emit 0x00
        _emit 0x00
        _emit 0x00
        push 0x0043E172
        ret
    }
}

static __declspec(naked) void sol345_slot_vv4(void) {
    __asm {
        cmp dword ptr [esp + 4], 8
        jne stock
        cmp dword ptr [esp + 8], SOL345_BUTTON_ID
        jne stock
        pushad
        push ecx
        call sol345_help_vv4
        add esp, 4
        popad
        xor eax, eax
        ret 8
    stock:
        push 0x0043E9F0
        ret
    }
}

static int sol_counter_install_vv4(void) {
    return sol345_install(&SOL_VV4, (void *)sol345_stub_vv4, (void *)sol345_make_stub_vv4, (void *)sol345_slot_vv4);
}
