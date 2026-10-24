# Guided card UX and callback repair

Latest routing safeguards and stage diagnostics:
[native callback routing repair](card-routing-repair.md). Repeated `/cards` during
an active step now asks for explicit restart instead of silently discarding it.

## Current entry and screens

Direct-mention the existing CoverWise agent and send:

```text
/cards
```

`/start` opens the same menu. The first screen is a native carousel, because the
documented carousel supports a subtitle while the predefined form example does
not document one. No unsupported form subtitle, description, prefill or widget
was added.

- Title: **Let's check your insurance**
- Subtitle: **Tell us what you need help with.**
- Choices: **I'm changing jobs**, **Compare health plans**, **Try an example**
- One entry notice: **Demo environment — sample policies — no real insurance issued.**

Subsequent forms use one short narration sentence and one label per field, with
no descriptions/placeholders repeating that label. Corrections keep the form's
labels intact and name the visible field in the message.

### I'm changing jobs

**Changing jobs** asks only:

- Last working day (YYYY-MM-DD).
- Do you know when new cover starts? — I know the date / I don't know.
- New employer cover start date (YYYY-MM-DD, if known).
- Current cover — Employer / Personal / Both / Unsure.
- Choose a sample policy.

**Review details** shows those values before **Check policy**. The Investigator
then inspects the selected actual PDF through existing SDK messages.
**Your job-change check** cites the employer termination clause and, for listed
members, uses the earlier documented expiry/termination endpoint. Unknown new
cover dates stay unknown: no gap duration is invented. Known new cover is a
user-supplied, unverified assumption. This is conditional sample-policy information,
not proof of actual membership or a gap in all protection.

No DOB, budget, medical event or hospitalization date is created/assumed for this
path. Personal/both cover is retained; unsure cover is not treated as absent.
Missing/conflicting document facts remain visible. A final date contradicting
the sample employer's fixed 2026-12-31 returns a correction citing EMP-02; the
document is never silently changed. **View policy evidence** and **Compare health
plans** are available as deliberate next actions.

### Compare health plans

Only after choosing comparison, **Compare health plans** asks:

- Annual budget (₹).
- Who needs cover? — Self / Self and spouse.
- Your date of birth; spouse's date of birth if included.
- Your health disclosure; spouse's disclosure if included.
- Coverage amount (₹).
- Room preference.
- Current cover, including Unsure.

Dates of birth and disclosures are needed by the existing catalogue's eligibility
rules. Omitted health disclosures remain unknown. Rupees use the existing exact
integer-paise conversion. Unknown current cover must be clarified, not silently
converted into an employer-only profile.

**Review details** shows these requirements without running a recommendation.
The existing assessment contract needs dated illness scenarios, so the user may
choose **Add an optional scenario**. This opens **Optional illness scenario**:
sample policy, last working day and assumed new cover start if not already
reviewed; new policy start; illness date; later illness date; selected person.
Confirmed job dates can be reused transparently; unknown dates are requested.
Hidden callback fields cannot overwrite already reviewed job dates.

The adapter does not invent personal dates to satisfy the existing contract.
No event-free recommendation engine was added. A user can instead choose the
labelled example. Once all scenario inputs are reviewed and **Compare plans** is
selected, the same Coordinator → Provider catalogue → Investigator assessment
path produces the actual candidate carousel, evidence and restrictions.

### Try an example

**Try an example** asks just **Sample cover** — employer only, or employer and
existing personal cover. **Review details** explicitly displays the sample:
self born 1992-04-10, spouse born 1994-08-15; absent pre-existing conditions;
₹30,000 annual budget; ₹10,00,000 shared-family minimum; uncapped private room;
last working day 2026-12-31; assumed new cover 2027-02-01; proposed policy start
2027-01-01; member-02 illness on 2027-01-15 and a separate later event on
2027-02-10. These are sample details, not inferred personal facts.

Confirming runs the unchanged dated comparison. Horizon's quote/application path
continues to use actual Provider computation and persistence. January 15 remains
excluded by the new policy's initial waiting interval. Explicit sandbox purchase
approval, expiry, revision/challenge binding and duplicate-click protection remain.
Review/completion retain the no-real-policy/no-real-money disclosure. Persisted
terms, evidence, references and existing exact commands remain accessible.

## Confirmed validation cause

The coordinator already receives flat selection JSON. Previously it removed only
`action` and `card_token`, then passed every remaining key into the editable
form's `extra="forbid"` model. A client-added `approved` key therefore triggered
`extra_forbidden`, rendered as the internal-name error **Correct fields: approved**.
The same current coordinator handler reproduced that failure before repair.

The official [card reference](https://innovationlab.fetch.ai/resources/docs/next/interactive-cards/asi-interactive-cards)
describes CTA selection merged with form fields, and review approve/reject CTA
selection. It does **not** document `approved` as an authority field. The supplied
canonical docs URL timed out on this review; the official `/next/` page was read
successfully. No undocumented outgoing property was added.

`CallbackMetadata` now separates the observed optional boolean from editable
fields. It is strict: null, strings and numbers are not accepted as confirmation.
Its absence remains None, not true; the documented explicit CTA selection still
works. The flag alone, or generic yes/prose/model output, can never approve.

For positive actions, false performs no action. An explicit server-held Back/Edit/
Cancel action still works with false, including actual Provider cancellation.
True on a form does not bypass the separate input review. Purchase execution
still requires the correct unexpired server token for the exact application
review, in the observed sender/session, followed by all existing Provider checks.
Unexpected editable fields and conflicting callback metadata remain rejected.
Messages use visible field names, never internal metadata names or raw profile
values. Backend error codes remain available in detailed results, while card
corrections describe what the user can do.

## Verification boundaries

Observed local checks:

- Before repair, the real coordinator-handler reproducer failed with
  **Correct fields: approved**: **1 failed, 39 deselected**, 22.52 s.
- `.\.venv\Scripts\python.exe -m pytest -q tests/test_cards.py tests/test_sandbox.py tests/test_acp_logging.py`:
  **158 passed in 78.17 s**.
- `.\.venv\Scripts\python.exe -m pytest -q`: **433 passed in 121.85 s**.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **passed** (62 files
  already formatted in the final run).
- `graphify update .`: AST-only rebuild, **993 nodes / 3,126 edges / 51 communities**.
  The multigraph diagnostic found no missing/dangling endpoints, duplicate edges
  or collapsed edges; one existing recursive self-call remains.

Tests use real generated PDFs, actual SDK handler functions and temporary SQLite,
without outbound agents or model calls. They cover form → review → confirm with
the observed flag, false/type-invalid/no-token purchase attempts, real Cancel with
false, progressive job/requirements/scenario paths, unknown dates/disclosures,
readable corrections, changed PDF terms, reviewed-date reuse and tampering, scoped
callbacks, duplicate purchase protection and unchanged slash-command behavior.

Use only demo information. Drafts/tokens are in memory; restart or `/clear-chat`
clears them, not persisted purchases. Save the actual scoped status command for
transaction recovery. Live rendering and this repaired callback sequence remain
pending user observation. Earlier text-command completion/restart recovery is
separate evidence. PDF visual review remains unconfirmed.

Changed runtime code is confined to `cards.py`; `card_schemas.py` was inspected
and reused without adding unsupported fields. Tests update card-screen expectations
and add progressive/callback regressions. No insurance engine, Provider transaction,
database schema, SDK pin, agent identity or live record changed. No live startup,
model calls, publication, staging or commits were performed.
Git status retains the pre-existing untracked workspace paths.
