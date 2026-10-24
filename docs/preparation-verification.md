# Rehearsal/submission preparation — 2026-10-24

This is a reviewable local package, not a submission or publication. README was
rewritten for a new judge, with actual setup, local/mailbox boundaries, command
usage, technology limits and **not yet supplied** public URL placeholders.
New guides: [timed demo](demo-script.md), [rehearsal](rehearsal.md) and
[submission checklist](submission-checklist.md). No fabricated public links,
usage/activity metrics or eligibility/prize claims.

## Evidence separation

Accepted as **user-observed live**: ACP diagnostic delegation and two distinct
computed results; personal PDF extraction; stress preset, waiting boundary and
conflicting-date behavior; candidate evidence and existing-cover recommendation;
quote, application review, deliberate approval and sandbox completion; the same
completed payment/transaction/confirmation after a reported restart; concise
completed-status presentation. No agent was started by this preparation run.

Pending: corrected details pagination live, live duplicate approval, the full
intentional Provider timeout/recovery sequence, generic discovery and every-page
visual PDF review. A repeated status is not a duplicate-approval test. Existing
completion/restart references remain documented in presentation/rehearsal guides;
none were put into application behavior.

## Official source

The [official hackpack](https://www.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack)
was successfully retrieved with the web reader on 2026-10-24. TinyFish's PowerShell
wrapper was blocked by local execution policy; its installed command wrapper then
returned fetch failed. No policy/configuration or authentication was changed.
The checklist identifies newly verified deliverables separately from project
implementation claims. Pre-event development eligibility still requires organizer
clarification; the source does not resolve that project-specific question.

## Safe reset support

No reset capability existed beyond pytest mock resets and temporary sandbox-demo
databases. Added `python -m coverwise.demo_reset`, with dry-run as default and an
explicit execution/confirmation pair. Only the resolved, separately designated
`runtime/demo/rehearsal.sqlite3` is accepted. Default live and arbitrary paths,
traversal, aliases/reparse points, hard links, missing safety marker, active leases,
SQLite locks and unknown schemas are refused.

The Provider holds a process-lifetime shared OS file lease **only for that separate
demo path**, so an idle-but-running updated Provider still blocks reset. Reset
requires exclusive lease plus a SQLite exclusive transaction. Financial records
are cleared child-first atomically; file/schema remain. Ordinary live database
behavior and transaction rules are unchanged. `SandboxProvider.close()` releases
the rehearsal lease and refuses further transactions on that closed instance;
OS handles also release when the process exits. No transaction spans SDK waits.
Local filesystem/process ownership is trusted; do not delete a guard to bypass a
running owner or reset an old backend outside this procedure.

No workspace or live database was reset. Only disposable temporary reset-test
fixtures were cleared. `demo_reset --help` was run; no workspace execute or dry-run
was run. No `.env`, seed, identity or live record was opened/modified. Source PDFs
were read for offline verification and packaging, never rewritten.
Only the explicitly public `.env.example` template was read and corrected: Provider
is required and the template now matches the existing 15-second live default.
An existing `.env`/inherited setting is neither read nor changed by this task.

## Packaging and publication inspection

Found a real wheel omission: fixture/PDF paths assumed a source checkout and no
assets were packaged. Fixed a narrow asset-root selection and Hatch allowlist.
Wheel assets are exactly six authored JSON files (catalogue plus five sources)
and five generated PDFs. Installed runtime state uses the working directory;
source-checkout runtime defaults remain unchanged. Catalogue loading and PDF
generation use the same source/bundled asset root. SDK/dependency pins unchanged.

Built a wheel and source archive offline with existing uv/cached Hatch tooling;
no global/dev dependency install or upgrade. An initial standard-library extraction
check and a final actual `uv pip install --target` into an isolated temporary
directory both succeeded. The final install used the local wheel with
`--no-index --no-deps --no-cache` and the existing Python 3.12 interpreter;
only CoverWise itself was temporarily installed, with no dependency changes.
It was then loaded using `python -I` with that directory first. Assertions verified the imported
module came from the isolated package, all five JSON sources and PDFs were
available, all five PDFs actually extracted, the catalogue had three products,
and stress assessment produced employer excluded with a 31-day gap. No runtime
directory was created. This tests installed assets without live SDK agents/network
or a new dependency install; the temporary installation was removed afterward.

Artifact membership checks confirmed 11 wheel assets, source archive lock/setup
template, and no runtime databases, `.env`, key files or pycache records. The
wheel contains package code/assets; the source archive additionally includes
README, guides, tests, `uv.lock`, `.python-version` and the blank template.

`.gitignore` excludes `.env` variants except the public template, databases and
journals, runtime/lease files, caches, local private configuration directories,
keys/keystores and temporary output. Under `output/`, only five allowlisted PDFs
remain publication candidates. Historical stdout/JSON reports and rendered review
samples are intentionally local: the latter may contain consumed temporary
approval commands and are not packaged. `git check-ignore` confirmed exclusions
and that `.env.example`/the source PDFs remain eligible. No secret-bearing file
was opened for an audit. This is a filename/configuration/artifact-membership
inspection, not a blanket certification of all public content.

Public repository/profile/shared-chat/video URLs and licence choice remain user
actions. Review intended public files before later staging/publishing. Nothing
was staged, committed, pushed, registered, shared or published here.

## Verification notes

The first full run reported 307 passes and one existing timeout-recovery harness
failure. Its deliberately injected 50ms timeout was incorrectly reused for the
normal recovery request, which also missed that tiny budget. The test now keeps
all short-deadline/late-response assertions and uses the normal 3-second harness
budget only for recovery, with an explicit success assertion. Production deadlines,
correlation checks, worker repair and `.env` were not changed. The focused two
timeout cases then passed; a subsequent full run passed all 308 cases before the
final missing-lease-marker test was added.

| Exact command/check | Actual result |
| --- | --- |
| `uv lock --check --offline` | Exit 0; 69 packages resolved in 50ms on final approved external-cache rerun. A restricted rerun first hit the existing uv cache lock permission; no network or dependency change. |
| `.\.venv\Scripts\python.exe -m coverwise.doctor` | Exit 0; Python 3.12.0, uagents 0.25.5, core 0.4.12, AgentChatProtocol 0.3.0. Local compatibility only. |
| `.\.venv\Scripts\python.exe -m pytest -q` | Exit 0; **309 passed in 90.65s**, no skips (290 prior cases plus 19 reset safety cases). |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; all checks passed. |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; all checked files formatted. |
| `uv build --offline --out-dir runtime/review-build` | Exit 0; wheel and source archive built with cached tooling. Initial external uv cache permission was resolved by approved offline rerun. |
| Isolated local wheel install/import check | Exit 0; temporary `uv pip install --target` with no index/deps/cache succeeded. 11 bundled assets, five PDFs actually extracted, three catalogue products, employer excluded, 31-day gap; no runtime directory created. Source archive includes lock/setup/template/guides, no runtime/secret/cache artifacts. |
| `.\.venv\Scripts\python.exe -m coverwise.stress preset` | Exit 0; employer excluded, personal temporal passes/overall insufficient information; 31-day employer-protection gap, unknowns visible. |
| Documented command parser self-check | Exit 0; all 23 ACP command blocks validated against existing parsers; no executable ellipsis placeholders. |
| `graphify update .` | Exit 0; 747 nodes, 2,237 edges, 41 communities; AST-only, no model calls. |
| `graphify diagnose multigraph --max-examples 1` | Exit 0; no missing/dangling endpoints, duplicates or same-endpoint collapses; one existing recursive paginator self-call. |

Required graph query/path operations were performed. Semantic docs/PDFs were not
rebuilt, and community labels use hub fallbacks without an LLM. The graph audit
does not certify absence of earlier producer-side suppression. Git remains the
same untracked project tree (`??` for top-level source/docs/configuration paths);
`git diff --stat` is empty because files are untracked. Nothing staged/committed.

Rehearsal lease tests covered shared owners, closed owners, dry-run preservation,
explicit confirmation, live/arbitrary/traversal path refusal, native hard links,
simulated Windows symlink flags, SQLite locks, unknown schema, missing marker and
missing database. No actual symlink privilege or unsafe shell delete was needed.

Changed files: README, `.env.example`, `.gitignore`, `pyproject.toml`;
`src/coverwise/policies.py`, `catalogue.py`, `generate_policies.py`, `sandbox.py`,
new `demo_reset.py`; new `tests/test_demo_reset.py` and the narrow harness fix in
`tests/test_sandbox.py`; the three new guides, this record, historical presentation
artifact guidance and verification/architecture links; required graph artifacts.
No insurance rules, catalogue/PDF bytes, SDK pins or external agent profile were
changed.
