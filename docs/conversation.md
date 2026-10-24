# Minimal natural-language slice

Native [Interactive Cards](interactive-cards.md) now provide an additional input
and explicit sandbox approval route; `/cards` and `/start` open the native form.
Structured card callbacks do not pass through the model. While a card draft is
active, prose gets safe card/exact-command guidance; `/clear-chat` clears that
draft to resume natural-language intake. Natural-language purchase restrictions
below still apply.

The configured live ASI adapter can interpret short conversational requests.
All existing slash commands and their exact self-mention normalization remain
available. No agent name, public profile, SDK pin, schema, purchase rule or
authorization boundary changed. Natural language cannot apply, approve, select a
payment outcome or execute a purchase. Use the exact Provider-generated application
and approval commands for those steps.

## Supported paths

When a draft awaits policy selection, reply with an exact ID from `/policies`.
That response is resolved deterministically against the current registry before
any model call. Invalid IDs repeat the available options without changing the
draft. Existing dates/requirements remain intact: a relative date is not resolved
again if the reply arrives on a later day. The usual exact leading self-mention
is removed by ACP routing before this check. See [follow-up repair](policy-followup-fix.md).

`confirm final date`, `run synthetic demo` and `confirm inputs` also use existing
state-specific deterministic handlers. They do not require model interpretation
and do not authorize purchase. An arbitrary `yes` is not purchase approval.

- Job-change questions: select one preloaded sample, inspect it through the
  Investigator, confirm an explicit final working date, cite its actual clause,
  preserve date contradictions and ask about existing personal cover.
- Inspection: request an exact preloaded ID or title (Horizon/Economy/Query are
  also supported product-name aliases). No uploads, URL fetching or arbitrary paths.
- Event stress assessment: explicitly request the supported illness-hospitalization
  illustration, supply member/date fields, review them and confirm before the
  existing Investigator stress operation runs. No event/treatment is invented.
- Dated plan comparison: collect cover baseline, synthetic member IDs/birth dates,
  annual budget, minimum shared limit, room requirement, proposed start, final
  working date, assumed new-employer start and explicit immediate/separate later
  illness-hospitalization scenarios. Review before execution. The existing engine
  needs those event fields; inspect plans instead if you do not want a clinical
  illustration. Missing health disclosures remain `unknown`, not absent.
- Quote: explicit product selection plus confirmed inputs. Provider still validates
  current catalogue/PDF terms, eligibility, budget, unknowns and disclosures. The
  existing-personal path remains blocked from an automatic duplicate-cover quote.
- Status: a literal reference supplied by the user, or a recent authoritative
  reference from this same draft. It uses the **read-only details SDK operation**
  and a compact factual summary. It cannot resume an approved operation or settle
  an unknown payment. Use the returned exact status command for reconciliation.
  After draft loss, ask for status and supply the original reference when prompted.

## Example: personal question and a fixed synthetic clause

This example uses an **injected test clock**, 2026-10-24 23:59 Asia/Kolkata; live
dates use the actual current clock. These are illustrative turns, not live success:

1. User: “I'm leaving my company in 3 days. Will my insurance continue?”
2. CoverWise first delivers: conversational messages may be processed by ASI;
   use synthetic data; commands avoid this parser. Then: “Which preloaded policy:
   existing-employer or existing-personal? These are fictional samples.”
3. User: “existing-employer”. The actual Investigator inspection is requested.
   CoverWise: “Proposed final working date: 2026-10-27 (Asia/Kolkata). Reply
   'confirm final date' or correct it. No scenario has run.”
4. User: “confirm final date”. CoverWise reports the contradiction: the actual
   synthetic PDF fixes **2026-12-31 inclusive**, p2/EMP-02, with its extracted
   evidence ID. It does not override the PDF or assert this is the user's policy.
5. User: “Correct final working date to 2026-12-31”. CoverWise requests date
   confirmation again. After “confirm final date”, it explains that listed members'
   employer protection ends on that date (or earlier expiry), with evidence, and
   asks about existing personal cover.
6. User: “I have no personal cover”. This is retained as an explicit baseline
   declaration; it does not create a profile, health declaration or illness event.

The preliminary continuation answer cites the policy; it does not require a
hospitalization. A gap calculation is part of the existing dated stress/comparison
tools, so its assumed next-employer date is asked only for that illustration.
There is no stand-alone generalized insurance or claims inference.

## Fast labelled demo

Send these as separate messages:

```text
Show me the job-change demo.
```

The reply first announces the supplied fictional profile and dates: self member-01
(1992-04-10), spouse member-02 (1994-08-15), explicit absence declarations, ₹30,000
annual budget, ₹10,00,000 minimum shared limit, uncapped private room, final work
2026-12-31, proposed start 2027-01-01, assumed new-employer start 2027-02-01,
illness event for member-02 on 2027-01-15 and separate later event 2027-02-10.

```text
run synthetic demo
```

This delegates a real catalogue request and Investigator assessment using the
existing preset only after that explicit selection. Horizon's January 1–30 wait
still excludes January 15. It is not the current user's profile or proof of cover.

To request a quote afterward:

```text
Request a quote for Horizon.
```

The agent displays an input review. Only the exact conversational phrase below
can confirm that reviewed data for a comparison/quote, never a purchase:

```text
confirm inputs
```

The resulting quote's application/approval commands must still be copied exactly
and sent separately. “Yes”, “buy it”, quoted instructions and model output cannot
approve anything. Review corrections invalidate the data review until it is shown
again. An arbitrary confirmation phrase outside its pending review does nothing.

## Partial answers and deterministic normalization

Supported examples: “my budget is 30000 rupees”, “I have no personal cover”, an
explicit YYYY-MM-DD date, and corrections naming another field. The model supplies
only verbatim spans; code resolves `today`, `tomorrow` and `in N days` (0–366) using
an injectable aware clock and the modern Asia/Kolkata UTC+05:30 offset. No tzdata
dependency is required. Other relative dates (for example next Friday) require
clarification. Explicit dates are bounded to 1900–2100. Final working dates require
confirmation before any scenario.

Currency requires explicit rupees/INR/₹ or integer paise. Conversion uses integer
arithmetic; ₹30,000.25 becomes 3,000,025 paise. Unsupported grouping, fractional
paise and missing units are rejected. No model chooses an amount or today's date.

For this small slice, supply members as comma-separated
`member-ID:YYYY-MM-DD:self/spouse/child`, optionally adding an explicit disclosure
after another colon. Omitted disclosures remain unknown. Separate declarations
can use `member-01:absent,member-02:unknown`. Use synthetic data only. Ages without
birth dates, open-ended diagnoses and arbitrary free-text policy uploads are not
supported. Requests can fall back to exact command guidance.

## Boundaries and privacy

The first privacy notice must be delivered before a model parse. Input is at most
1,500 characters; JSON output is at most 8,192 bytes. The existing async ASI adapter
uses model `asi1`, zero retries and a total model deadline of at most five seconds.
The installed OpenAI-compatible client exposes `response_format`; strict JSON
Schema behavior at the ASI endpoint was not tested. JSON-object output is locally
validated by extra-forbidding Pydantic contracts. Endpoint/JSON failure returns
honest `/start` fallback, not guessed results.

Only the latest message and pending-field name are sent to the parser, with a
fixed schema/public document list. Other drafts, sender/session values, existing
tool references, confirmation challenges and complete stored profiles are not
sent as model context. No raw text, disclosures, profiles or model payloads are
logged. The model cannot choose scope, references, payment mode or challenges;
status references come from the user or accepted same-scope SDK results.

Drafts are bounded to 128 sender/session pairs, expire after 15 minutes of
inactivity and keep at most eight recent authoritative references. They contain
normalized proposed/confirmed fields, pending question and minimal extracted
policy facts/citations, not message history. Busy turns reject overlapping natural
updates; clear/expiry identity checks prevent stale model/tool results from
updating a replacement draft. No lock waits for a human answer.

```text
/clear-chat
```

This removes only that observed sender/session's draft; no quotes, applications,
payments or purchases are deleted. It does not undo an already dispatched tool.
A restart loses drafts but persisted records remain available through the existing
authorized commands with the original scope. This is demo isolation, not verified
identity. Scope changes are not bypassed for convenience.

## Implementation and verification

`conversation.py` owns typed proposals, normalized draft state, review prompts and
the allowlisted dispatcher. Existing Coordinator methods still send real SDK
messages: `delegate(policy_id=...)`, `delegate(scenario=...)`, `recommend(...)`,
and `sandbox_operation(...)` with typed quote or read-only details commands.
Expected sender/session/request/deadline/input validation remains unchanged.
Material output uses deterministic existing presenters, not model paraphrases.

Local tests use mocked ASI HTTP but actual validated state/dispatch, SDK handlers,
PDF extraction, assessment and temporary SQLite Provider operations. They do not
construct outbound-capable agents, call live models or establish live transport.
| Exact command | Actual local result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; 69 packages resolved in 19ms on approved external-cache rerun. The initial restricted cache-lock denial was resolved without network or dependency changes. |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0, uagents 0.25.5, core 0.4.12, ACP 0.3.0; installed OpenAI-compatible client 3.37.0. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **353 passed in 99.95s**, no skips (309 previous cases plus 44 conversation cases). |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; all checked files formatted. |
| Focused privacy checks after strengthening INFO-level assertions | Exit 0; 2 passed, 42 deselected in 21.05s; no raw job text, birth dates or challenge strings logged. |
| `graphify update .` | Exit 0; 828 nodes, 2,524 edges, 41 communities; AST-only with no model calls. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, duplicates or same-endpoint collapse; one existing recursive paginator self-call. |

Cases cover deterministic India dates, final-date confirmation, real PDF
contradiction and unknown-linkage handling, partial corrections, unchanged personal
cover, absent disclosures staying unknown, integer currency, reviewed typed
recommendation/quote dispatch, explicit demos only, unsupported model actions and
fields, injection/quoted commands, yes/buy-it refusal, timeout fallback/zero retry,
scope isolation, reference follow-up, expiry/capacity, overlapping turns and clear.
Natural status was checked against a real pending sandbox payment: it stayed
unknown until the separate exact status command performed reconciliation.

Changed files: new `src/coverwise/conversation.py`, new
`tests/test_conversation.py`; `asi.py`, `agents.py`, `sandbox_ui.py`; README,
public template comments, architecture/communication/submission/verification
guidance, this document and required graph artifacts. No dependencies, SDK pins,
policy fixtures, database schema, transaction code or agent identities changed.

Required graph query/path/update operations were performed. The graph path from
Conversation to Coordinator is labelled inferred; runtime SDK delegation is
separately exercised by the local handler tests. Semantic docs/PDFs were not
rebuilt, and graph labels use hub fallbacks without model calls. Git remains the
existing untracked project tree; no staging, commits, registration, publication,
live startup, `.env` access or live database access occurred.

## Next user-run live messages

After the user reloads the updated local process with the same identities/database,
send the personal-question sequence above and observe the privacy notice, date
confirmation and clause contradiction. Then run the two labelled demo messages,
request a Horizon quote, review and confirm inputs. Stop at the quote unless you
deliberately choose the existing exact application/approval commands.

Check that “yes” and “buy it” do not purchase; ask for application status using
your own returned reference, and verify it is read-only when pending. Clear the
draft, request status again, and supply that same reference when prompted. A
different sender/session must be denied. Live model formatting, natural-language
interpretation and transport remain pending observation; no live success claimed.
