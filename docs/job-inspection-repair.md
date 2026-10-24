# Job-card inspection startup deadline repair

## Evidence and confirmed cause

User-observed live sequence: entry -> job -> job_review -> job_confirm. The
confirmation delegated inspection to Investigator, which returned
`extraction_timeout` after 2062 ms. The card stayed on job_review with
`inspection_unavailable`. No live process or database was inspected for this fix.

The traced path is `Cards.dispatch(job_confirm)` -> `Cards.job_result` ->
`Coordinator.delegate` -> typed `PolicyInspectionRequest` -> Investigator's
`inspect` SDK handler -> `asyncio.to_thread(inspect_policy, policy_id)` -> child
Python interpreter and actual `load_policy` PDF parser.

Before repair, `inspect_policy` used `subprocess.run(... --worker ...)` with a
two-second timeout covering process startup, imports, extraction and exit.
Quotes/recommendations already used `inspect_policies`, with a versioned readiness
frame after dependency imports and a separate five-second startup bound.
The single-document path had missed that repair.

Reproduction used the actual card, coordinator and Investigator SDK handlers,
freshly generated temporary PDFs and a real child process. The usual test harness
substitution of in-process `load_policy` was explicitly restored to production
`inspect_policy`. Only the child bootstrap redirected the registry to temporary
PDFs and injected controlled delays. No extraction results or evidence were mocked.
Before modifying production code, an injected 2.1-second startup delay reproduced
`extraction_timeout` at **2015 ms**, with the same card transition and fallback.
The regression failed as intended: **1 failed, 1 deselected in 6.66 s**.

This confirms the single-document startup/deadline defect and reproduces the live
symptom. It does not establish the exact import/extraction breakdown of the earlier
live request, which had no phase timing. Delayed startup below is a controlled
cold-start simulation, not a claim that every natural startup exceeds two seconds.

## Repair and boundaries

`inspect_policy(id)` now calls `inspect_policies([id])[0]`. Every caller therefore
uses the existing versioned readiness handshake, bounded process startup and
independent per-PDF deadline. Investigator, direct `/inspect`, the standalone
inspection command and stress inspection all receive the repair. Quote and
recommendation batch logic is unchanged. The internal legacy `--worker` child
switch remains compatible; runtime parents now use `--batch-worker` even for one PDF.

No deadline values were increased: startup remains five seconds, extraction
remains two seconds per PDF, and outer coordinator deadlines still apply.
Registry allowlisting, byte/page/report limits, actual-byte SHA-256, fresh PDF
parsers, clause/page evidence checks, document/version validation and failure
codes remain in force. The existing kill/wait, reader join and pipe cleanup are
reused. No cached report, alternate extraction, automatic retry or partial finding
is introduced.

On inspection failure, the card re-renders the same job review, explains that the
details are saved, and creates a fresh scoped, expiring **Check policy** token.
The old one-shot token remains used. Retry requires a new user action; it does
not submit an application or make a payment. The trace still reports
`job_review -> job_review`, accepted input and `inspection_unavailable`.

Cancelling the SDK handler or waiting card request retains existing cancellation
semantics: `to_thread` cannot stop a running thread immediately. The isolated
child still reaches the bounded extraction deadline and the parent reaps it and
closes its pipes. A real-child cancellation regression verifies this cleanup and
that the coordinator removes its pending request without accepting findings.

## Local measurements and verification

First post-repair real-handler measurements (milliseconds):

| Case | Worker startup | Per-PDF extraction | Card confirmation total |
| --- | ---: | ---: | ---: |
| No injected delay | 625 | 16 | 688 |
| Injected 2.1 s startup delay | 2734 | 16 | 2797 |

Additional real-handler measurements:

- Injected 5.1 s startup delay: rejected during startup at **5016 ms**, before
  `load_policy` began. The five-second bound remains enforced.
- Injected 2.1 s extraction delay after readiness: startup **625 ms**, rejected
  during extraction at **2000 ms**. The PDF deadline remains enforced.
- Startup/extraction/malformed-PDF failures each preserved all submitted review
  rows, returned no report, closed/reaped the child and succeeded on an explicit
  fresh-token retry after removing the test fault.
- Successful real-worker confirmation checked the actual PDF hash, validated
  every cited excerpt against its extracted page, retained `EMP-02` evidence and
  displayed the 31-day employer-cover gap. No quote or payment was created.
- Existing-personal and candidate `/inspect` commands also exercise the real
  coordinator/Investigator/worker path.

Parent timings use the existing monotonic clock; some short extraction samples
round to 0 ms on this Windows Python runtime. These are local observations, not
a live latency guarantee. The successful extraction assertions also compare
actual evidence and hashes; a rounded timing does not substitute for extraction.

Final checks executed against the repaired code:

- `.\.venv\Scripts\python.exe -m pytest -q -s tests/test_inspection_workers.py tests/test_quote_workers.py tests/test_policy_pdf.py tests/test_policy_rules.py tests/test_cards.py tests/test_card_routing.py tests/test_recommend.py tests/test_stress.py`:
  **222 passed in 44.53 s**. This includes all eight new real-worker inspection
  cases, existing real-worker quotes and recommendation/stress/card regressions.
- `.\.venv\Scripts\python.exe -m pytest -q`:
  **457 passed in 69.12 s**.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **passed**.
- `git diff --check`: **passed**.
- Required `graphify update .`: AST-only, no API cost; **1033 nodes / 3261 edges /
  45 communities**. Updated `graph.json`, `graph.html` and `GRAPH_REPORT.md`.
  This refreshes code relationships, not semantic extraction of the new prose.
- `graphify diagnose multigraph --max-examples 1`: zero missing/dangling
  endpoints, exact duplicates or collapsed edges in the saved graph. One existing
  self-loop remains; this diagnostic does not prove absence of producer-side loss.

The final focused run repeated the successful delayed-start card path at **2672 ms
startup / 2719 ms total**, with a sub-clock-resolution extraction sample displayed
as **0 ms**. Startup expiry was **5000 ms** and extraction expiry **2000 ms**.
Existing repeated quotes succeeded at **672/688/671 ms** without injected delay
and **2781/734/766 ms** with the first startup delayed 2.1 seconds. All six quotes
were temporary-test operations; zero payments were created in these quote cases.

## Exact live retest (manual; not performed here)

1. Stop the currently running local backend with **Ctrl+C**. Keep its existing
   configuration, identities, seeds and database. Do not reinstall or reset it.
2. In PowerShell, restart the existing backend:

   ```powershell
   Set-Location C:\Users\swapn\Desktop\coverwise
   .\.venv\Scripts\python.exe -m coverwise.live
   ```

3. In ASI:One, direct-mention the same agent and send `/cards`. Use the fresh menu
   to select **I'm changing jobs**. Tokens from the previous process are stale.
4. Enter last working day `2026-12-31`, new-cover start known with date
   `2027-02-01`, current cover **Unsure**, and sample policy **Harbor Employer
   Health** (`existing-employer`). Select **Review details**.
5. Verify the review retains these values, then select **Check policy**.
6. Expect a detail card citing `EMP-02`, the employment-end date and the 31-day
   employer-cover gap. It must retain uncertainty about personal protection and
   must not invent an illness event or promise coverage. No purchase is needed.
7. Inspect local operational logs: `pdf_worker_startup` must report readiness
   with `deadline_s=5.000`, then `pdf_extraction policy_id=existing-employer`
   must report success with `deadline_s=2.000`; the delegation must succeed and
   `job_confirm` must leave job_review without `inspection_unavailable`.
8. Repeat with a fresh `/cards` journey, then send `/inspect existing-personal`
   to check the shared single-document path. Optionally send `/recommend preset`
   and `/quote preset` to verify the existing batch journeys; do not approve a
   purchase. A quote is a new persisted sandbox operation.
9. If a genuine startup/extraction timeout occurs, record its phase and elapsed
   time. Expect the same job review with unchanged values and a fresh **Check
   policy** action. Select that latest action once to retry. The previous consumed
   token must not delegate again. Do not induce delays or edit PDFs in the live
   installation just to force this failure; those cases are covered offline.

Live retest remains pending. No `.env` access, live startup, network/model calls,
SDK upgrade, live database reset, staging or commit was performed for this repair.
