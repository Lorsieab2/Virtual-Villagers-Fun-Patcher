# Retired VV1 Magic Fruit mortality experiment

The **Magic Fruit of Life Alters Mortality** patch shipped in v1.24.0 and was
removed in the next corrective release.

Its persistent-storage premise was unsafe. Byte `+935` of the 984-byte VV1
villager record was described as an unused final name-buffer byte. The actual
Detail-screen routine at `0x43BA60` treats record offsets `+920`, `+924`,
`+928`, and `+932` as four pointers used to render likes and dislikes.
Therefore `+935` is the high byte of the fourth pointer, not free storage.

The player-observed crash was recorded by Windows as access violation
`0xC0000005` at executable offset `0x3BA86`, inside the stock Detail-screen
pointer-reading loop. Writing or clearing `+935` can corrupt that pointer and
cause precisely that failure.

The optional patch is no longer offered or applied. The school lesson,
continue-research, and F6 clothing patches do not write this field. A future
Magic Fruit mortality patch must identify and independently verify genuinely
safe per-villager persistent storage before it can be restored.
