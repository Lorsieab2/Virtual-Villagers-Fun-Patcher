# VV5 protected candidate-test runtime

`tools/vv5_protected_test_runtime.py` is a local-only test runner for the VV5
candidate checks. It is test infrastructure, not a patcher route or a candidate
builder. It does not change source behavior, catalogs, routes, native bytes,
package folders, playtest folders, saves, or generated candidate files.

## Local dependencies

The runner searches only inside the declared repository root for wheel files
whose distribution names normalize to `keystone-engine` and `capstone`. The
normal local checkout keeps these protected, untracked wheels under `.tools`.
Use `--wheel-root` when the local wheel directory is known:

```powershell
& 'C:\path\to\python.exe' tools\vv5_protected_test_runtime.py `
  --repo-root . `
  --wheel-root .tools\keystone-runtime `
  --wheel-root .tools\capstone
```

Exactly one wheel for each dependency must be visible. Missing dependencies and
multiple matches stop before the candidate test is loaded. An explicit
`--keystone-wheel` or `--capstone-wheel` may select a repository-local wheel
when a checkout contains more than one version.

No package installer or package index is used. Each selected wheel is hashed
and extracted into a temporary directory after path-traversal and link checks.
The temporary child interpreter runs with isolated/user-site-disabled flags,
imports both dependencies before the VV5 test module can insert its legacy
`.tools` paths, and blocks network connection calls. The temporary directory is
removed when the run completes.

## Windows ACL-safe local staging

The runner consumes wheel files; it does not consume an already extracted
`keystone` or `capstone` package directory. If a checkout contains protected
or account-owned `.tools` directories, copy the existing local wheel files into
a repository-local, ignored directory that the current account can open, such
as `.tools\protected-wheels-readable`, and pass that directory with
`--wheel-root` (or pass the two explicit wheel paths). Verify that both wheel
files can be opened before running the helper. Do not use an inaccessible
`keystone-runtime`, `local-python-packages`, or `test-deps` directory as
dependency evidence, and do not repair its ACL as part of this test workflow.

The protected VV5 Full Mastery candidate suite requires only Keystone and
Capstone. A validator that imports `pefile` may add a repository-local
`--pefile-wheel` and `--require-pefile`; the child then imports all three from
the selected temporary runtime. Missing or unreadable wheels stop cleanly with
`network_access: false`; no installer or ACL repair is attempted.

## VV5 candidate validation

The default test is the repository's existing static VV5 candidate suite:

```powershell
& 'C:\path\to\python.exe' tools\vv5_protected_test_runtime.py `
  --repo-root . `
  --wheel-root .tools\keystone-runtime `
  --wheel-root .tools\capstone `
  --test-path tests\test_vv5_full_mastery_candidate.py
```

The command prints a JSON receipt containing the repository commit, selected
wheel paths and SHA-256 values, test output, `network_access: false`, and
`writes: []`. A missing wheel reports `STOP_MISSING_LOCAL_WHEEL`; a nonzero
candidate-test result reports `FAIL`. Neither result is runtime/player proof or
publication approval. The runner does not launch a game or access saves.

The checked-in helper tests cover missing-dependency fail-closed behavior,
repository-local deterministic discovery, and unsafe wheel-member rejection:

```powershell
& 'C:\path\to\python.exe' -m unittest discover `
  -s tests -p test_vv5_protected_test_runtime.py -v
```
