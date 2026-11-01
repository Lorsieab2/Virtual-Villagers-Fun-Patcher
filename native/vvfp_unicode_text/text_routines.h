/* The game's text routines the companion detours, per game (found by disassembly of the stock
   executables; tests/test_unicode_utf8.py checks every address and stock byte against them).

   Calling conventions (all thiscall; ecx = this):
     width     (font; const char *s, float scale) ret 8 -> int        widest line, less one spacing
     draw      (ctx; s, x, y, ARGB colour, font or 0 = ctx+0x5C) ret 0x14
     linefit   (font; src, char *out, maxCount, maxWidth, bool *paragraph, bool newlineAsSpace,
                float scale) ret 0x1C -> where the next line starts            (VV2-VV5)
     nbyte     (ctx; s, maxBytes, x, y, bool measureOnly, ARGB, font) ret 0x1C -> advance  (VV3-VV5)
     justify   (holder [+0 = ctx]; text, x, y, width, ARGB, font, bool measureOnly) ret 0x1C -> height
                                                                                   (VV3-VV5)
     ctldraw   (text control) ret: draws a label or text box; an editable one first cuts its text
               one byte at a time while wider than its box (flag +0x24)
     seteditable (box; bool editable, limit) ret 8: the box's byte limit (+0x28), capped at 1200
     settext   (box; const char *) ret 4
     gettext   (wrapper [+0x10 = box]; char *buf, size) ret 8: strncpy, buf[size-1] = 0
     chartype  inside the text box's character handler (box; message, p1, p2) ret 0xC, at its
               `mov eax,[esp+4]; cmp eax,6` (focus already checked); message 5 = a character p2
     backspace inside it: `mov edx,[ecx+0x30]; mov byte [edx+eax-1],0` (eax = length > 0)
   Every site's first bytes are the same in all five games (STOCK_*). */
#ifndef VVFP_TEXT_ROUTINES_H
#define VVFP_TEXT_ROUTINES_H

typedef struct vt_game {
    unsigned int width, draw, linefit, nbyte, justify, ctldraw, seteditable, settext, gettext;
    unsigned int chartype, handler, backspace, line_height, default_colour;
} vt_game;

static const vt_game VT_GAMES[6] = {
    {0},
    {0x402160u, 0x409160u, 0, 0, 0, 0x40BFE0u, 0x40B7B0u, 0x40B860u, 0x40BB70u,
     0x40BE49u, 0x40BE30u, 0x40BE97u, 0x402100u, 0x486118u},                         /* vv1 */
    {0x4021F0u, 0x409360u, 0x4022B0u, 0, 0, 0x40C9C0u, 0x40C190u, 0x40C240u, 0x40C550u,
     0x40C829u, 0x40C810u, 0x40C877u, 0x402190u, 0x495118u},                         /* vv2 */
    {0x402230u, 0x409CD0u, 0x4022F0u, 0x409AD0u, 0x40A0C0u, 0x40D650u, 0x40CE20u, 0x40CED0u, 0x40D1E0u,
     0x40D4B9u, 0x40D4A0u, 0x40D507u, 0x4021C0u, 0x4A4238u},                         /* vv3 */
    {0x402430u, 0x409700u, 0x402550u, 0x4094F0u, 0x409C30u, 0x40CE20u, 0x40D050u, 0x40D110u, 0x40D420u,
     0x40D767u, 0x40D750u, 0x40D7B8u, 0x402500u, 0x4B827Cu},                         /* vv4 */
    {0x4023E0u, 0x409930u, 0x402500u, 0x409720u, 0x409F00u, 0x40D310u, 0x40D540u, 0x40D600u, 0x40D910u,
     0x40DC57u, 0x40DC40u, 0x40DCA8u, 0x4024B0u, 0x4C629Cu},                         /* vv5 */
};

static const unsigned char STOCK_WIDTH[7] = {0x83, 0xEC, 0x10, 0x55, 0x8B, 0x69, 0x04};
static const unsigned char STOCK_DRAW[7] = {0x83, 0xEC, 0x44, 0x8B, 0x44, 0x24, 0x58};
static const unsigned char STOCK_LINEFIT[5] = {0x83, 0xEC, 0x18, 0x53, 0x55};
static const unsigned char STOCK_NBYTE[7] = {0x83, 0xEC, 0x4C, 0x8B, 0x44, 0x24, 0x68};
static const unsigned char STOCK_JUSTIFY[6] = {0x81, 0xEC, 0xDC, 0x04, 0x00, 0x00};
static const unsigned char STOCK_CTLDRAW[6] = {0x83, 0xEC, 0x34, 0x56, 0x8B, 0xF1};
static const unsigned char STOCK_SETEDITABLE[5] = {0x53, 0x8A, 0x5C, 0x24, 0x08};
static const unsigned char STOCK_SETTEXT[6] = {0x56, 0x8B, 0xF1, 0x8B, 0x46, 0x30};
static const unsigned char STOCK_GETTEXT[6] = {0x8B, 0x41, 0x10, 0x8B, 0x48, 0x30};
static const unsigned char STOCK_CHARTYPE[7] = {0x8B, 0x44, 0x24, 0x04, 0x83, 0xF8, 0x06};
static const unsigned char STOCK_BACKSPACE[8] = {0x8B, 0x51, 0x30, 0xC6, 0x44, 0x02, 0xFF, 0x00};

#endif
