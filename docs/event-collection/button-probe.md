# Five to seven answer buttons: the probe (risk R1)

Isola Grand Event Collection, track B. Read from the stock executables in `inputs\vvN-stock-copy` with capstone, then
confirmed in the emulator by `tests/test_multi_answer_popup.py`, which drives each game's own click handler with
every new id.

## The Secret City, The Tree of Life, New Believers (`native/shared/vvfp_multi_answer.h`)

**Button ids 4 to 8 are free.**
- The two-choice dialog's constructor (0x4192F0 / 0x417790 / 0x418020) makes exactly three buttons: id 1 (OK, +0x864),
  id 2 and id 3 (the answers, +0x85C / +0x860). For example, in The Secret City the button constructor 0x4019F0 is
  called with `push 1` at 0x4193DE, `push 2` at 0x419521 and `push 3` at 0x419562, and with no other id.
- The dialog's click handler (0x419A00 / 0x417EA0 / 0x418720) compares the id with 1, 2 and 3 only, so any other id
  falls through and does nothing.
- Scrolling Popups draws its bars itself and adds no child buttons.
- Ours already use 4 and 5. Answers 5 to 7 take ids 6, 7 and 8. Our handler catches them before the game's handler.

**Label capacity is not a limit.**
- Our label goes through the dialog's text setter (0x4185A0 / 0x416F60 / 0x417700). It formats into the dialog's
  +0x58 buffer with a cap of 0x7D0 (2,000) bytes: `push 0x7d0` at 0x418612 / 0x416FD0 / 0x417770.
- The button's label routine (0x401620 / 0x401600 / 0x4015D0, through 0x4012E0 / 0x401140 / 0x401110) copies the
  text into a fresh heap block of strlen + 1 bytes (operator new 0x46EC93 / 0x470C5C / 0x47BBDC), with no fixed
  buffer.
- So a label of 95 bytes (the v6 limit) fits easily. The real limit is the popup's width in pixels (design B7, fit
  rule).

## A New Home, The Lost Children (`native/shared/vvfp_multi_answer_12.h`)

**Button ids 5 to 9 are free.**
- The encounter dialog's constructor (0x41A460 / 0x422380) stores its ids at +0x54 = 2, +0x58 = 3, +0x5C = 4
  (0x41A495-0x41A4A3 / 0x4223B5-0x4223C3) and makes three buttons with them.
- The click handler (0x41A3D0 / 0x4222F0) compares the id only with those three fields.
- Ours already use 5 and 6. Answers 5 to 7 take ids 7, 8 and 9.

**Label capacity.** Our label routine (0x4015B0 / 0x4015D0) heap-copies the text the same way. We pass the words
straight in, from our own buffer (`MB_LABEL_BYTES`).

## Conclusion

Nothing blocks seven answers on one page: the ids and the label capacity are both clear.

## Seven on one screen (risk R2)

One column, as decided (Q12). From five answers the buttons stand 1.25 button heights apart instead of 1.5, so seven
take 8.75 heights instead of 10.5 (`ma_step` / `mb_step`).

The question page keeps `CG_ANSWER_LINES` text lines for the buttons past two: 3, 6, 7, 10 and 12 lines for 3 to 7
answers. That is the extra height in 20-pixel lines, rounded up (for six answers 9.5 becomes 10, where
`vv_cie_graph.answer_room` says `ceil(2.5 n) - 6` = 9).

From five answers that reserve is capped so that a page always keeps 3 lines of text below the title the popup
leads with. Without the cap, The Secret City, The Tree of Life and New Believers (11 question lines) and A New Home
(13 lines, 5 of them the title) could not page the text at all.

The popup then grows past a two-answer popup's height by the rest of the reserve.
`tests/test_multi_answer_popup.py SevenFitOnScreen` checks every game, with and without Scrolling Popups. It
measures the panel as the companion lays it out: the constructor's 0x3C margin, the title, at least 3 text lines,
then 7 answers and OK. The panel is at most 600 pixels, and the companion's placed buttons sit inside it, below the
text, with no two meeting. **Two columns are not needed.**

UNCONFIRMED: the button heights are the emulator stand-ins (42 pixels in the later three games, 40 in the first two).
The game art's widest answer pictures are 32 pixels tall (`popup_button1`, `main_wide_button2`), so the real
heights are probably smaller. A New Home's 7-answer question is the tightest case, at 600 of 600 pixels with 40-pixel
buttons, so it needs a live look.
