# Foundation architecture

Current native UI: [Interactive Cards](interactive-cards.md) add predefined form,
review, carousel and detail payloads with opaque sender/session action tokens.
The adapter calls existing Coordinator SDK services; Provider remains authoritative
for approval, SQLite transactions and status. Cards add no database schema or
insurance rule and do not use the model for financial actions.

Current interface: [bounded natural language](conversation.md) reuses the same
SDK services, with expiring sender/session drafts and no natural-language purchase
approval. Prior review package: see [rehearsal/preparation](preparation-verification.md),
[presentation polish](presentation.md), [sandbox workflow](sandbox.md), [candidate recommendations](recommendations.md) and
[deterministic stress testing](stress-testing.md). Dependencies,
generation and byte-derived extraction now work. Older milestone descriptions
below reflect their implementation stage; the current verification record takes
precedence for observations.

## Eventual responsibilities

| Agent | Owns | Boundary |
| --- | --- | --- |
| Personal Insurance Agent | ASI:One conversation, profile, workflow, explicit approval | Coordinates; does not invent policy terms or execute payments itself |
| Coverage Investigator | Document extraction, clause evidence, deterministic scenarios and comparisons | Reports missing terms and limitations; does not approve purchases |
| Provider Agent | Versioned catalogue, validated quotes, application revisions, approvals, sandbox ledger and status | Authoritative SQLite state; no real insurer/payment API |

All identity data and products are synthetic. Purchases are sandbox-only.
General banking and real insurance sales are outside scope.

## Layout and current boundaries

- `src/coverwise/contracts.py`: domain data and structural validation only.
- `src/coverwise/doctor.py`: offline installed-version and ACP model diagnostic.
- `tests/test_contracts.py`: validation and serialization checks.
- `src/coverwise/agents.py`, `transport.py`: diagnostic and policy-inspection ACP
  coordinator, structured investigator messages and actual SDK handlers.
- `src/coverwise/policies.py`, `generate_policies.py`: allowlisted PDF extraction,
  evidence verification/presentation and editable-source generation.
- `src/coverwise/stress.py`: evidence-bearing typed interpretation, deterministic
  single-member job-change assessments and comparison; also the offline CLI.
- `src/coverwise/money.py`: exact integer-paise INR display; excerpts untouched.
- `src/coverwise/catalogue.py`, `provider.py`: Provider-owned catalogue contracts,
  bounded fixture loading and distinct SDK request/result handler.
- `src/coverwise/recommend.py`: explicit member/requirement inputs, PDF/catalogue
  consistency, separated assessment dimensions, deterministic ranking, compact
  presentation and page-based evidence retrieval.
- `src/coverwise/asi.py`, `live.py`, `runtime.py`: optional explanation adapter and
  explicit live lifecycle. Imports do not construct agents.
- `src/coverwise/smoke.py`: fail-closed local-only preflight for the SDK constructor
  limitation; see `docs/communication.md`.
- `fixtures/catalogue.v1.json`, `fixtures/policies/`: a versioned fictional
  catalogue and five editable policy sources; actual PDFs under `output/pdf/`.
- `sandbox_contracts.py`, `sandbox.py`, `sandbox_ui.py`: typed commands/results,
  transactional fictional insurer and deterministic ACP review/approval commands.
- `sandbox_demo.py`: offline real SDK-handler/SQLite demonstration without agents.

Domain contracts inherit Pydantic BaseModel, never uAgents transport Model.
Caller-supplied nonempty identifiers are stable references, not generated IDs.
Policy document identity includes its version and SHA-256. Hashes will cover raw
PDF bytes or exact UTF-8 pasted-text bytes, before extraction/normalization.
Page numbers and text line numbers are one-based and inclusive. Pasted evidence
requires both a section and a line interval; its locator must match source type.

Unknown data serializes as JSON null. In assessments, null restrictions means
unknown, while an empty list means no restrictions recorded by that assessment;
neither asserts unlimited cover. Evidence, missing-information lists, restrictions,
and next action must be explicitly supplied. No absent term becomes zero or false.
Budgets are strict integer INR paise; event dates are calendar dates and assessment
timestamps require a timezone offset. Interval ends may equal starts.

These contracts do not resolve cross-record references. Future workflow boundaries
must verify scenario members belong to the profile and evidence IDs belong to the
assessed document version/hash. The new inspection path reads only allowlisted
synthetic PDF files and returns extraction evidence, not coverage assessments.
No general ingestion, URL fetching or inferred policy rules exist. Separate
sandbox persistence/approvals do not change assessments. `JobChangeScenario` minimally extends the existing
`StressTestScenario` without breaking its callers. Interpretation accepts only
the documented synthetic grammar. Missing/conflicting/unrecognized facts stay
unknown. A definitive exclusion can coexist with visible missing terms. Temporal
passes cannot produce a guaranteed coverage result; this engine never returns
`covered`. Assessment timestamps are UTC observation metadata, never date inputs.

The coordinator delegates `StressTestRequest` to the Investigator using SDK
messages, and accepts `StressTestResult` only for the expected sender, session,
request ID, result type and exact validated scenario. The Investigator owns PDF
extraction and assessment; the coordinator validates and presents its result.
The CLI invokes that same engine offline. No model decides dates or statuses.
Reports bind every assessment/document/evidence ID to its inspection. A/B share
one scenario; the employer assessment is reused unchanged. Evidence IDs include
PDF bytes, version, page and excerpt.

Recommendation delegation uses `CatalogueRequest/Result` to Provider, then
`CandidateAssessmentRequest/Result` to Investigator. Pydantic v1 SDK envelopes
carry bounded JSON of v2 domain contracts, retaining the established transport
pattern. The coordinator checks expected sender, request, envelope session,
result class, exact inputs and the exact Provider snapshot on return. Investigator
validates catalogue claims against actual PDF terms/hashes, interprets supplied
document references with explicit proposed-start/member context, and assesses the
same immediate and separate later scenarios for every policy. It returns rejected
and unresolved candidates alongside any shortlist. Provider failure prevents
Investigator dispatch; either failure produces an honest incomplete result.

The live lifecycle constructs a third distinct `internal_agent("provider", seed)`
using the reserved setting and includes it in the existing public receiver-start
mechanism and existing cleanup context. No new private SDK lifecycle dependency
was added. All seeds are checked before construction. The 15-second live default
deadline is unchanged. A request reuses one child interpreter for sequential PDF
extraction. A versioned readiness frame separates a bounded five-second interpreter
and dependency startup from each fresh parser's two-second PDF deadline; see
[quote startup repair](quote-extraction-repair.md). One
recommendation execution lane bounds concurrent work, including after handler
cancellation. At most 16 further recommendation handlers wait for that lane;
additional requests receive busy. Queue and executor wait are logged separately.
The CLI's SDK-handler harness also uses 15 seconds and
does not construct agents, register routes, or perform real transport.

Request deadlines are checked explicitly before and after result validation, so a
delayed event-loop timer cannot accept an expired reply. Cleanup removes pending
state and retains only the last 128 request IDs, closing reasons and stage names
for accurate late/duplicate/cancelled-response logs. This is operational metadata,
not cached decisions. See [timing verification](recommendation-timing.md).

## SDK baseline and official references

Checked 2026-10-23:

- [ASI-compatible uAgents example](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents):
  documents `uagents==0.25.5`, resolver-supplied compatible core, separate `openai`
  and `python-dotenv`, and `AgentChatProtocol 0.3.0`. This baseline is retained.
- [Agent Chat Protocol](https://innovationlab.fetch.ai/resources/docs/agent-communication/agent-chat-protocol):
  canonical imports come from `uagents_core.contrib.protocols.chat`; acknowledgements,
  message IDs and session handling belong in the future transport layer.
- [uAgents on PyPI](https://pypi.org/project/uagents/): package metadata and SDK
  installation reference. Unseeded agent construction may create private key
  files; the foundation never constructs an agent.
- [Fetch-A-Thon hackpack](https://www.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack):
  requires eventual ACP, Agentverse registration, ASI:One discovery and an in-chat
  primary workflow; cards are recommended. This foundation fulfills none of those
  live requirements yet.

Python is constrained to 3.12. Pydantic is declared as `>=2,<3`, with the SDK's
own constraints applied by the resolver. No independent core override is used.
Exact runtime/development versions are recorded in the resolver-generated
`uv.lock` and printed by the doctor. Installation succeeded in ordinary
PowerShell; local verification confirms `AgentChatProtocol 0.3.0` with all four
required chat models. See `docs/verification.md` for versions and results.

## Configuration and open questions

`ASI1_API_KEY` is for future ASI model API access. The three seed variables in
`.env.example` are CoverWise naming conventions, not SDK requirements; future
entry points explicitly pass their values to the SDK. The explicit live main loads
`.env` and checks settings before agent construction. It may request a model
explanation only after a successful investigator diagnostic. Doctor and unit tests
do not load credentials or call a live model.

User-observed diagnostic and personal-policy inspection round trips are recorded
separately in verification.md. Live stress testing and employer inspection are
unconfirmed. Strict offline actual-agent verification is blocked by the pinned
SDK's eager ledger probes. Before live verification, confirm current mailbox and
discovery setup and session identity semantics. Resource schemas alone do not
establish ASI:One PDF attachment support: attachment delivery, access permissions,
size limits, and lifecycle remain unresolved. Cards/callback authentication also
remain unverified. Pre-event development eligibility remains unconfirmed; obtain
organizer clarification before treating this work as competition-eligible.
