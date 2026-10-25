"""Game Mechanics: the "Time away (catch-up)" group (src/vv_game_mechanics.py, TIME_AWAY), one game at a time.

What the game does with the time that passed while it was closed -- how much of it counts, how it is stepped
through and what every system does while catching up compared with live play -- and, for the save, when it was
last played, paused or not, and how much time away would count if it were opened now.  Read only, like the rest
of the page.  vv_game_mechanics.read adds these lines after the game's own module (catchup_facts).

TIME AND UNITS.  "Real-life" time is the clock on the wall; an age unit is 1/20 of a villager year and takes
60 x the speed value real-life seconds (3, 6 or 10 real-life minutes on Fast, Normal or Slow).

EVIDENCE.  Every rule below is read from the stock game's own reachable code at the addresses given (the owner,
2026-10-24: reachable live code is enough to drop UNCONFIRMED; gm.CODE), from the verified clamp (gm.CLAMP), from
the research spec's emulation (gm.RUNNING), from the owner (gm.OWNER) or from the save (gm.SAVE).  The stock exes
are inputs\\vvN-stock-copy (New Believers SHA-256 92946781...c65d).

NEW BELIEVERS (VV5).  Manager field X is file offset X + 0x10; villager records are 0x2F44 apart in memory
(array 0x554148), each believer's fields at record+0x48 +:
  0x1B8C age (shown), 0x1C34 time not yet counted (real seconds), 0x1C38 its last update (the real clock
  0x4036E0), 0x1C3C processed age, 0x1C40 health, 0x1C48 sick, 0x1C4C pregnant or nursing, 0x1C54 the job the
  player gave, 0x1CC8 the ageing rate (the Time Warp God Power), 0x1CEC Heathen.
  In the save the uncounted time and its stamp are at the villager entry (vv_last_names._entries) + 0x98, + 0x9C.
* 0x46FE90 (every update, from 0x4260E1): for each living villager the time since its last update is added to
  its uncounted time, then the clamp (0x46FFAB-0x470013, gm.AWAY_LIMITS); paused (speed >= 999) sets it to 0
  (0x47002E).  Believers only (0x470077) get uncounted ÷ 60 x rate ÷ speed whole age units added to the shown
  age at once (0x46F7F0); the rest under one unit is kept (0x4700B9-0x4700E2).  Time cut by the clamp is gone.
* 0x472C90 (from 0x4260EB, the same update): every villager whose processed age is behind steps one unit; the
  pass repeats (0x47336A -> 0x472CA0) until no one is behind, so all of it runs inside that one update.  Heathens
  are skipped (0x472CB7).  Each unit: Faith 0x468040, Divine Energy 0x424F80, eating 0x472D66, health and
  sickness 0x472F7C-0x472FC1, old age 0x472FC6-0x47304A, birth 0x4730AF.  While more than 2 units behind
  (0x4732EB), an adult (shown age >= 280 units) not sick and not pregnant or nursing gets 4 job turns 0x46E8E0
  (0x473311-0x473326) with the catch-up flag manager+0x17E10 set (0x47330A).
* 0x46E8E0: health >= 20 (0x46E90B); the live chooser 0x46A3C0; Children: rand(100) <= 5 and the population
  check 0x472BD0, then embrace; a job the player gave continues through 0x46BCF0; at food <= 250 Farming 20+
  farms (0x46E985), with no "Worried about food".  Steps run at once by 0x46E020 (table 0x46E230/0x46E244):
  4 walk -> instant move 0x466300; 10 skill check, 18-20 work payoffs, 31-34 projects (31 builds, 0x43B080)
  through the live executor 0x473B30; 16 conception 0x46E078 (rand(300) + 50 - 50 x Medicine <= Breeding,
  0x46E094-0x46E0C8; no Love Shack, no skill check, no hungry refusal, no first-time pass, no over-50 rule for
  the one who starts it); 25 cure 0x46E1A2 (Healing skill check only; People Cured +1 even on a failure,
  0x46E202); every other step is skipped.
* 0x425E30 (before the ageing): paused, the island-event, noni and crop timers move on by the paused time
  (0x425E45-0x425E7E); running, every missed noni tick (+2, cap 1,000, 0x425F64) and crop refill (to 800,
  0x425ED3 / 0x4260F7) is run back to back with no limit, and each noni tick also runs the Nursery School
  (0x425F80-0x4260A7): a child under 280 units gets the teacher's (job 8, 0x43AA06) six-skill total x speed ÷
  14,400 (1440.0 at 0x498B38, 10.0 at 0x498B30), half the time to its highest skill (0x4755C0; rand(6) when all
  are 0) if below 50, otherwise a fifth (5.0 at 0x498810) to each skill below 50.
* Research (event 19): the catch-up flag skips the 10% lab accident (0x46DB80 -> 0x46DC67) but not the 2%
  injury roll at 0x46DC67-0x46DC91; the divisors ÷7/÷7/÷5 and no speed factor (0x46DC96-0x46DE3B).
* Island events 0x442790-0x442834: the timer is real-life time; when due the event runs once and the next is
  set 8 to 15 hours from then (or 30 minutes while none has been seen).
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm

G = gm.TIME_AWAY
CODE, CLAMP, OWNER, SAVE, RUNNING = gm.CODE, gm.CLAMP, gm.OWNER, gm.SAVE, gm.RUNNING


def facts(village: gm.Village) -> list[gm.Fact]:
    game = _GAMES.get(village.game)
    return game(village) if game else []


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _patch(village: gm.Village, feature: str, normal: str, patched: str) -> gm.Fact | None:
    """A patch that changes a catch-up rule: the stock rule first, then the patched one (the owner, 2026-10-24);
    None when the patch is known not to be in the game."""
    has = village.has(feature)
    if has is False:
        return None
    state = "is in the game" if has else "may be in the game (it could not be told)"
    return gm.Fact(G, f"{normal} The patcher's \"{gm.feature_name(feature)}\" {state}: {patched}", CODE)


def _limits_words(speed: int) -> tuple[int, int, int, int]:
    limits = gm.AWAY_LIMITS[5]
    return limits["full"][speed], limits["band"], limits["band_end"], limits["over"]


def _pending_lines(village: gm.Village, speed_value: int, entries: list[tuple[int, float]],
                   unit: float, unit_word: str, who: str = "villager") -> list[gm.Fact]:
    """This save: the uncounted time kept for each villager, what would count if it were played now, and the two
    moments the counted time changes (live countdowns).  `entries`: (uncounted seconds, the real moment of its
    last update) for each living villager (believer) -- each one's time away runs from its own stamp."""
    out: list[gm.Fact] = []
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    if not entries:
        return out
    kept = sorted({p for p, _s in entries})
    words = gm.duration(kept[0], exact=True) if len(kept) == 1 else \
        f"{gm.duration(kept[0], exact=True)} to {gm.duration(kept[-1], exact=True)}"
    after = ("the game sets it to 0 as soon as it is loaded paused" if paused else
             "it is counted with the next time away")
    out.append(gm.Fact(G, f"Kept in the save: {words} of time not yet counted for each {who} (less than one age "
                          f"unit, {unit_word}; {after}).", SAVE))
    if paused:
        return out
    full, band, band_end, over = _limits_words(speed)

    def counted(pending: int, stamp: float) -> float:
        total = pending + max(0.0, village.now - stamp)   # a stamp ahead of the clock is reset to now (0x46FF7B)
        return total if total <= full else (band if total <= band_end else over)

    units = sorted({int(counted(p, s) // unit) for p, s in entries})
    ages = f"{units[0]:,} age units ({units[0] / 20:.2f} villager years)" if len(units) == 1 else \
        f"{units[0]:,} to {units[-1]:,} age units ({units[0] / 20:.2f} to {units[-1] / 20:.2f} villager years)"
    out.append(gm.Fact(G, (f"If it were played now each {who} would age {ages} at once, all worked through in the "
                           "first update after it loads."), SAVE))
    # The moments for the villagers last updated latest (the save's own last moment), the most of them.
    stamps: dict[float, list[int]] = {}
    for p, s in entries:
        stamps.setdefault(s, []).append(p)
    stamp = max(stamps, key=lambda s: (len(stamps[s]), s))
    pending = max(stamps[stamp])
    full_at = stamp + full - pending
    band_at = stamp + band_end - pending
    if village.now < full_at:
        out.append(gm.Fact(G, f"Time away counts in full until {gm.DUE}; from then until "
                              f"{gm.when(band_at)} only {gm.duration(band, exact=True)} counts.", SAVE,
                           due=full_at, due_kind="ends"))
    elif village.now < band_at:
        out.append(gm.Fact(G, f"Time away now counts as {gm.duration(band, exact=True)} until {gm.DUE}; from "
                              f"then on as {gm.duration(over)}.", SAVE, due=band_at, due_kind="ends"))
    else:
        out.append(gm.Fact(G, f"Time away now counts as {gm.duration(over)} however much longer the game stays "
                              "closed.", SAVE))
    return out


# ---------------------------------------------------------------------------
# New Believers (VV5)
# ---------------------------------------------------------------------------

VV5_SPEED, VV5_LAST = 0x17D8C, 0x17D60
VV5_PENDING, VV5_FACTION, VV5_HEALTH = 0x98, -0x1F, 0xA4      # from a villager entry (vv_last_names._entries)
VV5_WORK_FIRST = "vv5_builders_and_healers_work_first"
VV5_FIX_HUTS = "vv5_builders_fix_huts"
VV5_LEARNING = "vv5_learning_never_fails"
VV5_NURSERY = "vv5_vv4_nursery_divisor_parity"
VV5_STORY = "vv5_story_cheat_upgrades"
VV5_ORIGINS = "vv5_enable_origins_exclusive_features"


def _entries(village: gm.Village, pending_at: int, health_at: int, faction_at: int | None = None
             ) -> list[tuple[int, int, int]]:
    """(uncounted seconds, its stamp on the save's real clock) for each living villager (each believer, with
    `faction_at`), read from the villager entries as Last Names finds them; [] when the table cannot be read."""
    try:
        import vv_last_names
        found = vv_last_names._entries(village.game, village.data)
    except Exception:  # noqa: BLE001 -- a villager table that cannot be read gives no per-villager line
        return []
    out = []
    data = village.data
    for at in found:
        low = at + min(0, faction_at or 0)
        if low < 0 or at + max(pending_at + 8, health_at + 4) > len(data):
            continue
        if (faction_at is not None and data[at + faction_at] != 0) or _i32(data, at + health_at) <= 0:
            continue                                   # a Heathen, or a grave
        pending, stamp = struct.unpack_from("<iI", data, at + pending_at)
        if 0 <= pending <= 86_400:
            out.append((pending, stamp))
    return out


def _later_save(village: gm.Village, speed_at: int, last_at: int, paused_words: str,
                entries: list[tuple[int, int]], who: str) -> tuple[list[gm.Fact], int] | None:
    """The Tree of Life's and New Believers' save lines (int64 clock base at 0x08): when it was last played, the
    verified clamp's rule, the uncounted time kept and what would count now.  (lines, speed value), or None for
    a save that is not this game's.  `entries`: _entries (stamps on the save's clock)."""
    import vv_save_backup
    data = village.data
    found = vv_save_backup.save_speed(village.game, data)
    if found is None or found[0] != speed_at:
        return None
    speed_value = found[1]
    speed = gm.speed_base(speed_value)
    unit = 60 * speed
    unit_word = f"{gm.duration(unit)} of real-life time on {gm.speed_name(speed)} speed"
    base = struct.unpack_from("<q", data, 8)[0]
    last = base + _i32(data, last_at)
    out = gm.time_away(village, last, speed_value, paused_words, unit_seconds=20 * unit)
    out = [gm.Fact(f.group, f.text, CODE) if f.text.startswith("Saved paused:") else f for f in out]
    if not village.general:
        out += _pending_lines(village, speed_value, [(p, float(base + s)) for p, s in entries], unit, unit_word,
                              who)
    return out, speed_value


def _vv5(village: gm.Village) -> list[gm.Fact]:
    done = _later_save(village, VV5_SPEED, VV5_LAST,
                       "Saved paused: none of the time it stays closed will count. While paused the game sets every "
                       "villager's uncounted time to 0 each update and moves the noni, crop and island-event timers "
                       "on by the paused time; the fire and the weather stop with the game's clock.",
                       _entries(village, VV5_PENDING, VV5_HEALTH, VV5_FACTION), "believer")
    if done is None:
        return []
    out, speed_value = done
    add = lambda text, ok=CODE: out.append(gm.Fact(G, text, ok))  # noqa: E731

    # How it is counted and stepped through.
    add("How it counts: each villager keeps its own clock. Every update the real-life time since that villager's "
        "last update is added to its uncounted time, then cut to the limits above; what is cut off is lost and "
        "never counted later. Only believers then age: the counted time ÷ the length of an age unit (3, 6 or 10 "
        "real-life minutes on Fast, Normal or Slow) is added to the age shown at once, and what is left under one "
        "age unit is kept for the next update.")
    add("How it is stepped through: in that same update the game runs the counted age units one at a time for "
        "every believer, over and over until no one is behind, so all of the catch-up happens in the first update "
        "after the village loads, before the next picture is drawn. No in-game time passes while it runs; how many "
        "real-life seconds it takes depends on the computer (one pass of the life rules per believer per age unit, "
        "plus the job turns below).")
    add("Each counted age unit, for each believer, exactly as in live play: Faith rises or falls, Divine Energy is "
        "earned, food is eaten, health is regained or lost, sickness may start, the old-age death roll is made at "
        "each birthday past the limit, and babies due are born (twins and triplets as live). The ages shown, logs "
        "and graves therefore jump at once, and every death, birth and Heathen of the time away happens in that "
        "first update.")
    add("Work: for every counted age unit except the last 2, each believer aged 14 or more (by the age shown after "
        "the time away is added) who is not sick, not pregnant or nursing and has 20 health or more gets 4 job "
        "turns. A job turn uses the game's own job choice, and a job the player gave keeps going; walks become "
        "instant moves, and the skill checks, the work's food, tech points and Divine Energy, and the building "
        "steps all run, while every other step (animations, waits, talk, play, rest) is skipped. Live play has no "
        "job turns of this kind: villagers walk and work in real time.")
    add("Food while catching up: at 250 food or less a believer with Farming 20 or more farms first, as in live "
        "play, but nobody stops to be \"Worried about food\". A crop harvest gives 7 food at any speed (live: 10, 7 "
        "or 4 on Fast, Normal or Slow). Noni are picked only once the granary is made and The Hungry Totem is "
        "solved (live: the granary alone). Fishing gives 4 food, as live.")
    add("Research while catching up: nobody researches until The Knowing Totem is solved (live: any time). A "
        "success gives the skill ÷ 7, ÷ 7 or ÷ 5 at Science 1, 2 or 3, the same at every speed (live: ÷ 11, ÷ 9 or "
        "÷ 7, times 2 on Fast and 0.6 on Slow). The 10% lab accident (sparks only) is skipped, but the 2% chance "
        "of losing 0 to 9 health on each research success stays, as in live play.")
    add("Babies while catching up: a believer whose job choice is Children tries on 6 job turns in 100, if the "
        "population limit allows; the partner search is the live one (opposite sex, both 18 or more, the partner "
        "under 50 and not sick, pregnant or nursing). A baby is conceived when rand(300) + 50 - 50 x Medicine "
        "level is at most the Breeding skill (17%, 33% or 50% at Breeding 50 and Medicine 1, 2 or 3). Unlike live "
        "play there is no embrace skill check, no Love Shack needed, no refusal when food is low, the village's "
        "first conception is not certain, and a woman of 50 or more who starts it can still conceive.")
    add("Healing while catching up: a cure is the healer's Healing skill check alone (live: a healer who dislikes "
        "medicine also fails half the cures), and People Cured goes up even when the cure fails (live: only on a "
        "success).")
    add("Building while catching up: the build steps run, so huts, the statue, totems and other projects advance "
        "as in live play, with no walking to the site.")
    add("Honoring while catching up pays its Divine Energy (3, 7 or 12) as in live play; preaching to Heathens, "
        "Spreading the Word and every other live-only behaviour do not happen.")
    add("Heathens while catching up: they never age, eat or work, and their Faith does not change; a believer whose "
        "Faith falls to 0 during the catch-up becomes a Heathen then and stops ageing.", CODE)
    add("Heathens never age, while catching up or otherwise (the stock game's design).", OWNER)
    add("Nursery School: for every missed noni regrowth (one per age unit of the WHOLE time closed, with no limit) "
        "each child under 14 learns from the Nursery School teacher: the teacher's six skills added together x the "
        "speed value (3, 6 or 10) ÷ 14,400, half the time all to the child's highest skill (a random one while "
        "every skill is 0) if it is below 50, otherwise a fifth of that to every skill below 50. This is the live "
        "rule, run for the whole time closed; it runs before the time away is added to the ages, so a child who "
        "turns 14 during it learns for all of it.")
    nursery = _patch(village, VV5_NURSERY, "Normally the spread share is a fifth.",
                     "a sixth instead, one for each of the six skills.")
    if nursery:
        out.append(nursery)
    add("Noni and crops: every missed noni regrowth (+2 each age unit) and crop refill (to 800 every 40 age units, "
        "once the Hydroponic Farm is built) of the WHOLE time closed is added when it is next played, with no "
        "limit: noni stop at 1,000, crops at 800.")
    add("Island events: their timer runs on real-life time, so the whole time closed counts. If an event came due "
        "while the game was closed it happens once when the village is next played, and the next one is set 8 to "
        "15 whole real-life hours after that (30 minutes while no event has been seen yet).")
    add("Mushrooms and collectibles: none appear for the time closed. The appearance roll (18 in 32,768) is made "
        "once per update of the village, so the catch-up's one update gives one roll, like any other update.",
        RUNNING)
    add("The fire and the weather follow the game's own clock, which keeps running while the game is closed "
        "unpaused: the fire burns down (10, 20 or 33 hours 20 minutes of real-life time on Fast, Normal or Slow) "
        "and a weather spell ends, by the whole time closed, not only the counted part.", RUNNING)
    add("The campfire keeps burning down while the game is closed, when the save was left unpaused.", OWNER)
    add("Graves: the whole time closed counts toward a body's removal, not only the counted part (see Death and "
        "graves).")
    add("The Time Warp God Power (500 Divine Energy) speeds up ageing for 5 real-life minutes while the game is "
        "open; quitting during them loses the rest (see Hidden villager stats).", RUNNING)

    # The patches that change a catch-up rule (stock rule first).
    for fact in (
        _patch(village, VV5_WORK_FIRST, "Normally every job turn uses the game's own choice.",
               "on 75 job turns in 100 a builder (while it has hut work), a healer, or a believer whose job is "
               "Devotion (when Honoring is allowed) does that job first; at 250 food or less a believer with "
               "Farming 20 or more still farms first."),
        _patch(village, VV5_FIX_HUTS, "Normally a builder in a job turn joins only a site already more than 1% "
                                      "built, and examines huts only once Houses 1 to 3 and the Clothing Hut stand.",
               "when the job turn's job is building, the patch's build-first and hut-fixing rules apply to it."),
        _patch(village, VV5_LEARNING, "Normally a skill check in a job turn succeeds (skill + 34) times in 100.",
               "every skill check succeeds, in job turns too."),
    ):
        if fact:
            out.append(fact)
    if village.has(VV5_ORIGINS) is not False:
        warp = gm.time_warp_line(speed_value)
        out.append(gm.Fact(G, warp.text + " It is worked through like time away, in the first update after it.",
                           warp.verified))
    story = _patch(village, VV5_STORY, "The stock game has no time skip.",
                   "Choose Time Skip Amount skips 1 to 72 villager years as a run of Time Warps (12, 6 or 3 years "
                   "each on Fast, Normal or Slow, the last only what is left), each caught up before the next.")
    if story:
        out.append(story)
    return out


# ---------------------------------------------------------------------------
# The Tree of Life (VV4)
# ---------------------------------------------------------------------------

VV4_SPEED, VV4_LAST = 0x17120, 0x17100
VV4_PENDING, VV4_HEALTH = 0x98, 0xA4                         # from a villager entry (vv_last_names._entries)
VV4_WORK_FIRST = "vv4_builders_and_healers_work_first"
VV4_FIX_HUTS = "vv4_builders_fix_huts"
VV4_LEARNING = "vv4_learning_never_fails"
VV4_STORY = "vv4_story_cheat_upgrades"
VV4_ORIGINS = "vv4_enable_origins_exclusive_features"


def _vv4(village: gm.Village) -> list[gm.Fact]:
    """The Tree of Life (stock exe SHA-256 6d27a429...b220): the same design as New Believers at its own addresses
    -- the clamp and ageing 0x466450 (0x466538-0x4665FD; the ghost flag +0x1CC7 skipped at 0x46646E), from
    0x420556; the life tick 0x468430 (from 0x420560), repeated until no one is behind (0x468B09 -> 0x468440);
    job turns 0x465750 x 4 (0x468A24-0x468A75, flag game+0x171A4); the Fruitwells bonus 0x468A7A-0x468AC5; the
    step resolver 0x464FA0 (table 0x4651B0/0x4651C4: 3 walk -> move 0x45ECB0, 9 skill check, 15 conception
    0x464FF8, 24 cure 0x465122-0x465182, the rest of 17-19 and 29-32 through 0x46A4D0); research 0x464C08 /
    0x464C3E (÷7/÷7/÷5; the flag skips the 10% lab accident but not the 2% injury at 0x464BB0); the world tick
    0x420330 (paused: island event and world tick moved on by the pause, 0x42034A-0x42036F; running: every
    missed tick replayed, +2 berries to 1,000, stream debris +2% 0x4203E7, the Nursery School 0x4203F3-0x420515:
    the teacher's (job 8) five-skill total x speed ÷ 14,400, half to the highest skill (rand(5) when all are 0),
    otherwise ÷ 5.0 (0x48D678) to each skill below 50, ghosts and adults excluded); fruit gathering refused while
    catching up (0x463A30); the ghost visit 0x414260 (more than 1 hour overdue: reset, nothing spawns)."""
    done = _later_save(village, VV4_SPEED, VV4_LAST,
                       "Saved paused: none of the time it stays closed will count. While paused the game sets every "
                       "villager's uncounted time to 0 each update and moves the world tick (berries, stream, "
                       "Nursery School) and the island-event timer on by the paused time; the fire and the weather "
                       "stop with the game's clock.",
                       _entries(village, VV4_PENDING, VV4_HEALTH), "villager")
    if done is None:
        return []
    out, speed_value = done
    add = lambda text, ok=CODE: out.append(gm.Fact(G, text, ok))  # noqa: E731

    add("How it counts: each villager keeps its own clock. Every update the real-life time since that villager's "
        "last update is added to its uncounted time, then cut to the limits above; what is cut off is lost and "
        "never counted later. The counted time ÷ the length of an age unit (3, 6 or 10 real-life minutes on Fast, "
        "Normal or Slow) is added to the age shown at once, and what is left under one age unit is kept for the "
        "next update. The mausoleum's ghosts are skipped: they never age, eat or work.")
    add("How it is stepped through: in that same update the game runs the counted age units one at a time for "
        "every villager, over and over until no one is behind, so all of the catch-up happens in the first update "
        "after the village loads, before the next picture is drawn. No in-game time passes while it runs; how many "
        "real-life seconds it takes depends on the computer (one pass of the life rules per villager per age unit, "
        "plus the job turns below).")
    add("Each counted age unit, for each villager, exactly as in live play: food is eaten, health is regained or "
        "lost, sickness may start (and on Easy may clear), the old-age death roll is made at each birthday past "
        "the limit, and babies due are born (twins and triplets as live). The ages shown, logs and graves "
        "therefore jump at once, and every death and birth of the time away happens in that first update.")
    add("Work: for every counted age unit except the last 2, each villager aged 14 or more (by the age shown after "
        "the time away is added) who is not sick, not pregnant or nursing and has 20 health or more gets 4 job "
        "turns. A job turn uses the game's own job choice, and a job the player gave keeps going; walks become "
        "instant moves, and the skill checks, the work's food and tech points and the building steps all run, "
        "while every other step (animations, waits, talk, play, rest) is skipped. Live play has no job turns of "
        "this kind: villagers walk and work in real time.")
    add("Fruitwells while catching up: once the Fruitwells are restored, after its 4 job turns each such villager "
        "also gets 5 food (times Food Mastery) and a Farming skill check, if its player-given task is the game's farming task 2 "
        "(one of its seven farming tasks), or else with a chance of (Farming - 25) in 100. In live play fruit comes only from villagers shaking it "
        "down, 3 food a load, and that is never chosen while catching up.")
    add("Food while catching up: at 250 food or less a villager with Farming 20 or more farms first, as in live "
        "play, but nobody stops to be \"Worried about food\". Blackberry picking (the bush ÷ 100, at least 2) and "
        "fishing (4 food) give what they give live.")
    add("Research while catching up: a success gives the skill ÷ 7, ÷ 7 or ÷ 5 at Science 1, 2 or 3, the same at "
        "every speed (live: ÷ 11, ÷ 9 or ÷ 7, times 2 on Fast and 0.6 on Slow). The 10% lab accident (sparks only) "
        "is skipped, but the 2% chance of losing 0 to 9 health on each research success stays, as in live play.")
    add("Babies while catching up: a villager whose job choice is Children tries on 6 job turns in 100; the "
        "partner search is the live one (opposite sex, both 18 or more, the partner under 50 and not sick or "
        "pregnant), and the population limit and huts apply as live. A baby is conceived when rand(300) + 50 - "
        "50 x Medicine level is at most the Parenting skill (17%, 33% or 50% at Parenting 50 and Medicine 1, 2 or "
        "3). Unlike live play there is no embrace skill check, no Love Shack needed, no refusal when food is low, "
        "the village's first embrace does not skip the roll, and a woman of 50 or more who starts it can still "
        "conceive.")
    add("Healing while catching up: a cure is the healer's Healing skill check alone (live: a healer who dislikes "
        "medicine also fails half the cures), and People Cured goes up even when the cure fails (live: only "
        "on a success).")
    add("Building while catching up: the build steps run, with the walk to the site turned into an instant move, "
        "so huts and the other buildings advance as in live play.")
    add("Nursery School: for every missed world tick (one per age unit of the WHOLE time closed, with no limit) "
        "each child under 14 learns from the Nursery School teacher: the teacher's five skills added together x the "
        "speed value (3, 6 or 10) ÷ 14,400 (the teacher's total ÷ 240 per real-life hour at any speed), half the "
        "time all to the child's highest skill (a random one while every skill is 0) if it is below 50, otherwise "
        "a fifth of that to every skill below 50. This is the live rule, run for the whole time closed; it runs "
        "before the time away is added to the ages, so a child who turns 14 during it learns for all of it.")
    add("Blackberries and the stream: every missed world tick of the WHOLE time closed is added when it is next "
        "played, with no limit: +2 blackberries each (up to 1,000) and 2% more of the stream's debris.")
    add("Island events: their timer runs on real-life time, so the whole time closed counts. If an event came due "
        "while the game was closed it happens once when the village is next played, and the next one is set 8 to "
        "15 whole real-life hours after that (30 minutes while no event has been seen yet).", RUNNING)
    add("Ghost visits (the Mausoleum Mural Collection complete): their 50 to 58 real-life minute timer is not "
        "caught up. When the village is next played more than 1 hour after a visit was due, the timer is reset to "
        "0 to 8 minutes and no ghost comes for the time closed.", RUNNING)
    add("Mushrooms and collectibles: none appear for the time closed. The appearance rolls are made once per update "
        "of the village, so the catch-up's one update gives one set of rolls, like any other update.", RUNNING)
    add("The fire and the weather follow the game's own clock, which keeps running while the game is closed "
        "unpaused: the Fire Pit burns down (10, 20 or 33 hours 20 minutes of real-life time on Fast, Normal or "
        "Slow) and a weather spell, fog included, ends, by the whole time closed, not only the counted part.")
    add("The campfire keeps burning down while the game is closed, when the save was left unpaused.", OWNER)
    add("Graves: the whole time closed counts toward a body's removal, not only the counted part (see Death and "
        "graves).")

    for fact in (
        _patch(village, VV4_WORK_FIRST, "Normally every job turn uses the game's own choice.",
               "on 75 job turns in 100 a builder (while it has hut work) or a healer does that job first; at 250 "
               "food or less a villager with Farming 20 or more still farms first."),
        _patch(village, VV4_FIX_HUTS, "Normally a builder in a job turn joins only a building already more than 1% "
                                      "built, and examines huts only once Huts 1 to 3 and the Clothing Hut stand.",
               "when the job turn's job is building, the patch's build-first and hut-fixing rules apply to it."),
        _patch(village, VV4_LEARNING, "Normally a skill check in a job turn succeeds (skill + 34) times in 100.",
               "every skill check succeeds, in job turns too."),
    ):
        if fact:
            out.append(fact)
    _warp_lines(village, out, speed_value, VV4_ORIGINS, VV4_STORY)
    return out


def _warp_lines(village: gm.Village, out: list[gm.Fact], speed_value: int, origins: str, story: str) -> None:
    """The Origins Time Warp and the Story / Cheat time skip, when they may be in the game."""
    if village.has(origins) is not False:
        warp = gm.time_warp_line(speed_value)
        out.append(gm.Fact(G, warp.text + " It is worked through like time away, in the first update after it.",
                           warp.verified))
    fact = _patch(village, story, "The stock game has no time skip.",
                  "Choose Time Skip Amount skips 1 to 72 villager years as a run of Time Warps (12, 6 or 3 years "
                  "each on Fast, Normal or Slow, the last only what is left), each caught up before the next.")
    if fact:
        out.append(fact)


_GAMES = {4: _vv4, 5: _vv5}
