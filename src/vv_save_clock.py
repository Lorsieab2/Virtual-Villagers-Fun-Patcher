"""Changing a save's game speed or pause exactly the way each game does it itself.

The owner (2026-10-24), after The Secret City's campfire burned only about 9 hours on Normal: a Repair
Saves & Logs "Game speed" change had written the save's speed and nothing else, so the game's clock
kept running at the old speed under the new one, and the fire lit in that state got the old speed's
length.  "Pausing freezes the game clock the way the game does ... a speed change re-bases the clock
and rescales every timer the game ties to it."

So the patcher never writes the speed dword on its own: it replays, on the save's bytes, the game's
own routine that runs when the player changes speed or pauses in the game -- the same arithmetic, on
the same fields, at the moment the save was last ticked (the "now" every game writes into its state at
the end of its world tick, with the same clock the routine reads).  The result is the save the game
itself would have written had the player done that just before quitting.  Anything this cannot
reproduce exactly is refused, and the save is left as it is (the owner: no half-done patches).

TWO KINDS OF GAME (static reading of the five stock executables; tests/test_save_speed_edit.py runs
the stock routines in an emulator on the same fixtures and compares every byte):

  A New Home, The Lost Children, New Believers -- a real-seconds clock and a speed-change routine
  rescale(old, new) (VV1 0x42E830, VV2 0x43B5A0, VV5 0x426260): a speed of 999 or more (paused) counts
  as Normal (6) on either side; when the two differ, each timer the routine knows that is still ahead
  of now becomes now + (timer - now) * new / old in unsigned 32-bit arithmetic.  The pause key calls
  rescale(speed, 999) and adds 999; the unpause key rescale(speed + 999, speed); an Options speed
  button rescale(speed, new).  The routine's timers:
      VV1  the next regrowth (state 0xA2F0)
      VV2  the next regrowth (0x2EAC0) and the fire's end (0x2EAC4)
      VV5  the crops' next refill (0x17D44)

  The Secret City, The Tree of Life -- a game clock object (VV3 0x5825D4, VV4 0x4D6F18; saved as rate,
  the rate before a pause, wall base, game base) with the timers registered to it, and set_speed(new)
  (VV3 0x426630, VV4 0x41DBE0):
      new == 999 (pause): each registered timer that is set and already due becomes -1; then
      otherwise: from a running rate the factor is float(new / old) and every set timer not yet due
          becomes trunc(timer * factor) + (now - trunc(now * factor)); from a paused rate (0) the
          factor is 1 and every set timer moves by now - the wall base (the time paused);
      then the game base becomes the game clock at now (computed at the old rate), the wall base now,
      the rate before the old rate, and the rate the new one (0 for a pause).
  The pause key is set_speed(999) and adds 999 to the speed; the unpause key set_speed(speed).  The
  registered timers the save keeps (VV3: four of six; the rest are not saved and so are not here):
      VV3  the honey's timer (state 0x11FA9), object 0x594BC8's timer (0x120AE), the fire's two
           (0x12125, 0x12129) -- the world-objects block, whose size dword must be the stock 0x2AD
      VV4  the Fire Pit's (state 0x16240) -- the world-objects block, whose size must be 0x250
  The x87 arithmetic is reproduced exactly with rationals; values large enough that the game's own
  rounding could differ from the exact result are refused.

WHAT A CHANGE REPLAYS.  Running at r to running at s: an Options speed button (rescale / set_speed).
Running to paused: the speed button (if the speed under the pause differs), then the pause key.
Paused at b to anything else: the unpause key back to b first -- so the time paused is taken off as the
game takes it -- then as above.  The Secret City and The Tree of Life go by their clock, not the speed
dword, when the two disagree (saves an earlier patcher wrote that way): the clock is what the timers
follow.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from fractions import Fraction

MASK = 0xFFFFFFFF
PAUSED = 999
SPEEDS = (3, 6, 10)
# The games' x87 code rounds each product and quotient to the FPU's precision (53 bits, the Windows
# default the games keep; 64 if it were extended) before truncating it.  The exact result is used
# here, and only where no rounding at 53 or 64 bits could carry it across an integer -- otherwise
# the edit is refused (see _trunc).
_ROUNDING = Fraction(1, 1 << 52)


class SpeedEditRefused(Exception):
    """The edit cannot be made exactly as the game would make it; nothing was written."""


@dataclass(frozen=True)
class RescaleGame:
    """A New Home, The Lost Children, New Believers (rescale(old, new))."""
    name: str
    speed: int                 # state offsets (buffer offset = state - 8)
    now: int
    timers: tuple[int, ...]


@dataclass(frozen=True)
class ClockGame:
    """The Secret City, The Tree of Life (a game clock object and set_speed(new))."""
    name: str
    speed: int
    now: int
    clock: int                 # rate, before, wall base, game base
    timers: tuple[int, ...]
    block: int                 # the world-objects block's size dword ...
    block_size: int            # ... and the stock value it must hold
    rate_unit: str             # how the game turns a rate into wall seconds per game second


GAMES: dict[int, RescaleGame | ClockGame] = {
    1: RescaleGame("A New Home", 0xA318, 0xA304, (0xA2F0,)),
    2: RescaleGame("The Lost Children", 0x2EB08, 0x2EAE4, (0x2EAC0, 0x2EAC4)),
    3: ClockGame("The Secret City", 0x12F20, 0x12F04, 0x584, (0x11FA9, 0x120AE, 0x12125, 0x12129),
                 0x11ED4, 0x2AD, "times_f32_sixth"),
    4: ClockGame("The Tree of Life", 0x17110, 0x170F0, 0x8E8, (0x16240,), 0x160C0, 0x250, "over_six"),
    5: RescaleGame("New Believers", 0x17D7C, 0x17D50, (0x17D44,)),
}

# The Secret City's 0x426580: fild rate; fmul dword [0x4808A0] (0x3E2AAAAB, 1/6 in single precision).
_VV3_SIXTH = Fraction(struct.unpack("<f", struct.pack("<I", 0x3E2AAAAB))[0])


def _f32(value: Fraction | float) -> Fraction:
    """Rounded to single precision (fstp dword), from a value the game holds exactly or rounds once."""
    return Fraction(struct.unpack("<f", struct.pack("<f", float(value)))[0])


def _trunc(value: Fraction) -> int:
    """fistp / _ftol under truncation, low 32 bits, of a product or quotient the game first rounds to
    its precision: the same integer whatever that rounding was, or SpeedEditRefused."""
    whole = int(value)                       # toward zero; every value here is at least 0
    if Fraction(float(value)) != value:      # not held exactly at 53 bits: the game rounds it
        slack = value * _ROUNDING
        if value - slack < whole or value + slack >= whole + 1:
            raise SpeedEditRefused("a clock value in the save is one whose rounding in the game cannot be "
                                   "reproduced exactly")
    return whole & MASK


class _Buffer:
    def __init__(self, data: bytearray, header: int):
        self.data = data
        self.header = header

    def at(self, state: int) -> int:
        return self.header + state - 8

    def get(self, state: int) -> int:
        return struct.unpack_from("<I", self.data, self.at(state))[0]

    def put(self, state: int, value: int) -> None:
        struct.pack_into("<I", self.data, self.at(state), value & MASK)


# ---- A New Home, The Lost Children, New Believers ---------------------------------------------

def _rescale(game: RescaleGame, buf: _Buffer, now: int, old: int, new: int) -> None:
    old = 6 if old >= PAUSED else old
    new = 6 if new >= PAUSED else new
    if old == new:
        return
    for field in game.timers:
        timer = buf.get(field)
        if timer > now:
            buf.put(field, ((((timer - now) * new) & MASK) // old + now) & MASK)


def _edit_rescale(game: RescaleGame, buf: _Buffer, speed: int, paused: bool) -> None:
    value = buf.get(game.speed)
    now = buf.get(game.now)
    was_paused = value >= PAUSED
    base = value - PAUSED if was_paused else value
    if base not in SPEEDS:
        raise SpeedEditRefused("its game speed is not one the game writes")
    if was_paused:
        if paused and speed == base:
            return
        _rescale(game, buf, now, value, base)           # the unpause key
    if speed != base:
        _rescale(game, buf, now, base, speed)           # an Options speed button
    if paused:
        _rescale(game, buf, now, speed, PAUSED)         # the pause key
    buf.put(game.speed, speed + PAUSED if paused else speed)


# ---- The Secret City, The Tree of Life ---------------------------------------------------------

def _wall_per_game_second(game: ClockGame, rate: int) -> Fraction:
    if game.rate_unit == "times_f32_sixth":          # VV3 0x426580, stored by fst dword (0x42659B)
        return _f32(rate * _VV3_SIXTH)
    return _f32(rate / 6.0)                          # VV4 0x41DB00: fild; fdiv qword 6.0; fstp dword


def _game_clock(game: ClockGame, clock: list[int], now: int) -> int:
    """The game clock at `now` (VV3 0x426590, VV4 0x41DB20)."""
    rate, _before, wall, base = clock
    unit = _wall_per_game_second(game, rate)
    if unit == 0:
        return base
    elapsed = (now - wall) & MASK
    return (_trunc(Fraction(elapsed) / unit) + base) & MASK


def _set_speed(game: ClockGame, buf: _Buffer, now: int, new: int) -> None:
    clock = [buf.get(game.clock + 4 * k) for k in range(4)]
    rate, _before, wall, _base = clock
    if new == rate:
        return
    paused_now = _wall_per_game_second(game, rate) == 0
    timers = [buf.get(field) for field in game.timers]

    def due(timer: int) -> bool:                     # VV3 0x426870, VV4 0x41DE70
        return timer == 0 if paused_now else timer < now

    if new == PAUSED:
        timers = [MASK if timer != 0 and due(timer) else timer for timer in timers]
        new_rate = 0
    else:
        if rate == 0:
            factor = Fraction(1)
            shift = (now - wall) & MASK
        else:
            factor = _f32(new / rate)                # fild new; fidiv old; fstp dword
            shift = (now - _trunc(now * factor)) & MASK
        out = []
        for timer in timers:
            if timer != 0 and not due(timer):
                timer = (_trunc(timer * factor) + shift) & MASK
            out.append(timer)
        timers = out
        new_rate = new
    base = _game_clock(game, clock, now)
    for field, timer in zip(game.timers, timers):
        buf.put(field, timer)
    for k, value in enumerate((new_rate, rate, now, base)):
        buf.put(game.clock + 4 * k, value)


def _edit_clock(game: ClockGame, buf: _Buffer, speed: int, paused: bool) -> None:
    if buf.get(game.block) != game.block_size:
        raise SpeedEditRefused("its world-objects block is not laid out as the game writes it")
    value = buf.get(game.speed)
    if value not in SPEEDS and value - PAUSED not in SPEEDS:
        raise SpeedEditRefused("its game speed is not one the game writes")
    rate, before, wall, _base = (buf.get(game.clock + 4 * k) for k in range(4))
    now = buf.get(game.now)
    if rate not in (0,) + SPEEDS or (rate == 0 and before not in SPEEDS):
        raise SpeedEditRefused("its game clock is not in a state the game writes")
    if now < wall:
        raise SpeedEditRefused("its game clock was last changed after its last tick")
    if rate == 0:
        if not (paused and speed == before):
            _set_speed(game, buf, now, before)      # the unpause key
            rate = before
    if rate != 0:
        if speed != rate:
            _set_speed(game, buf, now, speed)       # an Options speed button
        if paused:
            _set_speed(game, buf, now, PAUSED)      # the pause key
    buf.put(game.speed, speed + PAUSED if paused else speed)


# ---- the edit ------------------------------------------------------------------------------------

def edit_speed(game: int, data: bytes, header: int, speed: int, paused: bool) -> bytes | None:
    """``data`` with its game set to ``speed`` (3, 6 or 10), paused or not, as the game itself would
    leave it; None when the save already is so.  SpeedEditRefused when that cannot be done exactly."""
    if speed not in SPEEDS:
        raise ValueError(speed)
    rules = GAMES[game]
    out = bytearray(data)
    buf = _Buffer(out, header)
    if isinstance(rules, ClockGame):
        _edit_clock(rules, buf, speed, paused)
    else:
        _edit_rescale(rules, buf, speed, paused)
    return None if bytes(out) == bytes(data) else bytes(out)
