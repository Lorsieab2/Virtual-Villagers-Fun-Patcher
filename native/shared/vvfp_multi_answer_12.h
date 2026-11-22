/* Island-event questions with 3 to 7 answers in A New Home's and The Lost Children's own two-choice popup (the villager
   encounters' dialog 0x41A460 / the family-A dialog 0x422380).  Shared by "VVFP More Island Events.dll" and "VVFP Story
   Upgrades.dll"; each includes it once and keeps its own one popup.  The later three games: vvfp_multi_answer.h.

   THE BUTTONS are made exactly as the constructor makes its two: operator new 0x14 bytes (0x44AF03 / 0x467F83), the
   button (0x4019B0 / 0x4019D0) with the answers' own picture ("0x4595C4" / "0x47677C", the constructor's), a new id
   (5 to 9: the constructor's are 2, 3 and OK 4, at +0x54 / +0x58 / +0x5C; docs/event-collection/button-probe.md) and the dialog as its listener, the label
   (0x4015B0 / 0x4015D0) in the constructor's colours (black, then grey 0x55 twice).  They are attached and taken off
   with the dialog's own add / remove (0x40AB80 / 0x40ABC0, 0x40B560 / 0x40B5A0), as its click handler swaps its two.
   All the answers stand one above the other in ONE column, centred, 1.5 button heights apart as the constructor
   spaces its two (its first at the height - 3.5 h, its second at - 2 h, OK at - h - 20 below them) -- 1.25 heights
   apart with 5 to 7 answers.

   WHEN.  These dialogs are built in one call that also places their buttons, and neither companion has a site after
   it; so the extra buttons are made when the dialog is first DRAWN (its +0x30, 0x4187E0 / 0x41F430), and at every
   draw after that they follow the client's state: made and laid out while its answers are asked, taken off and
   deleted while they are not (a draw is never inside a button's own click, so deleting there is safe).  The dialog's
   virtual table becomes a copy of the game's (0x459578 / 0x476714) with that draw, its click handler (+0x0C: ids 5
   to 9 answered as the game answers its two -- the sound, the answers off, OK on, the choice field +0x509C / +0x50A4
   = 3 to 7, the client's resolve, the result shown +0x50 -- every other click to the game's 0x41A3D0 / 0x4222F0, our
   buttons taken off first when it is one of its answers) and its keyboard handler (+0x08; the game's 0x41F620 /
   0x401180 takes no key): Enter / Esc is OK while OK is shown, as the games' own message boxes (0x415400 / 0x41AB80),
   and the keys 1 to N the answers while they are asked.

   ROOM.  The popup is sized once by its constructor from its text: the client pads the question with blank lines
   worth the extra buttons (mb_room_lines: as far above the game's first answer as the first of all stands, the button's height measured on a button made and
   deleted at once, in the font's lines -- 0x402100 / 0x402190 on the dialog's font +0x50AC / +0x50B4).

   With two answers nothing here is used: the dialog is the game's, untouched. */

#ifndef VVFP_MULTI_ANSWER_12_H
#define VVFP_MULTI_ANSWER_12_H

#define MB_MAX_ANSWERS 7
#define MB_EXTRA (MB_MAX_ANSWERS - 2)
#define MB_LABEL_BYTES 128
#define MB_FIRST_ID 5

#define MB_NOT_OURS 0
#define MB_OK_UP 1          /* a page with OK, the answers off */
#define MB_ASKING 2         /* the answers are shown, none taken */
#define MB_ANSWERED 3       /* an answer was taken: its pages with OK */

typedef struct {
    int game;
    unsigned int dialog_vtable, click, draw;
    unsigned int alloc, button, image, label;
    unsigned int attach, remove;
    unsigned int button_a, button_b, ok, choice;
    unsigned int sound_field, sound, sound_id;
    unsigned int font_field, line_height;
} mb_game;

static const mb_game MB_GAMES[2] = {
    { 1, 0x459578u, 0x41A3D0u, 0x4187E0u, 0x44AF03u, 0x4019B0u, 0x4595C4u, 0x4015B0u, 0x40AB80u, 0x40ABC0u,
      0x50BCu, 0x50C0u, 0x50C4u, 0x509Cu, 0x50A0u, 0x431470u, 0x44u, 0x50ACu, 0x402100u },
    { 2, 0x476714u, 0x4222F0u, 0x41F430u, 0x467F83u, 0x4019D0u, 0x47677Cu, 0x4015D0u, 0x40B560u, 0x40B5A0u,
      0x50C8u, 0x50CCu, 0x50D0u, 0x50A4u, 0x50A8u, 0x43F010u, 0x4Au, 0x50B4u, 0x402190u },
};

typedef struct {
    /* The popup's state (MB_*), the answers the question on screen has (2..7) and their words. */
    int (*state)(void *dialog);
    int (*answers)(void *dialog);
    void (*label)(void *dialog, int k, char *out, int cap);
    /* The answer's resolve, after the choice field is set (3 to 7) and the answers are off and OK on. */
    void (*resolve)(void *dialog);
    /* Optional (NULL: never): 1 when the answer just given shows its page in a popup of its own, so this one closes
       at once, as OK would close it (five or more answers: the Isola Grand Event Collection's G1). */
    int (*closes)(void *dialog);
} mb_client;

typedef struct {
    const mb_game *g;
    const mb_client *c;
    void *dialog;
    void *buttons[MB_EXTRA];
    int made;                       /* our buttons made (and attached) for `made_for` answers */
    char words[MB_EXTRA][MB_LABEL_BYTES];
    int room_px;                    /* the room the question was padded with for the extra buttons (Scrolling Popups) */
    unsigned int dvt[24];
} mb_popup;

static mb_popup g_mb;
static int g_mb_room_px;            /* mb_room_lines' last room, in pixels: the next mb_attach keeps it */

typedef void *(__cdecl *mb_new_fn)(unsigned int size);
typedef void (__fastcall *mb_button_fn)(void *self, void *unused, int id, const char *image, int a, int b,
                                        void *listener, int c);
typedef void (__fastcall *mb_label_fn)(void *self, void *unused, const char *text, unsigned int c1, unsigned int c2,
                                       unsigned int c3, int d);
typedef int (__fastcall *mb_vint_fn)(void *self, void *unused);
typedef void (__fastcall *mb_v1_fn)(void *self, void *unused, int a);
typedef void (__fastcall *mb_v2_fn)(void *self, void *unused, int a, int b);
typedef int (__fastcall *mb_lines_fn)(void *font, void *unused, const char *text);
typedef char (__fastcall *mb_message_fn)(void *self, void *unused, int message, int id);
typedef void (__fastcall *mb_draw_fn)(void *self, void *unused);

static const mb_game *mb_game_of(int game) {
    return game == 1 || game == 2 ? &MB_GAMES[game - 1] : NULL;
}

static int mb_vcall(void *object, unsigned int slot) {
    return ((mb_vint_fn)(*(void ***)object)[slot / 4])(object, NULL);
}

static void *mb_field(void *dialog, unsigned int offset) {
    return *(void **)((unsigned char *)dialog + offset);
}

static void mb_call1(unsigned int va, void *self, void *arg) {
    ((mb_v1_fn)(uintptr_t)va)(self, NULL, (int)(uintptr_t)arg);
}

/* One answer button made as the constructor makes its two; NULL when it could not be. */
static void *mb_make(const mb_game *g, void *dialog, int id, const char *text) {
    void *b = ((mb_new_fn)(uintptr_t)g->alloc)(0x14);
    if (b == NULL) {
        return NULL;
    }
    ((mb_button_fn)(uintptr_t)g->button)(b, NULL, id, (const char *)(uintptr_t)g->image, 0, 0, dialog, 0);
    ((mb_label_fn)(uintptr_t)g->label)(b, NULL, text, 0xFF000000u, 0xFF555555u, 0xFF555555u, 0);
    return b;
}

static void mb_delete(void *b) {
    __try {
        ((mb_v1_fn)(*(void ***)b)[0])(b, NULL, 1);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The distance between two answers' tops: 1.5 button heights (the constructor's) up to four answers, 1.25 from five. */
static int mb_step(int h, int count) {
    return count > 4 ? h + h / 4 : h + h / 2;
}

/* The room `count` answers take beyond the game's two, in pixels: 1.5 button heights for each answer past two, up to
   four; from five, how far above the game's own first (the height - 3.5 h) the first answer stands. */
static int mb_room_px(int h, int count) {
    if (count <= 2) {
        return 0;
    }
    if (count <= 4) {
        return (count - 2) * 3 * h / 2;
    }
    return (count - 1) * mb_step(h, count) - (h + h / 2);
}

/* The text lines `count` answers need beyond the game's two (0 for two), for the client's padding of the question. */
static int mb_room_lines(int game, void *dialog, int count) {
    const mb_game *g = mb_game_of(game);
    int lines = 0;
    if (g == NULL || dialog == NULL || count <= 2) {
        return 0;
    }
    __try {
        void *b = mb_make(g, dialog, MB_FIRST_ID, "");
        void **font = (void **)mb_field(dialog, g->font_field);
        int h = b != NULL ? mb_vcall(b, 0x10) : 0;
        int line = font != NULL && *font != NULL ? ((mb_lines_fn)(uintptr_t)g->line_height)(*font, NULL, NULL) : 0;
        int room = mb_room_px(h, count);
        if (b != NULL) {
            mb_delete(b);
        }
        lines = line > 0 ? (room + line - 1) / line : 0;
        g_mb_room_px = lines * line;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        lines = 0;
    }
    return lines > 0 && lines < 64 ? lines : 0;
}

/* Answer `k` of the dialog (0 the first): the game's two, then ours. */
static void *mb_button(void *dialog, int k) {
    if (k < 2) {
        return mb_field(dialog, k == 0 ? g_mb.g->button_a : g_mb.g->button_b);
    }
    return k - 2 < MB_EXTRA ? g_mb.buttons[k - 2] : NULL;
}

/* Our buttons taken off the dialog (and deleted when `free_them`: never inside a click). */
static void mb_take_off(void *dialog, int free_them) {
    int k;
    for (k = 0; k < MB_EXTRA; ++k) {
        void *b = g_mb.buttons[k];
        if (b == NULL) {
            continue;
        }
        if (g_mb.made) {
            __try {
                mb_call1(g_mb.g->remove, dialog, b);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        if (free_them) {
            g_mb.buttons[k] = NULL;
            mb_delete(b);
        }
    }
    g_mb.made = 0;
}

/* Every answer one above the other at the panel's bottom, centred, mb_step apart. */
static void mb_layout(void *dialog, int count) {
    unsigned char *d = (unsigned char *)dialog;
    int width = *(int *)(d + 0x1C) - *(int *)(d + 0x14);
    int height = *(int *)(d + 0x20) - *(int *)(d + 0x18);
    int k;
    for (k = 0; k < count; ++k) {
        void *b = mb_button(dialog, k);
        int bw, bh;
        if (b == NULL) {
            continue;
        }
        bw = mb_vcall(b, 0x0C);
        bh = mb_vcall(b, 0x10);
        ((mb_v2_fn)(*(void ***)b)[1])(b, NULL, width / 2 - bw / 2, height - 2 * bh - (count - 1 - k) * mb_step(bh, count));
    }
}

/* The dialog's draw (+0x30): our buttons follow the client's state, then the game draws. */
static void __fastcall mb_draw(void *dialog, void *unused) {
    (void)unused;
    __try {
        if (dialog == g_mb.dialog && g_mb.c != NULL) {
            int asking = g_mb.c->state(dialog) == MB_ASKING;
            int count = asking ? g_mb.c->answers(dialog) : 2;
            int k, same = 1;
            char words[MB_EXTRA][MB_LABEL_BYTES];
            for (k = 0; k + 2 < count && k < MB_EXTRA; ++k) {
                g_mb.c->label(dialog, k + 2, words[k], MB_LABEL_BYTES);
                same = same && g_mb.buttons[k] != NULL && lstrcmpA(words[k], g_mb.words[k]) == 0;
            }
            if (count <= 2 || !same || (g_mb.made && g_mb.made != count)) {
                for (k = 0; k < MB_EXTRA && g_mb.buttons[k] == NULL; ++k) {
                }
                if (k < MB_EXTRA) {
                    mb_take_off(dialog, 1);
                }
            }
            if (count > 2 && !g_mb.made) {
                for (k = 0; k + 2 < count && k < MB_EXTRA; ++k) {
                    if (g_mb.buttons[k] == NULL) {
                        g_mb.buttons[k] = mb_make(g_mb.g, dialog, MB_FIRST_ID + k, words[k]);
                        lstrcpynA(g_mb.words[k], words[k], MB_LABEL_BYTES);
                    }
                    if (g_mb.buttons[k] != NULL) {
                        mb_call1(g_mb.g->attach, dialog, g_mb.buttons[k]);
                    }
                }
                g_mb.made = count;
                mb_layout(dialog, count);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    ((mb_draw_fn)(uintptr_t)g_mb.g->draw)(dialog, NULL);
}

/* The dialog's click handler (+0x0C): ids 5 to 9 are our answers, the rest the game's. */
static char __fastcall mb_message(void *dialog, void *unused, int message, int id) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused;
    __try {
        int state = dialog == g_mb.dialog && g_mb.c != NULL ? g_mb.c->state(dialog) : MB_NOT_OURS;
        if (message == 8 && state == MB_ASKING && id >= MB_FIRST_ID && id < MB_FIRST_ID + g_mb.made - 2) {
            const mb_game *g = g_mb.g;
            void *sound = mb_field(dialog, g->sound_field);
            if (sound != NULL) {
                mb_call1(g->sound, sound, (void *)(uintptr_t)g->sound_id);
            }
            mb_take_off(dialog, 0);
            mb_call1(g->remove, dialog, mb_field(dialog, g->button_a));
            mb_call1(g->remove, dialog, mb_field(dialog, g->button_b));
            mb_call1(g->attach, dialog, mb_field(dialog, g->ok));
            *(int *)(d + g->choice) = 3 + (id - MB_FIRST_ID);
            g_mb.c->resolve(dialog);
            d[0x50] = 1;
            if (g_mb.c->closes != NULL && g_mb.c->closes(dialog)) {
                return mb_message(dialog, NULL, 8, *(int *)(d + 0x5C));   /* a popup of its own comes: OK now */
            }
            return 1;
        }
        if (message == 8 && state == MB_ASKING && g_mb.made
            && (id == *(int *)(d + 0x54) || id == *(int *)(d + 0x58))) {
            mb_take_off(dialog, 0);                    /* the game answers its own: ours go off first */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    {
        int own = message == 8 && dialog == g_mb.dialog && g_mb.c != NULL && g_mb.c->state(dialog) == MB_ASKING
                  && (id == *(int *)(d + 0x54) || id == *(int *)(d + 0x58));
        char handled = ((mb_message_fn)(uintptr_t)g_mb.g->click)(dialog, NULL, message, id);
        __try {
            if (own && g_mb.c->closes != NULL && g_mb.c->closes(dialog)) {
                handled = mb_message(dialog, NULL, 8, *(int *)(d + 0x5C));   /* a popup of its own comes: OK now */
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return handled;
    }
}

/* The dialog's keyboard handler (+0x08): Enter (0x3EB) or Esc (0x3E8) is OK while OK is shown; the typed keys 1 to N
   (type 5) the answers while they are asked.  1 when the key was used. */
static char __fastcall mb_key(void *dialog, void *unused, int type, int code, int raw) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused; (void)raw;
    __try {
        int state = dialog == g_mb.dialog && g_mb.c != NULL ? g_mb.c->state(dialog) : MB_NOT_OURS;
        if (state == MB_NOT_OURS) {
            return 0;
        }
        if (type == 6 && (code == 0x3EB || code == 0x3E8) && state != MB_ASKING) {
            mb_message(dialog, NULL, 8, *(int *)(d + 0x5C));
            return 1;
        }
        if (type == 5 && state == MB_ASKING && code >= '1' && code < '1' + g_mb.c->answers(dialog)) {
            int k = code - '1';
            mb_message(dialog, NULL, 8, k == 0 ? *(int *)(d + 0x54) : k == 1 ? *(int *)(d + 0x58) : MB_FIRST_ID + k - 2);
            return 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

/* The dialog being built gets our virtual table (the client's setup, inside the constructor: its table is set by
   then).  Leftover buttons of an earlier popup are deleted (none is on screen now).  0 when not done. */
static int mb_attach(int game, const mb_client *client, void *dialog) {
    const mb_game *g = mb_game_of(game);
    unsigned char *d = (unsigned char *)dialog;
    int k;
    for (k = 0; k < MB_EXTRA; ++k) {
        if (g_mb.buttons[k] != NULL) {
            mb_delete(g_mb.buttons[k]);
            g_mb.buttons[k] = NULL;
        }
    }
    g_mb.made = 0;
    g_mb.dialog = NULL;
    if (g == NULL || client == NULL || dialog == NULL || *(unsigned int *)d != g->dialog_vtable) {
        return 0;
    }
    g_mb.g = g;
    g_mb.c = client;
    g_mb.dialog = dialog;
    g_mb.room_px = g_mb_room_px;
    g_mb_room_px = 0;
    memcpy(g_mb.dvt, (const void *)(uintptr_t)(g->dialog_vtable - 4u), sizeof g_mb.dvt);
    g_mb.dvt[1 + 2] = (unsigned int)(uintptr_t)mb_key;
    g_mb.dvt[1 + 3] = (unsigned int)(uintptr_t)mb_message;
    g_mb.dvt[1 + 12] = (unsigned int)(uintptr_t)mb_draw;
    *(unsigned int **)d = &g_mb.dvt[1];
    return 1;
}

/* For Scrolling Popups (its island-event dialogs are known by their virtual table): the game's own table when
   popup is the dialog with our copy, and in *room the room its question was padded with; 0 for any other. */
static unsigned int mb_game_vtable(const void *popup, int *room) {
    unsigned int vt = 0;
    __try {
        if (popup != NULL && popup == g_mb.dialog && g_mb.g != NULL
            && *(const unsigned int *)popup == (unsigned int)(uintptr_t)&g_mb.dvt[1]) {
            vt = g_mb.g->dialog_vtable;
            if (room != NULL) {
                *room = g_mb.room_px > 0 && g_mb.room_px < 2048 ? g_mb.room_px : 0;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        vt = 0;
    }
    return vt;
}

/* Another dialog is built on the same stack: forget this one (its buttons are deleted at the next mb_attach). */
static void mb_op_forget(void);

static void mb_forget(void *dialog) {
    if (dialog != NULL && dialog == g_mb.dialog) {
        g_mb.dialog = NULL;
        g_mb.made = 0;
        mb_op_forget();
    }
}

/* ---- ONE popup per island event (native/shared/one_popup.h) ---------------------------------------------------

   With Scrolling Popups, a new island event runs whole in this dialog: its text in the question field (+0x74 /
   +0x7C; the result field and its flag +0x50 are never used), its choices drawn by Scrolling Popups after the text
   (VvfpOnePopupRows / VvfpOnePopupPick), the game's two answers always off, OK on only while no choice is asked.
   A choice (a row, or the keys 1 to 7) gives the client's pick, whose text replaces the shown one; OK gives the
   client's ok, which keeps the popup when it shows another text, else the game's OK closes it.  The buttons follow
   the client at every draw (as above: a draw is never inside a button's own click) and right after a pick or OK. */
#include "one_popup.h"

typedef struct {
    int (*rows)(void *dialog, op_rows *out);    /* the choices shown now (0: OK), their words */
    int (*pick)(void *dialog, int k);           /* choice k: its text in place; 1 when taken */
    int (*ok)(void *dialog);                    /* OK: 1 when another text replaced the shown one (the popup stays) */
} mb_op_client;

static const mb_op_client *g_mb_op;            /* non-NULL: g_mb.dialog is a one-popup event */
static int g_mb_ab_on;                          /* the game's two answers still attached */
static int g_mb_ok_on;                          /* OK attached */
static int g_mb_ok_made;                        /* the constructor is done (the dialog drawn once): OK exists */

static void mb_op_forget(void) {
    g_mb_op = NULL;
}

/* The choices shown now (and their words when `out`), 0 when none or not ours. */
static int mb_op_count(void *dialog, op_rows *out) {
    static op_rows scratch;
    op_rows *r = out != NULL ? out : &scratch;
    if (g_mb_op == NULL || dialog == NULL || dialog != g_mb.dialog) {
        return 0;
    }
    r->rows = 0;
    if (!g_mb_op->rows(dialog, r)) {
        return 0;
    }
    return r->rows > 0 && r->rows <= OP_MAX_ROWS ? r->rows : 0;
}

/* The game's buttons as the client's state says: its two answers off, OK on only while nothing is asked. */
static void mb_op_sync(void *dialog) {
    const mb_game *g = g_mb.g;
    int asking = mb_op_count(dialog, NULL) > 0;
    __try {
        if (g_mb_ab_on) {
            mb_call1(g->remove, dialog, mb_field(dialog, g->button_a));
            mb_call1(g->remove, dialog, mb_field(dialog, g->button_b));
            g_mb_ab_on = 0;
        }
        if (asking && g_mb_ok_on) {
            mb_call1(g->remove, dialog, mb_field(dialog, g->ok));
            g_mb_ok_on = 0;
        } else if (!asking && !g_mb_ok_on) {
            mb_call1(g->attach, dialog, mb_field(dialog, g->ok));
            g_mb_ok_on = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

static void __fastcall mb_op_draw(void *dialog, void *unused) {
    (void)unused;
    if (dialog == g_mb.dialog && g_mb_op != NULL) {
        g_mb_ok_made = 1;
        mb_op_sync(dialog);
    }
    ((mb_draw_fn)(uintptr_t)g_mb.g->draw)(dialog, NULL);
}

/* Choice k picked (a row or a key): the client's text in place, the buttons after it.  1 when taken. */
static int mb_op_pick(void *dialog, int k) {
    int n = mb_op_count(dialog, NULL);
    if (k < 0 || k >= n) {
        return 0;
    }
    __try {
        void *sound = mb_field(dialog, g_mb.g->sound_field);
        if (sound != NULL) {
            mb_call1(g_mb.g->sound, sound, (void *)(uintptr_t)g_mb.g->sound_id);   /* the game's answer click */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    if (!g_mb_op->pick(dialog, k)) {
        return 0;
    }
    ((unsigned char *)dialog)[0x50] = 0;          /* the question field is the one shown, always */
    mb_op_sync(dialog);
    return 1;
}

/* The dialog's click handler (+0x0C) for a one-popup event: OK goes to the client first (another text keeps the
   popup), the game's two answers are never on screen (a click from them is dropped), the rest is the game's. */
static char __fastcall mb_op_message(void *dialog, void *unused, int message, int id) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused;
    __try {
        if (message == 8 && dialog == g_mb.dialog && g_mb_op != NULL) {
            if (id == *(int *)(d + 0x5C)) {
                if (mb_op_count(dialog, NULL) > 0) {
                    return 1;                          /* asking: no OK */
                }
                if (g_mb_op->ok(dialog)) {
                    d[0x50] = 0;
                    mb_op_sync(dialog);
                    return 1;                          /* another text: the popup stays */
                }
                g_mb_op = NULL;                         /* the event is over: the game's OK closes it */
            } else if (id == *(int *)(d + 0x54) || id == *(int *)(d + 0x58)) {
                return 1;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return ((mb_message_fn)(uintptr_t)g_mb.g->click)(dialog, NULL, message, id);
}

/* The keyboard handler (+0x08): Enter / Esc is OK while no choice is asked, the keys 1 to N the choices. */
static char __fastcall mb_op_key(void *dialog, void *unused, int type, int code, int raw) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused; (void)raw;
    __try {
        int n;
        if (dialog != g_mb.dialog || g_mb_op == NULL) {
            return 0;
        }
        n = mb_op_count(dialog, NULL);
        if (type == 6 && (code == 0x3EB || code == 0x3E8) && n == 0) {
            mb_op_message(dialog, NULL, 8, *(int *)(d + 0x5C));
            return 1;
        }
        if (type == 5 && code >= '1' && code < '1' + n) {
            return (char)mb_op_pick(dialog, code - '1');
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

/* The dialog being built (the setup call, inside the constructor) is a one-popup event: our virtual table with the
   draw, click and key handlers above.  Its buttons are put right at its first draw (the constructor attaches the
   game's two answers after the setup call).  0 when not done. */
static int mb_attach_op(int game, const mb_op_client *client, void *dialog) {
    const mb_game *g = mb_game_of(game);
    unsigned char *d = (unsigned char *)dialog;
    int k;
    for (k = 0; k < MB_EXTRA; ++k) {
        if (g_mb.buttons[k] != NULL) {
            mb_delete(g_mb.buttons[k]);
            g_mb.buttons[k] = NULL;
        }
    }
    g_mb.made = 0;
    g_mb.dialog = NULL;
    g_mb_op = NULL;
    if (g == NULL || client == NULL || dialog == NULL || *(unsigned int *)d != g->dialog_vtable) {
        return 0;
    }
    g_mb.g = g;
    g_mb.c = NULL;
    g_mb.dialog = dialog;
    g_mb.room_px = 0;
    g_mb_room_px = 0;
    g_mb_op = client;
    g_mb_ab_on = 1;
    g_mb_ok_on = 0;
    g_mb_ok_made = 0;
    memcpy(g_mb.dvt, (const void *)(uintptr_t)(g->dialog_vtable - 4u), sizeof g_mb.dvt);
    g_mb.dvt[1 + 2] = (unsigned int)(uintptr_t)mb_op_key;
    g_mb.dvt[1 + 3] = (unsigned int)(uintptr_t)mb_op_message;
    g_mb.dvt[1 + 12] = (unsigned int)(uintptr_t)mb_op_draw;
    *(unsigned int **)d = &g_mb.dvt[1];
    return 1;
}

/* The room OK keeps below the content: 5/2 of its height, as the game's plain popup keeps; before the constructor
   has made OK (its panel is sized first), 5/2 of the answers' picture's 32 pixels. */
#define MB_OP_RESERVE_BEFORE (5 * 32 / 2)
static int mb_op_reserve(void) {
    int h = 0;
    __try {
        void *ok = mb_field(g_mb.dialog, g_mb.g->ok);
        h = ok != NULL && g_mb_ok_made ? mb_vcall(ok, 0x10) : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        h = 0;
    }
    return h > 0 && h < 200 ? 5 * h / 2 : MB_OP_RESERVE_BEFORE;
}

/* For Scrolling Popups (VvfpOnePopupRows): 1 when `popup` is the one-popup event here, `out` filled -- the choices,
   their words and the room OK keeps below the content (5/2 of its height, as the game's plain popup keeps). */
static int mb_op_rows(const void *popup, op_rows *out) {
    int r = 0;
    __try {
        if (popup != NULL && popup == g_mb.dialog && g_mb_op != NULL && out != NULL
            && OP_ROWS_SIZE_OK(out)) {
            out->rows = mb_op_count(g_mb.dialog, out);
            out->reserve = mb_op_reserve();
            r = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        r = 0;
    }
    return r;
}

#endif
