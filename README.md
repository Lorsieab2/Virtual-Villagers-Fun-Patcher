# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

**Supported game source:** This patcher only supports the games downloaded from the official **Last Day of Work (LDW) website** (ldw.com), where all five PC games are available for free â€” so there's no reason to get them from anywhere else. Every patch is pinned to the exact bytes of those free LDW builds. Other releases (for example the Steam version) are not tested and may have different bytes; if a game isn't the LDW download, the patcher rejects it rather than risk patching an unverified executable.

The app uses the supplied transparent `Island.png` artwork as its title-bar icon and as small image decorations around both its name and the credit:

`[Island image] Created with Codex AI. Made with love by Lorsieab2 :) [Island image]`

**Every feature has a "?" button.** Beside every patch, population mode, button, link and setting in the patcher window there is a small **?**. Clicking it opens a short, plain guide: what the feature does, how to use it (where it shows up in the game, what to click), and anything to watch out for -- for example that a patch needs another patch, that the game must be closed first, or that 256 Villagers (Experimental) keeps its saves in its own folder. On the All 5 Games tab, the **?** above each column of links is the guide for that link on every game's row. The guides ship with the patcher in `data/how_to_use.json`, and a test refuses any public patch, mode, button or setting without one.

The complete interface has a vertical scrollbar and supports mouse-wheel scrolling, so every patch option, game-folder field, action, and status message remains reachable on shorter displays.

Optional patches are shown under deterministic game-title headers in this order:
Virtual Villagers - A New Home; The Lost Children; The Secret City; The Tree of
Life; New Believers. Shared/all-games patches appear afterward only when they
exist, and each header is sorted by patch name and ID. Selecting a patch with a
prerequisite selects that prerequisite automatically; clearing a prerequisite
clears its dependents. The saved settings and patch logs record the resolved,
dependency-first selection. API and command-line requests that omit a required
prerequisite are rejected before any copied game folder or EXE is written.


## What's new in v1.35.80

- **A villager stays the same villager when their looks or title change** (all five games). A new head, body or mask, or a new title or special villager status (a Tribal Chief, an Esteemed Elder, a Golden Child, a Heathen converted), never means a villager left. In The Secret City the game gives a new Tribal Chief the chief's robe, a new body, and the Family Tree Maker showed the chief as *(left the village)* and again with a numeral. Now:
  - The Family Tree Maker, the Village Matchmaker and numbering follow a villager by what does not change: the name, the sex, the parents, the age, the likes, and an unbroken Village History. The looks only break ties.
  - When the records cannot settle whether an older record and a villager now are one villager, the Family Tree Maker asks, in one window beside the tree: **Same**, **Different** or **Don't know**, with both villagers' faces, looks, ages, dates and parents. Your answer is kept in Repair Saves & Logs' **Answered questions**, where you can change it. Don't know asks again next time.
  - Check Saves & Logs notes a change of looks; it no longer asks "Is this the same villager?".
  - The game no longer writes "Left the village" and "Arrived" Unaccounted records when a villager's looks and likes change at the same moment (the chief's robe), or when a villager's looks change and they die before the next save.
  - Repair Saves & Logs can add the missing "Appearance changed" record, with **Becoming the Tribal Chief (the chief's robe)** offered in The Secret City.
  - **Take off numbers given because a villager's looks or title changed** (Repair Saves & Logs). Each villager is listed with the evidence and asked about. When you say yes, the number comes off in the save and the logs, after a backup, and the change goes in the Repairs Made log. A villager with a genuine namesake keeps their number.

- **An answered question is never asked again** (Repair Saves & Logs, all five games). Every answer except "Don't know" is kept for the record or villager it is about, not for the line or file it is written in. It still holds after records are renumbered, after a log rolls into a new numbered file, after Move Files to Save Folders, after the game saves again, and after the patcher renames the villager. Before, "Only from now on", "Keep it" and "Keep both" were asked again at every Repair, and many questions came back whenever their record moved.
  - **Answered questions (N)...** in Repair Saves & Logs lists every answer of the save with its date. Change an answer (applied as a first answer is, when you click Repair: backup first, listed in the Repairs Made log) or clear it (asked again). An answer that no longer matches a question is listed too, never dropped.
  - Answers kept by earlier versions keep working, and are moved to the new form at the next Repair.
  - The lost-titles and The Lost Children's totem yes/no questions are asked once too.
- **The patcher's own renames are no longer questions** (Check Saves & Logs, all five games). After Number Duplicate Names or Give villagers last names, the next Check asked about villagers whose name, or mother's or father's name, the rename had changed ("mother Java in the save copy, Java I in the save", "possibly lost"). The patcher now keeps each rename it makes, reads the numbering listed in the Repairs Made log, and follows the villager to the new name.
- **Room for the parents of every villager who ever lived** (all five games).
  - A New Home: the parents file (`Parents (A New Home)\Virtual Villagers 1 Parentage Records - Save <n>.dat`) had one place per villager record, and a villager who passed away kept their parents only while their record stayed empty. In a village at 256 every death is followed by a birth into that record, so their parents were dropped. They now go to a list kept after the 256 records in the same file, which grows with the village: each is added once, never changed or removed. A file with nobody on the list is written exactly as before. **Restore A New Home Parents...** puts back the parents it used to list as "no room" (for example Etini, Fatai and Ginger Awanata) onto that list.
  - The Lost Children to New Believers keep a villager's parents on the villager's own record, which the game frees at the death and later gives to someone else. Every **Death** and **Disappeared** record now carries the villager's own parents (name, head and body, as the Village History prints them for the living), read before the record is freed, so the family tree and Villager Info keep them. A New Home's Death and Disappeared records do the same from its parents file (with Show Parents in Details Screen on). A villager with no recorded parents (a founder, an arrival) gets none. Older Death records are not rewritten: the tree still takes those villagers' parents from their Birth records and Village History snapshots.
  - **Patch every game again** after updating: the parentage companions changed. Not yet seen in a running game (checked by the C harnesses and tests).
- **A namesake's number is kept for life** (all five games). The oldest -- the first to appear -- is I. A number is kept for life and never lowered, removed or given twice: when a namesake dies the other keeps theirs, and a new namesake gets the next number after the highest ever used for that name, the dead and gone included.
  - Repair Saves & Logs: namesakes with the same looks are numbered too (the oldest is I; identical twins by the game's own order, the delivery's first child I); a record that cannot be tied to one of them keeps the name and is listed. What cannot be told for sure (a record without looks, a name too long for the game, a same-looks pair a Death record also names) is never guessed: it is left and shown to you as information, never as an error, and everything else is still numbered.
  - **Patch every game again** after updating: VVFP Number Names.dll changed. Not yet seen in a running game (checked by the C harness and tests).
- **The Unaccounted Villagers log follows villagers by who they are, never by record number** (all five games). A villager of the last save is matched to one in the village now by name, sex, looks, likes and dislikes with an age that fits, then through a changed head, a rename or a rejuvenation only when one villager on each side fits; a departure the game reported (a burial, a body's removal, a disappearance) accounts for the villager it names. A villager who only moved to another record -- every load packs the records, a full village reuses them, The Lost Children's Elder Totems move the totems out -- is neither Left nor Arrived, and one with a Death or Disappeared record is never Left. Before, the owner's Lost Children village got 112 false "Arrived" and 108 false "Left" records at its first load with the Elder Totems. **Patch every game again** after updating: the Cause of Death companion changed. Not yet seen in a running game (checked by the C harnesses and tests).
- **Repair Saves & Logs: Remove false Unaccounted records** (all five games). Every Unaccounted record the logs and the save contradict by identity -- the same villager Left and Arrived in one check, still in the village in the Village History, already there before, or a Death, Disappeared, Birth or Arrived record -- is listed with why, and taken out only if you say so (the game closed, the save folder backed up first, each log copied first, the Repairs Made log lists it). A record nothing contradicts is kept and listed. Check Saves & Logs reports them as WRONG, and its note "is Unaccounted (left the village) and has a Death record" says when the repair takes that record out. A Birth or Arrived record settles an Unaccounted arrival only when its age fits (they arrived no older than they are now) and no other villager of that name and look, dead or older, could be the one it is about; otherwise the record is kept and listed.
- **A villager renamed in the game no longer gets a second Arrived record** (all five games). The Arrived records' backfill follows "Name changed" records, as it follows "Appearance changed" ones; Repair Saves & Logs offers a "How: unknown" Arrived record already written that way (the owner's Coral Tangaroa and Mahalo Makawee I) as the duplicate it is. **Patch every game again**: the parentage companion changed.
- **Village Elders: an elder given a last name (or a number) since is never counted twice** (A New Home, The Secret City, The Tree of Life, New Believers). Repair's first-load reconcile no longer adds an older Village History snapshot's name ("Cheop") as a departed elder when the list or the village has the same villager under the newer name ("Cheop Bahati"). **Patch every game again**: the statistics companion changed.
- **Rarer false records, by identity** (the rest of the identity audit). Not yet seen in a running game (checked by the C harnesses and tests). **Patch every game again**: the Cause of Death, Statistics and A New Home Show Parents companions changed.
  - *The same village loaded again with no save between* (all five games): an arrival the game reported into a record counts only while that record holds the villager it was made for, so whoever the earlier save kept there never gets an Arrived record, and a newcomer the save never held gets none either. A villager back in the village after her own Death or Disappeared record -- a reload without a save and a record written back look the same -- is listed as exactly that in the Unaccounted log, never as "Arrived with no Birth record". A newcomer changed in place (renamed, say) keeps his arrival only while his age carries on from one look to the next; the saved occupant put straight into his record is never taken for him.
  - *A New Home, Show Parents*: when one of two villagers of one name, sex and family dies in play, the other keeps her own parents (before, both lost theirs), and after the next load her looks still tell her apart.
  - *Village Elders* (A New Home, The Secret City, The Tree of Life, New Believers): two elders of one name, one renamed and both moved by a reload, no longer swap lines; each line follows its villager by what a rename does not change (likes, dislikes, parents), and a line that cannot yet be told apart is neither added again nor closed. Giving last names or numbers (all five games) no longer renames a dead namesake's elder line, or a parent of that name, to the living villager's new name.
  - *A New Home's Golden Child*: a Birth record of another child of the same first name no longer counts as the Golden Child's own; the pregnancy the puzzle ended is asked about, never closed as lost without asking.
  - *New Believers' Former Heathens*: a former Heathen renamed while the file could not be written, or in the same moment as a birth or death, keeps her mark; when two villagers shared the old name, likes and dislikes, neither is given it. However long the file stays locked, no change waiting for it is ever dropped.
  - *Check Saves & Logs* now reports the duplicate "How: unknown" Arrived record of a villager renamed in the game (a "Name changed" record), as Repair offers it.
  - *Masks and custom titles* (The Lost Children, The Tree of Life, New Believers masks; custom titles in all five games): when one of two villagers of one name and looks dies during play, the other keeps her own mask or title (nobody moves during play; after a load the same picture is still never guessed). A rename in the same moment as a birth or a death is followed. **Patch every game again**: the Origins and Story / Cheat Upgrades companions changed.
  - *The Family Tree Maker*: a villager born with the name and looks of one who died is another person -- the living one is the Birth record naming the parents her own record keeps, the Death record is the other one's; when that cannot be told, no Birth or parents are guessed for either, and the tree's notes say so.
  - *Village Elders' first-load repair*: a dead elder whose namesake lives (the same name, or a name a last name grew into) is counted, once, by her own Death or Disappeared record; a listed line counts one elder of its name and parents, never twice.
- **The Lost Children: stale copies at the end of a save are no villagers.** The game does not zero the entries after its last villager; after deaths at a full table it leaves frozen copies there (the owner's save: four living children copied into entries 252-255). Every reader of the save -- Check, Repair, last names, numbering -- now stops at the entry the game flags as the end, as in the other four games, so no villager is counted twice. A Repairs Made answer given from those copies ("the same villager; the age was changed", Hoya Kalama 113 vs 88) can be changed in Repair Saves & Logs.
- **Totem colours are numbered 1 to 8** (The Lost Children). The Change Totem Colour window shows each number under its picture (1 is the leftmost of the game's own totems, 8 the rightmost) and lists each totem as, for example, "Amina Awanata's totem (colour 2, head 6, body 26)". The same numbers name a totem's colour everywhere: the Repairs Made log, the Story / Cheat Upgrades picker and the Island Events log ("Totem: colour 2 -> colour 5"), instead of words for how it looks. **Patch The Lost Children again** after updating: the Story / Cheat Upgrades and Island Events companions changed.
- **An elder's totem follows the patcher's own renames** (The Lost Children, Repair Saves & Logs). A statue that kept the name its Esteemed Elder had before Number Duplicate Names, Give villagers last names or another rename the patcher made (kept in its Log Decisions file or listed as "Renamed:" in the Repairs Made log) is that elder's for certain, with the same looks: it is no longer asked about (for example Azizi Kalama's totem and Azizi Kalama I). The in-game automatic totems use the same renames. A totem question that is still unsure is asked once: Yes or No is kept by who the elder is and what the statue is, listed in **Answered questions** to change or clear, and never asked again.
- **Sort by in the last-names windows** (Repair Saves & Logs: last names, and Each villager's own rule..., all five games). A "Sort by:" list orders the villagers: **As in the save** (the order the window always used, the default), **Alphabetical (first name, then last name)** (numbered namesakes in numeral order: Kalama I, II, III), **Arrived at top** (villagers who arrived through an event first), or **Age (oldest to youngest)** (the dead and gone by their age at death or when last seen). Re-sorting keeps every last name chosen or typed; nothing is written until OK. The choice is remembered until the patcher closes.
- **The in-game windows can be resized, and nothing in them is cut off** (Story / Cheat Upgrades and the Origins menus, all five games). Every window the patcher's companions open in the game has a sizing frame and minimise / maximise buttons; lists, text and drop-downs grow with it. **Pick Gong of Wonder Outcome** now uses the Pick Island Event layout: Random first, then all 23 results under Tier A, B and C in the game's own words, each with only its own settings. Every villager list in the Upgrades menus can be sorted by **Age (oldest at top)** or **Alphabetical (first name, then last name)**. **Patch every game again** after updating: the Story Upgrades and Origins companions changed. Not yet seen in a running game (checked on real Windows controls by the dialog-kit harness, the emulator and tests).
- **Custom Island Event: every villager action, "Celebrating" included** (all five games, Story / Cheat Upgrades). The action list under Villager Changes now holds everything the game's own code can start for one villager -- jobs and idle actions, the island events', the puzzles', the Golden Child's, the Tribal Chief's and the Heathens' -- for any villager, child or Heathen alike: 116 in A New Home, 161 in The Lost Children, 206 in The Secret City, 201 in The Tree of Life and 243 in New Believers (was 39, 49, 61, 57 and 51) -- also the game's own choosers, burial, the action runner, empty handlers and walking steps (each labelled with what it does), and picking up what lies where the villager stands. Each is labelled with the text the Details screen then shows ("Celebrating", "Celebrating Isola Day", "Honoring the Dead"...), and the list is grouped (Work, Leisure, Celebration and dance, Devotion, Family, Children, Health, Curiosity, Moods, Puzzles and story) and sorted. "Celebrating" starts the game's own celebration: in A New Home and The Lost Children at each place the village celebration uses, in the later games the celebration action itself. An action that may harm the game or the save (puzzle steps, building, stews, conversions, burial, a partner or object it needs) ends **(Unsafe)**: choosing it shows why and advises backing up the save first (Back Up Saves). What an action needs is found when the event happens the way the game finds it (the body awaiting burial, the object where the villager stands); with none there the villager is not changed. The full list, with each reason, is in `docs/custom-island-event-villager-actions.md`. A purchase queued before this version keeps its action. **Patch every game again** after updating: the Story Upgrades companion changed. Not yet seen in a running game (each action is started in an emulated stock game for an adult, a child and a Heathen, and its Details text checked).
- **Custom Island Event when everyone has died** (all five games, Story / Cheat Upgrades). None of the games ends a village whose last villager dies -- it keeps running and shows "Your tribe has been lost! Game over." on its status line -- but its island events wait for a living villager, so nothing could arrive, and the Custom Island Event refused a village with no living adult. Now a Custom Island Event can be bought for an empty village and arrives within seconds through the game's own island event (its sound, popup and Island Events Seen count): new villagers, food, Tech Points, refills, puzzles and revived skeletons bring the village back, and the game carries on as a normal village once someone lives. With everyone dead, Villager Changes says there is nobody to change (skeletons still awaiting burial can be chosen and revived), and a question with two choices is refused until someone lives. An empty village does not wait for a new village's two opening island events (it can never have them). In A New Home and The Lost Children a village that died before its first island event (always the game's own visitor) can be given one too: it is not counted, so the visitor is still that village's first island event once someone lives. In New Believers "everyone" means every believer, as the game counts (Heathens alone are an empty village to it). Works with 256 Villagers (Experimental). **Patch every game again** after updating: the Story Upgrades companion changed. Not yet seen in a running game (each game's own island-event trigger and New Believers' selector run in the emulator, in all three population modes and with 256 Villagers).

## What's new in v1.35.79

- **Villagers who share a name are numbered automatically, ON by default** (all five games). Two villagers with the same first and last name become "Chip Kenobi I", "Chip Kenobi II", ... (the oldest is I; the dead are numbered too; a name nobody else has gets no number).
  - In the game: a baby born with a living villager's full name is numbered at its birth, before its Birth record is written (needs Write Births and Conceptions Log; in A New Home, Show Parents in Details Screen; the new "VVFP Number Names.dll" ships with those rows). The villager who already had the name is not renamed while you play.
  - Repair Saves & Logs numbers whatever needs it, in the save and every log, each time it runs: backed up first, every rename listed in the Repairs Made log. Two look-alike namesakes, a record without looks, or a name too long for the game are never guessed: they are left and shown to you. Check Saves & Logs only reports it.
  - Per village: untick "Number villagers who share a name automatically" in Repair Saves & Logs to turn it off (the Number duplicate names buttons still work).
  - The Family Tree Maker shows duplicate names numbered by default; a tree you turned it off for (from this version on) keeps it off. Earlier versions saved "off" for every tree, so a tree last saved by an earlier version shows them numbered.
  - **Patch every game again** after updating: the parentage companions changed. Not yet seen in a running game (checked by the C harness and tests).
- **Start Over wipes the whole save** (all five games). Start Over wipes everything the Fun Patcher kept for that save: all its logs (the Village History too), all its data (ElderTotems.dat too) and its family tree files. It keeps Backups, Copies Made Before Repairs and exported family tree pictures. Other saves are not touched.
  - Deleted for save N: every file in the `Virtual Villagers Fun Patcher\Save N` folder (its empty folders stay, so the game can write the new tribe's files at once); the older places of the same files (`Virtual Villagers Fun Patcher Logs\Save N`, and every `... - Save N` file in `Virtual Villagers Fun Patcher Data`); in `Virtual Villagers Fun Patcher Family Trees` (and its `Reports`), that save's tree file (`.vvtree`, by the save it records), its Village Matchmaker text and its Genealogy report (`.txt`, `.html`). Deleting a tribe from the save-slot menu does the same.
  - Kept: every picture (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`) of any save, the game's own saves, and every other save's files. A file whose save cannot be told for sure, anything behind a link or junction, and a file in use are kept and listed in `Virtual Villagers Fun Patcher\Start Over Report - Save N.txt`.
  - **Patch every game again** after updating: the Save Reset companion changed. Not yet seen in a running game (checked by the C harnesses and tests).
- **Pick Gong of Wonder Outcome offers every outcome** (The Lost Children, Story / Cheat Upgrades). All 23 results of the Gong can now be picked at any time, including the 15 the game only gives after a village's first ring (they were listed as "not possible right now"). A new setting, **The villager who rang it**, chooses which living adult "Takes life", the loss of 90 health, "Grants wisdom", "Takes youth" and "Grants youth" act on (the youth results otherwise always change the villagers in slots 6 and 15, as the game does); if that villager has died, gone or changed by the ring, the game's own choice is used, and the same goes for a "Who falls sick" choice whose villagers are all gone. Buying it now makes the Gong ready to ring at once (it no longer waits out the Gong's day of rest); it is refused, with nothing spent, until the Gong is whole. Not yet seen in a running game (checked in emulation of the game's own Gong code).
- **Twins and triplets can be picked before the village has mastered them** (Story / Cheat Upgrades). The Lost Children's Gong "Grants life" and the poet's note (Pick Island Event), and The Tree of Life's Abandoned Infants, roll twins and triplets only once breeding / Parenting is mastered; picked, they now happen anyway, for that pick only (the village's own level is left as it was). A picked coconut outcome of the Gong follows the Gong of Wonder Coconuts Fix when that patch is ticked (+30 to the trees), as the game's own Gong does. Not yet seen in a running game (checked in emulation).
- **Last names: "Random last name from the list"** (all five games), a new choice in **Each villager's own rule**. Each child of that villager is given a last name drawn at random from the game's own list of 50 when it is born: every name equally likely, and twins and triplets each get their own draw. Which parent's own rule applies is decided as before (one parent's; both parents' when they agree; the village rule when they disagree or neither has one). Repair Saves & Logs keeps a list name such a child already carries, and gives one with none a random one. An older patcher or Last Names DLL ignores this choice and uses the village rule.
- **Random last names are now really random** (all five games). The in-game **50:50** rule used the clock's tick, so twins and triplets of one delivery nearly always got the same parent's last name. Each child now gets its own fair draw. The automatic last name for an arriving villager now picks evenly among the free names. Before, a name right after a run of taken names was picked far more often. **Patch every game again** after updating: the Last Names companion changed. Not yet seen in a running game (checked by the C harness, the emulator and tests).

## What's new in v1.35.74

- **Scroll bars in the patcher's windows.** A window whose content is taller than the window (for example the Repair Saves & Logs window, whose list ran off the bottom with no way to reach the buttons below it) now has a vertical scroll bar, and the mouse wheel scrolls it. Windows that already scrolled in their own text or canvas are unchanged. Not yet seen in a running window.

## What's new in v1.35.73

New in v1.35.73 (not yet seen in a running game):

- **The patch list draws only what is on screen** (Patches tab, every game). Each game's list builds the patches near its visible part and draws the rest as you scroll, so the window opens with far fewer widgets. Each game's list is a fixed-height area with its own scrollbar: the mouse wheel scrolls it while the pointer is over it, and scrolls the page once the list is at its end. Ticks, the "?" guides, the bold requirement lines, Select All and the saved selection all work as before. Not yet tried in a running game.

- **Family Tree Maker: the "continued on page N" labels no longer pile on top of one another.** On a page where many families have their children on the next page, the labels (and their long lines) could be drawn on top of each other along the bottom edge. They are now laid out like portraits, each sized to its words and given a place of its own, standing in rows and running out to one side of its line where they must; none touches another label or a portrait, every line still ends at its label, and the words, clicking, dragging and saved positions are unchanged.
- **Villager Info tab: the "shares this name and looks" note no longer leaks between a villager's looks.** A villager who changed looks with Change Appearance could be labelled as sharing their look because of an old look that was shared, and a shared villager could recover a title from an old look. The shared note now belongs to the villager's current look only, and a villager who shares their current look takes no title from an old one.
- **An island event that changes both a villager's likes and their head before the next frame keeps the custom title** (all five games). The head is stored under the new likes at once, in the Custom Titles file too, so a log written in that frame reads the new head.
- **A Custom Island Event that changes skills before the title list has been checked against the village after a load** now makes the check first, as the lookup does, so the title is on its villager before the change is carried (all five games). Limit: only when the change is the first thing the title list sees after a load, before the list has been checked against the village. Then the villager is below the stored skills, so the title waits unshown (pending) for the reconciliation to ask about, the lowering is not stored, and the title is never given to someone else. In the normal path the event checks the village first, so the lowered value is stored and the title follows its villager. A change after the list has been checked is carried as before.
- **Repair Saves & Logs can remove a restarted tribe's villagers from the history** (all five games). Started a game over with the same tribe name? The new checklist row "Remove villagers from the history that are not in this save (a restarted tribe with the same name)" is never ticked by default. It removes only the villagers proven gone (no villager in the save, no older copy of the save, no Name changed, Appearance changed or Island Events record and no shared name ties them to the tribe you play, and only snapshots older than your tribe's own list them), after you confirm the exact list, log by log. Everyone else not in the save, renamed villagers included, is kept and listed with the reason. Each log is copied to Copies Made Before Repairs first, the save is never changed, and every villager removed is listed in the Repairs log. The Family Tree Maker's new "Hide villagers not in the current save" (on by default) leaves those villagers out of the tree.
- **Patch selection settings and search** (Patches tab, all five games). A new **Patch Selection Settings...** button opens a window that lists every patch name once, with the games it appears in; **Tick These** and **Untick These** set that patch in every game that has it, using the same dependency and companion rules as a manual click. Each game's tab has a **Search patch names** box that matches names only (case-insensitive) and changes only which rows are shown, never a tick.
- **Anything uncertain is your decision, not the program's** (all five games). A possible match in the save that is not proof (the same sex, head and body; a shared name; a link; the same sex and one of head or body) is listed under "Not sure" in the same confirmation. It is kept unless you tick it to be removed.
- **Undelete villagers** (Repair Saves & Logs, all five games). A new checklist row, never ticked by default, puts back what the latest history revision removed. It restores each log from the copy the revision made, after you confirm the list. Lines written since are kept; if a log was edited in place since, nothing is changed. Each log is copied first, and the Repairs log records what came back.
- **A renamed founder is still a founder** (Family Tree Maker, all five games). A kept rename (for example Lupa Tangaroa to Coral Tangaroa) takes the Founder status of the older record, so the arrival rule no longer places the renamed villager outside Generation I.
- **Known gap (unchanged):** Change Appearance for All still publishes the Custom Titles file once for each titled villager it changes, not once for the whole change. Batching it would change the Change Appearance loops in the Origins DLLs and add a new export to the Story / Cheat Upgrades companion, which can not be checked without live games, so it is left for later.

- **Villagers the F7 developer command spawns in The Tree of Life are now named as that command (fixed).** Before, their Arrived records said "How: unknown", because the patcher did not list F7's path. They now say "How: Developer command (F7)". The patcher checked every direct call of a villager creator in all five stock executables: F7 was the only path without a listed label, and it is the game's own debug key (F1-F10 are commands 1018-1027, so F7 is 1024). Where the patcher cannot tell which path made a villager, the record now says "How: added outside a recorded event" instead of "unknown" (all five games). A villager the backfill finds with no record at all still says "unknown", with the note that they arrived before the log existed. Not yet seen in a running game.


## What's new in v1.35.72

New in v1.35.72:

- **The bottom of the patcher window was blank in v1.35.70 and v1.35.71 (fixed).** The patch list had grown so long that the window's page passed 32,767 pixels, which I believe is the largest size Windows can paint (the measurements match: 31,412 pixels at v1.35.68, 31,622 at v1.35.69, 33,237 at v1.35.71; not confirmed pixel for pixel), so the folder choosers and the Validate, Dry Run and Create buttons below it were blank. The patch list is now one tab per game (A New Home, The Lost Children, The Secret City, The Tree of Life, New Believers); every patch, "?" button, Select All Patches, Default Patches, Owner's Defaults, Deselect All Patches and dependency rule works as before, and the main page is about 9,100 pixels, under a third of its former height. A new test fails if the page ever grows past 24,000 pixels. Not yet seen in a running game.
- **A custom title now follows a Custom Island Event that lowers its villager's skills** (all five games). Before, the title kept the higher skills it was stored with, so after the next reload nobody "could be" the villager and the title went waiting. When an event changes a skill, what a title is kept by follows it down (never up, so an Alt-F4 or crash back to an older save still matches), also for a title given to that villager later or in the same event. (The event's dialog has no age control; the age is followed the same way as a precaution.) A change the patcher did not make itself is not followed, and is not guessed at: a skill lowered by a Cheat Engine edit leaves the title on nobody after the next reload (Check Saves & Logs asks who could be them), and an age lowered in the same session is taken for a younger namesake in the same record, so the title is deleted.
- **A log written the moment you Change Appearance now keeps the custom title** (all five games). The log compared the villager's new head and body with the old ones still stored in the Custom Titles file until the next frame, and left the title out. Change Appearance, and an island event that changes a head or body, now store the new head and body before they log, when Story / Cheat Upgrades is installed. Known gap: Change Appearance for All publishes the Custom Titles file once for each titled villager it changes, not once for the whole change. Two smaller known gaps: an island event that changes both a villager's likes and head before the next frame, and a Custom Island Event that changes skills before the title list has been checked against the village after a load, are left for the next frame to settle.
- **A Disappeared record no longer prints a custom title that could belong to two villagers** (all five games). When the Custom Titles file is an older version 2 file that keeps no looks, the villager being written counts as a possible owner of the title as well as a present villager with the same name, likes and dislikes, so the title is left off.
- **Villager Info tab** (Family Tree Maker). Villagers who share a name, head and body can no longer be shown one another's titles. The count comes from the save, with or without a Custom Titles file. The Notes say "2 villagers share this name and looks, so a title can not be told apart here", and show no Special title for them and no Custom title unless the Custom Titles file gives every one of them the same one.
- **Last Names: two villagers who share a title identity can now be given different last names** when the Custom Titles file's entry for that identity keeps looks that fit exactly one of them (as the game's own load tells them apart). The entry follows that villager. An entry that keeps no looks, is waiting and contested, or fits both is still refused rather than guessed.
- **Fixed:** the two custom-title test harnesses (the log harness and the titles harness) no longer overflow their path buffers or fail every check when %TEMP% is a long path (test-only).


## What's new in v1.35.71

New in v1.35.71:

- **A waiting custom title can be settled by your answer** (all five games). Check Saves & Logs' question about a custom title that is waiting ("pending") now offers, besides "Keep as is (leave it waiting)": "Give it to <villager>" for each living villager who could be them (the same name, likes, dislikes, head, body and sex, no younger and no less skilled, and holding no other title), and "Remove the title (it is nobody's now)". Repair Saves & Logs carries the answer out in the Custom Titles file with the game closed: a backup first, the file as it was kept in Copies Made Before Repairs, the new file written through a temporary file and read back, and a "Repair" record in the Repairs Made log. The answer is checked again against the file and the save as they are then; if either changed, nothing is changed and the question is asked again. Before, only giving the title again with the Custom Island Event ended the wait.
- **Two villagers with one name, likes and dislikes who were each given the same custom title** (all five games):
  - **A lost entry is now reported.** Check Saves & Logs counts each title's entries. Before, if one of the two entries was lost, the other entry hid the loss.
  - **Each waiting entry can be answered on its own.** When both entries are waiting, each one gets its own question and your answer changes only that entry. Before, Repair Saves & Logs could settle neither.
  - **Unchanged rules:** your answer is checked again against the file and the save as they are when Repair runs. If either changed, nothing is changed and you are asked again. Nothing is ever given to a villager you did not name.
- **The Villager Info tab and Restore Lost Titles now treat each such villager on their own** (all five games). This applies to villagers who share a name, likes and dislikes but not their looks.
  - **Villager Info shows each one their own custom title,** as the game does. Before, it showed neither.
  - **Restore Lost Titles no longer mistakes one's title for the other's.** Before, that mistake skipped one villager's lost title, or refused to restore it.
- **The logs now show each such villager's own custom title** (all five games). This covers the Village Population and Village History pages, and the Death, Disappeared, Unaccounted and Name changed records. Before, an identity two villagers shared printed no title for either of them, though the game showed each one's.
  - **The same rule as the game:** the title belongs to the villager in its own record whose looks it could be.
  - **Still shown on nobody:** identical twins the game can't tell apart, and an older file's entry with two possible owners.
  - **Patch every game again** after updating: the Population Export and Parentage Export companions changed.
- **Repair Saves & Logs no longer copies one villager's title, mask or faction into another's older records** (all five games). This applies to two villagers on the latest Village Population page who share a name, head and body but have different titles, masks or factions. Their older records are left as they are, with a note saying why.
- **Check Saves & Logs asks in more cases where something may be lost** (all five games): a Death record of a villager of the other sex no longer explains a missing villager of the same name and looks; the Village Population page is now compared too; a villager missing from a save restored from an older copy is asked about even when a later Death record names them; two villagers who share a name and likes can each keep their own custom title without one being reported lost.
- **Start Over always forgets the old village's custom titles** (all five games), even when the new founders appear before the game notices the deleted file.
- **A backup whose file times cannot be kept now fails safely** instead of passing with the copy's time (an old save could then look newer than a queued purchase it never paid for).
- **Faster with 256 villagers:** The Secret City with every villager masked costs about 0.43 ms a frame instead of 1.4 ms (same masks shown); a Time Skip no longer looks up the Island Events companion every frame.


Also in the v1.35.70 download (its notes did not list these three, so they are listed here):

- **Fix Vanilla Bugs: the Villager Details name box is saved only to the villager it was filled for** (all five games). Each game's Details screen fills a name box with the selected villager's name and, on Done or an arrow, copies the box back into whichever record is selected at that moment. If the selected record no longer held that villager (two clicks in one frame, or records shifting while the box is open), the name went into the wrong villager. The screen now remembers whom it filled the box for and writes back only to that same villager.
- **Lower frame cost at 256 villagers** (all five games, behaviour unchanged): the Cause of Death companion's per-villager pass in The Secret City and New Believers now runs once per draw pass (about 1.35 ms and 4.4 ms a frame before, about 17 and 29 microseconds after); The Secret City's mask lookup no longer fingerprints every record for every villager drawn when none is masked (1.09 ms to 18 microseconds a frame); The Lost Children's route descent no longer translates the whole field on every waypoint; and each Births, Conceptions and Deaths record no longer re-reads every log file in every folder (a record in the sixth 256-record file read 2.3 MB, now 0.21 MB).
- **Check Saves & Logs:** every question about a save older than the logs now names a quit without saving (Alt-F4: the game saves only on a clean quit) or a restored backup as the likely cause, and offers "Keep as is" first; nothing is called corruption.

**Not yet seen in a running game:** a waiting custom title settled by your answer (and the Repair that carries it out), the other Check Saves & Logs changes, the Start Over change, the backup change, the Details name-box guard and every frame-cost change are checked by tests, C harnesses and emulation (the full suite passes) but none has been watched in a running game yet.

## What's new in v1.35.70

New in v1.35.70:

- **Keep the Game's Own Log (ldwLog.txt)** (all five games, on by default, in Select All). Every Virtual Villagers game has always had a log of its own, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\); nothing in any game ever switched it off, but the base game starts the file afresh the first time it writes in each run, keeps what it writes in memory until the game closes, and writes only when something goes wrong, so most players never had one. Now the file is kept across runs, each line is written at once, each run starts with a "---- Game started ----" line, and every line the game's own code writes is kept: missing pictures and sounds (all five), the clock check (The Lost Children to New Believers), tutorial tips (The Lost Children), text-file problems and healers with nobody to heal (The Secret City to New Believers), and stuck villagers, villagers with no way through and trips to the love shack door (New Believers). Lines a game's code does not contain are never added. Repeats are written once a minute with a count, at most 1,000 lines a minute, and at 4 MB the file becomes 'ldwLog 1.txt' (then 2, 3, ...) and a new one starts; nothing is deleted. No executable byte changes: "VVFP Startup.dll" starts "VVFP Game Log.dll", which checks the game's own writer before replacing it.
- **New Believers: the gold dust pouring sound plays** (Fix Vanilla Bugs). The game asked for "gold_dust_pour .ogg", with a stray space, so the sound file it ships was never found (its log said "ldwSoundFx Missing File ->gold_dust_pour .ogg"). No other game has this sound, and no other sound, picture or text name in the five games has the same kind of typo.
- **New Believers no longer logs "String Table (sm.xml) malformed near id=\"eDemo\"" each time it opens** (Fix Vanilla Bugs): it looked up the demo version's population message under an old name; its text file calls it "eTipDemo". The message is for the demo version only and never shows in the full game.
- **Check Saves & Logs now reconciles everything, read-only, in all five games, and asks you about every contradiction.** It follows each villager through the save and the game's own two older copies of it, every Village History snapshot, the Village Population page and every log record (Birth, Arrived, Appearance changed, Name changed, Death, Disappeared, Left the tribe, Unaccounted, Island Events, Repairs) and the patcher's files, by who they are (name, looks, sex, likes, dislikes, parents, age), never by record number. Anything that does not add up is a numbered question naming the villagers, records and files, with the choices to keep things as they are, to say which record is right, or "don't know": a name changed with no record of a rename (for example a Birth record and the save naming one villager differently), looks, sex, likes, dislikes or parents changed with no record, an age going backwards, villagers gone from one roster to the next with no record of how (several at once are one question), and files that look damaged or replaced by an older copy. What the game or the patcher explains -- a last name or numeral given, a rename an island event recorded, record slots reused after deaths and births at the population cap -- is a note, not a question. It never changes anything; its report is kept in `Logs\Save <n>\Reconciliation`.
- **Deaths during the load-time catch-up, Time Warp or Time Skip keep their real cause** (all five games): a body buried after the village was loaded again no longer reads "(not recorded)".
- **Equal Division of Labor follows skill progress** (all five games): each villager gets the job whose skill they have made the most progress in, then the next best when that job is full; random placement only fills the seats that remain, so the counts per job stay equal. New Tech-menu rows **Clear All Skill Preferences** (half the Equal Division price) and **Check Highest Skill** (with and without Parenting).
- **Corrupted skill values are reset** (all five games): a skill the game itself could never produce (below 0, above 100, or not a number) is set to 0 or 100 by the upgrades that read skills (only once the purchase is confirmed and the tech points are there: a purchase refused with "Not enough tech points." changes nothing), and by a new Repair Saves & Logs item, **Reset corrupted skill values** (backup first, every change listed in Repairs Made). Valid values are never touched.
- **Last names:** in the last-names windows, a villager whose own rule for their children's last name the pending choices would change now reads in red bold too.
- **Patch every game again** after updating: the Startup and Origins companions changed (the new log companion was added to their list).

**Not yet seen in a running game:** the game log and the two New Believers fixes are checked by tests, a C harness running the log writer, and an emulated game start in all five games and all three modes; none has been watched in a running game yet. The reconciliation, the catch-up death causes, Equal Division by skill, the two new skill-preference rows, the corrupted-skill reset and the red-bold rule rows are checked by tests, harnesses and runs on copies of the owner's saves; none has been watched in a running game yet.

Also in v1.35.70 -- Fixes from an audit of v1.35.67 to v1.35.69:

- **Backups and restores keep each file's time.** Restoring an old save beside a Barrel of Babies or Story / Cheat Upgrades purchase still waiting to be delivered could deliver it with no charge in the restored save; the copies now keep their original times, so the purchase is believed only when the save really holds its charge.
- **A queued Story / Cheat Upgrades purchase is never written over another village's file** (after a quit to the menu, the title screen's founders are not taken for the village).
- **A New Home: a departed villager who comes back into her own record keeps her parents.**
- **Restore A New Home Parents** uses only the copies of the parents file that describe the same village, so another village's copy can no longer give its parents to namesakes.
- **Restore Lost Titles** numbers its Repairs Made record per game in the slot's own folder, like every other repair (no second "Repair 1").
- **Number Duplicate Names** no longer renames a parent who is a different villager with the same name, and the lost-titles list keeps a word that ends exactly at the companion's 512-character limit.
- **A custom title is never dropped because its villager can't be told apart after a load** (all five games). When a titled villager and a look-alike namesake (the same name, likes, dislikes, head, body and sex) could both be the one after a reload, the title used to be thrown away for good. It is now kept, waiting ("pending"), and shown on nobody; the game gives it back by itself as soon as exactly one villager has its whole identity -- name, likes, dislikes, head, body, sex, and an age and skills no lower than when it was last seen on them -- and never moves it to a different villager. If two or more villagers could be them at once, the game never guesses: even when only one of them is left later (the others died or left), the title keeps waiting, and Check Saves & Logs names the one left so you can decide. A reload is never taken for a death: a villager renamed and then reloaded without a save, or whose record now holds someone else, leaves the title waiting too. A corrupted skill put right (NaN, infinite, below 0 or above 100) never makes a villager look like someone else. Check Saves & Logs names every waiting title, who it is kept for and who could be them. A newborn in a dead villager's freed record (the 256 cap) and a younger or less-skilled namesake are never given it. The Custom Titles file is now version 3 (it keeps that identity); older files are still read and written back in the new form.
- **Patch every game again** after updating: the Story Upgrades and VV1 Parentage companions changed.

**Not yet seen in a running game:** these fixes are covered by tests and harnesses (including a new VV1 parentage harness case for the returning villager); none has been watched in a running game yet.


## What was new in v1.35.69

- Download replaced on 2026-10-11: wording corrected (no Skip button: the hidden F1 key); no behaviour changed.
- **A New Home: a village started by pressing F1 on the Start / "?" screen of a new village now writes its logs at once.** (F1 there is a hidden key, apparently a leftover developer shortcut; the game has no Skip button.) Before, its Births and Conceptions, Population, History and Statistics logs appeared only at the first quit (the game never sets that village's start time on that path, so its autosave skipped it). The patcher now makes the same save the quit makes, once, as soon as the village is on screen with its founders waiting.
- **A two-choice Custom Island Event question on screen when you quit is kept** (all five games): after the next load it is asked again, answered once, and the tech points are charged once.
- **One place for the "Retroactively edit records? No" answers.** The contradictions you chose to leave alone now share the Log Decisions file with the other answers; the older "Contradictions Left" file is still read, and never written again.
- **Move Old Files** also leaves a short note in the Repairs Made log of every save slot whose files it moved.
- **Reproducible companions.** Every companion DLL is now built so that the same source always gives the same bytes (so the DLLs the patcher ships match the hashes its manifests pin); no behaviour changes.
- **Known limit (documented):** a crash between buying a Story / Cheat Upgrades item and the next save loses both the item and its charge together -- consistent, never a charge without the item.
- **Custom Island Event: several changes to one villager now combine.** Several "Villager changes" entries for the same villager in one event all apply. Likes and dislikes are applied in the order you added them (several "Add a like" entries each add one); for every other field the later entry wins. Adding a second entry for a villager shows a warning saying so, and Edit works on a combined entry.
- **NOTE when updating from v1.35.68:** a Custom Island Event or Pick Island Event that you bought but that has not been delivered yet is **discarded** when you update to v1.35.69 (the saved queue layout changed; the tech points stay spent). **Deliver pending purchases before updating.**
- **Patch every game again** after updating: the Cause of Death, Story Upgrades and Origins companions changed.

**Not yet seen in a running game:** the creation save for a village started with the hidden F1 key on the Start / "?" screen (checked by emulation and the harness only; it is item B1 of docs/LIVE-CHECKLIST.md -- it calls the game's own save routine, so watch for a freeze in the first seconds); the two-choice question coming back after a quit in each game; several changes to one villager in one Custom Island Event; Move Old Files' per-slot notes; and everything still on the list under v1.35.66, which is carried in docs/LIVE-CHECKLIST.md.


## What was new in v1.35.68

> **Warning -- A New Home players on v1.35.66 or v1.35.67:** those versions can **wipe A New Home's parents on launch** (the parents file was emptied while the game's villager list was still empty at load). Do not play A New Home with them. **To recover:**
> 1. Patch with v1.35.68 **before** playing again.
> 2. Close the game.
> 3. In the patcher, open **Repair Saves & Logs** and choose **Restore A New Home Parents...** -- it puts back, from the copies the patcher kept of the parents file, the parents of every villager the file lost (it only ever adds; it never changes a parent that is there).
> 4. For the newest children (in the owner's village, the 19 born since), run **Repair Saves & Logs** or accept the quit check's offer: their parents are filled in from the Births log.

- **A New Home's parents are never wiped again.** The real cause, found live: for about five seconds after launch the game's villager list is empty while its slot is already set, and the patcher took that for the village. Nothing is loaded, replaced or written for a village until its own villagers are on screen, and the same rule now guards every per-slot file in all five games (masks, custom titles, the Barrel and Story purchases): another village's file is never written over.
- **Logs per save slot.** Each save slot now has its own log folders ("Logs\Save <n>\..."); everything older builds wrote to the shared folders is still read, as one history, and record numbers continue per game.
- **Custom titles and Former Heathens follow a change of likes or dislikes** (island events, the Custom Island Event, vials and the Running upgrades change them), in all five games, and Repair Saves & Logs can give back titles older builds lost that way. A death the Custom Island Event causes is recorded as "Died in a custom island event".
- **Log parity:** A New Home's Unaccounted and Arrived records name the villager's parents, as the other games' do; Deaths and Repairs numbers continue after an older build's folders, so no number is used twice.
- **Full likes and dislikes everywhere.** The Village Population and Village History logs and every Birth, Arrived, Death, Disappeared, Unaccounted, Appearance changed and Island Events record now list a villager's whole likes and dislikes, not only the first one the Details screen shows, in all five games.
- **Family Tree Maker:** generation label boxes hold every line at any font size; "1 male" / "1 female"; page names are no longer cut short.
- **Fix Vanilla Bugs: the Details screen's Likes and Dislikes line** (download replaced on 2026-10-10, same version). In A New Home and The Lost Children the game's own line ran past the last word of its list ("sleeping" / "dirt"), so later likes vanished or garbage appeared, and The Lost Children could overflow its buffer; the line now shows every like and dislike, skips a slot outside the list, and ends in "..." when it does not fit. Every line the base game already showed correctly looks exactly the same. In all five games a negative slot is left out instead of showing "ants".
- **Patch every game again** after updating: the logging and Origins companions changed.


## What was new in v1.35.67

- **Story / Cheat Upgrades purchases survive a quit (all five games).** A Pick Island Event, Custom Island Event (with its question), The Lost Children's Pick Gong of Wonder Outcome, or the years still to go of a Choose Time Skip Amount, bought and not delivered yet, is now kept in the save folder's Paid Purchases folder and delivered once the village is played again -- the island event the save made due brings it, never a random one instead, and nothing is charged twice. **Limits:** a crash (or anything that keeps the game from saving) loses whatever was bought since the last save, as it loses the rest of that play; and a two-choice question already on screen when you quit is not kept. **Patch every game again** after updating: the Story / Cheat Upgrades, Origins and Save Reset companions changed.


## What was new in v1.35.66

- **Births are numbered** ("Birth <n>"), as Conceptions are, in all five games, and a Birth number is never used twice. Repair Saves & Logs can number the Birth records an older patcher wrote as just "Birth".
- **Babies lost before birth.** When a mother dies or disappears while nursing, her Death or Disappeared record says "Nursing: yes, N babies (never born: lost with their mother)", and the Births and Conceptions log closes her Conception with a **Lost before birth** record (mother, expected father, babies). The babies get no Death record or grave. Repair Saves & Logs adds these records for older cases, and the Family Tree Maker notes them.
- **"Nursing", each game's own word,** replaces "Pregnant" and "Babies in pregnancy" in the logs ("Nursing: yes", "Babies nursing: 2"). Older logs that use the old words are still read.
- **Island Events log:** every game logs a conception's expected father (name, head and body) and babies. The later games log a two-choice answer as "Choice:". Likes and dislikes are shown as whole lists, and a line whose old and new values read the same is never written. The log also records a newcomer's sex and age, a custom title, the Custom Island Event's other changes, the village's changes and the weather, in the games' own words.
- **A New Home: the expected father** of an unborn baby appears in the Village Population log, the Family Tree Maker and the Village Matchmaker. The Custom Island Event can change him, and the first-load cross-check writes Birth records afterwards from the parents file for villagers that have none.
- **New Believers:** Village History and Village Population records carry a **Faction** line (Believer or Heathen), and Repair Saves & Logs adds it to older records. A believer who becomes a Heathen leaves the tribe with a Disappeared record, written the moment it happens, including while the game catches up on time away or a Time Warp. Repair Saves & Logs adds the record for Heathens who left before this (marked "Recorded afterwards", age unknown), and asks where the logs cannot settle it.
- **Cause of Death:** The Tree of Life's Custom Island Event "Disappears" writes its Disappeared record, a new village's founders get their Arrived records, and a villager buried at age 0 has a grave. Head 0, body 0 and age 0 are real values everywhere.
- **Village Statistics:** a reload that moves villagers to other records is still the same village, and only stews the game proves are counted. Food Gathered, Debris Cleared and Heathens Converted count what they say.
- **Records that contradict each other** (one villager recorded twice, a backfilled "How: unknown" Arrived record beside a Birth or a real Arrived record, a Death or Repair number used twice) are reported by Check Saves & Logs and asked about by Repair Saves & Logs, each with **"Retroactively edit records?"**: Yes corrects the old records (a copy kept first); No leaves the log exactly as it is and remembers the answer, so it is not asked again.
- **Missing last names:** with "Check logs automatically" on, the game's quit check names living villagers with no last name in a village that uses last names, and the patcher offers to give them the suggested names, to choose each one, or not now. Arrived villagers can be given a unique last name automatically (a toggle, on by default).
- **Choose Time Skip Amount (all five games, Story / Cheat Upgrades).** A new Tech-menu upgrade at the Time Warp's price (0 tech points, or 50,000 with *Story / Cheat Upgrades cost Tech Points*; the button shows the same price it charges): type 1 to 72 years and the village moves forward that many villager years as a run of the Time Warp's own advance, one Time Warp at a time, so villagers work, eat, have babies, grow up and die of old age as after a Time Warp. Keep the game running until it is done; Cancel charges nothing. When the last year has been played through, the game's own island-event popup says "Time Skip: N years have passed on the island." (not shown if the skip was cut short by loading another village, Start Over, a deleted tribe or no one left; it is not counted in Island Events Seen and writes nothing to any log).
- **Family Tree Maker:** vivid **Auto line colours** and **Rainbow**, **Gradient** and **Range** line modes with colour ordering, and a **Runner** line for villagers who like running. **Village Matchmaker:** a generation number by every name, **Prioritize latest generation**, and **List pairings by** generation, age or family tree number. **Repair Saves & Logs:** a **Random last names** option; rows whose last name, or whose own rule for their children's last names, will change are shown in red bold.
- **Last names: each villager's own rule** for their children's last name (From the father, From the mother or 50:50), beside the village's rule.
- **A New Home and The Lost Children: Dropping an Adult on a Child Tells a Story (new patch).** The adult always tells that child a story, as in the later games, instead of starting an embrace.
- **Family Tree Maker:** packed portraits never overlap and every portrait sits wholly on the page; a settable **canvas size**; faces and words can keep **one size** whatever the portrait ("Same face and text size"), and every face sits inside its own shape; **Auto-colour family lines**; lines keep 1 px between their edges; opacity sliders fade only their own parts, and resets keep what they should; extra portrait lines bold and italic by default; a new **Villager Info** tab (the selected villager's face, age, partners, children and notes); and edits, undo and zoom redraw only what changed, so they are much faster.
- **Doctors keep learning while you are away.** A New Home gets **Easier Healing Mastery** (new patch, as The Lost Children has): a healer with no one to treat studies the Medical Cactus, in play and during catch-up and Time Warp, so doctors no longer stay at Trainee or Adept. **Healers Study Plants Regardless of Food** now also keeps a villager dropped on the cactus studying during A New Home's catch-up, as it already did in The Lost Children. The Builders and Healers Work First and Healers Study descriptions now say when a healer studies in each game.
- **The games' own default fathers.** The Lost Children's Gong of Wonder "?" and The Tree of Life's and New Believers' island-event "Joey" are never matched to a living villager of that name: the logs say "(none: game's default father)" for his age, sex, likes and dislikes, and the Family Tree Maker and Matchmaker never treat him as anyone's kin (children of the Gong by different mothers are not half siblings). In A New Home, a birth whose conception was not captured gets the father "Unknown" (head 0, body 0) while Write Births and Conceptions Log is on.
- **Every disappearance is logged.** In New Believers, a believer who turns Heathen while the game catches up or during a Time Warp now gets her "Left the tribe: became a Heathen" record too, and Repair Saves & Logs can add the ones older builds never wrote (asking when the logs cannot settle it).
- **Family Tree Maker: families continued on the next page.** A parent whose children are on the next page no longer looks childless: the family's lines run down to "continued on page N", words you can restyle, retype, move or delete like any others. New Monstera and feather portraits are drawn straight.
- **Repair Saves & Logs: Fix grave information** (all five games, never pre-ticked): each grave as the game keeps it -- name, age at death, job line, epitaph, cause, looks, sex, titles, Custom title and mask, including what patches added -- is compared with its Death record and the patcher's files; every difference is listed in plain words for you to answer (or edit a grave directly), values the game could not keep are refused, and "Retroactively edit records?" decides whether the Death records change too. The game must be closed; the save folder is backed up first.
- **Custom Island Event: Health, parents and Edit** (all five games). A villager change can set **Health** 0-100 (with a warning that 0 kills: it is the game's own death); a new villager can be given Health and **Parents...** -- a villager of the village (living, or a body awaiting burial), **Unknown**, **Joey** (The Tree of Life and New Believers, as the games name their default father) or **Custom** (any name, head and body) -- and villager changes can change parents the same way. Every list gets **Edit...** (or double-click). The Births log's Arrived record and the Island Events log record the parents and Health.
- **Fixes from the live tests:** unburied bodies are no longer listed as living villagers in the Population and History logs (all five games); a village made during a session keeps its own save slot, so its causes of death and Graves file are kept (The Lost Children's save-all no longer confuses the slot); Choose Time Skip waits while an island event's popup is open, so the event is not logged with years of ageing (The Secret City, The Tree of Life, New Believers); and a mother who has delivered no longer shows a phantom "Upcoming child" in the Family Tree Maker or counts as expecting in the Matchmaker (The Lost Children to New Believers).
- **A bought Barrel of Babies survives a quit.** A Barrel of Babies bought from the Origins Tech menu that has not arrived yet when you quit is kept in the save folder's Paid Purchases file and arrives after the next load, in A New Home, The Lost Children, The Secret City and The Tree of Life (New Believers already kept it).
- **Patch every game again** after updating: the logging companions changed.

**Known issue (fixed in v1.35.67):** a Pick Island Event, Custom Island Event or Gong of Wonder outcome that was still waiting to happen, or the remaining years of a Choose Time Skip Amount, was lost at a quit with its tech points spent.

**Not yet seen in a running game** (checked by the test suite's emulation and harnesses, and on copies of the owner's saves and logs, but not yet played live): the numbered Birth records; the Lost before birth records and Nursing lines; the "Nursing" wording; the Island Events log's new lines; A New Home's expected father in the logs, Family Tree Maker and Matchmaker, and its Custom Island Event change; the first-load cross-check's Birth records written afterwards and the removal of backfilled Arrived records of villagers born here; New Believers' Faction line and "Left the tribe: became a Heathen"; The Tree of Life's "Disappears" record and the founders' Arrived records; the Village Statistics changes; each villager's own last-name rule; Choose Time Skip Amount in all five games; the contradiction questions; the missing last names question at the quit; Dropping an Adult on a Child Tells a Story in A New Home and The Lost Children; A New Home's Easier Healing Mastery and its Healers Study catch-up; the default fathers and A New Home's "Unknown" father; the catch-up "Left the tribe" record and its Repair backfill; the Time Skip popup; Fix grave information; and the Custom Island Event's Health, parents and Edit (seen live only in A New Home and The Tree of Life). The Family Tree Maker's "continued on page N" lines have been checked by tests, not yet on the owner's own trees.


## What was new in v1.35.65

- **Family Tree Maker: packed layouts.** Two new Positions, **Packed families** and **Packed generations**, fit the tree into far less room, with a **How tightly packed** slider (0-100): at 100 the portraits touch, rows nestle brick-wise where that saves space, and the tree's width is chosen to use the page well.
- **Most portraits in a row** caps how many portraits sit side by side (with **Keep families together**), so a wide generation wraps onto more rows.
- **Lines run behind portraits** (Layout tab): ticked, family lines run straight and are drawn behind the portraits in every layout; unticked, they go round them. Left alone, they run behind only in a packed layout at 98 or more, as before.
- **Other Members** (villagers with no family in the tree) sit in a grid of 1-6 columns, on the left or the right.
- **5 new portrait shapes: Feather, Coral, Sea fan, Brain coral and Beetle** (54 in all).
- **Repair Saves & Logs: Restore A New Home Parents...** gives back the parents v1.35.66 and v1.35.67 could lose from A New Home's parents file (the title screen's founders were taken for the village; fixed in this version), from the copies the patcher kept of that file. Only villagers with no parents now get any, an arrival never does, and a copy the Births log contradicts is not used; the save folder is backed up first and every villager is listed in the Repairs Made log. Patch the game with this version first.
- **Repair Saves & Logs: Move Old Files to New Names...** moves a save folder's files from the names an older patcher used to the new ones, when you ask and only once every game playing that save is patched with v1.35.64 or newer; old and new names are otherwise read alike everywhere (an A New Home parents file older still now goes into Parentage Records, which every version reads).
- **Deaths log numbers:** when a save has both the older Deaths folder and Deaths and Disappearances, a new death's number follows the highest in either, so two deaths never share a number. **Patch every game again** after updating: the shared logs patch and A New Home's parents patch changed.


## What was new in v1.35.64

- **Family Tree Maker: 49 portrait shapes** -- among them pentagon, trapezoid, arch, a horizontal oval, 4- and 6-pointed stars, arrows, scallop, snail and conch shells, hibiscus, sand dollar, starfish, a Monstera leaf, turtle shells, mermaid tails, fish, an ocean wave in a circle, a ship's wheel, a coconut, an anchor, a bunch of bananas and a **paw print** -- with light **detail lines** inside them (their colour, opacity and weight yours).
- **Special borders** that follow any shape: a **braided rope**, or a **vine** with leaves, hibiscus or both, drawn filled and shaded. Their colours: natural (with **natural hibiscus** in red, pink, yellow, orange, white or purple, by turns or as a gradient), **rainbow** (Bright, Medium or Deep), your own colour for each part, or 2-7 colours by turns or as a gradient -- and an **opacity** of their own.
- **Each portrait** can have its own inside and detail colours, be **flipped** or **turned** to an exact angle (its words turning or mirroring with it if you like), and have its words left, centred or right and at the top, middle or bottom. **Founder**, **"X's twin"** and **spacing** between generations are new options; **Keep aspect ratio** works on every width and height box; every portrait of a group can be **flipped or turned at once**; the options sit on their own tabs (**Shapes**, **Faces & Text**, **Layout**, **Marks**...); and **rainbow or alternating colours** (2-7) work on plain borders, portrait insides, detail lines, family lines and special marks. **Settings for:** (Faces & Text, and the Shapes tab's inside colour and detail lines) gives Males, Females or Babies on the way their own text alignment, text area, face and text size, characters per line, ages, twins, Founder, mirrored and turned words, detail lines and inside colour; **Same as everyone** and **Make every group the same** put them back.
- **The tree's options, tidied:** each tab is in clear sections with short names; every list opens wide enough to read; a **picture size** and **text size** inside the portraits, for every portrait or one villager; **rows** to the left, centre or right, and portraits of different sizes **lined up** by their tops, middles or bottoms; a group's size now resizes everyone in it; moving everyone at once no longer waits for the background picture.
- **Island Events** say which vial, crate or sack it was ("Item: an oily red vial").
- **Tidier save folders:** the patcher's folders and files have names that say what they hold (Deaths and Disappearances, Repairs Made, Family Trees\Reports, Family Tree Edits, Like and Dislike Words, Log Checks, Parents (A New Home), Villagers at Last Save, Villagers Counted), and every copy kept before a repair is in **Copies Made Before Repairs**. These names are used for new saves; **an older save keeps its folders and files where they are**, under their older names (Deaths, Repairs, Logs\Genealogy, Genealogy Edits, Log Words, Cross-Check, Parentage Records, Village Roster), and both the game and the patcher go on reading and writing them there. **Nothing is ever moved or renamed.** If a save folder holds both names (an older and a newer version both played it), the file written last is used, logs are read from both, and a Repair Saves & Logs approval under both names is ignored. Backups are never touched.


## What was new in v1.35.63

- **Island Events log (all five games, new patch).** Every change an island event makes to a villager is logged with the event's title and the answer you picked: health, age, sickness, pregnancy, looks, likes, dislikes, every skill, parents, custom title, mask and Special villager title, as old -> new, plus the villagers an event brings (with their sex and age) or takes away. What an event changes in the whole village -- food, tech points, the food stores, puzzles and the weather -- is a record of its own, and an event that changes nothing says "Changes: none". A new head or body is also an "Appearance changed" record, so the Family Tree Maker follows the villager. Custom Island Events are logged too.
- **Babies follow your last-name rule.** With Villagers Have Last Names, a baby takes its father's or mother's actual last name by the rule chosen in Repair Saves & Logs (From the father, From the mother, or 50:50), including babies born in the catch-up as a village loads.
- **Full Names on the Details Screen (new patch).** The Details screen no longer cuts long names short, and names it already cut are restored by Repair Saves & Logs.
- **Repair Saves & Logs:** set a save's **game speed** (Paused, Slow, Normal, Fast; unpausing warns that the game will catch up); **number duplicate names** is ticked when names break the rule (a Roman number only for the same first and last name); a look change with no record asks how it happened (island event, Custom Island Event or the Change Appearance upgrade); older backups and any saves you choose can be set to Paused.
- **Backups are saved Paused**, so a restored backup never fast-forwards through the time since it was made.
- **Family Tree Maker:** new portrait shapes (Flower, Butterfly, Clover, Spade, Leaf) with **Apply to every one**; glows in the mark's own colour; characters across a portrait, gap between portraits, shrink to fit a page and up to 10 generations a page; words fit inside their shape and each villager can have their own text size; a preview of the exported picture, which is never see-through; names follow renames and numbering; a villager whose looks changed with no record is no longer "left the village"; and it **remembers your look** for the next new tree.
- **Village Matchmaker:** One Family Per Partner, List pairings by (newest generation at the top by default), Prioritize previous partners (on by default), a generation number by every name, last names compared without Roman numbers, Show ages in game units, **Reset to Defaults**, **Refresh Pairings**, and your ticks are remembered.
- **A New Home's Golden Child** is recorded as a birth, with its parents, age (5 years), skills, likes and dislikes, and takes a last name.
- **The Lost Children's births** are logged again.


## Three population modes

Choose the population mode in the patcher; the choice and all paths are remembered.

| Mode | Collection/progression behavior | Output EXE |
|---|---|---|
| No Population Increase | The stock population cap, collection behavior, and progression gates are preserved. Automatic physical-capacity safety still clamps allocation paths at the game's real record pool. | `(Game name) - Modded.exe` |
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `(Game name) - Modded.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `(Game name) - Modded.exe` |

### What each mode does

**No Population Increase** keeps every game's stock population cap, collection
behavior, and progression gates exactly as shipped: 90 in A New Home, 115 in
The Lost Children, 125 in The Secret City, 115 in The Tree of Life, and 105 in
New Believers. Only the automatic physical-capacity safety is applied, and that
never changes the gameplay cap -- it just stops allocations from overrunning the
game's real villager record pool.

**Collection Progression Max Pop** keeps collections meaningful: they continue
to raise the cap, so the maximum is earned rather than granted. A New Home
reaches 256. The Lost Children starts at 231 and adds 0-25 collection points.
The Secret City starts at 115 and adds 0-25 collection points plus 10 more from
Magic level 3. The Tree of Life starts at 125 and adds 0-25 collection points.
New Believers starts at 135 and adds 0-15 collection points.

**Immediate Fixed Max Pop** grants the absolute slot maximum straight away:
256 in A New Home and The Lost Children, 150 in The Secret City, The Tree of
Life, and New Believers. Collection bonuses no longer change the maximum, and
The Secret City's Magic level no longer changes it either.

The two increased modes use every verified built-in villager slot: 256 in A New
Home and The Lost Children, and 150 in The Secret City, The Tree of Life, and
New Believers. Those are hard limits of each game's own record array, not
chosen numbers.

### Resulting maximums

| Game | Stock final maximum | No Population Increase | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|---:|
| A New Home | 90 | 90 | 256 | 256 |
| The Lost Children | 115 | 115 | 231 to 256 | 256 |
| The Secret City | 125 | 125 | 115 to 150 | 150 |
| The Tree of Life | 115 | 115 | 125 to 150 | 150 |
| New Believers | 105 | 105 | 135 to 150 | 150 |

Housing gates remain in place.

All three modes apply the game's existing automatic physical-capacity safety;
it only clamps allocations at the physical record limit and does not change
the selected mode's social cap or collection/progression behavior. All three
modes use the stable short `- Modded` name (a build with **256 Villagers
(Experimental)** ticked is named `- Modded 256` instead; see below). The selected mode,
optional patches, hashes, and applied edits remain identified in the
`.patch-log.json` in the Modded folder's `Virtual Villagers Fun Patcher Files`
folder.

In A New Home, the automatic safety also preflights the stock two-villager
creation path: when only one physical record remains it creates one villager,
and when the 256-record pool is full it skips the second creation. This keeps
the stock allocator from scanning past its physical record array.

### 256 Villagers (Experimental)

The Secret City, The Tree of Life and New Believers each have an optional
**256 Villagers (Experimental)** patch, off by default, that enlarges the game's
villager table from 150 slots to 256 (numbered 0 to 255, as the game counts
them). With it ticked, the two increased modes reach 256 instead of 150, and
No Population Increase is unchanged:

| Game | No Population Increase | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|
| The Secret City | 125 | 221 to 256 | 256 |
| The Tree of Life | 115 | 231 to 256 | 256 |
| New Believers | 105 | 241 to 256 | 256 |

Collection Progression keeps the same bonuses as the ordinary build (The Secret
City: 0-25 collection points plus 10 from Magic level 3; The Tree of Life: 0-25;
New Believers: 0-15) on a higher base, so everything collected reaches 256.

A build with it is named **`(Game name) - Modded 256.exe`**, in a
**`(Game name) - Modded 256`** folder, and keeps its saves and the patcher's
logs in its own save folder, `Documents\LDW\(Game name) - Modded 256\`, apart
from the ordinary `- Modded` saves. The patcher does not copy any saves there;
how to bring an existing village across is in each game's entry below. The
slot-safety guards for twins, triplets and Island Events work at 256 in these
builds.

## Optional patches by game

Every patch below is optional and off by default. The patcher lists them
under these same game headers, sorted by name. Selecting a patch that has a
prerequisite selects the prerequisite automatically.

**Learning Skills Never Fails** is available for all five games. It makes the
native work-task skill roll succeed every time for Farming, Building,
Researching, Healing, and Parenting; New Believers also includes Devotion.
The stock skill gains and caps remain active. It does not change pregnancies,
food, tech-point gain, or other outcomes. In New Believers it applies only to
believers; heathens remain unchanged. This optional patch is off by default.

**Write Births and Conceptions Log to Text File** is also available for all
five games. Records made before a village's first save are held and written
at that save; none is dropped. Since v1.35.30, a held record from a villager
table where hardly anyone is still present at that save ends with a `Note:`
line saying it was probably recorded among villagers who were not in the
village (for example the game's pre-tribe simulation, or a tribe left unsaved
by Start Over). The Note is only a hint and never decides whether a record is
written. A record is still lost if the game closes without saving after it.
**The holding, the village header and creating the log at a village's first
save all need Write Village Statistics to Text File on**: with it off, each
record is written at once without the header, and a village's log first
appears with its first record rather than when the village is started or
after Start Over.

### Virtual Villagers - A New Home

**Birth Control**

Matches the literal VV4/VV5 Birth Control boundary on the exact VV1 build. Manual pairing rejects only a category-2 carrier at internal age>=1000; the two action-9 writer-reaching scans and the planner reject only scanned candidates at internal age>=1000; the autonomous chooser uses the VV4/VV5 score floor and REQUIRES the parenting preference to be checked, rejecting an unchecked villager rather than applying the VV4/VV5 25% non-preference fallback; initiator males and older autonomous initiators retain no upper-age ceiling. Birth Control owns only its named ordinary-route checks; conception, pregnancy, delivery, direct event births, and pending delivery remain separate native paths, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv1_birth_control`

**Keep the Game's Own Log (ldwLog.txt)**

Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\). Every Virtual Villagers game has always had this log, but the base game starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), holds what it writes in memory until the game closes (a crash loses it), and writes only when something goes wrong -- so most players never see the file. Now each time the game opens it adds a "---- Game started ----" line, and every line the game writes is added to the file at once and kept: a missing font picture, a missing picture and a missing sound. A New Home's code contains no other log line (no clock, text-file, healer, tip or path-finding line), so nothing else can be logged. A line repeated without a break is written once a minute with how many times it repeated, at most 1,000 lines are written a minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**

- Patch ID: `vv1_game_log`

**Manual Drop-Breeding overrides Birth Control**

**In A New Home this only changes anything when Birth Control is also ticked: A New Home itself never refuses a woman aged 50 or older on a manual drop. Birth Control adds that refusal, and with both ticked this patch takes it back out for manual drops only; the rest of Birth Control is unchanged.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv1_manual_drop_breeding_overrides_birth_control`

**Builder Action Fixes**

Villagers whose selected job is Building are more likely to try the stock construction dispatcher when food is plentiful: at 400 food or more, about three times in four each time the game chooses what such a villager does, they get the construction attempt the stock game gives only below 400; the rest of the time the game chooses exactly as it always has. What they build, and in what order, is the stock game's: a new population hut first (project IDs 9, 10, and 11, started from nothing as the stock game does), then the projects already under way; the project gates and the manual, existing-work, and repair routes remain stock. On its own this patch draws its roll from the processor's time-stamp counter, never the game's random numbers. With Builders Fix Huts When Idle also selected, that patch's companion takes over this gate so both share its one roll per choice.

- Patch ID: `vv1_builder_action_fixes`

**Continue Research at Max Technologies**

Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3. A villager not checked on Research (any other job, or none) does so only 14% of the times the game gives them research work; otherwise the game goes on to its own next choice. The 14% roll lives in "VVFP VV1 Research At Max.dll", started by VVFP Startup.dll; if it cannot be loaded, every researcher continues as before.

- Patch ID: `vv1_continue_research_at_max_technologies`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen's Food and Tech Point Doublers do not double Island Event, Duplicate Collectible or Golden Child tech gains.

- Requires: vv1_enable_origins_exclusive_features
- Patch ID: `vv1_origins_village_wide_upgrades`

**Numeric Keys: Zip Around the Island**

The number keys move the view to nine measured feature targets in the VV1 1680-unit map, laid out like a numeric keypad (7 8 9 across the top, 4 5 6 in the middle, 1 2 3 along the bottom), using the measured truncating tenth-of-remaining glide on the native village-update cadence. Top-row digits and keypad digits both work; holding a key does not repeat; a glide keeps going even if the view is scrolled or a villager is dragged mid-glide -- press another number key to change course. Adds the loading-screen tip "You can zip around the island with your numeric keys." **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv1_number_keys`

**Show Parents in Details Screen**

Gives A New Home the true parentage the later games keep: every villager born in the village remembers their mother and father for life. While a villager is under 18 (and again if they are ever made younger), two small, faded figures of the parents stand in the upper corners of the Details portrait -- the father on the left facing right, the mother on the right facing left -- and hovering one reads "Son of <name>" or "Daughter of <name>". The record is kept in 'Virtual Villagers 1 Parentage Records - Save <slot>.dat' in the 'Virtual Villagers Fun Patcher Data\Parents (A New Home)' folder beside the saves (Documents\LDW\<game executable name>\), never inside a villager record or the save itself. Each villager's entry follows that villager when the game renumbers its villagers on a load, and is never erased by death, ageing or de-ageing; a new villager starts with none. Each birth is also written to the parentage log the moment it is seen, and the Village Population roster lists each villager's own parents. Founders and villagers born before this patch have no recorded parents. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL. **Needs Write Births and Conceptions Log to Text File on for the father**, which its conception hook supplies: with that patch off only the mother is recorded. **Needs Write Births and Conceptions Log to Text File on for the father (with it off only the mother is recorded) and for the "Birth" records in the parentage log.**

- Patch ID: `vv1_show_parents`

**Sort by Age/Skill/Health in Details Screen**

Adds The Lost Children's Sort By band to A New Home's Villager Detail screen, under the Age and Gender boxes: Age, Skill and Health, each with a radio. The left and right arrows then walk the villagers in that order the way the later games do -- ascending by age, by the villager's highest skill, or by health, with earlier villagers first among equals, and the place in the list is kept when the order is changed. Age is the default. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL, and the base's arrow hooks ask it which villager comes next.

- Patch ID: `vv1_sort_by`

**Improved Pathfinding**

Updates the pathfinding to resemble VV3-VV5. Hopefully villagers don't get stuck behind things anymore! A New Home has no route search: when a villager's next step toward a task is blocked, the stock game nudges them sideways a few times and then clears their whole action list, so they forget the task and drop what they carried. With this row the companion floods the game's own walkability grid from the task and walks the villager round the obstacle, corner by corner, the way The Secret City does. Bumping into a hut or the side of anything is always routed round; only a task that is truly unreachable (its own cell on an obstacle, or walled off) ends the action, at once and without the nudging, as The Secret City does. No executable bytes change: the Origins companion loads "VVFP Improved Pathfinding.dll", which installs its detour only after verifying the stock bytes at the handler. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock walk runs unchanged.

- Patch ID: `vv1_improved_pathfinding`

**Watering the Field Trains Building**

"Watering the field" now gives Building skill, but only when it makes progress towards the garden puzzle (after the lagoon puzzle is complete). Each watering that advances the garden ends with one ordinary Building practice roll, exactly like every other Building job; once the garden is restored, watering gives nothing extra. Because watering now trains Building, a villager whose job checkmark is not Building (any other job, or none) waters the field only 14% of the times the game would send them to it; otherwise the game gives them its next choice of work instead. Villagers checked on Building water exactly as before, and your own drop on the field is never restricted. "Watering crops" and "Trying to water strange patch" are unchanged. No executable bytes change: the Origins companion loads "VVFP VV1 Watering Builds.dll", which installs its hook only after verifying the stock bytes. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock game runs unchanged.

- Patch ID: `vv1_watering_trains_building`

**Dropping an Adult on a Child Tells a Story**

When you drop an adult (18 or older) on a child (under 18), the adult now tells the child a story instead of trying to embrace, as in the later Virtual Villagers games. The adult shows "Telling a story" and talks for a little while, and each story gives the adult one ordinary Breeding practice roll (A New Home's name for Parenting), with the game's own chance and amount. The child shows "Listening to a story" and waits where it is until the story is over, like a villager listening to a joke. Only your own drop does this: villagers never start a story by themselves, and dropping an adult on an adult, a child on anyone, or a 14-17 year old on a child works exactly as before. A dead child, or a sick one (who is sent for healing, as before), gets no story. No executable bytes change: "VVFP Startup.dll" starts "VVFP Storytelling.dll" as the game opens, and it installs its hook only after verifying the stock bytes. **Needs no other patch.**

- Patch ID: `vv1_storytelling`

**Misc Text Fixes**

Corrects a handful of A New Home's English texts: "breeding" becomes "parenting" wherever the game names the skill (the skill name, the improvement message and the Fish of Fertility popup), "This villager improved at farming" gains its full stop, and "Food available to villagers" loses its stray full stop. Each text is changed in place in the game's own string table; the other languages are untouched.

- Patch ID: `vv1_misc_text_fixes`

**Magic Fruit of Life Alters Mortality**

Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.

- Patch ID: `vv1_magic_fruit_alters_mortality`

**Reenable F6 Clothing Change Cheat**

The clothing shortcut cycles the selected active villager through the stock outfits: pressing F6 spends 5,000 tech points to advance to the next outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.

- Patch ID: `vv1_f6_clothing_change_cheat`

**School Lessons Grant Skill**

Each child who finishes the unlocked Going to school activity gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv1_school_lessons_grant_skill`

**School Lessons Stop at 50**

Each child who finishes the Going to school activity still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered. When every skill is at 50 the lesson awards nothing. This matches the Nursery Schools of the later games, which skip any skill at 50. **Requires School Lessons Grant Skill** (the lesson it caps). **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv1_school_lessons_cap_50`

**Easier Healing Mastery**

Healers and villagers who prefer Healing study the Medical Cactus whenever the game gives them healing work and no sick villager needs treatment, including during catch-up (the time that passes while the game is closed, and Time Warp). A villager not checked on Healing (any other job, or none) studies there only 14% of the time; otherwise, as in the normal game, there is nothing to do. Without this patch only a villager you dropped on the cactus does that, and such a villager always studies. The study and its Healing practice are the game's own. **Needs no other patch. With Builders and Healers Work First also selected, healers are given healing work more often, so they study more.** The 14% roll lives in "VVFP VV1 Easier Healing.dll", started by VVFP Startup.dll; if it cannot be loaded, every villager studies as before.

- Patch ID: `vv1_easier_healing_mastery`

**Healers Study Plants Regardless of Food**

Healers are more likely to keep studying plants regardless of the food supply. A villager who was studying the plant it was dropped on (the medical cactus) carries on studying when the village has 400 food or more, exactly as the stock game already does below 400 -- half the time (a 50% chance) each time the game chooses what the healer does; the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Healing (any other job, or none) carries on only on 14% of those checks, here and in catch-up, so farmers and other non-healers study noticeably less; when that roll fails the game chooses their work exactly as it always has. A villager checked on Healing is unchanged. Below 400 food nothing changes. With Builders Fix Huts When Idle also selected, its shared roll (three times in four) is kept: a choice that roll leaves to the stock game is the stock game's for this patch too, and when it passes this patch draws a two-in-three roll of its own, so the chance stays one in two (3/4 x 2/3). Whenever the roll fails, the game's own job choice runs. During catch-up -- the time that passes while the game is closed, and Time Warp -- the normal game continues plant study only when it happens to give that villager healing work while no one is sick; with this patch a villager who was studying the cactus carries on there too, at any food level, half the time (a 50% chance) each time catch-up chooses what they do (otherwise catch-up's own choice stands). **Only a villager you dropped on the medical cactus is studying it; for every healer to study the cactus whenever no one is sick, also select Easier Healing Mastery.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv1_healers_study_regardless_of_food`

**Visual Mods**

Adds decorative flowers to the lagoon and love hut, clothes to the extra hut near the farm, and colorful flowers to the restored garden, by swapping four scene/map images in the game's Images folder. Purely cosmetic -- no executable, gameplay, or save bytes change. Disabling restores the exact base-game images. Credit to the original mod creators.

- Patch ID: `vv1_visual_mods`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 1 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record, numbered like the Conceptions ("Birth 1", "Birth 2", ...), gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies; Repair Saves & Logs can number the Birth records an older patcher wrote without one. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** A New Home stores no parents on any villager record, so both parents are captured at conception; they cannot be recovered from the child afterwards. VV1 stores nothing about the father in the mother's record -- not his name, and no id that could find him -- so his details, his age included, are captured from his own record at the six conception call sites, where the game holds it briefly. A birth that reaches delivery without such a capture reports the father as not captured for that birth, rather than naming the wrong villager. **The Birth records are written by Show Parents in Details Screen, which sees every birth; with it off, only Conception records are written.** **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).** **Needs Show Parents in Details Screen on for the "Birth" records (conceptions are logged without it).**

- Patch ID: `vv1_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure. **Needs Show Parents in Details Screen on for the "Parents:" lines in the Village Population roster.**

- Patch ID: `vv1_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Building (any other job, or none) but whom the game gives building work anyway gets all of this only on 14% of those choices; otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First, Healers Study Plants Regardless of Food and Builder Action Fixes use the same roll when selected with it, so one choice is either all patched or all stock. Healers Study Plants Regardless of Food then adds its own two-in-three roll, so a studying healer carries on half the time. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv1_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine (**in A New Home a healer with no patient studies the medical cactus only if you dropped them on it, unless Easier Healing Mastery is also selected, which makes every healer study it whenever no one is sick**). This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv1_builders_and_healers_work_first`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv1_super_secret_golden_mushroom`

**Villagers Have Last Names**

Babies born in the village and the village's founders get a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last names come from: from the father, from the mother, or 50:50); without a rule recorded, a baby takes its father's last name (the village's default is from the father). A villager can also have a rule of their own for their children (Each villager's own rule): from the father, from the mother, 50:50, or a random last name from the list, which gives each child -- twins and triplets too -- its own random draw from the game's list, every name equally likely. Villagers who arrive through an island event get no last name, because theirs would not be their family's. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. The Golden Child, whose family is not one of the 50, gets no last name. **Needs no other patch.**

- Patch ID: `vv1_last_names`

**Write Island Events Log to Text File**

Every change an island event makes to a villager is written to a new log, the Island Events log ("Virtual Villagers Fun Patcher Logs\Island Events\Virtual Villagers 1 Island Events Log 1.txt"): one numbered record per villager it changed, with the event's title as the game shows it, the answer you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title -- "Gone" for a villager the event took away, and the sex and age of a villager it brought. What an event changes in the village as a whole -- food, tech points, the berries and crops, puzzles solved or unsolved -- is one record of its own, a "Village:" list of old -> new, and an event that changes nothing still gets its record, "Changes: none". A villager whose head or body an event changed also gets an "Appearance changed" record naming the event, so the Family Tree Maker knows the old and the new look are the same villager. The records are written when the game saves, like the other logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.** **A New Home keeps a villager's parents only with Show Parents in Details Screen on: without it, parents are not logged.**

- Patch ID: `vv1_island_events`

**Faster Village-Scrolling**

Updates the slow scrolling when selecting villagers and dragging the screen to VV3-VV5's behavior.

- Patch ID: `vv1_faster_village_scrolling`

**Fix Vanilla Bugs**

Fixes bugs in the base game. A Mysterious Vial (blue liquid): when a pregnant villager drinks it and turns back into a toddler, the pregnancy now ends completely, including the number of babies she was carrying; before, a villager who had been carrying twins or triplets kept that number and her next single pregnancy brought twins or triplets. Every default name can be chosen: the game numbers its 101 male and 101 female names from 0 but picks a number from 1, so Achak (male) and Aba (female) could never be given; now every name in each list can come up, for new villagers and twins alike. A "%" in a villager's name can no longer crash the game: the game showed some names by using them as formatting instructions; now it copies them as plain text, and its text boxes no longer accept a typed "%". The Likes and Dislikes on the Details screen are always shown correctly: the game read each word up to the next comma, but the last word of its list ("sleeping") has none, so a villager with that like or dislike showed stray characters and lost every word after it, and a number past the end of the list showed garbage. Now the last word shows like any other, a number that is not a word is left out, and the line can never run past the space the game keeps for it. A villager's name can no longer be given to another villager on the Details screen: when the arrows or Done are used, the game saves the name box into the selected villager, but it fills the box with the next villager's name only when the screen is next drawn, so two arrow clicks (or an arrow and then Done) taken in the same moment wrote one villager's whole name onto the next villager. Now the screen remembers which villager it filled the name box for, and the box is saved only into that samevillager; otherwise the box is dropped and the right name is shown. A name you type is still saved to that villager. **Needs no other patch.**

- Patch ID: `vv1_fix_vanilla_bugs`

**Full Names on the Details Screen**

The Villager Details screen keeps a villager's whole name. In the base game its name box holds only 10 characters (fewer for wide letters) and, when the screen closes, writes what it holds back to the villager, so a longer name -- a last name, a numbered namesake -- was cut short for good. Now the box holds the 27 characters the game's name field has room for, is wide enough to show them, and copies the whole name back; typing a new name there allows 27 characters too. **Needs no other patch.**

- Patch ID: `vv1_details_full_names`

**Restore Missing Island Events**

A New Home has two island events whose story and effects are complete in the game but which the original game never picks: A Mighty Storm (a typhoon washes away all of the stored food) and The Furry Food (the stored food goes moldy: remove the moldy pieces and some villagers get stomach trouble, or throw out all the food). This adds both to the game's normal random island events, with the same chance as any other event, whenever the village has stored food to lose. Their text and effects are the game's own. **Needs no other patch.**

- Patch ID: `vv1_restore_missing_island_events`

**Show Cause of Death and Epitaphs on Graves, and Log Every Death**

Shows each dead villager's cause of death and an epitaph on their grave, the way The Secret City, The Tree of Life and New Believers do. Clicking a gravestone shows the epitaph in quotes under the name, in a box you can type in (up to 31 characters; Done keeps it), and the cause under the age, in those games' own words (Old age, Disease, Starvation, Work accident, or Unknown causes). The cause is the one that killed them -- old age, sickness, hunger or an empty food bin, an injury at work -- and "Unknown causes" for an island event and anything else, which is how those games word an island-event death. The epitaph is chosen by the rule those games use at a burial: a child's is "Curious and Playful" or "Loving and Special"; an adult's comes from the skill the grave shows (for example "Strong Arms, Big Heart" or "Inspired Architect" for a builder); a villager with no skill is a "Respected Citizen". Those games' Chief, Esteemed Elder and Scholar epitaphs have no counterpart here and are not used. A New Home keeps neither, so both are kept for each save slot in a file beside the saves ('Virtual Villagers Fun Patcher Data\Graves\Virtual Villagers 1 Graves - Save <n>.dat'); Start Over deletes it. A child's grave -- a villager who died before the age of 14 -- names their job the way The Tree of Life words a child's grave, and the way the game's own villager panel names a working child: "Apprentice Farmer" rather than Trainee, Adept or Master, on the grave and in the Deaths log alike. A child with no skill of 20 or more is "Untrained", as before. **Graves dug before this patch was installed get an epitaph the first time they are opened, but no cause: how they died was never recorded.** Every death that leaves a body is written to the Deaths log ('Virtual Villagers 1 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths and Disappearances' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Mysterious Face and The Book, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Saves & Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 1 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 1 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 1 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. In A New Home a villager born here is told by their Birth record, which Show Parents in Details Screen writes: **without that patch no Arrived record is backfilled.** At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 1 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 1 Villagers at Last Save - Save <n>.dat'; Start Over deletes it. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv1_cause_of_death`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv1_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set), and the Tech menu gains **Choose Time Skip Amount** (type 1 to 72 years and the village moves forward that many years, one Time Warp at a time, the game catching up after each; **keep the game running until it is done** -- it waits while the game is paused, and loading another village, Start Over or deleting the tribe drops the rest). Off by default.

- Patch ID: `vv1_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Choose Time Skip Amount costs what the Time Warp upgrade costs: 50,000 tech points, paid when the skip starts. Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv1_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Lost Children

**Birth Control**

Matches the VV4/VV5 Birth Control boundary on the exact VV2 ordinary routes: the native chooser's score floor remains in force while its 25% non-preference fallback is removed so an unchecked preference is rejected outright, the two writer-reaching opcode-12 candidate scans reject candidates at internal age 1000 or greater, and the stock manual carrier/female-only gate rejects older carriers without adding a male upper-age gate. Birth Control owns only those two candidate scans; the conception roll, pregnancy writer, pregnancy, delivery, and automatic physical-capacity safety remain separate native/automatic paths in every public mode.

- Patch ID: `vv2_birth_control`

**Keep the Game's Own Log (ldwLog.txt)**

Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\). Every Virtual Villagers game has always had this log, but the base game starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), holds what it writes in memory until the game closes (a crash loses it), and writes only when something goes wrong -- so most players never see the file. Now each time the game opens it adds a "---- Game started ----" line, and every line the game writes is added to the file at once and kept: a missing font picture, a missing picture, a missing sound, "Seconds Timer out of bounds!" (the computer's clock was set back, so the game's one-second timer is ahead of it) and each tutorial tip shown. The Lost Children's code contains no text-file, healer or path-finding line, so those cannot be logged. A line repeated without a break is written once a minute with how many times it repeated, at most 1,000 lines are written a minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**

- Patch ID: `vv2_game_log`

**Manual Drop-Breeding overrides Birth Control**

**Works the same with or without Birth Control: the 50-and-over refusal it lifts is The Lost Children's own, which Birth Control does not change.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv2_manual_drop_breeding_overrides_birth_control`

**Easier Healing Mastery**

Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up. A villager not checked on Healing (any other job, or none) studies there only 14% of the time; otherwise, as in the normal game, there is nothing to do.

- Patch ID: `vv2_easier_healing_mastery`

**Improved Pathfinding**

Updates the pathfinding to resemble VV3-VV5. Hopefully villagers don't get stuck behind things anymore! The Lost Children already plans routes, but its route follower gives up -- clearing the villager's action list, so the task is dropped -- when a villager stands on a cell the route never reached, and it picks the first neighbour in a fixed order, cutting corners between obstacles. With this row the descent takes the neighbour nearest the task, never cuts a corner between two obstacles, and brings a stranded villager back to the route. As in The Secret City, only a task that is truly unreachable (its own cell on an obstacle, or walled off) ends the action. No executable bytes change: the Origins companion loads "VVFP Improved Pathfinding.dll", which installs its two detours only after verifying the stock bytes. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock walk runs unchanged.

- Patch ID: `vv2_improved_pathfinding`

**Dropping an Adult on a Child Tells a Story**

When you drop an adult (18 or older) on a child (under 18), the adult now always tells that child a story, as in the later Virtual Villagers games. The Lost Children has storytelling of its own, but its drop starts an embrace and only finds its way to the story when the embrace's own second search happens to find the same child, so dropping usually just embraced. Now the adult shows "Telling a story" and each story gives one ordinary Parenting practice roll; the child shows "Listening to a story", and a playing child nearby may join in -- all of it the game's own storytelling. As in the game's own code, an adult with Parenting 50 or more shows "Teaching children" instead. Only your own drop does this: villagers never start a story by themselves, and dropping an adult on an adult, a child on anyone, or a 14-17 year old on a child works exactly as before. A dead child, or a sick one (who is sent for healing, as before), gets no story. No executable bytes change: "VVFP Startup.dll" starts "VVFP Storytelling.dll" as the game opens, and it installs its hook only after verifying the stock bytes. **Needs no other patch.**

- Patch ID: `vv2_storytelling`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Tech and Food Point Doublers, and Cure All Villagers, the Villager Details screen grants Youth, Full Mastery, Running, and Set Age to 18, and the Heathen mask cosmetics are included. The point doublers do not double Island Event, Duplicate Collectible or Gong of Wonder tech gains.

- Requires: vv2_enable_origins_exclusive_features
- Patch ID: `vv2_origins_village_wide_upgrades`

**Tip Wording: Numeric Keys**

Rewords the loading-screen tip "You can zip around the island with your keypad." to "You can zip around the island with your numeric keys.", matching A New Home's new tip. The keys themselves already work in The Lost Children; nothing else changes.

- Patch ID: `vv2_numeric_keys_tip_wording`

**Gong of Wonder Coconuts Fix**

When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.

- Patch ID: `vv2_gong_of_wonder_coconuts_fix`

**Hospital Recovery Heals**

A villager who completes Recovering at the hospital gains exactly 1 health point, capped at 100. Stock VV2's hospital recovery action does not change health.

- Patch ID: `vv2_hospital_recovery_heals`

**Teaching Children Grants Skill**

Each child who finishes a Teaching Children lesson gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv2_teaching_children_grants_skill`

**Teaching Children Stops at 50**

Each child who finishes a Teaching Children lesson (Attending lessons) still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered. When every skill is at 50 the lesson awards nothing. This matches the Nursery Schools of the later games, which skip any skill at 50. **Requires Teaching Children Grants Skill** (the lesson it caps). **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv2_teaching_children_cap_50`

**Healers Study Plants Regardless of Food**

Healers are more likely to keep studying plants regardless of the food supply. A villager who was studying a plant (the same four-plant roll the stock game makes) carries on studying when the village has 300 food or more, exactly as the stock game already does below 300 -- half the time (a 50% chance) each time the game chooses what the healer does; the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Healing (any other job, or none) carries on only on 14% of those checks, here and in catch-up, so farmers and other non-healers study noticeably less; when that roll fails the game chooses their work exactly as it always has. A villager checked on Healing is unchanged. Below 300 food nothing changes. With Builders Fix Huts When Idle also selected, its shared roll (three times in four) is kept: a choice that roll leaves to the stock game is the stock game's for this patch too, and when it passes this patch draws a two-in-three roll of its own, so the chance stays one in two (3/4 x 2/3). Whenever the roll fails, the game's own job choice runs. During catch-up -- the time that passes while the game is closed, and Time Warp -- the normal game never continues plant study at all; with this patch a villager who was studying a plant carries on there too, at any food level, half the time (a 50% chance) each time catch-up chooses what they do (otherwise catch-up's own choice stands). **Only a villager studying a plant carries on (one you dropped on a plant, or a healer Easier Healing Mastery sent to study); for every healer to study whenever no one is sick, also select Easier Healing Mastery.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv2_healers_study_regardless_of_food`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 2 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record, numbered like the Conceptions ("Birth 1", "Birth 2", ...), gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies; Repair Saves & Logs can number the Birth records an older patcher wrote without one. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. VV2 keeps the father's name on the mother's record and no father id; his head and body are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His age, which has no copy on her, is read from his own record -- every caller that holds it passes it, the Love Note included -- so a normal birth records his real age. **Runs on the Origins-exclusive base, which is installed automatically with it and adds the Origins Upgrades buttons to the Tech and Villager Details screens**: the loader trampoline lives in the page that base appends, because VV2's own code cave is occupied by the renamed-build crash guard and has no room for it. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv2_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv2_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Building (any other job, or none) but whom the game gives building work anyway gets all of this only on 14% of those choices; otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First and Healers Study Plants Regardless of Food use the same roll when selected with it, so one choice is either all patched or all stock. Healers Study Plants Regardless of Food then adds its own two-in-three roll, so a studying healer carries on half the time. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv2_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine (**in The Lost Children a healer with no patient studies a plant only if you dropped them on one, unless Easier Healing Mastery is also selected, which makes every healer study whenever no one is sick**). This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv2_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv2_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv2_super_secret_golden_mushroom`

**Villagers Have Last Names**

Babies born in the village and the village's founders get a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last names come from: from the father, from the mother, or 50:50); without a rule recorded, a baby takes its father's last name (the village's default is from the father). A villager can also have a rule of their own for their children (Each villager's own rule): from the father, from the mother, 50:50, or a random last name from the list, which gives each child -- twins and triplets too -- its own random draw from the game's list, every name equally likely. Villagers who arrive through an island event get no last name, because theirs would not be their family's. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv2_last_names`

**Write Island Events Log to Text File**

Every change an island event makes to a villager is written to a new log, the Island Events log ("Virtual Villagers Fun Patcher Logs\Island Events\Virtual Villagers 2 Island Events Log 1.txt"): one numbered record per villager it changed, with the event's title as the game shows it, the answer you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title, Esteemed Elder and totem -- "Gone" for a villager the event took away, and the sex and age of a villager it brought. What an event changes in the village as a whole -- food, tech points, the coconut trees, fish, the field's protection from birds and the crops, puzzles solved or unsolved -- is one record of its own, a "Village:" list of old -> new, and an event that changes nothing still gets its record, "Changes: none". A villager whose head or body an event changed also gets an "Appearance changed" record naming the event, so the Family Tree Maker knows the old and the new look are the same villager. The records are written when the game saves, like the other logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.**

- Patch ID: `vv2_island_events`

**Faster Village-Scrolling**

Updates the slow scrolling when selecting villagers and dragging the screen to VV3-VV5's behavior.

- Patch ID: `vv2_faster_village_scrolling`

**Firepit: Dry Grass Drawn Above the Wood**

When both the dry grass and the firewood have been put in the unlit fire pit, the dry grass is drawn on top of the wood instead of being hidden behind it. Only the drawing order of those two pictures changes; nothing else about the fire pit, the fire puzzle or your save is touched. **Needs no other patch.**

- Patch ID: `vv2_firepit_dry_grass_above_wood`

**Fix Vanilla Bugs**

Fixes bugs in the base game. The Crystal Ball: the island event is only offered when at least one other living villager besides the one who finds the ball is there to trade places with, and if "Keep it" is ever chosen with nobody else living (for example through Pick Island Event), nothing is swapped and the game carries on instead of closing. Every default name can be chosen: the game numbers its 125 male and 125 female names from 0 but picks a number from 1 (and never the last one), so Achak and Zuri (male) and Aba and Zuna (female) could never be given; now every name in each list can come up, for new villagers and twins alike. A "%" in a villager's name can no longer crash the game: the game showed some names by using them as formatting instructions; now it copies them as plain text, and its text boxes no longer accept a typed "%". The Likes and Dislikes on the Details screen are always shown correctly: the game read each word up to the next comma, but the last word of its list ("dirt") has none, so a villager with that like or dislike showed stray characters and lost every word after it, a number past the end of the list showed garbage, and a villager with a great many likes or dislikes overflowed the game's 256-character line, damaging memory. Now the last word shows like any other, a number that is not a word is left out, and a line too long for its space ends in "..." instead of overflowing. A villager's name is saved only to the villager it belongs to on the Details screen: the screen remembers which villager it filled the name box for, and Done or the arrows save the box only into that same villager; if the selected villager is not the one the box was filled for, the box is dropped and the right name is shown. A name you type is still saved to the villager shown. Villagers never turn into totems: the game could bury an Esteemed Elder's totem as if it were a body, leaving its record marked as a totem, and a twin, triplet or the Silver Mirror's double born into that record became an immortal totem that still had a villager's Details screen. Now a totem is never buried and a twin, triplet or double never inherits the mark. **Needs no other patch.**

- Patch ID: `vv2_fix_vanilla_bugs`

**Full Names on the Details Screen**

The Villager Details screen keeps a villager's whole name. In the base game its name box holds only 18 characters (fewer for wide letters) and, when the screen closes, writes what it holds back to the villager, so a longer name -- a last name, a numbered namesake -- was cut short for good. Now the box holds the 23 characters the game's name field has room for, is wide enough to show them, and copies the whole name back; typing a new name there allows 23 characters too. **Needs no other patch.**

- Patch ID: `vv2_details_full_names`

**Restore Missing Island Events**

Lets the island events the original game contains but never runs happen. The Mosquito Swarm (some villagers fall ill and the adults take refuge in the water), The Dragonfly Migration (every villager is restored to full health and cured) and Science Awareness Day (the children gain research skill) join the game's own random island-event roll with the same chance as a typical event. Three events whose text the game ships but never shows are added as rarer no-choice events, each a third as likely as a typical event: The Tattered Diary, The Doctrine of Magicians and The Doctrine of Naturalists, pages of Isola's lore a villager finds; they change nothing else. **Needs no other patch.** With Story / Cheat Upgrades, Pick Island Event also offers the three new events.

- Patch ID: `vv2_restore_missing_island_events`

**Show Cause of Death on Graves, and Log Every Death**

Shows each dead villager's cause of death on their grave, the way The Secret City, The Tree of Life and New Believers do: clicking a gravestone shows the cause under the age, in those games' own words (Old age, Disease, Starvation, Work accident, or Unknown causes). The cause is the one that killed them -- old age, sickness, hunger or an empty food bin, an injury at work -- and "Unknown causes" for an island event and anything else, which is how those games word an island-event death. The Lost Children keeps no cause, so it is kept for each save slot in a file beside the saves ('Virtual Villagers Fun Patcher Data\Graves\Virtual Villagers 2 Graves - Save <n>.dat'); Start Over deletes it. The game's own epitaphs are unchanged. A child's grave -- a villager who died before the age of 14 -- names their job the way The Tree of Life words a child's grave, and the way the game's own villager panel names a working child: "Apprentice Farmer" rather than Trainee, Adept or Master, on the grave and in the Deaths log alike. A child with no skill of 20 or more is "Untrained", as before. **Graves dug before this patch was installed, and bodies that were already lying when it was, show no cause: how they died was never recorded.** Every death that leaves a body is written to the Deaths log ('Virtual Villagers 2 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths and Disappearances' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (A Dangerous Mission and The Voices In The Brush, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Saves & Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 2 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 2 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 2 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 2 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 2 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 2 Villagers at Last Save - Save <n>.dat'; Start Over deletes it. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv2_cause_of_death`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv2_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set), and the Tech menu gains **Choose Time Skip Amount** (type 1 to 72 years and the village moves forward that many years, one Time Warp at a time, the game catching up after each; **keep the game running until it is done** -- it waits while the game is paused, and loading another village, Start Over or deleting the tribe drops the rest). The Tech menu also gains **Pick Gong of Wonder Outcome**: choose what the next ring of the Gong of Wonder does -- any of its 23 results, including the ones the game only gives after a village's first ring, with the amounts, who falls sick, the skill, the babies, and which villager the results that act on the ringer, and the two youth results, act on (one who has died, gone or changed by the ring is left to the game's own choice); each setting starts at Random (original game). Buying it makes the Gong ready to ring at once; ring it within ten minutes, in the same save slot. It is refused, with nothing spent, until the Gong is whole. Off by default.

- Patch ID: `vv2_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event and Pick Gong of Wonder Outcome each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent; Pick Gong of Wonder Outcome is also refused, with nothing spent, while the Gong is not whole). Choose Time Skip Amount costs what the Time Warp upgrade costs: 50,000 tech points, paid when the skip starts. Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv2_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Secret City

**Birth Control**

Requires BOTH parenting skill and the checked preference before a villager will initiate Embracing. The native chooser's score floor remains in force and the scanned candidate stays in the stock internal-age 360..999 range, but the 25% non-preference fallback is removed: a roll that admitted one unchecked villager in four is the reported leak. The initiating villager has no extra upper-age rejection. Birth Control owns only the five ordinary initiator checks; the native manual category-1 carrier gate, conception, pregnancy, and delivery remain separate, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv3_birth_control`

**Keep the Game's Own Log (ldwLog.txt)**

Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\). Every Virtual Villagers game has always had this log, but the base game starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), holds what it writes in memory until the game closes (a crash loses it), and writes only when something goes wrong -- so most players never see the file. Now each time the game opens it adds a "---- Game started ----" line, and every line the game writes is added to the file at once and kept: a missing font picture, a missing picture, a missing sound, a text the game asks for that is missing from its text file (sm.xml), a text in sm.xml with no end, a healer who could not find anyone to heal and "Seconds Timer out of bounds!" (the computer's clock was set back, so the game's one-second timer is ahead of it). The Secret City's code contains no tip or path-finding line, so those cannot be logged (its villagers keep a pointer to the log, but no code writes through it). A line repeated without a break is written once a minute with how many times it repeated, at most 1,000 lines are written a minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**

- Patch ID: `vv3_game_log`

**Manual Drop-Breeding overrides Birth Control**

**Works the same with or without Birth Control: the 50-and-over refusal it lifts is The Secret City's own, which Birth Control does not change.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv3_manual_drop_breeding_overrides_birth_control`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Food and Tech Point Doublers, Complete all Collections, Reset all Collections, and Equal Division of Labor with and without Parenting, all supplied by the base Origins feature rather than this optional payload. The point doublers do not double Island Event or Duplicate Collectible tech gains.

- Requires: vv3_enable_origins_exclusive_features
- Patch ID: `vv3_origins_village_wide_upgrades`

**Everyone Tries On the Robe**

Dropping an active, living, non-nursing villager on the robe interrupts every other active, living, non-nursing villager and sends them to try on the robe too. Each villager receives the complete base-game success or failed-fit result, and the base game alone decides who becomes Tribal Chief.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv3_everyone_tries_on_robe`

**Nature Level 1 Actually Replenishes Food Sources Faster**

Nature level 1 or higher reduces fruit-tree refills from 3 hours to 2 hours 15 minutes and honey refills from 1 hour to 45 minutes. Fruit trees retain their stock Nature quantity bonus, while honey gains the same proportional quantity bonus.

- Patch ID: `vv3_nature_honey_refill`

**Nature Level 3 Actually Alters Mortality**

Nature level 3 shifts every ordinary villager's complete mortality curve seven displayed years later. The stock Medicine threshold is calculated first, so the benefits stack, and the shared aging loop applies the change during ordinary play and time catch-up.

- Patch ID: `vv3_nature_level_three_alters_mortality`

**Pointing Out a Rare Collectible Always Works**

When the Tribal Chief completes Pointing out a rare collectible and the stock game rejects its random choice (a collectible a villager is already after, or a special one already collected), the whole stock selection is run again, up to 20 times in all, stopping as soon as a collectible is placed. In practice a collectible almost always appears instead of the stock cooldown being spent for nothing; if every attempt is refused (for example, when every special collectible has already been found), nothing is placed, exactly as in the stock game. The original rare categories, collectible IDs, collection rules and placement logic are unchanged.

- Patch ID: `vv3_rare_collectible_retry`

**Fruit Counts When It Reaches the Food Bin**

Fruit picking works like honey gathering: the fruit leaves the tree, and the village gains its food, only when the villager puts it in the food bin. In the stock game both happened the moment the fruit was picked, before the walk to the bin. A villager who lets go of the fruit anywhere else -- the trip is interrupted, for example -- takes nothing from the tree and adds no food. Several villagers may pick the same tree at once: each delivery takes its own load off the tree, which never goes below zero, and a delivery that finds the tree already emptied by the others still adds its food, as honey does. The food per load, the Tribal Chief's supervision bonus, the Food Gathered statistic and the trees' regrowth are unchanged, and catch-up still gains the same food. **Unverified in play: the effect has not been tested in the game.**

- Patch ID: `vv3_fruit_harvested_at_food_bin`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 3 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record, numbered like the Conceptions ("Birth 1", "Birth 2", ...), gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies; Repair Saves & Logs can number the Birth records an older patcher wrote without one. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. VV3 keeps the father's name on the mother's record and no father id. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they are correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the conception hook reads the other parent's saved record -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv3_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv3_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Building (any other job, or none) but whom the game gives building work anyway gets all of this only on 14% of those choices; otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv3_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine (**in The Secret City, only once Medicine 2 has been researched**). This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv3_builders_and_healers_work_first`

**Tribal Chief Lessons Stop at 50**

The Tribal Chief's lessons stop at 50. Each child who finishes a lesson still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered, and when every skill is at 50 the lesson awards nothing. This matches A New Home's and The Lost Children's lesson patches and the later games' Nursery Schools. The Secret City has no companion that runs every frame, so the row diverts the lesson award into a small stub in the page Origins appends, which calls "VVFP Lesson Cap.dll"; if the DLL cannot be loaded, the stock lesson runs and trains to 100. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv3_chief_lessons_cap_50`

**Tribal Chief Supervises the Hospital**

Dropping the Tribal Chief on the Hospital hotspot (Medicine level 2 or more) makes him walk to the spot where he stands when he is "Concerned about the sick" and do the game's own "Directing work" action there; in the stock game he does nothing and picks another task. While he directs work, a healer who finishes studying medicine at the hospital gains twice the usual Medicine skill points (at least 1); the chance to learn is unchanged, so this does not stack with the Medicine technology's cure bonus. A healer whose cure roll fails also gets a second chance: the chief's supervision roll, which passes about 25% of the time per Leadership level, lets the cure go ahead as if the healer had passed. Otherwise the cure is exactly the stock one. The stock game already gives the chief this bonus for fishing, fruit, honey, huts, research and puzzles, but never for a cure. The companion is "VVFP VV3 Chief Hospital.dll", started by VVFP Startup.dll, and needs no other row. On by default; **the in-game effect is not yet verified by a live test.**

- Patch ID: `vv3_chief_hospital_supervision`

**Both Factions: Nature and Magic**

In the stock game the Tech screen lets a tribe join one faction: once Nature or Magic is bought, the other answers "You have already chosen your faction!", and a save holding both (made with a cheat) no longer loads at all -- the game's own loader refuses it. With this patch:

- **Buying the second faction:** buy one faction on the Tech screen as usual, then click the other; it is bought at its normal price in tech points. Buying level 1 of either faction asks Yes/No: "With the power of the Fun Patcher, you can now embrace both Nature and Magic Factions. Use this gift wisely." (No buys nothing). Levels 2 and 3 are bought without a question, as before, and both Buy buttons stay as they always are.
- **Every faction effect at once,** each at the level bought: Nature's faster food refills (level 1, with the patcher's "Nature Level 1 Actually Replenishes Food Sources Faster" row if ticked), the Pitcher Plant (level 2) and longer lives (level 3, with the patcher's "Nature Level 3 Actually Alters Mortality" row if ticked); Magic's extra tech point from research (level 1), the Berry Plant (level 2) and the population bonus (level 3, +10). Nature has no population bonus, so nothing stacks twice: the maximum stays 150 (256 with 256 Villagers), and Immediate Fixed keeps its fixed maximum.
- **Both herbs** grow on the island and can be gathered and brewed as in a one-faction game.
- **The Tech screen** lights both faction columns, every level filled in, each with its own floating petals or sparkles.
- **Seven new potions** need a Pitcher Plant and a Berry Plant in the pot together, with a Tiger Lily (a fun potion), Cactus (a trance), Lotus (crazy talk), Black Orchid (paralysis), Rose (a little bit lonely), a second Pitcher Plant (whoa! -- the drinker is moved) or a second Berry Plant (something smells yummy -- free children under 14 run to the pot). Each is exactly the game's own potion of that effect; the unpatched game gives these mixes the failed potion. They count toward "Alchemy R Us" (50 recipes) and Stews Found.
- **The sharks:** the latest shark potion decides how they look -- Nature's stink bomb makes them go, Magic's Shark Charmer Vial brings them back charmed and sparkling -- and nothing else changes: the puzzle, its message and reward stay once.
- **Save safety:** the faction bought first stays in the save exactly as the unpatched game keeps it; the second faction, and which new potions were brewed, are kept in a file of each save's own (`Virtual Villagers Fun Patcher\Save N\Data\Factions\Virtual Villagers 3 Second Faction - Save N.dat`) and come back when that save is loaded. **No save ever holds both factions, so every save is one the unpatched game loads; without this patch a village loads with its first faction only** (the file keeps the second, and putting the patch back brings it back). Start Over deletes the file with the rest of the save's data.

The companion is "VVFP VV3 Both Factions.dll", started by VVFP Startup.dll. **Needs no other patch.** On by default; **the in-game effect is not yet verified by a live test.** Research: `docs/vv3-both-factions.md`.

- Patch ID: `vv3_both_factions`

**Esteemed Elders' Totems Use No Villager Records** (The Lost Children)

In the stock game each Esteemed Elder's totem statue takes one of the village's 256 villager records for good, so a big village's statues crowd out babies waiting to be born, and a new elder's totem could take a freed record before a waiting baby. With this patch the totems are kept apart, in a file of each save's own (`Virtual Villagers Fun Patcher\Save N\Data\Elder Totems\ElderTotems.dat`), and take no villager record: when a village loads, every totem in it moves into that file and its record is free for a villager (a villager carrying the totem mark but alive is never moved). The totems look, stand in front of or behind villagers, show their "<name>`s totem" label and can be dragged and placed exactly as before, on the village and on the Map, and the totem puzzle's spot works as before. **There is no longer a limit of 50 Esteemed Elders**: the elder pass's two "fewer than 50 totems" checks never wait while the file works. The file is written before every save of that slot and read after every load; one that belongs to another village is moved aside, never used or overwritten; if the file is there but cannot be opened, that session plays as the stock game. Start Over deletes that save's ElderTotems.dat with the rest of its data. **The game without this patch never reads ElderTotems.dat: before removing the patch, use Repair Saves & Logs > "Put Totems Back Into the Save"** (the patcher also warns before building over a copy that has it), or the village simply shows no totems -- nothing else changes. The companion is "VVFP VV2 Totems.dll", started by VVFP Startup.dll, and needs no other row. **The in-game effect is not yet verified by a live test.**

- Patch ID: `vv2_totems_out_of_entries`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv3_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv3_super_secret_golden_mushroom`

**Villagers Have Last Names**

Babies born in the village and the village's founders get a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last names come from: from the father, from the mother, or 50:50); without a rule recorded, a baby takes its father's last name (the village's default is from the father). A villager can also have a rule of their own for their children (Each villager's own rule): from the father, from the mother, 50:50, or a random last name from the list, which gives each child -- twins and triplets too -- its own random draw from the game's list, every name equally likely. Villagers who arrive through an island event get no last name, because theirs would not be their family's. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv3_last_names`

**Write Island Events Log to Text File**

Every change an island event makes to a villager is written to a new log, the Island Events log ("Virtual Villagers Fun Patcher Logs\Island Events\Virtual Villagers 3 Island Events Log 1.txt"): one numbered record per villager it changed, with the event's title as the game shows it, the answer you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title, and Tribal Chief -- "Gone" for a villager the event took away, and the sex and age of a villager it brought. What an event changes in the village as a whole -- food, tech points, the fruit trees and honey, puzzles solved or unsolved and the weather -- is one record of its own, a "Village:" list of old -> new, and an event that changes nothing still gets its record, "Changes: none". A villager whose head or body an event changed also gets an "Appearance changed" record naming the event, so the Family Tree Maker knows the old and the new look are the same villager. The records are written when the game saves, like the other logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.**

- Patch ID: `vv3_island_events`

**Fix Vanilla Bugs**

Fixes bugs in the base game. The Royal Jelly: the dark vial now cures the villager's cold and raises their Healing, and the clear vial (whose text says the jelly turned bitter) changes nothing, so each vial does what its own text says. The Mysterious Vial (amber): the "flash of scientific insight" result now also gives the tribe 100 tech points, as its text promises, as well as the villager's Research gain. The Mysterious Vial (quartz): a villager who is exactly 14 now gets the text of what really happens to them (becoming an elder) instead of the text about becoming a little child. A village with exactly 150 villagers can be saved and loaded again: the base game, when it saves a full list of 150 villagers, writes past the end of that list and damages the next part of the save, so the village refused to load; now all 150 are kept and the village loads, and a village already saved that way is repaired when it is loaded. Every default name can be chosen: the game numbers its 125 male and 125 female names from 0 but picks a number from 1 (and never the last one), so Akivi and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. A "%" in a villager's name can no longer crash the game: the game showed some names by using them as formatting instructions; now it copies them as plain text, and its text boxes no longer accept a typed "%". A like or dislike holding a negative number other than the game's own "none" (-1) is left out of the Details screen instead of being shown as "ants". A villager's name is saved only to the villager it belongs to on the Details screen: the screen remembers which villager it filled the name box for, and Done or the arrows save the box only into that same villager; if the selected villager is not the one the box was filled for, the box is dropped and the right name is shown. A name you type is still saved to the villager shown. Builders build population huts while the game catches up: after a Time Warp, or when the game is opened after time away, the base game had builders work on a hut without walking there, so their work counted only if they already stood on that hut's site and the huts hardly grew; now each builder goes to the hut first, as in The Tree of Life and New Believers, so the work is added to that hut (each try still needs the builder's Building roll, as in the base game). **Needs no other patch.**

- Patch ID: `vv3_fix_vanilla_bugs`

**Full Names on the Details Screen**

The Villager Details screen keeps a villager's whole name. In the base game its name box holds only 18 characters (fewer for wide letters) and, when the screen closes, writes what it holds back to the villager, so a longer name -- a last name, a numbered namesake -- was cut short for good. Now the box holds the 23 characters the game's name field has room for, is wide enough to show them, and copies the whole name back; typing a new name there allows 23 characters too. **Needs no other patch.**

- Patch ID: `vv3_details_full_names`

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 3 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths and Disappearances' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Tsunami and The Low Tide, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Saves & Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 3 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 3 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 3 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 3 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 3 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 3 Villagers at Last Save - Save <n>.dat'; Start Over deletes it. The cause is the one The Secret City itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv3_cause_of_death`

**256 Villagers (Experimental)**

Gives The Secret City 256 villager slots (numbered 0 to 255) instead of 150. The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 221 and adds 0-25 collection points plus 10 from Magic level 3, reaching 256 with everything; No Population Increase keeps the stock cap of 125, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - The Secret City - Modded 256.exe' (in a 'Virtual Villagers - The Secret City - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - The Secret City - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - The Secret City - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**Needs Fix Vanilla Bugs on (it is on by default) to load a village that the base game's exactly-150-villager save bug has already damaged.** The base game damages a save made with exactly 150 villagers so that it will not load (see Fix Vanilla Bugs above); with Fix Vanilla Bugs ticked, the 256 build loads such a save with all 150 villagers and saves it in the 256 format. A 256 build cannot itself make that damage.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv3_population_256`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv3_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set), and the Tech menu gains **Choose Time Skip Amount** (type 1 to 72 years and the village moves forward that many years, one Time Warp at a time, the game catching up after each; **keep the game running until it is done** -- it waits while the game is paused, and loading another village, Start Over or deleting the tribe drops the rest). The Tech menu also gains **Recharge Chief Powers**: the Tribal Chief's once-a-day powers (granting food, educating the children, pointing out a rare collectible) are ready to use at once, exactly as when a villager first becomes the chief, and the next use rests that power for a day as usual; with no living chief, no powers yet (Leadership level 0) or every power ready already, it says so and nothing is spent. Off by default.

- Patch ID: `vv3_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Recharge Chief Powers costs the same 30,000, paid when the powers are recharged. Choose Time Skip Amount costs what the Time Warp upgrade costs: 50,000 tech points, paid when the skip starts. Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv3_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Tree of Life

**Complete Fish Scales = Golden Fish in Nets**

Golden Fish become eligible in the fishing nets only after all 12 Fish Scales are collected. This changes the stock partial-collection threshold while preserving the completed collection's original 25% Golden Fish chance and every other fishing outcome.

- Patch ID: `vv4_complete_scales_golden_fish`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Food and Tech Point Doublers, Full Heal/Cure All, All Villagers are Exactly 18, Complete and Reset All Collections, and Equal Division of Labor with and without Parenting, the Villager Details screen grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance, and the Heathen mask cosmetics are included. The point doublers do not double Island Event or Duplicate Collectible tech gains.

- Requires: vv4_enable_origins_exclusive_features
- Patch ID: `vv4_origins_village_wide_upgrades`

**Keep the Game's Own Log (ldwLog.txt)**

Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\). Every Virtual Villagers game has always had this log, but the base game starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), holds what it writes in memory until the game closes (a crash loses it), and writes only when something goes wrong -- so most players never see the file. Now each time the game opens it adds a "---- Game started ----" line, and every line the game writes is added to the file at once and kept: a missing font picture, a missing picture, a missing sound, "Seconds Timer out of bounds!" (the computer's clock was set back, so the game's one-second timer is ahead of it), a text the game asks for that is missing from its text file (sm.xml), a text in sm.xml with no end and a healer who could not find anyone to heal. The Tree of Life's code contains no tip or path-finding line, so those cannot be logged (its villagers keep a pointer to the log, but no code writes through it). A line repeated without a break is written once a minute with how many times it repeated, at most 1,000 lines are written a minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**

- Patch ID: `vv4_game_log`

**Optional Text changes**

Replaces some in-game text with wording consistent with the other Virtual Villagers games (for example, the "Scholar" title becomes "Esteemed Elder", and a few labels and event lines are capitalized and punctuated to match). When active, the game's Assets/sm.xml is swapped for the edited version; when the patch is not selected, the base-game text is left untouched. No executable bytes are changed.

- Patch ID: `vv4_optional_text_changes`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 4 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record, numbered like the Conceptions ("Birth 1", "Birth 2", ...), gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies; Repair Saves & Logs can number the Birth records an older patcher wrote without one. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. Village seeding is excluded, so a new village does not write a record for every starting villager. The game keeps only the father's name on the mother's record. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the moment the engine hands both parents to the hook -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv4_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv4_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Building (any other job, or none) but whom the game gives building work anyway gets all of this only on 14% of those choices; otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv4_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine (**in The Tree of Life, only once the Hospital has been built**). This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv4_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv4_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv4_super_secret_golden_mushroom`

**Villagers Have Last Names**

Babies born in the village and the village's founders get a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last names come from: from the father, from the mother, or 50:50); without a rule recorded, a baby takes its father's last name (the village's default is from the father). A villager can also have a rule of their own for their children (Each villager's own rule): from the father, from the mother, 50:50, or a random last name from the list, which gives each child -- twins and triplets too -- its own random draw from the game's list, every name equally likely. Villagers who arrive through an island event get no last name, because theirs would not be their family's. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv4_last_names`

**Write Island Events Log to Text File**

Every change an island event makes to a villager is written to a new log, the Island Events log ("Virtual Villagers Fun Patcher Logs\Island Events\Virtual Villagers 4 Island Events Log 1.txt"): one numbered record per villager it changed, with the event's title as the game shows it, the answer you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title -- "Gone" for a villager the event took away, and the sex and age of a villager it brought. What an event changes in the village as a whole -- food, tech points, the blackberries, cutting tools and bars of soap, puzzles solved or unsolved and the weather -- is one record of its own, a "Village:" list of old -> new, and an event that changes nothing still gets its record, "Changes: none". A villager whose head or body an event changed also gets an "Appearance changed" record naming the event, so the Family Tree Maker knows the old and the new look are the same villager. The records are written when the game saves, like the other logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.**

- Patch ID: `vv4_island_events`

**Manual Drop-Breeding overrides Birth Control**

**Needs no other patch: the 50-and-over refusal it lifts is The Tree of Life's own; this game has no Birth Control patch.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food, love-shack and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv4_manual_drop_breeding_overrides_birth_control`

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 4 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths and Disappearances' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Sealed Box, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Saves & Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 4 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 4 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 4 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 4 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 4 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 4 Villagers at Last Save - Save <n>.dat'; Start Over deletes it. The cause is the one The Tree of Life itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv4_cause_of_death`

**Fix Vanilla Bugs**

Fixes bugs in the base game. A village with exactly 150 villagers can be saved and loaded again: the base game, when it saves a full list of 150 villagers, writes past the end of that list and damages the next part of the save, so the village then refuses to load and the game offers to start a new tribe. Now all 150 villagers are kept and the village loads. A village that was already saved with 150 villagers and would not load is repaired when it is loaded. Only a village with 150 villagers is affected; the base game cannot reach 150 on its own, but the Collection Progression and Immediate Fixed population modes can. Every default name can be chosen: the game numbers its 185 male and 185 female names from 0 but picks a number from 1 (and never the last one), so Ago and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. A "%" in a villager's name can no longer crash the game: the game showed some names by using them as formatting instructions; now it copies them as plain text, and its text boxes no longer accept a typed "%". A like or dislike holding a negative number other than the game's own "none" (-1) is left out of the Details screen instead of being shown as "ants". A villager's name is saved only to the villager it belongs to on the Details screen: the screen remembers which villager it filled the name box for, and Done or the arrows save the box only into that same villager; if the selected villager is not the one the box was filled for, the box is dropped and the right name is shown. A name you type is still saved to the villager shown. **Needs no other patch.**

- Patch ID: `vv4_fix_vanilla_bugs`

**Full Names on the Details Screen**

The Villager Details screen keeps a villager's whole name. In the base game its name box holds only 18 characters (fewer for wide letters) and, when the screen closes, writes what it holds back to the villager, so a longer name -- a last name, a numbered namesake -- was cut short for good. Now the box holds the 23 characters the game's name field has room for, is wide enough to show them, and copies the whole name back; typing a new name there allows 23 characters too. **Needs no other patch.**

- Patch ID: `vv4_details_full_names`

**256 Villagers (Experimental)**

Gives The Tree of Life 256 villager slots (numbered 0 to 255) instead of 150. The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 231 and adds 0-25 collection points, reaching 256 with everything; No Population Increase keeps the stock cap of 115, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - The Tree of Life - Modded 256.exe' (in a 'Virtual Villagers - The Tree of Life - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - The Tree of Life - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - The Tree of Life - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**Needs Fix Vanilla Bugs on (it is on by default) to load a village that the base game's exactly-150-villager save bug has already damaged.** The base game damages a save made with exactly 150 villagers so that it will not load (see Fix Vanilla Bugs above); with Fix Vanilla Bugs ticked, the 256 build loads such a save with all 150 villagers and saves it in the 256 format. A 256 build cannot itself make that damage.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv4_population_256`

**Learning Skills Never Fails**

Believers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv4_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set), and the Tech menu gains **Choose Time Skip Amount** (type 1 to 72 years and the village moves forward that many years, one Time Warp at a time, the game catching up after each; **keep the game running until it is done** -- it waits while the game is paused, and loading another village, Start Over or deleting the tribe drops the rest). Off by default.

- Patch ID: `vv4_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Choose Time Skip Amount costs what the Time Warp upgrade costs: 50,000 tech points, paid when the skip starts. Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv4_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - New Believers

**Clickable Tips**

Clicking the curled vine beneath the on-screen Puzzles button shows a random in-game tip in the gray message bar (with the engine's own auto-hide timer) and plays the hou.ogg chime.

- Patch ID: `vv5_clickable_tips`

**Easier Devotee Training**

Villagers with positive Devotion skill can spontaneously use the stock Honoring action. Statue-drop Honoring remains available for training beginners, while villagers with no Devotion skill do not autonomously Honor. A villager not checked on Devotion (any other job, or none) honours only 14% of the times this patch would otherwise let them; villagers checked on Devotion are unchanged.

- Patch ID: `vv5_easier_devotee_training`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Tech and Food Point Doublers, Full Heal/Cure All, All Villagers are Exactly 18, Complete and Reset All Collections, Equal Division of Labor with and without Parenting, and Change Appearance for All, the Villager Details screen grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance, and the Heathen mask cosmetics are included. The point doublers do not double Island Event or Duplicate Collectible tech gains. The Village-Wide Running, Full Mastery and Make Villagers Young Adults process only Believers and skip Heathens; Change Appearance for All changes every villager, Heathens included.

- Requires: vv5_enable_origins_exclusive_features
- Patch ID: `vv5_origins_village_wide_upgrades`

**Guardians of Isola Rewrite**

Overhauls the New Believers story presentation: replaces the in-game text (Assets/sm.xml) and twelve story/UI images -- the five totem strips, idol states, the blinking-eyes and mask strips, and the main menu -- with the Guardians of Isola rewrite. Purely presentational; no gameplay, executable, or save bytes change. Disabling restores the exact base-game files.

- Patch ID: `vv5_guardians_of_isola_rewrite`

**Heathen Mommy Puzzle Restoration**

Restores the natural Heathen Mommy to newly created villages as a tag-17 Heathen mother with one nursing baby, using two physical slots, and restores the hidden 17th Heathen Parent graphic and full-tile rollover messages to the Puzzles screen. Existing saves are not retroactively given a new mother.

- Patch ID: `vv5_heathen_mommy_puzzle`

**Keep the Game's Own Log (ldwLog.txt)**

Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\LDW\<game executable name>\). Every Virtual Villagers game has always had this log, but the base game starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), holds what it writes in memory until the game closes (a crash loses it), and writes only when something goes wrong -- so most players never see the file. Now each time the game opens it adds a "---- Game started ----" line, and every line the game writes is added to the file at once and kept: a missing font picture, a missing picture, a missing sound, "Seconds Timer out of bounds!" (the computer's clock was set back, so the game's one-second timer is ahead of it), a text the game asks for that is missing from its text file (sm.xml), a text in sm.xml with no end, a villager who is stuck, a villager who cannot find a way to where it is going, a healer who could not find anyone to heal and each villager walking to the love shack door. New Believers' code contains no tip line, so tips cannot be logged. A line repeated without a break is written once a minute with how many times it repeated, at most 1,000 lines are written a minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**

- Patch ID: `vv5_game_log`

**Move the "Playing in the dirt" Spot**

Moves where children go to play in the dirt. In the stock game the spot is a strip of ground that runs from the rainbow totem's side down across the river, so a child playing in the dirt wanders through the water and ends up on the bank behind the research shelves; this makes it the flower patch east of the dirt path (the worn ground with the flowers, west of the flower rock), where the owner marked it: about 305 by 205 with six random steps inside it. The action, its text, its sound and its length are unchanged.

- Patch ID: `vv5_playing_in_the_dirt_spot`

**Charitable Soul Epitaph**

When a Devotee dies and is buried, the epitaph New Believers writes on the grave is chosen at random, with equal chances, between the game's usual epitaph ("Respected Citizen", or "Respected Devotee" with Guardians of Isola Rewrite) and "Charitable Soul". In the stock game every other job already gets one of two epitaphs on a coin flip (a Farmer is "Child of the Earth" or "Nature's Friend", and so on), but a Devotee always got the usual epitaph, which an adult with no skill at all also gets. A villager's job here is the one the grave names: their highest skill. Only Devotees change: the unskilled adult keeps the usual epitaph, children and villagers with three or more master skills keep their own epitaphs, and every other job keeps its pair. The epitaph is stored in the grave like any other, so it is saved with the village, the player can still edit it, and the Deaths log records it. Graves that earlier versions of this patch wrote as "Devoted Soul" keep that epitaph.

- Patch ID: `vv5_devoted_soul_epitaph`

**Statue Drops: Normal Action or Honoring**

Dropping a villager on a completed statue gives Polishing the Statue or Honoring on a 50/50 choice, regardless of that villager's skills. Only the completed statue is affected: building an unfinished statue, the upgradeable statue's Honoring, and the Confused result when the technology is missing all keep their stock behaviour. When a villager later carries that statue job on by themselves (the game's own choice), the 50/50 pick is kept only for a villager checked on its skill -- Honoring on Devotion, Polishing on Building -- and for anyone else 14% of the time; otherwise they do neither and the game gives them something else to do. Your own drop is never restricted.

- Patch ID: `vv5_statue_polishing_or_honoring`

**VV4 Nursery School Divisor Parity**

For parity with Virtual Villagers 4, changes VV5's six-skill spread lesson divisor from five to six. VV5 normally distributes one-fifth of a lesson to each of six skills, an arithmetic inconsistency that awards six-fifths in total; this patch distributes exactly one-sixth to each skill without claiming whether the original inconsistency was intentional.

- Patch ID: `vv5_vv4_nursery_divisor_parity`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 5 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record, numbered like the Conceptions ("Birth 1", "Birth 2", ...), gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies; Repair Saves & Logs can number the Birth records an older patcher wrote without one. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. Village seeding is excluded, so a new village does not write a record for every starting villager. The game keeps only the father's name on the mother's record. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the moment the engine hands both parents to the hook -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv5_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv5_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. A villager whose job checkmark on the Villager Details screen is not Building (any other job, or none) but whom the game gives building work anyway gets all of this only on 14% of those choices; otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv5_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine (**in New Believers, only once the Pain Totem has been dismantled**). This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv5_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv5_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv5_super_secret_golden_mushroom`

**Villagers Have Last Names**

Babies born in the village and the village's founders get a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last names come from: from the father, from the mother, or 50:50); without a rule recorded, a baby takes its father's last name (the village's default is from the father). A villager can also have a rule of their own for their children (Each villager's own rule): from the father, from the mother, 50:50, or a random last name from the list, which gives each child -- twins and triplets too -- its own random draw from the game's list, every name equally likely. Villagers who arrive through an island event get no last name, because theirs would not be their family's. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv5_last_names`

**Write Island Events Log to Text File**

Every change an island event makes to a villager is written to a new log, the Island Events log ("Virtual Villagers Fun Patcher Logs\Island Events\Virtual Villagers 5 Island Events Log 1.txt"): one numbered record per villager it changed, with the event's title as the game shows it, the answer you picked when it asked, and each change as old -> new -- health, age, sickness, pregnancy, head, body, name, likes, dislikes, every skill, parents, custom title, mask and Special villager title, faith and Heathen -- "Gone" for a villager the event took away, and the sex and age of a villager it brought. What an event changes in the village as a whole -- food, tech points, the noni and crops, puzzles solved or unsolved and the weather -- is one record of its own, a "Village:" list of old -> new, and an event that changes nothing still gets its record, "Changes: none". A villager whose head or body an event changed also gets an "Appearance changed" record naming the event, so the Family Tree Maker knows the old and the new look are the same villager. The records are written when the game saves, like the other logs. **Needs Write Births and Conceptions Log to Text File: that patch's DLL writes the records.**

- Patch ID: `vv5_island_events`

**Manual Drop-Breeding overrides Birth Control**

**Needs no other patch: the 50-and-over refusal it lifts is New Believers' own; this game has no Birth Control patch.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food, love-shack and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv5_manual_drop_breeding_overrides_birth_control`

**Learning Skills Never Fails**

Believers succeed every work-task skill roll for Farming, Building, Researching, Healing, Parenting, and Devotion; heathens and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv5_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set), and the Tech menu gains **Choose Time Skip Amount** (type 1 to 72 years and the village moves forward that many years, one Time Warp at a time, the game catching up after each; **keep the game running until it is done** -- it waits while the game is paused, and loading another village, Start Over or deleting the tribe drops the rest). Off by default.

- Patch ID: `vv5_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Choose Time Skip Amount costs what the Time Warp upgrade costs: 50,000 tech points, paid when the skip starts. Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv5_story_cheat_upgrades_cost_tech_points`


That is 103 optional patches across the five games.

Three patches change files rather than executable bytes: **VV1 Visual
Mods**, **VV4 Optional Text changes**, and the **VV5 Guardians of Isola
Rewrite** swap images and text inside the copied game folder only, and
restore the exact base-game files when the patch is not selected.

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 5 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths and Disappearances' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken by the Custom Island Event's "Disappears" gets a "Disappeared" record (the game itself has no such event), and a believer who goes over to the Heathens (faith falling to 0, in play or while the game catches up on time away or a Time Warp; The Spa; The Cracked Mask; or the Custom Island Event's "Becomes a Heathen") leaves the tribe with a "Disappeared" record, "Left the tribe: became a Heathen", written the moment it happens (a Heathen is never a villager; converted back, they get an "Arrived" record again), and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Saves & Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 5 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers, a Heathen converted to a believer (a Heathen is never a villager) -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 5 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", "Converted from the Heathens", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 5 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 5 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 5 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 5 Villagers at Last Save - Save <n>.dat'; Start Over deletes it. The cause is the one New Believers itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv5_cause_of_death`

**Fix Vanilla Bugs**

Fixes bugs in the base game. Every default name can be chosen: the game numbers its 185 male and 185 female names from 0 but picks a number from 1 (and never the last one), so Ago and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. A "%" in a villager's name can no longer crash the game: the game showed some names by using them as formatting instructions; now it copies them as plain text, and its text boxes no longer accept a typed "%". A like or dislike holding a negative number other than the game's own "none" (-1) is left out of the Details screen instead of being shown as "ants". The gold dust pouring sound plays: the game asked for it as "gold_dust_pour .ogg", with a stray space, so the sound file it ships (Sounds\gold_dust_pour.ogg) was never found and the game wrote "ldwSoundFx Missing File ->gold_dust_pour .ogg" to its log each time it opened; now it asks for "gold_dust_pour.ogg". The game no longer writes "String Table (sm.xml) malformed near id=\"eDemo\"" to its log each time it opens: it looked up the demo version's population message under the name "eDemo", which its text file calls "eTipDemo"; now it uses "eTipDemo" (the message is for the demo version only, is never shown in the full game, and has the same words either way). A villager's name is saved only to the villager it belongs to on the Details screen: the screen remembers which villager it filled the name box for, and Done or the arrows save the box only into that same villager; if the selected villager is not the one the box was filled for, the box is dropped and the right name is shown. A name you type is still saved to the villager shown. **Needs no other patch.**

- Patch ID: `vv5_fix_vanilla_bugs`

**Full Names on the Details Screen**

The Villager Details screen keeps a villager's whole name. In the base game its name box holds only 18 characters (fewer for wide letters) and, when the screen closes, writes what it holds back to the villager, so a longer name -- a last name, a numbered namesake -- was cut short for good. Now the box holds the 23 characters the game's name field has room for, is wide enough to show them, and copies the whole name back; typing a new name there allows 23 characters too. **Needs no other patch.**

- Patch ID: `vv5_details_full_names`

**256 Villagers (Experimental)**

Gives New Believers 256 villager slots (numbered 0 to 255) instead of 150 (believers, Heathens and Reanimate stand-ins share them, as in the stock game). The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Heathens, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 241 and adds 0-15 collection points, reaching 256 with everything; No Population Increase keeps the stock cap of 105, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - New Believers - Modded 256.exe' (in a 'Virtual Villagers - New Believers - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - New Believers - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - New Believers - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv5_population_256`

## The Origins upgrades menus

Each game's **Enable Origins Tech, Details, and Village-Wide Upgrades** patch
adds two menus reached from an **Upgrades** button. Every game uses the same
wording and the same shell, so the menus read identically across all five.

### Tech screen â€” `Origins Upgrades`

| Upgrade | Cost |
|---|---:|
| Time Warp - Advances the Village Clock | 50,000 |
| Island Event | 30,000 |
| Barrel of Babies | 75,000 |
| Tech Point Doubler | 500,000 |
| Food Point Doubler | 500,000 |
| Full Heal / Cure All | 30,000 |
| Grant Running to All Villagers | 1,000,000 |
| Grant Full Mastery to All Villagers | 1,000,000 |
| All Villagers are Exactly 18 | 1,000,000 |
| Complete All Collections | 1,000,000 |
| Reset All Collections | 1,000,000 |
| Equal Division of Labor (Includes Parenting) | 1,000,000 |
| Equal Division of Labor (No Parenting) | 1,000,000 |
| Clear All Skill Preferences | 500,000 |
| Check Highest Skill (Includes Parenting) | 1,000,000 |
| Check Highest Skill (No Parenting) | 1,000,000 |
| Change Appearance for All | 450,000 |

A New Home has no Collections rows, because it has no collections to complete
or reset. Every other row it shows uses the same wording as the rest.

**Time Warp** advances the village by **three villager years on slow, six on
normal and twelve on fast**. The amount depends on the speed because the game's
own clock does: one villager year takes 3 h 20 m of real time on slow, 2 hours
on normal and 1 hour on fast, so the same purchase buys more years the faster
the village is running. The confirmation names the cost, the speed and the
exact number of years before you commit, and the result says how many years it
advanced. The cost is written the same way as every other row -- **50,000**, not
50000.

While the game is **paused** it advances nothing at all, so it is refused with
a message and costs no tech points.

**Island Event** and **Barrel of Babies** are *queued* rather than fired the
instant you buy them. Each waits a few real seconds after you close the Tech
screen before it runs, so the purchase confirmation can be read first and the
event does not arrive underneath the menu you bought it from. The delay also
keeps a natural island event that happened to be due at the same moment from
consuming the one you paid for -- the failure that made a purchased Barrel look
like it had done nothing at all.

New Believers is the one exception today: its two rows still fire on the next
scheduler tick rather than after a delay.

While one of these events is still on its way, its row reads **Why not?** in all
five games instead of offering a second purchase. Clicking it explains why and
closes nothing -- so a second copy cannot be bought and cannot be charged for.

The wording differs between games, deliberately. Virtual Villagers 3 and 5
track a purchase directly, so they can say an event *has already been bought*.
The other three read a countdown that naturally scheduled events also write,
which cannot say who queued it -- so they say an event *is already queued and on
its way*, rather than claiming the player paid for something they may not have.

The same button appears when a **Barrel of Babies** cannot be delivered because
the village has no room for the three children it brings. That message says so
explicitly, and notes that a villager who has died still occupies a slot until
they are buried, so burying any remains may free the space. The two causes are
told apart on purpose: waiting clears a queued event, but waiting will not empty
a full village.

Earlier versions drew these rows as a disabled button reading *Unavailable*,
which said that the upgrade could not be bought without saying why or whether
waiting would help -- and, being disabled, the button could not respond to a
click at all.

**Barrel of Babies** delivers three children, so it is only sold when the
village has room for all three -- that is, when the population is at or below
its current maximum minus three. Above that it refuses and deducts nothing.
Room is measured in *occupied villager records* rather than in living
villagers, which is deliberately conservative: a record counts as occupied
whether the villager in it is alive, unborn, or a skeleton, so the check never
hands out a slot that is already spoken for. `docs/duplicate-purchase-guards.md`
records that reasoning, and the one measurement question still open about it.

Because the barrel is queued, the village can fill up during the wait. The room
check therefore runs **again at delivery**, and if there is no longer space the
barrel is *held* rather than spent: it stays queued and arrives once a slot
frees. You are never charged twice. A paid barrel is delivered as the game's
own barrel event at full strength, which is what makes it three children; it
leaves nothing behind that could change a later crate, sack or barrel.

That covers a barrel losing its room *during the queue delay*. It is not a
promise that every paid barrel always delivers three children: a separate,
still-unexplained short-spawn has been reproduced in a village with plenty of
free records, and `docs/duplicate-purchase-guards.md` records what is and is
not known about it.

**Equal Division of Labor** splits the village evenly across the jobs: each
job gets the same number of villagers as before, with males and females
balanced per job, and *(No Parenting)* leaves Parenting out. Since v1.35.70
**who gets which job follows their skill progress**: each villager is placed
in the job whose skill they have made the most progress in (highest skill
value first; a mastered skill counts as the most progress); if that job is
already full, their next-best job, and so on. Villagers with no progress yet
(newborns, for example), ties, and anyone left over are placed at random in
the seats that remain, so the counts per job are always equal.

**Clear All Skill Preferences** (500,000, half of Equal Division) unchecks every
villager's skill preference (the job checkmark on the Villager Details screen),
so each villager chooses their own work again, as in the stock game. Skills
themselves are not changed.

**Check Highest Skill** sets each villager's skill preference to the skill they
have made the most progress in. *(No Parenting)* leaves Parenting out of the
comparison. Ties go to the first skill in the Skills list order (Farming,
Building, Research, Healing, Parenting, and Devotion in New Believers).
Villagers with no progress in any skill yet keep their preference. It costs
the same as the matching Equal Division row.

All five rows touch the same villagers as Equal Division of Labor: A New Home
skips the Golden Child, The Secret City skips the Tribal Chief (who cannot hold
a preference) and New Believers never touches Heathens. Clear All Skill
Preferences and Check Highest Skill deduct nothing when no checkmark would
change, and cost 0 like every other row while Story / Cheat Upgrades makes
upgrades free.

**Corrupted skill values are reset.** A skill the game itself can never
produce -- below 0, above 100, or (The Tree of Life and New Believers) not a
number or infinite, as a memory editor or a damaged save can leave it -- is
reset by Grant Full Mastery (both rows), Equal Division of Labor, Clear All
Skill Preferences and Check Highest Skill before they read the skills: below 0
and not-a-number become 0, above 100 becomes 100. Valid values are never
touched. The result says *Reset N corrupted skill values.*, and a reset on its
own costs nothing. Repair Saves & Logs can do the same for a closed save.

v1.35.70 also fixed The Lost Children's Equal Division of Labor, which used the
wrong job numbers: its *Building* share was really given Parenting, its
*Research*, *Healing* and *Breeding* shares got Healing, Research and Building,
and *(No Parenting)* gave villagers Parenting and never Building. It now uses
the game's own job numbers.

Results that count villagers name the number and the reason, and read correctly
at one: *"Skipped over 1 villager. Reason: already likes running."*

Every row that completes says so, including Complete and Reset All
Collections, both Equal Division of Labor rows and Change Appearance for
All. In The Tree of Life those five used to apply silently -- the purchase
worked, but nothing confirmed it.

### Villager Details screen â€” `Villager Upgrades`

| Upgrade | Cost |
|---|---:|
| Grant Youth (-35 years, min age 5) | 50,000 |
| Grant Full Mastery | 100,000 |
| Grant Running | 40,000 |
| Set Age to 18 | 50,000 |
| Change Appearance | 5,000 |

**Change Appearance** and **Change Appearance for All** offer every head and
body the game ships, for both sexes: **20 each in A New Home** and **30 each in
the other four**. Both choosers offer the same range, so anything you can set on
one villager you can set for the whole village.

**Change Appearance for All** adds four village-wide groups on top of that pair
of per-sex selectors, and all five games now carry the same set:

- **Village-wide Heads** -- *Off (use the Head selectors above)*, *Random (by
  gender)*, or one hair bucket for everyone: *All Black Hair*, *All Brown
  Hair*, *All Red / Ginger Hair*, *All Blonde Hair*, or *All Other Hair /
  Styles*. Picking a head for the whole village raises the same genetics
  warning the per-villager chooser does.
- **Village-wide Bodies** -- *Off (use the Body selectors above)* or *Random
  (by gender)*.
- **Village-wide Single Mask Color** -- give every villager the same mask, or
  *None (remove all masks)*.
- **Mask Distribution (all villagers)** -- *Off*, *VV5-style* (1 Chief, 4
  Purple, up to 7 Red, up to 10 Orange, rest Blue), *Random*, or *Equal Colors*
  (all five colours, balanced between the sexes).

A village-wide group set to **Off** leaves that attribute alone and greys out
nothing; set to anything else it overrides the matching per-sex selectors,
which are disabled while the override is active so the two cannot disagree. The
single-colour and distribution mask choices are one exclusive set, so a colour
and a distribution can never both be selected.

Neither chooser charges for a change it did not make. **Change Appearance**
costs nothing if you press OK on the head, body and mask the villager already
has. **Change Appearance for All** counts what actually changes rather than who
was looked at, so it charges nothing when every villager already matches your
selection -- including when you set options only for a sex your village does
not currently have.

### Buying, removing, and the green checkmarks

Choosing a row asks `Do you want to buy ... for ... tech points?` and applies
nothing unless you confirm. If an upgrade would change nothing, the game says so
and **no tech points are deducted**.

**Tech Point Doubler** and **Food Point Doubler** are the only two upgrades you
own rather than perform. Once bought, their button changes from **Buy** to
**Remove**, and removing one takes effect immediately and issues no refund.

A small green checkmark appears on **exactly two rows and nowhere else**:
**Tech Point Doubler** and **Food Point Doubler**, and only while that doubler
is owned in the current save. Nothing else is ever marked -- the Villager
Details screen shows no checkmarks at all, and a row that would currently do
nothing tells you so in its result instead.

The checkmark never means a row is unavailable. Every visible row stays
clickable, and a row that changes nothing says so and deducts no tech points.

**Switching save files clears some upgrade state, and the details differ by
game.** Two kinds of state are affected when you load a different save slot:

- **Doubler ownership.** A doubler bought in one village used to stay owned in
  another that never paid for it. A New Home and The Lost Children keep that
  flag on the village itself, so they were never affected, and returning to a
  village restores exactly what it bought. The Secret City, The Tree of Life
  and New Believers keep it in memory shared by every save, and that memory is
  not part of the saved village, so there is nothing to reload: loading a
  different village now clears it. In those three, a doubler stays owned only
  until you switch villages -- come back to the village that paid for it and
  you will need to buy it again, the same as after restarting the game.
- **A queued Island Event or Barrel of Babies.** In all five games a pending
  event no longer follows you into another save, where its row would have read
  **Unavailable** and the event could have been delivered to a village that
  never bought it. A New Home, The Lost Children and New Believers already
  behaved this way; The Secret City and The Tree of Life now do too.

Saving does not trigger either reset -- only genuinely changing slots does, so
a doubler you own survives an autosave.

Both menus close with **Cancel** or the Esc key, and each shows
`Press ESC to exit this menu.` once.

### Buying the Doublers

Both Doublers are buyable in **all five games** at 500,000 tech points each. An
owned one can be removed for zero cost with no refund, and bought again
afterwards at full price.

An earlier release briefly held new purchases in A New Home, The Secret City and
The Tree of Life while their exact-build provenance was being checked. That hold
was lifted in v1.34.14 -- the gate that set the rows "Unavailable" is gone, and
those three games buy, remove and repurchase like the rest.

### The Secret City: Magic level and research points

The audit behind that decision also established what Magic actually does to
research. Magic level 1 or higher adds a deterministic flat `+1` tech point to
each completed research callback. It does not change research speed, duration,
the base award, the RNG, or Research-skill gain. Native research adds the base
award, the optional quarter-base bonus, the Magic `+1`, a timed `+1`, and an
independent RNG `+1`, in that order.

### The Lost Children: known crash

**A player reported that both Time Warp and Food Point Doubler crash The Lost
Children immediately after the purchased/success dialog is displayed.** That
records the observed trigger only; it does not establish whether the charge or
the action persisted.

**A later playtest did not reproduce it.** The player has since confirmed that
Time Warp and the Food Point Doubler no longer crash The Lost Children. That is
one clean run against one report, so it is recorded as what it is -- the trigger
failing to reproduce -- rather than as a proven fix. The `.shr` repair described
below is the most likely reason, but nothing here establishes that it was the
cause.

Nothing is disabled because of it: the VV2 Origins patch and its dependent
village-wide upgrade are selectable, and its Doublers buy, remove and
repurchase like every other game's.

The crash audit did find `.shr` raw-offset versus virtual-address confusion in
the VV2 builder, displacing some helper and header references by `0x2000`. The
isolated VV2 builder now corrects those runtime VAs, extends the `.shr` virtual
size and execute flags, and maps the payload's `.rdata` tail as executable.
Static render and regression checks pass. That is not yet proof the reported
crash is gone -- only a playtest can establish that. Every unrelated VV2 patch
is unaffected.

Since then the machine's actual crash records have been examined, and they do
narrow the question, though they do not close it. Of 61 recorded Lost Children
crashes, the two most frequent sites happen on the **unmodified** executable as
well as the modded one. That executable contains none of this project's code, so
those two cannot be caused by it. Two further sites appear only on modded builds,
at the two instructions immediately after the mask compositor hook; both were
checked in a disassembler and the hook replays the instructions it displaced with
the correct registers, while its sweep stays inside the structure it walks. That
rules out the two ways the hook could have caused them directly. It does not
prove the patch is uninvolved by some other path -- a hook can corrupt state that
stock code dereferences later -- so this narrows the question rather than
answering it.

The full measurements, including what would falsify them, are in
[docs/crash-dump-findings.md](docs/crash-dump-findings.md).

### A New Home: a Time Warp crash, once

A player bought Time Warp in A New Home and the game crashed on returning to the
village. It has happened once, with a full memory dump, and it has not recurred.

The fault is a null pointer dereferenced without a check, in game code this
project does not patch. The bytes that fault are byte-identical to the
unmodified executable, the call reaches them through a vtable slot no patch here
touches, and no code from this project appears anywhere on that path. The
patcher's file copying is also not implicated: it copies the game folder whole
and verifies every file by size and checksum, refusing to continue on a
mismatch.

That is not the same as this project being ruled out, and it is not written as
though it were. Buying Time Warp runs this patcher's code before the game
returns to the village, so it remains possible for that to leave the game in a
state its own code then trips over. Nothing measured so far excludes it.

What is **not** established is which sequence of events leaves the game in that
state. Because that is untraced, no fix is proposed -- a change aimed at a cause
nobody has pinned down could not be shown to work, and might hide the next
occurrence. Two plausible explanations were investigated: one was ruled out from
the game's own code, and the other could not be settled from a crash dump alone,
because a dump records a single instant. The write-up records exactly what each
one rests on, so neither is re-proposed as settled.

If it happens to you, the crash dump is what makes it traceable. The measurements
are in [docs/crash-dump-findings.md](docs/crash-dump-findings.md).

### Status

These menus are verified by build-level tests -- exact bytes, dialog wording,
and the purchased/success dialog paths -- and the patcher refuses to write an
executable whose bytes it cannot account for. They have had far less **playtest**
coverage than the ordinary patches, so **runtime** confirmation in a real village
is still the last step for many rows. The VV2 **crash** above did not reproduce
in a later playtest; the A New Home one happened once and its trigger is still
untraced.
Whatever happens, the unmodified original EXE and folder are always left
untouched beside the modded copy.

## Population safety

### New Believers: Heathens and physical slots

Heathens already occupy records in New Believers' 150-record villager pool. Converting one changes that existing record from Heathen to believer; it does not create an additional villager record. The population patch therefore measures physical slot demand before allowing births: every active record counts, including unconverted Heathens and corpses that the game has not released yet, and nursing babies reserve the records they will need later.

This means births can temporarily stop below 150 displayed believers while Heathens remain, but conversions are still safe and can continue at the physical ceiling. After every Heathen has been converted and old corpse records have cleared, the full 150 slots can be believers.

## Safe twins and triplets at the ceiling

All five stock games test the population limit once before choosing a singleton, twins, or triplets. Without an additional guard, a multiple birth at maximum minus one can report maximum plus one or maximum plus two, even though no corresponding villager records remain.

All three public modes apply a slot-saturation guard at the game's physical
boundary. No Population Increase leaves the stock cap, collection behavior,
and progression untouched; Collection Progression and Immediate Fixed retain
their documented cap behavior. The safety layer is allocation-only:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array. New Believers uses physical slot demand rather than only its displayed believer count, so still-active Heathens, corpses, and nursing babies cannot make the final multiple birth overbook the shared pool.

### Island Event population safety

All five games also contain Island Events that add villagers. The patcher guards every identified direct population-adding outcome: repeated allocations stop when the selected physical pool fills, and VV4/VV5 Abandoned Infants is reduced from six babies when fewer than six physical slots remain. VV3-VV5 use their verified 150-record boundary, or 256 in a build with 256 Villagers (Experimental). Events that remove villagers are unchanged. VV5 conversions and The Defector are unchanged because they reclassify existing records instead of allocating new ones.

### No villager without a free record

A corpse keeps its villager record until the game removes it, and so do The
Tree of Life's ghosts and New Believers' Heathens, and every baby still owed
needs one. So "the population is below the cap" never meant "a record is
free". In every population mode, including No Population Increase, and at 256
in the 256 Villagers builds, the safety layer makes every creation ask the
records themselves, and nothing is spent when there is none:

- A delivery waits, with the pregnancy kept, until its whole litter fits.
  The original games cleared the pregnancy and lost the baby.
- The room check behind conceptions, barrels and island events counts every
  occupied record plus every baby still owed.
- A New Home's Golden Child puzzle fires only with a free record. With none,
  the original game made the Golden Child in a record past the end of the
  table, where nobody could see him, and spent the mother's pregnancy.
- A New Home's Mysterious Face, The Lost Children's Strange Request, Savage
  Child and Silver Mirror, and The Secret City's Mysterious Vial and Crystal
  of Reflections are offered only with room. The Crystal checks before it
  changes anyone's likes.
- New Believers' Reanimate is refused, with nothing spent, when no record is
  free, and the gray message bar says "There's no room in your village to
  revive this person." The original game crashed.
- Twins and triplets at conception follow the free records. Earlier patcher
  builds read A New Home's lifetime Babies Made count here, so a village that
  had made 256 babies never had twins again.

## Requirements

The patcher runs from source through the bundled launcher. It needs nothing
beyond a normal Python install.

| Requirement | Detail |
| --- | --- |
| Windows | The five games are 32-bit Windows executables and the patcher writes Windows PE files. `Launch Virtual Villagers Fun Patcher.bat` is a Windows batch file. |
| Python 3.10 or newer | Download from [python.org](https://www.python.org/downloads/). During setup keep **tcl/tk and IDLE** ticked, which is the default: the patcher's window is built with `tkinter`. |
| No extra packages | The patcher uses only the Python standard library. There is nothing to `pip install`, and no internet connection is needed to patch. The **Check for updates** link is the one feature that reaches the internet, and it is entirely optional: it just opens the patcher's GitHub page in your browser, and everything else works with no connection at all. |
| An original game | The free downloads from [ldw.com](https://ldw.com), installed normally. Only those builds are supported. |
| Free disk space | The patcher copies each game whole rather than editing your original, so each modded copy needs about as much space as the game folder itself: roughly 25-85 MB per game, or about 300 MB for all five. |

The launcher tries `py -3` first and falls back to `python`, so either the
Python launcher or `python` on your `PATH` will do. If a console window opens
and reports that Python was not found, install Python and try again.

Your original game is never modified. Every patch is written into a separate
`(Game name) - Modded` folder, so you can delete that folder at any time and
keep playing the original.

The top-right of the window shows which build you are running, next to a
**Check for updates** link. Clicking it opens the patcher's GitHub page in
your browser. It deliberately makes no judgement about which build is newer: the
GitHub page already shows the latest release, and your build version is printed
directly beside the link, so the comparison is yours to make and nothing here
can hang or report a wrong answer.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a population mode.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Optionally choose a **Modded output location**. This is the parent folder that
   will receive each generated `(Game name) - Modded` folder. Leave it blank to
   keep the original sibling-folder behavior.
7. Validate, dry run, or create the copied-and-modified game folder set.

While the patcher is working -- loading its patches at startup, validating, dry
running, or copying and patching a game folder -- it shows a **Please wait**
window with a progress bar. Copying a whole game folder takes a moment; the
window means it is working, not stuck.

The window has two tabs: **Patches** (the population mode, the patches, the output location and the One Game / All 5 Games tabs that create the modified games) and **Tools** (everything else: backing up and restoring saves, renaming a tribe, checking and repairing logs, the Family Tree Maker and the Village Matchmaker -- for the game chosen on the One Game tab, or any of the five).

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The One Game tab includes clickable **Open Vanilla EXE Folder** and **Open Modified EXE Folder** links. All 5 Games provides matching Vanilla folder and Modified folder links on every game row. After patching, a compact confirmation window provides clear clickable links to both folders for every completed game.

**Back Up Saves** copies your modded games' saves, in all five games. On the **Tools** tab, click **Back Up Saves** (the game chosen on the One Game tab), **Back up saves** on any game's row, or **Back Up Saves (All 5)...** for every game. The patcher finds each game's save folders in `Documents\LDW` (the Documents folder Windows reports, so a Documents moved to OneDrive is found): `(Game name) - Modded`, `- Modded 256` and any other `- Modded...` folder, and lets you tick which to back up. Each chosen folder -- the `.ldw` saves, the `Virtual Villagers Fun Patcher Logs` and `Virtual Villagers Fun Patcher Data` folders and everything else in it -- is copied into a new `Backups\Backup YYYY-MM-DD HH-MM-SS` folder inside that save folder, and every copied file is checked against the original by size and SHA-256. An existing backup is never replaced, and no patcher feature (Start Over included) reads, moves or deletes anything in `Backups`. If the game is running it is paused for the copy and then resumes by itself; it is never closed. These games save only when you quit them normally, so a backup taken while a game is running holds the village as of its last save. If the game cannot be paused, nothing is copied and the result says why. The result window reports the file count and size and has an **Open Backup Folder** link.

**Restore Saves...** (Tools tab, and **Restore saves...** on every game's row) lists that game's backups newest first, with the date and time, the variant it came from, the village in each save slot and the size. Restore **the whole save folder** or **one save slot only**; a confirmation lists exactly which files will be replaced, added and removed. The game must be closed -- quit it from its own menu first, because a running game writes its village over the restored save when it quits -- and the patcher never closes it for you. Before anything changes, the current saves are backed up as `Backup <date> (before restore)`, so every restore can be undone; each file is put in place only after its copy is checked against the backup, and on any failure every file already changed is put back. A one-slot restore touches only that slot's saves (`<save>N.ldw` and its two older generations `N+20` and `N+40`) and that slot's patcher files (named `Save N`, or whose log header says `(Save N)`); it is refused, with the reason, when the backup and the current saves differ in a file that belongs to no single slot, such as the game's shared slot-0 save. **Delete Backup...** removes a chosen backup after asking; a restore never changes or deletes a backup.

**Rename Tribe** changes a tribe's name inside its save, in all five games and every Modded save folder (including `- Modded 256`). On the **Tools** tab, click **Rename Tribe...**, **Rename tribe...** on any game's row, or **Rename Tribe...** below them; pick the game, its save folder and the tribe (each slot is listed with its current name), then type the new name. The game's own limit applies, with a live character counter: **31 characters in A New Home and The Lost Children, 19 in The Secret City, The Tree of Life and New Believers** -- the most each game's own name entry stores -- and only characters the game can take (A New Home and The Lost Children cannot draw `# $ % & ( ) * + ; < = > @ [ \ ] ^ _ { } | ~`). A name that breaks the rule is refused, never cut short. A name wider than the game's Change Tribe button (181 pixels, or 130 in the later three) is allowed, as the games make such names themselves; the window notes that that one screen will show it shortened. **The game must be closed** (it saves when you quit, which would put the old name back); a running game is refused and never closed. Before anything is written the save folder is backed up into `Backups\Backup YYYY-MM-DD HH-MM-SS (before rename)`, which **Restore Saves...** lists like any other backup, so a rename can be undone. The name is changed in the slot's save, its older generations and the slot list, each file written to a temporary file, swapped in and read back; any failure puts every file back. The patcher's logs keep following the village: nothing already written is changed, and each of its logs gets one line, `Tribe renamed from <old> to <new> on <date>`, which the logs and Start Over follow -- the renamed village is the same village, so its logs, statistics, stews and elders carry on. The patcher's own data that names the village moves with it, written the same safe way after the same backup: the slot's answered questions and other Repair decisions (so no answered question is asked again, even for a village with no logs yet), The Lost Children's `ElderTotems.dat` (so its totems stay bound), and the Family Tree Maker's saved trees of that tribe.

**Check Saves & Logs...** shows, for one village, whether every log and data file the patcher keeps agrees with its save, in all five games and every Modded save folder (including `- Modded 256`). On the **Tools** tab, click **Check Saves & Logs...**, **Check logs...** on any game's row, or **Check Saves & Logs...** below them; pick the game, its save folder and the tribe. It runs the read-only checker `scripts/vvfp_consistency_check.py` (see [the cross-check](docs/first-load-cross-check.md)) inside the patcher and shows its report in a scrolling window: each file with **OK**, **WRONG**, **NOTE** or **UNCHECKED** and the details, then a summary line. It only reads -- nothing is written, moved or created, and the Backups folder is never read -- so it works while the game is running.

**Repair Saves & Logs...** (the same three places, **Repair logs...** on the rows) is your go-ahead for the game to repair that village: it repairs nothing itself, and the next time you **play** the village the game repairs everything confirmed wrong **without asking** -- A New Home's parents as soon as the village has settled, the rest at its next save (the save the game makes when you close it, at the latest) and anything still left right after that save -- each file backed up first (`<file>.before-v1.35.58-repair`) and every change listed in the Repairs log; then the go-ahead is used up. Close the game normally from its own menu so the repairs are saved. **The game must be closed** when you click it; a running game is refused and never paused or closed. The logs are checked first and the result shown -- if nothing is found wrong the window says so and offers to go ahead anyway -- then the save folder is backed up into `Backups\Backup YYYY-MM-DD HH-MM-SS (before repair re-arm)` (listed by **Restore Saves...**), that slot's "already checked" markers are cleared (`Virtual Villagers Fun Patcher Data\Cross-Check\Virtual Villagers 1 Cross-Check - Save N.dat` in A New Home, `...\Deaths\Virtual Villagers G Graves Logged - Save N.dat` and `...\Arrivals\Virtual Villagers G Arrivals Recorded - Save N.dat` in every game, `...\Births\Virtual Villagers G Births Recorded - Save N.dat` in The Lost Children to New Believers) and the go-ahead is written (`...\Cross-Check\Virtual Villagers G Repair Approved - Save N.dat`; Start Over deletes it with the village, and **Check Saves & Logs...** shows it while it waits). No log, backup or other data file is removed, and nothing is written twice: each part of the repair counts what the logs already hold before it writes.


**Move Old Files to New Names...** (a button in the Repair Saves & Logs window, v1.35.65) moves what in the chosen save folder is still under the names an older patcher used (Deaths, Repairs, Logs\Genealogy, Genealogy Edits, Log Words, Cross-Check, Parentage Records, Village Roster) to the new ones -- **only do this once every game that plays this save is patched with v1.35.64 or newer**, since older patches look only under the old names (a game the patcher can tell was patched by an older version is refused). It lists everything first and asks, refuses while the game is running, backs the save folder up (`(before repair re-arm)`), combines anything kept under both names as the patcher already reads it (Deaths and Repairs logs each record once, the smaller like / dislike word boundary, otherwise the file written last; a Repair approval under both names is kept under neither), puts whatever it replaces in `Copies Made Before Repairs` (nothing is deleted but empty old folders), and lists it all in the Repairs log. Backups, Tribe History and Tribe Population are never touched.

**Repair Saves & Logs' checklist (v1.35.61).** Repair Saves & Logs first shows what it can do for the village, each line ticked or unticked by you: the game's own repair the next time you play (above); correcting like / dislike words an older patcher wrote with the wrong list; and adding to records written by an older patcher what they lack -- the **Sex** line, the **Special villager** title (Tribal Chief, Retired Heathen Chief, Heathen roles, Former Heathen, Golden Child, Esteemed Elder, Scholar), the **Custom title**, the **Mask** and, on Birth records, **Born as: Single birth / Twin / Triplet**. Each is decided from the save, the patcher's own data files and the logs themselves wherever they settle it -- a record's own skills or grave, the latest Village Population page, the mother's Conception record -- and **whatever they cannot settle is asked**: **Answer the questions...** lists each one with its own choices (a title or mask "from which Village History snapshot on", how many babies were born together, a sex nothing records); **Don't know** and **Only from now on** add nothing. Check Saves & Logs lists the same things as NOTE lines. Every log is copied beside itself first (`<file>.before-v1.35.61-repair`, never replacing a copy), rewritten through a temporary file, and the additions are listed in the Repairs log.

**Give villagers last names** (the same checklist, unticked until you **Choose...**): every villager the save and the logs know -- the living, and the dead, disappeared and gone in every log -- gets the last name you pick after their name -- **Last names come from** **From the mother**, **From the father** (the default), **Equal mother/father** (a 50:50 chance of either parent's for each child, the same pick each time), **Random from list** (one of the game's 50 for each villager), **Choose from list** (each villager keeps the last name they have until you pick another); each villager's own list has **(custom last name - type here...)** to type one of your own, and a name too long for the game is marked and never written; a villager whose name has a second word that is no known last name (one typed in v1.35.62, or "Big Bob" set with Cheat Engine) gets a tick box, **'Bob' is a last name** -- ticked by default; untick it and the words stay one first name ("Big Bob Akikai"), and the answer is kept with the village; type any villager's own last name in their box (**Chapa Chapstick**), and their descendants inherit it by the rule -- a family is a couple and their children, so each child carries a parent's name, and a founder (one of the village's first villagers, with no recorded parent) gets a last name of their own, their family's from the game's list unless another such villager has it, while a villager the logs say arrived through an event (a newcomer, the Barrel O' Babies) has **(no last name)** unless you give one; then change any one, from its list (the father's and the mother's come first), by typing your own, or to none. **Random last names...** gives villagers random last names from the game's own list -- **Only villagers who have no last name** (the default) or **Everyone** (replaces the last names they have, after a warning and a confirmation), **Fully random per villager** (the default) or **Each family shares one random name** (children take their parents' by the village rule) -- with a **Seed** you can type and a **Reroll** button; the names show in the list at once, and every villager whose last name will change reads in red bold (normal again if you set the box back), so you can edit any row before pressing OK; a name that would not fit the game's name field is never given, Heathens are left alone, and a villager whose earlier record already gives a last name is asked about, never overridden. It is given by the same safe route as the other choices (backup first, refused while the game runs, the save and every log and file together). A parent's last name is the one their name already carries, or the one being given them now, so names pass down the generations -- **in the save and in every log**, so the logs keep matching the save. Everything the patcher keeps that holds the name follows: the children's father and mother names in the save (The Lost Children to New Believers), the masks, custom titles and New Believers' Former Heathens, A New Home's parent records, the Unaccounted Villagers roster, the statistics roster and the Village Elders, and every record that names the villager by name, head and body. A villager who has died is renamed on their grave too -- in the save and in the patcher's grave files; a grave the records cannot tie to one villager keeps its name, and you are told which. A record with the old name but other looks (before a Change Appearance) is asked about. The game must be closed; the save folder is backed up first (`Backups\Backup ... (before last names)`), every file is swapped in through a temporary file and read back, and any failure puts every file back as it was.

**Each villager's own rule** (v1.35.66, a button beside **Last names come from**): a living villager can pass their last name to their children by a rule of their own -- **From the father**, **From the mother**, **50:50** or (v1.35.79) **Random last name from the list** -- instead of **Use the village rule** (the default), so one villager's name need not spread through half the village. With **Random last name from the list**, each child is given a last name drawn at random from the game's own list of 50 at its birth (every name equally likely; twins and triplets each get their own draw); Repair keeps a list name such a child already carries and gives one with none a random one. An older patcher or Last Names DLL ignores that choice and uses the village rule. A villager whose own rule your choices will change reads in red bold, both in this window and in the last-names window (normal again if you set it back; an own rule that is not changing is shown normally). At a birth, when only one parent has a rule of their own it is used; when both do and they agree, theirs; when they disagree, or neither has one, the village's rule. A villager is known by their whole name, head, body and sex, so two living villagers who share all four cannot have one (number the duplicate names first); renames (last names, numbering, restored names) and a recorded change of looks carry the rule along, a father who dies before his baby is born keeps his for that birth, and the dead keep none. The rules are kept with the village's rule in `Virtual Villagers Fun Patcher Data\Last Names`, even when no name changes; the game must be closed.

**Number duplicate names** (the same checklist, unticked): villagers who share a name are numbered -- the first Soda to appear in the logs becomes Soda I, the next Soda II, and so on -- **Oldest first (order of appearance)**, as older villagers appear first -- unless you pick **By age now, oldest first** or **By age now, youngest first** beside it -- the dead, disappeared and departed too, so a living villager's number counts the namesakes before them. Each is renamed **in the save and in every log**, as a parent too, and in everything the patcher keeps, as **Give villagers last names** does, after any last names you are giving. The dead are renamed on their graves too -- in the save and in the patcher's grave files. Namesakes who also look the same cannot be told apart in the records, so they keep their names (and the patcher says so). The game must be closed; the save folder is backed up first (`Backups\Backup ... (before numbering names)`).

**Reset corrupted skill values** (the same checklist, v1.35.70, all five games; ticked only when the save holds one): a skill value no game can hold -- NaN, infinite, below 0, or above the games' maximum of 100 (whole numbers in A New Home, The Lost Children and The Secret City; decimals in The Tree of Life and New Believers) -- is reset: NaN, infinite and below 0 to 0, above 100 to 100. Every other value, 0 and 100 included, is left exactly as it is. Every villager the save loads is looked at, a body not yet buried and New Believers' Heathens too (named as Heathens). The game must be closed; the save folder is backed up first, a copy of the save is kept in Copies Made Before Repairs, and the Repairs Made log names each villager, skill and old -> new value. Check Saves & Logs lists them as a NOTE.

**Give Esteemed Elders Totems Retroactively** and **Fix Rare Villager Turning Into Totem** (the same checklist, The Lost Children only; each ticked only when the save has something for it). The game makes an Esteemed Elder's totem as a new villager record when the elder masters three skills; with every one of the 256 records in use it had no record for it, so some elders never got one. The first row gives each Esteemed Elder without a totem (a living elder in the save, or one the Deaths log names as an Esteemed Elder) a new totem of a random colour beside the campfire, made as the game makes one. It needs a free record for each, after the babies still on the way: a full village is never made room in by deleting or overwriting anyone, and the elders who cannot be given one now are listed with the reason, in the confirmation and in the Repairs Made log. The second row takes the totem mark off a living villager who carries it (the game never makes a living totem), changing nothing else. A totem that no Esteemed Elder matches, and an elder whose only possible totem has a different full name (a rename), are asked about, never guessed. The game must be closed; the save folder is backed up first, a copy of the save is kept in Copies Made Before Repairs, and the Repairs Made log lists every change. The cause is fixed too: an elder and the totem now wait for a free record (every build), and Fix Vanilla Bugs stops a totem from being buried and a twin, triplet or Silver Mirror double from inheriting the mark. With **Esteemed Elders' Totems Use No Villager Records** a new totem goes into the save's `ElderTotems.dat` instead, needs no free record, and a totem already there counts as the elder's.

**Move Totems Out of the Save**, **Put Totems Back Into the Save**, **Change Totem Colour...** and **Give Esteemed Elders their totems automatically** (the same checklist, The Lost Children only). The first moves every totem statue in the save into the save's `ElderTotems.dat` with the game closed (as the game does when it loads with the patch; a statue already in the file is not doubled, and a living villager carrying the mark is never moved). The second writes each totem in the file back into the save the way the game keeps a totem, as many as the free villager records allow after every baby still owed, and keeps the rest in the file, saying so -- do this before removing the patch. **Change Totem Colour...** shows the eight faces of the game's own `totems.png` (from The Lost Children's folder chosen in the patcher), numbered 1 to 8 from the left under each picture, and gives every ticked totem that colour in one go, wherever each is kept: tick one, several, or use **Select All** / **Select None** (for decorating the village); one backup and one Repairs Made record list each totem's old and new colour. The tick box is this village's setting: with it on and **Esteemed Elders' Totems Use No Villager Records** installed, every Esteemed Elder without a totem is given one **automatically, during play** -- when the village loads and after every elder check the game makes -- and an elder who passed away without one (from the Deaths log, which Check and Repair Saves & Logs list in the save's `PendingElderTotems.dat`) is given one the next time the village loads, beside the campfire; Repair Saves & Logs also gives them without the extra confirmation. One that may already have a totem (the same looks, or the same first name, unless a recorded rename says it is theirs) is never given a second: Repair Saves & Logs asks about it. The game must be closed; the save folder is backed up first, copies are kept in Copies Made Before Repairs, and the Repairs Made log lists every change.

**Check logs automatically** (a tick box beside those links on both tabs; **on** by default, and remembered; the patch selection buttons leave it alone) is written into every game you create from then on -- a game already created keeps its own setting until you create it again. **Off**, the games never check or ask anything while you play: use **Check Saves & Logs...** and **Repair Saves & Logs...**. **On**, the game checks each village silently a few seconds after it loads and, only if something is confirmed wrong, asks **Repair** or **Not now** when you **close the game** -- after its own save, never while you play. **Repair** repairs everything found there and then (backed up first, listed in the Repairs log); **Not now** changes nothing, and you are asked again the next time you close the game after playing that village. The question is about the village you played last, and if nobody answers within five minutes the game simply closes, as with **Not now**. The question ends by saying how to stop these checks: untick **Check logs automatically** in the patcher and patch the game again. On the command line it is on by default; `--no-check-logs-automatically` turns it off. See [the cross-check](docs/first-load-cross-check.md).

**Family Tree Maker...** (Tools tab, **Family tree maker...** on every game's row, and below them) draws a village's family tree, in all five games and every Modded save folder: who descends from whom, read from the save and the patcher's logs, and each villager's generation -- the founders are generation I, a villager who arrived later is in the generation they first appear in, and a child is one below their younger parent. Pick the game, its save folder and the tribe, and the game's folder so each villager shows their own head (the Change Appearance menus' front view). Every villager is numbered, generation by generation; each portrait says their name, age in game units and years, and *(deceased)*, *(disappeared)* or *(left the village)*; a square is a male, a circle a female, a diamond an upcoming child; twins and triplets hang from a triangle. **Every unrelated villager has a colour of their own, and each pairing has one colour** for its whole connector -- the line joining the two parents, the line down and the line joining their children -- which their children's portraits share. **Positions** are *dynamic* (each family under its parents, stepping down a row when crowded, as in a hand-made tree), *one straight row for each generation*, or *packed* by families or by generations (as tightly as you set, up to portraits touching), with at most as many portraits in a row as you choose; lines go round the portraits, or straight behind them if you tick **Lines run behind portraits**. The editor (**Help (F1)** lists every control): click a villager to select them (Ctrl+click adds, Shift+click a run, Ctrl+A everyone, Shift+drag a box); **drag anything to move it** -- villagers (every selected one together, their lines following), the title, subtitle, Key, generation labels and headings -- and right-click it to put it back; **right-click anything to change its colour** (with several villagers selected, all of them at once); put any villager in another generation, or move them left or right along theirs (the Selected tab; the numbers follow, and the genealogy report keeps the records' generations); line things up with **smart guides** (snap to other villagers' and pictures' edges and middles, and the middle of the tree), **snap to grid** (with a grid you can show) and **Align** (lefts, centres, rights, tops, middles, bottoms, centre on the tree, space evenly) -- hold Alt to drag freely; drag empty space to move around; the mouse wheel or **+** and **-** zoom; F4 hides the side panel, F11 is full screen. Retype any portrait or generation label, give special villagers a coloured border with its name in the Key (the **Special Marks** tab: ready-made Tribal Chief, Esteemed Elder, Scholar, Golden Child, Favourite, Heathen and Founder, or your own), choose any font on the computer for any words, pick a background colour, gradient, ready-made picture from any of the five games or your own picture (with its opacity), and add **stickers** -- any picture, the games' logos -- and **text boxes**, then move, resize and rotate them with PowerPoint-style handles, flip and fade them, and right-click them to layer (bring forward, send backward...), reset or remove them; **drag any piece of a line** to slide it, its joined pieces following and its ends staying on their portraits; backgrounds, logos and pictures are chosen from thumbnails, and every font from a list written in each font. Ctrl+C, Ctrl+X, Ctrl+V (a sticker, a picture copied from anywhere, picture files copied in File Explorer, or words, which become a text box), Ctrl+D, Ctrl+Z, Ctrl+Y, Ctrl+S, Ctrl+B / I / U, Delete, F2 and the arrow keys work as in any Windows program. **Save to Save Folder** (Ctrl+S) saves the tree as an editable tree file (`<tribe> (Save N) Family Tree.vvtree`) in the save folder's own `Virtual Villagers Fun Patcher Family Trees` folder, to be worked on later (**File, Open Tree File...** opens one), and closing the editor asks *Save changes to the tree before exiting?*; **Export as Picture...** (Ctrl+Shift+S) saves a PNG or JPG anywhere. Your edits are kept in `Virtual Villagers Fun Patcher Data\Family Tree Edits\Virtual Villagers G Family Tree Edits - Save N.json`; the tree's web page, its picture and the genealogy report (everyone by generation, and everyone in order of appearance) are written to `Virtual Villagers Fun Patcher Family Trees\Reports`. **Nothing in the save or the logs is changed**, unless **Number duplicate names** asks to number namesakes there too and you say Yes (the save folder is backed up first).

More in the editor: **portraits** come in 54 shapes (squares, rectangles, circles, ovals, hearts, stars, polygons and arrows, and drawn ones: flower, butterfly, clover, spade, leaf, shells, hibiscus, sand dollar, starfish, Monstera leaf, turtle shells, mermaid tails, fish, an ocean wave, a ship's wheel, a coconut, an anchor, a bunch of bananas, a paw print, a feather, a branching coral, a sea fan, a brain coral, a beetle), drawn at their own proportions with light **detail lines** inside them, and with thin, thick, extra thick, dotted, dashed or dotted-and-dashed borders or a **special border** that follows the shape -- a **braided rope**, or a **vine** with leaves, hibiscus or both, in natural colours (hibiscus in red, pink, yellow, orange, white or purple, by turns or as a gradient), rainbow (Bright, Medium or Deep), your own colours, or 2-7 colours by turns or as a gradient, with an opacity of its own; **rainbow or alternating colours** (2-7) for the plain borders, the portraits' insides, the detail lines, the family lines and the special marks too -- for every male, female or upcoming child, or for the villagers you select, each of whom can also have their own **inside and detail colours** and be **flipped** or **turned** (Selected tab; their words can turn and mirror with them, Text tab) -- and **click one villager to resize or turn their portrait** with the same handles as a picture; set **sizes, line weights and line types in batch** (the size boxes change the tree as you type); show each villager's age in game units, in years, both or neither, **Founder** in the first generation and **"X's twin"** after the age; put portrait words left, centred or right and at the top, middle or bottom, fit them in the shape's own outline or the rectangle or oval that fills it, and space portraits side by side and between generations in pixels (**Keep aspect ratio** keeps a portrait's proportions in every size box); make special marks a **glow** instead of a border, with its size and opacity; set the **opacity** of the words, the boxes behind them, the portraits and the lines; **right-click to add** a text box, picture, shape or logo, or **to delete** anything -- a villager, a line, the title, a whole generation label or one line of it -- and restore it from **Deleted items**; number the generations in Roman numerals or numbers; **Renumber** the villagers whose text you edited; **Number duplicate names** (Text tab or the Tools menu) shows namesakes numbered, in order of appearance unless you pick another order under **Who is "I"** (Soda I, Soda II...), and offers to number them in the game's save and logs too; split a long family onto **pages** (a page ends with the generation the next one starts at, and the next page shows that generation again at its top, as its first villagers, with no lines up to their parents; saving a picture saves every page); ready-made backgrounds include plain colours, gradients, rainbows across or down, and pictures (the picture's opacity works on any colour, Transparent included); **Allow diagonal lines** (off unless ticked) lets a dragged line move any way; the options sit on tabs by what they change -- **Selected**, **Shapes**, **Faces & Text**, **Fonts**, **Layout**, **Marks**, **Background** and **Pictures**; Undo, Redo, **Update Family Tree from Logs/Saves** (F5: the save and the logs read again, every edit kept) and the Reset buttons sit under every tab, and every reset asks first. Upcoming twins and triplets are read from the mother's own record in the save. **Change Appearance** (the Origins Upgrades, all five games) now writes an "Appearance changed" record -- the name, the old head and body and the new -- to the Births and Conceptions log at the next save, so the tree knows the villager with the old look (a child's parent, an older record) is the same villager; their edits follow them, and the tree asks, once for each change, whether to show the new look or keep the old one.

**Village Matchmaker...** (the same places) suggests who to pair, by rules you tick -- every rule is yours to switch on or off: an age window of 18-49 (**Allow 50 and older**, or **Plan ahead** for any age), **close in age** within a number of years you set, **no shared ancestors** (since the tribe began, or within the generations you set), **related by at most** a percentage you set, no parent and child, full siblings, half siblings, grandparent and grandchild, aunt or uncle and niece or nephew, or first cousins, **not already expecting**, **different last names** (a Roman number after a last name is the same family: Wanjiko II is a Wanjiko), **One Family Per Partner** (a villager who already has a child with someone of one family is not offered another of that family; the same partner again always is), **List pairings by:** with a **Direction** (only the listing order changes, never who may pair with whom; ties keep the usual ranking): **Generation** (the default, Descending: the latest generation at the top; Ascending puts the oldest generation at the top), **Age** (the woman's age, then the man's; Descending is oldest at the top), **Number in the family tree** (the woman's number, then the man's, as shown on the Family Tree) or **Default order** (least related first, as before), **Prioritize previous partners** (couples who already have a child together first), and **fresh blood first**; every villager's generation number (Generation II, as on the Family Tree) is shown beside the name and age; **Show ages in game units too** chooses "1379 game units (68 years old)" or "68 years old". Relatedness is worked out from the whole recorded family (double cousins included). It suggests one partner each, least related first, and lists every allowed partner for each woman; when the rules allow no pair it shows the least related pairs instead. A Golden Child is never suggested. **Refresh Pairings** reads the save and the logs again and redraws the suggestions. The suggestions are also saved as `Virtual Villagers Fun Patcher Family Trees\Virtual Villagers G Village Matchmaker - Save N.txt` in the save folder, beside the family tree files; your ticks are remembered and **Reset to Defaults** puts back the starting ones. It only suggests: nothing in the game is changed.

The **Additional fun patches** section is grouped in game order, with each
game's patches sorted by patch name. It includes **Select All Patches**,
**Default Patches**, **Owner's Defaults** (every patch except Learning Skills
Never Fails, so Story / Cheat Upgrades and 256 Villagers (Experimental) too) and
**Deselect All Patches** buttons. They change every optional
fun-patch checkbox at once without changing the selected population mode, and the
selection is remembered normally.

For every selected game, all three modes create **`(Game name) - Modded`**
containing **`(Game name) - Modded.exe`** (**`(Game name) - Modded 256`** and
**`(Game name) - Modded 256.exe`** when 256 Villagers (Experimental) is ticked). By default the selected folder is beside the
supplied original; the GUI's **Modded output location** chooser can place all
selected games under another parent folder. It copies every file and subfolder
from the original game folder, verifies the copied files by SHA-256, keeps the
stock EXE in the copy, and adds the modified EXE plus, in its
`Virtual Villagers Fun Patcher Files` folder, the add-ons and the
`.patch-log.json` (see below). The
original folder and original EXE are never edited, renamed, replaced, or
deleted. Asset-swap patches such as VV1 Visual Mods, VV4 Optional
Text changes, and the VV5 Guardians of Isola Rewrite replace their listed image
and text files inside that copy only; the base-game files are restored whenever
the patch is not selected. Applying another population mode refreshes that mode's same short folder
after confirmation.

### The patcher's own files

Every file the patcher adds to a Modded folder is in one subfolder,
**`Virtual Villagers Fun Patcher Files`**, beside the modified EXE: every add-on
DLL (`VVFP ... .dll`, including `VVFP Startup.dll`), the images only those
DLLs read, the `.patch-log.json` and the `VVFP Transparency Log.txt`. The game
folder itself holds only the game's own files, the modified EXE and that one
folder. The add-ons are always loaded from that folder by their full path,
built from the modified EXE's own location (never from the current folder or
the Windows DLL search order), and with Unicode paths, so a game installed in
a folder with accented or Japanese characters in its name still loads every
add-on and writes its logs. A missing folder or DLL just switches that add-on
off; the game always starts. If the Modded folder's path is so long that an
add-on's path would reach Windows' 260-character limit, the patcher says so
and writes nothing, so choose a shorter output location.

The only patcher files outside that folder are ones the game itself opens
from its own folders by name, so they must stay where the game looks:

| File | Why it stays in place |
| --- | --- |
| A New Home's Visual Mods images (`Images\garden_restored.png`, `lagoon_restored.jpg`, `MapX1Y2.jpg`, `MapX2Y1.jpg`) | replace stock images the game opens from `Images` |
| `Images\mask_atlas.png` (A New Home Origins) | the game's own sprite loader opens it by name |
| `Images\vvfp_sort_band.png`, `Images\vvfp_sort_radio.png` (A New Home Sort By) | the game's own sprite loader opens them by name |
| `Images\golden_mushroom.png` (Super-Secret Golden Mushroom) | the game's own sprite loader opens it by name |
| `Images\heathen_masks.png` (The Lost Children / The Secret City Origins; written by the add-on when the game starts) | the game's own sprite loader opens it by name |
| `Images\vvfp_mask_atlas00.png`, `Images\vvfp_bighead_mask_atlas00.png` (The Tree of Life Origins) | the game's own sprite loader opens them by name |
| `Images\bigheads_masks.png` (New Believers Origins) | the game's own sprite table names it |
| `Assets\sm.xml` (The Tree of Life Optional Text Changes, New Believers Guardians of Isola Rewrite) | replaces the game's own string table |
| New Believers' Guardians of Isola Rewrite images | replace stock images the game opens from `Images` |

Patching again over a Modded folder made by an older version moves
everything into the new layout: the loose `VVFP ... .dll` files, the loose
images only the add-ons read, the old `.patch-log.json` and the old
`VVFP Transparency Log.txt` beside the EXE are removed (only files the
patcher itself installed, matched by name and, for non-DLL files, by
content), and files you added yourself are kept.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, the PE checksum is recalculated, and each result is read back and hashed. File size is preserved unless a selected patch appends a new section to the executable -- the Origins-based patches do, so for example A New Home grows from 581,632 to 589,824 bytes and New Believers from 991,232 to 1,024,000 -- in which case the section is declared in the PE headers like any other.

Every build that ships a companion DLL also ships `VVFP Startup.dll` and gets
one more small section, `.vvfpst` (4,096 bytes, read and execute only). It
replaces the game's own start-up call of `WinMain`: before the game opens its
window, it loads `VVFP Startup.dll` from the `Virtual Villagers Fun Patcher
Files` folder beside the EXE (by full path, with a Unicode path),
which loads and arms the patcher companions this build ships (never a stray
DLL left in the folder), and then the game starts exactly as before. So every
patch is running before the title screen and before any village loads --
including the catch-up on time away, when most births, deaths and island
events happen. A companion that is missing or fails to load is skipped; the
game always starts.

Bulk mode validates and renders all five inputs before writing. Each supplied
game folder is then copied into a hidden temporary sibling folder
(`.<Modded folder name>.staging-<id>`), the modified EXE and its companion files
are written and verified there, and only then is it renamed into place as the
short **`- Modded`** output folder. Re-running with overwrite replaces that same
Modded folder: files you added to it are carried over, the previous folder is
moved aside to a hidden `.backup-<id>` sibling while the new one is put in
place, and that backup is deleted once the new folder verifies, or renamed back
if anything fails. If a failure leaves something that cannot be restored
automatically, it is kept in a `.recovery-<id>` sibling rather than deleted.
The supplied original folders remain unchanged.

Stock game executables, saves, and generated playtest outputs are never committed.
The disabled VV4 Full Mastery C6 candidate carries its exact mockup provenance
and baked PNG source asset under `assets/candidates/vv4_full_mastery/`; its
constructor bytes require fresh independent recertification, and all
Expanded-256 population modes are removed from the active patcher.

## Command line

Pass `--patch-mode stock`, `--patch-mode collection_progression`, or `--patch-mode immediate_fixed` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. The available IDs are all current user-selectable per-game patches, including the five combined Origins Tech, Details, and Village-Wide routes and the ordinary VV1-VV5 patches. Each combined route automatically resolves its internal Origins base prerequisite, so its Tech-screen and Villager Details-screen buttons/upgrades are applied together with the village-wide payload; duplicate base entries, individual Full Mastery entries, and other withdrawn historical records remain hidden. Runtime/player confirmation remains pending. All three population modes accept the Origins-style routes in every game; the earlier restriction to `collection_progression` and `immediate_fixed` for VV3-VV5 no longer applies, because those routes' append layouts now certify under `stock` as well. The disabled VV3 Full Heal / Cure All candidate is not a CLI or catalog ID. The per-game Village Statistics IDs are `vv1_write_village_statistics`, `vv2_write_village_statistics`, `vv3_write_village_statistics`, `vv4_write_village_statistics`, and `vv5_write_village_statistics`.
The five current combined Origins route IDs are `vv1_origins_village_wide_upgrades`, `vv2_origins_village_wide_upgrades`, `vv3_origins_village_wide_upgrades`, `vv4_origins_village_wide_upgrades`, and `vv5_origins_village_wide_upgrades`.
Historical standalone Full Mastery and individual Full Mastery records are kept
only as evidence and are not selectable or included in releases. The corrected VV4
`vv4_full_mastery_all_stage_a_candidate` is catalog-hidden and disabled pending
fresh independent recertification after the C6 startup-crash correction. Its
candidate-only UI uses the canonical mockup crop baked into a deterministic
`Images\\btn_upgrades_297x35.png` strip (three 99x35 RGBA frames). It is loaded
through `sub_401C20` at local 72,4 with Tech event 13 and Detail event 2;
the unchanged helper/Cure/command-7/PNG/DLL bytes and the new constructor hashes
are recorded in the candidate map. The withdrawn Cure row is rendered
unavailable and command 5 is rejected before charge/0x728004 dispatch. Commands
6 and 8 remain absent, and the legacy atomic village-wide records remain contained.

VV3's independent stock-only command-7 Full Mastery implementation is
emitted-byte certified under disassembly commit
`1e6ad7fd610d2fe9d80416fb218366ccd7d0656b` and available as
`vv3_full_mastery_all_stage_a_candidate`. It reacquires the fixed current-save
manager before both dry runs, uses the native skill writer and Award evaluator,
and supports only `collection_progression` and `immediate_fixed`. Commands 6 and 8,
ownership/Remove, raw skill stores, and save-format changes remain absent.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed --output-root "path\chosen output parent"
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode stock --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed --output-root "path\chosen output parent"
```

Technical evidence is in `docs/max-population-research.md`,
`docs/island-event-population-research.md`, and the game-specific reports under
`docs/`.

The public patcher exposes only the five current combined Origins Tech, Details,
and Village-Wide upgrades-menu routes, one per game. Each route resolves that
game's Origins menu prerequisite and includes the latest menu implementation
rather than separate Full Mastery or duplicate Origins records. VV5's native Tech and
Villager Upgrades menus provide Full Mastery, Running, Set Age to 18, and Full
Heal / Cure All for active living Believers only. VV5 records with the Heathen
mask/status set, including the sick-Heathen puzzle record, are skipped before
action-specific reads or writes. Full Heal raises only health below 80 to 100
and clears sickness; health from 80 through 100 is preserved. Native writers,
statistics, and other stock handlers remain in the call path. Runtime/player
confirmation is still pending.
