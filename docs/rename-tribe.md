# Rename Tribe: where the name lives, and the games' own rules

The owner asked for a "Rename Tribe" feature that "just renames the savefile
internally", "conforming to the natural character limit". This is the
evidence behind `src/vv_tribe_rename.py`, gathered statically from the five
stock executables in `research/stock-executables` and from the owner's saves
(read only: 254 slot saves across every save folder, all parsed). The live
results are in the pull request.

## Evidence table

| | A New Home (VV1) | The Lost Children (VV2) | The Secret City (VV3) | The Tree of Life (VV4) | New Believers (VV5) |
|---|---|---|---|---|---|
| Slot save | `Virtual Villagers<n>.ldw` | `Virtual Villagers - The Lost Children<n>.ldw` | `... - The Secret City<n>.ldw` | `... - The Tree of Life<n>.ldw` | `... - New Believers<n>.ldw` |
| File header | 12 bytes: `ldwg`, a time dword, the buffer length | 12 | 12 | 24 (length at +16); older saves 12 | 24 (length at +16) |
| Save buffer length | 0x0ABDC | 0x30370 | 0x12F1C; 0x1A4B4 with 256 Villagers | 0x1710C; 0x1DCB4 with 256 | 0x17D78; 0x1F168 with 256 |
| Name in the buffer | +0x8, 33 bytes to the next field | +0x8, 33 | +0x12ECC, 24 | +0x170B8, 24 | +0x17D14, 24 |
| Encoding | NUL-terminated ASCII | same | same | same | same |
| Checksum / CRC | none: the reader (0x402FD0) checks only `ldwg` and the length | none (0x403260) | none (0x4033A0) | none (0x4037E0) | none (0x403770) |
| Slot list `<base>0.ldw` | names at file offset 22, 33 bytes each; occupied flags at 187 | 22 / 33 / 187 | 22 / 21 / 127 | 34 / 21 / 139 | 34 / 21 / 139 |
| Slot list refilled from the saves at startup | yes (0x41D260) | yes (0x426410) | yes (0x4285E0) | yes (~0x41F980) | yes (~0x425470) |
| Older generations | `<base>2<n>`, `<base>4<n>`: the writer rotates n -> n+20 before every save (0x403176); never read back | same | same | same | same |
| Characters typed in the name entry (`SetEditable`) | 32 (`push 0x20`) | 32 | 20 (`push 0x14`) | 20 | 20 |
| Characters stored (`GetText(buf, size)` keeps size-1) | **31** (0x40BB70) | **31** (0x40C550) | **19** (0x40D1E0) | **19** (0x40D420) | **19** (0x40D910) |
| Characters the entry accepts | printable ASCII (the SDL text handler 0x403B9B passes single bytes only; the key filter takes 0x20..0xFF) | same (0x403E3B) | same (0x40445B) | same (0x404A3B) | same (0x4049CB) |
| Characters the font cannot draw (drawn as "A") | `# $ % & ( ) * + ; < = > @ [ \ ] ^ _ { } \| ~` | same | none | none | none |
| Spaces | kept as typed, never trimmed | same | same | same | same |
| Empty name | refused (restores "NEW PLAYER") | same | same | same | same |
| "NEW PLAYER" | the slot screen's empty-slot marker, compared exactly (0x413EE3) | same | same | same | same |
| Name shown in the game | slot screen; "Player: " + name (0x426100) | slot screen; "Tribe: " + name (0x431D56) | slot screen | slot screen | slot screen |
| Longest safe name | 32 (the 33-byte slot list field) | 32 | 20 (21-byte field; the restart copy uses a 24-byte stack local, so over 23 would break the stack) | 20 | 20 |

So the rename writes the new name, NUL-padded to the field, into the slot
save, into each older generation that still holds the same name, and into the
slot list; the limit is what each game stores itself (31 or 19), which is
also inside every safe bound. The header bytes are never changed: their time
dword is the game's clock base.

## The patcher's own files

| What | Bound to the village by | After a rename |
|---|---|---|
| Births and Conceptions, Deaths, Unaccounted Villagers logs | the header line `Village: <name> (Save <n>)` (parentage_export.c, `log_belongs_to_village`) | would have started a new file; now each gets the note `Tribe renamed from <old> to <new> on <date>`, which `read_log_header` applies, so records continue in the same file |
| Start Over / tribe delete | the same header (save_reset.c, `log_line_matches`) | follows the note, so the renamed village's logs and roster pages are still cleared, and a log only naming the old name is not |
| Village Population pages | header on line 2, rewritten at every save | note appended; new header at the next save |
| Village Statistics v2 - Save n | slot | note appended; new header at the next save |
| Village History | shared, one dated snapshot per save | one note naming the slot; later snapshots carry the new name |
| Statistics, Stew Discoveries, Village Elders, Roster, Graves, Parentage Records, Custom Titles .dat | slot, and the roster of villagers | untouched: no .dat holds the name |

The note parser (`native/shared/village_rename.h`, mirrored in Python) only
accepts `Tribe renamed from <current name> to <new> on YYYY-MM-DD` at the
start of a line, for the name the file currently stands for, so a stray line
cannot move a log to another village, and renames chain.
