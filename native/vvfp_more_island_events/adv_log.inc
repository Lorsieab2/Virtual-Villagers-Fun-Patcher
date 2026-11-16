/* More Island Events: the effects on their own page, and the Island Events log's ONE entry for each event, in all
   five games.  Included by vvfp_more_island_events.c after adv_core.inc.

   The owner's standing rule: the effects wait for their own page.  An ending's effects are made, once, when the page
   that ends its text is shown (each game's file calls adv_log_effects then) -- never on an earlier page, never twice:
   each event's effects carry their own "made" flag, and nothing of an event outlives its popup (the dialog is modal:
   the village does not run and the game does not save while it is up), so a quit before that page leaves the save
   without them and a reload never brings the event back.

   The Island Events log ("VVFP Island Events.dll") keeps ONE entry for each such event, as for a branching Custom
   Island Event: "  Event: <title>", a "  Choice: <answer>" line for each answer clicked (The Cave Explorers asks up to
   three questions), then what the effects page changed -- that companion's own comparison around it
   (VvfpIslandEventsGraphBegin / End) -- or "  Changes: none".  The entry is handed over once, complete, when the
   effects are made (VvfpIslandEventsGraphWrite, final; the Parentage Export's WriteVillageEventEntry), so at any save
   the log holds the event exactly when the save holds its effects.  The game's own brackets around the event's
   popups (each game's click handler, constructor) write nothing of their own: VvfpMoreIslandEventsLogged says so,
   from the event's composing until the game draws its next island event.  Without that companion: nothing. */

#define ADV_LOG_BYTES 4096
#define ADV_LOG_TITLE 160

static struct {
    int active;                           /* this event's popups are the companion's to log */
    int game;
    char title[ADV_LOG_TITLE];            /* as the popup shows it */
    char entry[ADV_LOG_BYTES];
    int len;
    int sent;                             /* the entry handed over (once) */
    char extra[1024];                     /* the event's own lines (what the villager comparison cannot say) */
} adv_log;

typedef int (__stdcall *adv_log_begin_fn)(int game);
typedef int (__stdcall *adv_log_end_fn)(int game, char *out, int cap);
typedef int (__stdcall *adv_log_write_fn)(int game, int key, const char *text, int disk, int final);

static FARPROC adv_log_export(const char *name) {
    HMODULE module = GetModuleHandleA("VVFP Island Events.dll");
    return module != NULL ? GetProcAddress(module, name) : NULL;
}

static void adv_log_put(const char *text) {
    int n = adv_len(text);
    if (adv_log.len + n + 1 < ADV_LOG_BYTES) {
        memcpy(adv_log.entry + adv_log.len, text, (size_t)n + 1);
        adv_log.len += n;
    }
}

/* The game is drawing an island event: whatever was ours before is over. */
static void adv_log_reset(void) {
    adv_log.active = 0;
    adv_log.len = 0;
    adv_log.entry[0] = '\0';
    adv_log.sent = 0;
    adv_log.extra[0] = '\0';
}

/* A line of the event's own, made by its effects (The Rumblings' damaged structures): after the comparison's. */
static void adv_log_extra(const char *line) {
    adv_cat(adv_log.extra, (int)sizeof adv_log.extra, line);
}

/* One of the companion's events is composed for its popup (`title` as shown). */
static void adv_log_event(int game, const char *title) {
    adv_log_reset();
    adv_log.active = 1;
    adv_log.game = game;
    adv_copy(adv_log.title, sizeof adv_log.title, title);
    adv_log_put("  Event: ");
    adv_log_put(title);
    adv_log_put("\n");
}

/* An answer clicked (its words as the button shows them). */
static void adv_log_choice(const char *label) {
    if (!adv_log.active || adv_log.sent) {
        return;
    }
    adv_log_put("  Choice: ");
    adv_log_put(label);
    adv_log_put("\n");
}

/* The ending's effects (`effects(ending)`), bracketed by the log's own comparison; the entry handed over, complete. */
static void adv_log_effects(void (*effects)(int), int ending) {
    static char lines[ADV_LOG_BYTES];
    adv_log_begin_fn begin = (adv_log_begin_fn)(void *)adv_log_export("VvfpIslandEventsGraphBegin");
    adv_log_end_fn end = (adv_log_end_fn)(void *)adv_log_export("VvfpIslandEventsGraphEnd");
    adv_log_write_fn write = (adv_log_write_fn)(void *)adv_log_export("VvfpIslandEventsGraphWrite");
    int began = adv_log.active && !adv_log.sent && begin != NULL && begin(adv_log.game);
    effects(ending);
    if (!adv_log.active || adv_log.sent) {
        return;
    }
    lines[0] = '\0';
    if (began && end != NULL && end(adv_log.game, lines, (int)sizeof lines) > 0) {
        adv_log_put(lines);
        adv_log_put(adv_log.extra);
    } else if (adv_log.extra[0] != '\0') {
        adv_log_put(adv_log.extra);
    } else {
        adv_log_put("  Changes: none\n");
    }
    adv_log.sent = 1;
    if (write != NULL) {
        (void)write(adv_log.game, (int)(GetTickCount() & 0x7FFFFFFFu) | 1, adv_log.entry, -1, 1);
    }
}

/* Asked by "VVFP Island Events.dll" as it compares a popup the game just showed (a click, a constructor): 1 when it
   is one of this companion's events -- its one entry is written here, never a record of its own. */
int __stdcall VvfpMoreIslandEventsLogged(int game, const char *title) {
    int ours = 0;
    __try {
        /* The Secret City, The Tree of Life, New Believers: their dialog's title pointer (+0x54) is the string the
           event object handed over; while the event is ours no other island-event popup can be up (the next one is
           drawn by the selector, which ends ours first: t_list), so the dialog is ours whatever it reads. */
        ours = adv_log.active && game == adv_log.game
            && (game >= 3 || title == NULL || title[0] == '\0' || lstrcmpA(title, adv_log.title) == 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ours = 0;
    }
    return ours;
}
