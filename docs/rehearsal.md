# CoverWise rehearsal and recovery

Actions below are user-run checks, not claims that they passed. Use synthetic
inputs only and record actual outcomes separately. Keep `.env`, seed values,
credentials and unused approval challenges out of screenshots and shared logs.
No live process or workspace database was reset while preparing these guides.

## Before startup

Use Python 3.12 and the locked setup in README. From the checkout:

```powershell
uv lock --check --offline
.\.venv\Scripts\python.exe -m coverwise.doctor
Get-ChildItem -LiteralPath output/pdf -Filter *.pdf | Select-Object Name,Length
.\.venv\Scripts\python.exe -m coverwise.policies existing-employer existing-personal candidate-economy candidate-query candidate-horizon
```

Expect five allowlisted PDFs and a three-product catalogue. If assets are missing,
regenerate from the unchanged authored fixtures:

```powershell
.\.venv\Scripts\python.exe -m coverwise.generate_policies
```

Candidate hash disagreement requires inspecting/versioning the source change; do
not bypass validation. Open and inspect every PDF page manually before claiming
visual review. That review remains pending.

Preserve the existing private seeds and SDK pins. Live settings require
`ASI1_API_KEY` and the three distinct `COVERWISE_*_AGENT_SEED` variables listed in
README. The Provider seed is required. Shell environment overrides `.env`;
the new template's 15-second deadline does not alter an existing configuration.
Do not print the environment or show `.env` to diagnose configuration.

## Choose the database intentionally

For checking the **previously observed** confirmation, retain its original database
setting and original sender/session. The existing source default is
`runtime/provider.sqlite3`; do not assume that default was used if the user had a
custom setting. Do not delete or reset it. In the original conversation:

```text
/sandbox-status a-310fa446c9da4f009584b3b96bfee088
```

The user-observed result was payment `pay-5eb98e585db544d5b059094951ef0191`,
transaction `txn-f9e46a57ff35410895e2aae0b7caf87b`, confirmation
`demo-778b006354b14ac99d0a4184b73fa6e6`. This is completion and status after a
reported restart, not live duplicate-purchase proof.

For fresh rehearsal purchases, stop the backend first and select the **separate
designated demo database** in the launch shell:

```powershell
$env:COVERWISE_SANDBOX_DB = Join-Path $PWD 'runtime\demo\rehearsal.sqlite3'
.\.venv\Scripts\python.exe -m coverwise.live
```

This sets a process environment value; it does not edit `.env` or change seeds.
It intentionally selects different history. Old live references are not expected
to exist in this demo database. Keep a private note of the original database
setting; restore it exactly before checking old history. Do not point the live
default at a reset operation or copy live records into the resettable database.

## Startup and mailbox

With your chosen database setting, start:

```powershell
.\.venv\Scripts\python.exe -m coverwise.live
```

Confirm `event=configuration request_timeout_seconds` in the operational logs;
the source is `LiveSettings`, with `dotenv_override=False`. Confirm the actual
effective value, not a value inferred from a template. New installations default
to 15 seconds. Missing values or duplicate seeds must fail before construction.
Do not rotate seeds, register new specialist identities or change the public handle
to fix a configuration error.

Use the SDK Inspector link, **Connect → Mailbox**, then the existing Agentverse
profile's **Chat with Agent** entry. Keep the local process running; Agentverse is
not hosting this backend. Only the Coordinator is registered/published. Provider
and Investigator are distinct internal SDK agents with receivers in the same
process. Generic ASI:One discovery is a separate pending check.

## Live checks, one message at a time

1. Send `/start`. Check that code blocks contain complete commands, not literal
   ellipses, template brackets or a fabricated identifier. The exact single leading
   self-mention is supported; don't add extra prose before a command.
2. Optionally reconfirm ACP measurements with the following two messages. Counts
   and hashes must differ. This diagnostic may call the optional ASI explanation
   adapter; deterministic measurements remain authoritative even if explanation
   is unavailable.

```text
/diagnose CoverWise connectivity
```

```text
/diagnose नमस्ते 🌱
```

3. Rehearse the source/assessment and candidate evidence:

```text
/inspect existing-employer
```

```text
/stress-test member-02 2026-12-31 2027-02-01 2027-01-15 illness_hospitalization
```

```text
/recommend preset
```

```text
/recommend-evidence candidate-horizon 3 preset
```

4. Confirm the alternative existing-cover path remains explicit:

```text
/recommend preset-existing
```

5. Request `/quote preset`, copy its actual application command and inspect the
   current review. Keep the returned exact approval command privately for the
   duplicate test. The review must show UTC expiry, revision, members, disclosures,
   material restrictions and January 15's waiting exclusion. Do not approve a stale
   revision. Before approval, cancellation must remain available.

6. **Corrected details pagination (live still pending):** copy the generated
   details command for that quote/application. Each page's JSON block must parse
   independently and have `reference`, `page`, `total` and path-labelled `records`.
   Follow every generated next-page command; compare reference and total, check
   the previous-page command, and retrieve all evidence. Oversized excerpts use
   explicit string segments, not a broken field. See [record format](details-pagination.md).
   A local manual parse can validate the JSON object copied from one page:

```powershell
$pageJson = Get-Clipboard -Raw
$pageObject = $pageJson | ConvertFrom-Json
$pageObject | Select-Object reference,page,total
```

Select only the JSON block, without Markdown fences. Keep the clipboard private;
do not paste profile/evidence contents into an operational log. Do not infer all
pages are valid merely because page one parses.

7. **Live duplicate approval (unobserved):** use a fresh current demo review and
   its actual challenge. Send that exact approval once. After actual completion,
   send the **same approval command** again, without creating a new quote or
   review. Compare application, payment, transaction and confirmation: all should
   remain identical. An expired challenge before first execution needs a new
   review; do not edit tokens. Never use the old verified application's reference
   with an invented challenge. Record the observed duplicate result separately.

8. **Restart recovery:** save the actual status command. Ctrl+C, wait for shutdown,
   restart with the same database and seeds, wait for mailbox readiness, and send
   the saved status command in the original conversation. Compare all four
   references. Same chat UI is necessary but not proof of unchanged envelope
   session; if isolation rejects it, inspect session metadata and do not weaken
   checks or grant cross-session access. Restart/status recovery was previously
   observed; the full rehearsal sequence must still be recorded truthfully.

9. **Intentional Provider timeout then recovery (full sequence unconfirmed):**

```text
/recommend-timeout preset
```

Wait for its bounded incomplete result, then:

```text
/recommend preset
```

Only the deliberate request should log `test_silence` / injection=True. A normal
request must not be labelled intentional. Record actual elapsed time and request/
session IDs; normal intermittent failures were observed previously, and the local
repair is not itself proof of this entire live recovery sequence.

## Unknown payments and status

On a separate fresh quote, the application command's explicit demo outcome can be
`unknown` instead of `success`; obtain/review its new revision before approving.
After approval, no completion should be claimed while pending. Use the returned
**status** command to reconcile the authoritative ledger; don't create another
purchase, repeat payment or infer success from a chat timeout. Details remains
read-only. For a Coordinator timeout, use the exact operation status command in
the error reply. Late replies remain expired; Provider records survive separately.
Live unknown/failure recovery is not claimed until tested.

## Safe demo reset

Prefer a fresh separate demo history; preserve the existing live database. The
reset tool accepts **only** `runtime/demo/rehearsal.sqlite3` under this checkout.
It refuses `runtime/provider.sqlite3`, arbitrary files, traversal, symlinks/
junctions/reparse points, hard links, unknown schemas and active/locked databases.
Provider holds a shared process-lifetime lease on this designated demo path;
reset requires exclusive access even when no request is running. Other SQLite
transactions must also release their locks. Stop all backend/demo processes and
database tools before reset; don't defeat the lease.

Dry-run (default, counts only):

```powershell
.\.venv\Scripts\python.exe -m coverwise.demo_reset --database runtime/demo/rehearsal.sqlite3
```

Only after reviewing those counts, the **user** may explicitly execute:

```powershell
.\.venv\Scripts\python.exe -m coverwise.demo_reset --database runtime/demo/rehearsal.sqlite3 --execute --confirm CLEAR-REHEARSAL-RECORDS
```

This clears quotes, applications/revisions, approvals, payment attempts, mock
ledger effects and operation records in one SQLite transaction. It retains the
file and schema. It never touches `.env`, seeds, source/generated PDFs or the
existing live database. Provider creates an empty safety lease file for this
designated database; reset refuses a missing marker instead of adopting an
unmarked database. Dry-run does not change financial records. Missing databases
are not created.
No workspace database was reset during this task; safety tests use disposable
temporary databases only.

## Troubleshooting observed problems

| Symptom | Check / safe response |
| --- | --- |
| ACP accepted/acknowledged, then no result | Track Provider/Investigator stage request/session IDs and effective deadline. An ack is not completion. Don't blindly increase timeouts. |
| Normal recommendation expires, response ignored | Preserve stage timings and ignore reason (expired/sender/session/duplicate/cancelled); do not accept late results as current. Use the repaired worker and pinned SDK. |
| `/recommend-timeout` silences Provider | Expected deliberate injection only. Follow with a normal recommendation to test recovery. |
| `not_found_or_not_authorized` after restart | Verify same database, stable seeds, original sender/session; don't expose another scope or create a replacement purchase to conceal it. |
| Review/quote expired or material terms changed | Fresh quote/review/approval as directed. Never modify a challenge, price or stored application to force success. |
| Completed status shows old active challenges | Confirm updated source was loaded by the restarted process; completed status should show status/details actions only. |
| Details page is truncated JSON | Confirm updated paginator is loaded; save the scoped reference/page and JSON parse error. Do not claim live pagination passed. |
| Reset refused active/locked | Stop all holders, wait for shutdown, retry dry-run. Do not delete lease files to bypass a live holder. |
| Python/SDK import error | Use `.venv` Python 3.12, `uv sync --locked --dev`, then doctor. Do not upgrade pins during rehearsal. |

## Evidence log

For each check record date, action, actual outcome, relevant safe request IDs and
whether the step was observed or remains pending. Never log private seeds,
credentials, challenge strings, full profiles or document payloads. User-observed
evidence and local test results are separated in [preparation verification](preparation-verification.md).
Direct profile chat does not prove generic discovery; repeated status is not a
duplicate-approval test. No future claim is guaranteed by a passing date check.
