# Synthetic fixture design and editable sources

This is the source specification for the two generated synthetic PDFs, not a
purchase offer. All names, members, policies, premiums and events are fictional.
Actual-byte inspection and deterministic outcomes now exist; see
[stress testing](stress-testing.md) for hashes, the dated preset and observations.
Outcomes depend on explicit PDF terms and inputs, never product-name checks.
IDs are stable and document versions are `1`.

Editable sources for all five policies are under `fixtures/policies/`, with
reproducible PDFs under `output/pdf/` and a versioned Provider catalogue at
`fixtures/catalogue.v1.json`. Deterministic stress and candidate assessment now
exist. See [recommendations](recommendations.md) for current grammar, explicit
inputs, evidence retrieval, eligibility and observed outcomes.
The source files add explicit dates, deductions, exclusions and scoped restrictions
without implementing a coverage decision. Renewal and pre-existing-condition
waiting terms are intentionally absent. Employer additional sublimits are explicitly
unconfirmed, not treated as unrestricted.

## Profile and job transition

Profile `profile-demo-01` has member `member-01` (Demo A, born 1992-04-10, self)
and `member-02` (Demo B, born 1994-08-15, spouse). Both are synthetic, with no
known pre-existing conditions declared; unknown history must be requested rather
than interpreted as absence. Annual premium budget is 3,000,000 INR paise
(INR 30,000). Required family hospitalization limit is at least 100,000,000 paise
(INR 10 lakh), and required room eligibility is a private single room without a
daily monetary cap. Annual budget includes the existing personal premium below.

Scenario `scenario-job-change-01`: final old-employer day 2026-12-31; next
employer cover begins 2027-02-01. Transition interval is 2027-01-01 through
2027-01-31 inclusive. Both member IDs are referenced. Stress event: non-accidental
appendicitis hospitalization of member-02, 2027-01-10 through 2027-01-12;
synthetic eligible cost 30,000,000 paise (INR 3 lakh), private single room.
Use explicit event dates for the hospitalization when creating its scenario
contract; the employment transition dates are separate fixture inputs.

## Two existing-policy documents

| Document | Planned evidence | Explicit fictional terms |
| --- | --- | --- |
| `existing-employer`, Harbor Employer Health | p1 `EMP-01`; p2 `EMP-02`; p3 `EMP-03` | Both members; family limit 100,000,000 paise; cover ends inclusive 2026-12-31 on employment termination; no conversion/continuity benefit; private single room |
| `existing-personal`, Pebble Personal Health | p1 `PER-01`; p2 `PER-02`; p3 `PER-03` | Both members; family limit 20,000,000 paise; inclusive term 2026-07-01 to 2027-06-30; annual premium 600,000 paise; room cap 300,000 paise/day; initial illness wait already completed on 2026-07-31 |

`PER-04` on p3 specifies no deductible/co-pay for the defined appendicitis event,
and no other event-specific sublimit. `PER-05` on p4 specifies that room cap
restricts room reimbursement only, with no proportional deduction to other costs.
Future evidence must quote the actual fixture excerpts and page/section locations.
The existing personal policy is below the stated family-limit and room requirements.

## Three candidate product documents

Candidate terms run 365 calendar days from an explicit proposed start. The preset
starts 2027-01-01 and ends 2027-12-31 inclusive. Proposed members are subject to
documented entry rules, not issued cover. Listed annual family premiums are
synthetic indicative list prices, not binding/personalized quotes; no additional
taxes/fees are assumed within this demo. No continuity credit or waiver is granted.
The new policies have fresh 30-day waits: January 1–30 inclusive for this start,
with January 31 the first post-wait day. Waiting duration is independent of any
elapsed existing-policy interval. All three have p4 illness-specific cost terms.

| Product/document ID | Annual premium (paise) | Family limit (paise) | Clause design and intended distinction |
| --- | ---: | ---: | --- |
| `candidate-economy`, Lantern Economy | 1,200,000 | 50,000,000 | p1 `ECO-01` limit and members; p2 `ECO-02` room cap 300,000/day; p3 `ECO-03` initial illness waiting interval 2027-01-01 through 2027-01-30 inclusive. Cheaper but fails the 100,000,000 limit and uncapped private-room requirements. |
| `candidate-query`, Lantern Query | 1,800,000 | 100,000,000 | p1 `QUE-01` limit and members; p2 `QUE-02` says only "room eligibility per schedule" but the schedule is deliberately absent; p3 `QUE-03` uses the same initial waiting interval. Room requirement cannot be determined; request the schedule. |
| `candidate-horizon`, Lantern Horizon | 2,200,000 | 100,000,000 | p1 `HOR-01` limit and members; p2 `HOR-02` private single room without monetary cap; p3 `HOR-03` same initial illness waiting interval; p4 `HOR-04` covered hospitalization after that wait, subject to supplied exclusions. Improves longer-term limits/room terms but cannot close the immediate illness gap. |

Existing personal plus candidate premiums total respectively 1,800,000,
2,400,000 and 2,800,000 paise, all within the 3,000,000 budget. A larger budget
must never cure a failing coverage requirement or an unknown term.

Before/after checks will compare the two existing policies with those same
policies plus each candidate; adding limits does not imply double reimbursement.
The January hospitalization falls within every candidate's explicit waiting
interval. Existing personal coverage remains limited; do not report the event as
uninsured merely because candidate coverage is unavailable. A later matched event
on 2027-02-10 through 2027-02-12 tests post-wait protection, using explicit inputs
for any new-employer terms rather than assuming them.

The former multi-day appendicitis/bill example above remains historical design;
the implemented recommendation preset uses a single illness event on January 15
and a separate matched later event on February 10, with no bill calculations.
The actual candidate documents add explicit fictional entry ages 18–60 at start,
self with optional spouse (maximum two adults), and required absence disclosures.
These rules and prices are PDF-evidenced and checked against catalogue data before
assessment. A pasted-text ingestion variant remains future work. Visual review of
all existing and candidate PDFs remains unconfirmed.
