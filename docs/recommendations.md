# Fictional candidate recommendations

Scope of recommendation commands: catalogue and deterministic prospective advice
only. Separate explicit [sandbox commands](sandbox.md) now provide quotes, review,
approval and mock payment; advice never triggers them. No real cover is issued.
The user observed successful live recommendations and intermittent Investigator
timeouts. The timing repair awaits live reliability retesting; see
[timing verification](recommendation-timing.md). Earlier
user-observed stress tests (preset, July 31 wait, December 30 mismatch) remain
accepted as user observations. PDF visual review remains unconfirmed.

## Catalogue and documents

`fixtures/catalogue.v1.json` is Provider's authoritative versioned structured
catalogue, `synthetic-catalogue-1`, published 2026-10-23T00:00:00Z. The tool adds
a retrieval timestamp and source-file SHA-256. Each product references a version-1
allowlisted PDF and its expected SHA-256. Products, insurer, premiums, identities,
disclosures and all documents are fictional/synthetic.

| Product | Indicative annual family list premium | Shared family limit | Room rule | Preset disposition |
| --- | --- | --- | --- | --- |
| Lantern Economy / candidate-economy | 1,200,000 paise / ₹12,000 | 50,000,000 paise / ₹5,00,000 | ₹3,000/day | Rejected: limit and room hard failures |
| Lantern Query / candidate-query | 1,800,000 paise / ₹18,000 | 100,000,000 paise / ₹10,00,000 | Schedule explicitly unconfirmed | Clarification required |
| Lantern Horizon / candidate-horizon | 2,200,000 paise / ₹22,000 | 100,000,000 paise / ₹10,00,000 | Uncapped private single room | Prospective shortlist; immediate event excluded |

All use Fictional Lantern Assurance. Prices are **indicative published list
premiums**, not binding/personalized quotes: one annual family price for up to two
eligible adults, no additional taxes/fees within this demo. Eligibility is ages
18–60 inclusive at proposed start, exactly one self and optionally one spouse,
maximum two members, and explicit declarations of no pre-existing conditions.
Children and other dependants fail these fictional entry rules. Unknown disclosure
requests clarification rather than assuming absence. Dates of birth and relationship
are mandatory and are never inferred from current users or policy names.

Each PDF has four pages: p1 identity, proposed period/membership, family limit and
premium; p2 entry rules, room rule and exclusions; p3 waiting and premium basis;
p4 conditional illness hospitalization costs/restrictions. Matching clause prefixes
are ECO, QUE, HOR. `/inspect` supports all five documents. The existing two-document
`REGISTRY` remains separate from the candidate allowlist so legacy stress comparison
keeps its exact two existing policies.

Regenerate reproducibly from `fixtures/policies/*.json`:

```powershell
.\.venv\Scripts\python.exe -m coverwise.generate_policies
```

ReportLab uses invariant output. Generation verifies candidate byte hashes against
the versioned catalogue; a changed source requires intentional version/reference
maintenance. Investigator separately compares actual PDF identity/insurer, list
premium/basis, limit, room, eligibility and durations to Provider data. Either hash
or term disagreement fails closed as `catalogue_pdf_disagreement`. A matching hash
alone cannot mask a false catalogue claim. Missing Query room data is represented
as unknown in both places and cannot pass a hard room requirement.

## Date grammar and arithmetic

Entry age is whole completed years at proposed start: subtract birth year and
subtract one more if the start month/day precedes the birth month/day. This
synthetic calculation advances a February 29 birthday on March 1 in non-leap
years. It is not a general insurer age convention.

The limited parser explicitly adds `Eligibility`, `Premium basis`, and `Identity`
labels; the bounded term list rises from 14 to 17. New-policy values are:

```text
365 days from proposed start, inclusive; independent of employment.
Proposed members subject to eligibility; no cover is issued.
Initial illness wait is 30 days from proposed start, inclusive. No continuity credit or waiver is granted.
```

Durations are calendar days, not month/year approximations. For proposed start S
and period length D, policy dates are S through S+(D−1), inclusive. A wait N covers
S through S+(N−1), inclusive; the first post-wait day is S+N. Thus a January 1,
2027 start has a January 1–30 wait, January 31 first post-wait day, and December 31
policy end. A February 1, 2028 start with 30 waiting days has March 2 as its first
post-wait day. No elapsed existing-policy wait is copied into any candidate, and
no continuity credit/waiver is granted. Unrecognized syntax stays unknown.

Proposed membership is explicitly conditional on entry rules, not evidence of
issuance or acceptance. Candidate eligibility is assessed separately from temporal
applicability. Generalized `stress.interpret` takes supplied PDF references plus
proposed-start/member context; it never branches on a candidate product name.
Known wait/expiry failures can exclude an event. Passing checks yields at best
conditional, never guaranteed coverage or payout. No bill reimbursement is computed.

## Inputs and exact commands

```text
/recommend
/recommend preset
/recommend preset-low
/recommend preset-clarify
/recommend preset-existing
/recommend-timeout preset
/recommend-evidence candidate-horizon 3 preset
/recommend-evidence candidate-query 2 preset
```

These are labelled synthetic presets, not assertions about the current user.
Normal preset: self member-01 born 1992-04-10 and spouse member-02 born 1994-08-15,
both explicitly declaring pre-existing conditions absent; budget 3,000,000 paise;
minimum family limit 100,000,000 paise; uncapped private room; proposed start
2027-01-01; final employment 2026-12-31; assumed new-employer cover 2027-02-01;
illness event for member-02 on 2027-01-15; **separate later event** on 2027-02-10.
The same immediate and later scenarios apply identically to baseline and every
candidate. New-employer insurance existence remains an unverified assumption.

`preset-low` changes only budget to 1,000,000 paise; `preset-clarify` changes only
budget to 2,000,000 paise. `preset-existing` retains existing-personal in the
baseline and charges its known 600,000-paise annual premium against the same
3,000,000-paise total budget. It never removes existing cover or recommends a
duplicate purchase automatically. The next action is retaining that comparison
and obtaining missing terms before considering additional cover. Its actual
membership, waiting and period findings remain visible, including adverse dates.

Fully explicit form, eleven single-space-separated fields:

```text
/recommend <employer-only|existing-personal> <budget-paise> <minimum-limit-paise> <uncapped-private|any-room> <proposed-start> <final-employment> <assumed-new-start> <immediate-event> <later-event> <event-member-id> <id:birth-date:relationship:disclosure,...>
/recommend employer-only 3000000 100000000 uncapped-private 2027-01-01 2026-12-31 2027-02-01 2027-01-15 2027-02-10 member-02 member-01:1992-04-10:self:absent,member-02:1994-08-15:spouse:absent
```

Dates use valid YYYY-MM-DD; relationships self/spouse/child; disclosures
absent/present/unknown. Required event member must be listed in the input. Up to
four members may be supplied to demonstrate eligibility rejection, not silently
drop dependants. Monetary inputs are strict integer paise; later event must be
after immediate event; new employer start must be after final employment.
Missing inputs request clarification. No profile/session defaults exist.

Offline equivalent examples (no credentials or `.env` loading):

```powershell
.\.venv\Scripts\python.exe -m coverwise.recommend preset
.\.venv\Scripts\python.exe -m coverwise.recommend preset-low
.\.venv\Scripts\python.exe -m coverwise.recommend preset-clarify
.\.venv\Scripts\python.exe -m coverwise.recommend preset-existing
.\.venv\Scripts\python.exe -m coverwise.recommend preset --provider-timeout
.\.venv\Scripts\python.exe -m coverwise.recommend preset --json
```

Replace `preset` with the eleven explicit fields to use arbitrary supported inputs.
Normal output is compact; `--json` contains all findings and unchanged evidence.
ASI:One evidence remains available separately via `/recommend-evidence <document>
<page> <same preset or explicit inputs>`. It returns complete page excerpts, hashes,
dimensions, both scenario findings, missing terms and next actions. Request pages
1–4 for each candidate; baseline pages remain accessible as well. Evidence commands
rerun the same explicit workflow rather than relying on hidden conversation state.

## Filtering, ranking, failure handling and lifecycle

Eligibility, budget including retained premiums, hard requirements, immediate
assessment, later assessment and material unknowns are separate fields. Definite
entry-rule failure excludes both overall event assessments while leaving temporal
findings visible; unknown disclosure keeps eligibility and later applicability
unresolved. Any known
hard failure rejects the candidate; unknowns never count as passes. Candidates with
material unknowns request clarification. A candidate excluded on the later event
is not shortlisted. Qualifying candidates alone are ranked by lowest annual list
premium, then product ID as an explicit deterministic tie-break. No score or LLM
decides suitability. Rejections remain in the response. Limits never stack.

Coordinator → Provider catalogue SDK request/result → Investigator assessment SDK
request/result → Coordinator presentation. Provider owns versioned catalogue data;
Investigator owns actual PDF evidence and decisions. Sender, session, request ID,
result type, exact inputs and catalogue snapshot are bound. Failures yield an
incomplete response with no fabricated fallback. Pending futures are bounded to 16
and removed on completion, timeout, cancellation or delivery failure. Test-timeout
mode makes Provider deliberately silent for that request without loading or
changing catalogue decisions. Offline harness uses a 0.05-second test deadline;
live timeout tests use the configured deadline.

Input payload ≤1500 characters, SDK input JSON ≤4096, catalogue snapshot ≤32768
bytes, result ≤262144 bytes, displayed reply ≤12000 characters. Full evidence is
paginated by PDF page; oversize results fail explicitly rather than hide limits.
PDF byte/page/text bounds and per-PDF two-second deadlines are preserved. A single
child interpreter now extracts each request's sequence, using fresh parser objects
and parent-controlled per-document start signals. One recommendation execution
lane avoids process contention; cancelled handlers do not release a running
worker's lane prematurely. Live delegation still defaults to 15 seconds,
configurable from 0.05 to 30 through
the existing setting; explicit old shorter values still apply and may time out.

Live configuration names (set locally, never paste seeds into chat):

```text
ASI1_API_KEY
COVERWISE_PERSONAL_AGENT_SEED
COVERWISE_INVESTIGATOR_AGENT_SEED
COVERWISE_PROVIDER_AGENT_SEED
COVERWISE_REQUEST_TIMEOUT_SECONDS=15
```

All three stable seeds must be present and distinct before any SDK construction.
The existing live entry point constructs distinct Provider and Investigator agents
through the existing internal runtime and receiver cleanup mechanism. No new
private SDK lifecycle API, identity changes, registration or publication were
performed for this milestone. Existing SDK constructor network limitations remain.
Do not treat the offline handler harness or mocked unit handlers as live transport.
