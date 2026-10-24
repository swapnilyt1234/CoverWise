# Fictional insurer sandbox workflow

Every quote, review, payment result and completion is labelled **Sandbox/demo —
no real policy issued. No real money moved.** Use synthetic data only. No cards,
Aadhaar, PAN, banking credentials, attachments, real insurer APIs, Agent Payment
Protocol or frontend are implemented. Recommendations and inspections remain
read-only and never create quotes, applications or payments.

## Agent and storage boundaries

Coordinator validates exact commands and forwards `SandboxRequest` to the distinct
Provider agent over `ctx.send`; Provider's SDK handler replies `SandboxResult`.
SDK envelopes retain request UUID, expected sender, envelope session, type and
monotonic deadline validation. Replies additionally bind the operation, scope,
action and explicit quote inputs/product or application reference. Coordinator
does not call the database or execute payments. Existing Provider catalogue →
Investigator recommendation delegation and bounded PDF worker repair are preserved.

Provider validates quotes with the existing actual-PDF assessment engine and
current catalogue, then owns all authoritative financial state. Blocking work runs
off the event loop. A local lock serializes Provider work; independent processes
use SQLite `BEGIN IMMEDIATE` and unique constraints. Connections are local to each
transaction, closed before SDK sends. No transaction spans a network wait.

Default database: `runtime/provider.sqlite3` under the workspace. Optionally set
`COVERWISE_SANDBOX_DB` in the Provider process environment to a persistent local
`.db`, `.sqlite` or `.sqlite3` path. Relative paths resolve from its working
directory. The runtime directory, database suffixes and journal files are ignored.
Do not commit runtime records. Schema `PRAGMA user_version=1` is created
transactionally; an unknown version fails closed. Tables: quotes, applications,
revisions, approvals, payments, payment_ledger and operations. Timestamps are UTC;
money is integer INR paise. Keep the same database and original sender/session
after restart. Losing either scope component prevents access by design; there is
no identity recovery or cross-session transfer in this demo.

## Quotes and exact commands

Send `/start` for a short workflow menu or `/sandbox` for help. `/quote preset` is explicitly a **synthetic employer-only
Horizon** example, not a description of the current user:

- Members `member-01:1992-04-10:self:absent` and
  `member-02:1994-08-15:spouse:absent` (last field is a synthetic pre-existing
  condition disclosure).
- Budget 3,000,000 paise/year; minimum shared family limit 100,000,000 paise;
  `uncapped-private` room requirement.
- Proposed policy start 2027-01-01; final employment 2026-12-31; assumed new
  employer protection 2027-02-01; illustrative illness hospitalization 2027-01-15;
  separate later event 2027-02-10; event member `member-02`.

Fully explicit equivalent (single line):

```text
/quote candidate-horizon employer-only 3000000 100000000 uncapped-private 2027-01-01 2026-12-31 2027-02-01 2027-01-15 2027-02-10 member-02 member-01:1992-04-10:self:absent,member-02:1994-08-15:spouse:absent
```

Syntax after product ID reuses the eleven `/recommend` fields, in that order.
Inputs are bounded to 2,000 characters, exactly spaced and fully typed; validation
errors do not echo profiles or challenges. No hidden profile/session defaults are
used. `/quote preset` is the only labelled shortcut. The existing-personal path
is deliberately rejected as `existing_cover_review_required`; keeping cover and
obtaining missing terms remains advice, with no purchase shortcut.

Provider recomputes eligibility, budget, disclosures, requirements, current
catalogue/PDF agreement and the separate later scenario. Missing Query room
schedule cannot pass a hard requirement. The versioned fictional price rule
`eligible-family-list-v1` charges the published annual family tariff once for one
or two eligible adults; no additional tax, fees or adjustments. For Horizon it
computes **2,200,000 paise (₹22,000)**. This is a persisted validated quote with a
unique ID and validity interval, distinct from an indicative catalogue listing.

Quotes contain Provider/product/catalogue/pricing versions, source hashes, full
validated inputs and members, price/basis, dates, restrictions, required synthetic
disclosures and extracted policy evidence. Quotes are immutable. Revalidation at
review, approval and new payment detects changed price/version/source/member/date
terms and requires a fresh review. Unrecognized PDF clauses remain unknown.
The existing catalogue identifies each plan version by its document version
together with the catalogue version/hash; the complete product snapshot is bound.

Dates use documented inclusive calendar arithmetic: cover S through S+364; a fresh
30-day illness wait S through S+29; first post-wait day S+30. The preset therefore
has cover 2027-01-01–2027-12-31, waiting 2027-01-01–30 and first post-wait day
2027-01-31. January 15 is excluded. Passing later temporal checks does not promise
acceptance, comprehensive cover or a claim payment. Existing waiting time is never
credited. Quote expiry is **15 real UTC wall-clock minutes**, independent of these
simulated 2027 dates; production does not freeze the clock.

## Review, approval and transitions

Copy the **actual next command** from each Provider reply; references and challenges
are generated, never fixed in instructions:

| Command | Effect |
| --- | --- |
| `/apply <returned-quote-id> confirm-demo success` | Explicitly confirm synthetic data; create review revision/challenge, no payment |
| `/apply <returned-quote-id> confirm-demo failure` | Same review, deterministic definite-failure payment test |
| `/apply <returned-quote-id> confirm-demo unknown` | Same review, deterministic lost-response-after-effect payment test |
| `/review <returned-application-id>` | New revision and unpredictable challenge; invalidates previous approval |
| `/review <application-id> <new-quote-id> confirm-demo <outcome>` | Explicit replacement quote/data/test outcome; new revision and approval required |
| `/approve <application-id> <revision> <returned-challenge>` | Authorize exactly that review, then execute actual sandbox code |
| `/sandbox-status <quote/application/operation-reference>` | Provider retrieval and authoritative reconciliation; no blind payment retry |
| `/sandbox-details <quote/application/operation-reference> [page]` | Read-only, same sender/session access checks; complete persisted terms and evidence, with exact next-page command |
| `/cancel <application-id>` | Cancel before execution; invalidate approval |

Review shows sandbox label, plan/provider, members, dates, computed premium, quote
ID/real expiry, restrictions, immediate wait exclusion, revision and actual approval
command. Only missing application field is explicit `confirm-demo`; payment mode
is clearly a synthetic test control, not a payment credential. Arbitrary `yes`,
recommendation text or model output cannot approve a purchase.

Approval is bound by SHA-256 to the **observed ACP sender AND envelope session**,
application ID/revision, complete quote (including provider/product/catalogue
versions, document hashes, premium/currency, members, dates, expiry and material
terms), application fields and challenge hash/expiry. The challenge uses standard
library cryptographic randomness, expires after five minutes or quote expiry,
whichever is earlier, and is shown only on explicit review. Only its hash is stored.
Lost review replies require `/review` to issue a new revision/challenge; status
does not disclose an old challenge. Changes invalidate old approvals. Expired
quotes require a fresh quote plus replacement review/approval. A previously
approved but unexecuted review cannot start a payment after its expiry.

The sender/session pair is **an isolation boundary, not verified personal identity**.
Provider trusts the configured Coordinator's signed forwarding of the observed
sender; another sender or session cannot use even a valid leaked challenge or
read these records. Local database/process access is trusted. These demo controls
are insufficient authorization for real insurance or money movement.

| From | Allowed operation / resulting state |
| --- | --- |
| Valid quote | apply → review |
| review / needs_review | new review → review; cancel → cancelled |
| review | valid explicit approval → approved |
| approved | atomic mock payment → completed / failed / payment_pending; before execution review/cancel remains possible |
| review / approved | changed or expired material authorization → needs_review |
| payment_pending | authoritative ledger reconciliation → completed / failed; no record → stays pending |
| completed / failed / cancelled | status/repeat result only; mutation or contradictory cancellation rejected |

The normal approve command passes through approved and executes immediately.
Cancellation cannot undo a committed mock effect; concurrent operations serialize
at transaction boundaries. Payments have unique application, approval and
idempotency keys; ledger effects and payment records commit atomically. A repeated
valid approval returns the same payment/confirmation even after expiry, without
authorizing any new effect. A failed payment does not issue a confirmation and is
not retried in that application. Do not start another application to recover it.

## Unknown outcomes, timeouts and restart

Success records a sandbox effect, succeeded payment, completed application and
stable confirmation. Definite failure records a zero-value failed effect and failed
application. Unknown mode deliberately records a successful effect but returns
`payment_pending`/unknown with **no confirmation**. Repeat approval stays pending;
only `/sandbox-status` reads the authoritative ledger and settles it. It never
invokes payment again. Missing or conflicting ledger evidence cannot complete it.

Provider operation IDs derive from SDK request UUIDs. Quote/review creation stores
the resource reference in the operation transaction; accepted approval survives
before payment execution. If Coordinator times out or a reply is late, its strict
deadline/correlation rules stay intact and the chat prints the **actual**
operation status recovery command. Use it in the same conversation/scope,
even after Provider restart with the same database. Unknown operations remain
pending and instruct status polling, never a fabricated success or repeat charge.
An already approved operation can resume its one authorized execution on status
if still valid; an existing unknown effect can reconcile after quote expiry.

Only request IDs, stage timing, state and outcome codes are logged. No profiles,
disclosures, document text, challenges, credentials or full payloads are logged.

## Offline and next user-run live tests

```powershell
.\.venv\Scripts\python.exe -m coverwise.sandbox_demo
# Or keep a new ignored database (an existing file is never overwritten):
.\.venv\Scripts\python.exe -m coverwise.sandbox_demo --database runtime/my-new-demo.sqlite3
```

This uses real SDK handler callbacks and actual SQLite/PDF validation with local
contexts, **not live agents or transport**. See [observed verification](sandbox-verification.md).

No settings were read or changed for live startup during implementation. Existing
user-run configuration names remain `ASI1_API_KEY`,
`COVERWISE_PERSONAL_AGENT_SEED`, `COVERWISE_INVESTIGATOR_AGENT_SEED`,
`COVERWISE_PROVIDER_AGENT_SEED`, optional `COVERWISE_REQUEST_TIMEOUT_SECONDS`
(existing default 15), and optional `COVERWISE_SANDBOX_DB`. Retain current identities,
seeds, SDK pins and mailbox setup. Only the explicit existing `python -m
coverwise.live` entry point loads live settings. No additional credentials needed.

In ASI:One with the running Coordinator, send `/start`, then `/quote preset`.
Copy the exact application command returned, review the terms, then copy the
exact approval command. Save and run the exact returned status command;
repeat the same approval to test the same confirmation (live duplicate testing
has not yet been observed). Commands are displayed in standalone code blocks;
do not type template brackets or ellipses. Full explicit inputs remain supported.
After user-controlled restart with the same database/session, run that same status
command. Offline references cannot be used in this live scope. For failure/unknown,
request fresh demo quotes, use `failure` or `unknown` in the apply command before
review, approve only the newly returned revision/challenge, then use status.
Test `/cancel` on a separate reviewed application before approval. If any operation
times out, use its returned operation status command, not a new purchase.

Preserve regression commands `/diagnose`, `/policies`, `/inspect`, `/stress-test`,
`/recommend`, `/recommend-timeout` and `/recommend-evidence`. No live sandbox
success is claimed without an observation. The user has now observed live sandbox
completion and retrieval of the same result after a reported agent restart; see
[presentation verification](presentation.md). Duplicate-purchase verification and
live failure/unknown reconciliation remain unobserved. PDF visual review remains pending.

## State-specific presentation

Quote summaries show price, members, simulated cover/wait dates, immediate-event
result and real quote expiry in UTC. Reviews show the material restrictions,
synthetic disclosures, member dates of birth, revision and approval expiry, with
exact approval/cancellation commands. Completed/failed/pending summaries omit
pre-purchase requirements, birth dates and challenge expiry. Unknown outcomes
direct status reconciliation and never another payment.

Every quote/application reply provides its exact scoped details command. Details
returns the complete persisted quote/application and payment record as structured
JSON record pages, including all original evidence, integer paise, version/hash
metadata and actual reviewed inputs. Each page parses independently and includes
reference, page/total and path-labelled records. Oversized strings are split into
explicit segments with character offsets and total length. Historical
approval expiry is labelled as metadata, never an active approval instruction;
plaintext challenges are excluded. Previous/next-page commands are generated for
the same reference. Reconstruct from records, not by concatenating JSON documents;
see [record format](details-pagination.md). An out-of-range response is also valid
JSON and points to page one. The full reply, including fences/navigation, is
bounded to 12,000 UTF-8 bytes. No shared profile defaults or unscoped reference
lookup were added.

Details uses the new typed read-only `details` action through the same Provider
SDK handler/access checks. It does not invoke status reconciliation or resume an
approved purchase. Page selection is presentation-only, so existing command JSON
and operation digests are unchanged. The database schema, material approval
binding, transaction rules and authorization checks are unchanged.
