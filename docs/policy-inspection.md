# Milestone 4 policy inspection

Current status (2026-10-23): dependencies are installed, real PDFs exist and both
policies extract offline. The user observed live `/inspect existing-personal`
with SHA-256 `8ceeaf6224499d4eb8de4d62f3444a161608260505573abcee7353800c8f7760`.
Employer live inspection and visual review of both PDFs remain unconfirmed.
The installation-failure account below is historical. See
[stress testing](stress-testing.md) and [verification](verification.md) for current
execution, deterministic assessments and separate pending evidence.

## Sources, IDs and generation

Editable source fixtures are `fixtures/policies/existing-employer.json` and
`fixtures/policies/existing-personal.json`. Runtime extraction never reads these
JSON files; only the generator reads them. The configured registry in
`coverwise.policies` maps exactly two IDs to fixed PDF filenames, titles and
document version 1. It is source-checkout based; assets must be packaged before
distributing a standalone wheel.

| ID | Source design / intended output |
| --- | --- |
| existing-employer | Fictional Harbor Employer Health; three pages; shared 100000000 INR paise family limit, dates 2026-01-01 through 2026-12-31; both members lose cover at employment termination, explicitly 2026-12-31 inclusive for Demo A; no conversion/continuity; uncapped private single room subject to overall limit |
| existing-personal | Fictional Pebble Personal Health; four pages; shared 20000000 INR paise family limit, dates 2026-07-01 through 2027-06-30; 600000 paise annual premium; 300000 paise/day room cap; explicit initial illness waiting interval through 2026-07-31 inclusive; event-specific deductible/co-payment and room deduction restrictions |

Every generated page is designed to carry the exact warning “Synthetic demo
policy — no real insurance”, an explicit clause ID and readable page numbering.
Both policies cover the same fictional member IDs and dates of birth from the
fixture design. Renewal dates and pre-existing-condition waits are deliberately
absent; neither is inferred from expiry or the initial illness wait. Employer
event sublimits explicitly reference an unconfirmed missing schedule. Explicit
“None” deductions remain stated terms with their scope, not missing information.
Canonical documents do not contain conflicting values; a modified-PDF integration
test deliberately introduces a conflict and requires both sources to survive.

After the required packages are installed, reproduce outputs with:

```powershell
Set-Location 'C:\Users\swapn\Desktop\coverwise'
.\.venv\Scripts\python.exe -m coverwise.generate_policies
.\.venv\Scripts\python.exe -m coverwise.policies existing-employer
.\.venv\Scripts\python.exe -m coverwise.policies existing-personal
```

Intended output files are `output/pdf/existing-employer.pdf` and
`output/pdf/existing-personal.pdf`. ReportLab's invariant mode removes variable
timestamps/IDs for reproducibility with the same sources and library version.
Generation buffers each document and replaces its output only after all pages
are authored. Source/registry versions must agree. No expected-result fixture is
used by the loader or parser.

## Bounded extraction and evidence

Use only these configured IDs. Unknown IDs, traversal strings and URLs are
rejected before opening files. No attachments, arbitrary paths, OCR or URL fetches
are supported. Resolved files must remain in the configured PDF directory.

Limits: 512 KiB PDF bytes, six pages, 256 KiB decoded page content stream,
20000 characters per page, 60000 total text characters, four sources per term,
280 characters per value, 400 per full excerpt, 65536 UTF-8 bytes per structured
report, and 12000 characters per displayed reply. All runtime inspection paths
use the same isolated worker: a five-second startup/readiness bound, followed by
a separate two-second deadline per PDF. This includes job-card confirmation,
`/inspect`, stress inspection, recommendation and quote batches. Timeout
kills/waits for that child and closes its pipes; see
[job confirmation repair](job-inspection-repair.md) and the earlier
[quote startup repair](quote-extraction-repair.md).
The coordinator's existing pending-request bound and configured timeout still
apply, so a very short coordinator timeout can expire first. The worker is not
an OS memory sandbox; decoded-stream checks happen after decompression. This is
for trusted preloaded synthetic assets, not hostile PDF uploads.

pypdf reads actual PDF bytes and extracts each page. Encrypted, malformed,
image-only/blank-text pages, excessive sizes and unsupported document grammar
return explicit errors without findings. The report records actual byte SHA-256,
registry version and counted pages. Missing assets return document_unavailable;
missing reader packages return dependencies_unavailable.

The transparent fixture grammar is:

```text
EMP-02 | Employment termination: <literal value> [END EMP-02]
```

Whitespace matching collapses every run of Unicode whitespace to one ordinary
space and trims the two ends (`" ".join(text.split())`). Case, punctuation,
numbers and all non-whitespace characters remain unchanged. No OCR correction,
semantic rewriting or insurance inference occurs. Terms use the fixed explicit
labels in policies.LABELS. Unmatched labels/grammar do not establish absence in
arbitrary insurance documents: this parser is limited to the authored fixtures.

Every material term has extraction status and zero or more ClauseEvidence
objects. Evidence includes document ID/version/hash, one-based page, clause ID,
the actual matched page excerpt and a stable ID derived from hash/version/page/
excerpt. Before returning, every excerpt is checked against its cited extracted
page under the normalization above. The page locator and document must agree.

- stated: one distinct literal value, including explicit “None”.
- not_stated: no recognized source; value null, no invented citation.
- ambiguous: an explicitly UNCONFIRMED value; null authoritative value, retained source.
- conflict: differing literal values for the same label; null authoritative value,
  all sources retained, including both sides of a conflict. Even superficial text
  differences are conservatively considered different; no precedence is inferred.

## Agent path and presentation

`/policies` lists the configured IDs and whether a PDF is present. It makes no
claim that a present PDF has already passed extraction. `/inspect <policy-id>`
delegates a typed PolicyInspectionRequest through Context.send to the existing
investigator. The investigator owns the bounded worker and verification. A typed
PolicyInspectionResult carries either an error or a serialized, validated domain
report; Pydantic v2 reports are not mixed into the SDK's v1 transport model.

Pending slots verify response model type, sender, request ID, envelope session and
policy ID. The coordinator validates successful reports, then deterministically
presents terms, statuses, short excerpts, clause/page/evidence references, document
hash/version and limitations. Long excerpts/display details are explicitly marked
as shortened/omitted. The full bounded report retains the evidence sources.
Policy inspection never invokes the optional model explanation adapter. Failures
return “No findings returned”, not successful terms. Logs retain metadata only.

Both new commands support the same one-exact-leading-self-mention normalization.
No arbitrary command search is added. /diagnose payload behavior, acknowledgements,
session routing, sender/correlation checks, configuration and SDK pins are preserved.
No stress tests, recommendations, Provider Agent, applications, purchases, cards
or coverage/payout decisions are implemented.

## Installation blocker and user verification

One Codex resolution attempt against official PyPI failed with socket error 10013.
The enforcing component remains unknown. pypdf>=6,<7 is declared as runtime
dependency; reportlab>=4,<5 is declared only in the development group for generation.
The existing uv.lock was not fabricated or edited; it is now stale against these
declarations. No PDF versions are installed or resolved yet.

Run one command at a time in ordinary PowerShell outside Codex, stopping at the
first failure and returning its output with secrets redacted. This is not a
guaranteed network fix:

```powershell
Set-Location 'C:\Users\swapn\Desktop\coverwise'
uv lock
uv sync --locked --dev
.\.venv\Scripts\python.exe -m coverwise.generate_policies
.\.venv\Scripts\python.exe -m coverwise.policies existing-employer
.\.venv\Scripts\python.exe -m coverwise.policies existing-personal
uv lock --check --offline
.\.venv\Scripts\python.exe -m coverwise.doctor
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Require real-PDF tests to execute without skips. Render all seven generated pages
with an available PDF renderer and inspect them before accepting the artifacts.
Neither pdftoppm nor mutool was found on PATH here; no visual QA is claimed.

After generation, offline extraction, evidence checks and visual QA succeed, the
user may restart the existing live entry point with unchanged local settings:

```powershell
.\.venv\Scripts\python.exe -m coverwise.live
```

In the existing ASI:One conversation, send `/policies`, then
`/inspect existing-employer` (optionally `/inspect existing-personal`). Confirm
acknowledgement, correlated investigator result, document hash/page/clause
references and readable ACP reply. Compare cited excerpts with the generated PDF.
This live policy-inspection procedure has not been run.

## References

Checked 2026-10-23:
[pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
documents page extraction, OCR limitations and decoded-stream memory risks.
[ReportLab canvas](https://docs.reportlab.com/reportlab/userguide/ch2_graphics/)
is the generation reference. APIs remain execution-unverified until packages are
installed; no broad PDF support is claimed from source inspection.
