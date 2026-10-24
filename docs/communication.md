# Milestone 3: diagnostic communication slice

Current addition: [natural language](conversation.md) proposes validated fields
before the same typed SDK operations. Exact commands skip that parser; natural
status uses read-only details. In-memory drafts are sender/session scoped and
`/clear-chat` does not delete persisted records. No new agent identity or public
handle was introduced.

Current extension: `/recommend` and `/recommend-evidence` use a distinct Provider
catalogue protocol followed by Investigator assessment. `/recommend-timeout`
deliberately withholds a Provider reply to exercise the same bounded coordinator
deadline; it does not alter catalogue decisions. See [recommendations](recommendations.md)
for exact commands and explicit fields. No recommendation calls the model adapter.

`/stress-test` displays help; `/stress-test preset` and the
five-field explicit form delegate typed `StressTestRequest`/`StressTestResult`
SDK messages using the existing pending sender/session/request/type boundaries.
The exact scenario is checked on return. Acknowledgements and exact self-mentions
use the unchanged normalizer. No model is called for this command. See
[stress testing](stress-testing.md) for syntax, limits and manual live checks.
The earlier dependency blockers below are historical. User-observed personal
inspection succeeded and the three stress scenarios were user observed; employer
inspection remains unconfirmed. Live three-agent recommendation testing is pending.

This implements the Personal Insurance Agent coordinator and Coverage Investigator
diagnostic path. Milestone 4 adds `/policies` and delegated `/inspect <policy-id>`;
see `docs/policy-inspection.md` for the current dependency/generation blocker.
The Provider supplies catalogue data and the separate persistent fictional insurer
workflow over typed `SandboxRequest/Result` SDK messages. See [sandbox](sandbox.md).
A hash/count is a
connectivity diagnostic, never a coverage finding.

## Modules and command

- `transport.py`: SDK `Model` request/result types using the SDK's Pydantic v1
  compatibility API. Existing Pydantic v2 domain contracts are unchanged.
- `agents.py`: canonical ACP handlers, coordinator correlation/deadlines and
  investigator-owned UTF-8 hash/count tool.
- `asi.py`: optional async ASI explanation of the tool result only.
- `runtime.py`: in-process investigator queues for explicit live execution.
- `live.py`: explicit live coordinator entry point; imports do not construct agents.
- `smoke.py`: fail-closed local-only smoke preflight for the pinned SDK limitation.

Send `/diagnose <nonempty text>` or
`@<this coordinator's exact address> /diagnose <nonempty text>`.
The handler uses the installed SDK's `ctx.agent.address`; it removes at most one
exact leading self-mention and its single ordinary separator space. Wrong agent
mentions, repeated mentions, extra separator whitespace, and arbitrary prose
before the command remain rejected. No command search or arbitrary trimming is
performed. Everything after `/diagnose ` is hashed as exact UTF-8, including all
remaining whitespace. Character count is Python
Unicode code points, not bytes or displayed graphemes. Maximum: 4096 characters
(at most 16384 UTF-8 bytes); invalid surrogate text yields an error. Empty input,
unknown commands, resources/attachments, and streaming/end-session blocks are
rejected after acknowledgement. Metadata and start-session blocks may accompany
text. Literal URLs after `/diagnose` are hashed as text; URLs are never fetched.
The 4096-character payload limit is unchanged. Incoming size allowance adds only
the exact self-mention overhead when that prefix actually matches.

A leading self-mention in the previously rejected live input remains a hypothesis.
On the next attempt inspect parser fields `self_mention_match`,
`normalized_exact_prefix`, `mention_prefix_length`, `removed_prefix_length`, and
`normalized_command_length`, alongside `accepted` and `reason`. Legacy
`exact_prefix` still describes the original text, so it may be False for an
accepted self-mention command. No text or address prefix is printed in these logs.

The reply is ACP text containing JSON: an explicit diagnostic label, incoming
message ID, authoritative deterministic result, and a separate optional
explanation. Failures have status `error` and null measurements. Model text never
changes measurements or dispatches tools. Local deterministic behavior is clearly
labelled; it is not live ASI reasoning. Normal turns do not send EndSessionContent.

## Routing, sessions and limits

`Protocol(spec=chat_protocol_spec)` imports canonical ACP 0.3.0 models. Incoming
ChatMessage receives ChatAcknowledgement first; acknowledgements do not trigger
acknowledgements. The coordinator reuses the incoming Context, so Context.send
retains the envelope session UUID through delegation and reply. ChatMessage has
no invented session_id field. Envelope sessions are routing context, not an
authenticated personal identity. No conversation/profile memory is implemented.

The coordinator keeps at most 16 investigator requests pending, each with a
generated UUID, expected investigator address and envelope session. Unknown IDs,
wrong senders/sessions and duplicate/late replies are ignored. A configurable
deadline includes sending and waiting. Completion, failure, cancellation and
timeout remove pending state. SDK concurrent handlers allow result processing
while a chat handler awaits it. The investigator accepts requests only from its
configured coordinator. Logs contain roles, IDs, durations and outcomes; never
supplied text, seeds, keys or model headers. Do not enable dependency debug logging
when using real secrets.

## Local-only transport limitation (important)

```powershell
Set-Location 'C:\Users\swapn\Desktop\coverwise'
.\.venv\Scripts\python.exe -m coverwise.smoke
```

This command currently returns **2 / BLOCKED**, without constructing agents,
starting tasks/listeners, loading credentials or attempting a network fallback.
It is not a successful transport test.

Installed `uagents==0.25.5` unconditionally calls `get_almanac_contract(network)`
inside Agent.__init__, even with mailbox disabled, no endpoints and a custom
resolver/registration policy. That function calls contract.check_version(), which
queries ledger contracts. Agent.setup() also schedules run_startup_tasks(), which
unconditionally posts active status. No supported constructor/startup flag was
found that suppresses both. `mark_inactive_on_shutdown=False` suppresses only the
shutdown status update. Bureau also calls get_almanac_contract and does not solve
the constructor issue. There is no report_events parameter in this installed
Agent signature; no fictitious telemetry flag is used.

An initial experimental in-process smoke delivered two distinct texts through
SDK Context.send -> dispatcher -> agent queues/handlers, observed ACP acks and
session-preserving results, exercised an investigator timeout and cleaned up.
However, constructor ledger warnings exposed outbound probes. That experiment
is **rejected as local-only acceptance evidence**, not repeated, and its unsafe
launch path was removed. No registration, model call or live chat occurred.

The final smoke intentionally refuses rather than patching SDK network internals,
mocking delivery or silently permitting outbound startup. Fully offline actual-agent
verification therefore remains blocked on a supported SDK lifecycle mechanism
or a separately reviewed compatibility approach; no SDK pin was changed.

In explicit live mode, the investigator uses only start_message_receivers(),
with no setup/server/mailbox/registration loop, disabled inspector/history/profile
publication, no endpoints, and a resolver that refuses nonlocal destinations.
Its constructor's ledger probe is still live behavior. The receiver context
manager cancels/drains owned workers/handlers and unregisters routes. Cleanup uses
the pinned SDK's _message_tasks attribute because no public stop-receiver API exists.
These lifecycle assumptions must be rechecked before changing SDK versions.

## Live setup (manual, not run by Codex)

Use synthetic diagnostic text only. Set secrets in your own PowerShell environment
or a local ignored `.env` file using `.env.example` as the blank template. Do not
paste values into this chat or source control. No secrets are generated for you.

| Variable | Purpose |
| --- | --- |
| ASI1_API_KEY | Live ASI model explanation only |
| COVERWISE_PERSONAL_AGENT_SEED | Stable coordinator identity, passed as SDK seed |
| COVERWISE_INVESTIGATOR_AGENT_SEED | Distinct stable internal investigator identity |
| COVERWISE_REQUEST_TIMEOUT_SECONDS | Optional per-tool delegation deadline; default 15, range 0.05-30 |
| COVERWISE_PROVIDER_AGENT_SEED | Required stable third-agent identity; distinct from the other seeds |

These seed names are CoverWise conventions, not SDK-required variable names.
Missing settings, duplicate seeds and invalid deadlines fail before constructors.
Only the explicit live main loads `.env`; doctor/tests do not inspect credentials.

After configuring settings locally, the user may start the live path:

```powershell
Set-Location 'C:\Users\swapn\Desktop\coverwise'
.\.venv\Scripts\python.exe -m coverwise.live
```

This is deliberately outbound-capable: it starts a coordinator with mailbox=True,
the SDK inspector on port 8001, publication of AgentChatProtocol's manifest, and
normal registration/status behavior. The pinned SDK inspector binds its default
server interface (0.0.0.0), not loopback-only; use an appropriate trusted machine.
The investigator stays in the same process and is not separately registered.
Stop with Ctrl+C. No live entry point has been started by Codex.

The ASI adapter uses the documented `https://api.asi1.ai/v1`, model `asi1`, with
AsyncOpenAI, zero retries, a five-second SDK timeout and total async deadline.
Only successful deterministic result JSON is sent to the model, never the raw
diagnostic input. Authentication/timeout/API errors produce an honest explanation
unavailable string; the observed tool result remains intact. Explanations are
optional model output, not authoritative measurements or insurance advice.

Follow the official user steps: open the Inspector link from your own terminal,
choose Connect -> Mailbox, and check the registration/manifest logs. Open Agent
Profile, configure the public diagnostic description/handle, then Chat with Agent
to reach ASI:One. These are user actions; code inspection proves none of them.

Two-turn ASI:One smoke, in the same conversation:

1. Send `/diagnose CoverWise connectivity`. Expect count 22 and SHA-256
   `c9c5acf5eaf20a9651076b9d6b4b5419d6e569452ebb161307f69da18d777120`.
2. Send `/diagnose नमस्ते 🌱`. Expect count 8 and SHA-256
   `a913b97e85538840b612fdf32a993ed74f351dd83a5cb8b3b112e4fc8dfca15f`.

Record the actual replies, correlation IDs and acknowledgement/timeout logs.
Check that the optional explanation is labelled separately and both measurements
match the actual text. Do not claim success from the inspector merely opening.

## Official references and evidence separation

Checked 2026-10-23 via the web tool; shell external connectivity was not retested:

- [Agent Chat Protocol](https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-chat-protocol)
- [ASI-compatible uAgents example](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)

Installed source, not remembered API signatures, determined the implementation:
uagents/agent.py (construction/startup/concurrent handlers), context.py and
communication.py (session-preserving local dispatch), dispatch.py (queues/routes),
uagents/protocol/__init__.py (handlers/manifest), and canonical chat models.

| Evidence field | Current observation |
| --- | --- |
| Local-only actual transport | Blocked by constructor ledger probe; experimental run rejected |
| Handler/validation behavior | Local mocked unit tests; not a transport substitute |
| ASI API | User reports second optional explanation timed out; no independent API verification by Codex |
| Mailbox registration/discovery | Diagnostic routing observed by user; generic discovery/provisioning not independently established |
| ASI:One conversation | Two diagnostic replies reported in one session; policy inspection still pending |

PDF attachment delivery, cards, identity authentication, and pre-event development
eligibility remain unconfirmed and outside this slice.
