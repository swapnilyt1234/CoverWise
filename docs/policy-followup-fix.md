# Deterministic policy-selection follow-up

## Confirmed cause

The live user reached the policy question, then received the generic parsing
fallback for `existing-employer`. Inspection confirmed there was no special
`pending == "policy"` branch: the exact ID went back through `parse_intent`.
The fallback catches all parser exceptions, including JSON/schema validation
errors, so that wording does **not** establish an ASI API outage. The private live
exception is unknown; no raw model payload or secrets were inspected.

A regression first reproduced the identical fallback with a locally forced parser
error after a successful mocked initial intent. This required no network or API
failure. The defect was an unnecessary model dependency for a known pending
response; existing tests had supplied a mocked policy interpretation and masked it.

## Minimal change

`conversation.py` now constructs the existing typed `update` proposal from an
exact policy ID when that sender/session is awaiting selection. It validates
against the actual current `REGISTRY | CANDIDATES`, repeats those options for an
invalid selection, and reuses the existing update/inspection/date-confirmation
flow. The policy lookup helper also reads the current registry rather than a
module-import snapshot. Other draft fields are preserved, no preset is loaded,
and relative dates are not recalculated at selection time.

The Coordinator's existing exact leading-self-mention normalization is reused;
no second prefix parser was added. `confirm final date`, `run synthetic demo` and
`confirm inputs` were already deterministic before model parsing and remain so.
Tests now explicitly make the parser fail if called for these expected replies.
Wrong-phase confirmations still do not execute tools or authorize purchases.

Changed source: `src/coverwise/conversation.py`. Tests:
`tests/test_conversation.py` (seven new cases plus strengthened existing cases).
Documentation: this record, conversation usage and verification/README links;
required graph artifacts. No ASI adapter, insurance/transaction rules, schema,
agent identity, SDK pins or exact-command purchase authorization changed.

## Reproduction and verification

The complete regression uses a context-derived agent-address self-mention:

1. A job-change question proposes `in 3 days` and a budget through mocked model
   HTTP. The injected India date is 2026-10-24, resolving final work to October 27.
2. Advance the clock to the next day and disable model parsing entirely.
3. Send the exact prefixed `existing-employer` answer. Actual SDK inspection runs;
   October 27 and the budget are preserved, with no profile/demo defaults.
4. Send prefixed `confirm final date`. The real extracted p2/EMP-02 clause fixes
   December 31; the contradiction is reported instead of changing the PDF.

Additional cases check invalid IDs, a removed registry entry, different senders
and sessions, and no model call for the existing demo/review confirmations.
All use temporary PDFs/databases and local SDK handlers, not live agents.

Before repair: the targeted regression failed with the reported fallback.
After repair: all 51 conversation cases passed in 20.03s. The first full run
exposed a test-isolation defect: deleting/restoring a registry item changed its
insertion order and affected later stress tests. The registry regression now uses
a temporary replacement dictionary, preserving the original registry and order.
No stress-engine validation or behavior was changed to accommodate that test.

| Exact command | Final actual result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **360 passed in 68.24s**, no skips (353 prior cases plus seven regressions). |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; all checked files formatted. |
| `graphify update .` | Exit 0; 842 nodes, 2,567 edges, 31 communities; AST-only, no model calls. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, duplicates or same-endpoint collapse; one existing recursive paginator self-call. |

Required graph query/update/path operations were performed. Semantic documents
and PDFs were not rebuilt; graph labels use hub fallbacks without model calls.
An ambiguous path symbol was resolved using its qualified source identifier.

No `.env` access, live startup, network/model calls, dependency upgrade, database
reset, staging or commit. Git retains the pre-existing untracked project tree.
Live retesting of the corrected follow-up remains pending user observation.

## Next user-run messages

After reloading the updated agents, use the same conversation and send each as
a separate message; the actual self-mention added by ASI:One is supported:

```text
I'm leaving my company in 3 days. Will my insurance continue?
```

```text
existing-employer
```

```text
confirm final date
```

Expect the preserved explicit final-date proposal, followed by any actual
contradiction with the fixed synthetic PDF date. No real insurance coverage is
inferred. Exact application/approval commands remain required for purchases.
