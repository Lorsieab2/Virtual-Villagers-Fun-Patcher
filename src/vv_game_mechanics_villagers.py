"""Game Mechanics: the Villagers group -- every living villager the save holds, one by one, in all five games (the
owner, 2026-11-26: "please add heathen info in game mechanics, as detailed as the believers. plus their current faith
and time until conversion cooldown expires" and "add villagers' faith and health too!").

Each villager is one bullet -- name, sex, age, health and, in New Believers, Faith -- with sub-bullets for the skills,
likes and dislikes, parents, a pregnancy, and the titles the patcher keeps.  New Believers lists the tribe first, then
every Heathen outside it with the same details and, besides, the mask, the camp role, how far their Faith is from
joining and their preaching wait.  Everything is read from the save (the fields of src/vv_game_mechanics_life.py
and src/vv_last_names.FIELDS) or from the patcher's own Custom Titles file and logs (src/vv_villager_info.py); the
rules each value means are the ones the other groups already cite.

NEW BELIEVERS' PREACHING WAIT, read from the stock exe (SHA-256 92946781...C65D):
  * the wait is the villager's own dword +0x1CF4: the moment, on the game's real-time clock, from which the Heathen
    listens again.  The sermon's end (the work event 0x468DA0) reads it at 0x468E19 and, while it is later than the
    clock (0x468E2B, unsigned "jbe"), the sermon fails with the "tired of listening" message (0x142) and the
    tip "You can only try to convert each heathen once ..." (0x2DF, 735); else, after the preacher's Devotion check,
    the Heathen gets +3..+5 Faith and the wait is set to the clock + 0x1C20 (7,200 s) at 0x468F2A / 0x468F33;
  * the same + 7,200 is set by Spreading the Word for its listener (0x46D2D8 / 0x46D2E4) and by the Earthquake God
    Power for every Heathen it reaches (0x41F7B8 / 0x41F7BD; the six puzzle roles are skipped at 0x41F78F); a new
    villager starts at 0 (0x468470); the village drawing clears an expired wait to 0 (0x4729D1..0x4729EB) and draws
    the "glowy light" over a Heathen whose wait still runs; a puzzle spot's handler also turns a tired Heathen away
    (0x4383CA);
  * the clock is 0x4036E0: _time64 (0x47C96A, GetSystemTimeAsFileTime) less the start time 0x4C6250, in whole
    seconds -- real time, the same at every speed, running while the game is paused or closed.  The start time is
    the time stamp in the save file's header (bytes 8..15: read by 0x403770 into 0x4C6248.., written back by every
    save, 0x4039D8), so the wait's moment is that stamp + the wait, in Unix seconds;
  * the save keeps it: the entry writer 0x465270 copies +0x1CF4 to entry +0x114 (0x465346 / 0x46534C), the loader
    puts it back (0x466C1D / 0x466C23) -- the name is at entry +0x20, so the wait is the name + 0xF4.
No patch of the patcher changes the 7,200 (the Fog of Doom listening patch keeps the same wait test).

Read only: nothing here writes anything.
"""
from __future__ import annotations

import math
import struct

import vv_game_mechanics as gm

GROUP = gm.VILLAGERS
YEAR = 20

# New Believers' saved entry, from the name (the writer 0x465270): faction +1, orange +2, red +3, Faith +8, role +0xC,
# the preaching wait +0x114 -- the name at +0x20.
VV5_FACTION, VV5_ORANGE, VV5_RED, VV5_ROLE, VV5_WAIT = -0x1F, -0x1E, -0x1D, -0x14, 0xF4
WAIT_SECONDS = 0x1C20                          # 0x468F2A, 0x46D2D8, 0x41F7B8
HEADER_STAMP = 8                               # the save header's time stamp (int64), the clock's start
PUZZLE_ROLES = {12: "the Heathen Doctor", 13: "the Heathen Chief", 14: "the Heathen Master Scientist",
                15: "the Heathen Master Builder", 16: "the Heathen Master Farmer", 17: "the Heathen Mommy"}
# How each puzzle Heathen joins (vv_game_mechanics_faith_vv5: the cure 0x468CFB, The Heathen Chief 0x4360EE, the
# Hydroponic Farm 0x439E35, the Heathen Mommy's puzzle 0x43979C).
PUZZLE_JOIN = {12: "joins when cured (The Sick Heathen puzzle), which sets Faith to 25 to 59",
               13: "joins when The Heathen Chief puzzle is solved, which sets Faith to 100",
               14: "joins through The Heathen Scientist puzzle",
               15: "joins through The Heathen Builder puzzle",
               16: "joins when the Hydroponic Farm is restored, which adds 80 Faith",
               17: "joins through the Heathen Parent puzzle"}
SERMON = (3, 5)                                # preaching's Faith: +3, +4 at Devotion 50, +5 at 88 (0x468F2F)


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def _u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def _number(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text if text != "-0" else "0"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def mask(data: bytes, at: int) -> str:
    """The mask the game draws on a Heathen (0x4728C6): by role, then the orange and red kind bytes, else blue."""
    role = _i32(data, at + VV5_ROLE)
    if role in (12, 14, 15, 16):
        return "purple"
    if role == 13:
        return "the Chief's"
    if data[at + VV5_ORANGE]:
        return "orange"
    if data[at + VV5_RED]:
        return "red"
    return "blue"


def role_words(role: int, colour: str) -> str:
    """A Heathen's place in the camp, in the game's own words where it has them (the tutorial's tips 678, 680, 682)."""
    if role in PUZZLE_ROLES:
        return f"{PUZZLE_ROLES[role]} (a puzzle Heathen)"
    return {"orange": "a heathen guard (orange: chases believers away)",
            "red": "a senior heathen guard (red: so scary that believers run)"}.get(
        colour, "an ordinary Heathen (blue: can be preached to)")


def clock_start(data: bytes) -> int | None:
    """The save header's time stamp: the start of New Believers' real-time clock (0x403770 -> 0x4C6250)."""
    if len(data) < HEADER_STAMP + 8:
        return None
    return struct.unpack_from("<q", data, HEADER_STAMP)[0]


def preaching_ready(data: bytes, at: int) -> tuple[int, float | None]:
    """(the saved wait, the real moment in Unix seconds it ends, or None when there is no wait or no clock start)."""
    wait = _u32(data, at + VV5_WAIT)
    start = clock_start(data)
    if wait == 0 or start is None:
        return wait, None
    return wait, float(start + wait)


def _titles(village: gm.Village) -> dict:
    try:
        import vv_villager_info
        return vv_villager_info.village_titles(village.folder, village.game, village.slot) or {}
    except Exception:  # noqa: BLE001 -- unreadable titles file or logs: no titles line, nothing else lost
        return {}


def _prefs(game: int, data: bytes, at: int) -> tuple[str, str] | None:
    try:
        import vv_lost_titles as lt
        got = lt._prefs(data, at, game)
        return lt.list_text(game, got["Likes"]), lt.list_text(game, got["Dislikes"])
    except Exception:  # noqa: BLE001
        return None


def health_words(ctx, p) -> str:
    """The health value and the sick mark, as the save holds them (a Heathen's sick mark costs no health)."""
    words = f"health {p.health} of 100" + (", sick" if p.sick else "")
    if p.sick and not p.heathen and not p.golden:
        words += (" (near death: at 20 or less a sick villager loses health more slowly)" if p.health <= 20 else
                  " (see Villager timers for when health would reach 0)")
    return words


def _detail_lines(ctx, p, data: bytes, titles: dict, add) -> None:
    import vv_corrupt_skills as cs
    import vv_last_names as ln
    game = ctx.game
    f = ln.FIELDS[game]
    names = cs.SKILL_NAMES[game]
    if len(p.skills) == len(names):
        add("Skills: " + ", ".join(f"{name} {_number(v)}" for name, v in zip(names, p.skills))
            + (f"; ticked job: {p.ticked}" if p.ticked else "") + ".", gm.SAVE)
    else:
        add("Skills: not readable in the save (Repair Saves & Logs can reset them).", gm.SAVE)
    prefs = _prefs(game, data, p.at)
    if prefs is not None:
        add(f"Likes: {prefs[0]}. Dislikes: {prefs[1]}.", gm.SAVE)
    if f.father is not None and f.mother is not None:
        father = ln._cstr(data, p.at + f.father, f.parent_cap)
        mother = ln._cstr(data, p.at + f.mother, f.parent_cap)
        if father or mother:
            add(f"Parents: father {father or '(none kept)'}, mother {mother or '(none kept)'}.", gm.SAVE)
        else:
            add("Parents: none kept in the save (a founder, a newcomer or a villager the game made without parents).",
                gm.SAVE)
    if p.carrying:
        left = max(0, p.conceived + 41 - p.processed)
        father = f" by {p.father}" if p.father else ""
        babies = {1: "1 baby", 2: "twins", 3: "triplets"}.get(p.babies, f"{p.babies} babies")
        if p.heathen:
            when = ("the game's age-unit update, where babies are born, skips Heathens, so the birth waits while they "
                    "are a Heathen")
        else:
            when = f"{_plural(left, 'age unit')} to go on the game's clock (see Nursing and pregnancy)"
        add(f"Pregnant / nursing: {babies}{father}; {when}.", gm.SAVE)
    head, body = _i32(data, p.at + f.head), _i32(data, p.at + f.body)
    got = titles.get((p.name, head, body), {})
    parts = [f"{label} \"{got[key]}\"" for key, label in (("custom", "Custom title"), ("special", "Special title"))
             if got.get(key)]
    if parts:
        add("Titles: " + "; ".join(parts) + " (the patcher's Custom Titles file and logs).", gm.SAVE)


def _ages(p) -> str:
    years = p.age // YEAR
    return f"{_plural(years, 'villager year')} ({p.age:,} age units on the game's clock)"


def lines(ctx, everyone: list) -> list[gm.Fact]:
    """The Villagers group for one save (nothing for a game's general page)."""
    village = ctx.village
    if village.general or not everyone:
        return []
    out: list[gm.Fact] = []
    game, data = ctx.game, village.data

    def add(text: str, ok=gm.SAVE, sub: bool = False, due: float | None = None, kind: str | None = None) -> None:
        out.append(gm.Fact(GROUP, text, ok, sub, due, kind))

    titles = _titles(village)
    tribe = [p for p in everyone if not p.heathen]
    heathens = [p for p in everyone if p.heathen]
    high, low = ctx.sick_loss
    # The rules the values mean, as Death and graves and Food sources give them.
    rule = (f"Health runs from 0 to 100 and a villager dies when it reaches 0 (see Death and graves). A sick villager "
            f"loses 1 health on {high:.0%} of age units, {low:.0%} at 20 health or less (see Villager timers).")
    if game == 5:
        rule += (" Faith runs from -100 to 100: a believer becomes a Heathen at 0 or less, a Heathen joins the tribe "
                 "when it rises above 0 (see Faith and Heathens).")
    if game == 1:
        rule += " The Golden Child never loses health to sickness or starvation."
    add(f"Every living villager the save holds ({len(tribe)}"
        + (f" in the tribe, {len(heathens)} Heathens outside it" if game == 5 else "")
        + ("), the tribe oldest first" if game == 5 else "), oldest first")
        + ", with each one's own values read from the save. " + rule, gm.RUNNING)

    who = "Believers in the tribe" if game == 5 else "Villagers"
    add(f"{who}: {len(tribe)}.", gm.SAVE)
    for p in sorted(tribe, key=lambda q: (-q.age, q.name)):
        head = f"{p.name}: {p.sex}, {_ages(p)}; {health_words(ctx, p)}"
        if game == 5 and p.faith is not None:
            head += f"; Faith {p.faith}"
            if p.faith <= 10:
                head += " (becomes a Heathen at 0 or less)"
        if game == 5 and _i32(data, p.at + VV5_ROLE) == 13:
            head += "; the Retired Heathen Chief"
        if p.golden:
            head += "; the Golden Child"
        if p.chief:
            head += "; the Tribal Chief"
        add(head + ".", gm.SAVE)
        _detail_lines(ctx, p, data, titles, lambda text, ok: add(text, ok, True))

    if game != 5:
        return out
    if not heathens:
        add("Heathens outside the tribe: none.", gm.SAVE)
        return out
    add(f"Heathens outside the tribe: {len(heathens)}, closest to joining first. Heathens never count in the "
        "patcher's Village Statistics, in the tribe's population or in any count or total on this page. The game's "
        "age-unit update skips them: they never eat or lose health, and never age unless a Heathen aging row of the patcher is in the game.",
        gm.RUNNING)
    now = village.now
    for p in sorted(heathens, key=lambda q: (-(q.faith if q.faith is not None else -1000), q.name)):
        role = _i32(data, p.at + VV5_ROLE)
        colour = mask(data, p.at)
        add(f"{p.name}: {p.sex}, {_ages(p)}; {health_words(ctx, p)}; Faith {p.faith}; {colour} mask; "
            f"{role_words(role, colour)}.", gm.SAVE)
        sub = lambda text, ok=gm.SAVE, due=None, kind=None: add(text, ok, True, due, kind)  # noqa: E731
        faith = p.faith if p.faith is not None else 0
        need = max(0, 1 - faith)
        if faith > 0:
            # The setter 0x467F90 makes a Heathen above 0 a believer, only while the island runs (manager +0x17E39).
            sub(f"Faith {faith} is already above 0: the game makes them a believer the next time it changes their "
                "Faith while the village runs (loading a save never converts anyone).", gm.CODE)
        elif role in PUZZLE_ROLES:
            sub(f"Faith {faith}: {need} short of joining (a Heathen joins when Faith rises above 0). Never preached "
                f"to and never reached by the Earthquake God Power: {PUZZLE_JOIN[role]}.", gm.CODE)
        elif colour == "blue":
            few, many = math.ceil(need / SERMON[1]), math.ceil(need / SERMON[0])
            sermons = (f"{_plural(few, 'sermon')}" if few == many else f"{few} to {many} sermons")
            sub(f"Faith {faith}: {need} short of joining (a Heathen joins when Faith rises above 0): {sermons} of +3 "
                f"to +5 (by the preacher's Devotion); Spreading the Word gives its one listener +30.", gm.CODE)
        else:
            sub(f"Faith {faith}: {need} short of joining (a Heathen joins when Faith rises above 0). A believer "
                f"dropped on a Heathen in the {colour} mask does nothing, so only the Earthquake God Power (+2 to +8) "
                "and island events raise it (see Faith and Heathens for the Fog of Doom patch).", gm.CODE)
        wait, moment = preaching_ready(data, p.at)
        if role in PUZZLE_ROLES:
            held = (f"; the save still holds a wait until {gm.when(moment)}" if moment is not None and moment > now
                    else "")
            sub(f"Preaching wait: does not apply (a puzzle Heathen is never preached to){held}.", gm.CODE)
        elif wait == 0:
            sub("Preaching wait: ready now (no wait set).", gm.CODE)
        elif moment is None:
            sub("Preaching wait: the save's clock start could not be read, so when it ends is not known.", gm.SAVE)
        elif moment <= now:
            sub(f"Preaching wait: ready now (the 2-hour wait ended {gm.when(moment)}).", gm.CODE)
        else:
            minutes = math.ceil((moment - now) / 60)
            sub(f"Preaching wait: tired of listening until {gm.DUE}; {_plural(minutes, 'real-life minute')} left "
                "when the page was read, the same at Fast, Normal and Slow (real time: it runs while the game is "
                "paused or closed). Each sermon, Spreading the Word or Earthquake sets a new 2-hour wait.",
                gm.CODE, moment, "ready")
        _detail_lines(ctx, p, data, titles, lambda text, ok: add(text, ok, True))
    return out
