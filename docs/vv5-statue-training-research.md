# VV5 Statue Polishing or Honoring Research

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

## Patch

Each of those four guarded five-byte behavior pushes becomes a call to one shared selector in zero-filled executable padding at file offset `0x944A0`. The selector:

1. Preserves the caller's return address.
2. Calls the stock random-number function with an exclusive bound of 2.
3. Selects behavior `0x9D` for result 0 or `0xA0` for result 1.
4. Restores the original stack shape, leaving the selected behavior where the displaced `push 0xA0` placed it.
5. Returns to the untouched stock dispatch.

Both outcomes therefore have equal odds. The selector reuses the original Polishing and Honoring routines; it does not reproduce either action or write Devotion skill directly.

## Preserved behavior

- Statue-state eligibility remains controlled by the original drop handlers.
- Polishing and Honoring retain their complete stock action queues.
- Devotion gain amounts and thresholds are unchanged.
- Autonomous work and Retired Chief activities are untouched.
- The original executable is never modified; the patcher writes a separately named copy with a recalculated PE checksum.
