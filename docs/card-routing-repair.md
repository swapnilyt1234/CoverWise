# Native callback routing and stage diagnostics

## Reproduction and evidence boundary

The user observed the example form become Submitted, then saw the home menu
again. Prior logs used `reason=cards / outcome=card_reply` for commands, JSON
callbacks and prose, so those logs cannot identify which input arrived.

The actual coordinator-handler reproducer confirmed:

- All eight generated JSON round trips (with/without the exact self-mention and
  no suffix/LF/CRLF/spaces) already reached **Review details**, retained
  **existing-personal**, and confirmed through Provider catalogue then Investigator
  recommendation handlers. The generated form submit selection contains a distinct
  token bound to action `example`, not the earlier menu-choice token.
- Replaying `/cards` while **Try an example** is open unconditionally returned
  home and advanced the draft epoch. The new regression failed before repair:
  **1 failed, 8 passed in 27.73 s**.

This establishes a real server reset defect and reproduces the screen transition.
It does **not** prove that the live client sent `/cards`, dropped a selection, sent
another callback, or displayed a cached card. Raw live callback data was not
available and was not guessed or added to logs. Revised stage logs distinguish
those server paths on the next live attempt.

## Home-menu path audit and repair

| Path | Behavior |
| --- | --- |
| Initial `/cards` or `/start` | Opens the existing home menu. |
| Repeated entry command during an active step | Keeps stage/epoch/data; explains no form submission arrived in that command and offers **Restart cards**. |
| Explicit Back (`edit`) | Intentional home navigation, validated against the issuing stage. |
| Explicit **Restart cards** | Clears only the conversational draft generation and opens home; Provider records are unchanged. |
| Invalid/missing/unknown/expired/wrong-scope/used callback | Clear recovery message and **Restart cards**, never an implicit home fallback. |
| Invalid editable form values | Existing field-specific correction form; never home. |
| Inspection/recommendation unavailable or processing exception | Honest incomplete/recovery response, never home. |
| Valid financial-action replay | Existing authoritative status/idempotency path, never a new payment or home fallback. |
| Unstructured planner prose | Existing explicit-command fallback plus restart guidance; no model-based approval. |

ACP now passes an explicit routing source (`entry_command`, `callback`, `prose`)
after the existing exact self-mention normalization. JSON callback content is not
rewritten into entry commands. `/diagnose` payload bytes and whitespace remain
unchanged. No network/client schema was invented or changed.

Drafts now track the emitted workflow stage. Intake actions carry their issuing
stage and are one-shot; fields/selection/confirmation metadata still validate
separately. A stale menu token cannot be reused as a form submit token or trigger
Back from another stage. Failed callbacks do not reset the current draft.
Financial approval/status records retain existing replay behavior: the original
Provider challenge, revision, terms, scope, expiry and SQLite idempotency remain
authoritative. Repeated approval still returns the recorded result.

## Privacy-safe logs

Each card attempt emits `event=card_transition` with:

- `source`, server-held `action`, `prior_stage`, `next_stage`;
- `validation` and a fixed `fallback_reason`;
- envelope session UUID for correlation with existing ACP/tool logs.

Validation here describes the callback/state checks, not insurance eligibility or
claim/payment success. Error recovery preserves the active workflow stage. Examples:

```text
source=callback action=entry prior_stage=entry next_stage=example validation=accepted fallback_reason=none
source=callback action=example prior_stage=example next_stage=input_review validation=accepted fallback_reason=none
source=callback action=confirm prior_stage=input_review next_stage=results validation=accepted fallback_reason=none
```

Useful failure reasons include `entry_during_active_flow`, `missing_selection`,
`invalid_selection`, `invalid_confirmation_metadata`, `unknown_or_wrong_scope`,
`expired_or_stale`, `already_used`, `wrong_stage`, `form_validation` and
`internal_error`. Unresolved client action values are never logged. Request-local
trace context prevents concurrent requests from sharing validation/fallback flags.
No tokens, raw JSON/prose, form values, health data, profiles or challenges are
logged. Tests assert this, including a private marker in a simulated exception.

## User-run retest

Executed local checks:

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_card_routing.py tests/test_cards.py tests/test_acp_logging.py`:
  **101 passed in 39.13 s**.
- `.\.venv\Scripts\python.exe -m pytest -q`: **449 passed in 136.84 s**.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **passed**.
- `graphify update .`: AST-only rebuild, **1,011 nodes / 3,184 edges / 57 communities**.
  Multigraph diagnostic: no missing/dangling endpoints, exact duplicates or
  collapsed edges; one existing recursive self-call remains.

Changed runtime files: `cards.py` and ACP source classification in `agents.py`.
`test_card_routing.py` adds the serialized coordinator round trips, guarded entry
replay, recovery/expiry/scope/used-token/exception checks and privacy-safe logging
assertions. The existing card test helper explicitly chooses Restart when starting
a different flow. No backend engine, SQLite schema, transaction records, SDK pins,
identity, secret configuration or existing card layout changed. Git retains its
pre-existing untracked workspace paths; nothing staged or committed.

Stop the old local process with Ctrl+C and restart with existing configuration,
identities and database:

```powershell
Set-Location C:\Users\swapn\Desktop\coverwise
.\.venv\Scripts\python.exe -m coverwise.live
```

Direct-mention the existing agent and send:

```text
/cards
```

Choose **Try an example** → **Employer and existing personal cover** →
**Review details**. Expect **Review details**, retaining existing personal cover.
Then **Compare plans** should return actual candidate results. This existing-cover
path retains cover and has no card purchase shortcut. If the form does not reach
review, use only the non-sensitive stage log fields above to identify the path;
do not copy tokens, challenges or full callback payloads into logs.

No live agent was started for this repair. Native live callback success remains
pending user observation. Prior user-observed rendering is evidence for those
screens, not proof of this repaired round trip or live duplicate purchase behavior.
