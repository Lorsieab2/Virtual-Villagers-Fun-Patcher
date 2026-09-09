# Village Statistics audit transparency

Exact-build audit `7fe0a047706693d69c9b504f7a7b0b014280dee3`
confirms that VV1-VV5 **Oldest Villager** exports the persisted lifetime
maximum rather than rescanning living, dead/skeleton, grave, mausoleum, VV3
Roster of the Dead, or other memorial records. Stock-layout export is proved;
expanded-256 walker coverage remains ON HOLD.

That statement describes what the exporter reads, and the field it reads is
maintained by the game rather than by this project. In The Lost Children the
whole age-event block is gated on the display age `+0x530` equalling the
processed age `+0x534` (`0x42EF1A` / `0x42EF20`), and every write to the
Oldest Villager statistic `state+0x2E51C` sits inside that block. While the
pair is apart the statistic is not updated at all. The pair converges again
because `sub_43B690` increments the processed age once per tick per villager
(`0x43C09A`), so any such stall is bounded by the size of the age gap rather
than permanent. The exported value is therefore the game's own persisted
maximum in every case, including while that maximum is temporarily not being
advanced.

**Twins Birthed** is exported from statistics `+0x28` in The Secret City, The
Tree of Life and New Believers. That field is incremented in the childbirth
routine on the twins branch (`0x455BE7`, `0x45E8DD`), and was previously
printed under a "Special Stews Found" label inherited from the games' internal
enum-name mapping. The Lost Children's Special Stews Found row is a separate
statistic read from `state+0x2E520` and is unchanged.

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
