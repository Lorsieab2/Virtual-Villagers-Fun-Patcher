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
    if (!ce_pending(game)) {
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
