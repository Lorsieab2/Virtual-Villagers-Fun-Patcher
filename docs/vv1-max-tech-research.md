# VV1 Continue Research at Max Technologies research

Supported executable: `Virtual Villagers - A New Home.exe`

- Size: `581,632` bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

The six technology-level fields are global-state offsets `+0xA2BC`, `+0xA2C4`, `+0xA2CC`, `+0xA2D4`, `+0xA2DC`, and `+0xA2E4`. Routine `0x41CEA0` sums those six fields. Its sole static caller at `0x447481` compares the result with `0x12` (18), the sum produced by six level-3 technologies. At 18 or above, the stock `jge 0x447901` skips the research-action call. Below 18, execution calls the stock routine at `0x442C10`.

The patch changes only the comparison immediate at file offset `0x47488` from `0x12` to `0x13`. A legitimate six-by-level-3 game state sums to 18, so it remains on the original research path. The patch does not modify the research action queue, Research skill field, Science technology multiplier, or tech-point increment routine `0x41D120`.

| File offset | Stock byte | Patched byte |
|---|---|---|
| `0x47488` | `12` | `13` |
