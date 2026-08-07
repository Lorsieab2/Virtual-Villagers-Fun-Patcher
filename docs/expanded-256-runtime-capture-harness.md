# VV4/VV5 Expanded-256 capture harness

`scripts/capture_expanded_runtime_evidence.py` is a disabled, no-launch
capture and verification harness. It does not start an executable, open a
save through the game, change a save, enable a patch, or alter the canonical
publication contract. The current repository contains no runtime saves and
this harness has not been run against a real game folder.

## Modes

The harness has three explicit commands:

- `dry-run` prints the exact staged player plan and contract binding without
  reading a folder or save tree.
- `preflight` verifies a complete self-contained folder and optionally takes
  one no-follow snapshot of an authorized save root.
- `capture` performs the same preflight, pauses for direct player
  acknowledgements, takes a no-follow save snapshot before and after every
  checkpoint, and writes one canonical unsigned candidate packet.

There is no observation JSON import, `--yes` shortcut, synthetic-fixture
mode, or manual evidence-field option. The only observation input is the
interactive acknowledgement token shown by the harness for each checkpoint.
The player must perform the game action manually between the before snapshot
and the acknowledgement. A later independent authorized process must
authenticate the unsigned packet before it can be considered for the runtime
contract; every packet keeps publication, runtime-GO, player-GO, and
eligibility `false`.

## Dry-run

For example:

```text
python scripts/capture_expanded_runtime_evidence.py dry-run \
  --game vv4 --mode experimental_expanded_256
```

The plan binds the selected static expanded fingerprint and the exact VV4/VV5
Origins relocation count and ledger digest. It includes stock import and
conversion, expanded save/reload, offline catch-up, failed-load nonmutation,
save rotation, late records `149`, `150`, `254`, and `255`, current Origins
behavior, every relocation row, and final player receipt review.

## Complete-folder preflight

Preflight requires all nine roles. Every role path is relative, every physical
file is enumerated, every file is hashed twice, and every directory/file is
rejected if it is a symlink or Windows reparse point. Required executable and
DLL identities are checked against
`data/expanded_256_runtime_evidence.json`; supporting files are retained in
the full-folder inventory rather than silently omitted.

The role map is deliberately explicit so an incomplete or ambiguous folder
cannot be mistaken for a complete package:

```text
--role stock_executable=Virtual Villagers - The Tree of Life.exe
--role expanded_executable_immediate=Expanded Immediate.exe
--role expanded_executable_progression=Expanded Progression.exe
--role companion_dll=VVFP Origins Icons.dll
--role runtime_inventory=runtime-inventory.json
--role checksum_list=SHA256SUMS.txt
--role patch_log=candidate.patch-log.json
--role transparency_log=VVFP Transparency Log.txt
--role player_readme=README.txt
```

`stock_executable` and `companion_dll` names are exact contract names.
Expanded executables must be `.exe` files; the inventory and checksum names
are exact. The preflight result includes both the contract-compatible required
artifact inventory and a complete-folder inventory with a canonical digest.

## Save scope and capture

Only a directory whose basename ends exactly in ` - Modded` is accepted. A
non-Modded path is rejected before filesystem inspection. Save snapshots use
relative paths, no symlink/reparse following, stable double reads, file
SHA-256, and a canonical snapshot digest. The capture output path must be
outside both the game folder and save root and existing output is never
overwritten.

Example shape (the role arguments are repeated exactly nine times):

```text
python scripts/capture_expanded_runtime_evidence.py capture \
  --game vv5 \
  --mode experimental_expanded_256_progression \
  --folder "C:\\Authorized\\VV5 Complete Folder" \
  --save-root "C:\\Authorized\\Village - Modded" \
  --output "C:\\Authorized\\vv5-runtime-candidate.json" \
  --source-commit 0123456789abcdef0123456789abcdef01234567 \
  --role stock_executable="Virtual Villagers - New Believers.exe" \
  --role expanded_executable_immediate="Expanded Immediate.exe" \
  --role expanded_executable_progression="Expanded Progression.exe" \
  --role companion_dll="VVFP Origins Icons.dll" \
  --role runtime_inventory="runtime-inventory.json" \
  --role checksum_list="SHA256SUMS.txt" \
  --role patch_log="candidate.patch-log.json" \
  --role transparency_log="VVFP Transparency Log.txt" \
  --role player_readme="README.txt"
```

The example commit is a format placeholder only; capture requires the actual
full lowercase source commit. The harness does not launch either executable.
It waits for the player to complete each stage and type the exact token
`OBSERVED:<checkpoint-id>`. Stock import, offline catch-up, and save rotation
must produce a changed before/after save tree. Failed-load nonmutation must
produce an identical before/after digest or the capture stops without output.

## Candidate boundary

The emitted `vvfp.expanded_256_runtime_capture.v1` packet contains:

- exact contract binding, stock/expanded/DLL identities, required artifact
  records, complete-folder records, and full VV4 13-row or VV5 66-row
  relocation row digests;
- no-follow save snapshots and per-checkpoint deltas;
- exact late-record indices, current Origins feature identity, relocation
  count/digest, and player-confirmation references;
- fixed `player_runtime_receipt` provenance with `synthetic: false`, a full
  source commit, and a canonical receipt digest; and
- an explicit unsigned authentication state plus all publication flags false.

The packet is not a GO record. It is unsigned evidence for a later authorized
authentication/integration step. Static renders, inferred behavior,
developer-only observations, manually injected fields, non-Modded saves,
partial folders, reparse points, and failed/partial checkpoint sequences are
STOP conditions.
