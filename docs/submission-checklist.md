# Submission review checklist

Prepared 2026-10-24. Reviewable package only: no repository creation, remote
configuration, staging, commit, push, shared-chat publication or Agentverse profile
change was performed. Use the user's existing coordinator identity.

## Official requirements: newly verified

The [official Fetch-A-Thon 3.0 hackpack](https://www.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack)
was retrieved on **2026-10-24** through the web reader after TinyFish fetch failed.
It requires an Agentverse-registered, ASI:One-discoverable ACP agent, meaningful
tool execution/orchestration, an in-chat primary workflow and a public repository
with run/test instructions. Submission is through Devpost with public shared
ASI:One chat, Agentverse profile URL(s), public GitHub repo, short video and
problem/target-user/outcome description. The video section specifies 3–5 minutes;
the README should identify agents and their addresses/resources. The page also
asks for Innovation Lab/hackathon badges on agent READMEs. Interactive Cards are
recommended; Payment Protocol is a bonus, not implemented here.

Organizer confirmation is still needed for **pre-event development eligibility**.
The displayed event schedule alone does not resolve it. Disclose the existing
development history; do not claim eligibility based on this document.

## Deliverables to fill and verify

| Deliverable | Current value | User action |
| --- | --- | --- |
| Public GitHub repository | **not yet supplied** | Review exclusions/content, choose licence, publish only when authorized; verify fresh locked setup. |
| Coordinator Agentverse profile URL | **not yet supplied** | Copy existing profile URL and check ACP readiness; do not rotate identity. |
| Public coordinator address/handle | **not yet supplied** | Add actual safe public address/handle to README after user confirmation. |
| Internal specialist profile URLs | Not separately registered | Describe the actual local identities; ask organizers whether separate profiles are required for specialists submitted as agents. Do not invent URLs. |
| Public ASI:One shared demonstration | **not yet supplied** | Share a synthetic, complete observed workflow after reviewing the chat contents. |
| 3–5 minute video | **not yet supplied** | Record the [timed script](demo-script.md), show real replies and limits, supply the URL. |
| Devpost entry | **not yet supplied** | Transfer verified deliverables into the organizer's actual submission form. |

Publication/sharing is a later user action. Wait for unused review challenges to
expire or cancel them before sharing. Do not expose `.env`, credentials or live
private configuration in the video, repository or shared chat. Links must be
actual public deliverables, not examples or fabricated addresses.

## Concise project description

CoverWise helps households changing jobs understand when employer health
protection ends and compare independent cover against explicit budget, family
limit and room requirements. Three SDK agents cooperate to retrieve a fictional
catalogue, assess actual authored policy PDFs with clause evidence, and prepare
a validated quote and reviewed application. Deliberate scoped approval executes
a mock payment and persists a stable sandbox confirmation. A fresh illness
waiting period remains visible: the example purchase cannot cover January 15.
No real insurance is issued or money moved.

## Concise architecture explanation

ASI:One sends ACP commands to a mailbox-connected local Coordinator. It validates
inputs, acknowledges requests and checks typed SDK responses against sender,
session, request and deadline. For recommendations it requests Provider catalogue
data then Investigator PDF assessment. For sandbox actions it delegates to the
Provider's authoritative SQLite tools. Unique keys and transactions make mock
payment effects idempotent; explicit status reconciles unknown outcomes. Read-only
details pages expose complete evidence without authorizing payment. Provider and
Investigator are real SDK agents with distinct seeds and handlers, running as
internal receivers in the same process, not separately registered hosted agents.

## Technology claims to keep accurate

- Actual: Python 3.12, pinned uAgents/ACP, ASI:One chat surface, Agentverse mailbox,
  typed SDK delegation, actual pypdf extraction, deterministic date/fit rules,
  versioned JSON catalogue, reproducible ReportLab PDFs, SQLite sandbox effects.
- ASI1 API: validated intent/field proposals and optional diagnostic explanation.
  Insurance/ranking/dates/money/authorization remain deterministic. Do not claim
  LLM underwriting, general autonomous planning or model-controlled approval.
- Local-only harness tests do not prove network transport. Agentverse does not
  host the whole backend; uptime depends on the local process and connection.
- Fictional insurer/payment and authored-clause parser only; no arbitrary-policy
  ingestion/OCR, real insurer/payment API, APP, Cards or frontend. Do not describe
  the mock ledger as Agent Payment Protocol or real settlement.
- No identity verification beyond demo sender/session isolation. No claim or
  underwriting guarantee; no automatic stacking of limits or replacement of
  existing personal cover. New-policy waiting periods are not waived.

## Evidence and remaining checks

- [x] User-observed ACP diagnostic delegation with two distinct computed results.
- [x] User-observed personal PDF extraction.
- [x] User-observed stress preset, waiting boundary and conflicting-date handling.
- [x] User-observed candidate evidence and existing-cover recommendation.
- [x] User-observed quote, reviewed application, explicit approval and sandbox completion.
- [x] User-observed same completed payment/transaction/confirmation after reported restart.
- [x] User-observed concise completed-status presentation.
- [ ] Corrected independent-JSON details pagination retested live.
- [ ] Live duplicate approval verified using the current demo review command.
- [ ] Full deliberate Provider timeout then successful normal request observed.
- [ ] Generic discovery from ASI:One, separate from direct profile chat.
- [ ] Every page of all five PDFs visually reviewed.
- [ ] Actual public links supplied; external profile/README badges verified by user.
- [ ] Pre-event development eligibility clarified with organizers.

Use the [rehearsal guide](rehearsal.md) and record actual outcomes rather than
checking boxes because a command exists. No invented usage/activity metrics,
generic-discovery success, prize predictions or promises of real insurance.

## Publication and package review

- [ ] Manually review all intended public content, including new untracked files;
  an empty `git diff` does not audit them. No staging was performed here.
- [ ] Keep `.env`, runtime databases/journals/leases, caches, key files and private
  configuration directories excluded. The intentionally blank `.env.example`
  remains distributable.
- [ ] Keep historical output reports/rendered review samples local. Only the five
  allowlisted PDFs are retained under `output/` for publication/builds. The old
  sample artifact may contain consumed temporary approval commands.
- [ ] Confirm wheel contains the catalogue, five authored JSON sources and five
  generated PDFs; the source archive also contains docs, tests and lock/setup files.
- [ ] Re-run README commands from a fresh checkout, then fill actual links.

Actual local verification, installed-asset inspection and Git/graph results are
recorded in [preparation verification](preparation-verification.md).
