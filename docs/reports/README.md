# Audit and research reports

Plain-text reports written while auditing and extending the Virtual Villagers Fun Patcher.

| File | Contents |
|---|---|
| `audit-final-report.txt` | Full audit of v1.35.40 onward and the fixes through v1.35.44: every defect, its cause, fix and evidence level. |
| `hidden-game-rules.txt` | 167 rules the five games apply but never tell the player (thresholds, rolls, catch-up behaviour), read from each game's code. |
| `island-event-conditions.txt` | The exact conditions each island event needs in all five games (who must exist, ages, technologies, puzzles, timers), what it then does, and the developer-dead events. Traced from the executables; not yet checked in a running game. |

Local folder paths have been generalised. Evidence levels in the reports: *live* = seen in a running game, *emulated* = the game's own code executed in tests, *traced* = read from the executable.
