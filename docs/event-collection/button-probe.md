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

Nothing blocks seven answers on one page: the ids and the label capacity are both clear. The open question is the
remaining risk, R2: whether seven stacked buttons leave room for the text on an 800 x 600 screen. The render test in
`tests/test_multi_answer_popup.py` answers it.
