/* VVFP VV3 Trees Take Turns -- "Fruit Trees Take Turns Refilling" (The Secret City;
   docs/vv3-fruit-tree-timing.md).  The fruit trees' refills are spread evenly over the refill
   interval -- with three trees one refills every hour (45 minutes with the Nature patch at
   Nature 1) -- so the village goes the shortest time with no tree to pick.  Each tree is paid
   the stock amount for the time since its own last refill, so no tree gains or loses fruit
   over time.  The save keeps the stock timers; the schedule is kept beside the save.
   Everything is in native/shared/vv3_fruit_timers.h. */
#define VV3_FRUIT_MODE 2
#include "../shared/vv3_fruit_timers.h"
