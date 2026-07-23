# VV5 Nursery School divisor parity

Supported executable:

- `Virtual Villagers - New Believers.exe`
- 991,232 bytes
- SHA-256 `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`

Evidence status: static code-confirmed for this exact Windows executable. Developer intent and visible player experience are not inferred.

VV5's periodic Nursery School updater is at `0x00425E30`. It includes Devotion throughout the six-skill system:

- teacher qualification scans six skills;
- teacher strength sums six skills;
- the focused branch selects among six child skills;
- the spread branch writes to six child skills.

The spread branch nevertheless divides the base award by the double constant `5.0`. Its division instruction is:

```text
0x00425FDF  DC 35 10 88 49 00  fdiv qword ptr [0x00498810]
```

The subsequent loop runs six times. When all six skills are below the Nursery threshold, stock VV5 therefore distributes `6A/5` in total. VV4 divides by five and writes to five skills, distributing exactly `A`.

The optional **VV4 Nursery School Divisor Parity** patch redirects only this instruction to a private `6.0` constant:

- instruction operand at file offset `0x25FE1`: `10 88 49 00` to `40 45 49 00`;
- private IEEE-754 double `6.0` at file offset `0x94540`, virtual address `0x00494540`: `00 00 00 00 00 00 18 40`.

The stock shared `5.0` constant at `0x00498810` is not changed. No other calculation is redirected.

The patch affects only spread lessons:

- each eligible skill receives `A/6` instead of `A/5`;
- six eligible skills receive exactly `A` in total;
- each individual spread share is 16.7% smaller.

It does not change focused strongest-skill lessons, teacher qualification, teacher selection, teacher strength, child eligibility, skill thresholds, visible actions, saved-clock processing, or offline catch-up.

This is described as an arithmetic inconsistency and a parity option. The executable alone does not establish whether the retained divisor was intentional.
