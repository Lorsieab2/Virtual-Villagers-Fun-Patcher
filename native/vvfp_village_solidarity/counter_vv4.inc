/* The Tree of Life's Tech screen counter (the shared helper is in counter_vv3.inc). */

/* 0x43E87E: pop edi / pop esi / pop ebp / pop ebx / add esp, 0x18 / ret -- the Tech screen draw's (0x43E640)
   epilogue, after its bottom label's text is set (0x43E879). */
static const unsigned char SOL4_SITE[8] = { 0x5F, 0x5E, 0x5D, 0x5B, 0x83, 0xC4, 0x18, 0xC3 };
static const unsigned char SOL4_RENDERER[6] = { 0xA1, 0x28, 0xB9, 0x4C, 0x00, 0xC3 };      /* mov eax, [0x4CB928] */
static const unsigned char SOL4_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0x8B, 0x88, 0x48, 0x00 };
static const unsigned char SOL4_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x29, 0xFB, 0xFF, 0xFF };     /* jmp 0x409700 */
static const unsigned char SOL4_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };

/* The counter: the carved strip of the top frame left of the title's plank (the title, string 0x161, is centred
   at x 400, y 4), in the colour of the screen's bottom label (its global 0x4BEEC4). */
static const sol345_game SOL_VV4 = {
    0x43E87Eu, 8, SOL4_SITE,
    0x408130u, SOL4_RENDERER,
    0x44DA20u, SOL4_RESOURCES,
    0x409BD0u, SOL4_DRAW,
    0x402430u,
    0x402500u, SOL4_HEIGHT,
    0x4BEEC4u, 0,
    30, 270, 8,
    600,
};

static void __cdecl sol345_frame_vv4(void) {
    sol345_draw(&SOL_VV4);
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

static int sol_counter_install_vv4(void) {
    return sol345_install(&SOL_VV4, (void *)sol345_stub_vv4);
}
