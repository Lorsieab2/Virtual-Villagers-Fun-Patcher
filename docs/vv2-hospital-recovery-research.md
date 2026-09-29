# VV2 Hospital Recovery Health Research

## Supported executable

- Game: Virtual Villagers 2: The Lost Children
- Size: 724,992 bytes
- SHA-256: `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`

All offsets below are limited to this exact Windows executable.

## Stock behavior

Localization ID `0x91` is **Recovering at the hospital**. Its action
constructor begins at virtual address `0x0045C250`. The constructor creates the
stock movement and recovery queue and then calls the normal queue finalizer at
`0x0045C56C`.

The complete constructor contains no health-field write and installs no
completion callback that changes health. The villager health field is the
integer at record offset `0x52C`, capped at 100 by the game's other healing
paths.

## Patch

The patch detours the final eight bytes at file offset `0x5C569` through
guarded zero-filled padding at `0x73E20`. The cave:

1. appends a private callback-126 queue entry after the complete stock recovery
   queue;
2. calls the original queue finalizer;
3. resumes the original return path.

The shared callback dispatcher at file offset `0x73D80` handles callback 126 by
locating the completing villager's record, adding exactly one to health only
when it is below 100, and returning. Every stock callback follows the displaced
dispatcher prologue and original switch. Callback 127 remains reserved for the
Teaching Children skill award.

Because the award is a final queue callback, interrupting the recovery before
completion gives no health. The patch does not alter hospital eligibility,
movement, action duration, sickness, doctors, Healing skill, food, or any
other health-changing routine.
