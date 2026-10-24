# CoverWise

CoverWise helps an employed household understand what happens to health protection
when a job ends, compare independent cover against stated requirements, and take
a concrete next step through a **fictional insurer sandbox**. It reads authored
policy PDFs, cites clauses, evaluates explicit dates deterministically, and can
prepare a quote and application that require deliberate approval before a mock
payment. **Sandbox/demo ? no real policy issued. No real money moved.**

The target user is someone changing jobs who needs to distinguish an employer
protection gap from a gap in all protection. A shortlist is prospective: buying a
new policy does **not** make its initial waiting period disappear or cover the
illustrative January 15 illness event.

## Review and submission links

| Item | Current value |
| --- | --- |
| Public GitHub repository | https://github.com/swapnilyt1234/CoverWire |
| Agentverse coordinator profile URL | **not yet supplied** |
| Public coordinator address/handle | **not yet supplied**; copy from the user's existing Inspector/profile |
| Public ASI:One shared chat URL | **not yet supplied** |
| Demo video | [Watch the CoverWise demo](https://drive.google.com/file/d/12QJ1qEMCWN3aixjitWpUJvVtVy4q07iH/view?usp=sharing) |

Entries marked **not yet supplied** remain placeholders. Local coordinator name in code:
`CoverWise Diagnostic` (legacy name retained to preserve identity). Internal
specialists have no separate registered profiles in this implementation.

## Live communication and synthetic scope

Three distinct SDK agents run in one local Python process with distinct stable
seeds and typed SDK messages:

| Agent | Responsibility | Actual boundary |
| --- | --- | --- |
| Personal coordinator | ACP acknowledgement, explicit input validation, orchestration and presentation | ASI:One chat via its Agentverse mailbox; validates expected sender, request ID, session, type and deadline |
| Provider | Versioned catalogue; authoritative quotes, application revisions, approval/payment records and status | Separate SDK handlers; SQLite transactions and idempotency constraints |
| Investigator | PDF extraction/evidence; deterministic stress and candidate assessment | Separate SDK handlers, bounded worker process with fresh PDF parsers |

Recommendation flow is Coordinator ? Provider catalogue ? Investigator assessment
? evidence-backed comparison. Sandbox commands delegate Coordinator ? Provider;
the Coordinator does not execute a purchase or query SQLite directly. Internal
specialists use SDK dispatch/receiver queues and are **not separately registered**
on Agentverse. Agentverse connects the mailbox/registry; it does not host this
whole local backend. The local process must remain running and connected.

Actual PDF extraction, SDK handlers, dates, quote computation and SQLite mock
payment effects are implemented. Every policy, insurer, premium, disclosure and
profile in the fixtures is fictional. No real insurer/payment APIs, payment-card
processing, Agent Payment Protocol or separate frontend are implemented. Native
[Interactive Cards](docs/interactive-cards.md) are a thin adapter over these tools;
The start menu and example form rendered in user-observed ASI:One tests; repaired
form submission remains pending. ASI:One provides the conversation surface.
The ASI1 adapter proposes a small validated
intent/field schema for natural language and optionally explains `/diagnose`.
It never determines insurance findings, dates, money, consent or payment status.
Code validates verbatim input spans and dispatches only allowlisted typed actions.
The quick conversational slice is bounded; all exact commands remain available.

User-observed live evidence includes diagnostic delegation with distinct results,
personal PDF extraction, stress/wait/conflict handling, candidate evidence and
existing-cover advice, quote/review/explicit approval/sandbox completion, the same
completed payment after a reported restart, and concise completed status.
**Not yet confirmed:** corrected details pagination live, duplicate approval live,
the full intentional-timeout/recovery sequence, generic discovery and PDF visual
review. Native card rendering/callbacks also remain unconfirmed. Local tests do
not establish those observations.

## Windows setup (Python 3.12)

Install Python 3.12 and uv separately. In PowerShell, from the checked-out project:

```powershell
Set-Location C:\Users\swapn\Desktop\coverwise
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
uv venv --python 'C:\Users\swapn\AppData\Local\Programs\Python\Python312\python.exe' --no-python-downloads .venv
uv sync --locked --dev
.\.venv\Scripts\python.exe -m coverwise.doctor
```

The explicit Python executable above is the observed installation on this machine;
select your own installed Python **3.12** path on another machine. Do not use the
machine's default Python 3.14. `uv sync --locked --dev` installs the checked-in
`uv.lock` without upgrading SDK pins; do not regenerate the lock for setup. Initial
installation needs package availability/network; subsequent cached checks can run
offline. The app requires Python `>=3.12,<3.13`, uagents 0.25.5 and ACP 0.3.0.
ReportLab is a development dependency for reproducible fixture generation.

## Private local configuration and startup

Create the ignored configuration **only if it does not already exist**:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

Edit `.env` privately on your machine using the blank template. Never paste its
contents into chat, logs, a video or a public repository. Reuse existing seeds and
settings; do not overwrite or rotate identities for rehearsal.

| Configuration name | Purpose |
| --- | --- |
| `ASI1_API_KEY` | Required by live startup; structured intent parsing and diagnostic explanation |
| `COVERWISE_PERSONAL_AGENT_SEED` | Stable coordinator seed |
| `COVERWISE_INVESTIGATOR_AGENT_SEED` | Distinct stable Investigator seed |
| `COVERWISE_PROVIDER_AGENT_SEED` | Distinct stable Provider seed; required, not reserved/unused |
| `COVERWISE_REQUEST_TIMEOUT_SECONDS` | Optional per-tool deadline, default 15 seconds, allowed 0.05?30 |
| `COVERWISE_SANDBOX_DB` | Optional SQLite path; source-checkout default `runtime/provider.sqlite3` |

All three seeds must be nonempty and distinct; missing/duplicate values fail before
agent construction. Existing process environment overrides `.env` (`override=False`).
The corrected template uses 15 seconds; it does not change an existing `.env` or
inherited setting. Startup logs the effective deadline without printing secrets.

User-run live startup (not performed while preparing this package):

```powershell
.\.venv\Scripts\python.exe -m coverwise.live
```

Keep the process alive. Open the Inspector link printed by the SDK (port 8001),
use **Connect ? Mailbox**, and follow the existing account's connection flow.
Confirm mailbox/ACP manifest readiness, open the existing Agentverse profile,
then choose **Chat with Agent** to enter ASI:One. Preserve the current public
handle/profile; this preparation does not register or edit it. Inspector UI labels
may vary. Direct profile chat is distinct from unconfirmed generic discovery.
The SDK's live constructor makes network/ledger probes; do not call this entry
point for an offline test. Inspector uses the SDK's default interface, so use a
trusted machine/network.

## ASI:One demonstration

You may instead ask “I'm leaving my company in 3 days. Will my insurance continue?”
The agent delivers a privacy notice before the first ASI parse, asks which sample
policy to inspect and confirms the explicit final date before assessment. The PDF's
fixed termination date is never replaced by that relative date. Use synthetic
information only; `/clear-chat` clears the expiring draft, not persisted records.
Say “Show me the job-change demo” to review a fictional profile and dates, then
“run synthetic demo” to use them. No personal question silently loads a preset.
See [natural-language usage and limits](docs/conversation.md).

For the native card demo, direct-mention the existing agent and send `/cards`.
Choose **Try an example**, then **Employer cover only**, review details, compare, open
Horizon's findings, request a quote, prepare/review the application, and deliberately
approve the sandbox purchase. January 15 illness remains excluded by the wait.
`/start` opens the same three-choice menu. Job-change questions ask dates and cover
first; plan requirements and an optional illness scenario are separate steps.
See [current card screens and safeguards](docs/card-ux-repair.md).
Use `/clear-chat` to leave the card draft and resume natural-language intake.
During an active card step, repeating `/cards` offers **Restart cards** while
preserving the pending form. See [callback routing diagnostics](docs/card-routing-repair.md).

Exact commands remain available; send one at a time in the same conversation:

```text
/start
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

```text
/quote preset
```

The quote returns an actual application command. Copy it, inspect the resulting
review, then copy the exact generated approval command **only if approving that
sandbox review**. Save the returned status/details commands. Do not type template
brackets, ellipses, a bare yes, or reuse another review's challenge. Advice alone
never creates an application or purchase.

The labelled recommendation/quote demo uses two synthetic adults (self born
1992-04-10, spouse born 1994-08-15), no declared pre-existing conditions, ?30,000
annual budget, ?10,00,000 minimum shared family limit and uncapped private room.
Final employment is 2026-12-31, assumed new-employer protection 2027-02-01,
proposed independent cover 2027-01-01, event member `member-02`, immediate illness
2027-01-15 and separate later event 2027-02-10. New-employer insurance is an
unverified scenario assumption. Horizon's new wait is January 1?30 inclusive;
January 31 is the first post-wait day, not a promise of claim payment.

Other commands: `/policies`, `/inspect existing-employer`, `/inspect existing-personal`,
`/stress-test` and `/recommend` for explicit-input syntax, `/recommend preset-low`,
`/recommend preset-clarify`, `/recommend preset-existing`, and
`/recommend-timeout preset` for deliberate Provider silence. `/sandbox` explains
explicit quote inputs. Generated `/sandbox-details` commands return complete,
independently parseable JSON record pages; generated navigation retains access
checks. Details is read-only; status performs authoritative reconciliation.

[Timed demo script](docs/demo-script.md) ? [Rehearsal and recovery](docs/rehearsal.md) ?
[Submission checklist](docs/submission-checklist.md)

## Offline tests and demonstrations

Latest repair: [native callback routing](docs/card-routing-repair.md),
**449 tests passed** with Ruff lint and formatting passing. Live submit/review retest is pending.
The preceding [guided card UX repair](docs/card-ux-repair.md) passed 433 tests.
The preceding [card-entry whitespace repair](docs/interactive-cards.md#card-entry-whitespace-repair)
passed 421 tests.
The preceding native card slice passed 401 tests.
The preceding [quote worker startup repair](docs/quote-extraction-repair.md)
passed 382 tests.
The preceding [generated application command repair](docs/apply-command-fix.md)
passed 374 tests.
The preceding [policy-selection repair](docs/policy-followup-fix.md) passed
**360 tests** with Ruff passing. The preceding natural-language
slice also passed offline lock check, doctor
and Ruff checks. These are local results, separate from live observations.

```powershell
uv lock --check --offline
.\.venv\Scripts\python.exe -m coverwise.doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m coverwise.policies existing-employer existing-personal
.\.venv\Scripts\python.exe -m coverwise.stress preset
.\.venv\Scripts\python.exe -m coverwise.recommend preset
.\.venv\Scripts\python.exe -m coverwise.recommend preset-existing
.\.venv\Scripts\python.exe -m coverwise.recommend preset --provider-timeout
.\.venv\Scripts\python.exe -m coverwise.sandbox_demo
```

The sandbox demo defaults to a temporary database, exercises actual SQLite code
and original PDFs, and checks repeated approval/status across new Provider
instances. Recommendation/sandbox harnesses use actual typed SDK callbacks with
local contexts, **not live agents or network transport**. Doctor validates local
imports/protocols only. `coverwise.smoke` intentionally returns BLOCKED because
the pinned SDK cannot construct a strictly offline actual agent without probes;
it is not a successful transport test.

Five allowlisted PDFs and six JSON fixtures are included in the wheel and source
archive. Regenerate PDFs from the authored JSON (development dependencies needed):

```powershell
.\.venv\Scripts\python.exe -m coverwise.generate_policies
```

Generation checks candidate hashes against the catalogue. No OCR, arbitrary PDF
upload or general policy-language parser is supported. [Fixture design](docs/fixtures.md)
and [rules/evidence](docs/stress-testing.md) explain the limited authored syntax.

## Rehearsal data and limits

Prefer a new separate `runtime/demo/rehearsal.sqlite3` for rehearsal. An offline
reset command defaults to dry-run and only accepts that designated path; it
refuses the live default, unsafe aliases and active/locked databases. It retains
the database/schema and clears only demo financial records after explicit
confirmation. No reset was performed on workspace/live records during preparation.
See [safe reset procedure](docs/rehearsal.md#safe-demo-reset).

Authorization uses the observed ACP sender plus envelope session as an isolation
boundary, **not verified personal identity**. Keep the same conversation, seeds
and database for restart recovery. A new session cannot retrieve another scope's
records. Quotes expire on the real UTC wall clock; cover dates are simulated.
Changing terms requires a new review/approval. Unknown payment responses must be
reconciled through status, never blindly paid again. Policy limits do not
implicitly stack, passed dates do not guarantee claims, and keeping existing
personal cover or obtaining missing terms may be preferable to a new purchase.

The insurer, quotes, ledger and confirmations are fictional and local. Process
uptime, network/mailbox availability and the limited parser constrain the demo;
there is no real underwriting, issuance, payment or claims settlement. Pre-event
development eligibility requires organizer clarification.

Official deliverables were checked on 2026-10-24 against the
[Fetch-A-Thon 3.0 hackpack](https://www.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack).
See the [preparation verification](docs/preparation-verification.md) for actual
checks, packaging inspection, publication exclusions and unresolved actions.
