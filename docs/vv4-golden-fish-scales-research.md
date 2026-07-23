# VV4 complete Fish Scales collection and Golden Fish

Supported executable:

- `Virtual Villagers - The Tree of Life.exe`
- 929,792 bytes
- SHA-256 `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`

Evidence status: static code-confirmed for this exact Windows executable. The user's statement that the stock threshold was a deliberate developer change is recorded as player-provided context; developer intent is not independently inferred from the executable.

Fishing-net action 129 is registered to `sub_4331D0`. Near the result selection, the stock function counts collected Fish Scales through:

```text
sub_413B90(dword_4CC838, 70, 1, 1, 1)
```

The collection screen strings establish three groups of four scales: four common, four uncommon, and four rare, for 12 total.

Define `C` as the returned collected-scale count. Stock Golden Fish eligibility is:

```text
RNG(100) < 2*C + 1
and C >= 1
```

The second call and threshold are:

```text
0x0043337F  call sub_413B90
0x00433384  cmp eax, 1
0x00433387  jl  normal_fish
```

Thus Golden Fish are eligible after the first scale. The chance rises with collection progress:

- 1 scale: 3%;
- 6 scales: 13%;
- 12 scales: 25%.

The optional patch changes only the comparison immediate at file offset `0x33386` from `01` to `0C`:

```text
cmp eax, 12
```

The original chance calculation remains unchanged. Before completion, Golden Fish are ineligible. At all 12 scales, the stock formula still gives 25%. Normal-fish selection, animations, food collection, scale collection, achievement counters, and other fishing outcomes are not modified.
