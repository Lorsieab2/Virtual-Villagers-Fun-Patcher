/* Island-event questions with 2 to 7 answers in the game's own two-choice island popup: The Secret City, The Tree
   of Life and New Believers.  Shared by "VVFP More Island Events.dll" (its events, The Troubling Signs first) and
   "VVFP Story Upgrades.dll" (Custom Island Events' questions); each includes it once and keeps its own one popup.

   THE POPUP is the game's own two-choice island-event dialog (constructors 0x4192F0 / 0x417790 / 0x418020), built by
   the game with its two answer buttons (+0x85C, +0x860) and OK (+0x864).  Each answer past two is a button made
   exactly as the constructor makes its two: operator new 0x14 bytes (0x46EC93 / 0x470C5C / 0x47BBDC), the answer
   picture of the image manager (0x42E9D0 + 0x42E8A0 picture 4 / 0x44CCF0 + 0x44CB60 picture 0x83 / 0x44FBB0 +
   0x44FA20 picture 0x65), the button (0x4019F0 / 0x401C20 / 0x401BD0) with ids 4 to 8 (the dialog's own are 1 OK, 2 and
   3: docs/event-collection/button-probe.md) and the dialog as its listener, the label (0x401620 / 0x401600 / 0x4015D0) set from the dialog's text (its text setter 0x4185A0 /
   0x416F60 / 0x417700 fills +0x58) in the game's own label colours (0x4A460C / 0x4B8E34 / 0x4C6D24, three dwords),
   and the dialog's add-child (0x40C1F0 / 0x40C190 / 0x40C680): the game's art, font and button look.
   All the answers stand one above the other in ONE column, centred, 1.5 button heights apart as the constructor
   spaces its two (its first at the height - 3.5 h, its second at - 2 h) -- 1.25 heights apart with 5 to 7 answers,
   so seven take 8.75 h rather than 10.5 h: the game's two move up and ours take the places below, so a label wider
   than its button stays whole on the screen and never meets another.  With two answers nothing here is
   used: the dialog is the game's, untouched.

   ROOM: the popup is sized by its constructor for its text; the client pads the tallest page with blank lines worth
   the extra buttons' room (ma_padded, measured by the game's own justified paragraph 0x40A0C0 / 0x409C30 / 0x409F00 as
   the constructor measures: the holder 0x408940 / 0x408130 / 0x4080C0, the box's width +0x858, the font 0x4B3D60 /
   0x4CCAF0 / 0x4DC930, the colour +0x82C), and Scrolling Popups asks for the room (ma_room) so a capped, scrolled
   popup keeps its text above every button.

   CLICKS AND KEYS: the dialog's virtual table becomes a copy of the game's (0x47F28C / 0x48D2C8 / 0x4984D8) with two
   entries of its own.  The click handler (+0x0C): ids 4 to 8 are the third to seventh answers (the answers hidden,
   +0x830 = 2 to 6, the client's answer); every other click goes to the game's own handler (0x419A00 / 0x417EA0 /
   0x418720), which answers ids 2 and 3 itself.  The keyboard handler (+0x08; the game's own takes no key: 0x4011D0 /
   0x401050 / 0x43F050): Enter or Esc is OK while OK is shown, as the game's own message box does it (0x41AC90 /
   0x418390 / 0x418AC0, the same engine), and the typed keys 1 to N pick the answers while they are shown.  Our
   buttons are taken off the dialog when an answer is chosen and deleted at the next OK click, before the dialog
   closes.

   The client gives: a string id that makes the dialog's text setter show a text (text_id), the popup's state
   (state), and what an answer of ours does (answer: show its first page, OK up). */

#ifndef VVFP_MULTI_ANSWER_H
#define VVFP_MULTI_ANSWER_H

#define MA_MAX_ANSWERS 7
#define MA_EXTRA (MA_MAX_ANSWERS - 2)
#define MA_LABEL_BYTES 128

/* The popup's state, as the client tells it. */
#define MA_NOT_OURS 0
#define MA_OK_UP 1          /* a page with OK, before the answer */
#define MA_ASKING 2         /* the answers are shown, none taken */
#define MA_ANSWERED 3       /* an answer was taken: its pages with OK */

typedef struct {
    int game;
    unsigned int dialog_vtable, click;
    unsigned int set_text, hide, show;
    unsigned int alloc, images, image;
    int image_id;
    unsigned int button, label, colours;
    unsigned int holder, justify, font;
} ma_game;

static const ma_game MA_GAMES[3] = {
    { 3, 0x47F28Cu, 0x419A00u, 0x4185A0u, 0x40C230u, 0x40C1F0u, 0x46EC93u, 0x42E9D0u, 0x42E8A0u, 4,
      0x4019F0u, 0x401620u, 0x4A460Cu, 0x408940u, 0x40A0C0u, 0x4B3D60u },
    { 4, 0x48D2C8u, 0x417EA0u, 0x416F60u, 0x40C210u, 0x40C190u, 0x470C5Cu, 0x44CCF0u, 0x44CB60u, 0x83,
      0x401C20u, 0x401600u, 0x4B8E34u, 0x408130u, 0x409C30u, 0x4CCAF0u },
    { 5, 0x4984D8u, 0x418720u, 0x417700u, 0x40C700u, 0x40C680u, 0x47BBDCu, 0x44FBB0u, 0x44FA20u, 0x65,
      0x401BD0u, 0x4015D0u, 0x4C6D24u, 0x4080C0u, 0x409F00u, 0x4DC930u },
};

typedef struct {
    int (*text_id)(const char *text);
    int (*state)(void *dialog);
    void (*answer)(void *dialog, int answer);     /* answer 2 to 6 clicked (or typed): its first page, OK up */
    /* Optional (NULL: never): 1 when the answer just given shows its page in a popup of its own, so this one closes
       at once, as OK would close it (five or more answers: the Isola Grand Event Collection's G1). */
    int (*closes)(void *dialog);
} ma_client;

typedef struct {
    const ma_game *g;
    const ma_client *c;
    void *dialog;                   /* the dialog with our buttons, NULL none */
    void *buttons[MA_EXTRA];
    int count;                      /* the answers shown: 3 to 7 */
    int shown;
    int room;                       /* the room the extra buttons take beyond the game's two */
    unsigned int dvt[24];           /* the dialog's virtual table: [0] its RTTI locator */
} ma_popup;

static ma_popup g_ma;

typedef void *(__cdecl *ma_new_fn)(unsigned int size);
typedef void *(__cdecl *ma_getter_fn)(void);
typedef void *(__fastcall *ma_fetch_fn)(void *manager, void *unused, int id);
typedef void (__fastcall *ma_button_fn)(void *self, void *unused, int id, void *image, int a, int b, void *listener,
                                        int c);
typedef void (__fastcall *ma_label_fn)(void *self, void *unused, const char *text, unsigned int c1, unsigned int c2,
                                       unsigned int c3, int d);
typedef int (__fastcall *ma_justify_fn)(void *holder, void *unused, const char *text, int x, int y, int width,
                                        unsigned int a, unsigned int b, int measure);
typedef char (__fastcall *ma_message_fn)(void *self, void *unused, int message, int id);
typedef int (__fastcall *ma_vint_fn)(void *self, void *unused);
typedef void (__fastcall *ma_v1_fn)(void *self, void *unused, int a);
typedef void (__fastcall *ma_v2_fn)(void *self, void *unused, int a, int b);

/* The game's table, NULL for A New Home and The Lost Children (their own dialogs). */
static const ma_game *ma_game_of(int game) {
    return game >= 3 && game <= 5 ? &MA_GAMES[game - 3] : NULL;
}

static int ma_vcall(void *object, unsigned int slot) {
    return ((ma_vint_fn)(*(void ***)object)[slot / 4])(object, NULL);
}

static void ma_dialog_call(unsigned int va, void *dialog, void *child) {
    ((ma_v1_fn)(uintptr_t)va)(dialog, NULL, (int)(uintptr_t)child);
}

static void *ma_control(void *dialog, unsigned int offset) {
    return *(void **)((unsigned char *)dialog + offset);
}

/* Answer `k` (0 the first) of the dialog with our buttons: the game's two, then ours. */
static void *ma_button(void *dialog, int k) {
    if (k < 2) {
        return ma_control(dialog, k == 0 ? 0x85Cu : 0x860u);
    }
    return k - 2 < MA_EXTRA ? g_ma.buttons[k - 2] : NULL;
}

/* The distance between two answers' tops: 1.5 button heights (the constructor's) up to four answers, 1.25 from five. */
static int ma_step(int h, int count) {
    return count > 4 ? h + h / 4 : h + h / 2;
}

/* The room `count` answers take beyond the game's two: how far above the game's own first (the height - 3.5 h) the
   first answer stands -- 1.5 button heights for each answer past two, up to four. */
static int ma_room_for(void *dialog, int count) {
    void *button = dialog != NULL ? ma_control(dialog, 0x85Cu) : NULL;
    int h;
    if (button == NULL || count <= 2) {
        return 0;
    }
    h = ma_vcall(button, 0x10);
    if (count <= 4) {
        return (count - 2) * 3 * h / 2;
    }
    return (count - 1) * ma_step(h, count) - (h + h / 2);
}

/* `text` with blank lines worth `room` pixels more, measured by the game's own justified paragraph as the constructor
   measures it.  `cap` the output's bytes. */
static const char *ma_padded(const ma_game *g, const char *text, void *dialog, int room, char *out, int cap) {
    ma_justify_fn justify;
    void *holder;
    unsigned char *d = (unsigned char *)dialog;
    int base, k, n;
    lstrcpynA(out, text != NULL ? text : "", cap);
    if (g == NULL || dialog == NULL || room <= 0) {
        return out;
    }
    justify = (ma_justify_fn)(uintptr_t)g->justify;
    holder = ((ma_getter_fn)(uintptr_t)g->holder)();
    base = justify(holder, NULL, out, 0, 0, *(int *)(d + 0x858), *(unsigned int *)(uintptr_t)g->font,
                   *(unsigned int *)(d + 0x82C), 1);
    for (k = 0; k < 40; ++k) {
        n = lstrlenA(out);
        if (n + 3 >= cap) {
            break;
        }
        if (justify(holder, NULL, out, 0, 0, *(int *)(d + 0x858), *(unsigned int *)(uintptr_t)g->font,
                    *(unsigned int *)(d + 0x82C), 1) >= base + room) {
            break;
        }
        out[n] = '\n';
        out[n + 1] = ' ';
        out[n + 2] = '\0';
    }
    return out;
}

static void ma_show(void *dialog, int shown) {
    int k;
    for (k = 0; k < g_ma.count; ++k) {
        void *b = ma_button(dialog, k);
        if (b != NULL) {
            ma_dialog_call(shown ? g_ma.g->show : g_ma.g->hide, dialog, b);
        }
    }
    g_ma.shown = shown;
}

/* Our buttons deleted (taken off the dialog first). */
static void ma_free(void *dialog) {
    int k;
    for (k = 0; k < MA_EXTRA; ++k) {
        void *b = g_ma.buttons[k];
        if (b != NULL) {
            g_ma.buttons[k] = NULL;
            __try {
                if (dialog != NULL && g_ma.shown && g_ma.g != NULL) {
                    ma_dialog_call(g_ma.g->hide, dialog, b);
                }
                ((ma_v1_fn)(*(void ***)b)[0])(b, NULL, 1);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
    }
    g_ma.shown = 0;
}

/* All the answers one above the other at the panel's bottom, centred, ma_step apart. */
static void ma_layout(void *dialog) {
    unsigned char *d = (unsigned char *)dialog;
    int width = *(int *)(d + 0x1C) - *(int *)(d + 0x14);
    int height = *(int *)(d + 0x20) - *(int *)(d + 0x18);
    int k;
    for (k = 0; k < g_ma.count; ++k) {
        void *b = ma_button(dialog, k);
        int bw, bh, step;
        if (b == NULL) {
            continue;
        }
        bw = ma_vcall(b, 0x0C);
        bh = ma_vcall(b, 0x10);
        step = ma_step(bh, g_ma.count);
        ((ma_v2_fn)(*(void ***)b)[1])(b, NULL, (width - bw) / 2, height - 2 * bh - (g_ma.count - 1 - k) * step);
    }
}

/* The dialog's click handler (its +0x0C): ids 4 to 8 are our answers, the rest the game's. */
static char __fastcall ma_message(void *dialog, void *unused, int message, int id) {
    char handled = 0;
    int state;
    (void)unused;
    __try {
        state = dialog == g_ma.dialog && g_ma.c != NULL ? g_ma.c->state(dialog) : MA_NOT_OURS;
        if (message == 8 && id >= 4 && id < 2 + g_ma.count && state == MA_ASKING) {
            const ma_client *c = g_ma.c;
            ma_show(dialog, 0);
            *(int *)((unsigned char *)dialog + 0x830) = id - 2;
            c->answer(dialog, id - 2);
            if (c->closes != NULL && c->closes(dialog)) {
                return ma_message(dialog, NULL, 8, 1);   /* its page comes as a popup of its own: OK now */
            }
            return 0;                                  /* as the game's own answer: the dialog stays */
        }
        if (message == 8 && id == 1 && state == MA_ANSWERED) {
            ma_free(dialog);                           /* OK after the answer: our buttons are no longer needed */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    handled = ((ma_message_fn)(uintptr_t)g_ma.g->click)(dialog, NULL, message, id);
    __try {
        if (message == 8 && (id == 2 || id == 3) && dialog == g_ma.dialog && g_ma.shown
            && g_ma.c->state(dialog) == MA_ANSWERED) {
            ma_show(dialog, 0);                        /* the game hid its two: ours go too */
            if (g_ma.c->closes != NULL && g_ma.c->closes(dialog)) {
                handled = ma_message(dialog, NULL, 8, 1);   /* its page comes as a popup of its own: OK now */
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return handled;
}

/* The dialog's keyboard handler (its +0x08): Enter (0x3EB) or Esc (0x3E8) is OK while OK is shown; the typed keys 1
   to N (type 5) pick the answers while they are shown.  1 when the key was used. */
static char __fastcall ma_key(void *dialog, void *unused, int type, int code, int raw) {
    (void)unused; (void)raw;
    __try {
        int state = dialog == g_ma.dialog && g_ma.c != NULL ? g_ma.c->state(dialog) : MA_NOT_OURS;
        if (state == MA_NOT_OURS) {
            return 0;
        }
        if (type == 6 && (code == 0x3EB || code == 0x3E8) && state != MA_ASKING) {
            ma_message(dialog, NULL, 8, 1);
            return 1;
        }
        if (type == 5 && state == MA_ASKING && code >= '1' && code < '1' + g_ma.count) {
            ma_message(dialog, NULL, 8, 2 + (code - '1'));
            return 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 0;
}

/* After the dialog's constructor: `count` answers (3 to 7; the game made the first two with labels[0] and [1]) --
   ours made with labels[2..], all laid out, our virtual table, and the answers shown.  The dialog's text is the last
   label afterwards: the client sets its page.  0 (nothing changed) when the buttons could not be made. */
static int ma_attach(int game, const ma_client *client, void *dialog, int count, const char *const *labels) {
    const ma_game *g = ma_game_of(game);
    void *manager;
    unsigned char *d = (unsigned char *)dialog;
    int k;
    ma_free(NULL);                                     /* never two sets */
    g_ma.dialog = NULL;
    g_ma.count = 0;
    g_ma.room = 0;
    if (g == NULL || client == NULL || dialog == NULL || count <= 2 || count > MA_MAX_ANSWERS) {
        return 0;
    }
    g_ma.g = g;
    g_ma.c = client;
    manager = ((ma_getter_fn)(uintptr_t)g->images)();
    for (k = 0; k < count - 2; ++k) {
        void *image, *b = ((ma_new_fn)(uintptr_t)g->alloc)(0x14);
        if (b == NULL) {
            ma_free(NULL);
            return 0;
        }
        image = ((ma_fetch_fn)(uintptr_t)g->image)(manager, NULL, g->image_id);
        ((ma_button_fn)(uintptr_t)g->button)(b, NULL, 4 + k, image, 0, 0, dialog, 0);
        g_ma.buttons[k] = b;
        ((ma_v1_fn)(uintptr_t)g->set_text)(dialog, NULL, client->text_id(labels[2 + k]));
        ((ma_label_fn)(uintptr_t)g->label)(b, NULL, (const char *)dialog + 0x58,
                                           *(unsigned int *)(uintptr_t)g->colours,
                                           *(unsigned int *)(uintptr_t)(g->colours + 4u),
                                           *(unsigned int *)(uintptr_t)(g->colours + 8u), 0);
    }
    g_ma.dialog = dialog;
    g_ma.count = count;
    for (k = 2; k < count; ++k) {
        ma_dialog_call(g->show, dialog, g_ma.buttons[k - 2]);   /* the constructor showed the game's two */
    }
    g_ma.shown = 1;
    g_ma.room = ma_room_for(dialog, count);
    ma_layout(dialog);
    memcpy(g_ma.dvt, (const void *)(uintptr_t)(g->dialog_vtable - 4u), sizeof g_ma.dvt);
    g_ma.dvt[1 + 2] = (unsigned int)(uintptr_t)ma_key;
    g_ma.dvt[1 + 3] = (unsigned int)(uintptr_t)ma_message;
    if (*(unsigned int *)d == g->dialog_vtable) {
        *(unsigned int **)d = &g_ma.dvt[1];
    }
    return 1;
}

/* The popup closed (or another is built): our buttons are gone with the dialog's children; forget it. */
static void ma_forget(void) {
    ma_free(NULL);
    g_ma.dialog = NULL;
    g_ma.count = 0;
    g_ma.room = 0;
}

/* The room our buttons take in `popup`, for Scrolling Popups: 0 for any other dialog. */
static int ma_room(const void *popup) {
    int room = 0;
    __try {
        room = popup != NULL && popup == g_ma.dialog ? g_ma.room : 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        room = 0;
    }
    return room > 0 && room < 2048 ? room : 0;
}

#endif
