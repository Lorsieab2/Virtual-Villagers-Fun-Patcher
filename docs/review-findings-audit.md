# Review findings audit

Every unresolved bot review finding in this repository, checked against `main`.

This replaces an earlier "P1 findings audit" that reviewed 17 of 66 findings
and described the rest as covered by later commits. That was not evidence —
a later commit on the same pull request need not touch the finding at all —
and review pointed out four further defects in it: the two counts disagreed,
the collection recipe read only the first page of inline comments, it never
queried review summaries at all, and it asserted a crash retest that the
README still calls unresolved. All of that is fixed by redoing the audit
rather than patching its conclusions.

## Scope

**Every** review thread on **every** pull request — merged, closed and open —
not only P1, and not only merged. A finding raised on a closed PR is still a
finding about code that may be in `main`.

At the start of the sweep: **239 unresolved bot review threads across 109
pull requests.** Of those, 87 already carried a substantive non-Codex reply
but had never been marked resolved, and 152 had no reply at all.

That 87 matters more than it looks. **Replying to a review thread does not
resolve it.** GitHub only clears a thread through the `resolveReviewThread`
mutation, so a year of careful answers can leave every thread open, and any
"unresolved findings" count includes them. Both people working this
repository had made that mistake.

## How the list was collected

Not with `gh api .../comments` and `gh pr view --json comments`. The first
returns only the first page unless `--paginate` is given, and the second
returns issue comments — review summaries live under `reviews` /
`latestReviews`, and inline findings under `reviewThreads`, so that pair
silently misses most of the data.

One paginated GraphQL query over all pull requests, walking `reviewThreads`
and their comments, and classifying each unresolved thread by whether a
non-Codex reply exists:

```graphql
query($cursor: String) {
  repository(owner: "Lorsieab2", name: "Virtual-Villagers-Fun-Patcher") {
    pullRequests(first: 25, after: $cursor,
                 orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title state
        reviewThreads(first: 100) {
          nodes {
            id isResolved isOutdated
            comments(first: 20) {
              nodes { databaseId author { login } path line body }
            }
          }
        }
      }
    }
  }
}
```

Two traps worth naming. The outer page needs its own cursor loop, or the audit
stops at the 25 newest pull requests. And `gh api graphql` output must be
decoded as UTF-8 explicitly — finding bodies carry badge markup and curly
quotes, and the default console codec drops them.

## How each finding was judged

Against the current tree, never against the pull request's own diff. The
patcher has changed enough that most old findings are genuinely superseded,
so the question is always "is this true of `main` today?", and the answer is
recorded with the evidence that settles it — the current code, the current
test, or the reason the construct no longer exists.

Three outcomes are legitimate, and they are not interchangeable:

- **Fixed** — the tree no longer has the defect, with the line or test quoted.
- **Moot** — the code, mode or file the finding concerns is gone or
  unreachable, with the proof of unreachability quoted.
- **Acknowledged, not fixed** — the finding is correct and still applies. This
  is left **open**, not resolved.

A finding is never closed because it is old, because a later commit touched
the same file, or because it would be inconvenient. Where a review was wrong,
the reply says so with evidence; where it was right and a previous reply
argued back, the reply says that too.

## Current state

| | count |
| --- | ---: |
| unresolved at the start of the sweep | 239 |
| resolved: already answered, never marked resolved | 87 |
| resolved: verified, answered with evidence | 151 |
| **open: correct and not yet fixed** | **1** |

The one open finding is [#200's deferred-Barrel capacity
recheck](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/pull/200).
VV1 and VV2 check capacity when the Barrel is bought and then defer delivery
by 180 ticks and 90 frames respectively, without rechecking. A birth landing
in that window can cost one or two of the three children the player paid
75,000 for.

It is open rather than fixed because the safe fix is not cheap: the delivery
helper runs from the main loop, and VV1 reaches the village object only as
`[menu_object + 0x0C]` with no global holding it, so a recheck needs a pointer
captured at purchase and stored. That pointer goes stale if the player loads
another village during the delay, and calling into a stale object in a
delivery path with a crash history trades a short-count Barrel for a possible
access violation. Reproducing the race to verify a fix means landing a birth
inside a three-second window in a live game.

## Two corrections to the earlier audit

**The VV2 crash is not retested.** The old audit said the owner had retested
Time Warp and Food Point Doubler in The Lost Children and that they no longer
crash. Nothing supports that, and `README.md` still carries the warning and
still calls the crash unresolved. The claim is removed; the README remains
authoritative.

**VV5 does not ship `194400 / speed`.** The old audit recorded that as
satisfying a finding. It was the bug: the engine clamps any pending slice over
23800/31000/38200 down to 31000 at `0x0046FFCB`, so no clock-only write
reaches the intended advance at any speed, and a larger delta yields a
*smaller* warp. Time Warp now runs in the companion and was measured in the
running game at 3.00 / 6.00 / 12.00 years on slow / normal / fast.

## Reproducing this

`scripts` has no audit tool; the query above is the whole method. To act on a
thread, reply through
`repos/{owner}/{repo}/pulls/{n}/comments/{id}/replies` and then resolve it:

```graphql
mutation { resolveReviewThread(input: {threadId: "..."}) { thread { isResolved } } }
```

Resolve only threads whose finding is actually addressed. An open thread is
information; a thread resolved without a fix is a lie that costs someone a
re-derivation later.
