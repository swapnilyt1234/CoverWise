# Generated application-command repair

## Diagnosis

The reported literal `/apply` command parses successfully locally. Its quote ID
has the expected shape. The error text originates in the coordinator's command
parser, before SDK delegation or any Provider quote lookup; persisted profile
data cannot cause that particular error at this stage.

The confirmed defect is boundary whitespace handling: `split(" ")` left a copied
LF or CRLF attached to `success`. `ApplicationFields.payment_outcome` then raised
a Pydantic literal-validation error, hidden by the generic catch. A temporary
database reproduction passed with no line ending and failed with LF, with the
same natural-language-created quote and generated command. The live message's
exact whitespace was not captured, so this is not proof of its unseen bytes or
of the running process's code version.

## Repair and checks

The existing parser now strips surrounding whitespace before tokenization.
Interior single-space requirements and typed field validation remain intact.
Validation errors give fixed instructions for invalid references or demo outcomes
without echoing input values or approval challenges. No schema, pricing, expiry,
authorization, Provider persistence or purchase behavior changed.

Regression tests route both natural-language quotes (mocked ASI HTTP only) and
`/quote preset` through actual typed SDK handlers, real PDF assessment, temporary
SQLite persistence, generated commands and Provider application review. Twelve
combinations cover no suffix/LF/CRLF and the exact optional leading self-mention.
The persisted quote is identical in the review; each run creates one application
and zero payments. Command handling makes no model call. Two additional tests
check safe actionable validation errors.

Observed local verification:

- Before repair, the new round-trip regression stopped at the LF case:
  **1 failed, 2 passed** (17.60 s).
- `.\.venv\Scripts\python.exe -m pytest -q tests/test_conversation.py tests/test_sandbox.py`:
  **136 passed** (75.14 s).
- `.\.venv\Scripts\python.exe -m pytest -q`: **374 passed** (92.43 s).
  An initial full run had 373 passes and one new integration case without a review
  before its harness deadline. The new cases now use the existing live 15-second
  budget instead of the harness's 3-second default; production deadlines were
  not changed.
- `.\.venv\Scripts\python.exe -m ruff check .`: **passed**.
- `.\.venv\Scripts\python.exe -m ruff format --check .`: **55 files already formatted**.
- `graphify update .`: AST-only rebuild, **850 nodes / 2,589 edges / 43 communities**.
  `graphify diagnose multigraph --max-examples 1` found no missing/dangling endpoints,
  exact duplicates or collapsed edges; one pre-existing recursive self-call remains.

Git status remains the pre-existing untracked workspace (`??` project paths).
Nothing was staged or committed. No live record or secret file was read.

## Live retest (user execution only)

Stop the existing local process, then restart from the workspace with its existing
configuration, seeds and database:

```powershell
.\.venv\Scripts\python.exe -m coverwise.live
```

In the same ASI:One conversation, request a fresh synthetic quote through the
natural-language flow, or compare with:

```text
/quote preset
```

Copy that reply's actual generated apply command, including its quote ID. It
should return a review, not execute payment. Quote expiry remains enforced; do
not reuse an expired quote. Explicit approval remains a separate deliberate
command. No live agent or model was started for this repair, and no live database
was opened. Live confirmation remains pending.
