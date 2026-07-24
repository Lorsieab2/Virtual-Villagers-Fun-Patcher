# Child teaching skill ceilings across all five games

Evidence status: static code-confirmed for the exact supported Windows
executables. The two Fun Patcher lesson awards are also distinguished from
stock behavior below.

| Game | Teaching mechanism | Skills | Award ceiling |
| --- | --- | --- | --- |
| A New Home | Stock Going to school action | None | Stock does not award skill |
| A New Home | Optional School Lessons Grant Skill patch | One random skill receives 7-9 points | 100 |
| The Lost Children | Stock Teaching Children / Attending lessons actions | None | Stock does not award skill |
| The Lost Children | Optional Teaching Children Grants Skill patch | One random skill receives 7-9 points | 100 |
| The Secret City | Tribal Chief lesson callback | One of five random skills receives 7-9 points | 100 |
| The Tree of Life | Periodic Nursery School updater | Five skills | Each skill is eligible only while its integer value is below 50 |
| New Believers | Periodic Nursery School updater | Six skills, including Devotion | Each skill is eligible only while its integer value is below 50 |

## VV1 and VV2 optional lesson patches

The VV1 and VV2 patches deliberately match the amount and random five-skill
selection used by the VV3 Tribal Chief lesson. Their private completion
callbacks cap the selected skill at 100. They therefore do not contain the
approximately-50 Nursery School ceiling.

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
