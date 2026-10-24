# Deterministic dated stress testing

This slice assesses the two existing synthetic PDF policies. It does not offer a
new product or calculate reimbursements. The user reports live confirmation of
the preset, July 31 waiting exclusion and December 30 termination-date mismatch.
PDF visual review remains unconfirmed. New candidate recommendations are documented
separately in [recommendations](recommendations.md).

## Commands and exact synthetic preset

From `C:\Users\swapn\Desktop\coverwise`:

```powershell
.\.venv\Scripts\python.exe -m coverwise.stress preset
.\.venv\Scripts\python.exe -m coverwise.stress member-01 2026-12-31 2027-02-01 2027-01-15 illness_hospitalization
.\.venv\Scripts\python.exe -m coverwise.stress preset --json
```

The first two use identical assumptions: member `member-01`, final employment
`2026-12-31`, assumed new employer coverage beginning `2027-02-01`, illustrative
illness hospitalization `2027-01-15`. Only the labelled synthetic preset supplies
those values. The explicit form requires all five fields, in that order, separated
by single ordinary spaces. No profile/session lookup, current-date default or
implicit continuity credit is used. `profile_id` is explicitly null: this slice
has no profile lookup, authenticated identity or saved profile default.

ACP forms (optionally preceded by one exact coordinator self-mention):

```text
/stress-test
/stress-test preset
/stress-test <member-id> <final-employment YYYY-MM-DD> <assumed-new-cover YYYY-MM-DD> <hospitalization YYYY-MM-DD> illness_hospitalization
```

Help is also discoverable from `/policies` and invalid-command guidance.
Member IDs use 1–64 ASCII letters/digits/hyphens; dates are valid ISO calendar
dates between 1900 and 2100. New coverage must begin after final employment.
Hospitalization may precede the job change (for boundary stress testing).
Only one member, one event date and `illness_hospitalization` are supported.
The stress payload is bounded to 512 characters, SDK scenario JSON to 2048,
result JSON to 131072 bytes in the Investigator, and readable replies to 12000
characters. Oversize reports fail explicitly without silently dropping limits.
PDF worker limits are unchanged. A new-employer start is only a supplied assumption;
it does not establish that employer insurance exists or that this member qualifies.

## Rule grammar and semantics

`stress.interpret` builds typed `Fact` values with evidence IDs, or an unknown
reason. It reads `PolicyInspection` produced from the actual PDF bytes, never the
editable source JSON and never a product-name/expected-answer switch.

Recognized clause values are deliberately narrow:

- Policy period: `YYYY-MM-DD through YYYY-MM-DD inclusive.` or the same interval
  followed by ` inclusive; subject to employment termination.` All endpoints are
  inclusive. Reversed/invalid intervals are unknown.
- Members: semicolon-separated `ID Name (self|spouse, born YYYY-MM-DD)` records,
  ending in a period. IDs are exact identifiers, names ASCII letters/spaces, birth
  dates valid and IDs unique. No membership is inferred from the scenario.
- Termination: `Coverage for both members ends on NAME's final employment date,
  YYYY-MM-DD inclusive, or policy expiry if earlier. No conversion or continuity
  benefit.` The typed rule is the earlier of final employment and policy expiry,
  with the last day inclusive. Scenario disagreement returns correction required,
  no computed gap, and a request to correct the scenario/document. Input never
  changes the PDF's stated date.
- Wait: `Initial illness waiting interval is YYYY-MM-DD through YYYY-MM-DD
  inclusive. No continuity credit or waiver is granted.` Alternatively the exact
  employer clause `None for initial illness hospitalization under this synthetic
  employer policy.` Unknown wording cannot waive a wait. First and last interval
  days exclude the supported illness event; the following day has elapsed.
- Exclusions: the exact existing `Cosmetic treatment and elective dental treatment
  are excluded.` or supported synthetic variant `Illness hospitalization is
  excluded.` The latter excludes the supported event. The first lists its scoped
  exclusions; neither matches the supplied illness event classification. No
  diagnosis beyond that event classification is inferred.

Missing, ambiguous, conflicting or unrecognized material clauses remain visible.
Known date/exclusion failures produce `excluded` while retaining unknown terms.
A termination-date mismatch takes precedence as `insufficient_information` with
`temporal=correction_required`. Passing date checks alone never produces `covered`.
Unknown member/period/termination/wait/exclusion or material benefit terms yield
`insufficient_information` when no definitive exclusion applies; otherwise the
best possible result is `conditional`. Pre-existing-condition terms are absent;
the personal deductible/co-payment/procedure clauses are scoped to appendicitis
and cannot be generalized to an unspecified illness hospitalization.

The employer gap is the inclusive interval from the day after the earlier
documented ending date through the day before assumed new coverage. Contiguous
dates mean no gap. Unknown employer membership/end rules or a date mismatch mean
the gap is unknown. This interval describes employer protection, not a proven gap
in all insurance protection. Personal policy findings are separate, using exactly
the same member and dates. Family limits are never added/stacked.

`money.inr` uses integer division/remainders and Indian grouping. The display layer
formats extracted values (₹10,00,000, ₹2,00,000, ₹3,000/day, ₹6,000/year),
preserving shared-family wording and annual-premium qualifiers. It does not modify
canonical paise or quoted evidence. Fractional rupees retain two decimal digits.
`--json` includes complete unchanged evidence excerpts and hashes; `/inspect`
continues providing page/clause/evidence references with labelled short excerpts.

## Observed offline result (2026-10-23)

The preset and changed-date commands returned exit 0. Original PDF hashes:

- Employer: `e3510d1ab552e25a85d3fe9fbbb616d1082b65177d76b5dd5469569df13ada99`.
- Personal: `8ceeaf6224499d4eb8de4d62f3444a161608260505573abcee7353800c8f7760`.

| Assumption set | Employer alone A (also unchanged in B) | Existing personal added in B |
| --- | --- | --- |
| Preset, event 2027-01-15 | Excluded: expired and employment ended | Temporal passes; overall insufficient information |
| Changed event 2026-07-31; all other dates/member unchanged | Temporal passes; overall insufficient information | Excluded: inside illness waiting interval |

The changed-date command actually executed:

```powershell
.\.venv\Scripts\python.exe -m coverwise.stress member-01 2026-12-31 2027-02-01 2026-07-31 illness_hospitalization
```

Supporting material evidence in both runs:

| Conclusion | Reference |
| --- | --- |
| Employer member listed | p1 EMP-01 `ev-6583477d7f0b2d2c29150df8` |
| Employer period through 2026-12-31 inclusive | p1 EMP-01 `ev-827420676e85214bf0f490e2` |
| Employer termination 2026-12-31 inclusive, expiry if earlier | p2 EMP-02 `ev-5562ee0dc8e548fbb4cbf125` |
| Employer initial illness wait explicitly none | p2 EMP-02 `ev-4cf364aae5af88e9a83e3b0c` |
| Employer procedure schedule unconfirmed | p3 EMP-03 `ev-3d1bf8f392e9a663b0267156` |
| Personal member listed | p1 PER-01 `ev-9deac55694117cc4979507ee` |
| Personal period 2026-07-01 through 2027-06-30 inclusive | p1 PER-01 `ev-c7d02e9f1230b99b4758fca6` |
| Personal illness wait through 2026-07-31 inclusive | p3 PER-03 `ev-1ed5f1fde58d984c15618f8c` |
| Personal deductible only specified for appendicitis | p3 PER-04 `ev-c2d036f88f248d984f1f84a2` |
| Personal co-payment only specified for appendicitis | p3 PER-04 `ev-9bfbb640db0e4a24cb0fb87f` |
| Personal procedure terms scoped to appendicitis | p3 PER-04 `ev-2394b1bb3decfe4c5522d874` |

For the preset, employer last day is December 31; January 1–31 is a **31-day gap
in employer protection**. Adding the existing personal policy adds temporal
availability on January 15 (its wait elapsed), with its shared-family and room
restrictions and unknown terms still visible. It does not establish comprehensive
coverage or a guaranteed payment. Both runs retain the same gap because only the
hospitalization date changed. Missing pre-existing-condition terms have no source
evidence; they are explicitly marked not stated, never invented evidence.

## Verification and pending live work

See [verification](verification.md) for executed check results. Tests generate
temporary modified PDFs, proving that changed actual terms alter both decisions
and byte/evidence hashes. SDK handler tests install protocols on a lightweight
test double; they never construct live agents or call a network.

Current evidence is separate: dependencies installed and both PDFs extracted
offline; user-observed live personal inspection with matching hash; employer live
inspection unconfirmed; visual review of both PDFs unconfirmed; live stress testing
user observed for those three cases. No new live process was started by Codex.
No `.env`, seeds,
identities, registrations, publications, pins or later milestones were changed.

When the user runs the existing live entry point, send these exact ASI:One inputs
(no launch or publication is performed by this implementation task):

```text
/policies
/inspect existing-employer
/inspect existing-personal
/stress-test
/stress-test preset
/stress-test member-01 2026-12-31 2027-02-01 2026-07-31 illness_hospitalization
/stress-test member-01 2026-12-30 2027-02-01 2027-01-15 illness_hospitalization
/diagnose CoverWise connectivity
```

Expect the mismatch command to request correction and leave the gap unknown.
Record acknowledgements, sender/session/request correlation and received findings;
unit tests and an open Inspector do not establish a successful live stress test.
Review every page of both PDFs visually in a separate pending verification step.
