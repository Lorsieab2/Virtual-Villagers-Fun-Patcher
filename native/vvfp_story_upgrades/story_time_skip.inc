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
   Steps pause while the game is paused and go on when it runs again.  The
   rest of a skip is dropped when the player loads another village, starts
   over or deletes the tribe (the same rule as a queued island event), or
   when the village has no one left to advance.  Nothing is written to any
   log: the normal Time Warp writes nothing either, and the births and deaths
   of the skipped years are logged by their own hooks as with a Time Warp. */

#define TIME_SKIP_MIN_YEARS 1
#define TIME_SKIP_MAX_YEARS 72
#define TIME_SKIP_PRICE 50000          /* the Time Warp upgrade, all five games */
/* A step the villager tick has not visibly replayed after this long is taken
   as replayed: the tick runs every two seconds of the game's clock, so only
   a game that is not running at all waits this long. */
#define TIME_SKIP_SETTLE_MS 20000u

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
    DWORD step_tick;
    story_village village;
} time_skip;

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
        time_skip.waiting = 1;
        time_skip.step_tick = STORY_TICK();
        if (time_skip.remaining <= 0) {
            time_skip.active = 0;
        }
    }
    return years;
}

/* Called every frame (VvfpStoryInstall): the next step, once the last one
   has been replayed. */
static void time_skip_tick(int game) {
    const story_host *host;
    int years;
    if (!time_skip.active || time_skip.game != game) {
        return;
    }
    host = story_time_skip_host(game);
    if (host == NULL || !story_village_is(game, &time_skip.village)) {
        time_skip.active = 0;          /* another village, or no host: dropped */
        return;
    }
    if (time_skip.waiting) {
        if (!host->time_skip_settled() && STORY_TICK() - time_skip.step_tick < TIME_SKIP_SETTLE_MS) {
            return;
        }
        time_skip.waiting = 0;
    }
    years = time_skip_step(host);
    if (years == 0) {
        time_skip.active = 0;          /* no one left to advance */
    }
    /* -1: paused -- the step is tried again next frame. */
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
    time_skip.village = story_village_now(game);
    first = time_skip_step(host);
    if (first <= 0) {
        time_skip.active = 0;
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
    if (time_skip.active && story_village_is(time_skip.game, &time_skip.village)) {
        wsprintfA(message, "A time skip is already under way (%d more years to go). "
                  "Keep the game running until it is done.", time_skip.remaining);
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
    if (time_skip.active) {
        wsprintfA(message, "Advanced %d years. The other %d follow as the game catches up; "
                  "keep the game running until it is done.", first, years - first);
    } else {
        wsprintfA(message, "Advanced %d year%s.", years, years == 1 ? "" : "s");
    }
    MessageBoxA(owner, message, TITLE, MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* What the button's label shows: the same price the purchase charges. */
__declspec(dllexport) int __stdcall VvfpStoryTimeSkipPrice(int game) {
    return time_skip_price(game);
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

/* What the upgrade costs in `game` now. */
__declspec(dllexport) int __stdcall VvfpStoryProbeTimeSkipPrice(int game) {
    return time_skip_price(game);
}

/* "Cost Tech Points" on or off for `game` (the install has not run). */
__declspec(dllexport) void __stdcall VvfpStoryProbeCharges(int game, int on) {
    charges[game] = on;
}
#endif
