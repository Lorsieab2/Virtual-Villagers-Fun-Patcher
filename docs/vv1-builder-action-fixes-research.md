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

The selected-job field is at villager-record offset `+0x3D0`; value 4 is the
Building job. The preferred-job selector's own switch at `0x439CAC` maps 1 to
Farming (`+0x3C4`), 2 Parenting (`+0x3BC`), 3 Research (`+0x3CC`), 4 Building
(`+0x3C0`) and 5 Healing (`+0x3C8`) -- skill names measured in the owner's
running game -- and the dispatcher's case 4 is the Building branch. The patch
compared with 1 until v1.35.35, so its high-food bypass went to
Farming-preferring villagers instead of Builders. The villager record stride is `0x3D8`.

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
autonomous construction project IDs 9, 10, and 11 through a common 48-byte
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
skill awards, project requirements, and completion handlers. The idle scheduler is
used during ordinary play; elapsed-time catch-up calls the Building dispatcher
directly from its worker (0x42E790), so the 400-food gate is live-only; only IDs 9,
10, and 11 gain the signed-positive progress eligibility check.

The executable size is unchanged, every original byte is guarded, and the PE
checksum is recomputed after patching.

## Removed: the new-hut progress gate (v1.35.42)

The owner: "The builders will prioritize fixing huts OVER building the new huts
or other projects, when in fact they should build new stuff first, then fix
huts."

The earlier version of this patch also routed the three new-hut calls (IDs 9,
10 and 11, raw `0x4753C`, `0x47568`, `0x4759A`) through a wrapper at raw
`0x568D0` that allowed them only once the hut's signed progress was greater
than zero. That was modelled on the other projects, which the stock branch only
*continues* once started -- but the new huts are the one construction the stock
branch deliberately *starts* from nothing (hut 9 while incomplete, hut 10 above
22 villagers, hut 11 above 45). With the gate a builder could never start a new
hut; finding nothing else, Builders Fix Huts sent it to fix a built hut instead.
The owner's saves show the project records plainly: `(progress, complete)`
counting up to each target (hut 9 250, hut 10 400, hut 11 600).

The gate and its wrapper are gone; the three calls are the stock calls to the
hut gate `0x442090` again. The food-level discriminator above is unchanged.

## About three times in four

The owner: the patch should "increase the LIKELIHOOD of villagers doing that
action, not 100% replace them" -- 75%, once per decision. The cave at raw
`0x568A0` (now 65 bytes, to `0x568E1`) keeps the Building-job test and sends
the villager to the preferred-job attempt only when the top two bits of
`rdtsc * 0x9E3779B9` are not both clear -- three quarters of all values, since
multiplying by an odd constant permutes them; eax and edx are pushed and
popped around it, and no game routine or RNG is called. With Builders Fix Huts
When Idle selected, its companion verifies this row's exact jmp at `0x48336`
and cave bytes and points the jmp at its own equivalent stub, which asks the
decision's shared roll, so one decision rolls once. See "About three times in
four, once per decision" in `docs/builders-fix-huts.md`.
