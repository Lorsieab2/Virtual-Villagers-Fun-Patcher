# Child teaching skill ceilings across all five games

Evidence status: static code-confirmed for the exact supported Windows
executables. The two Fun Patcher lesson awards are also distinguished from
stock behavior below.

| Game | Teaching mechanism | Skills | Award ceiling |
| --- | --- | --- | --- |
| A New Home | Stock Going to school action | None | Stock does not award skill |
| A New Home | Optional School Lessons Grant Skill patch | One random skill still below 50 receives 7-9 points | Exactly 50 |
| The Lost Children | Stock Teaching Children / Attending lessons actions | None | Stock does not award skill |
| The Lost Children | Optional Teaching Children Grants Skill patch | One random skill still below 50 receives 7-9 points | Exactly 50 |
| The Secret City | Tribal Chief lesson callback | One of five random skills receives 7-9 points | 100 |
| The Secret City | Optional Tribal Chief Lessons Stop at 50 patch | One random skill still below 50 receives 7-9 points | Exactly 50 |
| The Tree of Life | Periodic Nursery School updater | Five skills | Each skill is eligible only while its integer value is below 50 |
| New Believers | Periodic Nursery School updater | Six skills, including Devotion | Each skill is eligible only while its integer value is below 50 |

## VV1 and VV2 optional lesson patches

The owner (2026-09-29): lessons in A New Home, The Lost Children and The
Secret City stop at exactly 50, and a lesson picks only among the skills still
below 50, as the VV4/VV5 Nursery Schools skip any skill at 50. The VV1 and VV2
private completion callbacks count the skills below 50, ask the game's RNG for
one of them and for the stock 7-9 points, and clamp at 50; a skill at or above
50 is never chosen or lowered, and with all five at 50 a lesson awards nothing.
VV3's stock callback 42 is diverted to "VVFP Lesson Cap.dll" by the Tribal
Chief Lessons Stop at 50 row. Unlike the Nursery Schools' integer-below-50
eligibility test, the award is clamped, so it never ends above 50.
tests/test_lesson_cap_at_50.py runs all three awards in an emulator.

The player confirmed on 2026-07-24 that completed VV2 Teaching Children
lessons appear to award skill. Distribution across all five possible skills
has not yet been fully player-verified. The corrected VV1 callback route is
statically verified and covered by guarded-byte tests; live player
confirmation remains pending.

## VV3 Tribal Chief

The Leadership-level-2 Tribal Chief education route finishes with callback 42.
That callback selects one of the five skills with equal odds and adds
`RNG(3)+7`, producing 7, 8, or 9 points through the stock capped skill helper.
The helper permits progress to 100, so repeated successful lessons can
eventually make a child a Master in the selected skills.

## VV4 and VV5 Nursery Schools

These are saved-clock systems rather than completion awards attached to the
visible classroom animation. Each periodic update scans eligible children
under age 14 whenever a qualifying Nursery School teacher exists.

Both games test the integer part of each candidate skill against 50 before
adding the floating-point award. This is an eligibility threshold rather than
an exact post-award clamp, so a final addition may leave a skill slightly over
50. Nursery School alone does not continue training that skill to 100.

VV4 processes five skills. VV5 processes six skills throughout this updater,
including Devotion. The optional VV5 Divisor Parity patch changes only the
spread branch from fifths to sixths; it does not alter the skill set or the
approximately-50 eligibility threshold.
