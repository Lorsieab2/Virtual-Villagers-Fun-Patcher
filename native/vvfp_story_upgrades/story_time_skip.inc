/* Choose Time Skip Amount -- included by vvfp_story_upgrades.c.

   The owner (2026-10-10): "add a cheat upgrade: Choose Time Skip Amount
   (costs same as the normal upgrade).  Choose a number of years to skip
   from 1-72."

   THE NORMAL TIME WARP (each game's Origins companion, ShowOriginsTimeWarp /
   ShowVV2TimeWarp / ShowVV3TimeWarp / ShowVv4TimeWarp / ShowVv5TimeWarp)
   advances three villager years on slow, six on normal and twelve on fast
   (one Time Warp is about ten to twelve hours of the game's clock) for
   50,000 tech points (0 while the Story / Cheat Upgrades make every Origins
   upgrade free).  It moves the game's clock epoch back by the real seconds
   those years take and credits every living villager the exact age units
   (20 a year), moving each record's "last seen" marker by the same amount
   so the villager tick does not put the jump through its clamp.  The game's
   own villager tick then replays the new age units one at a time (A New
   Home: 0x42E900, its catch-up loop 0x42EC53-0x42F162) -- the work,
   food, pregnancies, births and deaths of the skipped time.

   THIS UPGRADE asks for 1-72 years and advances them as a run of those very
   Time Warps: each step is the companion's own Time Warp advance, at most
   the years one Time Warp buys at the current speed (the last step takes
   what is left), and the next step waits until the game's villager tick has
   replayed the last one.  So no single jump is bigger than the Time Warp the
   game already copes with, every step's catch-up is the game's own, and a
   child born in one step ages through the next.  72 years is 6 steps on
   fast, 12 on normal and 24 on slow, a couple of seconds each.

   The price is the Time Warp's own (all five games: 50,000; 0 while the
   upgrades are free), charged once, when the first step has been made;
   Cancel, a paused game or a village that cannot be reached charge nothing.
   Steps pause while the game is paused and go on when it runs again, and
   wait while an island event's popup is open (time_skip_event_open), so the
   Island Events log never gives an event the years a step adds.  The
   rest of a skip is dropped when the player loads another village, starts
   over or deletes the tribe (the same rule as a queued island event), or
   when the village has no one left to advance.  Nothing is written to any
   log: the normal Time Warp writes nothing either, and the births and deaths
   of the skipped years are logged by their own hooks as with a Time Warp.

   THE CLOSING POPUP (the owner, 2026-10-10: "please put an Island-Event
   style popup once the Timeskip has finished").  When the game has replayed
   the LAST step, the game's own island-event popup -- its window, art and
   sound -- says "Time Skip" / "<N> years have passed on the island.", N the
   years the skip advanced.  It is shown exactly as a Custom Island Event is
   (story_custom.inc): a plain event with no changes is armed and the island
   event made due as the Island Event purchase does, and each game's own
   delivery hook fills the popup when its trigger fires -- which it does only
   while the game runs, so a paused game sees it when it runs again.  It
   waits its turn behind a queued pick, custom event or island event (one at
   a time, as always), and for what the game's trigger itself needs (a
   living adult; in A New Home and The Lost Children the village's first
   island event, always a visitor, must have happened).  The trigger's count
   of it in Island Events Seen is taken back on delivery (it is not an island
   event), and it changes nothing, so the Island Events log writes nothing
   for it.  A skip cut short -- another village loaded, Start Over, a deleted
   tribe, or no one left to advance -- shows no popup: a partial skip is not
   "N years have passed", and a village with no one left has no one to show
   an island event to. */

#define TIME_SKIP_MIN_YEARS 1
#define TIME_SKIP_MAX_YEARS 72
#define TIME_SKIP_PRICE 50000          /* the Time Warp upgrade, all five games */
/* A step the villager tick has not visibly replayed after this much RUNNING
   time is taken as replayed: the tick runs every two seconds of the game's
   clock, so only a host whose replay sign failed waits this long.  Running
   time is counted only between two frames that both ran this tick, at most
   TIME_SKIP_FRAME_GAP_MS apart, with the game's clock running (the host's
   time_skip_running), no island event popup open and no time skip box open:
   a modal box, a pause, a minimised game or a popup stops the game's
   villager tick too, so none of that time counts, and a step is never made
   before the game has replayed the one before it -- two Time Warps never
   stack into one catch-up. */
#define TIME_SKIP_SETTLE_MS 20000u
#define TIME_SKIP_FRAME_GAP_MS 250u

enum {
    IDD_TIME_SKIP = 311,
    IDC_TS_YEARS = 3301,
    IDC_TS_NOTE = 3302
};

static struct {
    int active;
    int game;
    int remaining;                     /* years still to advance */
    int waiting;                       /* a step is made, its replay not seen yet */
    DWORD settle_ms;                   /* running time since the step (TIME_SKIP_SETTLE_MS) */
    DWORD last_frame;                  /* the tick of the last frame seen */
    int box_open;                      /* a time skip message box is open */
    story_village village;
    int done;                          /* years advanced so far */
    int finishing;                     /* the last step is made, its replay not seen yet */
    int notice;                        /* years the closing popup is to tell, 0 = none */
} time_skip;

static ce_event time_skip_notice_event;

/* Arms the closing popup for `years` in `game` (see THE CLOSING POPUP).
   1 when armed, 0 when it must wait (the slot is taken or the game's
   trigger could not show it now). */
static int time_skip_notice_arm(int game, int years) {
    const ce_adapter *a = ce_adapter_for(game);
    ce_event *e = &time_skip_notice_event;
    if (a == NULL || !story_installed(game)) {
        return 0;
    }
    drop_lapsed_pick();
    ce_drop_lapsed();
    if (pick_slot >= 0 || ce_armed || GAMES[game].island_pending() || a->arm_refusal() != NULL) {
        return 0;
    }
    memset(e, 0, sizeof *e);
    lstrcpynA(e->title, "Time Skip", sizeof e->title);
    if (years == 1) {
        lstrcpynA(e->text, "1 year has passed on the island.", sizeof e->text);
    } else {
        wsprintfA(e->text, "%d years have passed on the island.", years);
    }
    if (!ce_arm_with(game, e, NULL)) {
        return 0;
    }
    ce_armed_is_notice = 1;
    return 1;
}

/* What Choose Time Skip Amount costs in `game` now: the Time Warp's price,
   or 0 while the Origins upgrades are free. */
static int time_skip_price(int game) {
    return story_installed(game) && charges[game] ? TIME_SKIP_PRICE : 0;
}

/* One step of the skip: the companion's Time Warp for at most `time_skip.
   remaining` years.  Returns the host's answer (years, 0 or -1). */
static int time_skip_step(const story_host *host) {
    int years = host->time_skip_step(time_skip.remaining);
    if (years > 0) {
        if (years > time_skip.remaining) {
            years = time_skip.remaining;
        }
        time_skip.remaining -= years;
        time_skip.done += years;
        time_skip.waiting = 1;
        time_skip.settle_ms = 0;
        time_skip.last_frame = STORY_TICK();
        if (time_skip.remaining <= 0) {
            time_skip.active = 0;
            time_skip.finishing = 1;   /* the popup follows this step's replay */
        }
    }
    return years;
}

#ifdef VVFP_TEST
static int test_island_event_open;     /* VvfpStoryProbeIslandEventOpen */
#endif

/* Whether an island event's popup is open and being logged ("VVFP Island
   Events.dll"'s VvfpIslandEventOpen).  The Secret City, The Tree of Life and
   New Believers show an event inside their presenter's own modal loop, where
   the Origins companion's per-frame path -- and so this tick -- still runs;
   a Time Warp step taken there aged every villager between the event's
   "before" and "after", and the Island Events log gave the event those
   years (live, The Secret City, 2026-10-10: "The Ants and the Granary /
   Choice: Let them be / Age: 694 -> 814" on every villager, the second
   6-year step).  Absent (its row off): never open, nothing held. */
static int time_skip_event_open(void) {
    typedef int (__stdcall *open_fn)(void);
    HMODULE module;
    open_fn open;
#ifdef VVFP_TEST
    if (test_island_event_open) {
        return 1;
    }
#endif
    module = GetModuleHandleA("VVFP Island Events.dll");
    open = module != NULL ? (open_fn)GetProcAddress(module, "VvfpIslandEventOpen") : NULL;
    return open != NULL && open() != 0;
}

/* Called every frame (VvfpStoryInstall): the next step, once the last one
   has been replayed; after the last one, the closing popup. */
static void time_skip_tick(int game) {
    const story_host *host;
    int years;
    DWORD now, gap;
    if (time_skip.game != game || (!time_skip.active && !time_skip.finishing && time_skip.notice == 0)) {
        return;
    }
    now = STORY_TICK();
    gap = now - time_skip.last_frame;
    time_skip.last_frame = now;
    if (time_skip.box_open) {
        return;                        /* the purchase's own box: nothing moves, nothing counts */
    }
    host = story_time_skip_host(game);
    if (host == NULL || !story_village_is(game, &time_skip.village)) {
        /* another village, Start Over, a deleted tribe, or no host: the rest
           of the skip and its popup are dropped */
        time_skip.active = 0;
        time_skip.finishing = 0;
        time_skip.notice = 0;
        return;
    }
    if (time_skip_event_open()) {
        /* An island event's popup is open: nothing moves until it closes.
           The game's villager tick does not run in its modal loop either, so
           none of this time counts toward the replay wait -- never two steps
           in one catch-up because the popup outlasted the lapse. */
        return;
    }
    if (time_skip.active || time_skip.finishing) {
        if (time_skip.waiting) {
            if (gap <= TIME_SKIP_FRAME_GAP_MS && story_host_running(host)) {
                time_skip.settle_ms += gap;
            }
            if (!host->time_skip_settled() && time_skip.settle_ms < TIME_SKIP_SETTLE_MS) {
                return;
            }
            time_skip.waiting = 0;
        }
        if (time_skip.finishing) {
            time_skip.finishing = 0;   /* the last step is replayed: the skip is done */
            time_skip.notice = time_skip.done;
        } else {
            years = time_skip_step(host);
            if (years == 0) {
                time_skip.active = 0;  /* no one left to advance: cut short, no popup */
            }
            /* -1: paused -- the step is tried again next frame. */
            return;
        }
    }
    if (time_skip.notice > 0 && time_skip_notice_arm(game, time_skip.notice)) {
        time_skip.notice = 0;          /* armed: the game's own trigger shows it */
    }
}

/* Starts a skip of `years` in `game`: makes the first step now and charges
   `price` once it is made.  Returns the host's answer for the first step
   (years > 0 on success, 0 nothing to advance, -1 paused); on anything but
   success nothing is charged and no skip is under way. */
static int time_skip_start(int game, int years, int price) {
    const story_host *host = story_time_skip_host(game);
    const ce_adapter *a = ce_adapter_for(game);
    int first;
    if (host == NULL || a == NULL || years < TIME_SKIP_MIN_YEARS || years > TIME_SKIP_MAX_YEARS) {
        return 0;
    }
    time_skip.active = 1;
    time_skip.game = game;
    time_skip.remaining = years;
    time_skip.waiting = 0;
    time_skip.done = 0;
    time_skip.finishing = 0;
    time_skip.notice = 0;
    time_skip.village = story_village_now(game);
    first = time_skip_step(host);
    if (first <= 0) {
        time_skip.active = 0;
        time_skip.finishing = 0;
        return first;
    }
    if (price > 0) {
        a->change_tech(CE_AMOUNT_SUBTRACT, price);
    }
    return first;
}

/* ---- The dialog ------------------------------------------------------------ */

static INT_PTR CALLBACK time_skip_dialog(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    if (message == WM_INITDIALOG) {
        SendDlgItemMessageA(window, IDC_TS_YEARS, EM_LIMITTEXT, 2, 0);
        SetDlgItemInt(window, IDC_TS_YEARS, (UINT)lparam, FALSE);
        SetDlgItemTextA(window, IDC_TS_NOTE,
                        "The village moves forward one Time Warp at a time (3 years on slow, "
                        "6 on normal, 12 on fast), and the game catches up after each: "
                        "villagers work, eat, have babies, grow up and may die of old age, "
                        "just as after a Time Warp. Keep the game running until it is done.");
        SetWindowLongPtrA(window, DWLP_USER, 0);
        SetFocus(GetDlgItem(window, IDC_TS_YEARS));
        SendDlgItemMessageA(window, IDC_TS_YEARS, EM_SETSEL, 0, -1);
        return FALSE;
    }
    if (message == WM_COMMAND) {
        if (LOWORD(wparam) == IDOK) {
            BOOL ok = FALSE;
            UINT years = GetDlgItemInt(window, IDC_TS_YEARS, &ok, FALSE);
            if (!ok || years < TIME_SKIP_MIN_YEARS || years > TIME_SKIP_MAX_YEARS) {
                MessageBoxA(window, "Enter a number of years from 1 to 72.", "Choose Time Skip Amount",
                            MB_OK | MB_ICONINFORMATION);
                SetFocus(GetDlgItem(window, IDC_TS_YEARS));
                SendDlgItemMessageA(window, IDC_TS_YEARS, EM_SETSEL, 0, -1);
                return TRUE;
            }
            EndDialog(window, (INT_PTR)years);
            return TRUE;
        }
        if (LOWORD(wparam) == IDCANCEL) {
            EndDialog(window, 0);
            return TRUE;
        }
    }
    if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* The Choose Time Skip Amount button, called by the Origins companion
   (native/shared/story_bridge.h).  Asks for the years, confirms the price,
   checks the tech points and starts the skip.  Returns 1 when it is under
   way (the companion then closes its menu), 0 otherwise -- nothing charged. */
__declspec(dllexport) int __stdcall VvfpStoryChooseTimeSkip(int game, HWND owner) {
    static const char *const TITLE = "Origins Upgrades";
    const ce_adapter *a = ce_adapter_for(game);
    char message[512];
    char price_text[16];
    int price, years, first;
    if (!story_installed(game) || story_time_skip_host(game) == NULL || a == NULL) {
        return 0;
    }
    if ((time_skip.active || time_skip.finishing) && story_village_is(time_skip.game, &time_skip.village)) {
        if (time_skip.active) {
            wsprintfA(message, "A time skip is already under way (%d more years to go). "
                      "Keep the game running until it is done.", time_skip.remaining);
        } else {
            lstrcpyA(message, "A time skip is just finishing. Keep the game running until it is done.");
        }
        MessageBoxA(owner, message, "Not right now",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    years = (int)DialogBoxParamA(module_instance, MAKEINTRESOURCEA(IDD_TIME_SKIP), owner,
                                 time_skip_dialog, (LPARAM)TIME_SKIP_MIN_YEARS);
    if (years < TIME_SKIP_MIN_YEARS || years > TIME_SKIP_MAX_YEARS) {
        return 0;                      /* Cancel: nothing said, nothing charged */
    }
    price = time_skip_price(game);
    if (price >= 1000) {
        wsprintfA(price_text, "%d,%03d", price / 1000, price % 1000);
    } else {
        wsprintfA(price_text, "%d", price);
    }
    wsprintfA(message,
              "Do you want to buy Choose Time Skip Amount (%d year%s) for %s tech points?\r\n"
              "The village advances %d villager year%s, one Time Warp at a time.\r\n"
              "Press OK to confirm, or Cancel.",
              years, years == 1 ? "" : "s", price_text, years, years == 1 ? "" : "s");
    if (MessageBoxA(owner, message, TITLE, MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND)
        != IDOK) {
        return 0;
    }
    if (a->tech() < price) {
        wsprintfA(message, "This costs %s tech points, and your village has %d.", price_text, a->tech());
        MessageBoxA(owner, message, "Not enough tech points",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    first = time_skip_start(game, years, price);
    if (first <= 0) {
        MessageBoxA(owner,
                    first < 0 ? "Choose Time Skip Amount is unavailable while the game is paused. "
                                "No tech points have been deducted."
                              : "Choose Time Skip Amount could not reach the village records. "
                                "No tech points have been deducted.",
                    TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    /* What is happening now; the island's own popup says when it is done. */
    wsprintfA(message, "The time skip of %d year%s has started. Keep the game running: "
              "an island message will say when it is done.", years, years == 1 ? "" : "s");
    /* The first step is made: while this box is open the game's villager
       tick does not run, so nothing moves and none of it counts toward the
       replay wait (time_skip_tick). */
    time_skip.box_open = 1;
    MessageBoxA(owner, message, TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    time_skip.box_open = 0;
    return 1;
}

/* What the button's label shows: the same price the purchase charges. */
__declspec(dllexport) int __stdcall VvfpStoryTimeSkipPrice(int game) {
    return time_skip_price(game);
}

/* 1 when the popup `game` shows (or showed last) through the custom-event
   path is the closing notice: "VVFP Island Events.dll" then writes nothing
   for it -- it is not an island event, so no record and no event number. */
__declspec(dllexport) int __stdcall VvfpStoryTimeSkipNoticeShown(int game) {
    return game >= 1 && ce_notice_shown == game;
}

#ifdef VVFP_TEST
/* Starts a skip as the purchase does, past the dialog and the prompts, at
   test tick `tick`.  Returns the first step's answer. */
__declspec(dllexport) int __stdcall VvfpStoryProbeTimeSkipStart(int game, int years, DWORD tick) {
    if (game < 1 || game > 5) {
        return 0;
    }
    test_tick = tick;
    install_state[game] = 1;
    return time_skip_start(game, years, time_skip_price(game));
}

/* The skip's state: active, game, remaining years, waiting. */
__declspec(dllexport) void __stdcall VvfpStoryProbeTimeSkipState(int *out) {
    out[0] = time_skip.active;
    out[1] = time_skip.game;
    out[2] = time_skip.remaining;
    out[3] = time_skip.waiting;
}

/* The closing popup's state: years advanced, finishing, years still to be
   armed, and whether the armed custom event is the notice. */
__declspec(dllexport) void __stdcall VvfpStoryProbeTimeSkipNotice(int *out) {
    out[0] = time_skip.done;
    out[1] = time_skip.finishing;
    out[2] = time_skip.notice;
    out[3] = ce_armed && ce_armed_is_notice;
}

/* An island event's popup open (1) or closed (0), as "VVFP Island
   Events.dll" would answer (time_skip_event_open). */
__declspec(dllexport) void __stdcall VvfpStoryProbeIslandEventOpen(int open) {
    test_island_event_open = open;
}

/* The purchase's "has started" box open (1) or closed (0). */
__declspec(dllexport) void __stdcall VvfpStoryProbeTimeSkipBox(int open) {
    time_skip.box_open = open;
}

/* What the upgrade costs in `game` now. */
__declspec(dllexport) int __stdcall VvfpStoryProbeTimeSkipPrice(int game) {
    return time_skip_price(game);
}

/* "Cost Tech Points" on or off for `game` (the install has not run). */
__declspec(dllexport) void __stdcall VvfpStoryProbeCharges(int game, int on) {
    charges[game] = on;
}
#endif
