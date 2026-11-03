/* The facts native/vvfp_copy_paste needs from each stock executable.  Every address is proved against the
   stock executables by tests/test_copy_paste.py (TheStockCode). */
#ifndef VVFP_COPY_PASTE_TABLES_H
#define VVFP_COPY_PASTE_TABLES_H

/* Each game:
     key_site   the event pump's SDL_KEYDOWN case, its first two instructions (10 bytes):
                mov ecx, [esp + sym]; cmp ecx, imm32 -- moved into the hook, which runs them and goes on
                at key_site + 10 when the key is not ours;
     sym        the stack offset of the event's keysym.sym at key_site (keysym.mod is at sym + 4, the
                event's repeat byte at sym - 7);
     cont       where the pump goes on with the next event (the end of every case);
     manager    the global that holds the game's event manager: [manager] -> {list} -> {head node};
                node {listener, flags (2 = keyboard), last (the dispatch stops after it), next};
     handler    the text box's keyboard handler, the box class's third virtual function:
                thiscall(box; type, 0, character), ret 0xC -- type 5 is a typed character. */
typedef struct cp_game {
    unsigned int key_site; unsigned char key_bytes[10]; int sym; unsigned int cmp_imm;
    unsigned int cont, manager, handler;
} cp_game;

static const cp_game CP_GAMES[6] = {
    {0},
    {0x4039D6u, {0x8B, 0x4C, 0x24, 0x3C, 0x81, 0xF9, 0x41, 0x00, 0x00, 0x40}, 0x3C, 0x40000041u,
     0x403C73u, 0x48AEC8u, 0x40BE30u},                                                        /* vv1 */
    {0x403C66u, {0x8B, 0x4C, 0x24, 0x3C, 0x81, 0xF9, 0x41, 0x00, 0x00, 0x40}, 0x3C, 0x40000041u,
     0x403F03u, 0x4997A8u, 0x40C810u},                                                        /* vv2 */
    {0x404286u, {0x8B, 0x4C, 0x24, 0x3C, 0x81, 0xF9, 0x41, 0x00, 0x00, 0x40}, 0x3C, 0x40000041u,
     0x404523u, 0x4B3088u, 0x40D4A0u},                                                        /* vv3 */
    {0x4048A6u, {0x8B, 0x4C, 0x24, 0x38, 0x81, 0xF9, 0x3A, 0x00, 0x00, 0x40}, 0x38, 0x4000003Au,
     0x404B07u, 0x4CB508u, 0x40D750u},                                                        /* vv4 */
    {0x404836u, {0x8B, 0x4C, 0x24, 0x38, 0x81, 0xF9, 0x3A, 0x00, 0x00, 0x40}, 0x38, 0x4000003Au,
     0x404A97u, 0x4DACCCu, 0x40DC40u},                                                        /* vv5 */
};

/* The text box (every game the same): */
#define CP_BOX_PARENT   0x1C    /* -> its screen; byte +8: the screen takes input */
#define CP_BOX_FOCUSED  0x25    /* byte: has typing focus */
#define CP_BOX_LIMIT    0x28    /* int: most bytes it holds */
#define CP_BOX_DIGITS   0x2D    /* byte: digits only (and '-' first) */
#define CP_BOX_OTHER    0x2F    /* byte: length kept at +0x34 instead (never set by the stock code) */
#define CP_BOX_TEXT     0x30    /* char *: the text, NUL-terminated */

#endif
