/* Custom Island Event: the event object The Secret City, The Tree of Life
   and New Believers present.  Included by vvfp_story_upgrades.c.

   These three games keep their island events as objects (a vtable, the
   featured villager at +4, an amount at +8) and present the one their
   selector chose with the game's own dialog: its constructor asks the
   object for a title string id and a body string id, looks them up in the
   game's string table (entries {id, key, text, localized}, the localized
   text preferred) and copies the body; OK calls the object's apply.

   The custom event is one more such object: a copy of a stock simple
   event's vtable in which the title and body ids are two ids no code and no
   string uses in that game, whose string-table entries point at the custom
   title and description, the amount is -1 and no villager is featured (so
   the body is copied as it is, with no {name} formatting), and the apply
   does nothing -- the changes were made, as A New Home's and The Lost
   Children's own events make theirs, before the dialog was built, so the
   outcome lines can say what happened.  The object is never put in the
   game's event table (whose teardown deletes its entries), only handed to
   the presenter in place of the selector's choice. */

typedef struct {
    int id;
    const char *key;
    const char *text;
    const char *localized;
} story_string;

typedef struct {
    void *vtable;
    void *villager;
    int amount;
    int extra[2];
} story_event_object;

static story_string ce_strings[2];
static unsigned int ce_vtable[17];       /* [0] = the source's RTTI locator */
static story_event_object ce_object;

/* THE DIALOG'S 2,000 BYTES.  The dialog's text routine (The Secret City 0x4185A0, The Tree of Life 0x416F60, New
   Believers 0x417700) formats the text of a string id into its own field (+0x58, 2,000 bytes) with the game's
   formatter (0x42F1D0 / 0x44D410 / 0x450710, `push 0x7d0`), and the constructor's plain path (0x4197A0 / 0x417C49 /
   0x4184D0) copies it raw; both end in the C runtime's strncat(field, text, 2000), which writes 2,000 bytes AND the
   NUL after them -- one byte past the field -- for a text of 2,000 bytes or more.  So the string-table entry is
   never given more than 1,999 bytes: a longer text is entered as its first 1,999 (ce_popup_text), which the dialog
   copies whole, and Scrolling Popups asks for the rest (VvfpStoryPopupFullText) to draw and measure the whole text.
   The text never holds '{' (the game's placeholders): the names are filled in already, so the copy is the text's
   own first 1,999 bytes. */
#define CE_SHOWN_BYTES 2000
static char ce_shown_text[CE_SHOWN_BYTES];

/* What the string-table entry carries for `text`: itself, or its first 1,999 bytes. */
static const char *ce_popup_text(const char *text) {
    if (lstrlenA(text) < CE_SHOWN_BYTES) {
        return text;
    }
    lstrcpynA(ce_shown_text, text, CE_SHOWN_BYTES);
    return ce_shown_text;
}

static void __fastcall ce_object_nothing(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
}

static char __fastcall ce_object_true(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return 1;
}

/* Point string ids `title_id` and `body_id` of the table at `table` (the
   pointer array the game's lookup indexes) at the custom text.  The two ids
   are checked unused when the companion installs (story_tables.h); here the
   slot must still be empty or ours. */
static int ce_install_strings(unsigned int table, int title_id, int body_id, int replace_existing) {
    story_string **slots = (story_string **)(uintptr_t)table;
    ce_strings[0].id = title_id;
    ce_strings[0].key = "eStoryCustomTitle";
    ce_strings[0].text = ce_title_text;
    ce_strings[0].localized = NULL;
    ce_strings[1].id = body_id;
    ce_strings[1].key = "eStoryCustomText";
    ce_strings[1].text = ce_body_text;
    ce_strings[1].localized = NULL;
    if (!replace_existing
        && ((slots[title_id] != NULL && slots[title_id] != &ce_strings[0])
            || (slots[body_id] != NULL && slots[body_id] != &ce_strings[1]))) {
        return 0;
    }
    slots[title_id] = &ce_strings[0];
    slots[body_id] = &ce_strings[1];
    return 1;
}

/* The custom event object: `source` is a stock simple event's vtable (16
   slots); `slots`/`functions` (count of them) replace entries by slot. */
static void *ce_build_object(unsigned int source, const int *slots, void *const *functions, int count) {
    int i;
    memcpy(ce_vtable, (const void *)(uintptr_t)(source - 4), sizeof ce_vtable);
    for (i = 0; i < count; ++i) {
        ce_vtable[1 + slots[i]] = (unsigned int)(uintptr_t)functions[i];
    }
    memset(&ce_object, 0, sizeof ce_object);
    ce_object.vtable = &ce_vtable[1];
    ce_object.villager = NULL;
    ce_object.amount = -1;
    return &ce_object;
}

/* The delivery for these games: apply the armed event and fill the strings;
   NULL when no custom event is armed for `game`. */
static void *ce_deliver_object(int game, unsigned int string_table, int title_id, int body_id,
                               int replace_existing) {
    if (!ce_plain_pending(game) || ce_held(game, 1)) {
        return NULL;                      /* none, or one of the opening events (ce_held) */
    }
    if (!ce_install_strings(string_table, title_id, body_id, replace_existing)) {
        return NULL;
    }
    if (!ce_deliver(game, ce_body_text, sizeof ce_body_text)) {
        return NULL;
    }
    ce_strings[1].text = ce_popup_text(ce_body_text);
    lstrcpynA(ce_title_text, ce_armed_event.title, sizeof ce_title_text);
    return (void *)1;
}

/* ---- Two choices (The Secret City, The Tree of Life, New Believers) --------

   A question is one more event object, built from a copy of a stock
   TWO-CHOICE event's vtable (its +0x10 answers 1), handed to the presenter
   in place of the selector's choice exactly as the plain custom event is.
   The presenter's dialog (VV3 0x4192F0, VV4 0x417790, VV5 0x418020) asks:

     +0x08  the title id (looked up once; the dialog keeps the pointer)
     +0x1C  the villager shown -- a two-choice popup with none is never shown
            (the ctor returns with its "show" byte +0x4C clear), so the
            question always features a living villager
     +0x24  that villager's pose (5, the stock value of most two-choice events)
     +0x20  a second villager ({name2}): none
     +0x14 / +0x18  the button labels' ids
     +0x28(c)  the result's id, at BUILD for c = 0 and 1 (the popup is sized
            to the tallest of the question and both results) and at the click
     +0x0C  the question's id
   and the click (VV3 0x419A00, VV4 0x417EA0, VV5 0x418720) calls
     +0x34(c)  on the choice -- then +0x28(c) for the result shown in place
            of the question, then OK calls +0x2C(c), the apply.

   Every text goes through the dialog's own text routine, which looks the id
   up at once, so one string id (the plain event's body id) carries the
   question, each label and the result in turn: each method points the id's
   entry at its text just before returning the id.  On the choice the answer
   is rolled and applied (ce_choice_resolve) so the result can say what
   happened; before it, +0x28 gives the tallest result that button can show,
   so the popup is tall enough for any of them.  The apply on OK does
   nothing: the changes were made at the click. */

static char choice_labels[MA_MAX_ANSWERS][96];   /* a format 6 label: 95 bytes (story_graph.inc CG_LABEL_V6) */
static char choice_tallest[MA_MAX_ANSWERS][2000];
static char choice_result[CE_POPUP_TEXT_BYTES];
static int choice_answered;
static int choice_game;
static int choice_answers;               /* 2, or a branching event's question's 3 to 7 (format 4: 3 or 4) */
static int choice_tallest_at;            /* with 3 or 4: the answer whose first page is the tallest */
static char choice_padded[2000];

/* THREE OR FOUR ANSWERS (the owner, 2026-11-13: "Make the 2-4 option thing general").  The question is presented by
   the game's own presenter as any other, through the stub's own path (vvfp_story_upgrades.c vv3_stub ..): the
   constructor called as the presenter calls it, the dialog it builds in cs_dialog, then cs_after_ctor gives it the
   shared multi-answer popup (native/shared/vvfp_multi_answer.h): the third and fourth buttons made as the game makes
   its two, stacked and centred, ids 4 and 5 and the keys 1 to 4.  Before the click +0x28 gives the tallest first page
   of every answer, padded with blank lines worth the extra buttons' room.  With two answers nothing here is used. */
static int cs_multi;                     /* the question handed to the presenter has 3 or 4 answers */
static void *cs_dialog;                  /* the dialog the presenter builds for it */
static int cs_op;                        /* ... a one-popup event (vvfp_multi_answer.h ma_op_*): its whole run */

static int __fastcall choice_object_question(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    ce_strings[1].text = ce_popup_text(ce_body_text);
    return ce_strings[1].id;
}

static int __fastcall choice_object_first_label(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    ce_strings[1].text = choice_labels[0];
    return ce_strings[1].id;
}

static int __fastcall choice_object_second_label(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    ce_strings[1].text = choice_labels[1];
    return ce_strings[1].id;
}

static void *__fastcall choice_object_villager(void *self, void *unused_edx) {
    (void)unused_edx;
    return ((story_event_object *)self)->villager;
}

static void *__fastcall choice_object_nobody(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return NULL;
}

static int __fastcall choice_object_pose(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return 5;
}

/* +0x28 (ret 4). */
static int __fastcall choice_object_result(void *self, void *unused_edx, int choice) {
    (void)self;
    (void)unused_edx;
    if (cs_op) {
        ce_strings[1].text = ce_popup_text(ce_body_text);   /* one popup: its panel is sized for the text shown first */
        return ce_strings[1].id;
    }
    if (!choice_answered && choice_answers > 2) {
        const char *text = choice_tallest[choice_tallest_at];
        __try {
            text = ma_padded(ma_game_of(choice_game), text, cs_dialog, ma_room_for(cs_dialog, choice_answers),
                             choice_padded, sizeof choice_padded);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            text = choice_tallest[choice_tallest_at];
        }
        ce_strings[1].text = text;
        return ce_strings[1].id;
    }
    ce_strings[1].text = ce_popup_text(choice_answered ? choice_result : choice_tallest[choice != 0]);
    return ce_strings[1].id;
}

/* Answer `button` (0 the first): rolled and made, its result written. */
static void choice_answer(int button) {
    if (choice_answered) {
        return;
    }
    choice_answered = 1;
    if (!ce_choice_resolve(choice_game, button, choice_result, sizeof choice_result)) {
        choice_result[0] = '\0';     /* another village by now: nothing happened */
    }
}

/* +0x34 (ret 4): the click.  The game's own button order: 0 the first. */
static void __fastcall choice_object_choose(void *self, void *unused_edx, int choice) {
    (void)self;
    (void)unused_edx;
    choice_answer(choice != 0);
}

/* +0x2C (ret 4): OK.  The changes were made at the click. */
static void __fastcall choice_object_apply(void *self, void *unused_edx, int choice) {
    (void)self;
    (void)unused_edx;
    (void)choice;
    if (cs_op) {
        ma_op_forget();               /* one popup: the event is over */
        cs_op = 0;
    }
    if (cs_multi) {
        ma_forget();                  /* the popup closes: our buttons went at this OK */
        cs_multi = 0;
    }
}

/* ---- One popup per island event (native/shared/one_popup.h): the client of vvfp_multi_answer.h ma_op_* ---- */

static int cs_op_rows(void *dialog, op_rows *out) {
    int k, n = cg_op_rows(choice_game);
    (void)dialog;
    out->rows = n;
    for (k = 0; k < n && k < OP_MAX_ROWS; ++k) {
        lstrcpynA(out->labels[k], cg_label(k), OP_LABEL_BYTES);
    }
    return 1;
}

/* The text just made (choice_result) shown: the dialog's own field (its first 1,999 bytes: Scrolling Popups draws the
   whole, VvfpStoryPopupFullText), and the title in force on it. */
static void cs_op_show(void *dialog) {
    lstrcpynA((char *)dialog + 0x58, choice_result, CE_SHOWN_BYTES);
    lstrcpynA(ce_title_text, cg_op_title(), sizeof ce_title_text);
}

static int cs_op_pick(void *dialog, int k) {
    if (!ce_choice_resolve(choice_game, k, choice_result, sizeof choice_result)) {
        return 0;
    }
    choice_answered = 1;
    cs_op_show(dialog);
    return 1;
}

static int cs_op_ok(void *dialog) {
    if (!cg_op_ok(choice_game, choice_result, sizeof choice_result)) {
        return 0;
    }
    cs_op_show(dialog);
    return 1;
}

static const ma_op_client CS_OP_CLIENT = { cs_op_rows, cs_op_pick, cs_op_ok };

/* ---- The shared multi-answer popup's client ---- */

static int cs_text_id(const char *text) {
    ce_strings[1].text = ce_popup_text(text);
    return ce_strings[1].id;
}

static int cs_state(void *dialog) {
    if (dialog == NULL || dialog != g_ma.dialog || !cs_multi) {
        return MA_NOT_OURS;
    }
    return choice_answered ? MA_ANSWERED : MA_ASKING;
}

/* Answer 2 or 3: as the game's click handler answers its own two (the answer, its result as the text, OK shown). */
static void cs_answer(void *dialog, int answer) {
    const ma_game *g = ma_game_of(choice_game);
    choice_answer(answer);
    ((ma_v1_fn)(uintptr_t)g->set_text)(dialog, NULL, cs_text_id(choice_result));
    ma_dialog_call(g->show, dialog, ma_control(dialog, 0x864u));
}

/* G1: five or more answers: the answer's page is a popup of its own, so this one closes at the click. */
static int cs_closes(void *dialog) {
    (void)dialog;
    return cg_answer_closes(choice_game);
}

static const ma_client CS_CLIENT = { cs_text_id, cs_state, cs_answer, cs_closes };

/* After the presenter's constructor (the stubs' own path for 3 or 4 answers): the shared popup's extra buttons, then
   the question's text back (the labels went through it). */
static void __cdecl cs_after_ctor(void *dialog) {
    __try {
        unsigned char *d = (unsigned char *)dialog;
        const char *words[MA_MAX_ANSWERS];
        const ma_game *g = ma_game_of(choice_game);
        int k;
        if (!cs_multi || d == NULL || g == NULL || *(void **)(d + 0x50) != (void *)&ce_object || d[0x4C] == 0) {
            return;
        }
        if (cs_op) {
            ma_op_expect(choice_game, &CS_OP_CLIENT, dialog);
            ma_op_attach(dialog);       /* one popup: our virtual table, the game's answers hidden */
            return;
        }
        for (k = 0; k < choice_answers; ++k) {
            words[k] = choice_labels[k];
        }
        if (ma_attach(choice_game, &CS_CLIENT, dialog, choice_answers, words)) {
            ce_strings[1].text = ce_popup_text(ce_body_text);
            ((ma_v1_fn)(uintptr_t)g->set_text)(dialog, NULL, ce_strings[1].id);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* For Scrolling Popups: the whole text of the island-event popup whose dialog field holds `shown` -- the text it was
   made from when `shown` is that text's first 1,999 bytes (a strict prefix, cut where the dialog cuts it:
   ce_popup_text, cs_op_show); NULL for any other text (the field is the whole text, or not ours). */
__declspec(dllexport) const char *__stdcall VvfpStoryPopupFullText(const char *shown) {
    const char *const whole[2] = { ce_body_text, choice_result };
    const char *found = NULL;
    int k;
    if (shown == NULL) {
        return NULL;
    }
    __try {
        int n = lstrlenA(shown);
        for (k = 0; k < 2 && found == NULL && n == CE_SHOWN_BYTES - 1; ++k) {
            if (lstrlenA(whole[k]) > n && memcmp(whole[k], shown, (size_t)n) == 0) {
                found = whole[k];
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        found = NULL;
    }
    return found;
}

/* The room the extra buttons of the question on screen take, for Scrolling Popups: 0 for any other popup. */
__declspec(dllexport) int __stdcall VvfpStoryButtonRoom(const void *popup) {
    return ma_room(popup);
}

/* For Scrolling Popups (native/shared/one_popup.h): the one-popup event's choices, in any game.  The later three
   games' dialog is known from the presenter's stack slot before its constructor sizes it. */
__declspec(dllexport) int __stdcall VvfpOnePopupRows(const void *popup, op_rows *out) {
    if (cs_op && popup != NULL && popup == cs_dialog && g_ma_op_dialog != cs_dialog) {
        ma_op_expect(choice_game, &CS_OP_CLIENT, cs_dialog);
    }
    if (ma_op_rows(popup, out)) {
        return 1;
    }
    return mb_op_rows(popup, out);
}

__declspec(dllexport) int __stdcall VvfpOnePopupPick(const void *popup, int k) {
    if (popup != NULL && popup == g_ma_op_dialog && g_ma_op != NULL) {
        return ma_op_pick((void *)popup, k);
    }
    if (popup != NULL && popup == g_mb.dialog && g_mb_op != NULL) {
        return mb_op_pick((void *)popup, k);
    }
    return 0;
}

/* The question object of `game`, built from the two-choice vtable `source`
   with the title method `title`, featuring the picked villager or a random
   living one (ce_choice_featured); NULL when no question is armed (or nobody
   could be featured: the event stays armed and lapses as an undelivered one). */
static void *choice_object(int game, unsigned int string_table, int title_id, int body_id,
                           int replace_existing, unsigned int source, void *title) {
    static const int slots[11] = { 2, 3, 5, 6, 7, 8, 9, 10, 11, 13, 4 };
    void *functions[11];
    const ce_adapter *a = ce_adapter_for(game);
    unsigned char *villager;
    const char *text;
    void *object;
    int b;
    cs_multi = 0;
    cs_op = 0;
    if (a == NULL || !ce_choice_pending(game) || ce_held(game, 1)) {
        return NULL;
    }
    b = ce_choice_featured(game);
    villager = b >= 0 ? a->record(b) : NULL;
    if (villager == NULL) {
        return NULL;
    }
    if (!ce_install_strings(string_table, title_id, body_id, replace_existing)) {
        return NULL;
    }
    if (!ce_choice_begin(game, ce_body_text, sizeof ce_body_text)) {
        return NULL;
    }
    ce_strings[1].text = ce_popup_text(ce_body_text);
    if (cg_op_begun_take(game)) {
        /* One popup: the whole event in the presenter's dialog (cs_after_ctor), its choices drawn by Scrolling
           Popups; nothing to size for but the text shown first. */
        int n = cg_op_rows(game);
        cs_op = 1;
        cs_multi = 1;                 /* the stubs' own path: the dialog known before and after its constructor */
        choice_answers = n >= 2 ? n : 2;
        for (b = 0; b < MA_MAX_ANSWERS; ++b) {
            lstrcpynA(choice_labels[b], b < n ? cg_label(b) : "", sizeof choice_labels[b]);
            choice_tallest[b][0] = '\0';
        }
        choice_tallest_at = 0;
        lstrcpynA(ce_title_text, cg_op_title(), sizeof ce_title_text);
        choice_result[0] = '\0';
        choice_answered = 0;
        choice_game = game;
        functions[0] = title;
        functions[1] = (void *)choice_object_question;
        functions[2] = (void *)choice_object_first_label;
        functions[3] = (void *)choice_object_second_label;
        functions[4] = (void *)choice_object_villager;
        functions[5] = (void *)choice_object_nobody;
        functions[6] = (void *)choice_object_pose;
        functions[7] = (void *)choice_object_result;
        functions[8] = (void *)choice_object_apply;
        functions[9] = (void *)choice_object_choose;
        functions[10] = (void *)ce_object_true;
        object = ce_build_object(source, slots, functions, 11);
        ce_object.villager = villager;
        return object;
    }
    choice_answers = ce_choice_answers(game);
    choice_tallest_at = 0;
    for (b = 0; b < choice_answers; ++b) {
        int lines;
        text = ce_choice_label(game, b);
        lstrcpynA(choice_labels[b], text != NULL ? text : "", sizeof choice_labels[b]);
        lines = ce_choice_tallest(game, b, choice_tallest[b], sizeof choice_tallest[b]);
        if (b > 0 && lines > ce_text_lines(choice_tallest[choice_tallest_at])) {
            choice_tallest_at = b;
        }
    }
    cs_multi = choice_answers > 2;
    text = ce_choice_title(game);
    lstrcpynA(ce_title_text, text != NULL ? text : "", sizeof ce_title_text);
    choice_result[0] = '\0';
    choice_answered = 0;
    choice_game = game;
    functions[0] = title;
    functions[1] = (void *)choice_object_question;
    functions[2] = (void *)choice_object_first_label;
    functions[3] = (void *)choice_object_second_label;
    functions[4] = (void *)choice_object_villager;
    functions[5] = (void *)choice_object_nobody;
    functions[6] = (void *)choice_object_pose;
    functions[7] = (void *)choice_object_result;
    functions[8] = (void *)choice_object_apply;
    functions[9] = (void *)choice_object_choose;
    functions[10] = (void *)ce_object_true;
    object = ce_build_object(source, slots, functions, 11);
    ce_object.villager = villager;
    return object;
}
