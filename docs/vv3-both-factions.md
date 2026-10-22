# VV3 Both Factions: Nature and Magic

The owner asked for The Secret City to let a tribe buy **both** the Faction of
Nature and the Faction of Magic, with both working at once, without crashing
or breaking saves. An earlier attempt to cheat both in (memory / save edit)
broke the owner's save. The owner's suggested shape: the save keeps one normal,
stock-valid faction and the patcher keeps the second one in a per-save `.dat`
file and applies it at run time.

Everything below was read from the stock executable (hash pinned in
`data/builds.json`) with capstone, and checked by running the rendered bytes
in an emulator (`tests/test_vv3_both_factions.py`). **Not run in the game.**

## 1. Where the faction lives

There is no faction field. The technology manager `0x582618` holds seven
levels, `dword [0x582618 + 4*id]`, read by `0x426FC0(id)` (thiscall):

| id | technology (Tech screen label) | info string |
|---:|---|---|
| 0 | Science | 0x40B |
| 1 | Medicine | 0x40C |
| 2 | Alchemy | 0x40D |
| 3 | Restoration | 0x40E |
| 4 | Leadership | 0x40F |
| 5 | **Nature** | 0x410 "Faction of Nature" |
| 6 | **Magic** | 0x411 "Faction of Magic" |

A new village starts at 1,1,1,1,1,0,0 (`0x426F40`). The "chosen faction" is
whichever of 5 and 6 is above 0. Levels go to 3 (`0x426FD0` stops at 3).

In the save the seven levels are seven dwords at **save buffer offset 0x6CC0**
(the game object's `+0x6CC8`; the file is a 12-byte `ldwg` header plus the
buffer, so file offset 0x6CCC): Nature at buffer 0x6CD4, Magic at 0x6CD8. The
tech points follow at 0x6CDC. The owner's saves (read-only copies) show exactly
one of the two above 0, e.g. `(3,3,3,3,3,3,0)` or `(3,3,3,3,3,0,3)`.

### How it is bought

Tech screen message 8, button `id+1`, handler `0x465640`:

* `0x4656E6..0x465749`: buying Nature while Magic > 0, or Magic while
  Nature > 0, shows string 0x419 "You have already chosen your faction!" and
  stops.
* `0x465700`: price `0x427020(id)` = `dword [0x4A818C + 4*(level+1 + 3*id)]`
  (0 when fully researched -> message 0x32); not enough points -> 0x34.
* `0x46574E..0x4657BD`: when both are 0, the "Are you sure? Once you choose a
  faction for your tribe, you cannot change it." confirmation (0x418).
* `0x4657C8..0x4657DB`: points taken (`0x427130(-cost)` on `0x582644`), level
  up (`0x426FD0`).

## 2. Every reader of the two levels

Every call of the getter with id 5 or 6, and every other access, in the stock
executable (`EveryFactionReader` checks this list is complete: a new reader
fails the test).

| site | tech | what it does | with both |
|---|---|---|---|
| 0x415517 (event cond 0x4154F0) | 5 | Ghostly Dream: nature / healing (island event 16), needs Nature >= 1 | works: separate predicate |
| 0x415657 (event cond 0x415630) | 6 | Ghostly Dream: research / architecture (event 17), needs Magic >= 1 | works |
| 0x4347C3 (0x434760) | 5 | Nature 1: fruit-tree refill factor 42 instead of 37 | works |
| 0x4593DC (0x459095) | 6 | Magic 1: +1 tech point per research | works |
| 0x45FE9D (room check 0x45FE30) | 6 | Magic 3: +10 population maximum | works |
| 0x4601C4 (0x45FFE0) | 5 | Nature 3: longevity | works |
| 0x420BB9 / 0x420BDD (world draw 0x420B30) | 5 / 6 | Level 2 herb art: part 6 herb_nature.png (image 0x99, the Pitcher Plant) if Nature >= 2, **else** part 5 herb_magic.png (0x98, the Berry Plant) if Magic >= 2 | **exclusive** (the `ret` at 0x420BD5) -> handled |
| 0x464942 / 0x464969 (Tech screen open 0x464920) | 5 / 6 | `[screen+0xD4]` = the chosen faction (Nature first) | harmless; drawing handled below |
| 0x4649C0 (Tech screen draw), 0x464A0C / 0x464AB0 | any | level pips for every technology | works: both filled in |
| 0x464AE4..0x464BE1 (same draw) | `[+0xD4]` | sunbeam.png (0x90) on the chosen faction, the other column darkened | **one only** -> handled |
| 0x465583..0x465624 (Tech screen frame 0x465530) | `[+0xD4]` | floating particles in the chosen column only: one in ten frames, Nature's petals (type 0xA) or Magic's sparkles (type 2), shared pool 0x583B28 (0x429400, 0x200 slots, type 2 limited to the first 0x65) | **one only** -> handled (each column its own) |
| 0x464DBB.. / 0x464EB6.. (hover 0x464D90) | 5 / 6 | preview (sunbeam and particles) while neither is chosen | harmless; kept stock |
| 0x464C65 (info box 0x464C30) | any | level and next price | works |
| 0x4656F7 / 0x46572D (purchase) | 5 / 6 | "already chosen" refusal | **blocks** -> handled |
| 0x46575F / 0x46576F (purchase) | 5 / 6 | confirmation while neither is chosen | stock |
| 0x4325E2 (0x432550) | computed (0) | not a faction reader | - |
| save `0x426F60` (from 0x427D24) | all 7 | copies the array into the save buffer | would write both -> handled |
| load `0x427060` (from 0x428A0D) | all 7 | **refuses** Nature > 0 and Magic > 0 (0x427067..0x427079), any level > 3, and replays the rest through 0x426FD0 | the breakage -> never reached |
| level-change listeners (0x426FD0 -> list at +0x1C) | - | one listener, vtable 0x49D140, `ret 8` (does nothing) | - |

Nothing else names the two levels (no direct `0x58262C` / `0x582630` access).
Puzzles, the chief, statues, statistics and the patcher's own logs never read
them. The "prince of magic / princess of nature" text is story only. The
patcher's own Nature patches (honey refill, Nature 3 mortality) and the
population caps read the getter, so they see both.

### The sharks (owner requirement 8)

Stock (0x436580, a villager with a shark potion reaching the Diving Rock,
map region 0x2A): the puzzle counter 0xA goes up (solved at 1; its message
0x2C6 and reward once, 0x435990 does nothing once solved). Then:

* Nature's stink bomb (effect 0x1B, Black Orchid x2 + Pitcher Plant): the
  sharks go -- the shark object's byte 0x594BC0 = 1 (saved by 0x4364E0, read
  back by 0x436550) and the sharks switched off (0x425C70); particles 5.
* Magic's Shark Charmer Vial (effect 0x1A, Rose x2 + Berry Plant; task 0xA3
  carries the vial, item 0x2F): the sharks are charmed -- particles 6, and the
  shark update (0x425E20) keeps sparkling over them while the puzzle is solved
  and they are there; they stay and no longer stop fishing.

The save already says which look: puzzle solved, and the byte (1 gone, 0
charmed). With both factions (owner's rule) the latest shark potion decides
the look every time: the stink bomb after a charm makes them go (the stock
code already does); the vial after the stink bomb brings them back charmed
(0x4365B1: the byte back to 0 and the stock three sharks re-added with
0x425DE0 where the world's start puts them, (0x47E, 0x32), (0x4E2, 0x32),
(0x546, 0x32)). Nothing else: the puzzle, its message and rewards stay once;
nothing extra is kept in the file. One faction: stock (a vial after the stink
bomb only sparkles over the empty water).

### Every faction effect at once (owner's list), vanilla and patcher

| effect | granted by (stock info text) | read at | with both factions |
|---|---|---|---|
| longer lives | Nature 3 ("increase your villagers' longevity") | 0x4601C4 (stock); patch `vv3_nature_level_three_alters_mortality` cave (+7 years) | live level, getter |
| food refills | Nature 1 ("replenish your food sources more quickly") | 0x4347C3 (stock fruit factor); patch `vv3_nature_honey_refill` caves (fruit and honey timers, honey amount) | live level, getter |
| research point | Magic 1 ("increase your scientists' productivity") | 0x4593DC (+1 per research; the Origins doubler at 0x427130 doubles it as before) | live level, getter |
| population maximum | Magic 3 ("increase your villagers' max population") | 0x45FE9D (+10); the patcher's cap rows at 0x45FEA2/0x45FEE1/0x45FEE3 | live level; the only population bonus, so nothing stacks twice |
| Pitcher Plant | Nature 2 ("a special natural herb") | art 0x420BB9; gathering 0x421340 (no tech read) | drawn with the Berry Plant (0x420BD5) |
| Berry Plant | Magic 2 ("a special magical herb") | art 0x420BDD; gathering 0x4213D0 (no tech read) | drawn with the Pitcher Plant |

Every read of either faction in the rendered executable -- the stock code and
the patcher's caves -- is `push 5|6 / mov ecx, 0x582618 / call 0x426FC0` on
the live levels; none reads the save. The second faction is put in those
levels inside the loader (right after the levels load, before the villagers
and before any catch-up), and the companion installs at game start, before
any load, so load order and catch-up see both. No other companion (Story,
Custom Island Event, Chief Hospital, Statistics, the logs) reads a VV3
faction. `EveryFactionEffectAtOnce` runs every one of those reads, in all
three modes and the 256 build, and the population bonus:

| build | cap with Magic 3 | without |
|---|---|---|
| stock | 115 + collections (0-25) + 10, at most 150 | at most 140 |
| Collection Progression | 115 + collections + 10 = 150 at most | - 10 |
| Immediate Fixed | 150 (the bonus ignored by design) | 150 |
| 256, Collection Progression | 221 + collections + 10 = 256 at most | - 10 |
| 256, Immediate Fixed | 256 | 256 |

Never above the slot capacity (150 / 256).

### The level-2 herbs (owner requirement 1)

| | Nature (Pitcher Plant) | Magic (Berry Plant) |
|---|---|---|
| art | herb_nature.png, image 0x99, world-object part 6, drawn at (0x78, 0x4B5) | herb_magic.png, image 0x98, part 5, at (0x32, 0x550) |
| drop place | map region 30 ("Herb6", cmap.dat), handler 0x421340 (registered 0x422B14) | region 31 ("Herb7"), handler 0x4213D0 |
| gathering | task 0x73 "Gathering herbs" (0x44BCD0), carried item 0x24 (eCarrying_Herb6) | task 0x73, item 0x25 (eCarrying_Herb7) |
| object / names | eObject_Herb6 (0x2A), "Pitcher Plant" (say 0xB5, 0x209) | eObject_Herb7 (0x2B), "Berry plant" (0xB6, 0x20A) |

Separate images at separate places, separate regions, separate carried items:
nothing is shared. Gathering needs the Alchemy Lab restored (puzzle flag 2) and
room in the pot; **no gathering, carrying or alchemy code reads a technology**.
The only exclusive piece is the art's `else`. Both herbs therefore coexist
once the art is drawn for both; no new storage is needed for them.

## 3. Why the cheated save broke

Setting both levels and saving writes both into the buffer (0x426F60 copies
all seven). On the next load the village loader `0x428880` calls `0x427060`,
which returns 0 when `[in+0x14]` and `[in+0x18]` are both nonzero; the loader
then returns 0 at 0x428A74 after the systems before it were already loaded
and before the villagers. The slot no longer loads: the menu's load path
(0x428420) falls through to another slot or a new village. Reproduced in the
emulator on the stock executable: a save with (1,0), (0,3), (3,0) loads; (1,1),
(3,3), (2,1) fails (`WhyTheCheatedSaveBroke`).

## 4. Room for both

The runtime array already has a slot for each faction, and every reader reads
its own slot. Only four places make them exclusive (purchase, herb art, Tech
screen highlight, loader). So both can be active in memory; the save must
simply never hold both.

## 5. Design (built)

**Primary** = the faction bought first on the Tech screen; it stays in the save,
stock-valid. **Secondary** = the other one, bought second on the Tech screen;
it lives only in memory and in the sidecar file.

Companion `VVFP VV3 Both Factions.dll` (`native/vvfp_vv3_both_factions`), its
own DLL, started by `VVFP Startup.dll` (bit 25, appended). It verifies the
stock bytes at every site and installs all or nothing; the purchase last.

| site | stock | change |
|---|---|---|
| 0x427D1F | `mov ecx,0x582618 / call 0x426F60` | after the stock copy: the secondary written as 0 in the buffer; recorded in the file |
| 0x428A08 | `mov ecx,0x582618 / call 0x427060` | after the stock loader accepts: the file entry for exactly this save restores the secondary via 0x426FD0 |
| 0x4657D5 | `push esi / mov ecx / call 0x426FD0` | note which faction is bought second |
| 0x4656FE | `jg 0x465736` | nop nop (Magic while Nature) |
| 0x465734 | `jle 0x465700` | jmp (Nature while Magic) |
| 0x420BD5 | `ret` | nop: the Magic herb is drawn too |
| 0x464AE4 | `mov eax,[edi+0xD4] / cmp eax,-1` | with both: both sunbeams at full strength, no shade |
| 0x465583 | `cmp [esi+0xD4],-1 / je 0x465624` | with both: each column its own particles (petals, sparkles), stock chance and art |
| 0x46574E | `cmp esi,5 / je / cmp esi,6 / jne 0x4657C8` | level 1 of either faction goes to the confirmation (stock: only while both are 0) |
| 0x46577B | `push 0x418 / mov ecx,ebp / call 0x42F190` | the confirmation's text from the companion |
| 0x430520 | `push edi/ebx/ebp / mov esi,ecx / call 0x4302F0` | with both: the seven both-herb recipes |

### The confirmation (owner requirement 6)

Stock: `0x46574E..0x4657BD` asks only while Nature and Magic are both 0, with
string 0x418 ("Are you sure? Once you choose a faction for your tribe, you
cannot change it.", looked up by `0x42F190(0x418, 0, 1)`), in the game's
Yes/No box `0x401AF0` (-1 = No: nothing bought). With the companion level 1
of either faction is asked, with the owner's text supplied from the DLL (the
stock buffer is not patched): "With the power of the Fun Patcher, you can now
embrace both Nature and Magic Factions. Use this gift wisely." (lines broken
by hand, as the stock text is). Levels 2 and 3 are bought without a prompt, as
in the stock game.

The calling convention matters here: `0x42F190(id)` takes ONE argument
(`ret 4`); the `push 1` / `push eax` before it are the last two arguments of
the text box `0x41C7A0(text, 0, 1)` (`ret 0xC`). The first preview of the
prompt took them for the lookup's and dropped them, so the box returned
through a wrong address: the owner's crash (EIP 7) buying a faction's level 1.
The fix leaves them on the stack; every stub in the tests now pops exactly
what the stock routine pops (`real_pop`), which reproduces that crash with
the old DLL on the owner's own 256 executable.

### The both-herb recipes (owner requirement 7)

Stock alchemy (read with the research in `scratchpad\alch`, re-checked here):
the key `0x430270` packs the count of each herb (carried ids 0x1F..0x25:
Tiger Lily, Cactus, Lotus, Black Orchid, Rose, Pitcher Plant, Berry Plant)
base 4, so order does not matter. `0x4305A0` builds 77 records of 0x18 bytes
at pot+0x18 (key, effect, herbs, found byte +0x2C), count at +0x978, capacity
100. The lookup `0x430510` -> `0x4302F0`: no record and a Pitcher Plant ->
the record is APPENDED with effect 0x18 (the failed potion); then the found
byte is set and 50 found -> "Alchemy R Us" `0x412CD0(2)`. The pot saves only
the found bytes and the count (`0x430120`: 100 bytes + count; `0x4300C0`
loads, count must be < 100). All seven both-herb combinations are 0x18 today.

With both factions the companion answers the seven combinations before the
table (0x430520), so they are never appended and the save keeps exactly the
stock table's flags:

| herbs | effect |
|---|---|
| Tiger Lily + Pitcher + Berry | 0x07 "Whee! What a fun potion!" |
| Cactus + Pitcher + Berry | 0x23 "In a trance" |
| Lotus + Pitcher + Berry | 0x26 "Blannesamagawa loomajoobamooga!!" |
| Black Orchid + Pitcher + Berry | 0x16 "Paralyzed" |
| Rose + Pitcher + Berry | 0x19 "A little bit lonely" |
| Pitcher + Pitcher + Berry | 0x21 "Whoa!" |
| Pitcher + Berry + Berry | 0x28 "Something smells YUMMY!" |

What each potion does is the stock game's own effect code: the brew stores
only the effect id (pot+0x97C, written at 0x430ABC); the pot's particles
(0x430160) and the drink (0x4303E0 -> 0x4583A0 -> the effect switch
0x4268F0, jump table 0x426E6C) read nothing else, so a new combination and
the stock recipe of the same effect give identical results (checked in the
emulator against the stock table's own recipe for each effect):

* 0x07 (0x45B9B0 on the drinker), says "Whee! What a fun potion!" -- the drinker.
* 0x23 task 0xA1 "In a trance" -- the drinker.
* 0x26 task 0xBF, crazy talk "Blannesamagawa loomajoobamooga!!", lasts 0x258 -- the drinker.
* 0x16 task 0x9C "Paralyzed" -- the drinker.
* 0x19 task 0x66 "A little bit lonely" -- the drinker.
* 0x21 "Whoa!": the drinker is moved to a random free spot of the map (0x560990,
  0x420970), with a puff -- the drinker.
* 0x28 "Something smells YUMMY!" (said by the drinker): the village
  (0x45E0C0 -> 0x45DDE0, flag 1) gives task 0xC1 (0x44DB40: says it too and
  walks to the pot, then a short pose) to every living villager **younger
  than 14** (age < 0x118) who holds and heads for nothing (+0xF20 = -1). Adults
  never go; with no free child nobody moves. That is the stock game's own
  Cactus + Cactus + Rose potion; the owner's first test ("nothing really
  happened", the drinker did say it) matches a village with no free child.

Which ones were brewed is kept in the per-save file's entry (version 2 adds a
byte; version 1 files from the first preview are still read), and counted
with the table's found flags toward "Alchemy R Us". The Village Statistics
hook at the entry of 0x430510 still runs first, so Stews Found counts each
combination. With one faction or none every brew is the stock game's.

**The file**: `<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Factions\Virtual Villagers 3 Second Faction - Save <S>.dat`
(magic `VV2F`, version 1, game 3, slot, up to 16 entries: fingerprint,
secondary + level, primary + level, time). Read and written through
`native/shared/sidecar_io.h` (atomic `.tmp` + MoveFileEx; an unreadable file is
never replaced; an invalid one is set aside, never trusted).

**Bound to the village**: each entry carries the FNV-1a 64 fingerprint of the
save buffer's first 0x6CDC bytes (every system saved before the technologies,
the seven levels as saved) plus the tech points. At load the same fingerprint
is computed from the loaded file; only an entry with the same slot, fingerprint
and primary faction/level is applied. Another village, another save of the
slot, a Start Over, an older copy without an entry: nothing is applied. The
last 16 saves are kept, so restoring a recent backup (the game's slot+20
generation or a patcher backup) still finds its entry. Start Over deletes the
file (`native/shared/save_reset.c`, VVFP Save Reset.dll).

**Purchase**: on the Tech screen itself, the same click as any technology, at
the stock price of that faction's next level (tech points). The first faction
keeps its stock confirmation; the second needs none, like every other
technology. Saves that already have one faction: that faction is the primary,
and the other can be bought. Fresh villages: whichever is bought first.

**Uninstalling**: the save holds the primary only, which the stock loader
accepts; the stock purchase again refuses the other faction. The file stays
and is used again if the patch is put back.

### Owner requirements (binding) and the gate list

1. Both level-2 herbs in the world at once, usable normally: the art `else`
   removed (0x420BD5); regions, items and alchemy are already independent.
2. Every level effect of both factions at once: both levels live in memory;
   every reader in section 2 reads its own technology.
3. Primary = bought first (in the save, stock-valid); secondary = bought second
   on the Tech screen, only in the sidecar.
4. Tech screen: both factions' levels filled in (the pips draw from each
   level) and both highlighted with the game's own sunbeam.
5. (Owner, after the first preview) both factions' floating particles at the
   same time, each around its own column, with the game's own particles;
   the stock hover preview kept while neither is bought. The Buy buttons are
   the stock ones: the stock game never hides a faction's button (no reader
   of the two levels does), so both stay before and after both are bought; a
   click on a fully researched faction says so, as for any technology.

Gate: every reader in section 2 is handled or independent, the companion
installs only when every site is stock, and no path writes a save with both
factions (`test_the_companion_never_lets_such_a_save_be_written`, all slots
including the backup generation).

## 6. Not verified

* Not run in the game: the purchase click, the herbs on the island, the
  sunbeams, the particles, the prompt's look, the seven potions' effects on a
  villager (the effect ids are the owner's choice from the research; the
  effect switch 0x4268F0 was not run), a real save/load/quit cycle and a real
  file on disk.
* The emulator stubs display, sound, text and the other systems' savers and
  loaders; only the technology code, the purchase, the save/load routines, the
  herb draw and the Tech screen draw run for real.
* A save already broken by a cheat (both factions in the file) is not repaired:
  the stock loader refuses it before the companion is asked.
* If the file cannot be written at a save (locked, disk full), that save still
  holds the first faction only (always stock-valid), but its second faction is
  not recorded: loading that save gives the first faction only.
