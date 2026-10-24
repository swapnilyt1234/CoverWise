# Sandbox verification — 2026-10-24 (local date)

Implemented separate typed Coordinator → Provider workflow messages and real
SQLite fictional-insurer operations. No new dependency, SDK upgrade, live startup,
model call, network call, registration, publication, staging or commit. No `.env`
read or change, seed/identity change or overwrite of user runtime data. Existing
recommendation decisions and bounded extraction worker are retained.

Files added: `src/coverwise/sandbox.py`, `sandbox_contracts.py`, `sandbox_ui.py`,
`sandbox_demo.py`, `tests/test_sandbox.py`, `docs/sandbox.md` and this record.
Integration edits: `src/coverwise/agents.py`, `provider.py`, `transport.py`,
`policies.py` (command discovery), `.gitignore`, `README.md`,
`docs/architecture.md`, `communication.md`, `recommendations.md`, `verification.md`.
Required generated graph files were updated under `graphify-out/`. Catalogue,
source fixtures, original PDF bytes, dependency pins and live identity settings
were not changed.

## Observed offline flow

Executed with actual original PDFs and real production UTC clock:

```powershell
.\.venv\Scripts\python.exe -m coverwise.sandbox_demo --database runtime/sandbox-final.sqlite3
```

Exit 0. The harness invokes actual typed SDK protocol callbacks with local
contexts; it never constructs outbound-capable agents. This establishes local
orchestration and persistent transaction behavior, **not live transport**.
For each outcome it requested a fresh quote, explicitly applied, approved the
returned unpredictable challenge, repeated that same approval, reconstructed
Provider/Coordinator contexts using the same sender/session and database, retrieved
status and repeated status. The final two status calls returned the same payment.

| Test mode | Actual quote | Actual application | Before restart | Status after restart |
| --- | --- | --- | --- | --- |
| success | q-e6f8595d851440b496ab835236349e86 | a-54646b791c5c40e1b81d721a1c0f6471 | completed | completed |
| failure | q-680d30d18e9e42efb73b40eaaddfb35d | a-37393aafd90e4b3e8b63e08248b96b3d | failed | failed |
| unknown | q-6772e2789237485e874144723c134678 | a-8b14d7b61e3842fe87532ba66a0290d6 | payment_pending, no confirmation | completed through ledger reconciliation |

Success confirmation: `demo-a7b8ff7883a243789a965a3cf1626d0c`.
Unknown-mode reconciled confirmation: `demo-2de005f7e2c24eaf82a8be149d8638c2`.
Failure has no confirmation and its authoritative ledger amount is zero.
Success and unknown each have one 2,200,000-paise sandbox effect. Repeated approval
created neither another payment nor another ledger effect. All completions carry
**Sandbox/demo — no real policy issued. No real money moved.**

Actual final database counts, also independently queried after execution:

| Table | Records |
| --- | ---: |
| quotes | 3 |
| applications | 3 |
| revisions | 3 |
| approvals | 3 |
| payments | 3 |
| payment_ledger | 3 |
| operations | 18 |

Database schema version is 1. Runtime files are ignored and not staged.
These references belong only to that offline scope; they are not valid ASI:One
credentials or reusable live instructions. Approval challenges are not stored in
this report or database, only hashes are persisted.

The exact preset is documented in [sandbox commands](sandbox.md). It computes
₹22,000 annual premium under `eligible-family-list-v1`, using current eligibility,
budget, requirement, disclosure and document agreement checks. First quote was
created `2026-10-23T20:42:18.384758+00:00`, expiring exactly fifteen wall-clock
minutes later. Simulated cover dates remain 2027-01-01–12-31, illness wait January
1–30 inclusive, first post-wait day January 31. Immediate January 15 illness is
excluded; sandbox completion does not remove it.

Horizon PDF v1 SHA-256:
`1be9dd15f828d1c35733ce48ba111d712133656d282353678ba1d615829d0dd7`.
The persisted quote retains actual extracted evidence. Policy period uses p1
HOR-01 `ev-31c5de6202769f222e96778f`; eligibility/room use p2 HOR-02 and fresh
wait/premium basis p3 HOR-03. Source evidence/excerpts are unchanged and remain
retrievable through `/inspect candidate-horizon` and the existing detailed
`/recommend-evidence candidate-horizon 3 preset` command. No policy limits stack.

Two earlier new-database demonstrations also finished with the same 3/3/3/3/3/3/18
counts. Redirecting both native stderr INFO logs and stdout through Windows
PowerShell in one run returned a shell NativeCommandError despite complete
success output and database counts. The final unredirected command above was
rerun to establish a clean exit 0 without overwriting those databases.

## Checks

| Exact command | Observed result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; 69 packages resolved in 2ms. Initial restricted run could not open the existing external uv cache lock; approved offline rerun succeeded. |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0, uagents 0.25.5, core 0.4.12, AgentChatProtocol 0.3.0. Local compatibility only. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **269 passed in 66.37s**, no skips (219 baseline + 50 sandbox cases). |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 41 files already formatted. |
| `.\.venv\Scripts\python.exe -m coverwise.sandbox_demo --database runtime/sandbox-final.sqlite3` | Exit 0; actual results and counts above. |
| `graphify update .` | Exit 0; 638 nodes, 2,015 edges, 32 communities; AST-only, no model tokens. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, self-loops, duplicates or same-endpoint edge collapse in saved graph. |

Required initial graph query and final path query were executed. The undirected
path is SandboxRequest → provider.py → SandboxProvider (extracted import edges).
AST updates cover code relationships; semantic PDF/doc contents were not rebuilt.
Community labels use hub fallbacks without an LLM. The saved-graph diagnostic
does not establish absence of earlier producer-side edge suppression.

Git status remains the pre-existing untracked project tree (`??` for source,
tests, docs, fixtures, graph artifacts and configuration files). `git diff --stat`
is empty because these files are untracked; nothing was staged or committed.
`git check-ignore` confirms runtime database/output files are ignored. No
dependency installation blocker or remaining offline check failure.

Tests use temporary generated PDFs/databases and injected clocks for expiry
boundaries, but the demonstration uses real PDFs and the real wall clock. The
Provider implementation, SQLite payment effects and constraints are exercised,
including four concurrent approvals through separate Provider instances.
No test uses outbound-capable SDK agents or a network call. Local SDK routing tests
are separate from the unobserved live workflow.

Coverage includes quote budget/expiry boundaries; invalid applications; no payment
without approval; wrong sender/session/challenge; changed price, plan, members,
start or revision; exact scenario binding; duplicate/concurrent approval;
definite failure; unknown response and missing-authoritative-effect handling;
restart/idempotency; cancellation; crash after durable approval; lost resource
reply; historical quote reuse prevention; and Provider timeout after both quote
creation and actual purchase, followed by status recovery without another payment.

## Pending user observations and limits

Updated user observation: live sandbox completion and the same result retrieved
after a reported agent restart:

- Application `a-310fa446c9da4f009584b3b96bfee088`
- Payment `pay-5eb98e585db544d5b059094951ef0191`
- Transaction `txn-f9e46a57ff35410895e2aae0b7caf87b`
- Confirmation `demo-778b006354b14ac99d0a4184b73fa6e6`

This is user-observed live completion and restart/status recovery, separate from
offline tests and prior detailed-evidence/existing-cover advice observations.
**Live duplicate-purchase verification remains unobserved.** Live definite-failure
and unknown-outcome reconciliation are also unobserved. PDF visual review remains
pending. No claim of real issuance, verified identity, real money movement or
claim approval. The newer [presentation slice](presentation.md) records UI changes.

Scope isolation depends on retaining the original observed ACP sender and envelope
session. A fresh session cannot retrieve records even with the reference; there
is no migration/recovery identity system. Local database/process access is trusted.
The mock ledger deliberately shares the SQLite transaction with payment state;
real remote payment/insurer integrations require additional authorization and
reconciliation design and are outside this milestone. Exact next user-run tests
and configuration names are in [sandbox](sandbox.md#offline-and-next-user-run-live-tests).
