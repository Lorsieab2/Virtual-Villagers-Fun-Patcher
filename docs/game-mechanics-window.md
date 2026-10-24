# Game Mechanics window: live countdowns, Refresh, and the game's exe

The window is `src/vv_game_mechanics_window.py`; the shared page and renderer are `src/vv_game_mechanics.py`;
each game's facts come from `src/vv_game_mechanics_vv<N>.py`.

## A fact with a moment still to come

A `Fact` may carry two optional fields:

| field      | meaning |
|------------|---------|
| `due`      | the moment, as absolute real time in Unix seconds (work it out from `village.now` and the save's clock), or `None` |
| `due_kind` | what happens then, one word: `"refill"`, `"ready"`, `"ends"`, `"due"`, `"starts"`, `"next"` (`gm.DUE_KINDS`) |

The page shows the moment's date and time and, right after it on the same bullet, a live countdown:

    • Honey: 40 of 100; the next refill is 24 October 2026, 3:14 PM (in 12 min 03 s).

The window ticks every countdown once a second from one shared timer and reads no file to do it. At zero the
words become `..., due now (refresh to see the new state)`, because the game's real state is only known again
from the save.

Where the date goes:

1. The text holds `gm.DUE` (`"{due}"`): the date and the countdown replace it.
   `Fact("Refills", f"Honey: 40 of 100; the next refill is {gm.DUE}.", gm.SAVE, due=t, due_kind="refill")`
2. The text already holds `gm.when(due)`: the countdown goes right after it.
3. Neither: `<Kind>: <date> (countdown).` is added at the end of the line, `<Kind>` from `due_kind`
   (`Next refill`, `Ready`, `Ends`, `Due`, ...).

A fact whose clock is stopped (saved paused, a frozen clock) passes `due=None` and keeps its own words
("once unpaused"). It gets no countdown. A fact with a `due` is left out of a game's general rules
(`gm.general`), since those have no village.

`gm.render(facts, now)` gives the text as it reads at `now`. `gm.render_live(facts, now)` also returns a
`gm.Countdown(line, column, length, due)` for each countdown, which is what the window ticks.
`gm.countdown(due, now)` is the countdown's own words.

## The window

- **Refresh** reads every source again (the save, the patcher's logs, the save folder's `.dat` files and logs,
  the game's exe as it is now) and restarts the countdowns. It keeps the tab, the save folder, the tribe and
  the scroll position. The other tabs are read again when they are next shown.
- **Auto-refresh** (off by default) does the same every 30 seconds, from the same one-second timer.
- The top of each tab says when the save was last written. If the game for the save is running (looked for
  read-only in the list of running programs), it says that the values are from the last save, because the
  games save only when they are closed normally.
- **Browse...** beside the save folder picks the game's exe when the window cannot find it or its sources
  disagree. The choice is kept per save folder in the patcher's own settings file
  (`patcher_local_settings.json`, `game_mechanics_exes`), never in the save.
- Closing the window cancels its timer and every callback it scheduled before the window is destroyed.
