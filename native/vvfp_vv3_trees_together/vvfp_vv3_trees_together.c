/* VVFP VV3 Trees Refill Together -- "All Fruit Trees Refill at the Same Time" (The Secret
   City; docs/vv3-fruit-tree-timing.md).  Every fruit tree refills at the same moment: the
   earliest tree's refill time is every tree's, and each is paid the stock amount for the time
   since its own last refill, so no tree gains or loses fruit over time.  The save keeps the
   stock timers; the shared schedule is kept beside the save.  Everything is in
   native/shared/vv3_fruit_timers.h. */
#define VV3_FRUIT_MODE 1
#include "../shared/vv3_fruit_timers.h"
