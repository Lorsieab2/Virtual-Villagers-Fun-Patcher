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
    if (!ce_plain_pending(game)) {
        return NULL;
    }
    if (!ce_install_strings(string_table, title_id, body_id, replace_existing)) {
        return NULL;
    }
    if (!ce_deliver(game, ce_body_text, 2000)) {
        return NULL;
    }
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

static char choice_labels[2][CE_BUTTON_BYTES];
static char choice_tallest[2][2000];
static char choice_result[2000];
static int choice_answered;
static int choice_game;

static int __fastcall choice_object_question(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    ce_strings[1].text = ce_body_text;
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
    ce_strings[1].text = choice_answered ? choice_result : choice_tallest[choice != 0];
    return ce_strings[1].id;
}

/* +0x34 (ret 4): the click.  The game's own button order: 0 the first. */
static void __fastcall choice_object_choose(void *self, void *unused_edx, int choice) {
    (void)self;
    (void)unused_edx;
    if (choice_answered) {
        return;
    }
    choice_answered = 1;
    if (!ce_choice_resolve(choice_game, choice != 0, choice_result, sizeof choice_result)) {
        choice_result[0] = '\0';     /* another village by now: nothing happened */
    }
}

/* +0x2C (ret 4): OK.  The changes were made at the click. */
static void __fastcall choice_object_apply(void *self, void *unused_edx, int choice) {
    (void)self;
    (void)unused_edx;
    (void)choice;
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
    if (a == NULL || !ce_choice_pending(game)) {
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
    if (!ce_choice_begin(game, ce_body_text, 2000)) {
        return NULL;
    }
    for (b = 0; b < 2; ++b) {
        text = ce_choice_label(game, b);
        lstrcpynA(choice_labels[b], text != NULL ? text : "", sizeof choice_labels[b]);
        ce_choice_tallest(game, b, choice_tallest[b], sizeof choice_tallest[b]);
    }
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
