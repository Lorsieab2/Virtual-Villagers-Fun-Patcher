# Village Statistics audit transparency

Exact-build audit `7fe0a047706693d69c9b504f7a7b0b014280dee3`
confirms that VV1-VV5 **Oldest Villager** exports the persisted lifetime
maximum rather than rescanning living, dead/skeleton, grave, mausoleum, VV3
Roster of the Dead, or other memorial records. Stock-layout export is proved;
expanded-256 walker coverage remains ON HOLD.

A future **Villagers Buried** implementation must increment exactly once at
the earliest successful skeleton pickup. Known later grave placement,
record-release, or record-retirement sites are insufficient, regardless of
graveyard/mausoleum capacity, completion, occupancy, or later burial success.

Retained memorial records may provide a one-time lower-bound baseline only.
Initialization requires an atomic save-scoped initialized marker; the
baseline must never be added again per export. VV2 `state+0x2E514` is Village
Elders and is forbidden for buried migration, ownership, or initialization
state. Exact pickup hooks, safe migration storage, and expanded-256 walker
coverage remain ON HOLD.
