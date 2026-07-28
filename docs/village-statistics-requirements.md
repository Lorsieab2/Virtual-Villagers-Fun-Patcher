# Village Statistics requirements

The text exporter must track these lifetime statistics separately for every
save in all five games:

- Real Hours Played
- Points Earned
- Babies Made
- Food Gathered
- People Cured
- Mushrooms Found
- Highest Population
- Village Elders
- Oldest Villager
- Island Events Seen
- Twins Birthed
- Triplets Birthed
- Villagers Died, counting every villager death when it occurs
- Puzzles Solved

Game-specific lifetime statistics:

- The Lost Children:
  - Special Stews Found
  - Total Stews Found, with no herb-combination restriction
- The Secret City:
  - Chiefs Robed, counting every villager who is made Chief with the robe
  - Stews Found, including every herb combination
- The Tree of Life:
  - Debris Cleared from the stream
  - Stews Found, including every herb and salt/fresh-water combination
- New Believers:
  - Heathens Converted, including the Heathen Chief and red-, purple-, blue-,
    and orange-mask Heathens
  - The Heathen Mommy conversion counts as two

All counters are lifetime totals from creation of the individual save. They
must not be reconstructed only from current village state when that would lose
historical events.

Audit `7fe0a047706693d69c9b504f7a7b0b014280dee3` fixes two
cross-game rules:

- **Oldest Villager** is the persisted lifetime maximum in VV1-VV5. Stock
  export reads that field directly; it is not a living/dead/skeleton,
  graveyard/mausoleum, Roster of the Dead, or other memorial scan.
  Expanded-256 walker coverage remains ON HOLD.
- **Villagers Buried** increments exactly once at the earliest successful
  skeleton pickup. Later grave placement, record retirement, graveyard or
  mausoleum capacity/completion/occupancy, and later burial success cannot
  gate the increment.

A retained-memorial count is a one-time lower-bound baseline, not an amount
added per export. Initialization must atomically store the baseline and a
dedicated save-scoped initialized marker; future pickups increment the saved
counter. VV2 `state+0x2E514` is Village Elders and is forbidden for buried
migration, ownership, or initialization state.
