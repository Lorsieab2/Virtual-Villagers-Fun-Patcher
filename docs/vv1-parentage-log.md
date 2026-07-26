# Parentage log format (initially prototyped from VV1)

The parentage output is one ordinary `(<game name>) Parentage Log.html` file.
It opens
in a normal browser and is safe to copy or archive. It contains one compact
birth card for each child when that child becomes an independent villager.

Each card contains only:

- the child name, head/body numbers, likes, dislikes, and numeric skills;
- the mother name and head/body numbers;
- the father name and head/body numbers.

At the top of every file the renderer prints:

> head and body values correspond to the rows in the Body and Head pictures in the Images folder.

The same file format is intended for Virtual Villagers 1 through 5. The game
title changes per output file; the card fields and sprite-row explanation do
not. Build-specific native birth hooks remain a separate verification task;
the renderer must not be mistaken for an already-injected executable patch.

The HTML can contain more than 256 cards. It uses the VV1 sprite rows directly:
head row `n` is head index `n`; body row `n` is body index `n`, with body rows
10-19 read from the corresponding `bodies10.png` sheet. Sex is retained only
internally to select the male or female sheet and is not reported as an extra
field.

The renderer supports either relative `Images/` paths or embedded PNG data.
The planned game writer will use the modded game folder's existing `Images`
directory and replace the HTML through a temporary file so an interrupted
write does not destroy an earlier log.
