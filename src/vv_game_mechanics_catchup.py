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

    most = max(int(counted(p, s) // unit) for p, s in entries)   # one shape for every save (the claims export)
    out.append(gm.Fact(G, (f"If it were played now each {who} would age by at most {most:,} age units ({most / 20:.2f} "
                           "villager years) at once, all worked through in the first update after it loads."), SAVE))
    # Each villager crosses the limits at its own moments (its own stamp and kept time), so the state is counted
    # villager by villager, and the countdown is to the next crossing of any of them.  One sentence shape for every
    # state (the claims export renders a save at two moments only).
    in_full = cut = whole_day = 0
    crossings: list[float] = []
    for p, s in entries:
        total = p + max(0.0, village.now - s)
        if total <= full:
            in_full += 1
        elif total <= band_end:
            cut += 1
        else:
            whole_day += 1
        crossings += [t for t in (s + full - p, s + band_end - p) if t > village.now]
    out.append(gm.Fact(G, (f"Counted now, {who} by {who}: {in_full:,} in full, {cut:,} cut to "
                           f"{gm.duration(band, exact=True)}, {whole_day:,} cut to {gm.duration(over)}."), SAVE))
    if crossings:
        out.append(gm.Fact(G, f"The next {who}'s time away crosses a limit at {gm.DUE}.", SAVE,
                           due=min(crossings), due_kind="next"))
    else:
        out.append(gm.Fact(G, f"Every {who}'s time away now counts as {gm.duration(over)}, however much longer the "
                              "game stays closed.", SAVE))
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


def _entries(village: gm.Village, pending_at: int, health_at: int, faction_at: int | None = None,
             family_skip: tuple[int, int] | None = None) -> list[tuple[int, int]]:
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
        if family_skip is not None and 0 <= at + family_skip[0] and _i32(data, at + family_skip[0]) == family_skip[1]:
            continue                                   # A New Home's Golden Child: never counts time away
        pending, stamp = struct.unpack_from("<iI", data, at + pending_at)
        if 0 <= pending <= 86_400:
            out.append((pending, stamp))
    return out


def _later_save(village: gm.Village, speed_at: int, last_at: int, paused_words: str,
                entries: list[tuple[int, int]], who: str, base: int | None = None
                ) -> tuple[list[gm.Fact], int] | None:
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
    if base is None:
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
        "after the village loads, before the next picture is drawn. How many real-life seconds "
        "it takes depends on the computer (one pass of the life rules per believer per age unit, "
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
        "after the village loads, before the next picture is drawn. How many real-life seconds "
        "it takes depends on the computer (one pass of the life rules per villager per age unit, "
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


# ---------------------------------------------------------------------------
# The Secret City (VV3)
# ---------------------------------------------------------------------------

VV3_LAST = 0x12F08                                           # file offset: wall seconds from the epoch (+4)
VV3_PENDING, VV3_HEALTH = 0x98, 0xA4                         # from a villager entry (vv_last_names._entries)
VV3_WORK_FIRST = "vv3_builders_and_healers_work_first"
VV3_FIX_HUTS = "vv3_builders_fix_huts"
VV3_LEARNING = "vv3_learning_never_fails"
VV3_FIX_VANILLA = "vv3_fix_vanilla_bugs"
VV3_MORTALITY = "vv3_nature_level_three_alters_mortality"
VV3_STORY = "vv3_story_cheat_upgrades"
VV3_ORIGINS = "vv3_enable_origins_exclusive_features"


def _vv3(village: gm.Village) -> list[gm.Fact]:
    """The Secret City (stock exe SHA-256 8bc5db38...6503): the clamp and ageing 0x45F3E0 (0x45F4BB-0x45F588),
    the aging loop 0x45FFE0 (from 0x428CA0) repeated until no one is behind (0x4605CE -> 0x45FFF0), job turns
    0x45BF00 x 4 (0x46051F-0x460580: more than 2 units behind, not sick, not pregnant or nursing, age >= 280, not
    a look-alike record, and none for the Tribal Chief, +0xE80 at 0x460555; flag game+0x12FB4), the instant
    runner 0x45B790 (walk -> move 0x455EB0 at 0x45B7D7; conception 0x45B7EB-0x45B8C9; cure 0x45B91E-0x45B971);
    the partner search 0x45CE00 (both 18 to 49, 0x45CE3C-0x45CE7A); fruit and honey 4 while catching up
    (0x434ABB / 0x431BE8), fish 8 (0x458E90-0x458EBA); research ÷4/÷7/÷7/÷5 and the 2% injury with no catch-up
    test (0x45916D-0x459191); huts: the hut job skips its walks while catching up (0x4539CF, 0x453A2D, 0x453B1E,
    0x453B73) and a build step credits only the hut the builder stands in (0x432680)."""
    epoch = struct.unpack_from("<I", village.data, 4)[0] if len(village.data) >= 8 else 0
    import vv_save_backup
    found = vv_save_backup.save_speed(3, village.data)
    if found is None:
        return []
    done = _later_save(village, found[0], VV3_LAST,
                       "Saved paused: none of the time it stays closed will count. While paused the game sets every "
                       "villager's uncounted time to 0 each update, the game's clock (fruit trees, honey) is stopped "
                       "and the next island event is pushed back by the paused time.",
                       _entries(village, VV3_PENDING, VV3_HEALTH), "villager", base=epoch)
    if done is None:
        return []
    out, speed_value = done
    add = lambda text, ok=CODE: out.append(gm.Fact(G, text, ok))  # noqa: E731

    add("How it counts: each villager keeps its own clock. Every update the real-life time since that villager's "
        "last update is added to its uncounted time, then cut to the limits above; what is cut off is lost and "
        "never counted later. The counted time ÷ the length of an age unit (3, 6 or 10 real-life minutes on Fast, "
        "Normal or Slow) is added to the age shown at once, and what is left under one age unit is kept for the "
        "next update.")
    add("How it is stepped through: in that same update the game runs the counted age units one at a time for "
        "every villager, over and over until no one is behind, so all of the catch-up happens in the first update "
        "after the village loads, before the next picture is drawn. How many real-life seconds "
        "it takes depends on the computer (one pass of the life rules per villager per age unit, "
        "plus the job turns below).")
    add("Each counted age unit, for each villager, exactly as in live play: food is eaten, health is regained or "
        "lost, sickness may start, the old-age death roll is made at each birthday past the limit, and babies due "
        "are born (twins and triplets as live). The ages shown, logs and graves therefore jump at once, and every "
        "death and birth of the time away happens in that first update.")
    add("Work: for every counted age unit except the last 2, each villager aged 14 or more (by the age shown after "
        "the time away is added) who is not sick, not pregnant or nursing and has 20 health or more gets 4 job "
        "turns; the Tribal Chief gets none. A job turn uses the game's own job choice, and a job the player gave "
        "keeps going; walks become instant moves, and the skill checks, the work's food and tech points and the "
        "building steps all run, while every other step (animations, waits, talk, play, rest) is skipped. Live "
        "play has no job turns of this kind: villagers walk and work in real time.")
    add("Food while catching up: at 250 food or less a villager with Farming 20 or more farms first, as in live "
        "play, but nobody stops to be \"Worried about food\". Fruit and honey give 4 food a pick at any speed (live: "
        "7, 3 or 2 on Fast, Normal or Slow), fishing 8 (live: 11, 8 or 5).")
    add("Research while catching up: a success gives the skill ÷ 4, ÷ 7, ÷ 7 or ÷ 5 at Science 0, 1, 2 or 3, the "
        "same at every speed (live: ÷ 5, ÷ 11, ÷ 9 or ÷ 7, scaled by the speed). The 2% chance of losing 0 to 9 "
        "health on each research success happens while catching up too.")
    add("Babies while catching up: a villager whose job choice is Children tries on 6 job turns in 100; the "
        "partner search is the live one (opposite sex, both 18 to 49, the partner not sick, and neither pregnant "
        "or nursing), and the population limit and huts apply as live. A baby is conceived when rand(300) + 50 - "
        "50 x Medicine level is at most the Parenting skill. Unlike live play there is no embrace skill check, no "
        "refusal when food is low, no fertility potion bonus, and the village's first conception does not skip "
        "the roll.")
    add("Healing while catching up: a cure is the healer's Healing skill check alone (live: a healer who dislikes "
        "medicine also fails half the cures), and People Cured goes up even when the cure fails (live: only on a "
        "success).")
    add("Building while catching up: the other projects walk to their site (an instant move) and advance as in "
        "live play, but the population huts hardly grow: the hut job skips its walk to the hut while catching up, "
        "and a build step adds to a hut only when the builder already stands on that hut's site.")
    fix = _patch(village, VV3_FIX_VANILLA, "That is the stock game.",
                 "each builder goes to the hut first while catching up too, so the work is added to that hut.")
    if fix:
        out.append(fix)
    add("Fruit trees and honey: they follow the game's own clock, which keeps running while the game is closed "
        "unpaused, so they get the WHOLE time closed when it is next played, with no limit on how many refills: "
        "a tree stops at 1,000 fruit, the honey at 3,000.", RUNNING)
    add("Potions: saving the game ends every villager's potion effects, and the pot (with a brewed potion) is not "
        "saved, so nothing from a potion carries over the time away.", RUNNING)
    # The scheduler 0x468727 on the wall clock: nothing resets it when the game starts (an earlier line said the
    # first event of each start sets the next 30 minutes later; the 30 minutes follow only the village's first event
    # ever, 0x468899, as Island events says).
    add("Island events: their timer runs on real-life time, so the whole time closed counts. If an event came due "
        "while the game was closed it happens once when the village is next played, and the next comes 8 to 15 whole "
        "real-life hours after it (30 real-life minutes after the village's first event ever).", RUNNING)
    add("The Tribal Chief's powers: their 23-hour wait runs on real-life time, so the time closed counts in full.",
        RUNNING)
    add("Mushrooms and collectibles: none appear for the time closed. The appearance roll is made once per update "
        "of the village, so the catch-up's one update gives one roll, like any other update.", RUNNING)
    add("The campfire keeps burning down while the game is closed, when the save was left unpaused.", OWNER)
    add("Graves: the whole time closed counts toward a body's removal, not only the counted part (see Death and "
        "graves).")

    for fact in (
        _patch(village, VV3_WORK_FIRST, "Normally every job turn uses the game's own choice.",
               "on 75 job turns in 100 a builder (while it has hut work) or a healer does that job first; at 250 "
               "food or less a villager with Farming 20 or more still farms first."),
        _patch(village, VV3_FIX_HUTS, "Normally a builder in a job turn joins only a site already 2% or more "
                                      "built, and examines huts only once all four huts stand.",
               "when the job turn's job is building, the patch's build-first and hut-fixing rules apply to it."),
        _patch(village, VV3_LEARNING, "Normally a skill check in a job turn succeeds (skill + 34) times in 100.",
               "every skill check succeeds, in job turns too."),
        _patch(village, VV3_MORTALITY, "Normally the old-age rolls start at 47, 55, 63 or 71 years (Medicine 0 to "
                                       "3).", "at Nature level 3 they start 7 years later, while catching up too."),
    ):
        if fact:
            out.append(fact)
    _warp_lines(village, out, speed_value, VV3_ORIGINS, VV3_STORY)
    return out


# ---------------------------------------------------------------------------
# The Lost Children (VV2)
# ---------------------------------------------------------------------------

VV2_LAST = 0x2EAE4 + 4                                       # file offset (state + 4): the last tick
VV2_PENDING, VV2_HEALTH = -0x40, -0x38                       # from a villager entry (vv_last_names._entries)
VV2_WORK_FIRST = "vv2_builders_and_healers_work_first"
VV2_FIX_HUTS = "vv2_builders_fix_huts"
VV2_LEARNING = "vv2_learning_never_fails"
VV2_FIX_VANILLA = "vv2_fix_vanilla_bugs"
VV2_STUDY = "vv2_healers_study_regardless_of_food"
VV2_EASIER = "vv2_easier_healing_mastery"
VV2_STORY = "vv2_story_cheat_upgrades"
VV2_ORIGINS = "vv2_enable_origins_exclusive_features"


def _vv2(village: gm.Village) -> list[gm.Fact]:
    """The Lost Children (stock exe SHA-256 46c1503c...d677): the clamp and ageing in the world tick
    (0x43B819-0x43B95F; the Esteemed Elder totems, +0x558, skipped at 0x43B7FD); the life loop 0x43BA70-0x43C0BB
    repeated until no one is behind; job turns 0x43B4D0 x 4 (0x43BF94-0x43BFF5, flag state+0x3046C; health >= 20
    at 0x43B50D); the step simulator 0x464680 (table 0x464CA0/0x464CB4: 6 skill step, 12 embrace scan, 17
    payoff, 20 cure scan; every walk and wait is skipped).  Skill steps of Parenting and Healing get no check of
    their own (0x464780-0x46479A); a Healing step has a Healing-in-1,500 chance (0x4646D7) of a scan that cures
    the first sick villager whose check passes (0x464700-0x46477A); the cure step checks the healer once per
    villager and cures every sick one that passes (0x4647C2-0x464840).  The embrace scan (0x464847-0x464A4E and
    again 0x464A54-) goes through every villager without stopping at a conception: both 18+, the woman under 50,
    health > 0, neither nursing nor sick, the 34% refusal under 300 food (0x46490C), the initiator's Parenting
    check (0x46493A), rand(300) + 50 - 50 x Medicine <= Parenting (0x464947-0x464974), the child's 10 to 19
    points (0x464998-0x4649C9).  Yields 4/7/8 and research ÷7/÷6/÷4 keyed on the flag (callbacks 27-29, 31); the
    research injury 0x46361B has no test; building progress halved (the callbacks)."""
    import vv_save_backup
    found = vv_save_backup.save_speed(2, village.data)
    if found is None:
        return []
    epoch = struct.unpack_from("<I", village.data, 4)[0]
    done = _later_save(village, found[0], VV2_LAST,
                       "Saved paused: none of the time it stays closed will count. While paused the game sets every "
                       "villager's uncounted time to 0 each update, and the regrowth, the fire and the next island "
                       "event are pushed back by the paused time; the Gong of Wonder's rest is not.",
                       _entries(village, VV2_PENDING, VV2_HEALTH), "villager", base=epoch)
    if done is None:
        return []
    out, speed_value = done
    add = lambda text, ok=CODE: out.append(gm.Fact(G, text, ok))  # noqa: E731

    add("How it counts: each villager keeps its own clock. Every update the real-life time since that villager's "
        "last update is added to its uncounted time, then cut to the limits above; what is cut off is lost and "
        "never counted later. The counted time ÷ the length of an age unit (3, 6 or 10 real-life minutes on Fast, "
        "Normal or Slow) is added to the age shown at once, and what is left under one age unit is kept for the "
        "next update. The Esteemed Elder totems are skipped: they never age.")
    add("How it is stepped through: in that same update the game runs the counted age units one at a time for "
        "every villager, over and over until no one is behind, so all of the catch-up happens in the first update "
        "after the village loads, before the next picture is drawn. How many real-life seconds it takes depends on "
        "the computer (one pass of the life rules per villager per age unit, plus the job turns below).")
    add("Each counted age unit, for each villager, exactly as in live play: food is eaten, health is regained or "
        "lost, sickness may start, the old-age death roll is made at each birthday past the limit, and nursed "
        "babies grow into children. The ages shown, logs and graves therefore jump at once, and every death and "
        "birth of the time away happens in that first update.")
    add("Work: for every counted age unit except the last 2, each villager aged 14 or more (by the age shown after "
        "the time away is added) who is not sick, not nursing and has 20 health or more gets 4 job turns. A job "
        "turn uses the game's own job choice, and a job the player gave keeps going; every walk and wait is "
        "skipped and the skill checks and the work's payoffs run at once. Live play has no job turns of this kind: "
        "villagers walk and work in real time.")
    add("Food while catching up: a successful trip brings 4 coconuts, 7 crops or 8 fish at any speed (live: the "
        "same on Normal, 8, 10 or 11 on Fast and 2, 4 or 5 on Slow).")
    add("Research while catching up: a success gives the skill ÷ 7, ÷ 6 or ÷ 4 at Science 1, 2 or 3, the same at "
        "every speed (live: ÷ 11, ÷ 9 or ÷ 5, twice that on Fast and half on Slow). The 2% chance of losing 0 to "
        "9 health on each research success happens while catching up too.")
    add("Building while catching up: each successful try adds half as much (1 instead of 2).")
    add("Babies while catching up: a villager whose job choice is Children tries on 6 job turns in 100. The try "
        "goes through the whole village twice and does not stop at a conception: with each villager of the other "
        "sex (both 18 or more, the woman under 50, neither sick or nursing) it is refused 34 times in 100 when food "
        "is under 300, then needs the initiator's Parenting check, then a baby is conceived when rand(300) + 50 - "
        "50 x Medicine level is at most the Parenting skill, as long as the population limit and huts allow. So "
        "one man's job turn can make several women mothers. Each baby gets 10 to 19 points in one parent's best "
        "skill (live: 5 to 7, or 4 to 11 by Culture level when both parents' best skill is the same); live, "
        "the partner found must be under 50 whatever the sex.")
    add("Healing while catching up: a cure step checks the healer's Healing once for every villager and cures "
        "every sick villager (not the healer) whose check passes, so one job turn can cure the whole village, and "
        "each passed check trains Healing (live: one patient, after one Healing check). A Healing skill step "
        "(healing work, or studying a plant) gets no check of its own: only a chance of the healer's Healing in "
        "1,500 sends it looking for the first sick villager whose check passes. So a healer learns almost no "
        "Healing from its practice while catching up, and plant study does not continue.")
    for fact in (
        _patch(village, VV2_FIX_VANILLA, "That is the stock game.",
               "a healer's Healing practice (healing work, or studying a plant) runs while catching up as in live "
               "play."),
        _patch(village, VV2_STUDY, "Normally plant study never continues while catching up.",
               "a villager who was studying a plant carries on, at any food level, half the time each time a job "
               "turn chooses what it does (14 times in 100 for one whose job is not Healing)."),
        _patch(village, VV2_EASIER, "Normally healers study plants only when the game's own choice sends them.",
               "healers and villagers who prefer Healing study plants when no sick villager needs treatment, in "
               "job turns too."),
    ):
        if fact:
            out.append(fact)
    add("Regrowth: every coconut and crop regrowth missed while the game was closed is added when it is next "
        "played, with no limit on how many: coconuts stop at 1,500, crops at 800.", RUNNING)
    add("A stew cooking when the game is closed is lost: the save does not keep the pot.", SAVE)
    add("Island events: their timer runs on real-life time, so the whole time closed counts. If an event came due "
        "while the game was closed it happens once when the village is next played.", RUNNING)
    add("The Gong of Wonder's 24-hour rest runs on real-life time, so the time closed counts in full, paused or "
        "not.", RUNNING)
    add("Mushrooms and collectibles: none appear for the time closed; they appear only on live updates of the "
        "village.", RUNNING)
    add("The campfire keeps burning down while the game is closed, when the save was left unpaused.", OWNER)
    add("Graves: the whole time closed counts toward a body's removal, not only the counted part (see Death and "
        "graves).")

    for fact in (
        _patch(village, VV2_WORK_FIRST, "Normally every job turn uses the game's own choice.",
               "on 75 job turns in 100 a builder (while it has hut work) or a healer does that job first."),
        _patch(village, VV2_FIX_HUTS, "Normally a builder in a job turn follows the game's own building "
                                      "choice.",
               "when the job turn's job is building, the patch's build-first, hut-fixing and new-hut rules apply."),
        _patch(village, VV2_LEARNING, "Normally a skill check in a job turn succeeds (skill + 34) times in 100.",
               "every skill check succeeds, in job turns too."),
    ):
        if fact:
            out.append(fact)
    _warp_lines(village, out, speed_value, VV2_ORIGINS, VV2_STORY)
    out.append(gm.Fact(G, "A Time Warp also brings the regrowth, the fire, the next island event and the Gong 10 "
                          "hours (Slow) or 12 hours (Normal, Fast) sooner."))
    return out


# ---------------------------------------------------------------------------
# A New Home (VV1)
# ---------------------------------------------------------------------------

VV1_LAST = 0xA308                                            # file offset: the save moment
VV1_PENDING, VV1_HEALTH, VV1_FAMILY = -0x34, -0x2C, -0x04    # from a villager entry (vv_last_names._entries)
VV1_GOLDEN = 199
VV1_WORK_FIRST = "vv1_builders_and_healers_work_first"
VV1_FIX_HUTS = "vv1_builders_fix_huts"
VV1_LEARNING = "vv1_learning_never_fails"
VV1_FIX_VANILLA = "vv1_fix_vanilla_bugs"
VV1_STUDY = "vv1_healers_study_regardless_of_food"
VV1_EASIER = "vv1_easier_healing_mastery"
VV1_WATERING = "vv1_watering_trains_building"
VV1_MAGIC_FRUIT = "vv1_magic_fruit_alters_mortality"
VV1_STORY = "vv1_story_cheat_upgrades"
VV1_ORIGINS = "vv1_enable_origins_exclusive_features"


def _vv1(village: gm.Village) -> list[gm.Fact]:
    """A New Home (stock exe SHA-256 1ec790b9...f03d): the clamp and ageing in the world tick 0x42E900
    (0x42EA37-0x42EB6E; the Golden Child, family 199, set back to 100 age units and nothing pending every update,
    0x42EB70-0x42EB98); the life loop 0x42EC55-0x42F162 repeated until no one is behind; job turns 0x42E790 x 5
    (0x42F0E6-0x42F12A: more than 2 units behind, not sick, not pregnant, age >= 280; health >= 20 at 0x42E7C5);
    Children: rand(100) <= 5 (0x42E7E5) then the embrace queued and run at once by 0x446C70 (opcode 9: two scans
    0x446E70-0x44704F and 0x447055-0x447256, each going on past a conception 0x43BBC0; the 74% refusal under 400
    food 0x446F26/0x447118; the Parenting check and rand(300) <= Parenting - 50 + 50 x Fertility 0x446F5B/0x44715C);
    healing: opcode 17 0x446DD0-0x446E65 (a check per villager, every sick villager of 280 units or more that
    passes is cured), opcode 6 Healing 0x446CCF (rand(1500) < Healing).  A New Home has no catch-up flag: food and
    research pay as live (0x43AD62, 0x43AEC5, 0x43F4A7, 0x43B2AB)."""
    import vv_save_backup
    found = vv_save_backup.save_speed(1, village.data)
    if found is None:
        return []
    epoch = struct.unpack_from("<I", village.data, 4)[0]
    done = _later_save(village, found[0], VV1_LAST,
                       "Saved paused: none of the time it stays closed will count. While paused the game sets every "
                       "villager's uncounted time to 0 each update, and the regrowth and island event timers move "
                       "on with the paused time.",
                       _entries(village, VV1_PENDING, VV1_HEALTH, family_skip=(VV1_FAMILY, VV1_GOLDEN)), "villager",
                       base=epoch)
    if done is None:
        return []
    out, speed_value = done
    add = lambda text, ok=CODE: out.append(gm.Fact(G, text, ok))  # noqa: E731

    add("How it counts: each villager keeps its own clock. Every update the real-life time since that villager's "
        "last update is added to its uncounted time, then cut to the limits above; what is cut off is lost and "
        "never counted later. The counted time ÷ the length of an age unit (3, 6 or 10 real-life minutes on Fast, "
        "Normal or Slow) is added to the age shown at once, and what is left under one age unit is kept for the "
        "next update.")
    add("The Golden Child counts no time away: every update sets him back to 5 years with nothing pending, so he "
        "is always five, and he gets no job turns (see Golden Child).")
    add("How it is stepped through: in that same update the game runs the counted age units one at a time for "
        "every villager, over and over until no one is behind, so all of the catch-up happens in the first update "
        "after the village loads, before the next picture is drawn. How many real-life seconds it takes depends on "
        "the computer (one pass of the life rules per villager per age unit, plus the job turns below).")
    add("Each counted age unit, for each villager, exactly as in live play: food is eaten, health is regained or "
        "lost, sickness may start, the old-age death roll is made at each birthday past the limit, and babies due "
        "are born (twins and triplets as live). The ages shown, logs and graves therefore jump at once, and every "
        "death and birth of the time away happens in that first update.")
    add("Work: for every counted age unit except the last 2, each villager aged 14 or more (by the age shown after "
        "the time away is added) who is not sick, not pregnant and has 20 health or more gets 5 job turns. A job "
        "turn uses the game's own job choice; the walks and waits are skipped and the skill checks and the work's "
        "payoffs run at once. A New Home has no catch-up rates of its own: berries, crops, fish and research pay "
        "what they pay live. Live play has no job turns of this kind: villagers walk and work in real time.")
    add("Babies while catching up: a villager whose job choice is Children tries on 6 job turns in 100. The try "
        "goes through the whole village twice and does not stop at a conception: with each villager of the other "
        "sex (both 18 or more, not sick or pregnant; no upper age for either) it is refused 74 times in 100 below "
        "400 food, then needs the initiator's Parenting check, then a baby is conceived when rand(300) is at most "
        "Parenting - 50 + 50 x Fertility level, as long as the population limit and huts allow. So one man's job "
        "turn can make several women pregnant (live: the lowest-numbered partner only, after walking to them).")
    add("Healing while catching up: a cure step checks the healer's Healing ((Healing + 31) in 100) once for every "
        "villager and cures every sick villager of 14 or more whose check passes, so one job turn can cure all the "
        "sick adults (live: one patient of any age). A Healing skill step (healing work, or studying the medical "
        "cactus) gets no check of its own: only a chance of the healer's Healing in 1,500 sends it looking for a "
        "sick adult to cure. So a healer learns almost no Healing from its practice while catching up, and sick "
        "children are not cured.")
    for fact in (
        _patch(village, VV1_FIX_VANILLA, "That is the stock game.",
               "a healer's Healing practice (healing work, or studying the medical cactus) runs while catching up as "
               "in live play."),
        _patch(village, VV1_STUDY, "Normally cactus study continues while catching up only when a job turn happens "
                                   "to give that villager healing work while no one is sick.",
               "a villager who was studying the cactus carries on, at any food level, half the time each time a job "
               "turn chooses what it does (14 times in 100 for one whose job is not Healing)."),
        _patch(village, VV1_EASIER, "Normally healers study the cactus only when the game's own choice sends them.",
               "healers and villagers who prefer Healing study the cactus whenever they get healing work and no one "
               "is sick, in job turns too."),
        _patch(village, VV1_WATERING, "Normally \"Watering the field\" gives no Building skill.",
               "each watering that advances the garden puzzle ends with a Building practice roll, in job turns "
               "too."),
    ):
        if fact:
            out.append(fact)
    add("Regrowth: every regrowth missed while the game was closed is added when it is next played, with no limit "
        "on how many: the berry bush has no cap, the crop field stops at 800.", RUNNING)
    add("Island events: their timer runs on real-life time, so the whole time closed counts; after time away at "
        "most one event happens.", RUNNING)
    add("Mushrooms: none appear for the time closed; they are not saved and appear only on live updates (a "
        "2-in-120 roll every 2 real-life seconds while none is out).", RUNNING)
    add("Graves: the whole time closed counts toward a body's removal, not only the counted part (see Death and "
        "graves).")
    for fact in (
        _patch(village, VV1_WORK_FIRST, "Normally every job turn uses the game's own choice.",
               "on 75 job turns in 100 a builder (while it has hut work) or a healer does that job first."),
        _patch(village, VV1_FIX_HUTS, "Normally a builder in a job turn follows the game's own building choice.",
               "when the job turn's job is building, the patch's build-first, hut-fixing and new-hut rules apply."),
        _patch(village, VV1_LEARNING, "Normally a skill check in a job turn succeeds (skill + 31) times in 100.",
               "every skill check succeeds, in job turns too."),
        _patch(village, VV1_MAGIC_FRUIT, "Normally the old-age rolls start at 55, 63 or 71 years (Medicine 1 to 3).",
               "with the Magic Fruit of Life puzzle done they start 7 years later, while catching up too."),
    ):
        if fact:
            out.append(fact)
    _warp_lines(village, out, speed_value, VV1_ORIGINS, VV1_STORY)
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


_GAMES = {1: _vv1, 2: _vv2, 3: _vv3, 4: _vv4, 5: _vv5}
