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
  games save when they are closed normally and every 10 real-life minutes by their autosave.
- **Browse...** beside the save folder picks the game's exe when the window cannot find it or its sources
  disagree. The choice is kept per save folder in the patcher's own settings file
  (`patcher_local_settings.json`, `game_mechanics_exes`), never in the save.
- Closing the window cancels its timer and every callback it scheduled before the window is destroyed.

## Farmers needed

The Vital statistics' food estimates end with "Farmers needed to supply the village with food", for a farmer with
Farming 50 set to one food source (`src/vv_game_mechanics_farmers.py`; the numbers per game in
`src/vv_game_mechanics_farmers_vv1.py` .. `_vv5.py`):

- **While catching up** (time away and Time Warp): each counted age unit every villager who eats has its meal, and
  every working adult gets the game's job turns (5 in A New Home, 4 in the other games), each a whole trip at once
  with no walking. One farmer brings `job turns x trips a turn x (Farming + K)/100 x food a trip` each counted age
  unit (The Secret City's honey also x 11/12, the trips that reach the food bin). Farmers needed = the food eaten
  each counted age unit / that, rounded up.
- **Live**: one farmer brings food once every so many real-life seconds, measured by running the stock game's own
  per-frame villager update, walk and job choices frame by frame (33 ms, the game's 30 frames a second) over the
  game's real map, with failed checks, rests and other jobs included. The trips take the same real-life time at
  Fast, Normal and Slow (nothing in the walk or the waits reads the speed); the eating follows the speed.
- Each source's trip, its steps, its clock, the catch-up rule with addresses and the trip times of elders and
  villagers who like running are under Food earned.

The emulation tests (`tests/test_game_mechanics_farmers_vv1.py` .. `_vv5.py`) re-measure from the stock exes in
`research/stock-executables` and the game data copied into `research/game-data/vvN` (both gitignored); without them
the tests skip. The long re-measurements run only with `VVFP_RELEASE=1`.
