# Parentage Log

The parentage log uses one ordinary browser-readable HTML file per modified
game.  The filename is:

`(game name) Parentage Log.html`

It is written beside that game's modified executable, for example:

`Virtual Villagers - A New Home - Modded/(Virtual Villagers - A New Home) Parentage Log.html`

The same format is used for Virtual Villagers 1, 2, 3, 4, and 5.  A card is
added when a child becomes an independent villager, not when conception starts.
Each card contains only the child name, head/body row numbers, likes,
dislikes, and numeric skills, followed by the mother and father names and
head/body row numbers.

At the beginning of every file, the guide says:

> Head/body row guide: head and body values correspond to the rows in the Body and Head pictures in the Images folder.

The first row is number 0, the next row is number 1, and so on.  The HTML can
hold well beyond 256 cards and uses the existing `Images` folder in the copied
game directory for the male/female head and body pictures.  The writer updates
the file through a temporary file, so a failed write does not replace an
earlier complete log.

This document describes the shared file format.  It does not claim that an
unverified birth hook has been added to a game executable; each game's native
hook must still be fingerprinted against its exact supported build before the
optional patch is advertised as active.
