# Native ASI:One card journey

**Current screens and callback validation:** see [guided card UX repair](card-ux-repair.md).
The menu/progressive forms there supersede the original screen sequence below;
the original wire, authorization and verification notes remain historical evidence.

Job confirmation now shares the quote worker's separate startup and extraction
deadlines. If inspection fails, the current review preserves the submitted dates,
cover choice and policy, with a fresh **Check policy** action for retry and an
**Edit details** action. The failed confirmation token remains consumed. See
[job inspection repair and exact live retest](job-inspection-repair.md).

Uses the four predefined schemas in the [official ASI:One Interactive Cards
reference](https://innovationlab.fetch.ai/resources/docs/interactive-cards/asi-interactive-cards),
read on 2026-10-24 (reference version 1.0.5). No frontend, custom component,
external artwork, SDK upgrade or new dependency.

## One demo path

Restart the existing local process with its existing configuration and database:

```powershell
Set-Location C:\Users\swapn\Desktop\coverwise
.\.venv\Scripts\python.exe -m coverwise.live
```

Direct-mention the existing CoverWise agent in ASI:One and send:

```text
/cards
```

`/start` opens the same form. Select **Use fictional demo — employer-only**, then
Continue. The review visibly supplies the existing fictional preset: self
1992-04-10, spouse 1994-08-15, both synthetic absent pre-existing conditions;
₹30,000 annual budget, ₹10,00,000 shared family minimum, uncapped private room;
final employment 2026-12-31, assumed next-employer start 2027-02-01, proposed new
policy start 2027-01-01; illness illustration for member-02 on 2027-01-15 and a
separate later illness scenario on 2027-02-10. These are not inferred user facts.

1. Review the inputs and confirm comparison. This does not prepare an application.
2. The carousel shows actual computed candidate outcomes. Economy fails the room
   requirement; Query needs clarification; Horizon can qualify prospectively.
3. Open Horizon's findings and evidence, then request its computed quote.
4. The quote shows actual Provider premium, members, inclusive dates, expiry and
   illness waiting interval. January 15 remains excluded; purchasing does not
   remove the initial wait. Prepare the sandbox application.
5. Review the material restrictions, synthetic disclosures, revision and expiry.
   Full persisted terms/evidence are accessible via the actual generated
   `/sandbox-details` command before approval.
6. Deliberately click **Approve sandbox purchase — ₹22,000** only if approving
   that review. This is an additional explicit approval input route over the same
   Provider binding and transaction code; natural-language yes cannot approve.
7. The completion card shows the stable confirmation, status and evidence actions.
   Its secondary text preserves an actual status command for restart recovery.

All amounts/outcomes above describe the existing fixture preset; runtime cards
read them from actual validated catalogue/assessment/quote replies. No price,
plan-name decision or purchase result is fabricated by the adapter.

## Explicit form path and corrections

Choose **Enter my synthetic demo inputs** instead. Form 1 collects cover path,
preloaded policy, self DOB, optional spouse DOB and explicit health disclosures.
Omitted disclosures stay unknown. Form 2 collects explicit employment/start dates,
annual budget and minimum family cover in rupees, room requirement, event member
and two illustrative illness dates required by the existing comparison engine.
There is no implicit current date, health absence, default profile or policy date.
Dates are text fields labelled YYYY-MM-DD. Existing integer-paise conversion and
domain validators are reused. Invalid fields return the relevant correction form.

The Investigator inspects the selected PDF and employer PDF before review. A
different employment date cannot override the employer PDF's fixed 2026-12-31;
the correction cites the actual clause/evidence. Edit/cancel returns to form 1,
which includes **Cancel card draft**. Cancelling a draft leaves persisted records
unchanged. Application cancellation uses the Provider's existing cancel operation.

The existing-personal choice retains that cover and its unknown terms. Neither it
nor rejected/unresolved candidates receive a card quote/purchase shortcut. The
same backend determines eligibility, budget, requirements and waiting results.
Candidate details and paged evidence remain retrievable inside ASI:One.

No undocumented prefill fields are sent. Corrections ask the user to re-enter the
affected form; reviewed demo values are shown in the review, not secretly filled.

### Card entry whitespace repair

The observed live parser logged a seven-character normalized command for the
visible six-character `/cards`. Inspection confirmed that card routing was
already before the unsupported-command fallback, but its exact equality check
missed surrounding whitespace. A coordinator-handler regression reproduced
`/cards\n` falling through to `missing_exact_prefix` without any card metadata.
The logs alone do not identify the extra character.

Only argument-free `/cards` and `/start` are now matched after trimming surrounding
whitespace, and their canonical entry is passed to the card handler. No global
message stripping was added. `/diagnose` retains exact payload whitespace;
callback parsing, sender/session scope and authorization are unchanged. Twenty
coordinator-handler cases cover both commands, LF, CRLF, trailing spaces and
leading/trailing whitespace, with and without the exact self-mention. They assert
that an actual form MetadataContent response is emitted without a model/tool call.

Before repair, the new test stopped at `/cards\n`: **1 failed, 4 passed**.
After repair:

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_cards.py tests/test_acp_logging.py tests/test_communication.py`:
  **97 passed in 25.76 s**, including diagnostic payload whitespace/hash checks.
- `.\.venv\Scripts\python.exe -m pytest -q`: **421 passed in 119.51 s**.
- Ruff lint and formatting checks: **passed**.
- AST graph updated: **959 nodes / 3,012 edges / 52 communities**; diagnostic found
  no missing/dangling endpoints, duplicate edges or collapsed edges.

No live startup or live rendering test was performed for this routing repair.

## Wire, authority and lifecycle

- Each card reply has short TextContent and one MetadataContent. The four required
  metadata values are strings; payload JSON uses only documented predefined fields.
  Pydantic checks local payload shapes before sending. CoverWise also caps the
  combined fallback/metadata representation at 12,000 UTF-8 bytes, stricter than
  the reference's 64KB payload limit. Oversize result cards can fall back to the
  existing deterministic text presenter. No material transaction terms are removed
  from the approval binding.
- Every selection contains only a fixed adapter action and a random 192-bit
  token. Server-held records derive the actual typed operation, reference,
  revision and challenge. Callback-supplied extra amounts/products/challenges
  cannot alter those operations. Duplicate JSON keys are rejected.
- Records are scoped to **observed ACP sender plus envelope session**, with
  128 sessions, at most 1,024 action records, a 15-minute draft/action lifetime,
  and shorter quote/review action lifetimes. These are demo isolation boundaries,
  not verified identity or cryptographic attestation of a human click.
- Sessions serialize card work with at most four active/queued handlers and a
  bounded lock wait. Locks are never held while waiting for a user's next message.
  Edited/cleared drafts invalidate older card epochs. Clearing during an already
  authorized operation cannot undo Provider effects; its actual scoped status
  reference is returned rather than presenting stale draft actions.
- Quote, application, approval, status and details all call the existing typed
  Coordinator → Provider SDK path. Recommendations still delegate catalogue to
  Provider and document assessment to Investigator. Expected-sender, correlation,
  input, session and deadline validation are unchanged. No direct Coordinator
  database access or assessment shortcut.
- Structured callbacks are processed after acknowledgement and exact leading
  self-mention normalization, before natural-language parsing. Planner prose,
  model output and generic yes/buy-it never authorize payment. When a card session
  receives prose, the adapter gives the existing exact-command fallback; it does
  not ask the model to reconstruct an approval. Slash commands remain available.
- The existing Provider rechecks challenge, scope, revision, material terms,
  price, members, dates and expiry. Duplicate clicks serialize, then use status
  for the recorded result. SQLite payment/idempotency constraints remain the final
  authority. Unknown results offer reconciliation, never another payment.
- Completion cards retain status/evidence buttons, so they are **not terminal**.
  The helper marks pure informational details without actions terminal. No
  actionable card is marked terminal. Logs contain operational metadata only,
  never callback bodies, tokens, challenges, disclosures or profile inputs.

Drafts and action tokens are in memory and disappear on restart or `/clear-chat`;
SQLite purchases remain available through the existing scoped status command.
Save the actual generated status command before restarting. If a card no longer
works, use `/cards` for a new draft or the saved status command for an existing
transaction. Never create another payment merely because a result is unknown.

## Verification and remaining live checks

Local tests use temporary SQLite, real generated PDF terms, actual registered SDK
handler functions and validated messages. They construct no outbound-capable
agents and make no model calls. Native rendering and callback delivery in ASI:One
remain **unobserved**; local schema/handler tests cannot establish them.

Initial card-slice checks (before the entry-whitespace repair above):

- `.\.venv\Scripts\python.exe -m pytest -q tests/test_cards.py`:
  **19 passed in 23.67 s**. Covers schemas/string metadata/byte bounds, explicit
  forms, rupees with paise, omitted disclosures, date contradictions, two actual
  SDK delegation stages, wrong scope/tampering/expiry/stale revisions, concurrent
  approval replay, unknown payment, timeout/status recovery, cancellation,
  clear-during-approval recovery, bounded sessions and unchanged exact commands.
- `.\.venv\Scripts\python.exe -m pytest -q`: **401 passed in 127.69 s**.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **passed**, 61 files
  already formatted in the final run.
- `graphify update .`: AST-only rebuild, **956 nodes / 3,004 edges / 42 communities**.
  `graphify diagnose multigraph --max-examples 1`: no missing/dangling endpoints,
  exact duplicates or collapsed edges; the existing recursive self-call remains.

The duplicate-click test retrieved the same authoritative payment after concurrent
approval clicks and another repeat, with **one approval, one payment and one ledger
side effect**. Unknown outcomes and a forced coordinator timeout reconcile against
the real temporary Provider store without creating another payment. Quotes and
applications are never created by input review or comparison alone.

Changed source: `card_schemas.py`, `cards.py`, `agents.py`, `sandbox_ui.py`.
Tests add `test_cards.py`, capture ACP metadata in the existing conversation
harness, update `/start` expectations, and fix the test assessor to include the
actual personal PDF for existing-cover comparisons. The Provider, database schema,
SDK pins and insurance/transaction rules are unchanged. Git retains the existing
untracked workspace paths; nothing staged or committed.

Previous user-observed text-command completion/restart recovery remains recorded
separately. Live duplicate approval, the complete timeout-recovery sequence and
PDF visual review remain unconfirmed. No live records were reset or inspected.
