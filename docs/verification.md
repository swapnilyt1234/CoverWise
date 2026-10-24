# Milestone 2 verification record

Latest repair: [native callback routing and stage diagnostics](card-routing-repair.md)
records **449 passing tests**, including **101 focused card/routing/diagnostic
tests**, with Ruff passing. Generated existing-personal callbacks reach review and
real SDK recommendation delegation. Active entry replay no longer silently resets
the form. The precise incoming live path was not identifiable from the prior
coarse logs; revised stage logs distinguish it. The user observed the home menu
and example form render; the repaired live round trip remains pending.

Prior repair: [guided card UX and confirmation metadata](card-ux-repair.md)
records **433 passing tests**, including **158 focused card/sandbox/diagnostic
tests**. The extra `approved` flag is strict callback metadata rather than an
editable form field or purchase authority. Progressive intake leaves unknown
dates/disclosures unknown and defers illness scenarios. Ruff lint and formatting
pass. Revised live screens/callbacks remain pending user observation.

Prior repair: [argument-free card entry whitespace](interactive-cards.md#card-entry-whitespace-repair)
records **421 passing tests**, including **97 focused coordinator/card/diagnostic
tests**. Card entry emits actual MetadataContent for LF/CRLF/spaces and exact
self-mention variants. Diagnostic payload whitespace and callback authorization
remain unchanged. Ruff lint and formatting pass. Live retest remains pending.

Prior slice: [native Interactive Cards](interactive-cards.md) records **401 passing
tests**, including **19 focused card tests**, plus Ruff lint and formatting checks.
Actual handler functions and temporary SQLite verify duplicate-click idempotency
and timeout/unknown reconciliation. Native ASI:One rendering and live card callbacks
remain unobserved; earlier user-observed command completion/restart recovery is
separate evidence.

Latest repair: [quote worker startup deadline](quote-extraction-repair.md) records
**382 passing tests**, plus Ruff lint and formatting checks. Real Provider SDK
handlers, generated PDFs and temporary SQLite reproduced startup timeout and
verified repeated quotes after repair. Live retest remains pending.

Prior repair: [generated application command validation](apply-command-fix.md)
records **374 passing tests**, plus Ruff lint and formatting checks. Its live
retest remains pending; the reported command succeeds locally without a line
ending, and the reproduced LF/CRLF parser defect is fixed.
Prior fix: [deterministic policy follow-up](policy-followup-fix.md) records 360
passing tests. Live corrected follow-up testing remains pending.
Prior slice: [natural-language verification](conversation.md) records 353 passing
local tests with mocked model HTTP; live natural-language parsing remains pending.
Prior review preparation: [rehearsal/package verification](preparation-verification.md).
Prior [details pagination repair](details-pagination.md) records 290 passing
tests and independently parseable, lossless JSON record pages. The prior
[presentation verification](presentation.md) records 288 passing tests,
actual temporary renders and the user-observed live completion/restart recovery.
Live duplicate-purchase verification and PDF visual review remain unobserved.
The earlier [sandbox verification](sandbox-verification.md) records 269 passing
tests and actual SQLite flows. The earlier
[recommendation timing repair](recommendation-timing.md) records the
reproduced timeout, repair, measurements and live retest steps. The prior
[candidate recommendation verification](recommendation-verification.md)
records the three-agent implementation, executed offline results, 200 tests and
separate pending live/visual checks. Earlier entries below are historical.

This document preserves historical milestone observations. The latest dated
stress-test entry at the end supersedes earlier dependency and PDF blockers;
live observations are kept separate from offline verification.

Milestone 2 verified 2026-10-23 and remains complete for its local foundation scope.
No live Agentverse/ASI:One connectivity has been tested. During milestone 2 no agents were
constructed or started; no services, registration, model calls, credentials,
private keys, PDFs, insurance decisions, purchases, cards or frontend were used.

## Installation history and environment

Codex previously encountered socket error 10013 while fetching official PyPI;
DNS resolved both official package hosts, but TCP connections were denied. The
enforcing component remains unknown. No security, proxy, certificate or system
settings were changed. Those earlier failures were connection failures, not
reported dependency conflicts.

The user subsequently ran `uv lock` and `uv sync --locked --dev` successfully in
ordinary PowerShell, reporting 66 resolved packages and 65 installed packages,
including CoverWise. During final verification, the real `uv.lock`, installed
package metadata, imports and tests were observed locally. No dependencies were
reinstalled, no network diagnostics or resolution retries were performed, and no
dependency declarations were changed. Pydantic `>=2,<3` resolves with the pinned
`uagents==0.25.5`; no independent core or Pydantic override was needed.

- Base Python: `C:\Users\swapn\AppData\Local\Programs\Python\Python312\python.exe`.
- Verified executable: `C:\Users\swapn\Desktop\coverwise\.venv\Scripts\python.exe`.
- Python version: 3.12.0. uv version previously observed: 0.13.1.
- uv verification uses process-local `UV_CACHE_DIR=<workspace>\.uv-cache` to
  avoid the previously denied default cache lock, and explicit offline mode.

| Installed distribution | Verified version |
| --- | --- |
| coverwise | 0.1.0 |
| uagents | 0.25.5 |
| uagents-core | 0.4.12 |
| pydantic | 2.14.1 |
| openai | 3.37.0 |
| python-dotenv | 1.2.4 |
| pytest | 9.1.1 |
| ruff | 0.17.2 |

## Executed local checks

| Command | Exit | Result |
| --- | ---: | --- |
| `uv lock --check --offline` | 0 | Lock current; resolved 66 packages locally |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | 0 | Required models import; AgentChatProtocol 0.3.0 confirmed |
| `.\.venv\Scripts\python.exe -m pytest -q` | 0 | 22 passed |
| `.\.venv\Scripts\python.exe -m ruff check .` | 0 | All checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | 0 | 10 files already formatted |

The full test suite executed: 20 parameter-expanded contract cases and two doctor
failure-path cases. No tests or meaningful validations were removed or weakened.
Initial checks all passed, so no source or formatting fixes were necessary.
Documentation was corrected and graph artifacts refreshed, then the complete
local verification was repeated successfully.

The doctor's observed SDK output includes:

```text
SDK symbol: ChatMessage
SDK symbol: ChatAcknowledgement
SDK symbol: TextContent
SDK symbol: MetadataContent
Protocol: AgentChatProtocol 0.3.0
PASS: local SDK compatibility only; no live integration verified.
```

## Instructions, Git and limits

Applicable instructions in `C:\Users\swapn\AGENTS.md` were reread. An existing
Graphify graph was queried before source inspection; `graphify update .` refreshed
the generated artifacts using installed tooling. No additional tooling was
installed. These graph operations are local and do not establish live integration.

Git remains on `master` with no commits, staging, remotes or publication. All 18
project files, including the user-generated `uv.lock`, remain untracked. The
virtual environment, caches, secrets and runtime outputs remain ignored. Existing
source and dependency files were preserved.

Only milestone 2 is complete. Agent handlers, structured transport between agents,
ACP session handling, live discovery, PDF delivery, cards/callback validation,
insurance reasoning, persistence and sandbox purchase execution remain absent or
untested as appropriate. Pre-event development eligibility remains unconfirmed.
Milestone 3 work is recorded separately below.

## Milestone 3 diagnostic slice (2026-10-23)

New transport models inherit the SDK Model (Pydantic v1 compatibility API), while
existing domain contracts remain Pydantic v2 and unchanged. Real SDK coordinator
and investigator handlers, bounded correlation/deadline state, an explicit live
ACP/mailbox entry point and async ASI explanation adapter are implemented.
No SDK version/dependency changes or installations were needed. The new handler
unit tests use controlled contexts; they are not claimed as transport evidence.

Initial verification exposed an incorrect DeliveryStatus import, corrected to
the installed `uagents_core.types`, and formatting issues corrected by Ruff.
No existing tests or validations were removed. The complete suite now has 44
executed passing cases: the original 22 plus 22 communication/configuration/model
failure tests. They cover sender/session/request correlation, duplicate and late
responses, timeout/cancellation cleanup, capacity/delivery failure, ACP early
acknowledgement/no ack loop, unsupported input including resources, deterministic
results, local-smoke refusal and mocked ASI timeout/authentication errors with
zero retries. No real model endpoint was contacted.

### Actual transport experiment and blocker

An initial in-process SDK experiment used real Context.send serialization,
dispatcher delivery, agent queues, and concurrent handlers. It observed:

- Request `2ec61c68-6cf2-48a5-a402-fa61157de034`: ACP acknowledgement and preserved
  session, count 22, SHA-256
  `c9c5acf5eaf20a9651076b9d6b4b5419d6e569452ebb161307f69da18d777120`.
- Request `26834cbb-78b5-465f-9032-6082bb43784a`: ACP acknowledgement and preserved
  session, count 8, SHA-256
  `a913b97e85538840b612fdf32a993ed74f351dd83a5cb8b3b112e4fc8dfca15f`.
- Stopped investigator receiver: acknowledgement, explicit timeout/error with no
  hash, zero pending entries. Receiver/handler tasks closed, routes removed,
  temporary directory removed and no private-key files left in the project.

However, six SDK ledger-unavailable warnings revealed unintended constructor
ledger probes, so that run is **rejected as local-only acceptance evidence**.
Inspection confirmed Agent.__init__ unconditionally calls get_almanac_contract,
which queries versions; neither no endpoints nor mailbox=False nor a custom
registration policy suppresses it. Agent.setup also posts active status at startup.
The probes were a missed constructor side effect, not an authorized live action;
that unsafe local launch path was removed and not repeated. No agents were
registered or published, no ASI model API was called, and no live chat occurred.

The final `python.exe -m coverwise.smoke` exits **2 / BLOCKED** before construction
with the exact SDK limitation. It starts no tasks/listeners, reads no credentials,
does not patch SDK internals or mock delivery, and attempts no fallback. Strict
local-only actual-agent verification remains blocked pending a supported SDK
lifecycle or separately reviewed compatibility approach. No SDK pins were changed.

### Final verification

| Command | Result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; 66 packages resolved locally |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; unchanged installed baseline and AgentChatProtocol 0.3.0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; 44 passed |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; formatting current |
| `.\.venv\Scripts\python.exe -m coverwise.smoke` | Exit 2; blocked safely before SDK constructors |

Graph queries preceded source inspection; required `graphify update .` refreshed
the generated artifacts after code changes. Git remains on master without commits,
staging or remotes. Existing source and user-generated lockfile are preserved.
See `docs/communication.md` for exact modules, environment names, manual mailbox
steps, live launch command, two-turn ASI:One procedure and SDK source evidence.

| Evidence | Status |
| --- | --- |
| Strict local-only actual transport | Blocked; experimental run rejected for outbound constructor probes |
| Handler/configuration behavior | 44 total unit tests passing |
| ASI model API | Mocked HTTP failures tested; live call not performed |
| Mailbox registration/discovery | Not performed or observed |
| ASI:One conversation | Not performed or observed |

The milestone slice implementation and unit checks are ready, with the explicit
local-only execution limitation above. Live integration is unverified. No policy
analysis, Provider Agent, purchases, cards, frontend or broader workflow was built.

## Mailbox provisioning name fix (2026-10-23)

The user reported that RegistrationRequest rejected the configured 33-character
coordinator name. The installed `uagents_core.registration.RegistrationRequest`
name field requires 1-32 characters. The live entry point now passes
`COORDINATOR_NAME = "CoverWise Diagnostic"` (20 characters) to Agent.

A focused regression test validates that configured constant using TypeAdapter
with the installed RegistrationRequest name FieldInfo, and confirms rejection of
the former overlong value. It does not construct an agent, load `.env`, use
credentials or make network calls. Seeds, addresses, routing and dependency pins
were not modified. No mailbox provisioning or registration was retried here.

Executed after the fix:

| Command | Actual result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; 45 passed in 5.44s |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 18 files already formatted |

Applicable ancestor instructions were reread and the existing graph queried
before source inspection. `graphify update .` refreshed artifacts after the fix.
This addresses the observed name validation failure; successful live mailbox
provisioning remains unverified by Codex.

## Live ACP input diagnostics (2026-10-23)

The user reports ACP publication and a usage reply in ASI:One, but available
terminal evidence contains startup messages only. Successful mailbox connection,
the actual incoming ACP payload, and diagnostic execution remain unverified.

There is one source location for the usage reply: Coordinator.chat in
`src/coverwise/agents.py`. After accepting at most eight supported blocks and
checking the concatenated text length, it returns the unchanged string
`Connectivity diagnostic only. Use /diagnose <nonempty text>.` when either:

- Text does not start with the exact `/diagnose ` prefix (case-sensitive, with
  its trailing ordinary space). No text/metadata-only messages also reach this path.
- Text has that prefix but the remaining payload is empty or whitespace-only.

Unsupported blocks and oversized text produce different replies. The exact
`/diagnose CoverWise connectivity` string is accepted in a focused local test.
No conclusion can yet be drawn about what ASI:One actually delivered, which
process/address handled it, or whether the displayed text came from this handler.
UI rendering of the angle-bracket placeholder is also unverified. The parser was
not broadened; case, prefix matching, block concatenation, payload slicing and
whitespace preservation are unchanged.

### Confirmed logging configuration defect

`internal_agent` constructs the investigator with log_level=WARNING. Installed
SDK Agent.__init__ calls set_global_log_level for that nondefault level, which
sets all existing named loggers, including coverwise, to WARNING. The earlier
basicConfig(INFO) call does not restore that named logger. This explains why
CoverWise INFO diagnostics can be suppressed; it does not prove delivery failed.

The live run now configures the coverwise logger after both SDK constructors,
with an INFO stream handler and propagation disabled to avoid dependence on root
logging or duplicate output. An event=logging_ready marker confirms visibility.
An offline test invokes the real SDK logging helper, then verifies that the live
configuration restores visible INFO output without duplicate handlers. No Agent
is constructed by this check.

### Metadata-only diagnostics

INFO events now record message/request IDs, envelope session UUIDs, block types
and text lengths, exact-prefix matching, parser acceptance/rejection reasons,
ack/delegation/reply send outcomes, accepted investigator results and delegation
completion/timeout. At most eight blocks are summarized, with truncation marked.
For unsupported/excess blocks, exact_prefix=None means not evaluated, not false.
Reply IDs are linked back to incoming IDs by reply_ready; diagnostic_result links
incoming IDs and investigator request IDs. Session IDs remain routing context,
not authenticated identity.

No raw text, metadata values, resource URLs, measurements, reply/model payloads,
SDK delivery detail/endpoint fields, credentials, headers or exception messages
are logged. Send exceptions log only their class and are re-raised unchanged;
SDK delivery statuses are recorded without changing routing or control flow.
No seeds, addresses, dependencies, parser behavior or .env contents were changed.

The test suite now has 60 passing cases, including 15 metadata/privacy/logging
cases. These are local unit tests, not evidence of mailbox or ASI:One success.
Final pytest, Ruff lint and Ruff format checks were run; all exited 0.
Graph queries preceded inspection and graphify update refreshed required artifacts.
No agents were started, no network calls were made, no .env file was opened, and
no registration, publication, staging or commit occurred during this change.

### Next user-run observation

Stop the existing process with Ctrl+C and restart it in your ordinary PowerShell
terminal with the same local secret configuration; do not paste secrets here:

```powershell
Set-Location 'C:\Users\swapn\Desktop\coverwise'
.\.venv\Scripts\python.exe -m coverwise.live
```

After event=logging_ready, send `/diagnose CoverWise connectivity` once in
ASI:One. Capture these metadata lines from that attempt:

1. acp_received: message_id, session, block_count, block_types and text_lengths.
2. ack_send: outcome (or exception/error_type).
3. parser: exact_prefix, accepted and reason.
4. delegation_start, delegation_send, delegation_result and delegation_end
   (outcome=timeout if it expires), plus diagnostic_result correlation.
5. reply_ready, reply_send and chat_complete; acp_ack_received if observed.

For the exact canonical text in a single text block, expect text_lengths=[32]
and parser exact_prefix=True accepted=True reason=accepted. Additional allowed
metadata/start-session blocks do not themselves contribute text. If logging_ready
appears but acp_received does not, there is no handler-entry evidence for that
attempt; absence does not identify the mailbox/routing cause. If parser rejects,
its reason identifies the local branch without disclosing the input. Send status
is the SDK's classification, not proof of an ASI:One-visible reply. Capture any
mailbox connection success/failure outcome separately, redacting URLs/tokens or
other secrets from SDK startup output before sharing it.

## Optional exact leading self-mention (2026-10-23)

New user-provided live evidence shows one text block of length 99, delivered
acknowledgement/reply and missing_exact_prefix rejection. The entered direct
command has length 32, and ASI:One displayed a leading address mention. This
supports investigating a wrapper but does not confirm the received prefix.
The leading self-mention explanation remains unconfirmed pending structural logs.

Installed source confirms Context.agent returns AgentRepresentation, whose address
property is the receiving agent's configured address. The parser now uses
`ctx.agent.address` directly; no hardcoded live address, additional setting, agent
construction or live entry-point change was needed.

Supported forms:

- `/diagnose <payload>`
- `@<this coordinator's exact address> /diagnose <payload>`

Only one exact leading self-mention plus one ordinary separator space is removed.
Command-prefix matching remains exact and case-sensitive. Every character after
`/diagnose ` is delegated unchanged; strip is used only to reject an empty or
whitespace-only payload, never to rewrite it. Other mentions, arbitrary prose,
repeated mentions and extra whitespace before the command remain rejected.
The incoming size ceiling adds only the prefix length actually removed; normalized
command length must still fit the original command plus 4096-character payload
bound. Wrong wrappers cannot borrow the self-mention size allowance.

Parser INFO logs now include:

| Field | Meaning |
| --- | --- |
| exact_prefix | Original concatenated text begins with `/diagnose ` |
| self_mention_match | Exact `@` + receiving agent address + single space matched |
| normalized_exact_prefix | Text after removing at most that one prefix begins with `/diagnose ` |
| mention_prefix_length | Length of the expected exact self-mention prefix, including separator |
| removed_prefix_length | That length if matched, otherwise zero |
| normalized_command_length | Character count after removing at most the one matching prefix |
| accepted / reason | Final parser decision |

For rejected block types/excess block count these structural fields are None
because text parsing is not evaluated. No raw input, address, arbitrary prefix,
payload, resource URL or secret value is logged. The existing session/correlation,
acknowledgement, model and transport behavior is unchanged.

Added 18 focused unit cases: direct/exact self-mention forms; wrong/prose/repeated
wrappers; separator/address near-matches; exact whitespace/Unicode preservation;
empty payloads; exact 4096 and oversized boundaries for both forms; rejection of
extra size allowance for a wrong mention; and structural log privacy. Test context
addresses vary without creating SDK agents or identities. Existing tests remain.

Actual checks after the parser change:

| Command | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; 78 passed in 3.53s |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 19 files already formatted |

Applicable instructions were reread and the graph queried before inspection;
graphify update refreshed artifacts after code changes. No .env, seed, address,
dependency pin, session/transport setting or model behavior was changed. No agent
was started, no network call made, and nothing was staged or committed.

On the next user-controlled live attempt, capture event=parser with message_id and
session plus these flags/lengths, and the usual delegation/result/reply outcomes.
For the canonical payload, both supported forms have normalized_command_length=32
and normalized_exact_prefix=True. An exact mention also has self_mention_match=True
and removed_prefix_length=mention_prefix_length; a direct command has zero removed.
These observations can confirm or reject the wrapper hypothesis for that attempt.
They do not independently establish successful diagnostic execution or ASI:One
display of the result.

## User-observed live diagnostic evidence (reported for milestone 4)

The user reports two completed ACP -> coordinator -> structured investigator
request/result -> ACP reply paths, both using envelope session
`858c46aa-5a6c-47a2-8a9e-8b344e92bcea`:

| Reported text | Reported count | Reported SHA-256 |
| --- | ---: | --- |
| CoverWise connectivity | 22 | c9c5acf5eaf20a9651076b9d6b4b5419d6e569452ebb161307f69da18d777120 |
| नमसत 🌱 (latest displayed transcription) | 8 | a913b97e85538840b612fdf32a993ed74f351dd83a5cb8b3b112e4fc8dfca15f |

The second optional model explanation timed out while its authoritative
deterministic result and ACP reply succeeded. This is evidence for these two
diagnostic round trips only, not generic agent discovery, policy analysis or
model reliability. These are user-observed results, not live actions run by Codex.

There is a transcription discrepancy: locally hashing the literal latest displayed
`नमसत 🌱` produces six code points and a different digest. The earlier fixture
spelling `नमस्ते 🌱` has eight code points and matches the reported digest. The
literal check used Unicode escapes to avoid PowerShell pipeline encoding loss.
The reported count/hash are preserved as observations; the actual live bytes
cannot be reconstructed from the latest rendered transcription alone.

## Milestone 4 implementation and dependency blocker (2026-10-23)

Milestone 4 is **incomplete**. Two editable JSON sources, a reproducible ReportLab
generator, allowlisted pypdf extraction/verification, domain extraction contracts,
typed SDK policy requests/results and readable deterministic ACP presentation are
implemented. The policy commands reuse the existing self-mention normalizer and
pending sender/request/session validation; result type and policy ID are also
checked. /diagnose regression cases remain passing. Policy extraction never calls
the model adapter. Existing seeds, address, live configuration and SDK pins remain
unchanged; .env was not opened or modified.

Declared only the necessary PDF dependencies: runtime pypdf>=6,<7 and development
reportlab>=4,<5. Neither was installed in .venv. One bounded `uv lock` attempt
using official PyPI failed fetching ReportLab with socket error 10013 (exit 2).
No network diagnostics/retries, mirrors or TLS changes followed. The old uv.lock
was preserved, not fabricated; it does not yet cover the changed declarations.

The PDF skill's artifact-operation marker ran successfully once (two planned
PDFs), immediately before attempting fixture generation. Generation returned 1
with “ReportLab unavailable”. Inspection of existing-employer returned 1 with
document_unavailable. Therefore **zero PDFs exist**, no actual extraction/hash
sample is available, and no visual inspection was performed. Neither pdftoppm nor
mutool was available on PATH. Source clause designs are not actual PDF evidence.

Current executed verification:

| Command | Actual result |
| --- | --- |
| `uv lock --check --offline` | Exit 1; resolution needs uncached metadata (reported uagents absent from selected cache); not evidence of an SDK conflict |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; unchanged SDK versions and ACP 0.3.0; this doctor checks SDK compatibility, not PDF availability |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; 93 passed, 1 skipped (real-PDF integration module) |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 24 files already formatted on final run |
| `.\.venv\Scripts\python.exe -m coverwise.generate_policies` | Exit 1; missing ReportLab |
| `.\.venv\Scripts\python.exe -m coverwise.policies existing-employer` | Exit 1; document_unavailable |

The 93 passing tests include the previous 78 and 15 new dependency-independent
rule/validation/handler cases. They do not establish actual PDF extraction.
Real-PDF tests for byte-derived terms/hash, page excerpts, changed clauses,
conflicts, malformed/encrypted/excess-page and image-only documents are present
but were skipped at module import because pypdf is absent. Two early test setup
errors from oversized automatic pytest case names on Windows were fixed with
explicit bounded test IDs; no validation/test was removed.

Offline worker limits, normalization, missing/conflict statuses and display bounds
are documented in docs/policy-inspection.md. Trust is limited to configured
synthetic assets; the worker deadline is not an OS memory sandbox. Graph queries
preceded inspection and graphify update refreshed artifacts after changes. No
agent, model, registration, publication, local transport smoke, staging or commit
was run for this milestone.

Next: run the exact ordinary-PowerShell installation/generation/verification
commands in docs/policy-inspection.md, stopping at the first failure. Actual PDF
tests must run without skips, and all generated pages need visual review before
acceptance. Only then use the unchanged `python -m coverwise.live` entry point
and manually try `/policies`, `/inspect existing-employer`, and optionally
`/inspect existing-personal` in ASI:One. Live policy inspection remained unobserved
at that historical checkpoint.

## Deterministic coverage-date slice (2026-10-23)

Starting evidence supplied by the user: dependencies installed, real PDFs
generated, 101 tests passing, live `/inspect existing-personal` returned PDF terms
and evidence with SHA-256
`8ceeaf6224499d4eb8de4d62f3444a161608260505573abcee7353800c8f7760`.
These observations supersede the earlier dependency/PDF blockers. They do not
confirm employer live inspection or visual review of either PDF.

This slice implements typed evidence-bearing date/member/termination/wait/exclusion
interpretation, deterministic assessment, same-scenario A/B comparison, delegated
SDK requests/results, offline CLI, bounded presentation and exact INR display.
No model determines assessment status. No dependency declaration or pin changed.
The only existing test expectation updated is the expanded invalid-command help;
validation and diagnostic routing assertions were retained.

Executed final checks in this workspace:

| Command | Observed result |
| --- | --- |
| `uv lock --check --offline` | Initial sandbox cache-lock denial (uv cache outside workspace); approved exact rerun exit 0, resolved 69 packages in 2ms |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0, Python 3.12.0, uagents 0.25.5, core 0.4.12, AgentChatProtocol 0.3.0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0, **147 passed in 24.36s**, no skips |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0, all checks passed |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0, 28 files already formatted |
| `.\.venv\Scripts\python.exe -m coverwise.stress preset` | Exit 0; employer excluded, personal temporal passes/overall insufficient information, 31-day employer gap |
| `.\.venv\Scripts\python.exe -m coverwise.stress member-01 2026-12-31 2027-02-01 2026-07-31 illness_hospitalization` | Exit 0; employer temporal passes/overall insufficient information, personal excluded by last waiting day |
| `.\.venv\Scripts\python.exe -m coverwise.stress preset --json` | Exit 0; full evidence-bearing report, 29725 UTF-8 bytes saved in output/stress-preset.json |
| `graphify update .` | Exit 0; final code graph 336 nodes, 932 edges, 11 communities |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, self-loops, duplicates or same-endpoint collapse in saved graph |

The 46 new cases include inclusive boundary dates, expiry independently of
termination and vice versa, waiting boundaries, absent membership, relevant
unknown/conflicting/unsupported terms, document/scenario mismatch, contiguous
dates, invalid inputs, exact scenario/result correlation, modified actual PDFs
changing decisions and hashes, evidence binding, no guaranteed coverage, and INR
formatting with fractional rupees. Existing 101 cases continue passing. Pytest
does not construct agents or make live network calls. Earlier development runs
found four stale help-text expectations; their expected text was updated to the
new command guidance. No validation or regression case was removed.

Actual CLI stdout is saved as `output/stress-preset.txt` and
`output/stress-changed-date.txt`. [Stress testing](stress-testing.md) records the
exact assumptions, source hashes, page/clause/evidence references and outcomes.
Both final readable runs exit 0, at 5192 and 5203 UTF-8 bytes respectively, below
the reply limit. The JSON preserves integer paise text and verbatim evidence.

Graph query/path/explain and required AST updates were executed. The graph tool
initially warned that its separate environment lacks pypdf; application `.venv`
extraction and real-PDF tests succeeded. No graph-tool extra was installed. The
required `graphify update .` updates code relationships only, not semantic PDF/doc
content. Community names use hub fallbacks rather than a live labelling model.
The saved-graph diagnostic cannot prove absence of earlier producer-side edge
loss. Git remains an unstaged, untracked source tree (same top-level status as
at entry); nothing was staged or committed.

Separate outstanding observations:

- Employer live `/inspect`: **unconfirmed**.
- Personal live `/inspect`: **user observed**, matching hash above.
- Visual review of every page of both PDFs: **unconfirmed**.
- Live delegated `/stress-test`: **pending/unobserved**.
- Strict offline actual-agent transport: earlier SDK constructor blocker remains;
  mocked SDK handler tests do not replace a real transport observation.

No live agents were started, `.env` read/changed, identities/seeds changed,
registration/publication performed or later milestone implemented. No installation
blocker remains for this slice's application dependencies. The exact next manual
ASI:One inputs and expected mismatch behavior are in stress-testing.md.
# Current sandbox milestone

The latest implementation and actual checks are in
[sandbox verification](sandbox-verification.md). Its observed results supersede
older milestone counts above. User-observed detailed evidence and existing-cover
advice remain distinct from the unverified full live recovery sequence. Sandbox
completion/restart recovery are now user-observed; live duplicate-purchase
verification and PDF visual review remain pending. See [presentation](presentation.md).

