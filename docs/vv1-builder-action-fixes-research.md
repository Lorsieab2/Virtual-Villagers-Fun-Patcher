# VV1 Builder Action Fixes research

Supported executable: `Virtual Villagers - A New Home.exe`

- Size: `581,632` bytes
- SHA-256: `1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D`

## Stock scheduler behavior

VV1's adult idle scheduler begins at virtual address `0x448220`. After the
ordinary active-villager, age, nursing, and Golden Child checks, it reaches the
preferred-job branch at `0x448336`.

The stock branch compares the village food supply with 400. Below 400, it calls
the preferred-job selector at `0x439AE0` with its preference flag enabled and
passes the result to the stock work dispatcher at `0x4472C0`. At 400 food or
more, it jumps over that preferred-job attempt and proceeds to the general
selection path.

The selected-job field is at villager-record offset `+0x3D0`; value 1 is the
Building job. The villager record stride is `0x3D8`.

The Building branch in `0x4472C0` is already capable of selecting incomplete
huts, eligible repairs, and the other stock construction projects. The first
failure is therefore before construction selection: well-fed villages suppress
the assigned Builder's preferred-job attempt.

Three autonomous construction-project gates, IDs 9, 10, and 11, also called
the shared stock gate while their signed progress was zero. Those three
automatic call sites are distinct from the other six project gates and from
the manual, existing-work, and repair routes.

## Patch behavior

The guarded detour at file offset `0x48336` replaces the stock food comparison
and conditional jump with a jump into unused mapped `.text` padding at file
offset `0x568A0`.

The cave reconstructs the original comparison and:

1. preserves the stock preferred-job attempt whenever food is below 400;
2. also performs that preferred-job attempt at 400 food or more when the
   villager's selected job is Building;
3. preserves the original high-food jump for every other selected job.

The guarded calls at raw offsets `0x4753C`, `0x47568`, and `0x4759A` route only
autonomous construction project IDs 9, 10, and 11 through a common 49-byte
wrapper at raw offset `0x568D0`. The wrapper reads the project's signed progress
and:

1. tail-jumps the original stock gate at `0x442090` when progress is greater
   than zero;
2. rejects zero or negative progress and resumes at raw `0x4754A` for ID 9,
   raw `0x47576` for ID 10, or raw `0x475D1` for ID 11;
3. leaves the other six project gates and all manual, existing-work, and repair
   routes byte-identical.

The positive path leaves the original call frame untouched for the stock gate.
The rejection path consumes the same 16-byte frame before jumping to the
reviewed caller continuation. The wrapper changes only volatile `EAX`/`EDX`;
the caller's `ECX` receiver and nonvolatile registers are preserved.

The patch does not select a construction target itself. It reuses the stock
preferred-job selector, Building dispatcher, action queues, progress logic,
skill awards, project requirements, and completion handlers. The shared idle
scheduler is used during ordinary play and elapsed-time catch-up; only IDs 9,
10, and 11 gain the signed-positive progress eligibility check.

The executable size is unchanged, every original byte is guarded, and the PE
checksum is recomputed after patching.
