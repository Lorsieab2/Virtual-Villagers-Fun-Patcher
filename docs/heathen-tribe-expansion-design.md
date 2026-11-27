# Heathen Tribe Expansion and Evolution (New Believers): design

This is a design document. It contains no shipping code and nothing in it is built.

- Date: 2026-11-26.
- Branch: `design/heathen-tribe-expansion`, cut from `origin/main` 44b1f7b69.
- Target: the owner says "everything waits in one release", so the whole feature list ships in **v1.35.101**.

**What the evidence rests on.** Unless a line says otherwise, every address was read from the stock executable
`inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe` (991,232 bytes) with capstone. The sources:

- **Byte checks.** The stock bytes at every proposed splice site were re-checked for this document with a short
  pefile/capstone script. Section 12 lists them.
- **Earlier work in the repo.** `native/vvfp_heathen_aging/vvfp_heathen_aging.c`,
  `native/vvfp_story_upgrades/story_c5.inc`, `docs/hidden-gates-all-five-games.md` (gates 28-41),
  `src/vv_game_mechanics*_vv5.py` and the companions named in each section.
- **Ratings.** **Provable** means the disassembly shows it. **Likely** is an inference from the code that has not
  been run. **Unknown** has not been traced. Inferences are marked as such.
- **Nothing here has been seen in a running game.**

Record layout (the stock game, `vvfp_heathen_aging.c`):

- Stride 0x2F44; the records start at manager + 0x48.
- The manager is 0x554148 with 150 records in the stock build. The "256 Villagers (Experimental)" build moves it to
  0x800000 with 256 records; `native/shared/vv5_villager_table.h` reads which one from the exe.
- Fields:

| Offset | Field |
|---|---|
| +0x1B8C | age |
| +0x1B90 | sex (1 = woman) |
| +0x1B9C | name |
| +0x1BC0 / +0x1BD9 | father / mother name |
| +0x1C34 | health block (health itself at +0x1C40, cause at +0x1C44) |
| +0x1C3C | processed age |
| +0x1C48 | sick byte |
| +0x1C4C | pregnancy |
| +0x1C50 | litter |
| +0x1C5C | six skill floats: 0 Farming, 1 Parenting, 2 Healing, 3 Research, 4 Building, 5 Devotion |
| +0x1CD4 | present |
| +0x1CEC | faction (non-zero = Heathen) |
| +0x1CED / +0x1CEE | orange / red mask |
| +0x1CF0 | Faith |
| +0x1CFC | role |

Time: one age unit is 6 real minutes on Normal, so 240 units = 24 real hours (12 on Fast, 40 on Slow). 20 units
= 1 year.

---

## 1. Scope

**One new row**, "Heathen Tribe Expansion and Evolution" (New Believers), takes the place of three rows:

| Folded row | id | Ships today |
|---|---|---|
| Heathen Tribe Ages, Dies and Has Children | `vv5_heathen_tribe_ages` | `VVFP Heathen Aging.dll` + `VVFP Heathen Aging Tribe.txt` |
| All Heathens Leave Skeletons | `vv5_all_heathens_leave_skeletons` | `VVFP Heathen Skeletons All.txt` (read by the same DLL) |
| Heathens can be selected in Island Events/Heathen-Exclusive Events | `vv5_heathens_in_island_events` | `VVFP Heathen Aging Events.txt` (same DLL; Story Upgrades' event code calls `VvfpHeathenAgingEventGone` / `VvfpHeathenAgingEventPregnancy`) |

These rows **stay separate**:

- Former Villagers Keep Aging Among the Heathens;
- Former Villagers Among the Heathens Leave Skeletons;
- New Heathens Get a Heathen's Faith;
- Memorial Actions at the Heathen Hovel;
- Heathens Keep Their Masks When Converted.

**Defaults** (from `src/vv_fun_patcher_gui.py` as it is on main):

| Row today | Default Patches | Select All | Owner's Defaults |
|---|---|---|---|
| Heathen Tribe Ages | off (DEFAULT_OFF, line 465) | off (SELECT_ALL_OFF, line 558) | off (OWNERS_DEFAULT_OFF, line 520) |
| All Heathens Leave Skeletons | off (ALTERNATIVE_OFF) | off (ALTERNATIVE_OFF) | off (line 520) |
| Heathens in Island Events | off (line 416) | off (line 540) | **on** |

**The new row** follows what the folded rows do in the normal defaults and in Select All: **off in Default Patches,
off in Select All**. It is **on in Owner's Defaults**, because the owner said on 2026-11-25: "the heathen expansion =
default on in owners defaults". The sliders' Owner's Defaults values are owner question Q3.

**The skeleton conflict goes away.** All Heathens Leave Skeletons and Former Villagers Among the Heathens Leave
Skeletons exclude each other today, and Former Villagers ... Leave Skeletons is on in Owner's Defaults.

- Inside the new row, "every Heathen leaves a skeleton" covers former villagers too.
- So the new row has no `conflicts` entry. With the new row on, the Former Villagers row changes nothing (it is a
  subset).
- With the new row off, the Former Villagers row works as today. Section 6 covers where those graves go.
- This needs the owner's agreement: Q14.

---

## 2. Owner questions

Only the owner can decide these. Each one gives a recommendation.

1. **Births and arrivals before The Last Heathen (puzzle 25).**
   - The puzzle is solved only when no Heathen is left (0x471870 returns 0, then 0x437120; Provable).
   - Fast births or arrivals can make it hard, or in practice impossible, to solve. That would also block
     Memorial Actions at the Heathen Hovel, which waits for puzzle 25.
   - Recommendation: before puzzle 25, births and arrivals run at the slider rates, and the slider description says
     so in bold. The alternative is "no births or arrivals until puzzle 25 is solved".
2. **Births after The Last Heathen.** Today no Heathen baby is conceived once puzzle 25 is solved. The new rule says
   arrivals continue after puzzle 25 when the spawn rate is not zero. Should births continue too? Recommendation:
   yes, while at least one Heathen woman and one Heathen man are alive.
3. **Slider defaults.** Recommendation:
   - "0.1-10x Heathen Tribe Births": 1x everywhere (about one baby per tribe every 24 real hours, as PR #875).
   - "0-10x New Heathen Arrivals": 0 (off) in Default Patches; 1x in Owner's Defaults.
4. **What 1x arrivals means.** Recommendation: one arrival, which is a single Heathen or a group, about every 48
   real hours on Normal (480 age units).
5. **Group size and makeup.** Recommendation: 1 to 4 people. A group of 2 or more is sometimes a couple with 0-2
   children.
6. **The new Chief and Masters.**
   - (a) Cosmetic, no risk: the six skills at 100, a custom title "Heathen Chief", and the orange/red mask only.
   - (b) The real role 13 to 16, which brings the purple or Chief mask art (0x4728C6, table 0x472B60) but has the
     effects described in section 9.
   - Recommendation: (b) only for a role whose puzzle is unsolved (today's rule). After the puzzle is solved, (b)
     only once The Last Heathen is solved, otherwise (a).
7. **Masks for babies and new arrivals.** Orange and red are not only looks: red Heathens chase and scare, and both
   colours drive the AI and Fog of Doom listening. Recommendation:
   - babies take a parent's colour at random;
   - arrivals are 70% blue, 20% orange, 10% red;
   - with an option to keep everyone blue.
8. **Sickness.**
   - The believers' healers never look at a Heathen (0x470B7F; Provable).
   - Choose: (a) Heathens get well on their own, at the believers' "not sick" healing rule plus a daily chance to
     recover; or (b) believers may cure Heathens (their cures then must not count in People Cured).
   - Recommendation: (a).
   - The health floor while sick: 1, or 21 (the game's "low health" line is 20). Recommendation: 21, so a sick
     Heathen never looks near death.
9. **The stock Heathen noni bush.** The stock Heathen behaviour 0x97 already eats noni from the believers' bushes: -1
   on 40% (0x46DA43; Provable). Should the new patch stop that? (It is vanilla behaviour.) Recommendation: leave it as
   is. The new show harvests never touch a source.
10. **Facilities.** Which facilities should Heathens visit? Every visit is for show only: no building points, tech
    points, food or skill checks. Recommendation: the spa, the statue / Believer Idol, the nursery, the love shack
    door (no embrace) and the farm plots.
11. **Who buries a Heathen body, and when.**
    - The believers' burial chooser runs only once the Buried Mausoleum (project 6) is restored (0x46F130; Provable).
      Until then every body is removed unburied after 240 units.
    - Choose: (a) believers bury Heathen bodies as now, but carry them to the mud hut; or (b) Heathens bury their own
      at the hovel, with no project 6 needed.
    - Recommendation: (a) in this release; (b) later.
12. **The Heathen graves already in the believers' Roster of the Dead.**
    - Recommendation: **leave them where they are.** They stay out of the statistics through
      `VvfpHeathenAgingGrave`.
    - Moving them is not safe without repacking the roster: the game's loader stops at the first empty entry
      (0x464F15; Provable), and moving shifts the entry numbers the logs and the epitaph editor refer to.
    - An optional, separate "Move Heathen graves to the mud hut" repair, with a backup, could come later.
13. **The Heathen Mausoleum Screen title.** The screen reuses `mausoleum_ui_bg.jpg` and its art. Whether that
    background carries a title is Unknown. If it does, is the same title acceptable, or should the in-game-font text
    tool render a "Heathen ..." title? Recommendation: reuse it unchanged.
14. **The folded skeleton rule**, as section 1 describes it:
    - with the new row on, every Heathen leaves a skeleton, former villagers included;
    - the mud-hut memorial (burial routing and the screen) also ships when only "Former Villagers Among the Heathens
      Leave Skeletons" is on, so a former villager who died a Heathen goes to the mud hut in that case too.
    - Recommendation: yes to both.
15. **Couples.**
    - Should former villagers among the Heathens pair and have babies? Recommendation: yes, when Former Villagers Keep
      Aging or the new row ages them.
    - Should a couple stay together for life? Recommendation: yes, until one dies or converts.
    - Half-siblings: the Matchmaker does not block them by default. Recommendation: block them for Heathens.
16. **New log records with no believer counterpart.** "Couple formed" (Births and Conceptions log) and "Took the
    role" (Births log, beside the Arrived records). Are these new record kinds wanted?
17. **Skills on conversion.** A Heathen whose skills grew converts with those skills, because 0x4668B0 never touches
    +0x1C5C (Provable). A Heathen raised to 88 or more converts as a master, but no mastery trophy is given (0x475730
    is not called). Keep the skills? Recommendation: keep them.
18. **The cap on Heathen numbers.** Recommendation: Heathens never take a record that the believers could still need.
    The free records must stay at or above 10, plus the believers' remaining room under their own cap (0x472BD0).
    - Stock 150: at most about 35 Heathens plus bodies.
    - 256 build: more; that build's believer cap is Unknown and must be read from that exe.
    - Is a smaller fixed cap also wanted?

---

## 3. Shared groundwork (stock game, Provable unless marked)

| Item | Address | Facts |
|---|---|---|
| Age credit | 0x46FE90, faction test 0x470077 | Ages believers only. Heathen Aging splices 0x470077 (stock `38 9E EC 1C 00 00 8B F8 75 0C`, or `... 75 38` with the Statistics row). |
| Life tick | 0x472C90, Heathen skip 0x472CB7 (`80 BE B0 00 00 00 00 74 1B`) | A Heathen only copies age into the processed age and clears the sick byte (0x472CC0..0x472CD6). Heathen Aging owns this site. |
| Heathen creator | 0x46FD20 (thiscall on the manager, 9 args, `ret 0x24`), via 0x46FB80 | Args: lineage, skill index, value, sex (-1 random), age, orange, red, role, **Faith**. The 9th argument is the Faith passed to SetFaith 0x467F90 at 0x46FC31, not a flag; Faith ≤ 0 runs the to-Heathen conversion and its "stopped believing" message, so pass 1 and write +0x1CF0 after, as Heathen Aging does. Free-record scan bounded at 0x46FBA6/0x46FBBA; -1 when full. |
| Camp set-up | 0x424AC0 | 28 creator calls. Roles 0-11 ordinary; 12 Doctor, 13 Chief (age 1000, all six skills 100 at 0x424D87..0x424DAF, Faith -94), 14 Scientist, 15 Builder, 16 Farmer (skill 90, Faith -74). Then 0x470E60 gives five blue Heathens Faith -5/-9/-16/-23/-30 and the rest -38 - rand(30). Role 17 (Mommy) is not in the stock exe (see `docs/vv5-heathen-mommy-research.md`). |
| Role finder | 0x470690(role) | The first present Heathen with that role. |
| Conception | 0x465E00 (thiscall on the carrier, 7 args, `ret 0x1C`) | See section 5. |
| Who makes Heathens in stock | | Only the camp set-up and Barrel O' Heathen Babies (0x4152E8/0x415333/0x41537E; 10-year-olds, Faith -55). No periodic refill, no Heathen arrivals. |
| The Last Heathen | puzzle 25 | Solved when no Heathen is left (conversion 0x466982, main-scene check 0x4425ED). Nothing in stock stops Heathen creation afterwards, and nothing un-solves it (Likely). |
| Food store | dword 0x51D34C, writer 0x41EB40 | |
| Statistics block | 0x51D358.. | Babies Made 0x51D360, People Cured 0x51D368, Twins 0x51D380, Triplets 0x51D384, burials 0x51D39C, deaths 0x51D3A0, Heathens Converted 0x51D3A4. |

**How a slider reaches a companion** (the PR #872 pattern):

1. `RuntimeSlider` in `src/vv_fun_patcher.py` (line 11415) defines it.
2. `_write_runtime_slider_choices` writes the multiplier as ASCII ("1", "0.5", "2.5") into a text file in the
   patcher's folder.
3. The companion reads it with `native/shared/multiplier_choice.h` `vvfp_read_tenths(file, fallback, min, max)`.
4. `slider_scale.h` sets the rule that a companion draws from its own xorshift, so the game's `rand` is never drawn
   more or less often.

---

## 4. Feature 1: the sliders, and arrivals after The Last Heathen

**(a) The stock game.** It has no Heathen births and no Heathen arrivals (section 3). Believer arrivals:

| Source | What arrives | Address |
|---|---|---|
| Barrel O' Babies | up to 3 | 0x4151D0 |
| Chutes Without Ladders | 3 | 0x415410 |
| News From Another Tribe | 1 adult | 0x415510 |
| `CAdoptionScene` | 1 or 2 adults | 0x43E220 |

All of them use 0x471E20 → 0x46FAD0. Each person after the first needs the room check 0x472BD0, which counts
believers only (0x4713F0: faction 0 plus pending litters; Provable).

Heathen births today come from the companion, as PR #875 (open) makes them:

- each eligible woman (14-45, not expecting, not the Mommy, with a living adult Heathen man) rolls
  `rand(240 x eligible women) == 0` each age unit;
- that is about one baby per tribe every 240 units = 24 real hours on Normal.

**(b) What it takes.** Two sliders:

| Slider | Range | Default | What 1x means | Rule |
|---|---|---|---|---|
| **0.1-10x Heathen Tribe Births** | 0.1x-10x in tenths | 1x (Q3) | about 1 conception per tribe per 240 units | Each eligible woman rolls 1 in `2400 x W / t` per unit, where W is the number of eligible women and t the slider in tenths (1..100). At 10x that is 24 x W: one per 2.4 real hours. At 0.1x it is one per 240 real hours. |
| **0-10x New Heathen Arrivals** | 0 (off), then 0.1x-10x | 0 by default, 1x in Owner's Defaults (Q3) | 1 arrival per 480 units, about 48 real hours (Q4) | Rolled once per age unit, on the tribe as a whole: 1 in `4800 / t`. 0 means none. |

The arrivals slider needs a 0 position, which `vvfp_read_tenths` does not allow with min 1. So the arrivals reader
takes min 0. The name keeps the "0.1-10x ..." style but starts at 0 ("0-10x"); the owner may prefer a different name.

- Both sliders sit in the row's own **Settings…** window, by the owner's rule that patch settings go behind a button.
  They are not separate rows on the Difficulty Sliders page.
- Files: `VVFP Heathen Tribe Births.txt` and `VVFP Heathen Arrivals.txt`, each written as `multiplier_text(N)`.
- Both rolls use the companion's own xorshift (slider_scale.h), never the game's `rand` 0x403660. Today's code and
  PR #875 draw the game's `rand`; this changes that.
- **The new rule after The Last Heathen:** when the arrivals slider is not 0, arrivals keep coming after puzzle 25.
  Replacements of the dead keep today's rule (none after puzzle 25). Births after puzzle 25 are Q2.
- Arrivals are rolled in the age credit's throttled pass, once per age unit of the camp's oldest living Heathen.
  They are made by `create()` (Faith 1, then the real Faith written), roles 0-11 only. They are placed next to a
  living Heathen with 0x466300. When nobody is alive, they are placed at the camp's walk area 0x39; the exact point
  comes from lcmap.dat (W-A reads it).

**(c) Risks.**

| Risk | Rating |
|---|---|
| Records run out for the believers: 0x471E60 returns -1 at 0x47312A with a full table and the baby is lost. Mitigation: the cap in Q18, always applied before any create. | Likely |
| The Last Heathen becomes unreachable (Q1). | Provable gate, Likely effect |
| Statistics: arrivals and births never touch 0x4713F0, Highest Population or Babies Made, because force = 1 skips 0x51D360 (0x465F34..0x465F3E), and the twins/triplets counters are put back. | Provable |
| Save integrity: no save bytes are written. Records are made by the game's own creator, as the stock camp does. | Provable |

**(d) Effort:** S for the births slider; M for arrivals with the after-25 rule. It comes first in the order; nothing
depends on it except groups.

---

## 5. Features 2 and 3: groups join; couples form and have babies

**(a) The stock game.**

- **Groups.** The largest stock group is 3 (Barrel, Chutes), believers only. There is no Heathen group mechanism.
- **Couples.** There is no spouse field. Pairing is random each time:
  - The partner search 0x470A10 picks `rand(n)` at 0x470B1B among believers (`cmp byte [cand+0x1CEC],0` at 0x470A4A).
  - Both partners must be 18 or older (360 units), of opposite sex, not sick and not pregnant, and the candidate
    under 50.
  - There is no kinship or hut test, and the loop is hard-bounded at 150 (0x470AFA).
  - Embrace step 0x4689A0; the wrapper 0x467D20 calls 0x465E00 with force 0 (0x467DBE).
  - The other callers are 0x46E16B and 0x46E19B (offline) and 0x471B6D (an island event, force 1, father "Joey").
- **The litter roll** (0x465ECD..0x465F2D; re-checked here):
  - litter = 1;
  - Medicine (0x423600(1) on 0x51D5CC) must be 3 (0x465EDF);
  - then `rand(100) < 7` gives a multiple, and inside it `rand(100) < 25` gives triplets;
  - so twins 5.25% and triplets 1.75%, and only at Medicine 3;
  - 0x51D380 / 0x51D384 are always incremented; 0x51D360 only when force is 0.
- **Birth.** The life tick delivers when `+0x1C4C + 0x28 < processed` (0x4730BA). The companion's deliver() does the
  same for Heathens with the Heathen creator.

**(b) What it takes.**

**Groups.**

- An arrival (section 4) is a group of 1-4 (Q5).
- It is made all at once only if `free >= size + reserve` (Q18). Otherwise the group is smaller or waits: it is
  owed, as `pay_owed` does today.
- A group of 2 or more may be a couple (stored at once in the couple table) with 0-2 children aged 2-12. The
  children's parent fields (+0x1BC0/+0x1BD9 and heads/bodies) are filled from the couple, as deliver() does.
- Each member gets its own Arrived record (section 11).

**Couples: a companion table**, a new kind in the Heathen Aging .dat or a separate file:

- **Path:** `...\Virtual Villagers Fun Patcher\Save <S>\Data\Heathen Couples\Heathen Couples - Save <S>.dat`.
- **Format:**
  - header 'VHC1', version, game 5, count, slot;
  - entries {woman identity, man identity, formed at (processed age), state (0 active, 1 ended: death, 2 ended:
    conversion)};
  - child links {child identity, mother identity, father identity}, written by deliver().
  - Identities are `vv_title_identity` (name, likes, dislikes), as the Heathen Aging file uses.
  - Written through `sidecar_io.h`: atomic; an unreadable file is never replaced.
- **Forming a couple:** an eligible woman with no active partner pairs with a living adult Heathen man who has no
  active partner and is not kin.
  - The kin test uses the record fields only, never a name scan for parents (repo rule): parent and child; full and
    half siblings (Q15) by matching parent name + head + body; further kin through the child links.
  - Founders, camp Heathens, arrivals and Barrel Heathens have no parents, so they are unrelated.
- **Conceiving:** every later conception uses the stored man while both are living Heathens. Island events'
  `VvfpHeathenAgingEventPregnancy(father = -1)` prefers her partner. A couple ends at a death (gone()) or a
  conversion (the credit pass already sees conversions).
- **Litters:** the companion's own roll, not tied to Medicine 3, written to +0x1C50 after the forced 0x465E00 call
  (as story_c5.inc does). Recommended odds, which are the stock odds without the Medicine gate: single 93%, twins
  5.25%, triplets 1.75%. The births slider does not change these odds. If the owner wants twins and triplets more
  often, that is a further owner choice.
- **Log gap to fix (Likely, static):**
  - The VV5 parentage hook at 0x465F34 skips forced conceptions (`test bl,bl; jnz done`,
    `scripts/build_vv5_parentage_feature.py` lines 352-356).
  - So Heathen Aging's forced conceptions (maybe_conceive, create_role(17), VvfpHeathenAgingEventPregnancy) probably
    write **no Conception record**, although the companion's header says they get one.
  - Fix: call Parentage Export's `WriteParentageRecordWithFather` / `WriteParentageRecordCarried` after the call, as
    `story_log_conception` does (story_common.inc line 334).

**(c) Risks.**

| Risk | Rating |
|---|---|
| Identity drift: names and likes change through events, the Custom Island Event and renames. The couple table must follow the same rekey rules as `follow_identities`, and `src/vv_last_names.py`'s offline rekey must learn the new file. | Likely (manageable) |
| False kin blocks: Heathens share 4 family names per village, so names alone over-block; heads and bodies narrow it. | Likely |
| Save integrity: only the game's own conception and creator write records. | Provable |
| Statistics: Babies Made untouched (force 1); twins and triplets put back; the Statistics row's mother-faction guards at 0x465F1A/0x465F2D/0x465F3E also hold. | Provable |
| 150 / 256: the partner search is not used (companion pairing), so its 150 bound does not matter. The companion's tables are sized for 256. | Provable |
| Visible courting (a Heathen walking to the love shack): the Heathen AI 0x46E9E0 never queues an embrace. | Unknown; L effort; not proposed for this release |

**(d) Effort:** couples M; litters S; groups S on top of arrivals; the conception-log fix S. Dependency order:
arrivals → groups; couples → births.

---

## 6. Feature 4: generations, old age, the Heathens' own graves at the mud hut, and the Heathen Mausoleum Screen

**(a) The stock game.**

**Old age.** At each whole year of processed age past 1,100 + 160 × (Medicine - 1), `rand(100) < 10 ×` the years over
gives SetHealth(0, 2) (0x472FC6..0x47304A). Heathen Aging already applies this to Heathens.

**The body.** The per-frame update 0x4671E0 turns any record whose health is 0 or less into a body (0x46724A), with
no faction test. An unburied body is removed 240 minutes after death at 0x46FF12 (`88 9E D4 1C 00 00`; the Cause of
Death companion hooks it as "never buried"). The removal has no faction test.

**Burial.**

- The chooser 0x46F130 runs only once project 6 (the Buried Mausoleum) is restored.
- Its body finder 0x470940 has **no faction test**. The chooser stores the body index in 0x547D54 and starts
  behaviour 0x30 "Burying the dead" (script 0x45B5D0).
- The script walks to the body, then queues op 0x1D (0x475220(body)), then walks to the mausoleum door
  (0x7D + rand(20), 0x6BD).
- **Op 0x1D = 0x473F50 writes the grave at the pick-up**, before the carry walk:

```
473F8F  mov byte [esi+0x1CD4],0      ; record freed
473F96  mov ecx,[ebx+0x1B80] ; mov edx,[ecx+0x1C94] ; push edx ; push esi
473FA4  mov ecx,0x5481A8              ; the Roster of the Dead
473FA9  call 0x464C70                 ; E8 C2 0C FF FF
473FAE  pop esi                       ; (Cause of Death hook)
```

The faction byte +0x1CEC is intact at 0x473FA9: from 0x46F950 to the call, only +0x1CD4 is written. (Provable.)

**The Roster of the Dead.**

- 0x5481A8: 500 entries × 0x5C, then a 500-dword burier-id array at +0xB3B0 that is never saved, and a count at
  +0xBB80.
- **The writer 0x464C70** is a true thiscall: it stores ecx at 0x464C73 and takes the first entry whose age (+0x1C)
  is 0 (0x464C80). It returns 0 when all 500 are full (0x464C93).
- Entry fields: name +0, age +0x1C, head +0x20, body +0x24, profession +0x28, skill value +0x2C, flags +0x31..+0x33,
  cause +0x34, epitaph +0x38 (char[0x20]).
- **Save and load.**
  - Save 0x4244F0 → 0x464BA0 copies the entries to save buffer +0x854.
  - Load 0x464EF0 copies entries **until the first age-0 entry** (0x464F15).
  - Load checks each name (0x464B70), age ≥ 0, profession -1..5 and cause -1..4. **Any invalid entry fails the whole
    load** (0x464F6F). (Provable, re-checked here.)
  - So nothing foreign may ever go into the stock table, and a hole truncates the roster at the next load.

**The screen.**

- CMausoleumScene: vtable 0x49A12C, getter 0x43F4B0, scene id 0x14.
- It is opened by 0x43CC00, which takes no arguments and does not use ecx.
- 0x43CC00 is called from the area-0x19 handler 0x43CDE0 (the Buried Mausoleum puzzle) on a click once project 6
  is done.
- It reads the roster at exactly four immediates, each `B9 A8 81 54 00`: 0x43F4F1 (count via 0x464E90), 0x43F735
  (row draw via 0x464E70), 0x43FDC0 (click), 0x43FED6 (hover).
- Art: 0x35 mausoleum_ui_bg.jpg, 0x40 graves.png, 0x3F mausoleum_tint.png, knob 0x39-0x3B, arrows 0x3D/0x3E.
- Five graves a row; the grave dialog is 0x41C3F0(entry).

**The mud hut.**

- It has no area handler. 0x444310 only shows point-hover text; it does not dispatch.
- The map's 320×320 cell grid is at 0x718EE8. Bits 15..24 of a cell are the hotspot id that indexes the area-handler
  table **0x77DC80**: 12-byte entries {handler, highlight type, permission}, filled by 0x479810.
- Click: 0x443AEB → 0x479740 → handler(2, 0).
- Drop: 0x4441DA / 0x444212 → 0x4794A0 → handler(0, villager).
- Holding a villager over the hut: 0x4462CD → 0x479780 → handler(1, villager).
- Hotspot ids 0x0B and 0x21 have no cells in lcmap.dat and no handler. Hotspots are only ever set from lcmap.dat:
  the rect stamps 0x478440 and 0x478540 leave them alone.
- The hut's blocked cells are about x 2178-2290, y 1464-1560.
- The hovel cover (sprite 0x1B) is drawn at (1705, 1459) once puzzle 25 is solved (0x4370E0).
- The hotspot field is 0 everywhere in x 2080-2360, y 1440-1640 (lcmap.dat, read from a research copy).

**(b) What it takes:** a new companion, "VVFP Heathen Mausoleum.dll" (workstream W-C).

1. **Burial routes by faction.** Splice 0x473FA9 (`E8 C2 0C FF FF`) to call a stub:
   - when `[[esp+4]+0x1CEC] != 0` and the row is on, swap ecx to the companion's own 0xBB84-byte table;
   - then tail-jump to 0x464C70.
   - The game's own writer fills the Heathen entry by every stock rule (epitaph, cause, the Preferred Job Graves
     bytes). Presence, deselect and step-done run unchanged.
   - **The dead one's faction at death decides**: a Heathen (camp-born, arrival, puzzle Heathen or former villager)
     goes to the mud hut; a believer goes to the Roster of the Dead as now.
   - When the Heathen table is full (500), the stock rule applies: no grave, the body disappears, and the Death record
     says "the mud hut memorial was full".
2. **The burial walk.** For a Heathen body (index in 0x547D54 when script 0x45B5D0 queues its walks), the carry walk
   goes to the mud hut (the memorial walk points 2176-2272 × 1576-1600) instead of the mausoleum door (Q11 a).
   Hook: the walk's coordinate push in 0x45B5D0. The exact bytes are W-C's first task (Unknown here).
3. **Storage.**
   - **Path:** `...\Virtual Villagers Fun Patcher\Save <S>\Data\Heathen Mausoleum\Heathen Mausoleum - Save <S>.dat`.
   - **Format:** header 'VHM1', version 1, game 5, count, slot; then `count` entries in the stock 0x5C layout, packed
     with no holes.
   - The loader validates each entry by the game's own rules (printable name, age > 0, profession -1..5, cause -1..4).
     It rejects the whole file otherwise, and an unreadable or invalid file is set aside, never overwritten
     (sidecar_io.h).
   - **It must match the save** (the repo's "logs match the save" rule): a burial is staged in memory and published
     only when the game saves, so a quit without saving never leaves a grave for a body that is still lying in the
     save. W-C hooks the save path and decides on the hook as its first task:
     - the call at 0x424569 inside 0x4244F0 that copies the roster, followed by a publish; or
     - the save-arm pattern the Cause of Death companion uses (`VvfpCauseArmSave`).
     - Rated Likely; must be confirmed by emulation.
   - The file is read when the slot is first seen (as `keep_known`), and a Change Tribe switches files.
4. **The screen.**
   - Replace the four immediates with `call get_view`, a stub that does `mov ecx,[g_view]; ret`. It is balanced,
     because the arguments were pushed before. g_view defaults to 0x5481A8.
   - Wrap the stock opener's call at 0x43CE24 (and the area-0x0C handler 0x47A3F0, Likely dead code) to set g_view
     back to the believers' table.
   - **Never swap the table contents**: a save or burial while the screen is open would mix the two rosters (Likely).
   - Only native art: the same screen art is reused as is (Q13).
5. **The hovel.**
   - Register hotspot id 0x0B in the table at 0x77DD04 = {handler, 6, 1} after the startup registration. Permission
     1 lets a child or a pregnant villager be dropped.
   - After each lcmap load (calls at 0x423E2B `E8 80 37 05 00` and 0x4246E1 `E8 CA 2E 05 00`), stamp 0x0B into the
     hotspot field of the hut's rect.
   - The rect must stay clear of hotspot 0x2C, whose box reaches x ≥ 2112. W-C picks it from lcmap.dat and shows it
     to the owner.
   - The handler: on event 2 (click) or 0 (drop), set g_view to the Heathen table, call 0x43CC00 and return 1. On
     event 1 (hover), return 1 with no text.
   - Nothing else reads id 0x0B: the other hotspot readers compare against fixed ids 0x16, 1, 0x2B, 0x22 and 0xE
     (Provable).
   - **Open point (Likely):** a click with a villager under the cursor probably selects the villager first. That is
     the same as the stock mausoleum.
6. **The Cause of Death companion** (`native/vvfp_cause_of_death/cod_vv345.inc`):
   - The hook at 0x464E51 (`5EB0015D59`, the writer's exit) reads the entry from the hard-coded 0x5481A8. It must take
     the table base from the saved `this`, which the writer keeps at [esp+8] there, and name the grave as the mud hut
     memorial.
   - The epitaph editor (`cod_epitaph_edit.inc`; VV5 0x41CB33/0x41CB4B) must accept an entry outside 0x5481A8.
     Unknown: how it maps an entry back to a slot.
7. **Generations** need nothing more: babies grow up (Heathen Aging ages them), couples form (section 5), and the
   parents are on each record (deliver()). The Family Tree and the logs already carry the parents; the Family Tree
   leaves Heathens out today.
8. **Start Over and a deleted tribe.** `VVFP Save Reset.dll` (`native/save_reset_export`) calls a new export,
   `VvfpHeathenMausoleumVillageReset(game, slot)`, before it deletes the slot's folder, the same as
   `VvfpHeathenAgingVillageReset`.

**Existing Heathen graves in the believers' roster.**

- They are known by their KIND_GRAVE entries in the Heathen Aging .dat.
- Recommendation (Q12): **leave them.** `VvfpHeathenAgingGrave` keeps them out of the Village Elders.
- Moving them would need the stock roster repacked (holes truncate it at load), and their entry numbers would shift
  under the Cause of Death records and the epitaph editor.

**A former villager who died a Heathen.**

- In the stock game the faction is never read on the body path (0x470940, op 0x1D, the 240 removal), so a former
  villager's body is buried in the Roster of the Dead like anyone's (Provable).
- With the splice, the faction at 0x473FA9 decides, so a former villager who died a Heathen goes to the mud hut.
- Whether a body exists at all stays with the skeleton rows:
  - the new row: every Heathen;
  - "Former Villagers Among the Heathens Leave Skeletons" alone: former villagers only.
- By Q14, W-C's DLL ships with either row, so the mud hut works for the Former Villagers row on its own too.

**(c) Risks.**

| Risk | Rating |
|---|---|
| The stock save never carries the Heathen roster; it lives only in the .dat. Load validation is the game's own rules, so a bad file is rejected, never fed to the game. | Provable |
| The .dat and the save going out of step on a crash between the save and the publish. | Likely; mitigated by publishing right after the save write (sidecar_io's atomic replace) |
| Statistics: burials 0x51D39C are guarded by the Statistics row's faction guard at 0x473F8F. Heathen graves no longer enter 0x5481A8, so Village Elders and Day of Honor (0x414DB5), and Honoring (0x46B11B), see believers only, which is what's wanted. "Villagers Buried" in the export must skip Death records with a Heathen Faction line (`is_heathen_record`). | Provable / Likely |
| 150 / 256: the roster is 500 entries in both builds. The 256 build only appends after save offset 0x17D78, so +0x854 is unchanged. | Provable |
| Other rows: Memorial Actions at the Heathen Hovel patches 0x46409E, 0x46B145 and caves 0x494B40/0x494DA0, with no overlap. No other companion touches 0x473FA9, the four screen immediates, 0x77DC80, 0x4794A0, 0x479740 or 0x4775B0 (grep of native/, scripts/, data/). | Provable |

**(d) Effort:** M (the burial and screen) + S-M (the hovel) + S (the Cause of Death change). It is independent of
features 1-3.

---

## 7. Feature 5: age as normal, get sick and eat, never starve or die of sickness

**(a) The stock game.** The believer half of one unit (0x472CDB..0x473356), in order:

1. Faith drift (0x468040 at 0x472D17).
2. Divine Energy (0x424F80).
3. The meal: food -2 (0x472DA5). At food ≤ 500, a rand < 30 hunger hit AddHealth(-1, 1 Starvation) (0x472D97).
4. Starvation at food ≤ 0: AddHealth(-1, 1) (0x472E4B).
5. Sickness damage: AddHealth(-1, 0 Disease) at 0x472ED1, on rand ≤ 60 when health > 20, otherwise on a further
   rand ≤ 30.
6. Recovery: +1 (0x472EE2..0x472F65).
7. Sickness onset 0x465F50: Medicine 1 rand(1440) ≤ 3, Medicine 2 rand(2460) ≤ 3, Medicine 3 rand(5400) ≤ 2, then
   elders rand(1000) ≤ 14. It returns 1 when the villager is already sick: a sickness never ends here.
8. Old age.
9. Trophies.
10. Birth.
11. Catch-up job turns 0x46E8E0.

Where sickness ends: only a cure ends it (0x468CCB, 0x46E1FB) or an island event (0x4161FA/0x416203). Healers never
target a Heathen: 0x470B50 has `cmp byte [esi+0x1CEC],0 / jne` at 0x470B7F. (All Provable.)

**(b) What it takes.** **Never send a Heathen into the believer half**: it would draw on the food store, drift the
Faith, add Divine Energy, give trophies, run job turns and start believer births. Instead, a Heathen life step, called
from Heathen Aging's existing 0x472CB7 stub once per unit through a bridge export, `VvfpHeathenLifeUnit(record)` in
"VVFP Heathen Life.dll" (W-B):

- **Eating, for show:** no write to 0x51D34C and no hunger damage. A show meal (section 8) now and then.
- **Getting sick:** call 0x465F50(record) itself. Keep the sick byte: the stock skip's `mov byte [esi+0xC],0` is
  bypassed for these Heathens, which the bridge's return value controls. On a new sickness, stop the activity
  (0x473440) and start behaviour 0x20, as the believers do. Whether 0x20 (0x45C3A0) suits a Heathen is Unknown; it
  calls 0x43AE80 and 0x464F90. W-B checks this by emulation, and falls back to a show "rest" if not.
- **Sickness damage:** the believers' rule, but health never goes below the floor (Q8: 21 recommended). It is written
  with AddHealth with cause -1, never a cause that could kill.
- **Recovery:** the "not sick" +1 rule, and getting well on their own (Q8 a). The recommended recovery rate is the
  believers' cure as if a healer came: 1 in 240 per unit, about once a day.
- **Never starve:** Heathens have no hunger (the store is the believers').
- **Other damage.** Island events that hurt a Heathen go through `VvfpHeathenAgingEventGone` (their own rules, as
  now). Ordinary island events' AddHealth (0x4156C5 and others) can still reach 0 for a Heathen selected by Story
  Upgrades. That is a death by an event, which the owner allowed on 2026-11-23, not a death by sickness.

**(c) Risks.**

| Risk | Rating |
|---|---|
| Save integrity: only the record's own sick byte and health change, within the game's own ranges. | Provable |
| People Cured untouched, unless Q8 (b) is chosen; then the companion must put back 0x51D368 (incremented at 0x46E202). | Provable |
| A converted sick Heathen stays sick as a believer: an ordinary believer sickness. | Likely, harmless |
| Heathen Aging owns 0x472CB7, so W-B never splices it. A second DLL there is refused by install_sites. | Provable |

**(d) Effort:** M. It needs the bridge (W-A) first.

---

## 8. Features 6 and 9: show harvests and facility visits

**(a) The stock game.**

**The believers' next-action picker** is 0x46F070, called up to 10 times by 0x46F3DA. Fix Huts hooks its entry
(`83 EC 08 53 56`). The faction test at **0x46F0BA** (`38 9A EC 1C 00 00 74 0D`) sends a Heathen to the Heathen AI
0x46E9E0.

**The Heathen AI:**

- rain shelter 0x4B;
- children → 0x46E3F0;
- rand < 3 gestures 0x469DC0;
- then a switch on role - 1 (jump table 0x46F020): role 1 0x97 (noni), 3 and out of range 0x9C (camp wander,
  handler 0x455E80, walk area 0x39), 6 0x91/0x9A, 13 0x0B, 14 0x0C, 15 0x9A/0x0E, 16 0x0D, 17 0xC0, and so on.

Behaviours run through 0x465580(id) → handler table 0x5475C8 (231 entries). The steps:

| Adder | Step |
|---|---|
| 0x4744C0 | walk to an area |
| 0x474450 | gesture |
| 0x474780 | skill check, which runs 0x46B270 |
| 0x4747E0 | wait |
| 0x474D80 | carry |
| 0x474DE0 | drop |
| 0x474EF0 | event: the payoff, through 0x46CE60 |

**Harvest payoffs**, where the source is taken:

| Source | Behaviour | Event | Effect |
|---|---|---|---|
| Noni | 0x6C | 0xC at 0x46CFCD | noni stock game+0x17D58 decremented at 0x46D000 |
| Food Totem noni | 0x82 | 0xD | stock decremented at 0x46D079 |
| Crops | 0x6D | 0xE | crops game+0x17D5C decremented at 0x46D113 |
| Fish | 0xE9 | 0x10 | +4 food; the lake has no stock |
| Mushrooms | none | | a collectible a child picks up when the player drops it; delivered at 0x41496B, counter 0x51D36C |
| Stock Heathen noni | 0x97 | 0x53 at 0x46DA43 (`83 86 58 7D 01 00 FF`, re-checked) | noni -1 on 40% |

**Facilities.**

- A sweep of every `[reg+0x1CEC]` read found none inside the building or puzzle handlers (0x432400..0x43CBC8), so no
  facility turns a Heathen away. The gate is only the picker. (Provable for direct offsets.)
- But real facility behaviours do real work: build points (0x434D20), conception at the love shack, skill checks,
  tech points (event 0x5A uses 5,000) and food (event 0x57). (Likely)
- Which behaviour ids are sleeping, the spa or the kitchen is Unknown.

**(b) What it takes.** Show-only scripts, built in W-B from the game's own step adders: walk to the source or
facility area, gesture or the eat animation (0x475160(0x6F, 2, 1.0)), wait, optional carry and drop for the look,
then walk back to the camp (area 0x39).

- They **never** include a skill-check step or an event step, so no source, store, building, tech point or skill is
  touched.
- Hook: splice the Heathen AI's default case at 0x46F007 (`8D 44 24 1F 50 6A 50 ...`; W-B re-reads it before relying
  on it) or the picker's test at 0x46F0BA. Sometimes, by a mix rate, an adult Heathen with no puzzle duty gets a show
  script; otherwise the stock AI runs.
- Puzzle roles 12-17 keep their stock behaviours always, so no puzzle is changed.
- Mushrooms: a walk and a gesture at a spot. Where the mushroom places are is Unknown; W-B takes them from the
  collectible spawn data.
- Facilities (Q10): a show visit to the facility's walk area. W-B first maps each facility to its area id by reading
  each handler's first 0x4744C0 argument.
- **Not recommended:** reusing the believer behaviours 0x6C/0x6D/0xE9/0x33 for Heathens. That would need guards at
  0x46CE60 (`8B 44 24 04 83 EC 1C`) and 0x46B270 (`83 EC 0C 53 55 56 8B F1`), both re-checked. Those are hot,
  shared routines, and the Food Gain hooks (0x46CFFB, 0x46D10E, 0x46D79C, 0x41496B, 0x46CF9C) sit inside their paths.

**(c) Risks.**

| Risk | Rating |
|---|---|
| Sources and the food store untouched by show scripts. | Provable by construction, since no event step is queued |
| Walking far from the camp: Heathens walking among the believers' areas is new. Pathfinding never gives up (repo rule), but long walks crowd the paths. | Likely |
| Fix Huts at 0x46F070 is separate from 0x46F0BA/0x46F007. | Provable |
| Statistics untouched. | Provable |

**(d) Effort:** M for harvests; L for facilities (each id needs mapping). After W-A's bridge, in parallel with
feature 5.

---

## 9. Feature 7: new Heathens take the same positions and masks (a new Chief, new Masters)

**(a) The stock game.**

- Roles 12-17 are the puzzle Heathens (section 3). The mask art comes from the role: 0x4728C6 indexes table 0x472B60
  by role - 12. Roles 12, 14, 15 and 16 draw the purple mask (type 3), role 13 the Chief's (type 4). Otherwise orange
  (+0x1CED) is type 1, red (+0x1CEE) type 2, and neither is blue.
- Preaching refuses roles 12-17 (0x468DDC..0x468E12). Earthquake skips them (0x41F76B).
- The role finder 0x470690 returns only the first match.
- Converting resets the role to 0 except role 13 (0x466966), so a converted Chief becomes the Retired Chief (the
  scheduler at 0x46F1DD).
- When a station's puzzle is solved the role is rewritten (0x46EB03 and others). 0x469F20 hands out a random role
  among the stations whose puzzle is unsolved, plus 0.
- Heathen Aging today replaces a dead puzzle Heathen while its puzzle is unsolved, set up exactly as 0x424AC0 sets
  that role up (`create_role`).

**(b) What it takes** (W-A, inside Heathen Aging):

- **Puzzle unsolved:** today's rule stays. A new one in the same role, as the stock set-up makes it, only when
  `0x470690(role)` is 0.
- **Puzzle solved** (Q6):
  - (a) Cosmetic: when the old Chief or Master dies, the eldest adult Heathen (or a new arrival) gets that role's
    stock skills (Chief: all six at 100; Master: 90 in the role's skill) and the custom title ("Heathen Chief",
    "Heathen Master Builder", ...) through the Custom Titles file (`custom_titles.h`), with role 0..11. S effort.
  - (b) The real role 13-16 after The Last Heathen: the stock mask art. The new Chief cannot be preached to. A
    converted 13 must lose the role first, or it becomes a second Retired Chief: hook 0x466966, or set role 0 in the
    credit pass before conversion. That interacts with 0x46AB80 and 0x45433B (Unknown). L effort.
- **Masks for babies and arrivals** (Q7): written in +0x1CED/+0x1CEE through the creator's own orange and red
  arguments.
  - "Heathens Keep Their Masks When Converted" keeps a mask nibble per record (0x7B1D20, or 0x7F1400 in the 256
    build) from those same bytes, so it carries a new Heathen's mask with no change.
  - "Fog of Doom Lets Red and Orange Heathens Listen" reads the same bytes: a red arrival is a chaser.

**(c) Risks.**

| Risk | Rating |
|---|---|
| Real roles break puzzles: a second role-16 Heathen is never found; preaching refusals block conversion, and with it The Last Heathen. Hence (b) only after puzzle 25. | Provable mechanisms, Likely effects |
| Custom titles are per-villager data already kept per save. Heathens never count. | Provable |

**(d) Effort:** S for (a), L for (b). After arrivals.

---

## 10. Feature 8: skills grow by practice, devotion included

**(a) The stock game.**

- **The skill check 0x46B270(skill)**, a step in an action script:
  - It passes on `rand(100) <= skill + base`. The base is 33, or 66 if the villager likes Learning (preference 0x27),
    or 16 if they dislike it. Learning tech 2 or 3 adds 15 or 30.
  - The gain on a pass is `(70 - s) / 18` (magic 0x38E38E39, `sar 2`). It is doubled for a liker and halved for a
    disliker. At 0 or less it becomes 1 on `rand(100) <= 50 && rand(100) >= s`.
  - Only Devotion adds the Spirituality level (0x423600(5) at 0x46BC82). A skill at 100 skips the gain.
  - On a failure, a skill at exactly 0 gets +4; the activity stops, with messages.
- **The adder 0x475730** clamps the skill to 0..100. On crossing 88 it gives trophies 0x20..0x25, and with all six at
  88 or more, 0x26 and 0x27.
- No Heathen ever reaches a skill check: the Heathen behaviours have none found, and the tick skips them (Likely;
  the scripts were not walked step by step).

**(b) What it takes** (in W-B's `VvfpHeathenLifeUnit`):

- Now and then, an adult Heathen "practises": the skill of its role, or of its show action when it has one; see the
  table below.
- The believers' pass and gain formula is used, with the Learning likes and dislikes and **no tech bonus**: the
  Learning and Spirituality techs are the believers'.
- The float is written directly, clamped to 0..100. **Never call 0x475730** (trophies) or 0x46B270 (messages,
  activity stop).
- Devotion: Heathens practise it at the camp's own totem or the mud hut, as a show "devotion" action. The rate is the
  same as any skill.
- Practice runs on 1 unit in 20 (about once in two real hours per Heathen). That is a design choice, an inference, not
  a stock rate.

| Role | Skill practised |
|---|---|
| 1, 11, 16 | Farming |
| 2, 10, 14 | Research |
| 6-9, 15 | Building |
| 5, 17 | Parenting |
| 4, 12 | Healing |
| 0, 3 | the best skill |

**(c) Risks.**

| Risk | Rating |
|---|---|
| Conversion keeps the skills (Q17). | Provable |
| Esteemed Elder and mastery statistics count believers only, at the time of counting. | Provable (Heathens never count) |
| Save integrity: float writes within 0..100. | Provable |

**(d) Effort:** S-M. After the bridge.

---

## 11. Logs: every Heathen event is recorded and marked as a Heathen

The rules (`docs/log-parity-matrix.md`, `src/vv_log_additions.py` lines 1151-1175):

- Every Heathen record carries "Faction: Heathen", or "Isolan" with the Guardians of Isola Rewrite.
- Every reader that counts the village leaves those records out (`is_heathen_record`).
- Heathens are VV5-only, so a Heathen-only record kind breaks no five-game parity.

| Event | Log | Who writes it, and the export | New export? |
|---|---|---|---|
| A couple forms | Births and Conceptions: a "Couple" record (both names, ages, Faction) | Parentage Export | **Yes**: `WriteParentageHeathenCouple(game, woman, man)`, if the owner wants it (Q16) |
| A conception, with twins and triplets | Births and Conceptions: Conception record with the expected number of babies | Parentage Export `WriteParentageRecordWithFather` / `WriteParentageRecordCarried`, called by Heathen Aging after its forced 0x465E00 (story_log_conception pattern) | No. **Fixes the gap** in section 5 |
| A birth | Births and Conceptions: Birth record (litter) | `WriteParentageBirthLitter` + `VvfpCauseNoteArrival` (tell_born, as now) | No |
| A group joins | Births log: one Arrived record per member, "Joined the Heathen tribe" or "... with N others" | Cause of Death `VvfpCauseHeathenArrived(game, index, how)` | No (new words only, with Isolan forms in `isolan_log_words.h`) |
| A new arrival (also after The Last Heathen) | Arrived record "Arrived at the Heathen camp" | `VvfpCauseHeathenArrived` | No |
| A replacement (today's rule) | Arrived "Replaced a Heathen ..." | `VvfpCauseHeathenArrived` | No |
| A new Chief or Master takes the role | Births log: a "Took the role" record (name, role, Faction) | Cause of Death | **Yes**: `VvfpCauseHeathenRole(game, index, role)` (Q16). A replacement made into the role already says so in its Arrived record. |
| Sickness and recovery | none | | Not logged: no believer log records sickness or recovery. A grep of `native/vvfp_cause_of_death`, `native/parentage_export` and `src/vv_log_additions.py` found no such record (Likely). |
| Skill milestones | none | | Not logged: the believers' logs have no milestone records (same grep, Likely). The Village Statistics' masteries are believer statistics. |
| Death with no body | Deaths: Death record, "no grave (died among the Heathens ...)" | `VvfpCauseDiedAmongHeathens` (as now) | No |
| Death with a body, buried at the mud hut | Deaths: Death record at the burial, Grave "the mud hut memorial" | Cause of Death's 0x473FAE / 0x464E51 hook, reading the table base (section 6 b6) | No new export; a change in `cod_vv345.inc` |
| A body never buried | Deaths: "never buried" | Cause of Death 0x46FF12 hook (as now) | No |
| Island events | Island Events log entries | Story Upgrades / `WriteVillageEventEntry` (as now) | No |

Heathens still never count:

- the Statistics export reads none of these, because each carries the Heathen Faction;
- Heathen graves no longer enter 0x5481A8;
- the old ones stay excluded by `VvfpHeathenAgingGrave`.

---

## 12. Splice sites (stock bytes re-checked for this document)

| Site | Stock bytes | Owner | Purpose |
|---|---|---|---|
| 0x470077 | `38 9E EC 1C 00 00 8B F8 75 0C` (or `75 38`) | Heathen Aging (existing) | age credit |
| 0x472CB7 | `80 BE B0 00 00 00 00 74 1B` | Heathen Aging (existing) | life tick; bridges to Heathen Life |
| 0x46F0BA | `38 9A EC 1C 00 00 74 0D` | Heathen Life (new) | show-action mix (or 0x46F007) |
| 0x473FA9 | `E8 C2 0C FF FF` | Heathen Mausoleum (new) | burial routing |
| 0x43F4F1, 0x43F735, 0x43FDC0, 0x43FED6 | `B9 A8 81 54 00` each | Heathen Mausoleum | screen table |
| 0x43CE24, 0x47A3F0 | (W-C reads them) | Heathen Mausoleum | stock openers set the believers' table |
| 0x423E2B / 0x4246E1 | `E8 80 37 05 00` / `E8 CA 2E 05 00` | Heathen Mausoleum | stamp hotspot 0x0B after the lcmap load |
| 0x77DD04 (data) | 0 | Heathen Mausoleum | hotspot 0x0B handler entry |
| 0x45B5D0 (walk push) | (W-C reads it) | Heathen Mausoleum | carry a Heathen body to the mud hut |
| 0x464E51 | `5E B0 01 5D 59` | Cause of Death (existing) | entry read from the table base |

All are installed through `native/shared/install_sites.h`: stock bytes are checked first, all or none.

---

## 13. Workstreams (3-4 builders, one release)

Each workstream owns its files. The only shared code is one new header.

**W-0. The interface** (first, small; the W-A builder). New `native/shared/heathen_evo.h`:

- **Bridge exports:**
  - `int __stdcall VvfpHeathenLifeUnit(unsigned char *record, int flags)`, exported by Heathen Life and called by
    Heathen Aging's unit() through GetModuleHandleA/GetProcAddress, never LoadLibrary. It returns bit 0 "keep the sick
    byte" and bit 1 "handled".
  - `int __stdcall VvfpHeathenAgingCoupleOf(int index)`, exported by Heathen Aging for the logs and Heathen Life.
  - `int __stdcall VvfpHeathenMausoleumIsHeathenGrave(int entry)`, exported by Heathen Mausoleum for the Cause of
    Death and the statistics.
  - `void __stdcall VvfpHeathenMausoleumVillageReset(int game, int slot)`.
- **Settings and flag files** in the patcher folder:
  - `VVFP Heathen Tribe Evolution.txt` (the row's flag, which replaces the Tribe, Skeletons All and Events flags);
  - `VVFP Heathen Tribe Births.txt`;
  - `VVFP Heathen Arrivals.txt`;
  - `VVFP Heathen Options.txt`, with key=value lines for the owner's choices (group size, mask mix, sick floor, show
    mix), parsed by a small reader beside `multiplier_choice.h`.
- **The data file formats:** Couples (section 5) and Mausoleum (section 6).

**W-A. Tribe life and population.** Owns `native/vvfp_heathen_aging/*`, `tests/test_vv5_heathen_aging.py` and the
emulator tests for it.

- reading the new flag (and the old three, so old patch sets still work until W-D migrates them);
- the births slider (own xorshift);
- arrivals and groups, and the after-25 rule;
- the record cap (Q18);
- the couple table and kin test;
- the litter roll;
- roles and masks (Q6, Q7);
- the conception-log fix;
- the bridge call into Heathen Life.

**W-B. Heathen Life.** New `native/vvfp_heathen_life/` ("VVFP Heathen Life.dll") and its harness/emulator tests.

- sickness (onset, floor, recovery);
- show eating;
- show harvests and facility visits (the 0x46F0BA / 0x46F007 splice);
- skill practice, devotion included.

It depends on W-0, and on W-A for the bridge call; until that call exists, W-B is tested by calling its export
directly.

**W-C. The Heathen Mausoleum.** New `native/vvfp_heathen_mausoleum/` ("VVFP Heathen Mausoleum.dll") and its tests.

- the burial splice and walk;
- the roster .dat staged until the save;
- the screen redirection;
- the hovel hotspot and handler;
- plus its edits in `native/vvfp_cause_of_death/cod_vv345.inc` (0x464E51 table base, the grave's words) and
  `cod_epitaph_edit.inc`, and the "Villagers Buried" exclusion in `native/statistics_export`.

It is independent of W-A and W-B.

**W-D. The patcher and the logs.** Owns:

- `src/vv_fun_patcher.py`, `src/vv_fun_patcher_gui.py` (the new row, its Settings… window with the two sliders and
  options, and the defaults: off / off in Select All / on in Owner's Defaults);
- the new `data/vv5_heathen_tribe_evolution_feature.json` and its build script, and retiring the three folded rows'
  JSONs;
- migration of saved selections and presets from the three old ids to the new one;
- the Former Villagers skeleton row shipping the Mausoleum DLL (Q14);
- `native/parentage_export` (the Couple export), and `native/save_reset_export` (calling the new reset export);
- the README, How to Use, `data/how_to_use.json`, translations, the transparency log, and the Game Mechanics sources
  `src/vv_game_mechanics*_vv5.py`;
- `src/vv_log_additions.py` readers for the new record kinds;
- the row tests.

**Merge order:**

1. W-0.
2. W-A: a shippable slice by itself, the sliders + folded rows + arrivals after puzzle 25.
3. W-C: independent; can merge before or after W-A.
4. W-B: needs W-A's bridge.
5. W-D last: it ships the three DLLs and the flag and settings files, so it needs their final hashes.
6. A combined build, the full test suite once (one heavy run at a time), and the live checks.

**The smallest slice**, for the first internal milestone (inside W-A plus a thin W-D):

- the two sliders;
- the folded rows under one flag;
- arrivals after The Last Heathen;
- the conception-log fix.

It ships nothing new on screen.

---

## 14. Effort and dependency summary

| Feature | Workstream | Effort | Depends on |
|---|---|---|---|
| 1 Sliders, arrivals after puzzle 25 | W-A, W-D | S + M | W-0 |
| 2 Groups join | W-A | S | 1 |
| 3 Couples, litters | W-A | M + S | W-0 |
| 4 Graves at the mud hut, Heathen Mausoleum Screen | W-C (+ Cause of Death) | M + S-M + S | W-0 |
| 5 Eat and get sick, never die of it | W-B | M | W-A bridge |
| 6 Show harvests | W-B | M | W-A bridge |
| 7 Positions and masks | W-A | S (cosmetic) / L (real roles) | 1 |
| 8 Skills by practice, devotion | W-B | S-M | W-A bridge |
| 9 Facilities | W-B | L | 6 |
| Logs | W-A, W-C, W-D | S each | the features |

---

## 15. What must be checked live before the release

- A Heathen birth, twins, a couple's second baby by the same father, and the Conception record of each.
- A group arriving.
- An arrival after puzzle 25 on a test village.
- A Heathen buried at the mud hut: the screen opens on a click and on a drop, the believers' roster is unchanged,
  and the Death record names the mud hut.
- A quit without saving right after a Heathen burial: no grave in the .dat.
- A sick Heathen staying at or above the floor and getting well.
- A show harvest: the noni and crop counts unchanged.
- The Village Statistics unchanged by all of the above.
- The 256 build: the same checks, with the cap.
