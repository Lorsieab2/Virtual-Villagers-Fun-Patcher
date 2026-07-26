# VV5 Statue Normal Action or Honoring Research

## Supported executable

- Game: Virtual Villagers 5: New Believers
- Size: 991,232 bytes
- SHA-256: `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`

All file offsets and virtual addresses below refer only to this exact executable.

## Stock behaviors

The behavior registration table identifies:

- Slot `0x9D`: routine virtual address `0x455020`, whose displayed action is localization ID `0x321`, Polishing the Statue.
- Slot `0xA0`: routine virtual address `0x45CB70`, Honoring.

The upgradeable statue's two manual dispatch paths at file offsets `0x6C45D` and `0x6CDED` push behavior `0xA0` Honoring directly. The fully completed statue's corresponding direct dispatches at file offsets `0x6BF9A` and `0x796EB` push behavior `0x9D` Polishing directly.

The surrounding stock state tree also dispatches behavior `0x95`, **Building
a statue**, while construction is underway. The direct world-drop handler
uses that behavior at file `0x796B3`; the two companion statue handlers retain
their corresponding `0x6BF60` and `0x6CC39` dispatches. If a requested statue
upgrade lacks the necessary technology, the world-drop handler takes its
retained behavior-`0x1F` **Confused** route at file `0x79726`. These branches
occur before the eligible Polishing/Honoring choices.

## Patch

The patch routes all eight identified statue behavior dispatches into three
skill-aware selectors. A short trampoline remains at file offset `0x94460` and
the expanded selector bodies are stored in zero-filled executable padding from
`0x94740` onward:

- Construction routes choose behavior `0x95` **Building a statue** or `0xA0`
  **Honoring** only when the current villager has positive Devotion and
  positive Building skill.
- The missing-technology route chooses behavior `0x1F` **Confused** or `0xA0`
  **Honoring** only when the current villager has positive Devotion; it does
  not grant Honoring to a villager without that skill.
- Eligible upgradeable and completed routes choose behavior `0x9D`
  **Polishing the Statue** or `0xA0` **Honoring**. A devotee without Building
  skill is routed to Honoring, while a villager without Devotion keeps the
  normal polishing action.

Each selector:

1. Preserves the caller's return address.
2. Checks the current villager's Devotion skill before allowing the Honoring
   outcome, and checks Building skill before allowing a devotee's construction
   or polishing outcome.
3. Calls the stock random-number function with an exclusive bound of 2 only
   when both outcomes are skill-eligible.
4. Maps random result 0 to that state's normal behavior and result 1 to
   behavior `0xA0`; skill-ineligible cases are deterministic.
5. Preserves and restores `ECX`, which holds the current villager for the
   following stock behavior-setter call and is not preserved by the random
   function.
6. Restores the original stack shape, leaving the selected behavior where the
   displaced behavior push placed it. The Confused selector also reproduces
   the displaced `mov [esp+0x0C],0x66` at the matching stack depth.
7. Returns to the untouched stock dispatch.

Both outcomes in every state therefore have equal odds. The selectors reuse the
original Building, Confused, Polishing, and Honoring routines; they do not
reproduce any action or write Devotion skill directly.

The v1.28.0 selector preserved the stack but not `ECX`. When the random-number
call overwrote that register, the following behavior setter could dereference
an invalid current-villager pointer at virtual address `0x0046558A`. A copied
player save reproduced that defect as Windows exception `0xC0000005`. The
corrected selector explicitly saves and restores `ECX` around the random call.

## Preserved behavior

- Statue-state eligibility remains controlled by the original drop handlers.
- Building a statue, Confused, and Polishing remain available as the
  non-Honoring outcomes where their skill predicates allow them.
- Builders do not Honoring unless they also have positive Devotion, and
  devotees do not build or polish unless they also have positive Building.
- All four behaviors retain their complete stock action queues.
- Devotion gain amounts and thresholds are unchanged.
- Autonomous work and Retired Chief activities are untouched.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
