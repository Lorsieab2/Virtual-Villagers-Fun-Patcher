# VV3-VV5 fullscreen modal owner-transition evidence gate

This additive gate is disabled and publication-false. It emits no patch and
does not convert the existing VV3/VV4 wrapper hashes or historical menu reports
into runtime proof. VV5 has no current static wrapper hash in this contract.

Every Tech, Detail, Full Mastery, Full Heal, and other active modal-upgrade
route remains STOP until exact stock executable and complete-folder identity is
recorded and the following are proved together:

- SDL_Window is distinguished from HWND. A validated same-process HWND is
  captured before leaving the game modal state and reused for DialogBox and
  MessageBox ownership.
- Monitor work-area centering and clamping are demonstrated. SDL_GetWindowFlags
  has an exact calling convention and mask; leave/enter callees and their state
  byte have exact ABIs.
- The singleton, outer object, engine, SDL_Window, and HWND identities are
  freshly reacquired. The original target return is preserved.
- Every successful leave has exactly one guarded restore on every exit,
  including target failure and restore failure. Destructor and TLS cleanup are
  covered.
- Windowed and fullscreen receipts exist for cancel, no-op, success, failure,
  foreground-owner change, and restore failure on every route.
- Hook/cave ownership, parent order, byte ranges, and overlaps are proved for
  the complete composition.

The current per-game gap matrix is:

| Game | Static candidates | Runtime evidence | Principal gap |
| --- | --- | --- | --- |
| VV3 | Tech/detail/page hashes recorded | Empty | Complete owner transition, route matrix, full-folder identity, cleanup and composition |
| VV4 | Tech/detail/page hashes recorded | Empty | Complete owner transition, route matrix, full-folder identity, cleanup and composition |
| VV5 | None | Empty | Static wrapper plus all owner-transition and nonresponsive Tech/Detail route evidence |

The machine-readable contract is
`data/fullscreen_owner_transition_evidence.json`; its schema and validator are
`data/fullscreen_owner_transition_evidence.schema.json` and
`src/fullscreen_owner_transition_evidence.py`.
