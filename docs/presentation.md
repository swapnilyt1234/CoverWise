# ASI:One presentation polish — 2026-10-24

Presentation and command guidance only. Insurance interpretation, ranking,
eligibility, pricing, approval binding, transaction transitions, authorization,
timeouts and worker repair are unchanged. No runtime database was opened or
changed for this work. No schema change, dependency/SDK change, live startup,
network/model call, profile/handle change, registration, publication, staging or
commit. No `.env` access.

## Default replies and complete details

`/start` gives a short plain-language menu with copyable labelled synthetic demos.
`/sandbox` explains the workflow and shows a complete explicit-input quote example.
No executable example contains literal ellipses or placeholder identifiers.
References and approval commands always come from the Provider's actual reply;
no model rewrites identifiers, prices, conditions or commands.

- Quote: computed annual price, member summary, simulated dates/wait, actual
  immediate-event result, real UTC expiry, exact application and details commands.
- Review: all material restrictions, birth dates and synthetic disclosures,
  application/revision, UTC approval expiry, exact approval/cancellation commands.
- Completed/failed/pending: recorded state, plan/amount, actual application,
  payment/transaction and any confirmation. No active challenge expiry or
  pre-purchase requirements. Unknown outcomes say not to pay again and provide
  the exact status reconciliation command. Waiting/exclusion limits remain visible.

`/sandbox-details` accepts the returned quote/application/operation reference and
an optional page (1–64). It travels as a typed `details` action through the actual
Provider SDK protocol and existing sender/session access checks. It retrieves
the persisted record **without** resuming an approved purchase or reconciling an
unknown payment. Status retains those existing responsibilities. Details shows
independently parseable JSON pages with reference, page/total and path-labelled
records, plus generated navigation/status commands. Records contain whole values
or explicit object/array containers; oversized strings use labelled segments
with character offsets and total length. Reassembling these records recovers
unchanged material terms, full evidence/excerpts, canonical paise, versions/hashes
and application fields. The complete rendered reply stays within the existing
12,000-character bound (also enforced as UTF-8 bytes). Challenge expiry is labelled
historical; plaintext challenges are never returned by details. This corrects the
original arbitrary JSON continuation slices; see [pagination repair](details-pagination.md).

Page selection stays in presentation, outside the serialized SDK domain command.
Existing command JSON shape and persisted operation digests therefore remain
compatible. The Provider database/schema and approval binding code were not edited.

Stress replies lead with the two assessments and retain conflict/unknown findings,
wait and termination conclusions, scoped restrictions, employer-protection gap
and next actions. Repeated hashes and routine passed findings were removed from
the default summary; exact `/inspect` commands retrieve full source terms/evidence.
Recommendation summaries retain budget, eligibility/requirement failures,
unknowns, separate event dates, fresh wait, existing-cover retention and
no-suitable-option outcomes. Repeated birth-date profiles were removed. Detailed
recommendation evidence has a generated command with the same explicit inputs
and a generated next-page command. Assessment data/calculations are unchanged.

## Actual temporary renders

Local rendered quote, review, completed and pending replies in
`output/presentation-examples.md` were generated through actual offline SDK callbacks, original PDF extraction and
a temporary SQLite Provider. That temporary database was then removed. These
references/challenges are examples of actual output, not live commands.
This historical artifact is intentionally ignored and excluded from public build
artifacts because it includes consumed temporary approval commands; the current
public demo/rehearsal guides are standalone.

| Reply | Actual words |
| --- | ---: |
| Quote | 104 |
| Review | 304 |
| Completed | 74 |
| Pending | 73 |

Review deliberately retains every material restriction rather than hiding terms
to meet the approximate 250-word target. Other summaries satisfy their requested
content in fewer words. The temporary demonstration created two quotes,
applications, revisions, approvals, payments and ledger entries each, plus six
operation records; one purchase completed and one remained pending/unknown.
No existing live database or records were used.

## Observed live evidence — separate from these local tests

The user observed a live sandbox completion and retrieved the same result after
a **reported agent restart**:

- Application: `a-310fa446c9da4f009584b3b96bfee088`
- Payment: `pay-5eb98e585db544d5b059094951ef0191`
- Transaction: `txn-f9e46a57ff35410895e2aae0b7caf87b`
- Confirmation: `demo-778b006354b14ac99d0a4184b73fa6e6`

This is user-observed live completion and restart/status recovery. These
references exist only in documentation, never application behavior. **Live
duplicate-purchase verification remains unobserved.** This observation does not
establish live definite-failure/unknown recovery or the newly polished UI. PDF
visual review remains pending. Every completion remains sandbox/demo: no real
policy issued, no real money moved and no future claim guaranteed.

## Executed verification

| Exact command | Actual result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; resolved 69 packages in 2ms. |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0, uagents 0.25.5, core 0.4.12, AgentChatProtocol 0.3.0; local compatibility only. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **288 passed in 55.04s**, no skips (269 prior cases plus 19 presenter/details cases). |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; all checked files already formatted. |
| `graphify update .` | Exit 0; 662 nodes, 2,080 edges, 37 communities; code-only AST update without model tokens. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, self-loops, duplicate or same-endpoint collapsed edges in the saved graph. |

New checks cover state-appropriate commands and word bounds; no approval actions
after completion; pending status reconciliation; visible material waiting and
review restrictions; generated identifiers; complete lossless details; wrong
sender/session isolation for quote/application/operation references; read-only
details before and after approval; actual SDK delegation; page validation;
unchanged legacy command fields/digests; and read-only self-mentioned `/start`.
Existing insurance, transaction, correlation and regression cases remain passing.
No test constructs outbound-capable SDK agents or establishes live transport.

Graph query/path and required AST update/diagnostic were performed. Semantic
PDF/doc contents were not rebuilt; community labels use hub fallbacks without
an LLM. Saved graph diagnostics do not prove absence of producer-side suppression.
Git remains the same untracked project tree; `git diff --stat` is empty because
the files are untracked. Nothing staged or committed.

Changed source: `sandbox_ui.py`, `sandbox_contracts.py` (new read-only action only),
`agents.py`, `recommend.py`, `stress.py`, `tests/test_sandbox.py`. Also updated
README, architecture/sandbox/verification guides, this record, the temporary
render artifact and generated graph artifacts. No insurance fixtures/PDFs,
Provider transaction code, schema, live identities or public profile were changed.

## Next user-run ASI:One checks

In the **original sender/session**, inspect the observed record:

```text
/start
```

```text
/sandbox-status a-310fa446c9da4f009584b3b96bfee088
```

```text
/sandbox-details a-310fa446c9da4f009584b3b96bfee088
```

Completed status should contain the observed confirmation and no active approval
instructions. Details should retain full reviewed material terms/evidence and
provide its exact next-page command. A different session must be denied.

To inspect fresh quote/review presentation, send:

```text
/quote preset
```

Copy the actual generated application command. Review its terms; approval remains
a separate deliberate command. No approval is necessary to check presentation;
copy the returned cancellation command if stopping at review. Existing explicit
inputs remain documented in [sandbox](sandbox.md). Also recheck:

```text
/stress-test preset
```

```text
/recommend preset-existing
```

Copy generated evidence commands rather than typing placeholders. Do not infer
live duplicate verification from retrieval of an existing status or from offline
concurrency tests.
