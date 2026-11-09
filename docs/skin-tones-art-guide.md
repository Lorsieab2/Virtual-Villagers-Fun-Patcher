# Skin tones for A New Home: the art you draw

This is the draft row **Skin Tones (Draft)** (`vv1_skin_tones`). It is not for a release yet. The patcher
recolours nothing: for each villager it picks which pictures the game draws, and the pictures for every tone
but 0 are yours. Draft PR #707 holds the design notes and the rejected automatic recolours.

## How many tones

- **Tone 0 is the game's own art.** You draw nothing for it.
- **Tones 1, 2, 3 ...** are numbered folders. The patcher counts the folders `1`, `2`, `3` ... when the game
  starts. The first missing number ends the count, so make them without gaps. Up to 15 are read.
- **With no folder at all there are 8 tones.** Villagers are given tones 0 to 8 before the art exists, and
  each tone shows as soon as its folder is there.
- **Number them from light (1) to dark.** A baby's tone is the one halfway between its parents' tones, so
  the numbers have to be in order. Tone 0, the game's own painted skin, counts as the lightest.
- Founders and newcomers get a random tone from 0 to the number of tones, each equally likely.

## Where the files go

In the game folder (beside `Virtual Villagers - A New Home.exe`, or the patched copy):

```
Images\vvfp_skin\1\
Images\vvfp_skin\2\
...
Images\vvfp_skin\8\
```

## The files in each tone folder

Every file has the game's own name and **exactly** the game's own size. Start from a copy of the game's own
file in `Images\` and paint only the skin. Keep the transparent background, and keep every cell where it is.

| File | Size (pixels) | Cells | What is in it |
|---|---|---|---|
| `male_heads.png` | 280 x 1300 | 7 across x 20 down, 40 x 65 each | A row is a head (the head number 0-19). A column is a facing or frame. Row 19 is the Golden Child's head. |
| `female_heads.png` | 280 x 1300 | the same | The women's heads. |
| `male_bodies00.png` | 640 x 650 | 16 x 10, 40 x 65 each | Bodies 0-9, frames 0-15. |
| `male_bodies10.png` | 640 x 650 | 16 x 10 | Bodies 0-9, frames 16-31. |
| `male_bodies01.png` | 640 x 650 | 16 x 10 | Bodies 10-19, frames 0-15. |
| `male_bodies11.png` | 640 x 650 | 16 x 10 | Bodies 10-19, frames 16-31. |
| `female_bodies00.png`, `10`, `01`, `11` | 640 x 650 each | the same | The women's bodies. |
| `male_actions00.png` | 360 x 650 | 9 x 10, 40 x 65 each | Bent over, at work, sitting: bodies 0-9. |
| `male_actions01.png` | 360 x 650 | 9 x 10 | The same for bodies 10-19. |
| `female_actions00.png`, `01` | 360 x 650 each | the same | The women's. |
| `vvfp_grey_male_heads.png` | 280 x 1300 | 7 x 20, 40 x 65 each | Grey Hair at 55's grey heads, in this tone. |
| `vvfp_grey_female_heads.png` | 280 x 1300 | the same | The women's grey heads. |

That is **16 files per tone**. In a body file name, the first digit is the half of the frames (0 or 1) and
the second is the half of the bodies (0 or 1), the way the game names its own files.

Children are drawn from the same sheets, smaller. The dead (`skelly.png`) have no skin and are not part of
this. The masks are drawn over the head and are not part of this either.

## What happens when a file is missing

Each file is checked on its own. A file that is missing, or not exactly the size above, is drawn from the
game's own picture for that villager. Only that file falls back; the tone's other files are still used. So you
can do one tone, or one sheet, at a time. A missing grey head of a tone falls back to Grey Hair's own grey
head, the one without a tone.

Each file is loaded once, the first time a villager of that tone needs it. After you change a picture, quit
and start the game again to see it.

## How to test a tone

1. Patch A New Home with **Skin Tones (Draft)** ticked. Origins and Grey Hair at 55 are ticked with it. Tick
   **Write Births and Conceptions Log to Text File** too, so babies know their father's tone.
2. Make `Images\vvfp_skin\1\` in the patched game folder, and copy your 16 files into it. For a quick look,
   one file is enough, for example `male_heads.png`.
3. Start the game. Open a man's **Change Appearance** (Villager Details, Origins Upgrades). In the **Skin
   tone** row, press `>` until it says **Tone 1**. The preview shows his head and body from your files; a file
   that is not there shows the game's own picture.
4. Press **OK**. He is drawn with your tone in the village, on the map and in the Details portrait. The
   Births and Conceptions log gets an "Appearance changed" record with an "Old skin tone" and a "New skin
   tone" line.
5. To see every tone at once, use **Change Appearance for All**. Its **Skin tone (every villager)** row can
   choose one tone for everyone, or **Random (each villager)**.
6. To check a baby, let two villagers of different tones have a child. The baby gets the tone halfway between
   theirs.

Each villager's tone is kept in `Virtual Villagers Fun Patcher\Save <slot>\Data\Skin Tones\Skin Tones - Save
<slot>.dat`, beside the saves. **Start Over** deletes it. Delete it yourself and every villager gets a new
random tone.

## Not done yet

- Show Parents' small parent figures, the Family Tree Maker and Picture Studio still use the game's own skin.
- None of this has been seen in a running game yet. It was checked by emulating the stock executable.
- The other four games come after you approve this one.
