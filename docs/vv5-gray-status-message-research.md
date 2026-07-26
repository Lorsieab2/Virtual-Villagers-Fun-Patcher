# VV5 gray status-bar message

The brief gray-bar message seen while a selected devotee was Honoring is stock
New Believers behavior:

> The villager wasn't successful this time.

The supported stock executable identifies it as localization ID 96,
`eSayFailedSkill`.

The stock Honoring action has a 50-percent choreography branch. That branch
then has a 25-percent chance to queue a Devotion skill attempt, so 12.5 percent
of completed Honoring actions reach that attempt. When it fails, the gray-bar
message is displayed only if the villager performing the action is currently
selected. A successful attempt uses localization ID 100, “This villager
improved at devotion!” A villager already at mastery uses ID 98.

The retained stock success threshold is:

`33 + integer Devotion skill`

The base becomes 66 with the Learning like or 16 with the Learning dislike.
Learning technology then adds 15 at level 2 or 30 at level 3.

Neither **Easier Devotee Training** nor **Statue Drops: Normal Action or
Honoring** edits the message renderer, localization ID, Devotion award
calculation, or Honoring action. Those patches can make eligible villagers
enter the stock Honoring action more often, which can make the retained message
appear more often as a consequence.

Evidence addresses in the supported VV5 executable:

- Honoring action: `sub_45CB70`
- Devotion skill handler: `sub_46B270`, skill index 5
- selected-villager check: `sub_4653D0`
- gray status message dispatcher: `sub_44EF60`
- gray status state: `byte_520F68`
